"""Measure whether path ownership, rather than positions, limits the long guide."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import hashlib,json,sys
from pathlib import Path
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj
OUT=ROOT/'tests/toilet-path-reselection';OUT.mkdir(exist_ok=False)
folder=ROOT/'tests/toilet-sampled-paths/captured-seed2-401';layout_file=folder/'layout.json';raw=json.loads(layout_file.read_text())
candidate_file=folder/'two-guides-long-1800-4.json';packet=json.loads(candidate_file.read_text());positions=np.asarray(packet['vertices']);faces=np.asarray(packet['faces']);edges=cq._edges(faces)
curve_file=ROOT/'tests/toilet-stress/two-guides-long-1800/curves.json';curves=[np.asarray(c) for c in json.loads(curve_file.read_text())['curves']]
sv,sf=read_obj(ROOT/'assets/models/toilet.obj');spacing=np.sqrt(trimesh.Trimesh(sv,sf,process=False).area/1800)
before=[cq._guide_path(np.asarray(raw['vertices']),edges,c,spacing)[0] for c in curves]
after=[cq._guide_path(positions,edges,c,spacing)[0] for c in curves]
rows=[]
for label,paths in [('original',before),('reselected',after)]:
 fit=cq._guide_fit(positions,paths,curves)
 rows.append(dict(selection=label,guideGatePassed=all(f['p95Distance']<=.2*spacing and f['p95TangentAngleDegrees']<=30 for f in fit),guideFit=fit))
 print(label,[(round(f['p95Distance'],6),round(f['p95TangentAngleDegrees'],3),len(f['vertices'])-1) for f in fit],flush=True)
diagnostics=[]
for curve,path in zip(curves,before):
 points=cq._sample(curve,257);tangent=np.roll(points,-1,axis=0)-np.roll(points,1,axis=0)
 tangent[0]=points[1]-points[0];tangent[-1]=points[-1]-points[-2]
 if path['closed']:tangent[0]=tangent[-1]=points[1]-points[-2]
 tangent/=np.maximum(1e-12,np.linalg.norm(tangent,axis=1))[:,None]
 pe=np.asarray(list(zip(path['vertices'][:-1],path['vertices'][1:])));a=positions[pe[:,0]];delta=positions[pe[:,1]]-a
 t=np.clip(((points[:,None,:]-a)*delta).sum(axis=2)/(delta*delta).sum(axis=1),0,1)
 ds=np.linalg.norm(points[:,None,:]-a-t[:,:,None]*delta,axis=2);owners=ds.argmin(axis=1)
 unit=delta/np.linalg.norm(delta,axis=1)[:,None];actual=np.degrees(np.arccos(np.clip(np.abs((tangent*unit[owners]).sum(axis=1)),0,1)))
 ideal=np.zeros(len(points));groups=[]
 for owner in np.unique(owners):
  ids=np.flatnonzero(owners==owner);_,vectors=np.linalg.eigh(tangent[ids].T@tangent[ids]);direction=vectors[:,-1]
  angles=np.degrees(np.arccos(np.clip(np.abs(tangent[ids]@direction),0,1)));ideal[ids]=angles
  if np.any(actual[ids]>30):groups.append(dict(edge=pe[owner].tolist(),samples=ids.tolist(),actualAngles=actual[ids].tolist(),unconstrainedPrincipalAngles=angles.tolist(),unconstrainedDirection=direction.tolist(),midpoint=((a[owner]+positions[pe[owner,1]])*.5).tolist()))
 diagnostics.append(dict(originalP95=float(np.percentile(actual,95)),unconstrainedPrincipalP95=float(np.percentile(ideal,95)),badSampleCount=int(np.count_nonzero(actual>30)),unconstrainedBadSampleCount=int(np.count_nonzero(ideal>30)),badEdgeGroups=groups))
 print('tangent diagnostic',diagnostics[-1]['badSampleCount'],'bad samples; unconstrained edge-direction fit',diagnostics[-1]['unconstrainedBadSampleCount'],flush=True)
report=dict(complete=True,cases=rows,tangentDiagnostics=diagnostics,changedPaths=[a['vertices']!=b['vertices'] for a,b in zip(before,after)],geometryQualified=None,
 inputHashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (layout_file,candidate_file,curve_file)},
 sourceHashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('curved_quad.py','assets/models/toilet.obj','tests/inspect_toilet_path_reselection.py')},
 scope='Path selection and tangent diagnostics on unchanged retained geometry. Reselection uses the production path algorithm at the fitted vertex positions. Principal directions fit each fixed owner group independently; they need not be realizable by shared mesh vertices and are not a mesh result. No new full surface/contact/shape audit or production generation is claimed.')
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
