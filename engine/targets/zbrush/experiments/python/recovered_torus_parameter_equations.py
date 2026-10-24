"""Ordinary2992d0 rows with reviewed scalar multiplication grouping.

This accepts original-derived face/frame/chart boundaries, not native values.
Degenerate/symmetry/nonordinary branches remain excluded.
"""
import numpy as np
from verify_parameter_rows import dot32

def equations(p,frame_a,frame_b,length,direction_a,direction_b,scale_u,scale_v):
 e1=np.float32(p[1]-p[0]);e2=np.float32(p[2]-p[0]);cross=np.cross(e1,e2);D=np.sqrt(np.float32(np.float32(cross[0]*cross[0]+cross[1]*cross[1])+np.float32(cross[2]*cross[2])),dtype=np.float32)
 if not D>0:raise ValueError('Positive ordinary triangle area required')
 x=float(dot32(e2,frame_a));y=float(dot32(e2,frame_b));L=float(length);inverse=1./float(D)
 def row(direction,scale):
  k=float(scale)*inverse;dx=float(direction[0]);dy=float(direction[1]);a=dx*(k*y);b=dy*((x-L)*k);c=dy*(k*x);d=dy*(k*L)
  return np.asarray([-a+b,a-c,d],dtype='<f8')
 return [row(direction_a,scale_u),row(direction_b,scale_u),row(direction_b,scale_v),row(direction_a,scale_v)]
