"""Instruction-order UV interpolation, engine RVA0xeb5d0, finite determinant."""
import numpy as np


def position(q,uv,xyz):
    f=np.float32;a=f(uv[1]-uv[0]);b=f(uv[2]-uv[0]);c=f(q-uv[0]);det=float(b[1])*float(a[0])-float(b[0])*float(a[1])
    if det==0:raise ValueError('Degenerate UV interpolation requires caller fallback')
    inverse=1./det
    gamma=(inverse*float(a[0]))*float(c[1])-(inverse*float(a[1]))*float(c[0])
    beta=(inverse*float(b[1]))*float(c[0])-(inverse*float(b[0]))*float(c[1])
    return f(f(xyz[1]-xyz[0]).astype(float)*beta+xyz[0].astype(float)+f(xyz[2]-xyz[0]).astype(float)*gamma)
