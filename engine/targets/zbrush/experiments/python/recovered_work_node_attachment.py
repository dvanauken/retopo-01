"""New ordinary grid-node closest-edge attachment, 0x2aadc0/0x2b4540."""
import numpy as np
F=np.float32


def dot(a,b):return F(F(F(a[1]*b[1])+F(a[0]*b[0]))+F(a[2]*b[2]))


def segment_distance(point,a,b):
    point=F(point);a=F(a);b=F(b);delta=F(b-a)
    if dot(F(point-a),delta)<=0:closest=a.copy();res=F(point-closest)
    elif dot(delta,F(point-b))>=0:closest=b.copy();res=F(point-closest)
    else:
        length=F(np.sqrt(dot(delta,delta)));direction=F(delta*F(F(1)/length)) if abs(length)>=F(1e-14) else delta
        residual=F(point-a);t=dot(residual,direction);res=F(residual-F(direction*t));closest=F(point-res)
    return dot(res,res),closest


def classify(point,face,positions,triangles,face_edges):
    triangle=positions[triangles[face]].astype(float);a=triangle[1]-triangle[0];b=triangle[2]-triangle[0]
    cross=np.array([a[1]*b[2]-b[1]*a[2],b[0]*a[2]-a[0]*b[2],a[0]*b[1]-b[0]*a[1]])
    area=F(np.sqrt((cross[0]*cross[0]+cross[1]*cross[1])+cross[2]*cross[2]));threshold=F(area/F(100000));kind=0;index=-1
    for k in range(3):
        distance,_=segment_distance(point,positions[triangles[face,k]],positions[triangles[face,(k+1)%3]])
        if distance<threshold:kind=2;index=int(face_edges[face,k]);threshold=distance
    return kind,index
