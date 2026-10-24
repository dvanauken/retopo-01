"""1651f0 option byte9=0 connected closed degree2/4 branch LIFO subset."""
from collections import Counter

def enumerate_stack(selected,edges,vo,ve):
    selected=sorted(set(map(int,selected)));remaining=set(selected);encounter=[];degree=Counter()
    for edge in selected:
        for vertex in edges[edge]:
            vertex=int(vertex)
            if not degree[vertex]:encounter.append(vertex)
            degree[vertex]+=1
    if any(n not in [2,4] for n in degree.values()):raise NotImplementedError('Connected closed degree2/4 empty-forced/boundary network only')
    reached=set();pending=[encounter[0]] if encounter else []
    while pending:
        vertex=pending.pop()
        if vertex in reached:continue
        reached.add(vertex)
        for edge in ve[vo[vertex]:vo[vertex+1]]:
            if int(edge) in remaining:
                a,b=map(int,edges[edge]);pending.append(b if a==vertex else a)
    if len(reached)!=len(encounter):raise NotImplementedError('Disconnected closed networks remain unqualified')
    branches=[v for v in encounter if degree[v]>=3]
    if not branches:branches=[encounter[0]]
    stack=[v for v in branches for _ in range(max(1,degree[v]-1))];paths=[];maximum=len(selected)+1
    while remaining:
        if not stack:raise NotImplementedError('Disconnected residual or extra branch refill policy')
        vertex=stack.pop();es=[];vs=[]
        for _ in range(maximum):
            edge=next((int(e) for e in ve[vo[vertex]:vo[vertex+1]] if int(e) in remaining),None)
            if edge is None:
                if es:vs.append(vertex)
                break
            remaining.remove(edge);es.append(edge);vs.append(vertex);a,b=map(int,edges[edge]);vertex=b if a==vertex else a
            if degree[vertex]!=2:vs.append(vertex);break
        else:raise ValueError('Closed network walk bound')
        if es:paths.append((es,vs))
    return paths,branches
