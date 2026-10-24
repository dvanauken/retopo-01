"""EXP-0062: owned-array native double guide-walk leaves, including float determinants."""
import ctypes as C
import hashlib,json,math,os,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
SHA='0d45ea6f9331cecb55c12a10dcdb6d4bedb86cf302cd873748704dbaa82b00bc'
F=np.float32

def dot(a,b):return (b[1]*a[1]+b[0]*a[0])+b[2]*a[2]
def norm(a):return math.sqrt((a[0]*a[0]+a[1]*a[1])+a[2]*a[2])
def cross(a,b):return np.array([a[1]*b[2]-a[2]*b[1],b[0]*a[2]-a[0]*b[2],a[0]*b[1]-b[0]*a[1]])
def determinant(a,b,c,d):return F(F(F(a)*F(d))-F(F(b)*F(c)))
def reference(line,segment,tol):
 o,d=line[:3],line[3:];a,b=segment[:3],segment[3:];delta=b-a;length=norm(delta);u=delta*(1/length);v=a-o
 parallel=-tol<norm(cross(d,u))<tol
 c=dot(d,u);den=float(determinant(1,c,-c,-1)) if not parallel else 0.
 if parallel or den==0:return norm(cross(d,v)),dot(v,d),0.,True
 vd=dot(v,d);vu=dot(v,u)
 return 0.,float(determinant(vd,vu,-c,-1))/den,(float(determinant(1,c,vd,vu))/den)/length,False

def main():
 out=ROOT/'work/zbrush/runtime/algorithm-recovery/guide-walk-math';dest=out/'result.json'
 if dest.exists():raise RuntimeError('Preserve previous native result')
 engine=Path(json.loads((ROOT/'targets/zbrush/target.local.json').read_text())['inputs']['engine']);assert hashlib.sha256(engine.read_bytes()).hexdigest()==SHA
 with os.add_dll_directory(str(engine.parent)):dll=C.CDLL(str(engine))
 D=C.c_double;P=C.POINTER(D);B=C.c_bool
 fn=C.CFUNCTYPE(D,P,P,P,P,C.POINTER(B))(dll._handle+0x2e8e80)
 project=C.CFUNCTYPE(B,P,P)(dll._handle+0x2d14b0);normalize=C.CFUNCTYPE(D,P)(dll._handle+0x2d1600);pointline=C.CFUNCTYPE(D,P,P,P)(dll._handle+0x2b4240)
 array=lambda a:(D*len(a))(*a)
 tol=struct.unpack('<d',bytes.fromhex('f168e388b5f8e43e'))[0];low=struct.unpack('<d',bytes.fromhex('30058ee42eff2bab'))[0];high=struct.unpack('<d',bytes.fromhex('30058ee42eff2b2b'))[0]
 rng=np.random.default_rng(1062);rows=[]
 for k in range(1200):
  origin=rng.normal(size=3);direction=rng.normal(size=3);direction/=norm(direction);a=rng.normal(size=3);edge=rng.normal(size=3)
  if k<200:
   perpendicular=cross(direction,[1.,0.,0.]);perpendicular/=norm(perpendicular)
   edge=direction+perpendicular*(10.**rng.uniform(-10,-2))
  if k%17==0:edge=direction.copy()
  line=np.r_[origin,direction];segment=np.r_[a,a+edge];s=D();t=D();p=B();distance=fn(array(line),array(segment),C.byref(s),C.byref(t),C.byref(p));expected=reference(line,segment,tol);got=(distance,s.value,t.value,bool(p.value));err=max(abs(x-y) for x,y in zip(got[:3],expected[:3]));rows.append(dict(kind='line-edge',index=k,native=got,expected=expected,maxError=err,passed=got==expected))
 for k in range(160):
  v=rng.normal(size=3);n=rng.normal(size=3);n/=norm(n);native=array(v);project(native,array(n));wanted=v-n*dot(v,n);error=float(np.max(abs(np.array(native)-wanted)));rows.append(dict(kind='tangent-projection',index=k,maxError=error,passed=error==0))
  w=rng.normal(size=3)*(10.**rng.uniform(-20,20));native=array(w);length=normalize(native);wantedLength=norm(w);wanted=w*(1/wantedLength) if wantedLength<=low or high<=wantedLength else w;error=float(np.max(abs(np.array(native)-wanted)));rows.append(dict(kind='normalization',index=k,lengthError=abs(length-wantedLength),maxError=error,passed=error==0 and length==wantedLength))
  point=rng.normal(size=3);line=np.r_[rng.normal(size=3),n];parameter=D();distance=pointline(array(point),array(line),C.byref(parameter));delta=point-line[:3];wantParameter=dot(delta,n);residual=delta-wantParameter*n;wantDistance=math.sqrt((residual[1]*residual[1]+residual[0]*residual[0])+residual[2]*residual[2]);rows.append(dict(kind='point-line',index=k,maxError=max(abs(parameter.value-wantParameter),abs(distance-wantDistance)),passed=parameter.value==wantParameter and distance==wantDistance))
 result=dict(experimentId='EXP-0062',engineSha256=SHA,passed=all(r['passed'] for r in rows),cases=rows,constants=dict(parallelCrossLengthTolerance=tol,normalizationLower=low,normalizationUpper=high),scope='Owned finite nondegenerate double arrays. Line direction unit, segment endpoints distinct. Exact scalar replay including float32 determinants; no full surface-walk or cut-connectivity claim.')
 out.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(cases=len(rows),failed=sum(not r['passed'] for r in rows),passed=result['passed'],maxError=max(r['maxError'] for r in rows))))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
