"""Reproduce the plain toilet fixture from the user's Draco GLB (never the gold variant)."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile,shutil,sys
import numpy as np,trimesh

ROOT=Path(__file__).resolve().parents[1]
def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=ROOT/'assets/raw/toilet/SW_Toilet.closed.web.glb');ap.add_argument('--blender',default=r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe');args=ap.parse_args()
 if args.source.name!='SW_Toilet.closed.web.glb':raise ValueError('Use the original plain SW_Toilet.closed.web.glb asset.')
 raw=ROOT/'assets/raw/toilet';raw.mkdir(parents=True,exist_ok=True)
 if args.source.resolve()!=(raw/args.source.name).resolve():shutil.copyfile(args.source,raw/args.source.name)
 with tempfile.TemporaryDirectory(prefix='retopo-toilet-') as scratch:
  extracted=Path(scratch)/'mesh.json'
  subprocess.run([args.blender,'--background','--python',str(ROOT/'scripts/extract_blender_mesh.py'),'--',str(args.source.resolve()),str(extracted)],check=True)
  data=json.loads(extracted.read_text())
 v=np.asarray(data['vertices'],float);f=np.asarray(data['faces'],int);repaired=0
 # A zero-area triangle can encode a collinear split of its opposite neighbor.
 # Conform that neighbor at the existing middle vertex; never displace geometry.
 while True:
  areas=np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1);bad=np.flatnonzero(areas<=1e-16)
  if not len(bad):break
  index=int(bad[0]);a,b,c=map(int,f[index]);pairs=[(a,b,c),(b,c,a),(c,a,b)];a,c,b=max(pairs,key=lambda q:np.linalg.norm(v[q[0]]-v[q[1]]))
  adjacent=[i for i,face in enumerate(f) if i!=index and a in face and c in face]
  if len(adjacent)!=1:raise ValueError('Cannot conform a collapsed source triangle safely.')
  neighbor=adjacent[0];row=list(map(int,f[neighbor]));edge=next(j for j in range(3) if {row[j],row[(j+1)%3]}=={a,c});start,end,opposite=row[edge],row[(edge+1)%3],row[(edge+2)%3]
  replacement=np.array([[start,b,opposite],[b,end,opposite]])
  f=np.concatenate((np.delete(f,[index,neighbor],axis=0),replacement));repaired+=1
 original_bounds=np.array([v.min(axis=0),v.max(axis=0)])
 # Blender has already converted glTF Y-up to Z-up. Rotate around Z to expose
 # the front to this application's default camera; normalize only by a similarity.
 center=original_bounds.mean(axis=0);scale=2/np.ptp(v,axis=0).max();v=(v-center)*np.array([-1.,-1.,1.])*scale
 obj=ROOT/'assets/models/toilet.obj'
 with obj.open('w',encoding='utf-8',newline='\n') as stream:
  stream.write('# Plain white SW_Toilet; original source geometry, normalized Z-up.\n')
  for p in v:stream.write('v '+' '.join(format(float(x),'.12g') for x in p)+'\n')
  for face in f:stream.write('f '+' '.join(str(int(i)+1) for i in face)+'\n')
 v=np.array([[float(x) for x in line.split()[1:4]] for line in obj.read_text().splitlines() if line.startswith('v ')])
 mesh=trimesh.Trimesh(v,f,process=False)
 if not mesh.is_watertight or not mesh.is_winding_consistent or len(mesh.split(only_watertight=False))!=1:raise ValueError('Decoded toilet failed closed-surface validation.')
 sys.path.insert(0,str(ROOT/'engine/targets/zbrush/experiments/python'))
 from measure_geometry import topology
 stats,_,_=topology(v,f.tolist())
 entry={'id':'toilet','title':'White toilet','description':'The original plain SW_Toilet, decoded from its closed white mesh. A detailed curved test subject for surface guides; this mesh uses the general solver.','source':{'author':'User-provided SW_Toilet','license':'Original source attribution not recorded','url':'','asset':args.source.name},'surface':'closed','featurePolicy':'native-qualified','target':1800,'sourceSha256':sha(obj),'displayColor':'#f5f5f2','displaySmooth':True,'wireOpacity':.22,'requiresGuides':False,'experimentalRetopology':False,'solver':'surface-quads','solverNotice':'Guides steer fitted quad edge paths. Each result must pass surface, topology and quad-quality checks.'}
 section=mesh.section(plane_origin=[0,0,.1],plane_normal=[0,0,1]);contour=max(section.discrete,key=lambda p:np.linalg.norm(np.diff(p,axis=0),axis=1).sum())
 presets=[{'name':'Bowl contour','description':'Actual horizontal intersection of the original bowl surface, at normalized z=0.1.','curves':[contour.tolist()]}]
 write(ROOT/'assets/models/toilet.json',dict(entry,vertices=v.tolist(),faces=f.tolist(),creases=[],presets=presets,stats=stats))
 catalog=json.loads((ROOT/'assets/catalog.json').read_text());catalog=[e for e in catalog if e['id']!='toilet'];catalog.append(entry);write(ROOT/'assets/catalog.json',catalog)
 provenance={'sourceFile':str(args.source.resolve()),'sourceSha256':sha(args.source),'sourceKind':'Original plain, non-gold closed GLB exported from SW_Toilet.skp via SW_Toilet.glb in the user-provided model collection.','originalDecodedBounds':original_bounds.tolist(),'decodedVertices':len(v),'decodedTriangles':len(data['faces']),'collinearTrianglesRepaired':repaired,'preparedTriangles':len(f),'watertight':bool(mesh.is_watertight),'consistentWinding':bool(mesh.is_winding_consistent),'components':1,'eulerCharacteristic':int(mesh.euler_number),'conversion':{'decoder':'Blender glTF Draco importer','axis':'glTF Y-up to Blender Z-up, then rotation pi around Z','center':center.tolist(),'uniformScale':float(scale),'geometryEdits':'Coordinate similarity and conformity repair of '+str(repaired)+' collinear triangles by splitting adjacent faces at existing vertices; no vertex displacement, decimation or geometry substitution.','materialOverride':'White nonmetallic porcelain #f5f5f2; decoded vertices retained; local triangle conformity recorded above.'},'preparedObjSha256':sha(obj),'preparedMeshJsonSha256':sha(ROOT/'assets/models/toilet.json')}
 write(raw/'preparation.json',provenance);print(json.dumps(provenance,indent=2))
if __name__=='__main__':main()
