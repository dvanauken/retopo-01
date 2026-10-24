"""Restricted2a3e60 boundary cap, including balanced four-vertex holes.

Length-five-and-larger behavior follows the earlier regular transcription. A
four-loop is accepted only when both ordered float32 diagonal squared lengths
are within the native ratio9. Then both native ratio predicates are true and
the independent absolute-size threshold cannot select collapse. Thin-diagonal,
triangle, protected/splitting and nonmanifold policies are not invented here.
"""
import numpy as np
from recovered_mesh_topology import build as topology
F=np.float32
def cap(vertices,faces,protected,enabled=True):
    points=np.asarray(vertices,dtype='<f4')
    if points.ndim!=2 or points.shape[1]!=3 or not np.isfinite(points).all():raise ValueError('Finite XYZ required')
    if len(protected)!=len(points):raise ValueError('One protected flag per point required')
    edges={}
    for face,row in enumerate(faces):
        if len(row)<3 or any(not 0<=v<len(points) for v in row):raise ValueError('Valid polygon corners required')
        for k,a in enumerate(row):
            b=row[(k+1)%len(row)];edges.setdefault(tuple(sorted([a,b])),[]).append((face,k,a,b))
    if any(len(c)>2 for c in edges.values()):raise NotImplementedError('Nonmanifold boundary preparation')
    boundary=[c[0] for c in edges.values() if len(c)==1]
    #07d1a0 visits marked boundary edges by independently generated cache ID,
    #then uses that edge's first incident source corner as the directed start.
    cache=topology(len(points),faces);order={tuple(map(int,row)):i for i,row in enumerate(cache['edges'])}
    boundary.sort(key=lambda c:order[tuple(sorted((c[2],c[3])))])
    outgoing={};incoming={}
    for _,_,a,b in boundary:
        if a in outgoing or b in incoming:raise NotImplementedError('Shared/branch boundary splitting')
        outgoing[a]=b;incoming[b]=a
    visited=set();loops=[];result=[list(row) for row in faces];events=[]
    for _,_,start,_ in boundary:
        if start in visited:continue
        loop=[];vertex=start
        while vertex not in visited:
            loop.append(vertex);visited.add(vertex)
            if vertex not in outgoing:raise NotImplementedError('Open boundary chain')
            vertex=outgoing[vertex]
        if vertex!=start:raise NotImplementedError('Boundary chain joins another loop')
        loops.append(loop)
        if not enabled or any(protected[v] for v in loop) or len(loop)>=1000:continue
        row=list(reversed(loop));event=dict(loop=loop.copy(),appended=row.copy(),branch='large-simple-loop')
        if len(loop)<=4:
            if len(loop)!=4:raise NotImplementedError('Three-corner and shorter boundary policies')
            diagonal=[]
            for a,b in [(0,2),(1,3)]:
                d=F(points[row[a]]-points[row[b]]);diagonal.append(F(F(d[0]*d[0]+d[1]*d[1])+d[2]*d[2]))
            x,y=diagonal
            if not (x>0 and y>0 and F(y/F(9))<=x and F(x/F(9))<=y):raise NotImplementedError('Short-diagonal absolute threshold/collapse policy')
            event.update(branch='balanced-four-loop',diagonalSquared=[float(x),float(y)],ratio=9,absoluteThresholdNotNeeded=True)
        result.append(row);events.append(event)
    return result,loops,events
