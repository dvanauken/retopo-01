"""Ordinary27f780 reference frames and default isotropic1efb00 scale arrays.

No symmetry/feature reference-edge remapping, density map or anisotropic size.
"""
import math
import numpy as np
from probe_transport_helpers import cross,dot
F=np.float32


def normalize(vector):
    length=math.sqrt(float(dot(vector,vector)))
    if not length>=1e-28:raise NotImplementedError('Tiny reference-frame vector')
    return np.asarray([F(float(c)*(1/length)) for c in vector],dtype='<f4'),F(length)


def prepare(positions,triangles,normals,component_scale):
    first=[];second=[];lengths=[]
    for face,row in enumerate(triangles):
        a,length=normalize(F(positions[row[1]]-positions[row[0]]));b,_=normalize(cross(normals[face],a));first.append(a);second.append(b);lengths.append(length)
    return dict(basisA=np.asarray(first,dtype='<f4'),basisB=np.asarray(second,dtype='<f4'),localLength=np.asarray(lengths,dtype='<f4'),permutation=np.zeros(len(triangles),dtype=np.uint8),scaleA=np.full(len(triangles),F(component_scale),dtype='<f4'),scaleB=np.full(len(triangles),F(component_scale),dtype='<f4'))
