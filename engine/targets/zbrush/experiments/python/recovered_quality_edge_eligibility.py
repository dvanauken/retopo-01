"""25aeb0 finite ordinary two-triangle quality-mutation numerical decision.

Literal arithmetic from782/784/785/786 primary instructions. Explicit quad
positions, cached normals/dihedral, face flags and threshold are leaf inputs.
No source topology, cache producer, candidate selection or mutation is read.
"""
import math
import numpy as np
F=np.float32
ONE_DEGREE=0.017453292519943295
TWO_DEGREES=0.03490658503988659
PI_F=F(3.1415927410125732)

def dot_xyz(a,b):return F(F(F(a[0]*b[0])+F(a[1]*b[1]))+F(a[2]*b[2]))
def cross(a,b):return np.asarray([F(F(a[1]*b[2])-F(a[2]*b[1])),F(F(a[2]*b[0])-F(a[0]*b[2])),F(F(a[0]*b[1])-F(a[1]*b[0]))],dtype='<f4')

def unsigned_angle(a,b):
    denominator=math.sqrt(float(dot_xyz(b,b))*float(dot_xyz(a,a)))
    if denominator==0:return 0.
    cosine=float(dot_xyz(b,a))/denominator
    if cosine<=-1:return math.pi
    return math.acos(cosine) if cosine<1 else 0.

def oriented_angle(a,b,normal):
    angle=unsigned_angle(a,b);c=cross(a,b);orientation=F(F(F(c[1]*normal[1])+F(c[0]*normal[0]))+F(c[2]*normal[2]))
    return F(2*math.pi-angle if orientation<=0 and angle!=0 else angle)

def normalize(v):
    v=np.asarray(v,dtype='<f4');norm=math.sqrt(float(dot_xyz(v,v)))
    if norm<=-1e-28 or norm>=1e-28:return np.asarray([F(float(x)*(1./norm)) for x in v],dtype='<f4')
    return v.copy()

def normal_angle(a,b):
    value=float(F(F(F(b[1]*a[1])+F(b[0]*a[0]))+F(b[2]*a[2])))
    if value<=-1:return F(math.pi)
    return F(math.acos(value)) if value<1 else F(0)

def evaluate(positions,normals,small_faces,old_dihedral,threshold):
    p=np.asarray(positions,dtype='<f4');n=np.asarray(normals,dtype='<f4').copy();small=np.asarray(small_faces,dtype=bool);old=F(old_dihedral);limit=F(threshold)
    if p.shape!=(4,3) or n.shape!=(2,3) or small.shape!=(2,) or not np.isfinite(p).all() or not np.isfinite(n).all() or not np.isfinite(old) or not np.isfinite(limit):raise ValueError('Finite ordinary quad/two-normal/cache inputs required')
    if small.all():return dict(accepted=False,score=None,reason='both-small-faces')
    if small[0]:n[0]=n[1]
    elif small[1]:n[1]=n[0]
    diagonal=F(p[3]-p[2]);angles=[oriented_angle(F(p[0]-p[2]),diagonal,n[0]),oriented_angle(diagonal,F(p[1]-p[2]),n[0])]
    if any(x>=PI_F for x in angles):return dict(accepted=False,score=None,reason='first-convexity',angles=angles)
    angles.extend([oriented_angle(F(p[3]-p[1]),diagonal,n[1]),oriented_angle(diagonal,F(p[3]-p[0]),n[1])])
    if any(x>=PI_F for x in angles[2:]):return dict(accepted=False,score=None,reason='second-convexity',angles=angles)
    score=min(angles)
    if score<limit:return dict(accepted=False,score=None,reason='minimum-angle',angles=angles,minimumAngle=score)
    first=normalize(cross(F(p[3]-p[0]),F(p[2]-p[0])));second=normalize(cross(F(p[2]-p[1]),F(p[3]-p[1])));new=normal_angle(first,second);keep=new<=F(old+old) if float(old)>=ONE_DEGREE else float(new)<=TWO_DEGREES
    return dict(accepted=bool(keep),score=score if keep else None,reason='accepted' if keep else 'normal-change',angles=angles,minimumAngle=score,newDihedral=new)
