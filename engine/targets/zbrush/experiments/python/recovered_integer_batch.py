"""Finite bounded0dd470 integer batch selection; exact list order and error budget."""
import math
def rounded(v):return float(math.trunc(v+.5 if v>=0 else v-.5))
def select(solution,indices,steps,fixed,budget,threshold):
 fixed=list(fixed);selected=[];values=[];total=0.
 def item(i):
  step=float(steps[i]) if len(steps) else 1.;value=float(solution[indices[i]])/step;r=rounded(value);return abs(value-r),r*step
 if threshold==0:
  for factor in [1e-5,1e-4,.001,.01,.05]:
   limit=budget*factor
   for i in range(len(indices)):
    if fixed[i]:continue
    error,value=item(i)
    if error<limit:
     total+=error
     if total>budget:break
     selected.append(i);values.append(value);fixed[i]=True
   threshold=limit
   if not total<budget:break
 while len(selected)<len(indices):
  best=None;minimum=float('inf')
  for i in range(len(indices)):
   if fixed[i]:continue
   error,value=item(i)
   if error<minimum:best=i;minimum=error;roundedValue=value
  if best is None:break
  total+=minimum
  if total>budget:
   if not selected:selected.append(best);values.append(roundedValue);fixed[best]=True
   threshold=minimum;break
  selected.append(best);values.append(roundedValue);fixed[best]=True
 return dict(indices=selected,values=values,fixed=fixed,threshold=threshold)
