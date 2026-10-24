"""30db20 opposite-span quad patch initialization, provenance, relaxation and emission."""
import numpy as np
from recovered_polygon_grid_relaxation import relax
from recovered_polygon_provenance import Provenance
F=np.float32


def replace(points,faces,face,classes,provenance=None):
    points=np.asarray(points,dtype='<f4').copy();row=list(faces[face]);classes=np.asarray(classes,dtype='<i4');n=len(row);corners=[(i+1)%n for i in range(n) if classes[(i+1)%n]==1]
    if len(corners)!=4 or not np.all(np.isin(classes,[0,1])):raise ValueError('Four class1 corners and flat class0 spans required')
    spans=[(corners[(i+1)%4]-corners[i])%n for i in range(4)]
    if spans[0]!=spans[2] or spans[1]!=spans[3]:raise ValueError('Opposite corner spans must agree')
    width=(corners[0]-corners[-1])%n+1;height=(corners[1]-corners[0])%n+1;rotated=row[corners[-1]:]+row[:corners[-1]];grid=np.full((height,width),-1,dtype='<i4');grid[0]=rotated[:width];grid[-1]=rotated[width+height-2:2*width+height-2][::-1]
    for r in range(1,height-1):grid[r,0]=rotated[n-r];grid[r,-1]=rotated[width-1+r]
    if provenance is None:provenance=Provenance(len(points))
    extras=[];before=len(points);rowReciprocal=F(F(1)/F(height-1));colReciprocal=F(F(1)/F(width-1))
    for r in range(1,height-1):
        vertical=F(F(F(r)*rowReciprocal)*F(.5));bottom=F(F(.5)-vertical)
        for c in range(1,width-1):
            horizontal=F(F(F(c)*colReciprocal)*F(.5));left=F(F(.5)-horizontal);ids=[int(grid[r,0]),int(grid[r,-1]),int(grid[0,c]),int(grid[-1,c])];weights=[left,horizontal,bottom,vertical];value=F(F(F(F(points[ids[0]]*left)+F(points[ids[1]]*horizontal))+F(points[ids[2]]*bottom))+F(points[ids[3]]*vertical));new=before+len(extras);grid[r,c]=new;extras.append(value)
            if provenance.append(ids,weights)!=new:raise ValueError('Coordinate/provenance index mismatch')
    if extras:points=np.vstack([points,np.asarray(extras,dtype='<f4')])
    initial=points[grid].copy();smoothed,history=relax(initial,10,True)
    for r in range(height):
        for c in range(width):
            if grid[r,c]>=provenance.base:points[grid[r,c]]=smoothed[r,c]
    additions=[[int(grid[r-1,c-1]),int(grid[r-1,c]),int(grid[r,c]),int(grid[r,c-1])] for r in range(1,height) for c in range(1,width)];result=[list(x) for x in faces[:face]]+[list(x) for x in faces[face+1:]]+additions
    return points,result,dict(width=width,height=height,newVertexStart=before,newVertexCount=len(points)-before,cornerOrder=corners,grid=grid.tolist())
