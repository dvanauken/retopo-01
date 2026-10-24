"""255b10 ordinary closed fractional source-path preparation, no triple reduction.

Near-endpoint requests and original-position reset precede exact25a7e0 closure;
linear shared-edge collapse precedes at most five cyclic endpoint propagations.
"""
import numpy as np
F=np.float32

def prepare(vertices,edges,paths,fraction=F(.05),reset_positions=True):
    original=np.asarray(vertices,dtype='<f4');updated=original.copy();lookup={tuple(sorted(map(int,e))):i for i,e in enumerate(edges)};result=[];requests=[];details=[]
    for source in paths:
        p={k:v.copy() for k,v in source.items()};ids=p['edges'];t=p['parameters'];points=p['points'];count=len(ids)
        if count<4 or len(points)!=count or len(t)!=count or len(p['faces'])!=count-1:raise NotImplementedError('Ordinary nonempty closed record layout only')
        if len(p['attributes']) or np.any(ids<0) or np.any(ids>=len(edges)) or np.any(~np.isfinite(t)) or np.any(t<0) or np.any(t>1):raise NotImplementedError('Closed fractional attributes/free/range policy remains unqualified')
        begin=len(requests);upper=F(F(1)-fraction)
        for i,(edge,value) in enumerate(zip(ids,t)):
            if 0<value<fraction:t[i]=0;vertex=int(edges[edge,0])
            elif upper<value<1:t[i]=1;vertex=int(edges[edge,1])
            else:continue
            requests.append((vertex,points[i].copy()))
            if reset_positions:points[i]=original[vertex]
        def endpoint(i):return int(edges[int(ids[i]),int(t[i])]) if t[i] in (0,1) else -1
        closed=(endpoint(0)>=0 and endpoint(0)==endpoint(-1)) or (t[0] not in (0,1) and ids[0]==ids[-1] and t[0]==t[-1])
        if not closed:raise NotImplementedError('All paths must satisfy exact25a7e0 closed classifier after snapping')
        previous=-1;previous_index=-1;collapses=[]
        for i in range(count):
            vertex=endpoint(i)
            if vertex<0:continue
            edge=lookup.get(tuple(sorted((previous,vertex)))) if previous>=0 and previous!=vertex else None
            if edge is not None and i>previous_index+1 and bool((ids[previous_index+1:i]==edge).all()):t[previous_index+1:i]=0;collapses.append(dict(first=previous_index,last=i,edge=edge))
            previous,previous_index=vertex,i
        #Native closed triples use modulo n-1 (the repeated endpoint is omitted).
        for i in range(count-1):
            if ids[i]==ids[(i+1)%(count-1)]==ids[(i+2)%(count-1)]:raise NotImplementedError('Closed face-conditioned triple reduction remains unqualified')
        propagated=0;passes=0
        #Native endpoint propagation instead iterates all n stored entries and
        #uses modulo n, including both copies of the closing descriptor.
        for _ in range(5):
            changed=False;passes+=1
            for i in range(count):
                vertex=endpoint(i)
                if vertex<0:continue
                for j in ((i-1)%count,(i+1)%count):
                    if t[j] in (0,1):continue
                    if edges[ids[j],0]==vertex:t[j]=0;changed=True;propagated+=1
                    elif edges[ids[j],1]==vertex:t[j]=1;changed=True;propagated+=1
            if not changed:break
        result.append(p);details.append(dict(points=count,closed=True,requests=len(requests)-begin,sharedEdgeCollapses=collapses,propagationPasses=passes,propagatedParameters=propagated,scope='No free/attribute/triple cases; native closed cyclic propagation, ordinary pooled relocation requests.'))
    for vertex,point in requests:updated[vertex]=point
    return updated,result,requests,details
