"""Ordinary default50/50 single-component field radii,275a00 and274f30.

Only the qualified default range/mixed interpolation branch is implemented.
Guide/feature sizing, explicit edge size and other detail controls are excluded.
"""
import math
import numpy as np
from recovered_original_densification import threshold_from_geometry
F=np.float32


def prepare(positions,faces,target):
    area,_,_=threshold_from_geometry(positions,faces,target)
    scale=F(np.sqrt(F(area/F(target))))
    # At detail50 the piecewise interpolants evaluate exactly to these knots.
    # Default component edge scale dominates sqrt(area * float1e-4).
    fallback=F(np.sqrt(F(area*F(1e-4))))
    if fallback>scale:raise NotImplementedError('Different field sizing base branch')
    low=F(F(.33)*scale);high=F(F(1.75)*scale)
    if float(high)*.8<float(low):raise NotImplementedError('Radius lower bound cap')
    ratio=F(high/low)
    count=1 if ratio==F(1) else 2 if ratio<F(1.7) else 3 if ratio<F(3) else 4 if ratio<F(4) else 5 if ratio<F(7) else 6
    values=[]
    for index in range(count):
        if count==1:value=high
        else:
            t=F(F(index)/F(count-1));linear=F(F(high-low)*t+low)
            exponent=F(F(math.log10(float(F(high/low))))*F(t-F(1)))
            logarithmic=F(F(math.pow(10,float(exponent)))*high)
            value=F(F(logarithmic+linear)*F(.5))
        values.append(value)
    return dict(area=area,componentScale=scale,minimum=low,maximum=high,ratio=ratio,radii=np.asarray(values,dtype='<f4'))
