"""Ordered ordinary weighted normal assembly at a9f00/a99f0/aab00.

Compute each upper pair once, then mirror, rather than independent rounded
upper/lower products. Actual a9f00 instructions precompute coefficient*weight. Finite ordinary
double systems only; no exceptional matrix mode or NaN behavior inferred.
"""
import numpy as np
from scipy import sparse

def assemble(A,weights,targets,threshold=1e-16):
 A=A.tocsr(copy=True);A.sort_indices();weights=np.asarray(weights,dtype='<f8');targets=np.asarray(targets,dtype='<f8');m,n=A.shape
 if weights.shape!=(m,) or targets.shape!=(m,) or not np.isfinite(A.data).all() or not np.isfinite(weights).all() or not np.isfinite(targets).all() or np.any(weights<0):raise ValueError('Finite ordinary nonnegative-weight system required')
 if threshold!=1e-16:raise NotImplementedError('Only reviewed normal pruning threshold')
 lower=[{} for _ in range(n)];rhs=np.zeros(n,dtype='<f8')
 for row in range(m):
  begin,end=A.indptr[row:row+2];columns=A.indices[begin:end];values=A.data[begin:end];w=float(weights[row]);t=float(targets[row])
  for at,(i,a) in enumerate(zip(columns,values)):
   i=int(i);a=float(a);rhs[i]=((t*w)*a)+float(rhs[i]);terms=lower[i]
   for j,b in zip(columns[at:],values[at:]):
    j=int(j);value=(a*w)*float(b);terms[j]=value+terms.get(j,0.)
 full=[{} for _ in range(n)]
 for i,row in enumerate(lower):
  for j,value in row.items():
   if abs(value)>threshold:full[i][j]=value;full[j][i]=value
 columns=[];values=[];offset=[0]
 for row in full:
  for j,value in sorted(row.items()):columns.append(j);values.append(value)
  offset.append(len(columns))
 return sparse.csr_matrix((np.asarray(values,dtype='<f8'),np.asarray(columns,dtype='<i4'),np.asarray(offset,dtype='<i4')),shape=(n,n)),rhs
