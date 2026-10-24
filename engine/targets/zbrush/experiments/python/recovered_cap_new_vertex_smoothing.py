"""311330 Jacobi neighbor smoothing of only vertices >= initial count.

Caller controls iterations+A4, gain+A8 and fixed prefix+308. Finite tested
profiles do not establish UI names, bounds or arbitrary host acceptance.
"""
import numpy as np
from recovered_mesh_topology import build
F=np.float32

def smooth(points,faces,start,iterations,gain):
 points=F(points).copy();start=int(start);iterations=int(iterations);gain=F(gain)
 if not 0<=start<=len(points):raise ValueError('Fixed-prefix count outside allocated points')
 if start==len(points):return points,[],None
 cache=build(len(points),faces);edges=cache['edges'];offsets=cache['vertexEdgeOffsets'];indices=cache['vertexEdges'];scratch=np.zeros((len(points)-start,3),dtype='<f4');history=[]
 for _ in range(max(0,iterations)):
  for vertex in range(start,len(points)):
   begin,end=map(int,offsets[vertex:vertex+2]);degree=end-begin
   if not degree:continue
   total=np.zeros(3,dtype='<f4')
   for edge in indices[begin:end]:
    a,b=map(int,edges[edge]);other=b if a==vertex else a;total=F(total+points[other])
   weight=F(gain/F(degree));scaled=F(total*weight);scratch[vertex-start]=F(F(points[vertex]*F(F(1)-gain))+scaled)
  points[start:]=scratch;history.append(points.copy())
 return points,history,cache
