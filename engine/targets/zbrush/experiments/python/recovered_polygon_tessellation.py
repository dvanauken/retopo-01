"""30aab0 float projection and accepted tessellation/original-order fan policy.

Uses a pinned independent public GLU reference, not the embedded engine kernel.
This does not recover every internal sweep/render branch.
"""
import math,struct
import numpy as np
from reference_glu_tessellation import tessellate
F=np.float32
TINY=struct.unpack('<d',bytes.fromhex('196050bef6b01f3a'))[0]


def projection(points,faces,face,closing_vertex=None):
    points=np.asarray(points,dtype='<f4');row=list(faces[face]);normal=np.zeros(3,dtype='<f4');closing=int(faces[0][0] if closing_vertex is None else closing_vertex)
    def add(a,b,closing=False):
        term=F([F(F(a[2]+b[2])*F(a[1]-b[1])),F(F(a[2]-b[2])*F(b[0]+a[0])),F(F(b[1]+a[1])*F(a[0]-b[0]))]);normal[:]=F(term+normal) if closing else F(normal+term)
    for a,b in zip(row[:-1],row[1:]):add(points[a],points[b])
    add(points[row[-1]],points[closing],True);square=F(F(F(normal[1]*normal[1])+F(normal[0]*normal[0]))+F(normal[2]*normal[2]));length=math.sqrt(float(square))
    if length<=-TINY or TINY<=length:normal=F(normal.astype(float)*(1/length))
    x,y,z=normal
    if abs(x)<=abs(y):axis=2 if abs(z)<abs(x) else 0
    else:axis=2 if abs(z)<=abs(y) else 1
    basis=np.zeros(3,dtype='<f4');basis[axis]=F(1)
    def cross(a,b):return F([F(F(a[1]*b[2])-F(a[2]*b[1])),F(F(a[2]*b[0])-F(a[0]*b[2])),F(F(a[0]*b[1])-F(a[1]*b[0]))])
    u=cross(basis,normal);v=cross(normal,u);out=[]
    for index in row:
        p=points[index];first=F(F(F(p[0]*u[0])+F(p[1]*u[1]))+F(p[2]*u[2]));second=F(F(F(v[1]*p[1])+F(p[0]*v[0]))+F(v[2]*p[2]));out.append([first,second])
    return np.asarray(out,dtype='<f4'),dict(normal=normal.tolist(),u=u.tolist(),v=v.tolist(),axis=axis,closingVertex=closing)


def replace(points,faces,face):
    row=list(faces[face]);flat,details=projection(points,faces,face);result=tessellate(flat,0);accepted=not result['combine'] and len(result['triangles'])==len(row)-2
    if accepted:additions=[[row[x] for x in tri] for tri in result['triangles']]
    else:additions=[[row[0],row[i],row[i+1]] for i in range(1,len(row)-1)]
    faces=[list(x) for x in faces[:face]]+[list(x) for x in faces[face+1:]]+additions;details.update(projected=flat,reference=result,accepted=accepted,action='reference-tessellation' if accepted else 'original-order-fan')
    return np.asarray(points,dtype='<f4').copy(),faces,details
