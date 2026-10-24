"""Bounded generic direct-solve integer loop, including positive-multiple initialization.
Residual construction/elimination and transfer back to source UVs are inputs/consumers.
"""
import numpy as np
from recovered_integer_batch import select,rounded
def solve(A,weights,targets,integer_indices,steps,original_mapping,positive_start,budget):
 H=np.asarray((A.T@A.multiply(weights[:,None])).toarray());rhs=np.asarray(A.T@(weights*targets)).ravel();x=np.linalg.solve(H,rhs);initial=x.copy();mask=[False]*len(integer_indices);threshold=0.;forced=[];forcedValues=[]
 def fix(list_indices,values):
  nonlocal x,H,rhs
  for listed,value in zip(list_indices,values):
   variable=int(integer_indices[listed]);rhs-=H[:,variable]*value;H[:,variable]=0.;H[variable,:]=0.;H[variable,variable]=1.;rhs[variable]=value
  x=np.linalg.solve(H,rhs)
 for i,variable in enumerate(integer_indices):
  if original_mapping[variable]>=positive_start:
   step=float(steps[i]) if len(steps) else 1.;forced.append(i);forcedValues.append(max(1.,rounded(float(x[variable])/step))*step);mask[i]=True
 if forced:fix(forced,forcedValues)
 batches=[]
 while not all(mask):
  before=x.copy();selection=select(x,integer_indices,steps,mask,budget,threshold)
  if not selection['indices']:raise RuntimeError('Integer loop made no progress')
  mask=selection['fixed'];threshold=selection['threshold'];fix(selection['indices'],selection['values']);batches.append(dict(before=before,selection=selection,after=x.copy()))
  if len(batches)>len(integer_indices):raise RuntimeError('Bounded loop exceeded variable count')
 return dict(solution=x,initial=initial,forced=forced,forcedValues=forcedValues,batches=batches)
