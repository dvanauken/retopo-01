"""Reviewed float line/line and line/segment leaves2b2cf0/2b2760."""
import numpy as np
F=np.float32
TOL=F(1e-5)


def dot_yxz(a,b):return F(F(F(a[1]*b[1])+F(a[0]*b[0]))+F(a[2]*b[2]))


def length_yxz(v):return F(np.sqrt(dot_yxz(v,v)))


def line_line(first,second):
    a,u=F(first[:3]),F(first[3:]);b,v=F(second[:3]),F(second[3:]);w=F(b-a);cross=F([F(F(u[1]*v[2])-F(u[2]*v[1])),F(F(v[0]*u[2])-F(u[0]*v[2])),F(F(u[0]*v[1])-F(v[0]*u[1]))]);size=length_yxz(cross);wu=dot_yxz(u,w)
    if size>=TOL:
        uv=F(F(F(u[0]*v[0])+F(v[1]*u[1]))+F(u[2]*v[2]));wv=dot_yxz(v,w);denominator=F(F(uv*uv)-F(1))
        if denominator!=0:
            inverse=F(F(1)/denominator);s=F(F(F(wv*uv)-wu)*inverse);t=F(F(wv-F(wu*uv))*inverse);distance=F(abs(F(dot_yxz(w,cross)/size)));return distance,s,t,'ordinary'
        branch='zero-float-denominator'
    else:branch='near-parallel'
    cross=F([F(F(u[1]*w[2])-F(u[2]*w[1])),F(F(u[2]*w[0])-F(u[0]*w[2])),F(F(u[0]*w[1])-F(u[1]*w[0]))]);return length_yxz(cross),wu,F(0),branch


def line_segment(line,segment):
    line=F(line);segment=F(segment);edge=F(segment[3:]-segment[:3]);inverse=F(F(1)/length_yxz(edge));direction=F(edge*inverse);distance,s,t,branch=line_line(line,np.r_[segment[:3],direction].astype('<f4'));fraction=F(inverse*t)
    if fraction<0 or fraction>1:
        endpoint=segment[:3] if fraction<0 else segment[3:];branch+='-clamp-start' if fraction<0 else '-clamp-end';delta=F(endpoint-line[:3]);s=dot_yxz(delta,line[3:]);residual=F(delta-F(line[3:]*s));distance=length_yxz(residual);fraction=F(0 if fraction<0 else 1)
    return distance,s,fraction,branch
