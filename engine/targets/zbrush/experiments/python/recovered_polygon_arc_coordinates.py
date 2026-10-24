"""30f680 float normalized cumulative lengths on an explicit cyclic ID span."""
import numpy as np
F=np.float32


def coordinates(points,ids,start,end,initial):
    points=np.asarray(points,dtype='<f4');ids=np.asarray(ids,dtype='<i4');out=np.asarray(initial,dtype='<f4').copy();total=F(0);index=int(start);n=len(ids)
    with np.errstate(all='ignore'):
        while index!=end:
            after=(index+1)%n;delta=F(points[ids[index]]-points[ids[after]]);x,y,z=delta;out[index]=total;length=F(np.sqrt(F(F(F(y*y)+F(x*x))+F(z*z))));total=F(total+length);index=after
        if start!=end:
            reciprocal=F(F(1)/total);index=int(start)
            while index!=end:out[index]=F(out[index]*reciprocal);index=(index+1)%n
    out[end]=F(1);return out
