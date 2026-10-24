"""30f8f0 three-ring replacement, ordered by cyclic distance from an anchor."""
import numpy as np
from recovered_polygon_new_vertices import path


def replace(points,faces,face,selection):
    row=list(faces[face]);n=len(row);anchor,first,second=map(int,selection)
    if len({anchor,first,second})!=3:raise ValueError('Three distinct selected indices required')
    near,far=sorted([first,second],key=lambda x:(x-anchor)%n)
    additions=[path(row,anchor,near),path(row,near,far)+[row[anchor]],path(row,far,anchor)]
    return np.asarray(points,dtype='<f4').copy(),[list(x) for x in faces[:face]]+[list(x) for x in faces[face+1:]]+additions
