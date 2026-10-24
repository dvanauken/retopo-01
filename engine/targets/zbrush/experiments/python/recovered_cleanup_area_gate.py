"""263480 first candidate gate: cached doubled face area versus total area.

209650 subtracts float coordinates after promotion to double and stores each
cross magnitude as float;05d910 totals in stored face order and halves once.
This helper proves only the no-eligible-face branch, never a moving repair.
"""
import math
import numpy as np
F=np.float32

def measure(positions,faces):
    areas=[];total=F(0)
    for row in faces:
        a,b,c=positions[row].astype('f8');u=b-a;v=c-a
        x=u[1]*v[2]-v[1]*u[2];y=u[2]*v[0]-u[0]*v[2];z=u[0]*v[1]-u[1]*v[0]
        area=F(math.sqrt((x*x+y*y)+z*z));areas.append(area);total=F(total+area)
    total=F(total*F(.5));limit=F(float(total)*1e-8)
    if float(limit)<1e-12:limit=F(1e-12)
    areas=np.asarray(areas,'<f4')
    return dict(areas=areas,totalArea=float(total),limit=float(limit),eligibleFaces=np.flatnonzero(areas<=limit))
