"""Reviewed29d240 undirected relaxation targets; no captured targets are read."""
import numpy as np
from recovered_reflex_hexagon import norm
F=np.float32


def aggregate(positions,edges,directed,guide_edges):
    if np.shape(directed)!=(2*len(edges),7):raise ValueError('Two seven-float directed records per edge required')
    directions=[];minimum=[];maximum=[]
    for i,(a,b) in enumerate(edges):
        x,y=directed[2*i:2*i+2];weight=F(x[2]/F(y[2]+x[2]));other=F(F(1)-weight)
        minimum.append(F(F(other*y[0])+F(weight*x[0])));maximum.append(F(F(other*y[1])+F(weight*x[1])))
        valid=F(y[6]+x[6])
        if valid==0:direction=np.zeros(3,dtype='<f4')
        else:
            w=F(x[6]/valid);v=F(F(1)-w);direction=norm(F(F(x[3:6]*w)-F(y[3:6]*v)))
        if guide_edges[i]:direction=norm(F(positions[b]-positions[a]))
        directions.append(direction)
    return dict(directions=np.asarray(directions,dtype='<f4'),minimum=np.asarray(minimum,dtype='<f4'),maximum=np.asarray(maximum,dtype='<f4'))
