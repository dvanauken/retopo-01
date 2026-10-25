"""Check feasibility between retained bowl and combined-guide candidates.

This is a diagnostic on one genuine retained connectivity, not generation or a
production fallback. Every trial uses unchanged guide, shape, contact and full
surface gates. A passing trial would motivate a constrained continuation solve.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
if not args.label.replace('-','').isalnum():raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-feasible-blend'/args.label
OUT.mkdir(parents=True,exist_ok=False)
folder=ROOT/'tests/toilet-sampled-paths/captured-seed2-401'
layout_file=folder/'layout.json';raw=json.loads(layout_file.read_text())
(OUT/'layout.json').write_bytes(layout_file.read_bytes())
bowl_file=folder/'bowl-only-1800-1.json';bowl=json.loads(bowl_file.read_text())
positions0=np.asarray(bowl['vertices']);faces=np.asarray(bowl['faces']);edges=cq._edges(faces)
sv,sf=read_obj(ROOT/'assets/models/toilet.obj');source=trimesh.Trimesh(sv,sf,process=False);spacing=np.sqrt(source.area/1800)
files=['curved_quad.py','surface_distance.py','surface_intersections.py','quad_quality.py','assets/models/toilet.obj','tests/probe_toilet_feasible_blend.py']
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
cases=[];errors=[]
def save(complete):
 report=dict(complete=complete,cases=cases,errors=errors,sourceHashes=hashes,
  implementationUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),
  seed=raw['seed'],layoutSource=str(layout_file.relative_to(ROOT)),layoutSha256=hashlib.sha256(layout_file.read_bytes()).hexdigest(),
  anchorSource=str(bowl_file.relative_to(ROOT)),anchorSha256=hashlib.sha256(bowl_file.read_bytes()).hexdigest(),
  scope='Nine fixed convex blends between a retained bowl-only qualified experimental candidate and each retained combined-guide candidate on the same genuine seed-2 topology. This probes feasibility; it is not a fresh solve, an integrated method or a production result. All acceptance limits remain unchanged. Full surface bounds run only for otherwise eligible candidates.')
 (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
try:
 for name,endpoint in [('two-guides-short-1800',1),('two-guides-long-1800',4)]:
  curve_file=ROOT/'tests/toilet-stress'/name/'curves.json';curves=[np.asarray(c) for c in json.loads(curve_file.read_text())['curves']]
  target_file=folder/f'{name}-{endpoint}.json';packet=json.loads(target_file.read_text());positions1=np.asarray(packet['vertices'])
  assert np.array_equal(faces,packet['faces'])
  paths=[cq._guide_path(np.asarray(raw['vertices']),edges,c,spacing)[0] for c in curves]
  record=dict(name=name,curvesSha256=hashlib.sha256(curve_file.read_bytes()).hexdigest(),targetSource=str(target_file.relative_to(ROOT)),targetSha256=hashlib.sha256(target_file.read_bytes()).hexdigest(),attempts=[],qualified=False)
  cases.append(record)
  for iteration,weight in enumerate(np.linspace(0,1,9)):
   started=time.monotonic();positions=(1-weight)*positions0+weight*positions1
   quality=cq.quad_quality(positions,faces,1800);fit=cq._guide_fit(positions,paths,curves)
   contacts=cq.surface_intersections(positions,faces,both_quad_diagonals=True)
   guided=all(p['p95Distance']<=.2*spacing and p['p95TangentAngleDegrees']<=30 for p in fit)
   eligible=quality['passed'] and contacts['passed'] and guided
   surface=cq.validate_surface(sv,sf,positions,faces,1800,whole_surface=eligible)
   qualified=bool(eligible and surface['passed']);record['qualified']|=qualified
   record['attempts'].append(dict(iteration=iteration,combinedWeight=float(weight),quality=quality,guideFit=fit,contacts=contacts,surface=surface,qualified=qualified,elapsedSeconds=time.monotonic()-started))
   (OUT/f'{name}-{iteration}.json').write_text(json.dumps(dict(vertices=positions.tolist(),faces=faces.tolist())))
   save(False)
   print(name,'weight',weight,'angles',[round(p['p95TangentAngleDegrees'],2) for p in fit],'distance',[round(p['p95Distance'],5) for p in fit],'contacts',contacts['passed'],'surface',surface['passed'],'qualified',qualified,flush=True)
except Exception:
 errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:save(True)
raise SystemExit(1 if errors else 0)
