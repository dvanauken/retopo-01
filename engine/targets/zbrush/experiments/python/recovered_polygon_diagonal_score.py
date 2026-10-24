"""30ca00 two endpoint unsigned-angle imbalance multipliers, literal float order."""
import math,struct
import numpy as np
F=np.float32
COEFFICIENT=np.frombuffer(bytes.fromhex('4576f43f'),'<f4')[0]
TINY=struct.unpack('<d',bytes.fromhex('196050bef6b01f3a'))[0]


def dot(a,b):return F(F(a[1]*b[1]+a[0]*b[0])+a[2]*b[2])


def normalized(vector):
    vector=F(vector);length=math.sqrt(float(dot(vector,vector)))
    if length<=-TINY or TINY<=length:return F(vector.astype(float)*(1/length))
    return vector


def adjust(points,begin,end,length,score):
    points=F(points);n=len(points);axis=F(F(points[begin]-points[end])*F(F(1)/F(length)));score=F(score);factors=[]
    for vertex in [begin,end]:
        first=normalized(F(points[vertex]-points[(vertex-1)%n]));second=normalized(F(points[vertex]-points[(vertex+1)%n]));a=abs(dot(axis,first));b=abs(dot(axis,second));a=F(math.acos(float(a))) if a<F(1) else F(0);b=F(math.acos(float(b))) if b<F(1) else F(0);factor=F(F(F(abs(F(a-b)))*COEFFICIENT)+F(1));score=F(factor*score);factors.append(factor)
    return score,np.asarray(factors,dtype='<f4')
