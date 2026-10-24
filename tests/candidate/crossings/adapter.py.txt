"""Original-input interface to the recovered guided-remesher reference core.

This adapter is new engineering code, not a transcription of a native UI.
Unsupported native branches remain explicit failures. See README.md.
"""
from __future__ import annotations

import argparse
import builtins
from collections import Counter, defaultdict
from contextlib import contextmanager, ExitStack
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback

import numpy as np

HERE=Path(__file__).resolve().parent
TARGET=HERE.parent
RESEARCH=TARGET/'experiments/python'
sys.path.insert(0,str(RESEARCH))
from recovered_torus_full_remesh import prepare
from recovered_cholmod_reference_backend import initialize, source_paths, DLL, EXPECTED

_LOCK=threading.Lock()

class OutputValidationError(RuntimeError):
    def __init__(self,reason,positions,faces,validation):
        super().__init__(reason+': '+json.dumps(validation))
        self.positions=positions;self.faces=faces;self.validation=validation

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_obj(path):
    """Read only geometry. Reject unsupported records rather than drop attributes."""
    vertices=[]; faces=[]
    for number,line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(),1):
        fields=line.partition('#')[0].split()
        if not fields: continue
        if fields[0]=='v':
            if len(fields)!=4: raise ValueError(f'OBJ line {number}: exactly three position coordinates required')
            vertices.append([float(x) for x in fields[1:]])
        elif fields[0]=='f':
            if len(fields)!=4 or any('/' in x for x in fields[1:]):
                raise ValueError(f'OBJ line {number}: this recovered backend requires bare triangle indices; triangulate explicitly and retain that input')
            row=[]
            for text in fields[1:]:
                index=int(text)
                if index==0: raise ValueError('OBJ vertex zero is invalid')
                row.append(index-1 if index>0 else len(vertices)+index)
            faces.append(row)
        elif fields[0] not in {'o','s'}:
            raise ValueError(f'OBJ line {number}: unsupported record {fields[0]!r}; attributes/groups must not be silently discarded')
    return np.asarray(vertices,dtype=np.float64),np.asarray(faces,dtype=np.int64)

def check_inputs(vertices,triangles,curves,target,mode,allow_empty_curves=False):
    v=np.asarray(vertices,dtype=np.float64); f=np.asarray(triangles)
    if v.ndim!=2 or v.shape[1:]!=(3,) or len(v)<4 or not np.isfinite(v).all():
        raise ValueError('Finite three-coordinate source positions required')
    if f.ndim!=2 or f.shape[1:]!=(3,) or not len(f) or not np.issubdtype(f.dtype,np.integer):
        raise ValueError('Nonempty integer triangle array required')
    if f.min()<0 or f.max()>=len(v): raise ValueError('Source triangle index out of range')
    if len(np.unique(f))!=len(v): raise ValueError('Unused source vertices must be removed explicitly')
    if np.any(np.sort(f,axis=1)[:,1:]==np.sort(f,axis=1)[:,:-1]): raise ValueError('Repeated source face index')
    edges=defaultdict(list)
    for row in f:
        for a,b in zip(row,np.roll(row,-1)):
            edges[tuple(sorted((int(a),int(b))))].append((int(a),int(b)))
    if any(len(incident)>2 for incident in edges.values()): raise ValueError('EDGE-01: nonmanifold source edge')
    if any(len(incident)==1 for incident in edges.values()):
        raise NotImplementedError('CORE-03: recovered backend requires closed surfaces; open terrain remains active implementation work')
    if any(a!=d or b!=c for ((a,b),(c,d)) in edges.values()): raise ValueError('Inconsistent source winding')
    area=np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)
    if np.any(area==0): raise ValueError('EDGE-01: zero-area source triangle')
    if type(target) is not int or not 1<=target<=1_000_000: raise ValueError('Positive integer target (at most one million) required')
    if type(mode) is not int or mode not in (1,2):
        raise NotImplementedError('CORE-04: choose explicit homogeneous guide mode 1 or 2, not UI strength')
    if not isinstance(curves,(list,tuple)) or not curves and not allow_empty_curves: raise ValueError('At least one declared guide curve required')
    drawn=[]
    for curve in curves:
        points=np.asarray(curve,dtype=np.float64)
        if points.ndim!=2 or points.shape[1:]!=(3,) or len(points)<2 or not np.isfinite(points).all():
            raise ValueError('Each curve needs at least two finite XYZ points in source coordinates')
        if np.any(np.linalg.norm(np.diff(points,axis=0),axis=1)==0):
            raise ValueError('EDGE-02: consecutive coincident guide samples')
        drawn.append(points)
    return v,f,drawn

