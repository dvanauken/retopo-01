"""Signed curvature edge tensors; ordinary two-sided triangle source only.

Composes the independently recovered source topology and triangle normals.
No captured cache, normals, tangent, angle or tensor is a construction input.
Boundary edges have zero angle; nonmanifold edges are deliberately rejected.
"""
import math
import numpy as np
from recovered_mesh_topology import build
from recovered_surface_normals import triangle_normals
F=np.float32


def prepare(positions,triangles,cached_lengths=False):
    topology=build(len(positions),triangles);normal=triangle_normals(positions,triangles)
    edges=topology['edges'];offset=topology['edgeCornerOffsets'];corners=topology['edgeCorners']
    tensors=[];angles=[];tangents=[]
    if cached_lengths:
        from recovered_alternate_vertex_path import lengths
        source_lengths=lengths(positions,edges)
    for edge,(i,j) in enumerate(edges):
        delta=F(positions[j]-positions[i]);length=np.sqrt(F(F(delta[1]*delta[1]+delta[0]*delta[0])+delta[2]*delta[2]),dtype=F)
        if cached_lengths:length=source_lengths[edge]
        tangent=F(delta*F(1/length)) if length else np.zeros(3,dtype=F)
        count=int(offset[edge+1]-offset[edge]);angle=0.
        if count>2:raise NotImplementedError('Nonmanifold curvature tensor policy')
        if count==2:
            c0,c1=map(int,corners[offset[edge]:offset[edge+1]]);n0=normal[c0//3].astype(float);n1=normal[c1//3].astype(float)
            denominator=math.sqrt(float(np.dot(n0,n0)*np.dot(n1,n1)))
            if denominator:
                cosine=float(np.dot(n0,n1)/denominator)
                angle=math.acos(cosine) if -1<cosine<1 else math.pi if cosine<=-1 else 0.
            opposite0=positions[triangles[c0//3,(c0+2)%3]].astype(float);opposite1=positions[triangles[c1//3,(c1+2)%3]].astype(float)
            if np.dot(opposite1-opposite0,n0)>=0:angle=-angle
        angle=F(angle);alpha=float(F(length*angle));x,y,z=map(float,tangent)
        tensors.append([x*alpha*x,x*alpha*y,x*alpha*z,y*alpha*y,y*alpha*z,z*alpha*z]);angles.append(angle);tangents.append(tangent)
    return dict(topology=topology,normals=normal,angles=np.asarray(angles,dtype='<f4'),tangents=np.asarray(tangents,dtype='<f4'),tensors=np.asarray(tensors,dtype='<f8'))
