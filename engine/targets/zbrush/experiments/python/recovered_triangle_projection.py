"""Reviewed ordinary float nearest-triangle2d9c80 plane/barycentric/edge policy."""
import numpy as np
F=np.float32


def dot(a,b):return F(F(F(a[1]*b[1])+F(a[0]*b[0]))+F(a[2]*b[2]))
def length(a):return F(np.sqrt(dot(a,a)))


def segment(query,a,b):
    edge=F(b-a)
    if dot(F(query-a),edge)<=0:point=a.copy();return point,length(F(query-point))
    if F(-dot(edge,F(query-b)))<=0:point=b.copy();return point,length(F(query-point))
    size=length(edge)
    if size<F(1e-14):raise NotImplementedError('Tiny segment normalizer branch')
    direction=F(edge*F(F(1)/size));delta=F(query-a);parameter=dot(delta,direction);residual=F(delta-F(direction*parameter));return F(query-residual),length(residual)


def closest(query,triangle,normal):
    a,b,c=triangle;u=F(b-a);v=F(c-a);cross=F([F(F(normal[2]*v[1])-F(normal[1]*v[2])),F(F(normal[2]*v[0])-F(normal[0]*v[2])),F(F(normal[1]*v[0])-F(normal[0]*v[1]))]);det=F(F(F(cross[0]*u[0])-F(cross[1]*u[1]))+F(cross[2]*u[2]))
    if det==0:raise NotImplementedError('Degenerate normal/triangle stale point policy')
    size=length(normal)
    if size==0:raise NotImplementedError('Zero input normal')
    plane=F(normal*F(F(1)/size));offset=F(-dot(a,plane));size=length(plane)
    if size<F(1e-14):raise NotImplementedError('Tiny plane normalizer branch')
    direction=F(plane*F(F(1)/size));denominator=dot(direction,plane)
    if abs(denominator)<F(1e-5):raise NotImplementedError('Near-zero plane denominator stale point policy')
    point=F(query-F(direction*F(F(dot(query,plane)+offset)/denominator)));delta=F(point-a);uu=dot(u,u);uv=dot(v,u);du=dot(delta,u);dv=dot(delta,v);vv=dot(v,v);inverse=F(F(1)/F(F(vv*uu)-F(uv*uv)));s=F(F(F(vv*du)-F(dv*uv))*inverse);t=F(F(F(dv*uu)-F(du*uv))*inverse)
    branch='plane'
    if s<0 or t<0 or F(s+t)>1:
        p0,d0=segment(query,a,b);p1,d1=segment(query,b,c);p2,d2=segment(query,c,a);point=p0 if d0<d1 else p1;distance=d0 if d0<d1 else d1
        if d2<=distance:point=p2
        branch='boundary'
    return point,length(F(point-query)),branch