@contextmanager
def no_construction_io():
    """Selected Python API guard, not an operating-system sandbox.

    A declared independently built CHOLMOD function is preloaded before this
    region. Other APIs or already held function pointers are not certified.
    Global hooks require a single construction per process at a time.
    """
    originals=[(Path,'open',Path.open),(builtins,'open',builtins.open),
               (np,'fromfile',np.fromfile),(ctypes,'CDLL',ctypes.CDLL),
               (subprocess,'Popen',subprocess.Popen)]
    if hasattr(ctypes,'WinDLL'): originals.append((ctypes,'WinDLL',ctypes.WinDLL))
    def forbidden(*args,**kwargs):
        raise PermissionError('Filesystem/native-process access forbidden during reference construction')
    for module,name,_ in originals: setattr(module,name,forbidden)
    try: yield
    finally:
        for module,name,original in originals: setattr(module,name,original)

def construct(vertices,triangles,curves,*,target=500,guide_mode=2,normalize=False,
              feature_policy='native-qualified',sharp_angle=30.,solid_method='auto'):
    """Return final source-frame mesh and provenance, or an explicit exception.

    Curves share the source coordinate system. Repeating the first sample
    closes a curve. Explicit mode 1 is field guidance; mode 2 also enables the
    recovered strict edge-preservation consumers. No per-curve mixing yet.
    Normalization is an adapter choice, not recovered host serialization.
    """
    if feature_policy not in ('native-qualified','preserve-sharp'):raise ValueError('Unknown feature policy')
    preserve=feature_policy=='preserve-sharp'
    if solid_method not in ('auto','field','planar'):raise ValueError('Unknown solid method')
    if not preserve and solid_method!='auto':raise ValueError('Explicit solid methods require preserve-sharp')
    if not np.isfinite(sharp_angle) or not 0<sharp_angle<180:raise ValueError('Sharp angle must lie strictly between zero and 180 degrees')
    if preserve and guide_mode!=2:raise NotImplementedError('Preserve-sharp currently requires mode 2 for every user and automatic curve')
    v,f,drawn=check_inputs(vertices,triangles,curves,target,guide_mode,allow_empty_curves=preserve)
    user_count=len(drawn);source_features=[];automatic_count=0
    from mesh_validation import validate_closed
    if preserve:
        import features
        import planar
        domain=None
        if solid_method!='field':
            try:domain=planar.decompose(v,f,sharp_angle)
            except NotImplementedError:
                if solid_method=='planar':raise
        use_planar=solid_method=='planar' or domain is not None
        if use_planar:
            with _LOCK:
                local={Path(module.__file__).resolve() for module in list(sys.modules.values()) if getattr(module,'__file__',None) and Path(module.__file__).resolve().parent in (RESEARCH,HERE)}
                paths=sorted({Path(__file__).resolve(),*local});before={str(p):digest(p) for p in paths}
                center=(v.min(axis=0)+v.max(axis=0))*.5 if normalize else np.zeros(3);scale=2/float(np.ptp(v,axis=0).max()) if normalize else 1.
                transformed=(v-center)*scale;transformed_curves=[(c-center)*scale for c in drawn];start=time.monotonic()
                with no_construction_io():positions,faces,metadata=planar.construct_planar(transformed,f,transformed_curves,target=target,sharp_angle=sharp_angle,domain=domain if not normalize else None)
                positions=positions/scale+center;_,source_features=features.feature_curves(v,f,sharp_angle)
                validation=validate_closed(v,f,positions,faces,target=target,physical_edges=source_features)
                if not validation['passed']:raise OutputValidationError('Planar output validation failed',positions,faces,validation)
                if before!={str(p):digest(p) for p in paths}:raise RuntimeError('Planar construction sources changed')
                metadata.update(sourceHashes=before,sourcesStable=True,closedValidation=validation,elapsedSeconds=time.monotonic()-start,
                                userCurveCount=user_count,requestedSolidMethod=solid_method,actualSolidMethod='planar',
                                sourceAngularFeatureEdges=[list(e) for e in source_features],
                                selectedApiGuard='Selected filesystem/native-process APIs denied during actual planar construction',
                                referenceBackend=dict(initialized=False,required=False),
                                coordinateMap=dict(sourceToCore='(position-center)*scale, float64 planar charts',center=center.tolist(),scale=scale,nativeHostTransform=False,float32Narrowing=False))
                metadata['outputCreases']=features.output_creases(positions,faces,sharp_angle)
                return positions,faces,metadata
        automatic,source_features=features.feature_curves(v,f,sharp_angle)
        drawn,automatic_count=features.append_unique(drawn,automatic)
        if not drawn:raise ValueError('No user curves or angular features; no-guide dispatch is separate')
    with _LOCK, ExitStack() as stack:
        policy_diagnostics=stack.enter_context(features.override_core(sharp_angle)) if preserve else None
        initialize(); backend_paths=source_paths()
        local={Path(module.__file__).resolve() for module in list(sys.modules.values())
               if getattr(module,'__file__',None) and Path(module.__file__).resolve().parent in (RESEARCH,HERE)}
        paths=sorted({Path(__file__).resolve(),*backend_paths,*local})
        before={str(path):digest(path) for path in paths}
        center=(v.min(axis=0)+v.max(axis=0))*.5 if normalize else np.zeros(3)
        scale=2/float(np.ptp(v,axis=0).max()) if normalize else 1.
        source=np.asarray((v-center)*scale,dtype='<f4')
        source_curves=[np.asarray((curve-center)*scale,dtype='<f4') for curve in drawn]
        if not np.isfinite(source).all() or any(not np.isfinite(x).all() for x in source_curves):
            raise ValueError('Positions overflow the recovered float32 frame')
        start=time.monotonic()
        with no_construction_io():
            full=prepare(source,np.asarray(f,dtype='<i4'),target,source_curves,guide_mode)
        elapsed=time.monotonic()-start
        after={str(path):digest(path) for path in paths}
        if before!=after: raise RuntimeError('Construction sources changed during execution')
        finished=full['finishedMesh']
        positions=finished['positions'].astype(np.float64)/scale+center
        faces=[list(map(int,row)) for row in finished['faces']]
        if not len(positions) or not faces or not np.isfinite(positions).all():
            raise RuntimeError('Constructor returned empty/nonfinite output')
        validation=validate_closed(v,f,positions,faces,target=target,physical_edges=source_features)
        if not validation['passed']:raise OutputValidationError('Recovered field output validation failed',positions,faces,validation)
        metadata=dict(backend='recovered-reference',nativeComparisonPerformed=False,
                      generalAlgorithmRecovered=False,guideMode=guide_mode,target=target,
                      closedValidation=validation,requestedSolidMethod=solid_method,actualSolidMethod='field',
                      elapsedSeconds=elapsed,sourceHashes=before,sourcesStable=True,
                      selectedApiGuard='Path.open,builtins.open,numpy.fromfile,ctypes.CDLL/WinDLL,subprocess.Popen denied during construction',
                      referenceBackend=dict(path=str(DLL),sha256=EXPECTED,origin='independently compiled SuiteSparse 5.6.0; no Maxon DLL'),
                      coordinateMap=dict(sourceToCore='(position-center)*scale',center=center.tolist(),scale=scale,
                                         nativeHostTransform=False,float32Narrowing=True),
                      featurePolicy=feature_policy,engineeringPolicyDiagnostics=policy_diagnostics,
                      userCurveCount=user_count,automaticCurvesAdded=automatic_count,
                      sourceAngularFeatureEdges=[list(e) for e in source_features],
                      sourceVertices=len(v),sourceTriangles=len(f),vertices=len(positions),faces=len(faces),
                      faceSizes=dict(Counter(map(len,faces))),
                      limitations=['Bounded recovered constructor; unsupported branches raise explicitly.',
                                   'A completed construction alone does not qualify native correspondence or mesh validity.',
                                   'No source attributes, crease/group transfer, symmetry or UI-strength conversion is implied.'])
        if preserve:
            metadata['outputCreases']=features.output_creases(positions,faces,sharp_angle)
            metadata['limitations'].append('Preserve-sharp uses explicit engineering choices: all angular conditioning locks, complete graph fallback if needed, robust parallel skipping and binary output-dihedral crease export. Arbitrary source tag/partial-strength transfer is not implemented.')
        return positions,faces,metadata

