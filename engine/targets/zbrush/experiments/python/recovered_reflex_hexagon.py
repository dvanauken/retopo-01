"""Reviewed20ed70 normalization and30fe20 angles; six-gon heuristic remains scoped."""
import math,struct
import numpy as np
F=np.float32


def constant(bits):return np.frombuffer(struct.pack('<I',bits),'<f4')[0]


def norm(v):
    v=F(v).copy();square=F(F(v[0]*v[0]+v[1]*v[1])+v[2]*v[2]);length=np.sqrt(np.float64(square))
    if np.isnan(length) or length<=-1e-28 or length>=1e-28:v=F(v.astype(np.float64)*(np.float64(1)/length))
    return v


def angles(points,edge_directions=None):
    points=F(points);normal=np.zeros(3,dtype="<f4")
    for a,b in zip(points,np.roll(points,-1,axis=0)):
        normal[0]=F(F(F(a[1]-b[1])*F(a[2]+b[2]))+normal[0]);normal[1]=F(F(F(a[2]-b[2])*F(a[0]+b[0]))+normal[1]);normal[2]=F(F(F(a[0]-b[0])*F(a[1]+b[1]))+normal[2])
    normal=norm(normal)
    result=[]
    for i,p in enumerate(points):
        a=F(p-points[i-1]) if edge_directions is None else F(edge_directions[i][0]);b=F(points[(i+1)%len(points)]-p) if edge_directions is None else F(edge_directions[i][1]);aa=F(F(a[0]*a[0]+a[1]*a[1])+a[2]*a[2]);bb=F(F(b[0]*b[0]+b[1]*b[1])+b[2]*b[2]);ab=F(F(b[0]*a[0]+b[1]*a[1])+b[2]*a[2]);denominator=np.sqrt(np.float64(bb)*np.float64(aa))
        if denominator==0 or np.isnan(denominator):value=0.
        else:
            cosine=np.float64(ab)/denominator;value=(math.acos(float(cosine)) if cosine<1 else 0.) if cosine>-1 else math.pi
        cross=F([F(F(a[1]*b[2])-F(a[2]*b[1])),F(F(a[2]*b[0])-F(a[0]*b[2])),F(F(a[0]*b[1])-F(a[1]*b[0]))]);orientation=F(F(F(normal[1]*cross[1])+F(cross[0]*normal[0]))+F(normal[2]*cross[2]))
        if not orientation>0 and value!=0:value=math.tau-value
        result.append(F(value))
    return np.asarray(result,dtype="<f4")

def classify(points):
    if len(points)!=6:raise NotImplementedError('Only reviewed existing-vertex six-gon special branch')
    a=angles(points);classes=np.full(6,3,dtype='<i4');ambiguous=0;pi=constant(0x40490fdb)
    for i,angle in enumerate(a):
        folded=F(constant(0x40c90fdb)-angle) if angle>pi else angle
        if folded<constant(0x3f71463b) or constant(0x400cbe4c)<folded:
            if folded<=constant(0x3ef1463b):classes[i]=0
            elif folded<constant(0x402ae714):ambiguous+=1
            else:classes[i]=2
        else:classes[i]=1 if angle<=pi else -1
    largest=int(np.argmax(a));nonreflex=a[a<pi]
    if ambiguous and a[largest]>constant(0x4071463b) and max(nonreflex,default=F(0))<constant(0x4024deec) and min(a)>constant(0x3f10c3bd):
        classes[:]=1;classes[largest]=-1
    else:raise NotImplementedError('General polygon class adjustment not recovered')
    return a,classes
