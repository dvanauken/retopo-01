"""254210 bounded ordered boundary cuts, ordinary two-chord intersections.

Same-edge overlaps, shared endpoint/near-endpoint intersection fallbacks, and
parallel/skew fallback policies remain guarded. Source floats promote to double
before2b50a0/2b1a00 normalized-line arithmetic; final point narrows to float3.
"""
import math
import numpy as np
F=np.float32

def intersection(positions,first,second):
    a,b=positions[list(first)].astype('f8');c,d=positions[list(second)].astype('f8')
    u=b-a;v=d-c
    length=math.sqrt((u[1]*u[1]+u[0]*u[0])+u[2]*u[2]);other=math.sqrt((v[1]*v[1]+v[0]*v[0])+v[2]*v[2])
    if min(length,other)<1e-18:raise NotImplementedError('Degenerate intersection directions')
    u=u*(1/length);v=v*(1/other);delta=c-a
    uv=(u[0]*v[0]+u[1]*v[1])+u[2]*v[2]
    du=(delta[1]*u[1]+delta[0]*u[0])+delta[2]*u[2]
    dv=(delta[1]*v[1]+delta[0]*v[0])+delta[2]*v[2]
    denom=1-uv*uv
    if denom<1e-50:raise NotImplementedError('Parallel2b1a00 fallback')
    inv=1/denom;along=(du-dv*uv)*inv;across=(du*uv-dv)*inv
    if not 0<along<length or not 0<across<other:raise NotImplementedError('2b50a0 exterior fallback')
    fraction=along/length
    if not 1e-5<fraction<1-1e-5:raise NotImplementedError('254210 endpoint intersection repair')
    return F(u*along+a),fraction

def cut(polygon,positions,records,split_degenerate=True):
    polygon=list(map(int,polygon));records=[tuple(r) for r in records]
    if not 1<=len(records)<=2:raise NotImplementedError('One/two ordered chords only')
    s,t,a,b=records[0];n=len(polygon)
    s=0. if s==n else s;t=0. if t==n else t
    if 0<=t<s:s,t,a,b=t,s,b,a
    if not 0<=s<=t<n:raise NotImplementedError('Boundary coordinates required')
    if s==t:
        if len(records)!=1 or a!=b or s==int(s) or not split_degenerate:raise NotImplementedError('General degenerate254210 branch')
        t=float((int(s)+2)%n);b=polygon[int(t)]
        if t<s:s,t,a,b=t,s,b,a
    if int(s)==int(t):raise NotImplementedError('Same-edge chord')
    i,j=int(s),int(t);fa=s-i;fb=t-j
    left=polygon[:i+1]+([int(a)] if fa else [])+[int(b)]+polygon[j+1:]
    right=[int(a)]+polygon[i+1:j+1]+([int(b)] if fb else [])
    if min(len(left),len(right))<3:raise NotImplementedError('Adjacent-corner redundant constraint')
    if len(records)==1:return [left,right],np.empty((0,3),'<f4')
    x,y,c,d=records[1]
    if 0<=y<x:x,y,c,d=y,x,d,c
    if not 0<=x<y<n or x in (s,t) or y in (s,t):raise NotImplementedError('Shared/degenerate multiple boundary endpoints')
    next_index=i+(1 if fa==0 else 2)
    def side(value):return 2 if s<value<t else (1 if value<s else 3)
    def mapped(value,which):
        k=int(value);f=value-k
        if which==1:return f/fa+i if k==i else value
        if which==2:return (f-fa)/(1-fa) if k==i else value-i
        return (f-fb)/(1-fb)+next_index if k==j else (value+next_index)-j
    sx,sy=side(x),side(y);mx,my=mapped(x,sx),mapped(y,sy)
    if (sx==2)==(sy==2):
        if sx==2:rhs,added=cut(right,positions,[(mx,my,c,d)],split_degenerate);return [left]+rhs,added
        lhs,added=cut(left,positions,[(mx,my,c,d)],split_degenerate);return lhs+[right],added
    point,fraction=intersection(positions,(int(a),int(b)),(int(c),int(d)))
    vertex=len(positions);extended=np.concatenate([positions,point[None]])
    if sx==2:
        lr=(next_index-1+fraction,my,vertex,d);rr=(mx,(1-fraction)+(j-i+(1 if fb else 0)),c,vertex)
    else:
        lr=(mx,next_index-1+fraction,c,vertex);rr=((1-fraction)+(j-i+(1 if fb else 0)),my,vertex,d)
    lhs,extra1=cut(left,extended,[lr],split_degenerate);rhs,extra2=cut(right,extended,[rr],split_degenerate)
    if len(extra1) or len(extra2):raise AssertionError('Unexpected recursive intersection')
    return lhs+rhs,point[None]
