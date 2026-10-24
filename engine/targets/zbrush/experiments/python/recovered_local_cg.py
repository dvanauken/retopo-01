"""Recovered selector0 sparse-support CG at engine0dec90.
Input row order and seed order are part of the operation. This module does not
choose generic full-solve fallbacks or replace the unqualified selector1 path.
"""
import numpy as np
from verify_local_cg import squared

def correct(H,x,rhs,seeds,tolerance=.10000000149011612,limit=50):
 x=np.asarray(x,dtype='f8').copy();active=list(seeds);r=np.zeros(len(x));p=np.zeros(len(x))
 for i in active:
  product=0.
  for j,v in H[i]:product+=v*float(x[j])
  r[i]=float(rhs[i])-product;p[i]=r[i]
 rho=squared(r,active);initial=rho;threshold=(tolerance*tolerance)*rho;iterations=0;success=rho<1e-5
 for step in range(0 if success else 1000 if limit==-1 else limit):
  if rho<threshold:success=True;break
  q=np.zeros(len(x));support=[];seen=set()
  for i in active:
   for j,v in H[i]:
    value=float(p[i])*v
    if j in seen:q[j]=value+float(q[j])
    else:q[j]=value;seen.add(j);support.append(j)
  for i in active:
   if i not in seen:q[i]=0;seen.add(i);support.append(i)
  denominator=0.
  for i in active:denominator+=float(p[i])*float(q[i])
  if denominator==0:break
  alpha=rho/denominator
  for i in active:x[i]=float(x[i])+alpha*float(p[i])
  for i in support:r[i]=float(r[i])-alpha*float(q[i])
  nextRho=squared(r,support);beta=nextRho/rho
  for i in support:p[i]=beta*float(p[i])+float(r[i])
  active=support;rho=nextRho;iterations=step+1
 if iterations<(1000 if limit==-1 else limit) and rho<threshold:success=True
 return dict(values=x,success=success,iterations=iterations,squaredInitialResidual=initial,squaredFinalResidual=rho,threshold=threshold,finalSupport=len(active))
