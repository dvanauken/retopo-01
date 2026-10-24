"""1651f0 connected closed cut graphs, including cycles with branch nodes.

Retains the reviewed leaf/FIFO branch ordering. Boundaries and disconnected
components remain guarded; no native path schedule is an input.
"""
from collections import Counter,deque

def enumerate_paths(selected,edges,vertexOffsets,vertexEdges,forced,boundary):
    if len(boundary):raise ValueError('Boundary-node policy not qualified')
    selected=list(dict.fromkeys(map(int,selected)));remaining=set(selected);encounter=[];degree=Counter();parent={}
    def find(v):
        parent.setdefault(v,v)
        while parent[v]!=v:parent[v]=parent[parent[v]];v=parent[v]
        return v
    for edge in selected:
        a,b=map(int,edges[edge]);a=find(a);b=find(b)
        if a!=b:parent[a]=b
    if parent and len({find(v) for v in parent})!=1:raise ValueError('Disconnected cut graph not qualified')
    for edge in selected:
        for vertex in edges[edge]:
            vertex=int(vertex)
            if degree[vertex]==0:encounter.append(vertex)
            degree[vertex]+=1
    leaves=[v for v in encounter if degree[v]==1];branches=[v for v in encounter if degree[v]>=3]
    if encounter and not leaves and not branches:branches.append(encounter[0])
    for vertices in [forced,boundary]:
        for vertex in vertices:
            vertex=int(vertex)
            if degree[vertex]==2:branches.append(vertex);degree[vertex]=3
    nodes=leaves+branches;queue=deque();filled=False;paths=[];maximum=len(selected)+1
    while remaining:
        if leaves:start=leaves.pop()
        elif queue:start=queue.popleft()
        elif not filled and branches:
            queue.extend(v for v in branches for _ in range(max(1,degree[v]-1)));filled=True;continue
        else:start=int(edges[min(remaining)][0])
        vertex=start;path=[];vertices=[]
        for _ in range(maximum):
            edge=next((int(e) for e in vertexEdges[vertexOffsets[vertex]:vertexOffsets[vertex+1]] if int(e) in remaining),None)
            if edge is None:break
            remaining.remove(edge);path.append(edge);vertices.append(vertex);a,b=map(int,edges[edge]);vertex=b if a==vertex else a
            if degree[vertex]!=2:vertices.append(vertex);break
        else:raise ValueError('Path loop bound')
        if path:
            if len(vertices)==len(path):vertices.append(vertex)
            paths.append((path,vertices))
            if degree[vertex]>2:queue.extend([vertex]*(degree[vertex]-1))
        if len(paths)>len(selected):raise ValueError('Path count bound')
    return paths,nodes
