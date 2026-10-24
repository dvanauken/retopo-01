"""EXP-0051: reference tangent bases, projected target angles, normal transport."""
import argparse,json,math,struct
from pathlib import Path
import numpy as np
from probe_transport_helpers import ROOT,f32,dot,cross,unsigned,oriented,rotation

def normalize(v):
 norm=math.sqrt(float(dot(v,v)))
 return (v.astype('f8')/norm).astype('f4') if norm>=1e-28 else v.copy(),f32(norm)
def perpendicular(n):
 x,y,z=abs(n)
 basis=np.array([1,0,0] if x<=y and z>=x else [0,0,1] if (x<=y and z<x) or (x>y and z<=y) else [0,1,0],dtype='f4')
 return cross(basis,n)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('capture');a=ap.parse_args();root=Path(a.capture).resolve();p=next(root.glob('*-return-0x1e6990'));field=next(root.glob('*-field-before-release'))
 def array(folder,name,d='<f4'):return np.fromfile(folder/name,d)
 h=(field/'field-structure.bin').read_bytes();assert struct.unpack_from('<i',h,0x2f0)[0]==0,'Symmetry needs a separate fixture'
 xyz=array(p,'source-positions.f32x3').reshape(-1,3);tri=array(p,'source-triangles.i32x3','<i4').reshape(-1,3);normal=array(p,'source-normal.f32x3').reshape(-1,3);nativeA=array(p,'basis-a.f32x3').reshape(-1,3);nativeB=array(p,'basis-b.f32x3').reshape(-1,3);direction=array(field,'directions.f32x3').reshape(-1,3);expectedA=[];expectedB=[];length=[];target=[]
 for i,t in enumerate(tri):
  aa,ll=normalize(f32(xyz[t[1]]-xyz[t[0]]));bb,_=normalize(cross(normal[i],aa));expectedA.append(aa);expectedB.append(bb);length.append(ll)
  projected=f32(direction[i]-f32(normal[i]*dot(direction[i],normal[i])));angle=float(f32(oriented(aa,projected,normal[i])))
  if angle>float(f32(math.pi)):angle+=-2*math.pi
  target.append(angle)
 checks=[]
 def compare(name,got,want,tol):
  error=abs(np.asarray(got)-np.asarray(want));checks.append(dict(name=name,passed=bool((error<=tol).all()),values=int(error.size),maxAbsoluteError=float(error.max(initial=0)),tolerance=tol))
 compare('basis-a',nativeA,expectedA,2e-6);compare('basis-b',nativeB,expectedB,2e-6);compare('local-length',array(p,'local-length.f32'),length,2e-6);compare('projected-target-angle',array(p,'target-angle.f64','<f8'),target,2e-6)
 offsets=array(p,'source-edge-face-offset.i32','<i4');corners=array(p,'source-edge-face-corners.i32','<i4');transport=np.zeros(len(offsets)-1,dtype='f4');generic=parallel=opposite=0
 for edge in range(len(transport)):
  if offsets[edge+1]-offsets[edge]!=2:continue
  i,j=corners[offsets[edge]:offsets[edge+1]]//3;axis=cross(normal[j],normal[i]);sq=float(dot(axis,axis))
  if sq>=1e-7:
   axis,_=normalize(axis);theta=f32(oriented(normal[j],normal[i],axis));matrix=rotation(axis,theta);generic+=1
  elif dot(normal[i],normal[j])<0:matrix=rotation(perpendicular(normal[j]),f32(math.pi));opposite+=1
  else:matrix=np.eye(3,dtype='f4');parallel+=1
  # Native218220 accumulates y*x + x*x + z*x in double then narrows.
  moved=np.array([f32(float(matrix[row,1])*float(nativeA[j,1])+float(matrix[row,0])*float(nativeA[j,0])+float(matrix[row,2])*float(nativeA[j,2])) for row in range(3)])
  angle=f32(oriented(nativeA[i],moved,normal[i]))
  if angle>f32(math.pi):angle=f32(angle+f32(-2*math.pi))
  transport[edge]=angle
 compare('normal-transport-connection',array(next(root.glob('*-entry-0x281020')),'connection-angle.f32'),transport,2e-6)
 result=dict(experimentId='EXP-0051',capture=root.relative_to(ROOT).as_posix(),cases=checks,passed=all(c['passed'] for c in checks),branches=dict(generic=generic,parallel=parallel,antiparallel=opposite),scope='Nonsymmetric reference basis/default first source edge, projected target angle and transported reference connection. Initial quarter integers and symmetry are separate.')
 dest=root/'angular-transport-check.json'
 if dest.exists():raise RuntimeError('Preserve previous result')
 dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
