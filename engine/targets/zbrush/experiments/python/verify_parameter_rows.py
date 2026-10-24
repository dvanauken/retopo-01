"""Compare recovered per-triangle equations to unmodified native assembly captures."""
import argparse,json,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
def read(folder,name,dtype,dim=1):
 a=np.fromfile(folder/name,dtype=dtype);return a.reshape(-1,dim) if dim>1 else a

def dot32(a,b):return np.float32(np.float32(np.float32(a[1]*b[1])+np.float32(a[0]*b[0]))+np.float32(a[2]*b[2]))
def equations(p,frame_a,frame_b,length,direction_a,direction_b,scale_u,scale_v):
 e1=np.float32(p[1]-p[0]);e2=np.float32(p[2]-p[0]);cross=np.cross(e1,e2);D=np.sqrt(np.float32(np.float32(cross[0]*cross[0]+cross[1]*cross[1])+np.float32(cross[2]*cross[2])),dtype=np.float32)
 if D==0:raise ValueError('Degenerate triangle requires recovered native sentinel')
 x=float(dot32(e2,frame_a));y=float(dot32(e2,frame_b));L=float(length)
 gx=np.array([-y,y,0.]);gy=np.array([x-L,-x,L])
 def row(direction,scale):return (float(direction[0])*float(scale)/float(D))*gx+(float(direction[1])*float(scale)/float(D))*gy
 return [row(direction_a,scale_u),row(direction_b,scale_u),row(direction_b,scale_v),row(direction_a,scale_v)]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('capture');args=ap.parse_args();root=Path(args.capture).resolve();entry=next(root.glob('*-entry-0x296050'));m=json.loads((next(root.glob('*-return-0x2992d0'))/'matrix-rows.json').read_text())
 pts=read(entry,'source-positions.f32x3','<f4',3);tri=read(entry,'source-triangles.i32x3','<i4',3);ids=read(entry,'parameter-triangles.i32x3','<i4',3);perm=read(entry,'triangle-permutation.u8','u1');fa=read(entry,'basis-a.f32x3','<f4',3);fb=read(entry,'basis-b.f32x3','<f4',3);length=read(entry,'local-length.f32','<f4');da=read(entry,'uv-direction-a.f32x2','<f4',2);db=read(entry,'uv-direction-b.f32x2','<f4',2);structure=(entry/'component-structure.bin').read_bytes();scale=struct.unpack_from('<f',structure,0x6c0)[0];su=read(entry,'scale-a.f32','<f4');sv=read(entry,'scale-b.f32','<f4');per_face=len(su)==len(tri) and len(sv)==len(tri)
 errors=[];bad=[];rows=[]
 for f in range(len(tri)):
  order=np.roll(np.arange(3),-int(perm[f]));p=pts[tri[f,order]];vertex_ids=ids[f,order];expected=equations(p,fa[f],fb[f],length[f],da[f],db[f],su[f] if per_face else scale,sv[f] if per_face else scale)
  for j,values in enumerate(expected):
   actual=dict(m['terms'][4*f+j]);want={int(i*2+(j>=2)):float(c) for i,c in zip(vertex_ids,values) if c!=0};keys=actual.keys()|want.keys();error=max([abs(actual.get(i,0)-want.get(i,0)) for i in keys],default=0);errors.append(error)
   if error>1e-8 and len(bad)<8:bad.append(dict(face=f,row=j,error=error,actual=actual,expected=want))
 result=dict(experimentId='EXP-0014',capture=str(root.relative_to(ROOT)),operation='Four residual rows per triangle at engine0x2992d0, before substitution/normal equations',rowsCompared=len(errors),faces=len(tri),maxAbsoluteCoefficientError=max(errors),tolerance=1e-8,passed=max(errors)<=1e-8,firstMismatches=bad,perFaceScale=per_face,scalarScale=scale)
 (root/'row-equation-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
