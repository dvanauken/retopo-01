"""Ordinary0x2a6270 source/output correspondence and relaxation metadata."""
import struct
import numpy as np
F=np.float32


def build(graph):
    g=graph;n=g.counter;source=np.full(len(g.xyz),-1,dtype='<i4');weights=np.zeros(n,dtype='<f4');attachments=np.zeros((n,2),dtype='<i4');faces=np.full(n,-1,dtype='<i4');neighbors=np.full((4,n),-1,dtype='<i4');protected=np.zeros(n,dtype=bool);boundary=np.zeros(n,dtype=bool);snapped=[]
    def effective(node):
        index,alias=struct.unpack_from('<2i',node,40);return alias if alias>=0 else index
    for bucket in g.buckets:
        for pointer in bucket:
            node=g.nodes[pointer];kind,index=struct.unpack_from('<2i',node,24);out,alias=struct.unpack_from('<2i',node,40)
            if kind==1 and effective(node)>=0:source[index]=effective(node)
            if out>=0 and alias>=0:weights[alias]=F(.3)
    delta=F(g.xyz.max(axis=0)-g.xyz.min(axis=0));diagonal=F(np.sqrt(F(F(delta[1]*delta[1]+delta[0]*delta[0])+delta[2]*delta[2])));scale=struct.unpack('<d',bytes.fromhex('f168e388b5f8d43e'))[0];tolerance=((float(diagonal)*scale)*float(diagonal))*scale
    for bucket in g.buckets:
        for pointer in bucket:
            node=g.nodes[pointer];out=struct.unpack_from('<i',node,40)[0]
            if out<0:continue
            face=struct.unpack_from('<i',node,20)[0];kind,index=struct.unpack_from('<2i',node,24);point=np.frombuffer(node[8:20],'<f4');best=tolerance
            if face>=0:
                for vertex in g.tri[face]:
                    d=F(point-g.xyz[vertex]);distance=float(F(F(d[0]*d[0]+d[1]*d[1])+d[2]*d[2]))
                    if distance<best:kind=1;index=int(vertex);best=distance
                if kind==1:snapped.append(dict(output=out,source=index))
            attachments[out]=[4,face] if kind==0 else [kind,index];faces[out]=face
            for slot in range(4):
                target=struct.unpack_from('<Q',node,56+8*slot)[0]
                if target:neighbors[slot,out]=effective(g.nodes[target])
            if node[48]&16:weights[out]=0 if kind==1 and g.tags['vertices'][index] else 1
            protected[out]=bool(node[48]&0xa0);boundary[out]=bool(node[48]&0x20)
    return dict(sourceVertexOutput=source,relaxationWeights=weights,attachments=attachments,sourceFaces=faces,neighbors=neighbors,protected=protected,boundary=boundary,snapped=snapped,snapToleranceSquared=tolerance)
