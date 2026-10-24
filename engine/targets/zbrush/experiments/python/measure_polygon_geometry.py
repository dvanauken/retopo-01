"""Explicit projected-ear triangulation convention for nonconvex native polygons.
This is a measurement surface convention, not recovered ZBrush triangulation.
"""
from pathlib import Path
import hashlib,numpy as np,trimesh
from measure_geometry import read_obj,topology,surface_samples,surface_distances,guide_alignment

def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def triangulate(vertices,faces,epsilon=1e-12):
 result=[]
 for face in faces:
  if len(set(face))!=len(face):raise ValueError('Repeated polygon vertex')
  if len(face)==3:result.append(face);continue
  p=vertices[face];_,_,basis=np.linalg.svd(p-p.mean(axis=0),full_matrices=False);q=(p-p.mean(axis=0))@basis[:2].T;n=len(face)
  for i in range(n):
   for j in range(i+1,n):
    if j==(i+1)%n or i==(j+1)%n:continue
    a,b=q[i],q[(i+1)%n];c,d=q[j],q[(j+1)%n];v=[cross(b-a,c-a),cross(b-a,d-a),cross(d-c,a-c),cross(d-c,b-c)]
    if v[0]*v[1]<-epsilon**2 and v[2]*v[3]<-epsilon**2:raise ValueError('Self-crossing polygon projection')
  area=sum(cross(q[i],q[(i+1)%n]) for i in range(n))/2
  if abs(area)<=1e-14:raise ValueError('Zero projected polygon area')
  sign=1 if area>0 else -1;remaining=list(range(n))
  while len(remaining)>3:
   for k,i in enumerate(remaining):
    a,b,c=remaining[k-1],i,remaining[(k+1)%len(remaining)]
    if sign*cross(q[b]-q[a],q[c]-q[b])<=epsilon:continue
    inside=False
    for j in remaining:
     if j in [a,b,c]:continue
     if all(sign*cross(q[y]-q[x],q[j]-q[x])>=-epsilon for x,y in [(a,b),(b,c),(c,a)]):inside=True;break
    if inside:continue
    result.append([face[a],face[b],face[c]]);remaining.pop(k);break
   else:raise ValueError('No nondegenerate projected ear')
  result.append([face[i] for i in remaining])
 triangles=np.array(result,dtype=int);p=vertices[triangles];areas=np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)/2
 if np.any(areas<=1e-14):raise ValueError('Zero area triangle in selected measurement surface')
 return triangles

def measure(source,output,guides,coordinate_frame_qualified):
 if not coordinate_frame_qualified:raise ValueError('Coordinate mapping unqualified')
 v,f=read_obj(source);ov,of=read_obj(output);base,_,_=topology(v,f);out,_,edges=topology(ov,of);tri=triangulate(v,f);ot=triangulate(ov,of)
 return dict(schemaVersion=1,method='Best-fit-plane projected ear triangulation with preserved polygon winding; sampled exact triangle distance; nearest-edge guide alignment.',coordinateFrameQualified=True,source=dict(path=str(source),sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),metrics=base),output=dict(path=str(output),sha256=hashlib.sha256(Path(output).read_bytes()).hexdigest(),metrics=out),canonicalGeometryChanged=base['canonicalGeometrySignature']!=out['canonicalGeometrySignature'],sourceToOutput=surface_distances(ov,ot,surface_samples(v,tri)),outputToSource=surface_distances(v,tri,surface_samples(ov,ot)),guideAlignment=[guide_alignment(ov,edges,g) for g in guides],remeshingQualified=False,tolerances=dict(projectedEar=1e-12,triangleArea=1e-14),toolchain=dict(numpy=np.__version__,trimesh=trimesh.__version__,measurementSourceSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),baseSourceSha256=hashlib.sha256(Path(__file__).with_name('measure_geometry.py').read_bytes()).hexdigest()),limitations=['Projected ear triangulation defines a chosen surface for nonplanar polygons; it is not the native hidden diagonal.','Self-crossing, repeated or untriangulable polygons fail explicitly.','Deviation is sampled, not certified Hausdorff.','This measurement alone does not prove remeshing execution.'])
