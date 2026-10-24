"""12db90 zero-attachment early return, composed with the existing mover.

The native branch returns0 without committing a position for kind0. Other
unsupported kinds retain the existing mover's guard; sharp turns remain guarded.
"""
import numpy as np
from recovered_attached_surface_move import move as attached
def move(source,tri,topology,normals,guides,attachment,point,displacement):
    if int(attachment[0])==0:
        return np.asarray(point,dtype='<f4').copy(),np.asarray(attachment,dtype='<i4').copy(),[]
    return attached(source,tri,topology,normals,guides,attachment,point,displacement)
