"""Diagnose source-support correspondence without changing fitting or gates."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import hashlib,json,sys
from pathlib import Path
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine/targets/zbrush/experiments/python'))
from measure_geometry import read_obj
OUT=ROOT/'tests/toilet-support-normal-diagnostics';OUT.mkdir(exist_ok=True)
layout=ROOT/'tests/toilet-layout-seeds/fresh-seeds-2-3/layout-2.json'
packet=json.loads(layout.read_text());vertices=np.asarray(packet['vertices']);faces=np.asarray(packet['faces'])
sv,sf=read_obj(ROOT/'assets/models/toilet.obj');source=trimesh.Trimesh(sv,sf,process=False)
points=np.r_[source.vertices,source.triangles_center]
normals=np.r_[source.vertex_normals,source.face_normals]
spacing=np.sqrt(source.area/1800)
report=dict(layoutSha256=hashlib.sha256(layout.read_bytes()).hexdigest(),sourceSha256=hashlib.sha256((ROOT/'assets/models/toilet.obj').read_bytes()).hexdigest(),diagonals={},
 scope='Nearest Euclidean source-support ownership before refinement. Source vertex normals are averaged; triangle-centroid normals are exact source face normals. Opposing normals indicate correspondence ambiguity, not a geometric acceptance decision.')
implicated={828,972,973,987,988,884}
for name,first,second in [('02',[0,1,2],[0,2,3]),('13',[0,1,3],[1,2,3])]:
 tri=np.r_[faces[:,first],faces[:,second]];surface=trimesh.Trimesh(vertices,tri,process=False)
 near,error,owners=trimesh.proximity.closest_point(surface,points)
 selected=error>spacing*.25;dot=np.einsum('ij,ij->i',normals,surface.face_normals[owners])
 face_ids=owners%len(faces);bad=selected & np.isin(face_ids,list(implicated))
 rows=[]
 for face in sorted(implicated):
  ids=np.flatnonzero(selected & (face_ids==face))
  rows.append(dict(face=face,supports=len(ids),opposingNormals=int(np.count_nonzero(dot[ids]<0)),normalDotMinimum=float(dot[ids].min()) if len(ids) else None,
   samples=[dict(sourcePoint=points[i].tolist(),nearestPoint=near[i].tolist(),distance=float(error[i]),normalDot=float(dot[i]),sourceKind='vertex' if i<len(sv) else 'face-centroid') for i in ids[np.argsort(dot[ids])[:3]]]))
 report['diagonals'][name]=dict(selectedSupportPoints=int(selected.sum()),opposingNormals=int(np.count_nonzero(dot[selected]<0)),
  belowHalfDot=int(np.count_nonzero(dot[selected]<.5)),implicatedFaces=rows)
 print(name,'selected',int(selected.sum()),'opposing',int(np.count_nonzero(dot[selected]<0)), 'implicated opposing',int(np.count_nonzero(dot[bad]<0)),flush=True)
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
