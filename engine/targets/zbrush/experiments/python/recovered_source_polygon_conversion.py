"""24ea90 default tri/quad and preferred2d0a90 ordinary polygon conversion.

Newell double normal, least-component axis, unnormalized cross basis and pzQ
Triangle binding compose. Duplicate/degenerate/general fallback stays guarded.
"""
import math
import numpy as np
import triangle
from verify_cut_polygon_conversion import triangulate as small

def ngon(polygon,positions):
    points=positions[polygon].astype('f8');normal=np.zeros(3,'<f8')
    for a,b in zip(points,np.concatenate([points[1:],points[:1]])):
        normal[0]=(b[2]+a[2])*(a[1]-b[1])+normal[0]
        normal[1]=(a[2]-b[2])*(b[0]+a[0])+normal[1]
        normal[2]=(a[1]+b[1])*(a[0]-b[0])+normal[2]
    length=math.sqrt((normal[0]*normal[0]+normal[1]*normal[1])+normal[2]*normal[2])
    if length<=1e-100:raise NotImplementedError('Degenerate polygon normal')
    normal=normal*(1/length);x,y,z=abs(normal)
    index=(2 if z<x else 0) if x<=y else (2 if z<=y else 1)
    axis=np.zeros(3,'<f8');axis[index]=1
    u=np.array([normal[2]*axis[1]-normal[1]*axis[2],axis[2]*normal[0]-axis[0]*normal[2],axis[0]*normal[1]-axis[1]*normal[0]])
    v=np.array([normal[1]*u[2]-normal[2]*u[1],u[0]*normal[2]-normal[0]*u[2],normal[0]*u[1]-u[0]*normal[1]])
    projected=np.array([[(p[1]*u[1]+p[0]*u[0])+p[2]*u[2],(p[1]*v[1]+p[0]*v[0])+p[2]*v[2]] for p in points],'<f8')
    if len(set(map(tuple,projected)))!=len(points):raise NotImplementedError('Projected duplicate polygon policy')
    segments=np.array([[i,(i+1)%len(points)] for i in range(len(points))],'<i4')
    result=triangle.triangulate(dict(vertices=projected,segments=segments),'pzQ')
    if len(result['vertices'])!=len(points) or len(result.get('triangles',[]))!=len(points)-2:raise NotImplementedError('Preferred ngon triangulation failure/fallback')
    faces=np.asarray(polygon,'<i4')[result['triangles']]
    return faces,dict(points=projected,segments=segments,normal=normal,axis=u,other=v,localTriangles=result['triangles'])

def triangulate(polygons,positions):
    output=[];flipped=0
    for p in polygons:
        if len(p)<=4:
            tris,count=small([p],positions);flipped+=count
        else:tris,_=ngon(p,positions)
        output.extend(tris.tolist())
    return np.asarray(output,'<i4'),flipped
