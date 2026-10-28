"""Fresh experimental backend call; never submits rejected geometry to the app."""
from pathlib import Path
import argparse,json,sys,uuid
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj
from feature_quad import construct
from guided_layout import obj
ap=argparse.ArgumentParser();ap.add_argument('--case',choices=['bowl','none'],default='bowl');ap.add_argument('--target',type=int,default=7200);args=ap.parse_args()
job=ROOT/'runs'/('feature-fresh-'+args.case+'-'+uuid.uuid4().hex[:8]);job.mkdir();print(job,flush=True)
v,f=read_obj(ROOT/'assets/models/toilet.obj')
curves=json.loads((ROOT/'tests/toilet-sampled-worker/integrated-fallback/bowl-only-1800/curves.json').read_text())['curves'] if args.case=='bowl' else []
(job/'curves.json').write_text(json.dumps(dict(curves=curves)))
p,q,meta=construct(v,f,curves,target=args.target,job=job)
obj(job/'output.obj',p,q)
print('ACCEPTED',job,flush=True)
