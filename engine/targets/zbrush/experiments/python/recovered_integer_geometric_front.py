"""0x28fe70 ordinary FIFO distance/owner/root/parent propagation in UV space.

Seed arrays and queue order are inputs; seed selection is a separate producer.
Strict improvements, float32 rounding, first-in adjacency and enqueue-once
membership reproduce the reviewed 0x290d2a..0x290e70 instruction interval.
"""
from collections import deque
import numpy as np

def initialize(triangles, parameter_triangles, parameter_edges, groups, axes, source_seeds, axis):
    """Ordinary empty excluded-face mask branch; source fan encounter order."""
    count=int(np.max(parameter_triangles))+1
    distance=np.full(count,np.finfo(np.float32).max,dtype=np.float32)
    owner=np.full(count,-1,dtype=np.int32);root=owner.copy();parent=owner.copy()
    queue=[];queued=set();marked=set()
    def seed(v,region):
        distance[v]=0;owner[v]=region;root[v]=v;parent[v]=-1
        if v not in queued:queue.append(v);queued.add(v)
    for group_id,(path,group_axis) in enumerate(zip(groups,axes)):
        if group_axis!=axis:continue
        for edge in path:
            marked.add(int(edge))
            for v in parameter_edges[edge]:seed(int(v),group_id)
    fans={}
    for source,parameter in zip(triangles.ravel(),parameter_triangles.ravel()):
        row=fans.setdefault(int(source),[]);parameter=int(parameter)
        if parameter not in row:row.append(parameter)
    for index,source in enumerate(source_seeds):
        for v in fans.get(int(source),[]):
            if owner[v]<0:seed(v,len(groups)+2*index+axis)
    return dict(distance=distance,owner=owner,root=root,parent=parent,queue=queue,marked=marked)

def propagate(uv, edges, offsets, incident, distance, owner, root, parent, queue):
    F=np.float32
    distance=np.asarray(distance,dtype=np.float32).copy()
    owner=np.asarray(owner,dtype=np.int32).copy()
    root=np.asarray(root,dtype=np.int32).copy()
    parent=np.asarray(parent,dtype=np.int32).copy()
    pending=deque(map(int,queue));enqueued=set(pending)
    if len(enqueued)!=len(pending):raise ValueError('Duplicate FIFO seed')
    pops=updates=0
    while pending:
        v=pending.popleft();enqueued.remove(v);pops+=1
        for e in incident[offsets[v]:offsets[v+1]]:
            e=int(e);a,b=map(int,edges[e]);w=b if a==v else a
            if v!=a and v!=b:raise ValueError('Inconsistent incidence')
            dx=F(uv[v,0]-uv[w,0]);dy=F(uv[v,1]-uv[w,1])
            cost=F(F(np.sqrt(F(F(dx*dx)+F(dy*dy))))+distance[v])
            if cost<distance[w]:
                distance[w]=cost;owner[w]=owner[v];root[w]=root[v];parent[w]=e;updates+=1
                if w not in enqueued:pending.append(w);enqueued.add(w)
    return dict(distance=distance,owner=owner,root=root,parent=parent,pops=pops,updates=updates)

def candidates(uv, edges, distance, owner, marked):
    """Static translation of ordered cross-owner candidate scan; unqualified."""
    F=np.float32;result=[];index={}
    for edge,(a,b) in enumerate(edges):
        a,b=int(a),int(b);oa,ob=int(owner[a]),int(owner[b])
        if oa<0 or ob<0 or oa==ob:continue
        dx=F(uv[a,0]-uv[b,0]);dy=F(uv[a,1]-uv[b,1])
        cost=F(F(distance[a]+distance[b])+F(np.sqrt(F(F(dx*dx)+F(dy*dy)))))
        candidate=edge
        if edge in marked and distance[a]==0 and distance[b]==0:
            cost=F(-1e-7);candidate=-1
        key=tuple(sorted((oa,ob)))
        if key not in index:
            index[key]=len(result);result.append(dict(regions=list(key),edge=candidate,cost=float(cost)))
        elif cost<result[index[key]]['cost']:
            result[index[key]]=dict(regions=list(key),edge=candidate,cost=float(cost))
    return result
