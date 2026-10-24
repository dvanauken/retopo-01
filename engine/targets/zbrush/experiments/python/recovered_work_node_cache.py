"""Bidirectional cache writes at the end of successful 0x2aadc0 walks."""
import struct
from recovered_work_node_frame import transport


def update(nodes,start,finish,input_direction,input_face,input_uv,
           output_direction,output_face,output_uv,link,geometry):
    a=nodes[start];b=nodes[finish];writes=[]
    def slot(node,d,f):
        face=struct.unpack_from('<i',node,0x14)[0];attachment=struct.unpack_from('<2i',node,0x18)
        ok,d,_=transport(face,attachment,d,f,*geometry)
        return d if ok else None
    def fill(node,index,pointer,d,face,uv):
        if index is not None and struct.unpack_from('<Q',node,0x38+8*index)[0]==0:
            struct.pack_into('<Q',node,0x38+8*index,pointer);struct.pack_into('<b',node,0x58+index,d);struct.pack_into('<i',node,0x5c+4*index,face);node[0x6c+8*index:0x74+8*index]=uv;node[0x8c+index]=link;return True
        return False
    if not a[0x30]&16:
        index=slot(a,input_direction,input_face)
        if fill(a,index,finish,output_direction,output_face,output_uv):writes.append((start,index))
    if not b[0x30]&16:
        index=slot(b,(output_direction+2)%4,output_face)
        if fill(b,index,start,(input_direction+2)%4,input_face,input_uv):writes.append((finish,index))
    return writes
