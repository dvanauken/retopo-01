"""Repair retained surface-error witnesses with local, checked fitting steps.

Only vertices around actual whole-surface witnesses may move. Full steps that
break shape, guide or contact limits are backtracked. Every final acceptance
uses the original gates. This diagnostic never publishes a production result.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,inspect,json,sys,time,traceback
from pathlib import Path
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True)
parser.add_argument('--input-folder',type=Path,default=ROOT/'tests/toilet-sampled-paths/captured-seed2-401')
parser.add_argument('--case',dest='case_name',default='two-guides-short-1800')
parser.add_argument('--candidate-iteration',type=int,default=1)
args=parser.parse_args();args.weight=12.
if not args.label.replace('-','').isalnum():raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-witness-repair'/args.label;OUT.mkdir(parents=True,exist_ok=False)
(OUT/'executed-probe.py').write_bytes(Path(__file__).read_bytes())
folder=args.input_folder.resolve();name=args.case_name
if not name.replace('-','').isalnum() or args.candidate_iteration<0:raise ValueError('Invalid candidate selector')
layout_file=folder/'layout.json';raw=json.loads(layout_file.read_text());(OUT/'layout.json').write_bytes(layout_file.read_bytes())
candidate_file=folder/f'{name}-{args.candidate_iteration}.json';packet=json.loads(candidate_file.read_text());positions=np.asarray(packet['vertices']);faces=np.asarray(packet['faces']);edges=cq._edges(faces)
curve_file=ROOT/'tests/toilet-stress'/name/'curves.json';curves=[np.asarray(c) for c in json.loads(curve_file.read_text())['curves']]
sv,sf=read_obj(ROOT/'assets/models/toilet.obj');sv=np.asarray(sv);sf=np.asarray(sf)
mesh=trimesh.Trimesh(sv,sf,process=False);spacing=np.sqrt(mesh.area/1800)
paths=[];pin_rows=[];target_rows=[];pin_groups=[]
for curve in curves:
 path,pin,target=cq._guide_path(np.asarray(raw['vertices']),edges,curve,spacing)
 paths.append(path);pin_groups.append((curve,len(pin_rows),len(pin_rows)+len(pin)));pin_rows.extend(pin);target_rows.extend(target)
pins=np.asarray(pin_rows,dtype=int);targets=np.asarray(target_rows)
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('curved_quad.py','surface_distance.py','surface_intersections.py','quad_quality.py','assets/models/toilet.obj','tests/probe_toilet_witness_repair.py','tests/probe_toilet_sampled_paths.py')}
case=dict(name=name,curvesSha256=hashlib.sha256(curve_file.read_bytes()).hexdigest(),attempts=[],qualified=False)
errors=[];steps=[]

def pin_residual(points):
 nearest=[]
 for curve,begin,end in pin_groups:
  _,parameter=cq._nearest_curve(points[begin:end],curve);arc=cq._arc(curve)
  projected=np.array([np.interp(parameter,arc,curve[:,i]) for i in range(3)]).T
  if np.linalg.norm(curve[0]-curve[-1])>=1e-8:projected[0],projected[-1]=curve[0],curve[-1]
  nearest.extend(projected)
 return ((points-np.asarray(nearest))*80+(points-targets)*4).ravel()/spacing

def sampled_path_residual(points):
 a=points[sample_edges[:,0]];delta=points[sample_edges[:,1]]-a;den=np.maximum(1e-18,(delta*delta).sum(axis=1))
 t=np.clip(((sample_points-a)*delta).sum(axis=1)/den,0,1);near=a+t[:,None]*delta;unit=delta/np.sqrt(den)[:,None]
 return np.r_[((near-sample_points)/spacing*32*sample_weights[:,None]).ravel(),(np.cross(unit,sample_tangents)*12*sample_weights[:,None]).ravel()]

definition=inspect.getsource(cq._refine)
begin=definition.index('    out_tri = ');end=definition.index('    ids = np.array(sorted(active)',begin)
support='''    source_samples = np.r_[source_mesh.vertices, source_mesh.triangles_center, witness_source]
    supports, barycentrics, support_targets = [], [], []
    for first, second in (([0, 1, 2], [0, 2, 3]), ([0, 1, 3], [1, 2, 3])):
        out_tri = np.r_[faces[:, first], faces[:, second]]
        out_surface = trimesh.Trimesh(positions, out_tri, process=False)
        near, error, owners = trimesh.proximity.closest_point(out_surface, source_samples)
        selected = (error > spacing * .25) & np.any(np.isin(out_tri[owners], list(patch_vertices)), axis=1)
        owned = out_tri[owners[selected]]
        supports.append(owned)
        barycentrics.append(trimesh.triangles.points_to_barycentric(positions[owned], near[selected]))
        support_targets.append(source_samples[selected])
    support = np.concatenate(supports)
    barycentric = np.concatenate(barycentrics)
    support_target = np.concatenate(support_targets)
    active = set(patch_vertices)
'''
definition=definition[:begin]+support+definition[end:]
assert definition.count('(q[pins] - targets).ravel() / spacing * 80')==1
definition=definition.replace('(q[pins] - targets).ravel() / spacing * 80','pin_residual(q[pins])')
definition=definition.replace('    sparsity = lil_matrix(','    groups += [(len(sample_edges)*3,sample_edges)]*2\n    sparsity = lil_matrix(')
anchor='np.maximum(np.linalg.norm(surface_delta, axis=1) / spacing - .35, 0) * 40]'
assert definition.count(anchor)==1
definition=definition.replace(anchor,anchor[:-1]+', sampled_path_residual(q)]')
(OUT/'executed-refine.py').write_text(inspect.getsource(pin_residual)+'\n'+inspect.getsource(sampled_path_residual)+'\n'+definition,newline='\n')
namespace=dict(vars(cq),pin_residual=pin_residual,sampled_path_residual=sampled_path_residual);exec(definition,namespace)

def evaluate(p,extra=None):
 quality=cq.quad_quality(p,faces,1800);fit=cq._guide_fit(p,paths,curves);contacts=cq.surface_intersections(p,faces,both_quad_diagonals=True)
 guided=all(f['p95Distance']<=.2*spacing and f['p95TangentAngleDegrees']<=30 for f in fit)
 eligible=bool(quality['passed'] and guided and contacts['passed'])
 surface=cq.validate_surface(sv,sf,p,faces,1800,whole_surface=eligible);bounds=surface['wholeSurfaceDiagonals'].copy()
 if eligible and not bounds:
  for name,a,b in [('02',[0,1,2],[0,2,3]),('13',[0,1,3],[1,2,3])]:
   bounds[name]=cq.surface_distance(mesh,trimesh.Trimesh(p,np.r_[faces[:,a],faces[:,b]],process=False),.5*spacing)
 score=max((direction['sampledMax'] for bound in bounds.values() for direction in (bound['sourceToOutput'],bound['outputToSource'])),default=None)
 record=dict(iteration=len(case['attempts']),quality=quality,guideFit=fit,contacts=contacts,surface=surface,witnessBounds=bounds,eligibleForRepair=eligible,maxObservedSurfaceError=score,qualified=bool(eligible and surface['passed']))
 record.update(extra or {});case['attempts'].append(record);case['qualified']|=record['qualified']
 (OUT/f"{case['name']}-{record['iteration']}.json").write_text(json.dumps(dict(vertices=p.tolist(),faces=faces.tolist())))
 return record

def save(complete):
 (OUT/'result.json').write_text(json.dumps(dict(complete=complete,cases=[case],steps=steps,errors=errors,seed=raw['seed'],
  sourceHashes=hashes,implementationUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),
  layoutSource=str(layout_file.relative_to(ROOT)),layoutSha256=hashlib.sha256(layout_file.read_bytes()).hexdigest(),
  initialCandidate=str(candidate_file.relative_to(ROOT)),initialCandidateSha256=hashlib.sha256(candidate_file.read_bytes()).hexdigest(),
  scope='Isolated local repair of the retained sampled-path short combined candidate. Patch is two vertex-connected face rings around actual full-surface failure witnesses, on both output diagonals. Only patch vertices move; the original residual weights and 401-sample path objective are retained. Backtracking requires unchanged shape/contact/257-sample guide gates and decreases the measured worst surface witness error. That progress metric is not a surface certificate; final qualification still requires the original full surface gates. No production result.'),indent=2)+'\n',newline='\n')

try:
 current=evaluate(positions,dict(initial=True));save(False)
 assert current['eligibleForRepair'] and current['witnessBounds'],'Expected a guide/contact/shape-valid surface failure'
 for step in range(6):
  if current['qualified']:break
  witnesses=np.asarray([d['witness'] for b in current['witnessBounds'].values() for d in (b['sourceToOutput'],b['outputToSource']) if not d['passed'] and d['witness'] is not None])
  assert len(witnesses),'A failed surface bound must expose a witness for this experiment'
  witness_source=trimesh.proximity.closest_point(mesh,witnesses)[0];patch_vertices=set()
  for a,b in (([0,1,2],[0,2,3]),([0,1,3],[1,2,3])):
   tri=np.r_[faces[:,a],faces[:,b]];surface=trimesh.Trimesh(positions,tri,process=False)
   owner=trimesh.proximity.closest_point(surface,witnesses)[2];patch_vertices.update(tri[owner].ravel())
  for _ in range(2):patch_vertices.update(faces[np.any(np.isin(faces,list(patch_vertices)),axis=1)].ravel())
  sample_edges=[];sample_points=[];sample_tangents=[];sample_weights=[]
  for path,curve in zip(paths,curves):
   pe=np.array(list(zip(path['vertices'][:-1],path['vertices'][1:])),dtype=int);points=cq._sample(curve,401)
   tangent=np.roll(points,-1,axis=0)-np.roll(points,1,axis=0);tangent[0]=points[1]-points[0];tangent[-1]=points[-1]-points[-2]
   if path['closed']:tangent[0]=tangent[-1]=points[1]-points[-2]
   tangent/=np.maximum(1e-12,np.linalg.norm(tangent,axis=1))[:,None]
   a=positions[pe[:,0]];delta=positions[pe[:,1]]-a
   t=np.clip(((points[:,None,:]-a)*delta).sum(axis=2)/np.maximum(1e-18,(delta*delta).sum(axis=1)),0,1)
   error=points[:,None,:]-a-t[:,:,None]*delta;selected=(error*error).sum(axis=2).argmin(axis=1)
   sample_edges.extend(pe[selected]);sample_points.extend(points);sample_tangents.extend(tangent);sample_weights.extend([np.sqrt(len(pe)/len(points))]*len(points))
  sample_edges=np.asarray(sample_edges);sample_points=np.asarray(sample_points);sample_tangents=np.asarray(sample_tangents);sample_weights=np.asarray(sample_weights)
  namespace.update(patch_vertices=patch_vertices,witness_source=witness_source,sample_edges=sample_edges)
  started=time.monotonic();proposal,refinement=namespace['_refine'](mesh,positions,faces,edges,pins,targets,1800)
  step_record=dict(step=step,patchVertices=sorted(map(int,patch_vertices)),witnesses=witnesses.tolist(),refinement=refinement,continued=False,trials=[]);steps.append(step_record)
  for power in range(5):
   alpha=.5**power;candidate=positions+alpha*(proposal-positions)
   outside=np.array(sorted(set(range(len(positions)))-patch_vertices),dtype=int);assert np.array_equal(candidate[outside],positions[outside])
   trial=evaluate(candidate,dict(step=step,alpha=alpha,elapsedSeconds=time.monotonic()-started));step_record['trials'].append(trial['iteration'])
   progress=trial['eligibleForRepair'] and trial['maxObservedSurfaceError']<current['maxObservedSurfaceError']-spacing*1e-6
   print('step',step,'patch',len(patch_vertices),'alpha',alpha,'guide',[round(f['p95TangentAngleDegrees'],3) for f in trial['guideFit']],'contacts',trial['contacts']['passed'],'error',trial['maxObservedSurfaceError'],'qualified',trial['qualified'],'progress',progress,flush=True)
   if trial['qualified'] or progress:
    positions=candidate;current=trial;step_record.update(continued=True,continuedCandidate=trial['iteration']);save(False);break
   save(False)
  if not step_record['continued']:break
except Exception:
 errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:save(True)
raise SystemExit(1 if errors else 0)
