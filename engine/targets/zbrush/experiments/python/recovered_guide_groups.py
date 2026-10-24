"""Bounded untrimmed ordinary guide parameter-edge grouping from source constraints."""
from collections import Counter,defaultdict
import numpy as np

def construct_groups(positions,sourceTriangles,parameterTriangles,sourceFaceEdges,constrained,sourceModes,basisA,basisB,directionA,directionB,parameterEdges,skip):
 if np.any(skip):raise ValueError('Positive source-edge compatibility/trim mask not qualified')
 constrained=list(map(int,constrained));sourceCorners=defaultdict(list)
 for corner,edge in enumerate(sourceFaceEdges.ravel()):sourceCorners[int(edge)].append(corner)
 axis=np.zeros(sourceTriangles.size,bool)
 def dot(a,b):return np.float32(np.float32(a[1]*b[1]+a[0]*b[0])+a[2]*b[2])
 for edge in constrained:
  for corner in sourceCorners[edge]:
   face,c=divmod(corner,3);delta=np.float32(positions[sourceTriangles[face,(c+1)%3]]-positions[sourceTriangles[face,c]]);a=np.float32(directionA[face,0]*basisA[face]+directionA[face,1]*basisB[face]);b=np.float32(directionB[face,0]*basisA[face]+directionB[face,1]*basisB[face]);axis[corner]=abs(dot(b,delta))<abs(dot(a,delta))
 pairToEdge={tuple(sorted(map(int,e))):i for i,e in enumerate(parameterEdges)};uvCorners=defaultdict(list);cornerEdges=[]
 for corner in range(parameterTriangles.size):
  face,c=divmod(corner,3);edge=pairToEdge[tuple(sorted([int(parameterTriangles[face,c]),int(parameterTriangles[face,(c+1)%3])]))];cornerEdges.append(edge);uvCorners[edge].append(corner)
 selected=[];modes={}
 for edge in constrained:
  mapped=list(dict.fromkeys(cornerEdges[c] for c in sourceCorners[edge]));selected.extend(mapped)
  for parameterEdge in mapped:modes[parameterEdge]=int(sourceModes[edge])
 groups=[];axes=[]
 for selectedAxis in [0,1]:
  items=list(dict.fromkeys(e for e in selected if int(axis[uvCorners[e][0]])==selectedAxis));degree=Counter();encounter=[];adj=defaultdict(list)
  for edge in items:
   for v in parameterEdges[edge]:
    v=int(v)
    if degree[v]==0:encounter.append(v)
    degree[v]+=1;adj[v].append(edge)
  if any(v>2 for v in degree.values()):raise ValueError('Branched same-axis guide grouping not qualified')
  remaining=set(items);leaves=[v for v in encounter if degree[v]==1]
  while leaves:
   vertex=leaves.pop();path=[]
   while True:
    edge=next((e for e in adj[vertex] if e in remaining),None)
    if edge is None:break
    remaining.remove(edge);path.append(edge);a,b=map(int,parameterEdges[edge]);vertex=b if a==vertex else a
    if degree[vertex]!=2:break
   if path:groups.append(path);axes.append(selectedAxis)
  if remaining:raise ValueError('Closed same-axis guide cycles not qualified')
 return dict(groups=groups,axes=axes,cornerAxes=axis,edgeModes=modes,selectedParameterEdges=list(dict.fromkeys(selected)))
