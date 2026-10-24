"""Persistent ordinary extraction graph; caller still supplies operation schedule."""
import struct
import numpy as np
from recovered_grid_isoline import advance
from recovered_work_node_frame import transport
from recovered_work_node_lookup import lookup
from recovered_work_node_attachment import classify
from recovered_work_node_cache import update
from recovered_cycle_assembly import assemble


class Graph:
    def __init__(self,xyz,tri,pt,uv,fe,eo,ec,quarters,seeds,threshold,cut_threshold,tags):
        self.xyz=xyz;self.tri=tri;self.pt=pt;self.uv=uv;self.fe=fe;self.eo=eo;self.ec=ec;self.quarters=quarters;self.seeds=seeds;self.threshold=threshold;self.cut_threshold=cut_threshold;self.tags=tags
        self.cs=[list(map(int,ec[eo[e]:eo[e+1]])) for e in range(len(eo)-1)];self.geometry=(tri,pt,uv,fe,self.cs,quarters);self.buckets=[[] for _ in tri];self.nodes={};self.positions={};self.counter=0;self.polygons=[];self.constructed=0;self.pending=None;self.frontier=[]
        self.vertex_corners=[[] for _ in xyz]
        for c,v in enumerate(tri.flat):self.vertex_corners[int(v)].append(c)
        self.cut=set()
        for edge,cs in enumerate(self.cs):
            if len(cs)==2 and set(pt[cs[0]//3,[cs[0]%3,(cs[0]%3+1)%3]])!=set(pt[cs[1]//3,[cs[1]%3,(cs[1]%3+1)%3]]):self.cut.add(edge)

    def allocate(self,pointer,face,point,uv):
        node=bytearray(0x90);struct.pack_into('<Q',node,0,self.buckets[face][0] if self.buckets[face] else 0);node[8:20]=np.asarray(point,dtype='<f4').tobytes();struct.pack_into('<iii',node,20,face,0,-1);node[32:40]=np.asarray(uv,dtype='<f4').tobytes();struct.pack_into('<ii',node,40,-1,-1);self.nodes[pointer]=node;self.positions[pointer]=np.asarray(point,dtype='<f4').copy();self.buckets[face].insert(0,pointer);self.constructed+=1
        if self.constructed<=len(self.seeds):
            seed=int(self.seeds[self.constructed-1]);expectedFace=self.vertex_corners[seed][0]//3
            if face!=expectedFace or not np.array_equal(point,self.xyz[seed]) or np.asarray(uv).any():raise ValueError('Seed constructor inputs do not match source seed order')
            struct.pack_into('<iii',node,20,-1,1,seed);struct.pack_into('<i',node,40,self.counter);self.counter+=1;node[48]=16
        else:
            if self.pending is None or self.pending.get('pointer') is not None:raise ValueError('Unexpected native allocation operation')
            a=self.pending
            if face!=a['face'] or not np.array_equal(np.asarray(uv,dtype='<f4'),a['uv']) or not np.array_equal(np.asarray(point,dtype='<f4'),a['position']):raise ValueError('Constructor geometry differs from own pending grid endpoint')
            kind,index=classify(a['position'],face,self.xyz,self.tri,self.fe);struct.pack_into('<ii',node,24,kind,index);a['pointer']=pointer;self.frontier.append(pointer)

    def walk(self,pointer,direction,face,uv,frontier_mode):
        node=self.nodes[pointer];kind,index=struct.unpack_from('<2i',node,24)
        if not node[48]&16:
            ok,slot,_=transport(struct.unpack_from('<i',node,20)[0],[kind,index],direction,face,*self.geometry)
            if ok:
                cached=struct.unpack_from('<Q',node,56+slot*8)[0]
                if cached:
                    self.pending=dict(status=0,pointer=cached,face=struct.unpack_from('<i',node,92+slot*4)[0],uv=np.frombuffer(node[108+slot*8:116+slot*8],'<f4').copy(),direction=struct.unpack_from('<b',node,88+slot)[0],link=node[140+slot],cached=True);return self.pending
        ans=advance(face,uv,direction,index if kind==1 and node[48]&16 else None,self.xyz,self.tri,self.uv,self.pt,self.fe,self.eo,self.ec,self.quarters,ordinary_start=not node[48]&16);ans['cached']=False
        if ans['status']==0:
            if ans['link'] and frontier_mode:ans['status']=6;ans['pointer']=0
            else:
                found,_=lookup(ans['face'],ans['corner'],ans['position'],ans['expand'],self.threshold,self.buckets,self.positions,self.tri,self.fe,self.cs,self.vertex_corners,self.cut,self.cut_threshold);ans['pointer']=found or None
                if found:
                    other=self.nodes[found];stored=struct.unpack_from('<i',other,20)[0]
                    if not other[48]&16 and stored!=ans['face']:
                        ok,d,_=transport(stored,struct.unpack_from('<2i',other,24),ans['direction'],ans['face'],*self.geometry)
                        if ok:ans.update(face=stored,uv=np.frombuffer(other[32:40],'<f4').copy(),direction=d)
        else:
            last=ans['states'][-1];ans.update(pointer=0,face=last['face'],uv=last['uv'],direction=last['direction'])
        self.pending=ans;return ans

    def finish_walk(self,pointer,direction,face,uv):
        ans=self.pending
        if ans['status']==0:
            if ans['pointer'] is None:raise ValueError('Missing constructor identity binding')
            if not ans['cached']:update(self.nodes,pointer,ans['pointer'],direction,face,np.asarray(uv,dtype='<f4').tobytes(),ans['direction'],ans['face'],ans['uv'].astype('<f4').tobytes(),ans['link'],self.geometry)
        self.pending=None;return ans

    def cycle(self,pointers,directions,faces,links):
        self.counter,polygons,_=assemble(pointers,self.nodes,directions,faces,links,self.counter,self.geometry,set(self.tags['selected']),self.tags['owner']);self.polygons+=polygons

    def polygon_buffer(self):
        offsets=[0];indices=[]
        for polygon in self.polygons:indices+=polygon;offsets.append(len(indices))
        return dict(offsets=offsets,indices=indices)

    def materialize(self):
        """Geometry part of0x2a6270; attachment/relaxation metadata separate."""
        vertices=np.zeros((self.counter,3),dtype='<f4');aliases={}
        for bucket in self.buckets:
            for pointer in bucket:
                node=self.nodes[pointer];index,alias=struct.unpack_from('<2i',node,40)
                if index>=0:
                    vertices[index]=np.frombuffer(node[8:20],'<f4')
                    if alias>=0:aliases[index]=alias
        polygons=[[aliases.get(i,i) for i in row] for row in self.polygons]
        return vertices,polygons


def active_header_differences(own,native):
    """Only pointer-selected cache data is initialized; padding is excluded."""
    bad=[]
    for offset,size,name in [(0,8,'next'),(8,12,'position'),(20,28,'face-kind-id-uv-id-alias'),(48,1,'flags'),(56,32,'neighbors')]:
        if own[offset:offset+size]!=native[offset:offset+size]:bad.append(name)
    for slot in range(4):
        if struct.unpack_from('<Q',own,56+slot*8)[0] or struct.unpack_from('<Q',native,56+slot*8)[0]:
            for offset,size in [(88+slot,1),(92+slot*4,4),(108+slot*8,8),(140+slot,1)]:
                if own[offset:offset+size]!=native[offset:offset+size]:bad.append('cache-'+str(slot)+'-'+str(offset))
    return bad
