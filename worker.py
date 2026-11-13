"""Original mesh + actual surface curves -> reference construction -> measured export."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,sys,traceback,time
# One math thread per process, set before NumPy loads: the low bits of a result depend on the number of BLAS threads,
# and rows layouts are processed several processes at a time. The verification scripts have always run this way.
for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(_name,'1')
from process_ownership import protect_service_tree
from job_progress import emit
import numpy as np
ROOT=Path(__file__).resolve().parent;ENGINE=ROOT/'engine'
sys.path.insert(0,str(ENGINE/'targets/zbrush/clone'));sys.path.insert(0,str(ENGINE/'targets/zbrush/experiments/python'))
from retopo import construct,read_obj,write_obj,OutputValidationError
from terrain import construct_heightfield
from features import output_creases
from measure_geometry import topology,guide_alignment
from mesh_validation import links
from structured_prism import construct as construct_structured,detect as detect_prism
from quad_quality import measure as measure_quad_quality
from source_features import measure as measure_source_features, use_crease_angle
from crease_angle import DEFAULT as DEFAULT_CREASE_ANGLE
from curved_quad import construct as construct_curved_quads, BACKEND as SURFACE_QUAD_BACKEND, guide_tangent_limits
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,data):p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def pack(vertices,faces,source,curves,target,metadata,elapsed):
 faces=[list(map(int,f)) for f in faces];vertices=np.asarray(vertices);stats,_,edges=topology(vertices,faces);vl=links(faces)
 samples=[np.asarray(c)[np.linspace(0,len(c)-1,min(len(c),129),dtype=int)] for c in curves]
 alignment=[p['alignment'] for p in metadata['guidePaths']] if metadata['backend']==SURFACE_QUAD_BACKEND else [guide_alignment(vertices,edges,c) for c in samples];crease=metadata.get('outputCreases') or output_creases(vertices,faces)
 return dict(quality=measure_quad_quality(vertices,faces,target,extra_faces=bool(metadata.get('extraFaces'))),guidePaths=metadata.get('guidePaths',[]),vertices=vertices.tolist(),faces=faces,creases=crease['edges'],stats=stats,vertexLinks=vl,guideAlignment=alignment,guideSampleMethod='Up to129 evenly indexed surface samples per curve; Euclidean distance to actual output edges and unsigned tangent angles.',target=target,elapsedSeconds=elapsed,backend=metadata['backend'],validationPassed=True,quadPercent=100*stats['quadFraction'],sourceSha256=source,guideCount=len(curves),coordinateFrame='source',limits='Measured surface/topology checks are bounded; they do not certify absence of every3D self intersection or exact native equivalence.')

def main():
 protect_service_tree()
 ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--feature-layout',action='store_true');args=ap.parse_args();job=args.job.resolve()
 if not job.is_relative_to(ROOT/'runs'):raise ValueError('Job must be inside this project runs directory')
 settings=read(job/'settings.json');curve_packet=read(job/'curves.json');key=settings['meshId'];spec=read(ROOT/'assets/models'/(key+'.json'))
 source=ROOT/'assets/models'/(key+'.obj')
 if settings.get('partSource'):
  from mesh_parts import load_part
  spec,part_folder=load_part(settings['partSource'],key);source=part_folder/'source.obj'
  if not spec['canRemesh']:raise ValueError('This working part has no supported generation route.')
  write(job/'part-provenance.json',dict(recipe=spec['partRecipe'],repair=spec['repair'],originalSourceSha256=spec['originalSourceSha256']))
 shutil.copyfile(source,job/'source.obj');assert sha(source)==settings['sourceSha256'];curves=curve_packet['curves'];v,f=read_obj(job/'source.obj');start=time.monotonic();constructed=False
 try:
  crease_angle=settings.get('creaseAngle',DEFAULT_CREASE_ANGLE);use_crease_angle(crease_angle)
  emit(job,f"Starting generation · target {settings['target']:,} quads · {len(curves)} guides · {len(f):,} source triangles · crease angle {crease_angle:g}°",kind='start',details=dict(partSource=settings.get('partSource'),target=settings['target'],guides=len(curves),creaseAngle=crease_angle))
  if settings.get('allowExtraFaces') and spec.get('solver')!='open-surface-quads':
   emit(job,'Add faces where the shape needs them is available for open parts only; this part keeps its count within tolerance of the target.',kind='stage')
  options=dict(target=settings['target'],normalize=False)
  if spec.get('solver')=='open-surface-quads':
   from open_surface import construct as construct_open_surface
   # Rows layouts are processed several at a time; the accepted mesh does not depend on how many (open_surface.ROW_WORKERS).
   import open_surface
   row_workers=max(1,int(os.environ.get('RETOPO_ROW_WORKERS',min(open_surface.ROW_WORKERS,max(1,(os.cpu_count() or 2)//2)))))
   positions,faces,meta=construct_open_surface(v,f,curves,target=settings['target'],job=job,extra_faces=bool(settings.get('allowExtraFaces',False)),workers=row_workers)
  elif spec.get('solver')=='surface-quads':
   if args.feature_layout or spec.get('featureLayout',False):
    from feature_quad import construct as construct_feature_quads
    positions,faces,meta=construct_feature_quads(v,f,curves,target=settings['target'],job=job)
   else:positions,faces,meta=construct_curved_quads(v,f,curves,target=settings['target'],job=job,guided_layout=spec.get('guidedLayout',False))
  elif spec['surface']=='heightfield':positions,faces,meta=construct_heightfield(v,f,curves,**options)
  else:
   try:detect_prism(v,f)
   except NotImplementedError:positions,faces,meta=construct(v,f,curves,guide_mode=settings['guideMode'],feature_policy=spec['featurePolicy'],solid_method='auto',**options)
   else:positions,faces,meta=construct_structured(v,f,curves,target=settings['target'])
  constructed=True
  elapsed=time.monotonic()-start;mesh=pack(positions,faces,settings['sourceSha256'],curves,settings['target'],meta,elapsed)
  if settings.get('partSource'):mesh.update(partSource=settings['partSource'],originalSourceSha256=spec['originalSourceSha256'],sourceRepair=spec['repair'])
  if meta['backend']==SURFACE_QUAD_BACKEND:
   mesh['guideSampleMethod']='257 uniformly spaced authored arc-length samples per guide, measured against its connected output-edge path.'
   mesh['surfaceValidation']=meta['closedValidation']
   if meta.get('openSurface'):mesh.update(openSurface=True,boundaryValidation=meta['boundaryValidation'])
   for field in ('featureRows','registeredFeatures','registrationSkipped','layoutStyle','candidateSelection','creaseRows'):
    if field in meta:mesh[field]=meta[field]
   mesh['intersectionValidation']=meta['intersectionValidation']
   # Crease rows are enforced where the solver fits them (open parts); the closed-part solver records them.
   # With extra faces allowed on an open part, a face is the local face at each crease edge (crease_rows.local_sizes).
   mesh['featureValidation']=measure_source_features(v,f,positions,faces,settings['target'],enforce_rows=bool(meta.get('openSurface')),extra_faces=bool(meta.get('openSurface') and meta.get('extraFaces') and meta.get('localFaces',True)))
   mesh['featurePolicy']='enforced' if 'featureValidation' in meta else 'diagnostic'
   write(job/'source-features.json',mesh['featureValidation'])
   if mesh['featurePolicy']=='enforced' and not mesh['featureValidation']['passed']:
    raise ValueError('Source feature preservation failed: '+', '.join(mesh['featureValidation']['failures']))
   if meta.get('openSurface'):
    # Independent of the solver's own bookkeeping: the source against the output where crease branches meet
    # (corner_zones). Reported for every open part; a failing corner rejects the mesh when extra faces are allowed.
    import corner_zones
    from source_features import detect as detect_creases, spacing as requested_spacing
    corner_spacing=requested_spacing(v,f,settings['target']);crease_edges,_=detect_creases(v,f,corner_spacing,target=settings['target'])
    # Enforced while the solver's local-face rules were in force; reported when it fell back to the strict-count rows.
    solver_corners=meta.get('cornerZones',{})
    mesh['cornerZones']=dict(corner_zones.measure(v,f,crease_edges,positions,faces,corner_spacing),enforced=bool(solver_corners.get('enforced',meta.get('extraFaces'))),extraFacesFallback=bool(solver_corners.get('extraFacesFallback')))
    write(job/'corner-zones.json',mesh['cornerZones'])
    if mesh['cornerZones']['enforced'] and not mesh['cornerZones']['passed']:
     raise ValueError('Corner zones are not followed: '+', '.join(mesh['cornerZones']['failures']))
  valid=mesh['stats']['nonmanifoldEdges']==0 and mesh['stats']['zeroAreaFanTriangles']==0 and not mesh['vertexLinks']['nonmanifoldVertices'] and mesh['vertexLinks']['inconsistentWindingEdges']==0
  if not valid:raise ValueError('Output failed the demo topology checks')
  h=float(np.sqrt(np.sum(np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1))*.5/settings['target']))
  guide_failures=[]
  if meta['backend'] in ('engineering-structured-prismatic-annulus',SURFACE_QUAD_BACKEND):
   missing=set(range(len(curves)))-{p['curve'] for p in mesh['guidePaths']}
   if missing:guide_failures.append('No measured output edge path for guide(s): '+', '.join(str(i+1) for i in sorted(missing)))
  angle_limits=guide_tangent_limits(mesh['guidePaths']) if meta['backend']==SURFACE_QUAD_BACKEND else [30]*len(mesh['guidePaths'])
  for path,angle_limit in zip(mesh['guidePaths'],angle_limits):
   if path['p95Distance']>.20*h:guide_failures.append('guide path distance exceeds 0.20 target edge lengths')
   if path['p95TangentAngleDegrees']>angle_limit:guide_failures.append(f'guide tangent error exceeds {angle_limit:g} degrees')
  if meta.get('openSurface') and curves:
   # Independent of the solver's own bookkeeping: each guide needs one continuous edge loop (guide_rows).
   from guide_rows import measure as measure_guide_rows
   mesh['guideRows']=measure_guide_rows(positions,faces,[np.asarray(c,float) for c in curves],h)
   for item in mesh['guideRows']['guides']:
    if not item['passed']:guide_failures.append(f"guide {item['curve']+1} is not followed by one continuous edge loop ("+', '.join(item['failures'])+')')
  if guide_failures:mesh['quality']['passed']=False;mesh['quality']['failures'].extend(guide_failures)
  write(job/'quality.json',mesh['quality'])
  if not mesh['quality']['passed']:
   write(job/'failed-mesh.json',mesh)
   raise ValueError('Mesh quality rejected: '+', '.join(mesh['quality']['failures'])+'. The candidate is retained for inspection; it is not a qualified result.')
  write_obj(job/'output.obj',positions,faces);write(job/'mesh.json',mesh);write(job/'features.json',meta.get('outputCreases',output_creases(positions,faces)));write(job/'engine-provenance.json',meta)
  emit(job,f'Accepted {len(faces):,} faces in {time.monotonic()-start:.1f}s. Output is ready to view and export.',kind='complete')
  write(job/'report.json',dict(passed=True,constructionCompleted=True,vertices=len(positions),faces=len(faces),elapsedSeconds=elapsed,sourceSha256=sha(job/'source.obj'),curvesSha256=sha(job/'curves.json'),outputSha256=sha(job/'output.obj'),workerSha256=sha(Path(__file__)),backend=meta['backend'],qualityPassed=mesh['quality']['passed'],quality=mesh['quality'],scope='Actual original-input construction from user surface guides. No native process or native output oracle. Geometry validation and methods retained.'))
  print(json.dumps(dict(passed=True,vertices=len(positions),faces=len(faces),elapsedSeconds=elapsed)),flush=True);return 0
 except Exception as error:
  message=str(error)
  diagnostics=getattr(error,'diagnostics',None)
  if diagnostics is not None and settings.get('allowExtraFaces') and spec.get('solver')=='open-surface-quads':
   # With extra faces allowed the acceptance asks for more: say so, and how to generate without it.
   message+=' "Add faces where the shape needs them" is checked; neither its own rules nor the rows of the strict count gave an acceptable mesh without a count ceiling. Unchecking it may still generate within the count tolerance.'
  if isinstance(error,NotImplementedError) and message=='Degenerate source normal policy':message='The solver created a degenerate triangle during mesh conditioning. No result was accepted; your source mesh and guides are unchanged.'
  if constructed:write_obj(job/'failed-output.obj',positions,faces)
  if isinstance(error,OutputValidationError):write_obj(job/'failed-output.obj',error.positions,error.faces);write(job/'failed-validation.json',error.validation)
  emit(job,f'Generation failed after {time.monotonic()-start:.1f}s: {message}',level='error',kind='failed',details=diagnostics)
  write(job/'report.json',dict(passed=False,constructionCompleted=constructed or isinstance(error,OutputValidationError),message=message,diagnostics=diagnostics,technicalMessage=str(error),traceback=traceback.format_exc(),elapsedSeconds=time.monotonic()-start,sourceSha256=sha(job/'source.obj'),workerSha256=sha(Path(__file__))));traceback.print_exc();return 1
if __name__=='__main__':raise SystemExit(main())
