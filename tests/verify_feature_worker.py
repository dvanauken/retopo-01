"""Run the actual feature worker on captured user guides, with isolated output."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--case',choices=['bowl','four'],default='four');ap.add_argument('--target',type=int,default=7200);args=ap.parse_args()
packet=(ROOT/'tests/toilet-sampled-worker/integrated-fallback/bowl-only-1800/curves.json' if args.case=='bowl' else ROOT/'tests/fixtures/toilet-four-guides.json')
job=ROOT/'runs'/uuid.uuid4().hex;job.mkdir();source=ROOT/'assets/models/toilet.obj'
(job/'curves.json').write_bytes(packet.read_bytes());curves=json.loads(packet.read_text())['curves']
settings=dict(meshId='toilet',target=args.target,guideMode=2,sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest())
(job/'settings.json').write_text(json.dumps(settings));print('WORKER',job,'guides',len(curves),flush=True)
result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'worker.py'),'--feature-layout','--job',str(job)],cwd=ROOT)
print('EXIT',result.returncode,'JOB',job,flush=True)
if result.returncode:raise SystemExit(result.returncode)
mesh=json.loads((job/'mesh.json').read_text());report=json.loads((job/'report.json').read_text())
assert report['passed'] and mesh['quality']['passed'] and mesh['surfaceValidation']['passed'] and mesh['intersectionValidation']['passed']
assert mesh['featurePolicy']=='enforced' and mesh['featureValidation']['passed']
assert mesh['guideCount']==len(curves) and len(mesh['guidePaths'])==len(curves)
print('VERIFIED actual worker output',job,flush=True)
