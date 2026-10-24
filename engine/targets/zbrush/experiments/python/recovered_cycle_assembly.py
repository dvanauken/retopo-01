"""Ordinary cycle reduction/ID assignment/slice emission, engine 0x2a9ac0.

Optional source-class preferences and general oversize partitioning reject
explicitly; the captured closed smooth fixture has neither branch.
"""
import struct
from recovered_work_node_frame import transport


def integer(node,offset):return struct.unpack_from('<i',node,offset)[0]
def put(node,offset,value):struct.pack_into('<i',node,offset,int(value))


def assemble(pointers,nodes,directions,faces,links,counter,geometry,guide_edges,edge_path):
    pointers=list(pointers);faces=list(faces);links=list(links);polygons=[];decisions=[]
    for p,d,f in zip(pointers,directions,faces):
        node=nodes[p]
        if integer(node,0x28)==-1:put(node,0x28,counter);counter+=1
        if not node[0x30]&16:
            ok,d,_=transport(integer(node,0x14),[integer(node,0x18),integer(node,0x1c)],int(d),int(f),*geometry)
            if ok:node[0x30]|=1<<d
    i=0
    def constrained(node):return integer(node,0x18)==2 and integer(node,0x1c) in guide_edges
    while i<len(pointers):
        if not links[i]:i+=1;continue
        j=(i+1)%len(pointers);a=nodes[pointers[i]];b=nodes[pointers[j]];ag=constrained(a);bg=constrained(b)
        if ag and bg and edge_path[integer(a,0x1c)]!=edge_path[integer(b,0x1c)]:i+=1;continue
        keep=integer(a,0x28)<integer(b,0x28)
        if a[0x30]&16:
            if i==0 and len(pointers)>2 and pointers[1]==pointers[-1]:keep=False
            if bg:keep=False
        if not keep:
            if ag:keep=True
        elif bg:keep=False
        if keep:
            put(b,0x2c,integer(a,0x2c) if integer(a,0x2c)>=0 else integer(a,0x28));remove=j
        else:
            put(a,0x2c,integer(b,0x2c) if integer(b,0x2c)>=0 else integer(b,0x28));remove=i
        decisions.append(dict(index=i,keptCurrent=keep,removedPointer=pointers[remove]));pointers.pop(remove);faces.pop(remove);links.pop(i)
    if len(pointers)==3 and not any(integer(nodes[p],0x18)==1 for p in pointers) and any(links):return counter,polygons,decisions
    virtual=sum(bool(nodes[p][0x30]&64) for p in pointers)
    def ids(ps):return [integer(nodes[p],0x2c) if integer(nodes[p],0x2c)>=0 else integer(nodes[p],0x28) for p in ps]
    def emit(ps):
        row=ids(ps)
        if row and not any(row[i]==row[(i+2)%len(row)] for i in range(len(row))):polygons.append(row)
    while len(pointers)>2 and len(pointers)-virtual>4:
        n=len(pointers)
        if n<6:raise ValueError('General oversize partitioning remains unqualified')
        first=next((i for i in range(n) if pointers[i]==pointers[(i+2)%n]),None)
        if first is None:raise ValueError('General oversize partitioning remains unqualified')
        middle=first+1
        if n<7:
            removed={middle%n,(middle+1)%n};pointers=[p for i,p in enumerate(pointers) if i not in removed];polygons.append(ids(pointers));return counter,polygons,decisions
        removed=set()
        for start,stop in [(middle,middle+3),(middle-3,middle)]:
            indices=[k%n for k in range(start,stop+1)];polygons.append(ids([pointers[k] for k in indices]));removed.update(indices[1:-1])
        pointers=[p for i,p in enumerate(pointers) if i not in removed]
    if len(pointers)>2:emit(pointers)
    return counter,polygons,decisions
