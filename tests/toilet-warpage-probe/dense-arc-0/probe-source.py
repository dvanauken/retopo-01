"""Isolate a quad-warpage fitting residual on a retained real QuadriFlow layout.

This is an experiment, not production generation. Original geometry, authored
guides, topology, and acceptance thresholds are unchanged. No result is published
to the application. The exact executed refinement source and layout are retained.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
from pathlib import Path
import hashlib
import argparse
import inspect
import json
import shutil
import sys
import time
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
parser=argparse.ArgumentParser(); parser.add_argument('--seed',type=int,choices=[0,1],default=1); parser.add_argument('--pin-weight',type=float,default=80); parser.add_argument('--cases',nargs='+'); parser.add_argument('--layout',type=Path); parser.add_argument('--label'); parser.add_argument('--target-spacing',choices=['corners','arc','path'],default='corners'); parser.add_argument('--dense-support',action='store_true'); args=parser.parse_args()
if not 0 < args.pin_weight <= 1000: raise ValueError('Use a finite positive pin weight')
label=args.label or f'seed-{args.seed}-pin-{args.pin_weight:g}'
if not label.replace('-','').isalnum(): raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-warpage-probe'/label; OUT.mkdir(parents=True,exist_ok=True)
(OUT/'probe-source.py').write_bytes(Path(__file__).read_bytes())
from measure_geometry import read_obj


def warpage(positions,faces):
    p=positions[faces]
    cross=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
    area=cross+np.cross(p[:,2]-p[:,0],p[:,3]-p[:,0])
    return np.einsum('ij,ij->i',cross,p[:,3]-p[:,0])/np.maximum(1e-15,np.linalg.norm(area,axis=1))


definition=inspect.getsource(cq._refine)
replacements={
    '    vertex_anchor, vertex_error, vertex_triangles =': '    bad |= np.abs(warpage(positions, faces)) > spacing * .05\n    vertex_anchor, vertex_error, vertex_triangles =',
    '    groups += [(len(local_edges), local_edges)] * 2': '    groups += [(len(local_faces), local_faces)]\n    groups += [(len(local_edges), local_edges)] * 2',
    'np.maximum(ratio - 3.5, 0) * 10, np.maximum(.4 - length / spacing, 0) * 5,': 'np.maximum(ratio - 3.5, 0) * 10, warpage(q, local_faces) / spacing * 8, np.maximum(.4 - length / spacing, 0) * 5,',
    '(q[pins] - targets).ravel() / spacing * 80,': f'(q[pins] - targets).ravel() / spacing * {args.pin_weight},',
}
if args.dense_support:
    replacements.update({
        'trimesh.proximity.closest_point(out_surface, source_mesh.vertices)': 'trimesh.proximity.closest_point(out_surface, source_points)',
        'support_target = source_mesh.vertices[selected]': 'support_target = source_points[selected]',
    })
for old,new in replacements.items():
    assert definition.count(old)==1,old
    definition=definition.replace(old,new)
(OUT/'refine-source.py').write_text(inspect.getsource(warpage)+'\n'+definition)
namespace=dict(vars(cq),warpage=warpage);exec(definition,namespace)
sv,sf=read_obj(ROOT/'assets/models/toilet.obj'); sf=np.asarray(sf)
source=trimesh.Trimesh(sv,sf,process=False); spacing=np.sqrt(source.area/1800)
namespace['source_points']=np.r_[source.vertices,source.triangles_center,source.vertices[source.edges_unique].mean(axis=1)]
old=json.loads((ROOT/'tests/toilet-stress/result.json').read_text())['cases']
layout_case=next(c for c in old if c['name']=='lid-only-1800')
layout_path=args.layout or ROOT/'runs'/layout_case['job']/f'quadri-layout-{args.seed}.json'
shutil.copyfile(layout_path,OUT/'quadri-layout.json')
layout=json.loads(layout_path.read_text()); faces=np.asarray(layout['faces']); edges=cq._edges(faces)
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('curved_quad.py','surface_distance.py','surface_intersections.py','quad_quality.py','assets/models/toilet.obj','tests/probe_toilet_warpage.py')}
cases=[]
for name in (args.cases or ('unguided-1800','two-guides-short-1800','two-guides-long-1800')):
    positions=np.asarray(layout['vertices'])
    curves=[np.asarray(c) for c in json.loads((ROOT/'tests/toilet-stress'/name/'curves.json').read_text())['curves']]
    paths,pins,targets=[],[],[]
    for c in curves:
        path,pin,target=cq._guide_path(positions,edges,c,spacing)
        if args.target_spacing!='corners':
            arc=cq._arc(c)
            offset=cq._nearest_curve(positions[pin[:1]],c)[1][0] if path['closed'] else 0.
            if args.target_spacing=='arc':
                parameters=np.linspace(0,arc[-1],len(pin),endpoint=not path['closed'])
            else:
                trace=positions[path['vertices']]; lengths=cq._arc(trace)
                parameters=lengths[:len(pin)]/lengths[-1]*arc[-1]
            parameters=(parameters+offset)%arc[-1] if path['closed'] else parameters
            target=np.array([np.interp(parameters,arc,c[:,i]) for i in range(3)]).T
        paths.append(path);pins.extend(pin);targets.extend(target)
    pins=np.asarray(pins,dtype=int);targets=np.asarray(targets).reshape(-1,3)
    for iteration in range(5):
        start=time.monotonic()
        positions,refinement=namespace['_refine'](source,positions,faces,edges,pins,targets,1800)
        quality=cq.quad_quality(positions,faces,1800)
        crossing=cq.surface_intersections(positions,faces)
        fit=cq._guide_fit(positions,paths,curves)
        guided=all(p['p95Distance']<=.2*spacing and p['p95TangentAngleDegrees']<=30 for p in fit)
        full=quality['passed'] and crossing['passed'] and guided
        surface=cq.validate_surface(sv,sf,positions,faces,1800,whole_surface=full)
        accepted=full and surface['passed']
        record=dict(name=name,iteration=iteration,refinement=refinement,quality=quality,contacts=crossing,
                    surface=surface,guideFit=fit,candidateQualified=accepted,elapsedSeconds=time.monotonic()-start,
                    maxWarpage=float(np.abs(warpage(positions,faces)).max()))
        cases.append(record)
        (OUT/f'{name}-{iteration}.json').write_text(json.dumps(dict(vertices=positions.tolist(),faces=faces.tolist())))
        (OUT/'result.json').write_text(json.dumps(dict(complete=False,attempts=cases,sourceHashes=hashes),indent=2)+'\n')
        print(name,iteration,'quality',quality['passed'],'contacts',crossing['passed'],'surface',surface['passed'],
              'full',full,'fit',[(round(p['p95Distance'],5),round(p['p95TangentAngleDegrees'],1)) for p in fit],
              'qualified',accepted,'seconds',round(record['elapsedSeconds'],1),flush=True)
        if accepted:break
(OUT/'result.json').write_text(json.dumps(dict(complete=True,attempts=cases,sourceHashes=hashes,
    executedRefinementSha256=hashlib.sha256((OUT/'refine-source.py').read_bytes()).hexdigest(),
    layoutSha256=hashlib.sha256((OUT/'quadri-layout.json').read_bytes()).hexdigest(),originalLayoutJob=layout_case['job'] if not args.layout else None,layoutSource=str(layout_path),seed=args.seed,pinWeight=args.pin_weight,targetSpacing=args.target_spacing,denseSupport=args.dense_support,
    scope='Isolated fitting experiment with retained real layout. Adds a warpage residual and records the pin residual weight; original source/guides and every acceptance threshold are unchanged. No production publication or fresh layout generation is claimed.'),indent=2)+'\n')
