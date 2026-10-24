"""Ordinary triangle bounding-box permutation/recursive partition2dab20."""
import numpy as np
F=np.float32


def build(positions,faces):
    vertices=F(positions)[np.asarray(faces,dtype='<i4')];boxes=np.c_[vertices.min(axis=1),vertices.max(axis=1)].astype('<f4');order=np.arange(len(faces),dtype='<i4');nodes=[];diagnostic=dict(partitions=0,smallFailedPartitions=0,medianFallbacks=0)
    def bound(begin,end):
        subset=boxes[order[begin:end]];return np.r_[subset[:,:3].min(axis=0),subset[:,3:].max(axis=0)].astype('<f4')
    def recurse(begin,end,bounds):
        pointer=len(nodes);node=dict(pointer=pointer,bounds=bounds.tolist());nodes.append(node);count=end-begin
        if count<=5:node.update(kind='leaf',begin=begin,end=end);return pointer
        extent=F(bounds[3:]-bounds[:3]);axis=(2 if extent[1]<extent[2] else 1) if extent[0]<=extent[1] else (0 if extent[2]<=extent[0] else 2);middle=F(F(bounds[axis+3]+bounds[axis])*F(.5));left=[];right=[];crossing=[]
        for face in order[begin:end]:
            lo,hi=boxes[face,axis],boxes[face,axis+3]
            if lo<middle:
                if middle<hi:crossing.append(int(face))
                else:left.append(int(face))
            else:right.append(int(face))
        # Native scratch writes right entries from the high end down, including
        # crossing entries after pure-right entries. Keep the reversal explicit.
        for face in crossing:
            if F(middle-boxes[face,axis])<F(boxes[face,axis+3]-middle):right.append(face)
            else:left.append(face)
        order[begin:end]=left+right[::-1];split=begin+len(left);diagnostic['partitions']+=1
        if split<begin+2 or end-2<split:
            if count<=10:node.update(kind='leaf',begin=begin,end=end);diagnostic['smallFailedPartitions']+=1;return pointer
            split=(begin+end)>>1;diagnostic['medianFallbacks']+=1
        node.update(kind='branch',children=[recurse(begin,split,bound(begin,split)),recurse(split,end,bound(split,end))]);return pointer
    if not len(faces):raise NotImplementedError('Empty source cache construction')
    root=recurse(0,len(faces),bound(0,len(faces)));return dict(root=root,faceCount=len(faces),nodes=nodes),order,diagnostic
