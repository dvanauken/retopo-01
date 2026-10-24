"""Reviewed ordinary 1efb00 caps including low confidence and zero curvature.

This is a leaf operator. Area balance, source classes, excluded-face copying,
diffusion, ratio clamping and the coupled objective are separate operations.
Native branch qualification uses explicit controlled field interventions.
"""
import math
import numpy as np
F=np.float32
THRESHOLD=F(.01);TINY=1e-8
THIRD=np.frombuffer(bytes.fromhex('abaaaa3e'),'<f4')[0]
TWO_THIRDS=np.frombuffer(bytes.fromhex('abaa2a3f'),'<f4')[0]
FLOOR_FACTOR=np.frombuffer(bytes.fromhex('1d78963f'),'<f4')[0]
def prepare(middle,largest,weights,gauge,component_scale,samples=16,maximum_ratio=4.):
    middle=np.asarray(middle,dtype='<f4');largest=np.asarray(largest,dtype='<f4');weights=np.asarray(weights,dtype='<f4');gauge=np.asarray(gauge,dtype='<i4');shape=middle.shape
    if middle.ndim!=1 or not len(middle) or any(x.shape!=shape for x in [largest,weights,gauge]):raise ValueError('Nonempty equally sized face arrays required')
    if not all(np.isfinite(x).all() for x in [middle,largest,weights]):raise ValueError('Finite source fields required')
    with np.errstate(over='ignore',invalid='ignore'):parameters=np.asarray([component_scale,samples,maximum_ratio],dtype='<f4')
    if not np.isfinite(parameters).all() or parameters[0]<=0 or not math.isfinite(samples) or not float(samples).is_integer() or not 1<=samples<=2147483647 or parameters[2]<=1:raise ValueError('Finite float32 positive scale/ratio and positive int32 circle count required')
    coefficient=F(2*math.sin(3.1415/float(F(samples))));lower=F(F(F(component_scale)/F(maximum_ratio))*F(.9));a=np.full(shape,F(component_scale),dtype='<f4');b=a.copy();mid=abs(middle);large=abs(largest);low=weights<=THRESHOLD
    lowactive=low&(large.astype(float)>=TINY);highactive=(~low)&((large.astype(float)>=TINY)|(mid.astype(float)>=TINY))
    with np.errstate(divide='ignore',over='ignore',invalid='raise'):
        reciprocal_middle=F(F(1)/mid);reciprocal_largest=F(F(1)/large)
        mixed=F(F(mid*THIRD)+F(large*TWO_THIRDS));reciprocal_mixed=F(F(1)/mixed)
        cap_middle=F(reciprocal_middle*coefficient);cap_largest=F(reciprocal_largest*coefficient);cap_mixed=F(reciprocal_mixed*coefficient)
        floor_middle=np.minimum(lower,F(reciprocal_middle*FLOOR_FACTOR));floor_largest=np.minimum(lower,F(reciprocal_largest*FLOOR_FACTOR));floor_mixed=np.minimum(lower,F(reciprocal_mixed*FLOOR_FACTOR))
    odd=(gauge&1)!=0
    higha=np.maximum(np.minimum(a,np.where(odd,cap_largest,cap_middle)),np.where(odd,floor_largest,floor_middle))
    highb=np.maximum(np.minimum(b,np.where(odd,cap_middle,cap_largest)),np.where(odd,floor_middle,floor_largest))
    a[highactive]=higha[highactive];b[highactive]=highb[highactive]
    mixedsize=np.maximum(np.minimum(F(component_scale),cap_mixed),floor_mixed);a[lowactive]=mixedsize[lowactive];b[lowactive]=mixedsize[lowactive]
    if not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('Nonfinite output outside qualified ordinary domain')
    return dict(scaleA=a,scaleB=b,circleCoefficient=coefficient,lowerScale=lower,lowConfidence=low,lowActive=lowactive,highActive=highactive,scope='Finite ordinary curvature cap leaf, no source-class/excluded-face/area-balance handling or later sizing operations; branch coverage must come from declared native controls.')
