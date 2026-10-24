"""1ec840 ordered mean and1ec3c0 repeated minimum, closed triangle subset.

Across quarter-odd seams the neighbor's two axes exchange roles. Constrained
guide corners permit only the supplied aligned axis to participate.
"""
import numpy as np
F=np.float32

def pass_once(size_a,size_b,topology,guide_edges,corner_axes,transitions,operation):
    a=np.asarray(size_a,dtype='<f4');b=np.asarray(size_b,dtype='<f4');fe=topology['faceEdges'].reshape(-1,3);off=topology['edgeCornerOffsets'];corn=topology['edgeCorners'];guide=np.asarray(guide_edges,bool);axes=np.asarray(corner_axes,bool).reshape(-1,3);turn=np.asarray(transitions,dtype='<i4')
    if operation not in ['mean','minimum']:raise ValueError('Explicit mean/minimum operation required')
    if len(a)!=len(fe) or b.shape!=a.shape or axes.shape!=fe.shape or len(guide)!=len(off)-1 or len(turn)!=len(guide):raise ValueError('Logical sizing/topology lengths disagree')
    if not np.all(np.diff(off)==2):raise NotImplementedError('Closed manifold triangle diffusion only')
    if not np.all(np.isfinite(a)&np.isfinite(b)&(a>0)&(b>0)):raise ValueError('Positive finite sizes required')
    x=np.empty_like(a);y=np.empty_like(b)
    for face in range(len(a)):
        va=a[face];vb=b[face];ca=F(1);cb=F(1)
        for k,edge in enumerate(fe[face]):
            pair=corn[off[edge]:off[edge+1]]//3;other=int(pair[1] if pair[0]==face else pair[0]);na=b[other] if turn[edge]&1 else a[other];nb=a[other] if turn[edge]&1 else b[other];allow_a=not guide[edge] or axes[face,k];allow_b=not guide[edge] or not axes[face,k]
            if operation=='mean':
                if allow_a:va=F(va+na);ca=F(ca+F(1))
                if allow_b:vb=F(vb+nb);cb=F(cb+F(1))
            else:
                if allow_a and na<va:va=na
                if allow_b and nb<vb:vb=nb
        x[face]=F(va/ca) if operation=='mean' else va;y[face]=F(vb/cb) if operation=='mean' else vb
    return x,y

def ratio_clamp(size_a,size_b,lower,maximum_ratio):
    a=np.asarray(size_a,dtype='<f4').copy();b=np.asarray(size_b,dtype='<f4').copy()
    if a.shape!=b.shape or not lower>0 or not maximum_ratio>=1:raise ValueError('Positive lower size and valid ratio required')
    #1f2cd0 identifies the smaller axis first, raises it, limits the larger
    #axis to the resulting smaller value times ratio, then raises the larger.
    for i in range(len(a)):
        if a[i]<=b[i]:small=max(a[i],F(lower));large=max(min(b[i],F(small*F(maximum_ratio))),F(lower));a[i]=small;b[i]=large
        else:small=max(b[i],F(lower));large=max(min(a[i],F(small*F(maximum_ratio))),F(lower));b[i]=small;a[i]=large
    return a,b
