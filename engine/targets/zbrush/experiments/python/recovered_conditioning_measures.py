"""Ordinary cached21a790 corners,219890 deficit and21b370 edge angles."""
import math
import numpy as np
from recovered_mesh_topology import build
from recovered_surface_normals import triangle_normals
F=np.float32


def dot(a,b):return F(F(F(a[0]*b[0])+F(a[1]*b[1]))+F(a[2]*b[2]))


def angle(a,b):
    den=math.sqrt(float(dot(a,a))*float(dot(b,b)))
    if den==0:raise NotImplementedError('Degenerate triangle angle')
    cosine=float(dot(a,b))/den;return math.acos(max(-1.,min(1.,cosine)))


def produce(positions,faces):
    topology=build(len(positions),faces);corners=[]
    for row in faces:
        if len(row)!=3:raise NotImplementedError('Only cached triangle measures')
        a,b,c=positions[row];ab=F(b-a);ac=F(c-a);bc=F(b-c);first=angle(ab,ac);second=angle(bc,ab);corners.extend([F(first),F(second),F((math.pi-first)-second)])
    corners=np.asarray(corners,dtype='<f4');deficit=np.zeros(len(positions),dtype='<f4')
    for vertex in range(len(positions)):
        cs=topology['vertexCorners'][topology['vertexCornerOffsets'][vertex]:topology['vertexCornerOffsets'][vertex+1]];total=0.
        for corner in cs:total+=float(corners[corner])
        deficit[vertex]=F(math.tau-total)
    normal=triangle_normals(positions,np.asarray(faces,dtype='<i4'));edges=[]
    for e in range(len(topology['edges'])):
        cs=topology['edgeCorners'][topology['edgeCornerOffsets'][e]:topology['edgeCornerOffsets'][e+1]]
        if len(cs)!=2:raise NotImplementedError('Only ordinary closed edge angles')
        cosine=float(dot(normal[int(cs[0])//3],normal[int(cs[1])//3]));edges.append(F(math.acos(max(-1.,min(1.,cosine)))))
    return dict(corners=corners,deficit=deficit,edgeAngles=np.asarray(edges,dtype='<f4'),normals=normal,topology=topology)