def write_obj(path,vertices,faces):
    with Path(path).open('w',encoding='utf-8',newline='\n') as stream:
        stream.write('# Guided retopology reference output; see result.json for method and scope\n')
        for row in vertices: stream.write('v '+' '.join(format(float(x),'.17g') for x in row)+'\n')
        for row in faces: stream.write('f '+' '.join(str(int(x)+1) for x in row)+'\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True,help='Geometry-only triangle OBJ')
    parser.add_argument('--curves',type=Path,required=True,help='JSON with curves, all in source coordinates')
    parser.add_argument('--target',type=int,default=500)
    parser.add_argument('--guide-mode',type=int,choices=[1,2],default=2)
    parser.add_argument('--normalize',action='store_true',help='Engineering adapter normalization; may change native byte agreement')
    parser.add_argument('--feature-policy',choices=['native-qualified','preserve-sharp'],default='native-qualified')
    parser.add_argument('--sharp-angle',type=float,default=30.,help='Geometric feature threshold in degrees for preserve-sharp')
    parser.add_argument('--solid-method',choices=['auto','field','planar'],default='auto',help='Auto uses planar constrained charts for eligible sharp polyhedra; field explicitly selects the recovered route')
    parser.add_argument('--surface',choices=['closed','heightfield'],default='closed',help='Heightfield is an explicit engineering enclosure route, requiring preserve-sharp/mode 2')
    parser.add_argument('--surface-tolerance',type=float,help='Heightfield maximum sampled surface deviation in source units')
    parser.add_argument('--boundary-tolerance',type=float,help='Heightfield maximum sampled border deviation in source units')
    parser.add_argument('--guide-tolerance',type=float,help='Heightfield interior guide-to-edge p95 distance in source units')
    parser.add_argument('--output',type=Path,required=True,help='New retained directory; never overwritten')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,constructionCompleted=False,nativeComparisonPerformed=False)
    try:
        (args.output/'input.obj').write_bytes(args.input.read_bytes())
        (args.output/'curves.json').write_bytes(args.curves.read_bytes())
        result['inputs']=[dict(originalPath=str(original.resolve()),retainedName=name,sha256=digest(args.output/name)) for original,name in [(args.input,'input.obj'),(args.curves,'curves.json')]]
        vertices,faces=read_obj(args.output/'input.obj')
        packet=json.loads((args.output/'curves.json').read_text(encoding='utf-8-sig'))
        if not isinstance(packet,dict) or set(packet)!={'coordinateFrame','curves'} or packet['coordinateFrame']!='source':
            raise ValueError('Curve schema requires exactly coordinateFrame="source" and curves=[[[x,y,z],...],...]')
        if args.surface=='heightfield':
            if args.feature_policy!='preserve-sharp' or args.guide_mode!=2:
                raise ValueError('Heightfield requires explicitly selected --feature-policy preserve-sharp --guide-mode 2')
            from terrain import construct_heightfield
            positions,polygons,metadata=construct_heightfield(vertices,faces,packet['curves'],target=args.target,normalize=args.normalize,sharp_angle=args.sharp_angle,solid_method=args.solid_method,surface_tolerance=args.surface_tolerance,boundary_tolerance=args.boundary_tolerance,guide_tolerance=args.guide_tolerance)
        else:
            if any(x is not None for x in [args.surface_tolerance,args.boundary_tolerance,args.guide_tolerance]):raise ValueError('These explicit tolerance controls currently apply only to the heightfield route')
            positions,polygons,metadata=construct(vertices,faces,packet['curves'],target=args.target,guide_mode=args.guide_mode,normalize=args.normalize,feature_policy=args.feature_policy,sharp_angle=args.sharp_angle,solid_method=args.solid_method)
        result.update(metadata,constructionCompleted=True,passed=False)
        write_obj(args.output/'output.obj',positions,polygons)
        offsets=np.cumsum([0]+list(map(len,polygons)),dtype=np.int64)
        np.savez(args.output/'output.npz',positions=positions,faceOffsets=offsets,
                 faceIndices=np.asarray([x for row in polygons for x in row],dtype=np.int64))
        if 'outputCreases' in metadata:
            (args.output/'features.json').write_text(json.dumps(metadata['outputCreases'],indent=2)+'\n',encoding='utf-8')
        result.update(metadata,passed=True,constructionCompleted=True,
                      outputSha256=digest(args.output/'output.obj'))
    except Exception as exception:
        result.update(error=traceback.format_exc())
        if isinstance(exception,OutputValidationError):
            write_obj(args.output/'failed-output.obj',exception.positions,exception.faces)
            result.update(constructionCompleted=True,validationPassed=False,closedValidation=exception.validation,
                          failedGeometryArtifact='failed-output.obj',failedGeometrySha256=digest(args.output/'failed-output.obj'))
    result['adapterSha256']=digest(__file__)
    (args.output/'adapter.py.txt').write_bytes(Path(__file__).read_bytes())
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ['passed','constructionCompleted','vertices','faces','error']}))
    return 0 if result['passed'] else 1

if __name__=='__main__': raise SystemExit(main())
