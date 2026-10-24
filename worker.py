"""Original mesh + actual surface curves -> reference construction -> measured export."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys,traceback,time
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
from curved_quad import construct as construct_curved_quads, BACKEND as SURFACE_QUAD_BACKEND
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,data):p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def pack(vertices,faces,source,curves,target,metadata,elapsed):
 faces=[list(map(int,f)) for f in faces];vertices=np.asarray(vertices);stats,_,edges=topology(vertices,faces);vl=links(faces)
 samples=[np.asarray(c)[np.linspace(0,len(c)-1,min(len(c),129),dtype=int)] for c in curves]
 alignment=[p['alignment'] for p in metadata['guidePaths']] if metadata['backend']==SURFACE_QUAD_BACKEND else [guide_alignment(vertices,edges,c) for c in samples];crease=metadata.get('outputCreases') or output_creases(vertices,faces)
 return dict(quality=measure_quad_quality(vertices,faces,target),guidePaths=metadata.get('guidePaths',[]),vertices=vertices.tolist(),faces=faces,creases=crease['edges'],stats=stats,vertexLinks=vl,guideAlignment=alignment,guideSampleMethod='Up to129 evenly indexed surface samples per curve; Euclidean distance to actual output edges and unsigned tangent angles.',target=target,elapsedSeconds=elapsed,backend=metadata['backend'],validationPassed=True,quadPercent=100*stats['quadFraction'],sourceSha256=source,guideCount=len(curves),coordinateFrame='source',limits='Measured surface/topology checks are bounded; they do not certify absence of every3D self intersection or exact native equivalence.')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);args=ap.parse_args();job=args.job.resolve()
 if not job.is_relative_to(ROOT/'runs'):raise ValueError('Job must be inside this project runs directory')
 settings=read(job/'settings.json');curve_packet=read(job/'curves.json');key=settings['meshId'];spec=read(ROOT/'assets/models'/(key+'.json'))
 source=ROOT/'assets/models'/(key+'.obj');shutil.copyfile(source,job/'source.obj');assert sha(source)==settings['sourceSha256'];curves=curve_packet['curves'];v,f=read_obj(job/'source.obj');start=time.monotonic();constructed=False
 try:
  options=dict(target=settings['target'],normalize=False)
  if spec.get('solver')=='surface-quads':positions,faces,meta=construct_curved_quads(v,f,curves,target=settings['target'],job=job)
  elif spec['surface']=='heightfield':positions,faces,meta=construct_heightfield(v,f,curves,**options)
  else:
   try:detect_prism(v,f)
   except NotImplementedError:positions,faces,meta=construct(v,f,curves,guide_mode=settings['guideMode'],feature_policy=spec['featurePolicy'],solid_method='auto',**options)
   else:positions,faces,meta=construct_structured(v,f,curves,target=settings['target'])
  constructed=True
  elapsed=time.monotonic()-start;mesh=pack(positions,faces,settings['sourceSha256'],curves,settings['target'],meta,elapsed)
  if meta['backend']==SURFACE_QUAD_BACKEND:
   mesh['guideSampleMethod']='257 uniformly spaced authored arc-length samples per guide, measured against its connected output-edge path.'
   mesh['surfaceValidation']=meta['closedValidation']
  valid=mesh['stats']['nonmanifoldEdges']==0 and mesh['stats']['zeroAreaFanTriangles']==0 and not mesh['vertexLinks']['nonmanifoldVertices'] and mesh['vertexLinks']['inconsistentWindingEdges']==0
  if not valid:raise ValueError('Output failed the demo topology checks')
  h=float(np.sqrt(np.sum(np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1))*.5/settings['target']))
  guide_failures=[]
  if meta['backend'] in ('engineering-structured-prismatic-annulus',SURFACE_QUAD_BACKEND):
   missing=set(range(len(curves)))-{p['curve'] for p in mesh['guidePaths']}
   if missing:guide_failures.append('No measured output edge path for guide(s): '+', '.join(str(i+1) for i in sorted(missing)))
  for path in mesh['guidePaths']:
   if path['p95Distance']>.20*h:guide_failures.append('guide path distance exceeds 0.20 target edge lengths')
   if path['p95TangentAngleDegrees']>30:guide_failures.append('guide tangent error exceeds 30 degrees')
  if guide_failures:mesh['quality']['passed']=False;mesh['quality']['failures'].extend(guide_failures)
  write(job/'quality.json',mesh['quality'])
  if not mesh['quality']['passed']:
   write(job/'failed-mesh.json',mesh)
   raise ValueError('Mesh quality rejected: '+', '.join(mesh['quality']['failures'])+'. The candidate is retained for inspection; it is not a qualified result.')
  write_obj(job/'output.obj',positions,faces);write(job/'mesh.json',mesh);write(job/'features.json',meta.get('outputCreases',output_creases(positions,faces)));write(job/'engine-provenance.json',meta)
  write(job/'report.json',dict(passed=True,constructionCompleted=True,vertices=len(positions),faces=len(faces),elapsedSeconds=elapsed,sourceSha256=sha(job/'source.obj'),curvesSha256=sha(job/'curves.json'),outputSha256=sha(job/'output.obj'),workerSha256=sha(Path(__file__)),backend=meta['backend'],qualityPassed=mesh['quality']['passed'],quality=mesh['quality'],scope='Actual original-input construction from user surface guides. No native process or native output oracle. Geometry validation and methods retained.'))
  print(json.dumps(dict(passed=True,vertices=len(positions),faces=len(faces),elapsedSeconds=elapsed)),flush=True);return 0
 except Exception as error:
  message=str(error)
  if isinstance(error,NotImplementedError) and message=='Degenerate source normal policy':message='The solver created a degenerate triangle during mesh conditioning. No result was accepted; your source mesh and guides are unchanged.'
  if constructed:write_obj(job/'failed-output.obj',positions,faces)
  if isinstance(error,OutputValidationError):write_obj(job/'failed-output.obj',error.positions,error.faces);write(job/'failed-validation.json',error.validation)
  write(job/'report.json',dict(passed=False,constructionCompleted=constructed or isinstance(error,OutputValidationError),message=message,technicalMessage=str(error),traceback=traceback.format_exc(),elapsedSeconds=time.monotonic()-start,sourceSha256=sha(job/'source.obj'),workerSha256=sha(Path(__file__))));traceback.print_exc();return 1
if __name__=='__main__':raise SystemExit(main())
