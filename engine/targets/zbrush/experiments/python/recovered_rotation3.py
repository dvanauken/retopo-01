"""3059d0 quaternion3x3 with326a90/3274b0 bounded float sin/cos polynomial.

Packed lanes use nearest-even quadrant conversion and explicit float rounding.
Large-lane fallback above10000 and nondefault FP rounding are unsupported.
"""
import numpy as np
F=np.float32


def literal(h):return np.frombuffer(bytes.fromhex(h),'<f4')[0]


def sine_lane(value):
    x=F(value)
    if not np.isfinite(x) or abs(float(x))>10000:raise NotImplementedError('Large/nonfinite trigonometric reduction')
    q=int(np.rint(F(x*literal('83f9a23e'))));n=F(q)
    r=F(F(F(x-F(literal('00004940')*n))-F(literal('00a07d3a')*n))-F(literal('00202234')*n))
    u=F(r-F(literal('1a61b42c')*n));z=F(r*r);p=F(F(literal('19052f36')*z)+literal('f1ba4fb9'));p=F(F(p*z)+literal('7387083c'));p=F(F(p*z)+literal('a5aa2abe'));result=F(F(F(p*z)*u)+u)
    bits=np.asarray(result,dtype='<f4').view('<u4').item()^((q&1)<<31)
    return np.asarray(bits,dtype='<u4').view('<f4').item()


def sincos(value):
    x=F(value)
    if abs(float(x))<float(literal('00000039')):return x,F(F(1)-F(F(x*x)*F(.5)))
    return F(sine_lane(x)),F(sine_lane(F(abs(x)+literal('db0fc93f'))))


def rotation(axis,angle,double_output=False):
    x,y,z=map(F,axis);length=F(np.sqrt(F(F(x*x+y*y)+z*z)))
    if float(length)>=1e-8:
        sine,w=sincos(F(F(angle)*F(.5)));factor=F(sine/length);x,y,z=[F(c*factor) for c in [x,y,z]]
    else:x=y=z=F(0);w=F(1)
    wx,wy,wz=F(w*x),F(w*y),F(w*z);xy,xz,yz=F(x*y),F(x*z),F(y*z);ww=2*float(F(w*w));out=np.empty(9,dtype='<f4')
    out[0]=F(float(F(F(x*x)+F(x*x)))+ww-1);out[1]=F(F(F(xy+xy)+wz)+wz);out[2]=F(F(xz-wy)+F(xz-wy));out[3]=F(F(xy-wz)+F(xy-wz));out[4]=F(float(F(F(y*y)+F(y*y)))+ww-1);out[5]=F(F(F(yz+yz)+wx)+wx);out[6]=F(F(F(xz+xz)+wy)+wy);out[7]=F(F(yz-wx)+F(yz-wx));out[8]=F(float(F(F(z*z)+F(z*z)))+ww-1)
    if double_output:
        xy,xz,yz,wx,wy,wz=map(float,[xy,xz,yz,wx,wy,wz]);out[1]=F((xy+xy)+(wz+wz));out[2]=F((xz-wy)+(xz-wy));out[3]=F((xy-wz)+(xy-wz));out[5]=F((yz+yz)+(wx+wx));out[6]=F((xz+xz)+(wy+wy));out[7]=F((yz-wx)+(yz-wx))
    return out.reshape(3,3,order='F')
