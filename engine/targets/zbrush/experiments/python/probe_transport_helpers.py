"""EXP-0050: native unsigned/oriented angles and double-half-angle 4x4 rotation."""
import ctypes as C,hashlib,json,math,os
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
SHA='0d45ea6f9331cecb55c12a10dcdb6d4bedb86cf302cd873748704dbaa82b00bc'
f32=np.float32

def dot(a,b):return f32(f32(a[0]*b[0]+a[1]*b[1])+a[2]*b[2])
def cross(a,b):return np.array([f32(a[1]*b[2]-a[2]*b[1]),f32(a[2]*b[0]-a[0]*b[2]),f32(a[0]*b[1]-a[1]*b[0])],dtype='f4')
def unsigned(a,b):
 den=math.sqrt(float(dot(a,a))*float(dot(b,b)))
 if den==0:return 0.
 value=float(dot(a,b))/den
 return math.pi if value<=-1 else math.acos(value) if value<1 else 0.
def oriented(a,b,n):
 value=unsigned(a,b)
 return 2*math.pi-value if dot(cross(a,b),n)<=0 and value!=0 else value

def rotation(axis,theta):
 norm=math.sqrt(float(dot(axis,axis)))
 if norm<1e-7:return np.eye(3,dtype='f4')
 x,y,z=axis.astype(float)*(math.sin(float(theta)*.5)/norm);w=math.cos(float(theta)*.5)
 return np.array([[2*x*x+2*w*w-1,2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),2*y*y+2*w*w-1,2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),2*z*z+2*w*w-1]],dtype='f4')

def main():
 dest=ROOT/'work/zbrush/runtime/algorithm-recovery/transport-helpers/result.json'
 if dest.exists():raise RuntimeError('Preserve previous result')
 engine=Path(json.loads((ROOT/'targets/zbrush/target.local.json').read_text())['inputs']['engine']);assert hashlib.sha256(engine.read_bytes()).hexdigest()==SHA
 with os.add_dll_directory(str(engine.parent)):dll=C.CDLL(str(engine))
 P=C.POINTER(C.c_float);u=C.CFUNCTYPE(C.c_double,P,P)(dll._handle+0x81e00);o=C.CFUNCTYPE(C.c_double,P,P,P)(dll._handle+0xca1b0);rot=C.CFUNCTYPE(None,P,P,C.c_float)(dll._handle+0x31a820);ptr=lambda a:(C.c_float*len(a))(*a);rng=np.random.default_rng(2750);rows=[]
 vectors=[([0,0,0],[1,0,0],[0,0,1]),([1,0,0],[1,0,0],[0,0,1]),([1,0,0],[-1,0,0],[0,0,1]),([1,0,0],[0,1,0],[0,0,1]),([1,0,0],[0,1,0],[0,0,-1])]+[(rng.normal(size=3),rng.normal(size=3),rng.normal(size=3)) for _ in range(64)]
 for a,b,n in vectors:
  a,b,n=[np.asarray(x,dtype='f4') for x in [a,b,n]]
  for name,got,want in [('unsigned',u(ptr(a),ptr(b)),unsigned(a,b)),('oriented',o(ptr(a),ptr(b),ptr(n)),oriented(a,b,n))]:rows.append(dict(kind=name,inputs=[a.tolist(),b.tolist(),n.tolist()],native=got,replay=want,maxError=abs(got-want),passed=abs(got-want)<=1e-12))
 for axis in [[0,0,0],[1e-8,0,0],[1e-7,0,0],[1,0,0],[0,1,0],[0,0,1],*[rng.normal(size=3) for _ in range(12)]]:
  a=np.asarray(axis,dtype='f4')
  for theta in [f32(0),f32(math.pi/2),f32(math.pi),f32(-.73)]:
   matrix=np.eye(4,dtype='f4').reshape(-1,order='F');out=ptr(matrix);rot(out,ptr(a),theta);got=np.array(out,dtype='f4').reshape(4,4,order='F');expected=np.eye(4,dtype='f4');expected[:3,:3]=rotation(a,theta);error=float(abs(got-expected).max());rows.append(dict(kind='rotation4x4',axis=a.tolist(),theta=float(theta),native=got.tolist(),maxError=error,passed=error<=2e-7))
 result=dict(experimentId='EXP-0050',engineSha256=SHA,cases=rows,passed=all(c['passed'] for c in rows),scope='Native081e00/0ca1b0 angular semantics and31a820 rotation4x4 numerical formula.32-bit trig helper3059d0 remains a separate qualified operation.')
 dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(cases=len(rows),passed=result['passed'],maxError=max(c['maxError'] for c in rows))))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
