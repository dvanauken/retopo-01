"""Literal scalar3x3 Jacobi operation order from engine2fa020.

Returns [vector.x,y,z,eigenvalue] rows in increasing absolute eigenvalue order.
No external eigensolver or remesher engine is used.
"""
import math
import numpy as np
from numba import njit


@njit(cache=False,fastmath=False)
def solve(packed,deferred_diagonal=False):
    a=np.zeros((3,3),dtype=np.float64);a[0,0]=packed[0];a[0,1]=packed[1];a[0,2]=packed[2];a[1,1]=packed[3];a[1,2]=packed[4];a[2,2]=packed[5]
    b=np.array([packed[0],packed[3],packed[5]]);d=b.copy();v=np.eye(3)
    for sweep in range(1,71):
        z=np.zeros(3,dtype=np.float64);total=(abs(a[0,2])+abs(a[0,1]))+abs(a[1,2])
        if total<1e-20:break
        threshold=total*.022222222222222223 if sweep<4 else 0.
        for p in range(2):
            for q in range(p+1,3):
                value=a[p,q];magnitude=100*abs(value)
                if sweep>=5 and magnitude<1e-20:a[p,q]=0.;continue
                if not abs(value)>threshold:continue
                difference=d[q]-d[p]
                if magnitude>=1e-20:
                    theta=(.5/value)*difference;t=1/(math.sqrt(theta*theta+1)+abs(theta))
                    if theta<0:t=-t
                else:t=value/difference
                a[p,q]=0.;h=value*t;d[p]-=h;d[q]+=h;z[q]+=h
                if deferred_diagonal:z[p]-=h
                else:b[p]-=h
                cosine=1/math.sqrt(t*t+1);sine=cosine*t;tau=sine/(cosine+1)
                for j in range(p):
                    g=a[j,p];h=a[j,q];a[j,p]=g-(tau*g+h)*sine;a[j,q]=(g-tau*h)*sine+h
                for j in range(p+1,q):
                    g=a[p,j];h=a[j,q];a[p,j]=g-(tau*g+h)*sine;a[j,q]=(g-tau*h)*sine+h
                for j in range(q+1,3):
                    g=a[p,j];h=a[q,j];a[p,j]=g-(tau*g+h)*sine;a[q,j]=(g-tau*h)*sine+h
                for j in range(3):
                    g=v[j,p];h=v[j,q];v[j,p]=g-(tau*g+h)*sine;v[j,q]=(g-tau*h)*sine+h
        for p in range(3):b[p]+=z[p];d[p]=b[p]
    out=np.empty((3,4),dtype=np.float64)
    for i in range(3):
        for j in range(3):out[i,j]=v[j,i]
        out[i,3]=d[i]
    for i,j in [(0,1),(1,2),(0,1)]:
        if abs(out[j,3])<abs(out[i,3]):
            for k in range(4):value=out[i,k];out[i,k]=out[j,k];out[j,k]=value
    return out
