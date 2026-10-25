"""Re-read fresh accepted OBJ exports with independent geometric checks.

Uses the unmodified reference validator, dense surface samples, Blender BVH,
and linear-program witnesses for shared-vertex triangle interiors. Failed
generation cases remain unqualified; this report only audits actual exports.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
from pathlib import Path
from collections import defaultdict
import argparse
import hashlib
import json
import subprocess
import sys
import time
import numpy as np
import trimesh
from scipy.optimize import linprog

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python'),str(ROOT)]
from measure_geometry import read_obj, topology, guide_alignment
from mesh_validation import validate_closed
from quad_quality import measure as quality
parser=argparse.ArgumentParser(); parser.add_argument('--matrix',nargs='+',type=Path,required=True); parser.add_argument('--label',default='current'); args=parser.parse_args()
OUT=ROOT/'tests/toilet-fresh-geometry'/args.label; OUT.mkdir(parents=True,exist_ok=True)


def samples(mesh):
    rng=np.random.default_rng(20261026)
    weights=rng.dirichlet([1,1,1],(len(mesh.faces),2))
    interior=np.einsum('tij,tkj->tki',mesh.triangles.transpose(0,2,1),weights).reshape(-1,3)
    return np.r_[mesh.vertices,mesh.triangles_center,mesh.vertices[mesh.edges_unique].mean(axis=1),interior]


def distances(points,mesh,tolerance):
    error=[]
    for first in range(0,len(points),2048):
        error.extend(trimesh.proximity.closest_point(mesh,points[first:first+2048])[1])
    error=np.asarray(error)
    return dict(passed=bool(error.max()<=tolerance),samples=len(points),maximum=float(error.max()),
                p95=float(np.percentile(error,95)),overTolerance=int(np.count_nonzero(error>tolerance)),
                worstPoint=points[int(error.argmax())].tolist())


def adjacent_interiors(vertices,faces):
    incidence=defaultdict(list)
    for i,face in enumerate(faces):
        for vertex in face: incidence[vertex].append(i)
    pairs=sorted({(a,b) for connected in incidence.values() for a in connected for b in connected if a<b})
    triangles=[[vertices[[f[0],f[i],f[i+1]]] for i in range(1,len(f)-1)] for f in faces]
    inequality=np.r_[np.c_[-np.eye(4),np.ones(4)],[[1,1,0,0,1],[0,0,1,1,1]]]
    overlaps,unresolved,tested=[],[],0
    for index,(a,b) in enumerate(pairs):
        found=False
        for ta in triangles[a]:
            for tb in triangles[b]:
                if np.any(ta.max(axis=0)<tb.min(axis=0)) or np.any(tb.max(axis=0)<ta.min(axis=0)): continue
                equality=np.c_[ta[1]-ta[0],ta[2]-ta[0],-(tb[1]-tb[0]),-(tb[2]-tb[0]),np.zeros(3)]
                result=linprog([0,0,0,0,-1],A_eq=equality,b_eq=tb[0]-ta[0],A_ub=inequality,b_ub=[0,0,0,0,1,1],bounds=[(0,None)]*4+[(0,1/3)],method='highs')
                tested+=1
                if result.status not in (0,2): unresolved.append(dict(faces=[a,b],status=result.status))
                if result.success and result.x[-1]>1e-7:
                    error=float(np.linalg.norm(equality@result.x-(tb[0]-ta[0])))
                    if error<=1e-9:
                        overlaps.append(dict(faces=[a,b],minimumBarycentric=float(result.x[-1]),equalityError=error)); found=True; break
                    unresolved.append(dict(faces=[a,b],equalityError=error))
            if found: break
        if (index+1)%2500==0: print('  independent adjacent-face LPs:',index+1,'of',len(pairs),flush=True)
    return dict(passed=not overlaps and not unresolved,adjacentFacePairs=len(pairs),trianglePrograms=tested,overlaps=overlaps,unresolved=unresolved,
                scope='Independent HiGHS feasibility/maximum-interior-margin problems for every shared-vertex face pair after triangle AABB pruning. Reports strict interior contacts above 1e-7 barycentric margin; boundary-only contacts and smaller margins are outside this supplemental test.')


source_file=ROOT/'assets/models/toilet.obj'; sv,sf=read_obj(source_file); source=trimesh.Trimesh(sv,sf,process=False); source_samples=samples(source)
cases,unqualified=[],[]; hashes={str(p):hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
    ('assets/models/toilet.obj','engine/targets/zbrush/clone/mesh_validation.py','tests/check_toilet_overlap_blender.py','tests/verify_toilet_fresh_geometry.py')}
for matrix in args.matrix:
    folder=matrix.parent
    for case in json.loads(matrix.read_text())['cases']:
        if case['state']!='complete': unqualified.append(dict(matrix=str(matrix),**case)); continue
        obj=folder/case['name']/'output.obj'; digest=hashlib.sha256(obj.read_bytes()).hexdigest()
        # Equal geometry can still accompany different authored curves/paths.
        # Keep every case so no input's guide-fit check is skipped by an OBJ hash.
        start=time.monotonic(); v,f=read_obj(obj); packet=json.loads((obj.parent/'mesh.json').read_text()); worker_report=json.loads((obj.parent/'report.json').read_text())
        exact=bool(digest==worker_report['outputSha256'] and np.allclose(v,packet['vertices'],atol=1e-10,rtol=0) and f==packet['faces'])
        target=json.loads((obj.parent/'settings.json').read_text())['target']; tolerance=.5*np.sqrt(source.area/target)
        print(case['name'],'checking exported geometry',flush=True)
        reference=validate_closed(sv,sf,v,f,target=target); shape=quality(v,f,target); stats,_,edges=topology(v,f)
        diagonal={}
        for name,a,b in (('02',[0,1,2],[0,2,3]),('13',[0,1,3],[1,2,3])):
            indices=np.asarray(f); mesh=trimesh.Trimesh(v,np.r_[indices[:,a],indices[:,b]],process=False)
            diagonal[name]=dict(sourceToOutput=distances(source_samples,mesh,tolerance),outputToSource=distances(samples(mesh),source,tolerance))
        adjacent=adjacent_interiors(v,f)
        bvh_file=OUT/(case['name']+'-bvh.json')
        with (OUT/(case['name']+'-blender.log')).open('w',encoding='utf-8') as log:
            subprocess.run([r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe','--background','--threads','2','--python',str(ROOT/'tests/check_toilet_overlap_blender.py'),'--',str(bvh_file),str(obj.resolve())],check=True,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=180)
        bvh=json.loads(bvh_file.read_text()); curves=json.loads((obj.parent/'curves.json').read_text())['curves']; valid_edges={tuple(sorted(e)) for e in edges}; fits=[]
        for curve,path in zip(curves,packet['guidePaths']):
            ids=path['vertices']; points=np.asarray(curve); arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
            sampled=np.array([np.interp(np.linspace(0,arc[-1],257),arc,points[:,i]) for i in range(3)]).T
            fit=guide_alignment(v,list(zip(ids[:-1],ids[1:])),sampled)
            closed=bool(np.linalg.norm(points[0]-points[-1])<1e-8); unique=ids[:-1] if closed else ids
            path_valid=(ids[0]==ids[-1])==closed and len(set(unique))==len(unique) and all(tuple(sorted(e)) in valid_edges for e in zip(ids[:-1],ids[1:]))
            fits.append(dict(pathValid=path_valid,measurement=fit,passed=bool(path_valid and fit['p95Distance']<=.4*tolerance and fit['p95UnsignedTangentAngleDegrees']<=30)))
        passed=exact and reference['passed'] and shape['passed'] and adjacent['passed'] and bvh['passed'] and len(fits)==len(curves) and all(x['passed'] for x in fits) and all(x['passed'] for d in diagonal.values() for x in d.values())
        producer=case.get('producerKind','worker')
        record=dict(name=case['name'],job=case['job'],producerKind=producer,outputFile=str(obj),outputSha256=digest,sourceSha256=hashes['assets/models/toilet.obj'],exportMatchesProducer=exact,exportMatchesWorker=exact if producer=='worker' else None,
                    passed=bool(passed),target=target,tolerance=float(tolerance),referenceValidation=reference,shape=shape,denseDiagonals=diagonal,adjacentInteriors=adjacent,blenderBVH=bvh,guideFits=fits,elapsedSeconds=time.monotonic()-start)
        cases.append(record); print(case['name'],'independent validation',passed,'seconds',round(record['elapsedSeconds'],1),flush=True)
        (OUT/'result.json').write_text(json.dumps(dict(complete=False,passed=False,cases=cases,unqualifiedCases=unqualified,sourceHashes=hashes),indent=2)+'\n')
report=dict(complete=True,passed=bool(cases) and all(c['passed'] for c in cases),cases=cases,unqualifiedCases=unqualified,sourceHashes=hashes,
            scope='Actual exported OBJ re-read independently: unchanged reference validator, dense bidirectional checks under both quad diagonals, separate Blender BVH nonadjacent test, LP adjacent-interior tests, topology/shape and actual guide-edge paths. This audits accepted exports only; unqualified generation cases are not converted into passes.')
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)
