from pathlib import Path
import json, sys, numpy as np
ROOT=Path.cwd();sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
import trimesh
from measure_geometry import read_obj
sv,sf=read_obj(ROOT/'assets/models/toilet.obj'); spacing=np.sqrt(trimesh.Trimesh(sv,sf,process=False).area/1800)
folder=ROOT/'tests/toilet-layout-seeds/fresh-seeds-2-3'
records=[]
for seed in (2,3):
    raw=json.loads((folder/f'layout-{seed}.json').read_text());v=np.asarray(raw['vertices']);f=np.asarray(raw['faces']);e=cq._edges(f)
    record=dict(seed=seed,rawContacts=cq.surface_intersections(v,f,both_quad_diagonals=True),curves=[])
    curves=json.loads((ROOT/'tests/toilet-stress/bowl-only-1800/curves.json').read_text())['curves']
    for c in curves:
        c=np.asarray(c);path,pins,targets=cq._guide_path(v,e,c,spacing)
        d,param=cq._nearest_curve(v[pins],c);targetd=np.linalg.norm(v[pins]-targets,axis=1);arc=cq._arc(c);ts=cq._nearest_curve(targets,c)[1];ts=(ts-ts[0])%arc[-1]
        gaps=np.diff(np.r_[ts,arc[-1]])
        record['curves'].append(dict(pathVertices=len(pins),spacing=spacing,initialDistanceP95=float(np.percentile(d,95)),targetDisplacementP95=float(np.percentile(targetd,95)),maxTargetDisplacement=float(targetd.max()),targetSpacingQuantiles=np.quantile(gaps,[0,.05,.5,.95,1]).tolist(),path=path))
    records.append(record)
print(json.dumps(records,indent=2))
(ROOT/'tests/toilet-layout-seeds/path-diagnostics.json').write_text(json.dumps(records,indent=2)+'\n')
