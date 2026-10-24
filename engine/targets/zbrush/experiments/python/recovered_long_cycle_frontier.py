"""Ordinary extraction with qualified long zero-step duplicate rejection.

No cancellation, optional source classes, virtual points, oversize repair or
fallback seed insertion is supplied. Those branches require qualification.
"""
import struct
import numpy as np
from recovered_work_node_frame import transport,folded
from recovered_seed_turn import turn


class Driver:
    def __init__(self,graph):self.g=graph;self.cycles=[];self.walks=[];self.assemblies=[];self.allocations=[];self.deferred=[];self.longCycleRejections=[]

    def allocate(self,face,point,uv):
        pointer=len(self.g.nodes)+1;self.g.allocate(pointer,face,point,uv);self.allocations.append(dict(pointer=pointer,face=int(face),position=np.asarray(point,dtype='<f4').tobytes().hex(),uv=np.asarray(uv,dtype='<f4').tobytes().hex()));return pointer

    def cycle(self,start,direction,face,uv,frontier):
        g=self.g;uv=np.asarray(uv,dtype='<f4').copy();initial=g.nodes[start];special=bool(initial[48]&16);startid=struct.unpack_from('<i',initial,40)[0];pointers=[start];directions=[direction];faces=[face];links=[];zero_steps=0;original_direction=direction;self.cycles.append(dict(pointer=start,direction=int(direction),face=int(face),uv=uv.tobytes().hex()));assembled=False
        for _ in range(201):
            current=pointers[-1];node=g.nodes[current]
            if not node[48]&16:
                ok,slot,_=transport(struct.unpack_from('<i',node,20)[0],struct.unpack_from('<2i',node,24),direction,face,*g.geometry)
                if ok and node[48]&(1<<slot):return 0
            olduv=uv.copy();oldface=face;oldd=direction
            self.walks.append(dict(pointer=current,direction=int(direction),face=int(face),uv=uv.tobytes().hex(),policy=int(special and len(pointers)==1),frontierMode=int(frontier)))
            ans=g.walk(current,direction,face,uv,frontier)
            if ans['status']==0 and ans['pointer'] is None:self.allocate(ans['face'],ans['position'],ans['uv'])
            ans=g.finish_walk(current,oldd,oldface,olduv);self.walks[-1].update(status=ans['status'],outputPointer=ans.get('pointer') or 0)
            if ans['status']!=0:
                if ans['status']==6:self.deferred.append((start,original_direction))
                return 0
            nxt=ans['pointer'];face=ans['face'];uv=ans['uv'].copy();d=ans['direction'];link=ans['link'];out=g.nodes[nxt]
            zero_steps+=bool(np.array_equal(olduv,uv))
            if nxt==current or (special and out[48]&16 and struct.unpack_from('<i',out,40)[0]<startid):return 0
            if nxt==start:
                if len(pointers)<=2:return 0
                if special and g.nodes[pointers[1]][48]&16:
                    ids=[struct.unpack_from('<i',g.nodes[p],40)[0] for p in pointers]
                    if all(g.nodes[p][48]&16 for p in pointers) and ids in g.polygons:return 0
                links.append(link);self.assemblies.append(dict(pointers=pointers.copy(),directions=list(map(int,directions)),faces=list(map(int,faces)),links=links.copy()));g.cycle(pointers,directions,faces,links);return 1
            if out[48]&16 and struct.unpack_from('<i',out,24)[0]==1:
                vertex=struct.unpack_from('<i',out,28)[0];ok,face,direction,uv=turn(vertex,face,d,uv,g.tri,g.pt,g.uv,g.fe,g.cs,g.vertex_corners)
                if not ok or face<0 or vertex not in g.tri[face]:return 0
            else:direction=(d+(3 if folded(face,g.uv,g.pt) else 1))%4
            pointers.append(nxt);directions.append(direction);faces.append(face);links.append(link)
            if len(pointers)>10:
                if len(pointers)-zero_steps>10 or len(pointers)>200:return 0
                #2a908a..2a91a0 appends nxt before searching the entire pointer
                #vector for that same pointer. The appended slot guarantees a
                #match, so this ordinary >10 branch rejects. Native561/565
                #positively observes an earlier match at index4 and return0.
                self.longCycleRejections.append(dict(length=len(pointers),zeroSteps=zero_steps,effectiveSteps=len(pointers)-zero_steps,newPointer=nxt,firstOccurrence=pointers.index(nxt),pointers=pointers.copy()))
                return 0
        raise ValueError('Cycle guard')

    def seed_nodes(self):
        for seed in self.g.seeds:
            seed=int(seed);face=self.g.vertex_corners[seed][0]//3;self.allocate(face,self.g.xyz[seed],np.zeros(2,dtype='<f4'))

    def run(self):
        g=self.g;self.seed_nodes()
        for pointer,seed in enumerate(g.seeds,1):
            fans=[]
            for corner in g.vertex_corners[int(seed)]:
                v=int(g.pt.flat[corner])
                if v not in fans:fans.append(v)
            for vertex in fans:
                uv=g.uv[vertex]
                if not all(float(v)==int(v) for v in uv):continue
                for c,v in enumerate(g.pt.flat):
                    if int(v)==vertex:
                        self.cycle(pointer,0,c//3,uv,False);self.cycle(pointer,1,c//3,uv,False)
        if not g.polygons:raise ValueError('Fallback source seed insertion remains unsupported')
        while g.frontier:
            pointer=g.frontier.pop()
            for direction in range(4):
                node=g.nodes[pointer]
                if not node[48]&(1<<direction):self.cycle(pointer,direction,struct.unpack_from('<i',node,20)[0],np.frombuffer(node[32:40],'<f4'),True)
        for pointer,direction in self.deferred:
            node=g.nodes[pointer]
            if not node[48]&(1<<direction):self.cycle(pointer,direction,struct.unpack_from('<i',node,20)[0],np.frombuffer(node[32:40],'<f4'),False)
        return g.materialize()
