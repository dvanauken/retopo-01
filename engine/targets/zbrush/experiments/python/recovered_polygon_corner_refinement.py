"""3092b0 unresolved corner refinement, counters and last straight-corner index."""
import struct
import numpy as np
LOW=struct.unpack('<d',bytes.fromhex('000000887cd90240'))[0]
PREFERRED=struct.unpack('<d',bytes.fromhex('00000078e25c0540'))[0]
HIGH=struct.unpack('<d',bytes.fromhex('000000387a6a0f40'))[0]


def counters(classes,start=0,end=None):
    row=np.asarray(classes,dtype='<i4')[start:end];zero=np.flatnonzero(row==0)
    return np.asarray([np.sum(row==1),np.sum(row==0),np.sum(row==-1),np.sum(row==2),np.sum(row==3),start+int(zero[-1]) if len(zero) else -1],dtype='<i4')


def refine(angles,classes,stats,start,end):
    angles=np.asarray(angles,dtype='<f4');classes=np.asarray(classes,dtype='<i4').copy();stats=np.asarray(stats,dtype='<i4').copy();changed=False;events=[]
    if stats[4]+stats[0]==4 and stats[2]==0:
        for i in range(start,end):
            if classes[i]==3 and (np.isnan(angles[i]) or float(angles[i])<PREFERRED):classes[i]=1;stats[4]-=1;stats[0]+=1;changed=True;events.append([i,1])
    if stats[4]>=0 and stats[0]==4 and stats[2]==0:
        for i in range(start,end):
            if classes[i]==3 and LOW<float(angles[i])<HIGH:classes[i]=0;stats[4]-=1;stats[1]+=1;stats[5]=i;changed=True;events.append([i,0])
    return classes,stats,changed,events
