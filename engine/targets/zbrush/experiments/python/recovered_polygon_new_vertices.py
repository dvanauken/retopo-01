"""Independent30c310 two-corner extrapolation and ordered ring replacement."""
import numpy as np
from recovered_polygon_provenance import Provenance
F=np.float32


def path(row,begin,end):
    n=len(row);result=[];index=begin%n
    while True:
        result.append(row[index])
        if index==end%n:return result
        index=(index+1)%n


def two_corners(points,faces,face,begin,end,provenance=None):
    points=np.asarray(points,dtype='<f4');row=list(faces[face]);n=len(row)
    if not(0<=begin<n and 0<=end<n and 3<=(end-begin)%n<=n-3):raise ValueError('Reviewed nonadjacent corner pair required')
    b=row[begin];e=row[end];bp=row[(begin-1)%n];bn=row[(begin+1)%n];ep=row[(end-1)%n];en=row[(end+1)%n]
    newb=len(points);newe=newb+1
    pb=F(points[bn]+F(F(points[bp]-points[b])*F(.6)))
    pe=F(points[ep]+F(F(points[en]-points[e])*F(.6)))
    if provenance is not None:
        if provenance.append([bn,bp,b],[1,F(.6),F(-.6)])!=newb:raise ValueError('Coordinate/provenance base mismatch')
        if provenance.append([ep,en,e],[1,F(.6),F(-.6)])!=newe:raise ValueError('Coordinate/provenance base mismatch')
    replacements=[path(row,begin+1,end-1)+[newe,newb],[e,en,newe,ep],[newb,newe]+path(row,end+1,begin-1),[b,bn,newb,bp]]
    result=[list(x) for x in faces[:face]]+[list(x) for x in faces[face+1:]]+replacements
    return np.vstack([points,pb,pe]).astype('<f4'),result


def three_corners(points,faces,face,begin,middle,end,provenance=None):
    points=np.asarray(points,dtype='<f4');row=list(faces[face]);n=len(row)
    if not(0<=begin<n and 0<=middle<n and 0<=end<n and begin!=end):raise ValueError('Distinct endpoint indices required')
    a,b,c=[row[index] for index in [begin,middle,end]];new=len(points)
    point=F(F(F(points[a]-points[b])+points[b])+F(points[c]-points[b]))
    if provenance is not None and provenance.append([b,a,c],[-1,1,1])!=new:raise ValueError('Coordinate/provenance base mismatch')
    opposite=(middle+n//2)%n
    replacements=[path(row,begin,end)+[new],path(row,end,opposite)+[new],path(row,opposite,begin)+[new]]
    result=[list(x) for x in faces[:face]]+[list(x) for x in faces[face+1:]]+replacements
    return np.vstack([points,point]).astype('<f4'),result


def five_corners(points,faces,face,selection,provenance=None):
    from recovered_polygon_diagonal_score import normalized
    points=np.asarray(points,dtype='<f4');row=list(faces[face]);begin,second,middle,fourth,end=map(int,selection);a,b,c,d,e=[row[x] for x in selection];new=len(points)
    def length(vector):
        x,y,z=F(vector);return F(np.sqrt(F(F(F(x*x)+F(y*y))+F(z*z))))
    u=normalized(F(points[d]-points[c]));v=normalized(F(points[b]-points[c]));ab=length(F(points[a]-points[b]));ed=length(F(points[e]-points[d]));point=F(F(F(u*ab)+points[c])+F(v*ed))
    if provenance is not None and provenance.append([c,a,b,e,d],[1,1,-1,1,-1])!=new:raise ValueError('Coordinate/provenance base mismatch')
    replacements=[path(row,begin,middle)+[new],path(row,middle,end)+[new],path(row,end,begin)+[new]]
    result=[list(x) for x in faces[:face]]+[list(x) for x in faces[face+1:]]+replacements
    return np.vstack([points,point]).astype('<f4'),result
