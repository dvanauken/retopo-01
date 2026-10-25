"""Isolate tangent-aligned sliding guide fitting on a retained real layout.

The exact executed production refinement plus the one pin-residual substitution
is retained. This experiment neither publishes a mesh nor weakens acceptance.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
import argparse,hashlib,inspect,json,sys,time,traceback
from pathlib import Path
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj
parser=argparse.ArgumentParser()
parser.add_argument('--layout',type=Path,required=True)
parser.add_argument('--label',required=True)
parser.add_argument('--weight',type=float,default=8.)
parser.add_argument('--cases',nargs='+',default=['bowl-only-1800'])
args=parser.parse_args()
if not args.label.replace('-','').isalnum(): raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-tangent-pins'/args.label;OUT.mkdir(parents=True,exist_ok=True)
raw=json.loads(args.layout.read_text()); seed=raw['seed']
(OUT/'layout.json').write_bytes(args.layout.read_bytes())
source,triangles=read_obj(ROOT/'assets/models/toilet.obj'); source=np.asarray(source);triangles=np.asarray(triangles)
mesh=trimesh.Trimesh(source,triangles,process=False);spacing=np.sqrt(mesh.area/1800)
faces=np.asarray(raw['faces']); edges=cq._edges(faces)
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('curved_quad.py','surface_distance.py','surface_intersections.py','quad_quality.py','assets/models/toilet.obj','tests/probe_toilet_tangent_pins.py')}
results,errors=[],[]

def pin_residual(points):
    nearest=[]
    for curve,begin,end in pin_groups:
        _,parameters=cq._nearest_curve(points[begin:end],curve)
        arc=cq._arc(curve)
        projected=np.array([np.interp(parameters,arc,curve[:,i]) for i in range(3)]).T
        if np.linalg.norm(curve[0]-curve[-1])>=1e-8:
            projected[0],projected[-1]=curve[0],curve[-1]
        nearest.extend(projected)
    return ((points-np.asarray(nearest))*80+(points-targets)*4).ravel()/spacing

def tangent_residual(points):
    vectors=points[tangent_edges[:,1]]-points[tangent_edges[:,0]]
    vectors/=np.maximum(1e-12,np.linalg.norm(vectors,axis=1))[:,None]
    return np.cross(vectors,tangent_directions).ravel()*args.weight

source_code=inspect.getsource(cq._refine)
old='(q[pins] - targets).ravel() / spacing * 80'
assert source_code.count(old)==1
source_code=source_code.replace(old,'pin_residual(q[pins])')
owner_anchor='    sparsity = lil_matrix('
assert source_code.count(owner_anchor)==1
source_code=source_code.replace(owner_anchor,'    groups += [(len(tangent_edges)*3,tangent_edges)]\n'+owner_anchor)
residual_anchor='np.maximum(np.linalg.norm(surface_delta, axis=1) / spacing - .35, 0) * 40]'
assert source_code.count(residual_anchor)==1
source_code=source_code.replace(residual_anchor,residual_anchor[:-1]+', tangent_residual(q)]')
(OUT/'executed-refine.py').write_text(inspect.getsource(pin_residual)+'\n'+inspect.getsource(tangent_residual)+'\n'+source_code)
namespace=dict(vars(cq),pin_residual=pin_residual,tangent_residual=tangent_residual);exec(source_code,namespace)

def save(complete):
    (OUT/'result.json').write_text(json.dumps(dict(complete=complete,cases=results,errors=errors,seed=seed,
        sourceHashes=hashes,layoutSha256=hashlib.sha256(args.layout.read_bytes()).hexdigest(),layoutSource=str(args.layout),
        executedRefinementSha256=hashlib.sha256((OUT/'executed-refine.py').read_bytes()).hexdigest(),
        implementationUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),
        scope='Isolated fitting experiment on a retained genuine layout. Pin residual is distance to authored polyline (80) plus original target anchor (4), with open endpoints fixed. All original acceptance gates including full surface bounds and mixed quad diagonals remain unchanged. Normalized guide-edge cross-tangent residual is added with weight '+str(args.weight)+'. Directions are closest authored-segment tangents at current edge midpoints and refreshed between passes. No production publication.'),indent=2)+'\n')

try:
    for name in args.cases:
        curve_file=ROOT/'tests/toilet-stress'/name/'curves.json'
        curves=[np.asarray(c) for c in json.loads(curve_file.read_text())['curves']]
        positions=np.asarray(raw['vertices']);paths=[];pin_rows=[];target_rows=[];pin_groups=[]
        for curve in curves:
            path,pins,targets=cq._guide_path(positions,edges,curve,spacing)
            pin_groups.append((curve,len(pin_rows),len(pin_rows)+len(pins)))
            paths.append(path);pin_rows.extend(pins);target_rows.extend(targets)
        pins=np.asarray(pin_rows,dtype=int); targets=np.asarray(target_rows).reshape(-1,3)
        for pin in set(pin_rows):
            shared=targets[pins==pin]
            assert np.max(np.linalg.norm(shared-shared[0],axis=1))<=spacing*.1, 'Competing pins'
        record=dict(name=name,curvesSha256=hashlib.sha256(curve_file.read_bytes()).hexdigest(),attempts=[],qualified=False)
        results.append(record)
        for iteration in range(5):
            tangent_edges=[];tangent_directions=[]
            for path,curve in zip(paths,curves):
                pe=np.array(list(zip(path['vertices'][:-1],path['vertices'][1:])),dtype=int)
                _,parameters=cq._nearest_curve(positions[pe].mean(axis=1),curve)
                indices=np.clip(np.searchsorted(cq._arc(curve),parameters,side='right')-1,0,len(curve)-2)
                direction=(curve[1:]-curve[:-1])[indices]
                direction/=np.maximum(1e-12,np.linalg.norm(direction,axis=1))[:,None]
                tangent_edges.extend(pe);tangent_directions.extend(direction)
            tangent_edges=np.asarray(tangent_edges,dtype=int);tangent_directions=np.asarray(tangent_directions)
            namespace['tangent_edges']=tangent_edges
            start=time.monotonic(); positions,refinement=namespace['_refine'](mesh,positions,faces,edges,pins,targets,1800)
            quality=cq.quad_quality(positions,faces,1800);fit=cq._guide_fit(positions,paths,curves)
            contacts=cq.surface_intersections(positions,faces,both_quad_diagonals=True)
            guided=all(p['p95Distance']<=.2*spacing and p['p95TangentAngleDegrees']<=30 for p in fit)
            eligible=quality['passed'] and contacts['passed'] and guided
            surface=cq.validate_surface(source,triangles,positions,faces,1800,whole_surface=eligible)
            qualified=bool(eligible and surface['passed']);record['qualified']=qualified
            record['attempts'].append(dict(iteration=iteration,refinement=refinement,quality=quality,guideFit=fit,contacts=contacts,surface=surface,qualified=qualified,elapsedSeconds=time.monotonic()-start))
            (OUT/f'{name}-{iteration}.json').write_text(json.dumps(dict(vertices=positions.tolist(),faces=faces.tolist())))
            save(False)
            print(name,iteration,'quality',quality['passed'],'contacts',contacts['passed'],'guide',guided,'surface',surface['passed'],'qualified',qualified,'seconds',round(time.monotonic()-start,1),flush=True)
            if qualified: break
except Exception:
    errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:save(True)
