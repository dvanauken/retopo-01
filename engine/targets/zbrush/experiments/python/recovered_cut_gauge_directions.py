"""29ad50 ordinary cut-aware FIFO gauge and float rotated tangent coefficients."""
from collections import deque
import numpy as np
from recovered_rotation3 import rotation
F=np.float32


def prepare(geometry,topology,frames,angles,quarters,cut):
    count=len(geometry['faces']);face_edges=topology['faceEdges'].reshape(-1,3);offset=topology['edgeCornerOffsets'];corners=topology['edgeCorners'];gauge=np.full(count,-1,dtype='<i4');components=0
    if len(cut)!=len(topology['edges']):raise ValueError('Logical source edge cut count')
    for seed in range(count):
        if gauge[seed]>=0:continue
        gauge[seed]=0;components+=1;queue=deque([seed])
        while queue:
            face=queue.popleft()
            for edge in face_edges[face]:
                if cut[edge] or offset[edge+1]-offset[edge]!=2:continue
                a,b=map(int,corners[offset[edge]:offset[edge+1]]//3);other=b if a==face else a
                if gauge[other]>=0:continue
                gauge[other]=(int(gauge[face])+(-int(quarters[edge]) if a==face else int(quarters[edge])))%4;queue.append(other)
    transitions=np.zeros(len(quarters),dtype='<i4')
    for edge in range(len(quarters)):
        if offset[edge+1]-offset[edge]!=2:continue
        a,b=map(int,corners[offset[edge]:offset[edge+1]]//3);transitions[edge]=int(quarters[edge])+int(gauge[b])-int(gauge[a])
    first=[];second=[];period=np.frombuffer(bytes.fromhex('db0fc93f'),'<f4')[0]
    for face in range(count):
        matrix=rotation(geometry['normals'][face],F(F(F(gauge[face])*period)+angles[face]),double_output=True);a=frames['basisA'][face];b=frames['basisB'][face];r=np.asarray([F(F(a[0]*matrix[k,0]+a[1]*matrix[k,1])+a[2]*matrix[k,2]) for k in range(3)],dtype='<f4');x=F(F(a[0]*r[0]+r[1]*a[1])+r[2]*a[2]);y=F(F(r[1]*b[1]+r[0]*b[0])+r[2]*b[2]);first.append([x,y]);minus=np.asarray(y,dtype='<f4').view('<u4').item()^0x80000000;second.append([np.asarray(minus,dtype='<u4').view('<f4').item(),x])
    return dict(gauge=gauge,transitions=transitions,directionA=np.asarray(first,dtype='<f4'),directionB=np.asarray(second,dtype='<f4'),components=components)
