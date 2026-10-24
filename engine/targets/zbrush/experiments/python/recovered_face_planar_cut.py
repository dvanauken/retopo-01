"""252e50 ordinary triangle planar constraints, with qualified finite ordered inward repair.

Independent Triangle20250106 pzQ dependency qualified in EXP0068; arbitrary
duplicate-policy/nonfinite branches are not silently approximated.
"""
import math
import numpy as np
import triangle
from recovered_triangle_inward_repair import repair
F=np.float32

def cut(tri,positions,records):
    a,b,c=positions[tri];e=F(b-a).astype('f8');f=F(c-a).astype('f8')
    length=math.sqrt((e[1]*e[1]+e[0]*e[0])+e[2]*e[2]);axis=e*(1/length)
    along=(axis[1]*f[1]+axis[0]*f[0])+axis[2]*f[2];other=f-axis*along
    other*=1/math.sqrt((other[0]*other[0]+other[1]*other[1])+other[2]*other[2])
    height=(other[0]*f[0]+other[1]*f[1])+other[2]*f[2]
    points=[[0.,0.],[length,0.],[along,height]];mapping=list(map(int,tri));boundary=[(0.,0),(1.,1)];segments=[]
    for s,t,i,j in records:
        pair=[]
        for scalar,vertex in [(s,i),(t,j)]:
            vertex=int(vertex)
            if vertex not in mapping:
                d=F(positions[vertex]-a).astype('f8')
                point=np.array([(d[0]*axis[0]+d[1]*axis[1])+axis[2]*d[2],(d[0]*other[0]+d[1]*other[1])+other[2]*d[2]])
                if scalar<0:point=repair(point,np.asarray(points[:3]))[0]
                points.append(point.tolist());mapping.append(vertex)
            local=mapping.index(vertex);pair.append(local)
            if scalar>=0:boundary.append((float(scalar),local))
        segments.append(pair)
    boundary.append((2.,2));boundary.sort(key=lambda x:x[0])
    for k,(scalar,local) in enumerate(boundary):
        prior,previous=boundary[k-1]
        if prior!=scalar and previous!=local:segments.append([previous,local])
    points=np.asarray(points,'<f8');segments=np.asarray(segments,'<i4')
    if len({tuple(p) for p in points})!=len(points):raise NotImplementedError('2d0490 duplicate point policy remains unqualified')
    result=triangle.triangulate(dict(vertices=points,segments=segments),'pzQ')
    added=[]
    for x,y in result['vertices'][len(points):]:
        mapping.append(len(positions)+len(added));added.append(F(F(axis*x+other*y)+a))
    faces=np.asarray(mapping,'<i4')[result['triangles']]
    return faces,np.asarray(added,'<f4').reshape(-1,3),dict(points=points,segments=segments,outputPoints=result['vertices'],triangles=result['triangles'])
