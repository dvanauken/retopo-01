"""31d5c0 boundary-length weighted two-buffer grid iterations, literal float grouping."""
import numpy as np
F=np.float32


def length(v):
    x,y,z=F(v);return F(np.sqrt(F(F(F(x*x)+F(y*y))+F(z*z))))


def relax(grid,iterations=10,enabled=True):
    source=np.asarray(grid,dtype='<f4').copy();history=[]
    if not enabled:return source,history
    h,w,_=source.shape;bottom=np.asarray([length(F(source[0,c]-source[0,c+1])) for c in range(w-1)],dtype='<f4');top=np.asarray([length(F(source[-1,c]-source[-1,c+1])) for c in range(w-1)],dtype='<f4');left=np.asarray([length(F(source[r,0]-source[r+1,0])) for r in range(h-1)],dtype='<f4');right=np.asarray([length(F(source[r,-1]-source[r+1,-1])) for r in range(h-1)],dtype='<f4');destination=source.copy()
    with np.errstate(all='ignore'):
        for iteration in range(iterations):
            for r in range(1,h-1):
                t=F(F(r)/F(h-1))
                for c in range(1,w-1):
                    fraction=F(F(c)/F(w-1));vertical=F(F(F(F(1)-fraction)*left[r-1])+F(fraction*right[r-1]));a=F(F(F(1)-t)*bottom[c-1]);numerator=F(F(top[c-1]*t)+a);denominator=F(F(F(F(t+t)*top[c-1])+a)+F(F(F(1)-t)*bottom[c-1]));q=F(numerator/denominator);p=F(F(F(.5)/vertical)*vertical);neighbors=F(F(F(F(F(1)-p)*source[r-1,c])+F(p*source[r+1,c]))+F(F(F(F(1)-q)*source[r,c-1])+F(q*source[r,c+1])));destination[r,c]=F(F(destination[r,c]*F(.5))+F(F(neighbors*F(.5))*p))
            source,destination=destination,source;history.append(source.copy())
    return source,history
