"""26f400 face tensor averaging and largest-absolute eigenpair channels.

Validity and cross-scale selection are separate consumers. No excluded faces
are accepted by this bounded ordinary producer.
"""
import numpy as np
from numba import njit
from recovered_field_eigensystem import solve


@njit(cache=False,fastmath=False)
def prepare(triangles,tensors,marks):
    directions=np.zeros((len(tensors),len(triangles),3),dtype=np.float32);middle=np.zeros((len(tensors),len(triangles)),dtype=np.float32);largest=middle.copy()
    for scale in range(len(tensors)):
        for face in range(len(triangles)):
            accum=np.zeros(6,dtype=np.float64);count=0
            for corner in range(3):
                vertex=triangles[face,corner]
                if marks[vertex]:continue
                for channel in range(6):accum[channel]+=tensors[scale,vertex,channel]
                count+=1
            if count:
                factor=1./count
                for channel in range(6):accum[channel]*=factor
            result=solve(accum,deferred_diagonal=True)
            for channel in range(3):directions[scale,face,channel]=np.float32(result[2,channel])
            middle[scale,face]=np.float32(result[1,3]);largest[scale,face]=np.float32(result[2,3])
    return directions,middle,largest
