"""Keep rejected surface witnesses as fitting constraints while correcting guides.

Only vertices around actual surface failures or outlying guide samples may move. Full steps that
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
parser.add_argument('--input-folder',type=Path,default=ROOT/'tests/toilet-joint-repair/long-seed2-protected')
parser.add_argument('--case',dest='case_name',default='two-guides-long-1800')
parser.add_argument('--candidate-iteration',type=int,default=5)
parser.add_argument('--tail-weight',type=float,default=40.)
parser.add_argument('--memory-weight',type=float,default=8.)
args=parser.parse_args();args.weight=12.
if not np.isfinite(args.tail_weight) or args.tail_weight<0:raise ValueError('Tail weight must be finite and nonnegative')
if not args.label.replace('-','').isalnum():raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-constraint-memory'/args.label;OUT.mkdir(parents=True,exist_ok=False)
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
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('curved_quad.py','surface_distance.py','surface_intersections.py','quad_quality.py','assets/models/toilet.obj','tests/probe_toilet_witness_repair.py','tests/probe_toilet_sampled_paths.py','tests/probe_toilet_joint_repair.py','tests/probe_toilet_tangent_tail.py','tests/probe_toilet_constraint_memory.py')}
case=dict(name=name,curvesSha256=hashlib.sha256(curve_file.read_bytes()).hexdigest(),attempts=[],qualified=False)
errors=[];steps=[];memory=[];memory_keys=set()

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
 cross=np.cross(unit,sample_tangents);sine=np.linalg.norm(cross,axis=1)
 factor=12+args.tail_weight*np.maximum(sine-np.sin(np.radians(25)),0)/np.maximum(sine,1e-12)
 return np.r_[((near-sample_points)/spacing*32*sample_weights[:,None]).ravel(),(cross*factor[:,None]*sample_weights[:,None]).ravel()]

def memory_residual(points):
 delta=(points[memory_tri]*memory_bary[:,:,None]).sum(axis=1)-memory_target
 return np.r_[(delta/spacing*args.memory_weight).ravel(),np.maximum(np.linalg.norm(delta,axis=1)/spacing-.4,0)*40]

def remember(candidate,trial):
 for diagonal,bound in trial['witnessBounds'].items():
  a,b=([0,1,2],[0,2,3]) if diagonal=='02' else ([0,1,3],[1,2,3])
  tri=np.r_[faces[:,a],faces[:,b]];output=trimesh.Trimesh(candidate,tri,process=False)
  for direction in ('sourceToOutput','outputToSource'):
   row=bound[direction]
   if row['passed'] or row['witness'] is None:continue
   witness=np.asarray([row['witness']]);near,_,owner=trimesh.proximity.closest_point(output,witness)
   indices=tri[owner[0]];bary=trimesh.triangles.points_to_barycentric(candidate[indices][None],near)[0]
   assert np.isfinite(bary).all() and bary.min()>-1e-8
   bary=np.maximum(bary,0);bary/=bary.sum()
   key=(tuple(map(int,indices)),tuple(np.round(bary,5)))
   if key in memory_keys:continue
   memory_keys.add(key)
   target=trimesh.proximity.closest_point(mesh,witness)[0][0]
   memory.append(dict(vertices=indices.tolist(),barycentric=bary.tolist(),target=target.tolist(),witness=row['witness'],
    diagonal=diagonal,direction=direction,discoveredCandidate=trial['iteration'],sampledMax=row['sampledMax']))

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
definition=definition.replace('    sparsity = lil_matrix(','    groups += [(len(sample_edges)*3,sample_edges)]*2 + [(len(memory_tri)*3,memory_tri),(len(memory_tri),memory_tri)]\n    sparsity = lil_matrix(')
anchor='np.maximum(np.linalg.norm(surface_delta, axis=1) / spacing - .35, 0) * 40]'
assert definition.count(anchor)==1
definition=definition.replace(anchor,anchor[:-1]+', sampled_path_residual(q), memory_residual(q)]')
(OUT/'executed-refine.py').write_text(inspect.getsource(pin_residual)+'\n'+inspect.getsource(sampled_path_residual)+'\n'+inspect.getsource(memory_residual)+'\n'+definition,newline='\n')
namespace=dict(vars(cq),pin_residual=pin_residual,sampled_path_residual=sampled_path_residual,memory_residual=memory_residual);exec(definition,namespace)

def evaluate(p,extra=None,protected=None):
 quality=cq.quad_quality(p,faces,1800);fit=cq._guide_fit(p,paths,curves)
 ratios={};passed={}
 for i,f in enumerate(fit):
  ratios[f'guide{i}Distance']=f['p95Distance']/(.2*spacing)
  ratios[f'guide{i}Angle']=f['p95TangentAngleDegrees']/30
 passed.update({k:bool(v<=1) for k,v in ratios.items()})
 protected=protected or {}
 broken=[k for k in passed if protected.get(k) and not passed[k]]
 contacts=dict(passed=None,checked=False,reason='Rejected by shape or a protected guide gate before contact checking')
 surface=dict(passed=None,checked=False,wholeSurfaceDiagonals={})
 bounds={};eligible=False
 if quality['passed'] and not broken:
  contacts=dict(cq.surface_intersections(p,faces,both_quad_diagonals=True),checked=True)
  if contacts['passed']:
   surface=cq.validate_surface(sv,sf,p,faces,1800);surface['checked']=True;bounds=surface['wholeSurfaceDiagonals'].copy()
   if not bounds:
    for diagonal,a,b in [('02',[0,1,2],[0,2,3]),('13',[0,1,3],[1,2,3])]:
     bounds[diagonal]=cq.surface_distance(mesh,trimesh.Trimesh(p,np.r_[faces[:,a],faces[:,b]],process=False),.5*spacing)
   for diagonal,bound in bounds.items():
    for direction in ('sourceToOutput','outputToSource'):
     key=diagonal+direction;row=bound[direction]
     passed[key]=row['passed'];ratios[key]=row['sampledMax']/(.5*spacing)
     if not row['passed'] and ratios[key]<=1:ratios[key]=1.000001
   broken=[k for k in passed if protected.get(k) and not passed[k]]
   eligible=not broken
 score=max(ratios.values()) if eligible else None
 observed=max((d['sampledMax'] for b in bounds.values() for d in (b['sourceToOutput'],b['outputToSource'])),default=None)
 record=dict(iteration=len(case['attempts']),quality=quality,guideFit=fit,contacts=contacts,surface=surface,witnessBounds=bounds,
  gateRatios=ratios,gatePassed=passed,protectedGateFailures=broken,eligibleForRepair=eligible,maxObservedSurfaceError=observed,
  violationScore=score,qualified=bool(eligible and all(passed.values()) and surface['passed']))
 record.update(extra or {});case['attempts'].append(record);case['qualified']|=record['qualified']
 (OUT/f"{case['name']}-{record['iteration']}.json").write_text(json.dumps(dict(vertices=p.tolist(),faces=faces.tolist())))
 return record

def guide_witnesses(p,gate_passed):
 selected_points=[]
 for index,(path,curve) in enumerate(zip(paths,curves)):
  if gate_passed[f'guide{index}Angle'] and gate_passed[f'guide{index}Distance']:continue
  points=cq._sample(curve,257);tangent=np.roll(points,-1,axis=0)-np.roll(points,1,axis=0)
  tangent[0]=points[1]-points[0];tangent[-1]=points[-1]-points[-2]
  if path['closed']:tangent[0]=tangent[-1]=points[1]-points[-2]
  tangent/=np.maximum(1e-12,np.linalg.norm(tangent,axis=1))[:,None]
  pe=np.array(list(zip(path['vertices'][:-1],path['vertices'][1:])),dtype=int);a=p[pe[:,0]];delta=p[pe[:,1]]-a
  t=np.clip(((points[:,None,:]-a)*delta).sum(axis=2)/(delta*delta).sum(axis=1),0,1)
  ds=np.linalg.norm(points[:,None,:]-a-t[:,:,None]*delta,axis=2);owners=ds.argmin(axis=1)
  unit=delta/np.linalg.norm(delta,axis=1)[:,None]
  angle=np.degrees(np.arccos(np.clip(np.abs((tangent*unit[owners]).sum(axis=1)),0,1)))
  mask=np.zeros(len(points),dtype=bool)
  if not gate_passed[f'guide{index}Angle']:mask|=angle>30
  if not gate_passed[f'guide{index}Distance']:mask|=ds[np.arange(len(points)),owners]>.2*spacing
  selected_points.extend(points[mask])
 return np.asarray(selected_points).reshape(-1,3)

def save(complete):
 (OUT/'result.json').write_text(json.dumps(dict(complete=complete,cases=[case],steps=steps,errors=errors,seed=raw['seed'],
  sourceHashes=hashes,memory=memory,memoryWeight=args.memory_weight,tailWeight=args.tail_weight,tailStartDegrees=25.,implementationUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),
  layoutSource=str(layout_file.relative_to(ROOT)),layoutSha256=hashlib.sha256(layout_file.read_bytes()).hexdigest(),
  initialCandidate=str(candidate_file.relative_to(ROOT)),initialCandidateSha256=hashlib.sha256(candidate_file.read_bytes()).hexdigest(),
  scope='Isolated joint local repair of a retained guide-and-surface-failing candidate. Patch combines actual whole-surface witnesses and outlying samples of currently failing guide metrics. Only patch vertices move. Original shape/surface/distance weights and 401-sample fitting remain. Tangent residual adds a weight 40 tail penalty beyond sin(25 degrees); original 257-sample guide and complete surface acceptance remain. Every previously passing guide or directional surface gate must remain passing. Shape/contact gates always apply. Backtracking decreases the maximum tolerance-normalized measured violation; unresolved bounds cannot count as passed. Cheap rejected steps explicitly skip further checks. Rejected full-surface witnesses are retained as barycentric output-triangle constraints targeting the original surface, with a0.4h barrier. They enlarge the next local patch. Retry a stalled step only when it discovers a new constraint, within the8step budget. Original final gates still decide acceptance. No production result.'),indent=2)+'\n',newline='\n')

try:
 current=evaluate(positions,dict(initial=True));save(False)
 assert current['eligibleForRepair'] and current['witnessBounds'],'Expected a shape/contact-valid candidate with measured surface bounds'
 for step in range(8):
  if current['qualified']:break
  surface_witnesses=np.asarray([d['witness'] for b in current['witnessBounds'].values() for d in (b['sourceToOutput'],b['outputToSource']) if not d['passed'] and d['witness'] is not None]).reshape(-1,3)
  guide_points=guide_witnesses(positions,current['gatePassed'])
  memory_before=len(memory)
  witnesses=np.r_[surface_witnesses,guide_points,np.asarray([m['target'] for m in memory]).reshape(-1,3)]
  assert len(witnesses),'A failed surface bound must expose a witness for this experiment'
  witness_source=trimesh.proximity.closest_point(mesh,witnesses)[0];patch_vertices=set()
  for a,b in (([0,1,2],[0,2,3]),([0,1,3],[1,2,3])):
   tri=np.r_[faces[:,a],faces[:,b]];surface=trimesh.Trimesh(positions,tri,process=False)
   owner=trimesh.proximity.closest_point(surface,witnesses)[2];patch_vertices.update(tri[owner].ravel())
  for item in memory:patch_vertices.update(item['vertices'])
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
  memory_tri=np.asarray([m['vertices'] for m in memory],dtype=int).reshape(-1,3)
  memory_bary=np.asarray([m['barycentric'] for m in memory]).reshape(-1,3)
  memory_target=np.asarray([m['target'] for m in memory]).reshape(-1,3)
  namespace.update(patch_vertices=patch_vertices,witness_source=witness_source,sample_edges=sample_edges,memory_tri=memory_tri)
  started=time.monotonic();proposal,refinement=namespace['_refine'](mesh,positions,faces,edges,pins,targets,1800)
  step_record=dict(step=step,memoryBefore=memory_before,patchVertices=sorted(map(int,patch_vertices)),witnesses=witnesses.tolist(),surfaceWitnessCount=len(surface_witnesses),guideWitnessCount=len(guide_points),refinement=refinement,continued=False,trials=[]);steps.append(step_record)
  for power in range(5):
   alpha=.5**power;candidate=positions+alpha*(proposal-positions)
   outside=np.array(sorted(set(range(len(positions)))-patch_vertices),dtype=int);assert np.array_equal(candidate[outside],positions[outside])
   trial=evaluate(candidate,dict(step=step,alpha=alpha,elapsedSeconds=time.monotonic()-started),protected=current['gatePassed']);step_record['trials'].append(trial['iteration'])
   remember(candidate,trial)
   step_record['memoryAfter']=len(memory)
   progress=trial['eligibleForRepair'] and trial['violationScore']<current['violationScore']-1e-6
   print('step',step,'patch',len(patch_vertices),'alpha',alpha,'guide',[round(f['p95TangentAngleDegrees'],3) for f in trial['guideFit']],'contacts',trial['contacts']['passed'],'violation',trial['violationScore'],'qualified',trial['qualified'],'progress',progress,'memory',len(memory),flush=True)
   if trial['qualified'] or progress:
    positions=candidate;current=trial;step_record.update(continued=True,continuedCandidate=trial['iteration']);save(False);break
   save(False)
  if not step_record['continued'] and len(memory)==memory_before:break
except Exception:
 errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:save(True)
raise SystemExit(1 if errors else 0)
