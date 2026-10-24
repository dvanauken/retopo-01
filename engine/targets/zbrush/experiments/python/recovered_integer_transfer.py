"""Bounded integer column compression and outer fix back-transfer."""
from recovered_integer_batch import rounded

def compress(rows,dimension):
 forward=[-1]*dimension;inverse=[];out=[]
 for row in rows:
  result=[]
  for column,value in row:
   if not 0<=column<dimension:raise ValueError('Invalid original scalar index')
   if forward[column]<0:forward[column]=len(inverse);inverse.append(column)
   result.append([forward[column],value])
  out.append(result)
 return out,forward,inverse

def transfer(solution,outer_indices,outer_mapping,forward,dependencies,dependency_map,constant,steps):
 positions=[];values=[];dependent_positions=[-1]*len(dependencies)
 for i,variable in enumerate(outer_indices):
  original=outer_mapping[variable];reduced=forward[original]
  if reduced!=-1:positions.append(i);values.append(float(solution[reduced]))
  elif dependency_map[original]!=-1:dependent_positions[dependency_map[original]]=i
 for index in range(len(dependencies)-1,-1,-1):
  value=0.
  for original,coefficient in dependencies[index]['terms']:
   if original==constant:value-=coefficient
   elif forward[original]>=0:value+=float(solution[forward[original]])*coefficient
  position=dependent_positions[index]
  if position!=-1:
   step=float(steps[position]) if len(steps) else 1.
   positions.append(position);values.append(rounded(value/step)*step)
 return positions,values
