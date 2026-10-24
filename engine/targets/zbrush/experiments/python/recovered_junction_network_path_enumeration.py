"""1651f0 option8/9=0 graph paths, empty forced/boundary arrays.

Static branch refill selects the front once, then resumes LIFO consumption.
Native1020 qualifies degree-three cuboid paths and that refill; earlier869
qualifies the degree-four connected branch without refill. Disconnected/fallback
and higher-degree generalizations remain separately unqualified native branches.
"""
from collections import Counter

def enumerate_stack(selected,edges,vo,ve):
    selected=sorted(set(map(int,selected)))
    if not selected:return [],[]
    if min(selected)<0 or max(selected)>=len(edges):raise ValueError('Guide edge index out of range')
    remaining=set(selected);encounter=[];degree=Counter()
    for edge in selected:
        for vertex in edges[edge]:
            vertex=int(vertex)
            if not degree[vertex]:encounter.append(vertex)
            degree[vertex]+=1
    if any(n not in (2,3,4) for n in degree.values()):
        raise NotImplementedError('Qualified nonleaf degree2/3/4 network only')
    reached=set();pending=[encounter[0]]
    while pending:
        vertex=pending.pop()
        if vertex in reached:continue
        reached.add(vertex)
        for edge in ve[vo[vertex]:vo[vertex+1]]:
            if int(edge) in remaining:
                a,b=map(int,edges[edge]);pending.append(b if a==vertex else a)
    if len(reached)!=len(encounter):
        raise NotImplementedError('Disconnected cycle fallback requires separate native qualification')
    branches=[v for v in encounter if degree[v]>=3]
    if not branches:branches=[encounter[0]]
    stack=[v for v in branches for _ in range(max(1,degree[v]-1))]
    paths=[];refilled=False
    while remaining:
        first=None
        if not stack:
            if refilled:raise NotImplementedError('Residual after one reviewed branch refill')
            stack=[v for v in branches for _ in range(max(1,degree[v]-1))]
            refilled=True
            first=stack.pop(0)
        vertex=stack.pop() if first is None else first
        es=[];vs=[]
        for _ in range(len(selected)+1):
            edge=next((int(e) for e in ve[vo[vertex]:vo[vertex+1]] if int(e) in remaining),None)
            if edge is None:
                if es:vs.append(vertex)
                break
            remaining.remove(edge);es.append(edge);vs.append(vertex)
            a,b=map(int,edges[edge]);vertex=b if a==vertex else a
            if degree[vertex]!=2:vs.append(vertex);break
        else:raise ValueError('Guide network traversal bound')
        if es:paths.append((es,vs))
    return paths,branches
