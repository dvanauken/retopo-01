"""EXP-0049: replay the captured unpreconditioned local sparse CG correction."""
import argparse,json,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]

def squared(values,ids):
 lanes=[0.,0.,0.,0.];end=len(ids)//4*4
 for k in range(end):v=float(values[ids[k]]);lanes[k%4]+=v*v
 total=((lanes[0]+lanes[2])+lanes[1])+lanes[3]
 for i in ids[end:]:total+=float(values[i])*float(values[i])
 return total

def main():
 ap=argparse.ArgumentParser();ap.add_argument('capture');a=ap.parse_args();root=Path(a.capture).resolve();pre=next(root.glob('*-entry-0xdec90'));post=next(root.glob('*-return-0xdec90'));header=(pre/'pcg-settings.bin').read_bytes();returned=(post/'pcg-settings.bin').read_bytes();tol=struct.unpack_from('<d',header)[0];limit=struct.unpack_from('<i',header,8)[0];preconditioner=struct.unpack_from('<i',header,16)[0];assert preconditioner==0,'Only actual captured unpreconditioned branch qualified here';limit=1000 if limit==-1 else limit
 m=json.loads((next(root.glob('*-entry-0xdec90-matrix'))/'matrix-rows.json').read_text());H=[[(int(i),float(v)) for i,v in row] for row in m['terms']];x=np.fromfile(pre/'solution.f64','<f8').copy();rhs=np.fromfile(pre/'rhs.f64','<f8');active=np.fromfile(pre/'seeds.i32','<i4').tolist();seedCount=len(active);r=np.zeros(len(x));p=np.zeros(len(x))
 for i in active:
  product=0.
  for j,v in H[i]:product+=v*float(x[j])
  r[i]=float(rhs[i])-product;p[i]=r[i]
 rho=squared(r,active);initial=rho;target=(tol*tol)*rho;iterations=0;trace=[];success=initial<1e-5
 for step in range(0 if success else limit):
  if rho<target:success=True;break
  q=np.zeros(len(x));discovered=[];seen=set()
  for i in active:
   for j,v in H[i]:
    term=float(p[i])*v
    if j in seen:q[j]=term+float(q[j])
    else:q[j]=term;seen.add(j);discovered.append(j)
  for i in active:
   if i not in seen:q[i]=0;seen.add(i);discovered.append(i)
  denom=0.
  for i in active:denom+=float(p[i])*float(q[i])
  if denom==0:break
  alpha=rho/denom
  for i in active:x[i]=float(x[i])+alpha*float(p[i])
  for i in discovered:r[i]=float(r[i])-alpha*float(q[i])
  previous=rho;rho=squared(r,discovered);beta=rho/previous
  for i in discovered:p[i]=beta*float(p[i])+float(r[i])
  active=discovered;iterations=step+1;trace.append(dict(iteration=iterations,support=len(active),squaredLocalResidual=rho,alpha=alpha,beta=beta))
 if iterations<limit and rho<target:success=True
 actual=np.fromfile(post/'solution.f64','<f8');err=abs(actual-x);nativeInitial=struct.unpack_from('<d',returned,24)[0];nativeFinal=struct.unpack_from('<d',returned,32)[0];nativeIterations=struct.unpack_from('<i',returned,20)[0];nativeFinalSupport=struct.unpack_from('<i',returned,44)[0];checks=[dict(name='correction-vector',passed=bool((err<=1e-10).all()),values=len(x),maxAbsoluteError=float(err.max(initial=0)),tolerance=1e-10),dict(name='iteration-count',passed=iterations==nativeIterations,replay=iterations,native=nativeIterations),dict(name='initial-local-residual',passed=abs(initial-nativeInitial)<=1e-10,replay=initial,native=nativeInitial),dict(name='final-local-residual',passed=abs(rho-nativeFinal)<=1e-10,replay=rho,native=nativeFinal),dict(name='final-support-size',passed=len(active)==nativeFinalSupport,replay=len(active),native=nativeFinalSupport),dict(name='native-local-stopping-condition',passed=success and rho<target,threshold=target,finalSquaredResidual=rho)]
 result=dict(experimentId='EXP-0049',capture=root.relative_to(ROOT).as_posix(),cases=checks,passed=all(c['passed'] for c in checks),settings=dict(tolerance=tol,maxIterations=limit,preconditioning=preconditioner),seedCount=seedCount,iterationTrace=trace,scope='Captured local unpreconditioned CG correction with exact native seed order and sparse structural support expansion; not the optional preconditioned branch or generic fallback schedule.')
 dest=root/'local-cg-check.json'
 if dest.exists():raise RuntimeError('Preserve previous result')
 dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
