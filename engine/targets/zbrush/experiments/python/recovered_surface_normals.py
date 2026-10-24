"""Ordinary209650 triangle normals using double geometry and float storage."""
import math
import numpy as np


def triangle_normals(positions,triangles):
    out=[]
    for row in triangles:
        a,b,c=positions[row].astype(float);u=b-a;v=c-a;n=np.asarray([u[1]*v[2]-v[1]*u[2],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]);length=math.sqrt((n[0]*n[0]+n[1]*n[1])+n[2]*n[2])
        if not length>0 or not math.isfinite(length):raise NotImplementedError('Degenerate source normal policy')
        out.append(np.asarray(n*(1/length),dtype='<f4'))
    return np.asarray(out,dtype='<f4')
