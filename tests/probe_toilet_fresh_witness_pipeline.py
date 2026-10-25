"""Reproduce sampled fitting and witness repair from a fresh Blender layout.

Original source and authored curves are the inputs. Intermediate candidates are
produced during this run; none is loaded from a previous run. This remains an
isolated numerical pipeline, not the app's production worker route.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,json,subprocess,sys,time,traceback
from pathlib import Path
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj
from process_ownership import protect_service_tree
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);parser.add_argument('--seed',type=int,default=2)
parser.add_argument('--case',dest='case_name',default='two-guides-short-1800');args=parser.parse_args()
if not args.label.replace('-','').isalnum() or not args.case_name.replace('-','').isalnum() or args.seed<0:raise ValueError('Invalid labels or seed')
protect_service_tree()
OUT=ROOT/'tests/toilet-fresh-witness'/args.label;OUT.mkdir(parents=True,exist_ok=False)
(OUT/'executed-probe.py').write_bytes(Path(__file__).read_bytes())
fit_label=args.label+'-fit';repair_label=args.label+'-repair';audit_label=args.label+'-export'
fit_folder=ROOT/'tests/toilet-sampled-paths'/fit_label;repair_folder=ROOT/'tests/toilet-witness-repair'/repair_label
assert not fit_folder.exists() and not repair_folder.exists()
files=['assets/models/toilet.obj','curved_quad.py','surface_distance.py','surface_intersections.py','quad_quality.py','scripts/quadriflow_mesh.py',
 'tests/probe_toilet_sampled_paths.py','tests/probe_toilet_witness_repair.py','tests/probe_toilet_fresh_witness_pipeline.py','tests/export_toilet_probe.py',
 'tests/verify_toilet_fresh_geometry.py','tests/verify_toilet_all_diagonal_audit.py','process_ownership.py']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={file:sha(ROOT/file) for file in files};curve_file=ROOT/'tests/toilet-stress'/args.case_name/'curves.json';curve_hash=sha(curve_file)
source,triangles=read_obj(ROOT/'assets/models/toilet.obj');source=np.asarray(source);triangles=np.asarray(triangles)
spacing=np.sqrt(trimesh.Trimesh(source,triangles,process=False).area/1800)
input_path=OUT/'source.json';input_path.write_text(json.dumps(dict(vertices=source.tolist(),faces=triangles.tolist())))
layout=OUT/'layout.json';started=time.monotonic();stages=[];errors=[];qualified=False;export_matrix=None;chosen=None
blender=cq.find_blender();blender_hash=sha(blender)
def save(complete):
 report=dict(complete=complete,generationPassed=qualified,productionResult=False,freshSourceGeneration=True,case=args.case_name,seed=args.seed,
  stages=stages,errors=errors,sourceHashes=hashes,curvesSha256=curve_hash,layoutSha256=sha(layout) if layout.exists() else None,
  blender=str(blender),blenderSha256=blender_hash,chosenRepairCandidate=chosen,exportMatrix=str(export_matrix.relative_to(ROOT)) if export_matrix else None,
  implementationUnchanged=all(sha(ROOT/p)==h for p,h in hashes.items()) and sha(curve_file)==curve_hash,elapsedSeconds=time.monotonic()-started,
  scope='Fresh original-source Blender layout, distributed sampled-path fitting, automatic selection of the best measured guide/shape/contact-valid surface-failing candidate, local witness repair, and independent OBJ audits. Every intermediate mesh is produced during this run. No prior candidate or saved result is used as input. This is an isolated experimental pipeline; the production toilet route is unchanged.')
 (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
def python_stage(name,arguments):
 print('START',name,flush=True);begin=time.monotonic()
 process=subprocess.run([sys.executable,'-X','utf8',*arguments],cwd=ROOT,timeout=900,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 stages.append(dict(name=name,arguments=arguments,exitCode=process.returncode,elapsedSeconds=time.monotonic()-begin));save(False)
 if process.returncode:raise RuntimeError(name+' returned '+str(process.returncode))
try:
 command=[str(blender),'--background','--threads','8','--python',str(ROOT/'scripts/quadriflow_mesh.py'),'--','--input',str(input_path),'--output',str(layout),'--target','1800','--seed',str(args.seed)]
 print('START fresh Blender layout seed',args.seed,flush=True);begin=time.monotonic()
 with (OUT/'blender.log').open('w') as log:
  process=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 stages.append(dict(name='fresh-layout',command=command,exitCode=process.returncode,elapsedSeconds=time.monotonic()-begin));save(False)
 if process.returncode:raise RuntimeError('Fresh Blender layout failed')
 raw=json.loads(layout.read_text());assert raw['seed']==args.seed
 python_stage('sampled-fit',['tests/probe_toilet_sampled_paths.py','--layout',str(layout),'--label',fit_label,'--cases',args.case_name])
 fit_report=json.loads((fit_folder/'result.json').read_text());assert fit_report['complete'] and not fit_report['errors'] and fit_report['implementationUnchanged']
 record=fit_report['cases'][0];producer=fit_folder;kind='isolated-sampled-path-probe'
 if not record['qualified']:
  eligible=[a for a in record['attempts'] if a['quality']['passed'] and a['contacts']['passed'] and a['surface']['wholeSurfaceDiagonals']
   and all(p['p95Distance']<=.2*spacing and p['p95TangentAngleDegrees']<=30 for p in a['guideFit'])]
  if not eligible:raise ValueError('No guide/shape/contact-valid surface-failing candidate is available for witness repair')
  selected=min(eligible,key=lambda a:max(d['sampledMax'] for b in a['surface']['wholeSurfaceDiagonals'].values() for d in (b['sourceToOutput'],b['outputToSource'])))
  chosen=dict(iteration=selected['iteration'],candidateSha256=sha(fit_folder/f"{args.case_name}-{selected['iteration']}.json"))
  python_stage('witness-repair',['tests/probe_toilet_witness_repair.py','--label',repair_label,'--input-folder',str(fit_folder),'--case',args.case_name,'--candidate-iteration',str(selected['iteration'])])
  repair=json.loads((repair_folder/'result.json').read_text());assert repair['complete'] and not repair['errors'] and repair['implementationUnchanged']
  record=repair['cases'][0];producer=repair_folder;kind='isolated-witness-repair-probe'
 if record['qualified']:
  python_stage('experimental-export',['tests/export_toilet_probe.py','--probe',str(producer/'result.json'),'--producer-kind',kind]);export_matrix=producer/'export-matrix.json'
  python_stage('independent-export-audit',['tests/verify_toilet_fresh_geometry.py','--matrix',str(export_matrix),'--label',audit_label])
  python_stage('mixed-diagonal-audit',['tests/verify_toilet_all_diagonal_audit.py','--matrix',str(export_matrix),'--label',audit_label])
  qualified=True
except Exception:
 errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:save(True)
raise SystemExit(0 if qualified and not errors else 1)
