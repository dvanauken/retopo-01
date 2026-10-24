"""Reviewed30d6e0 guard: ordered/unordered two-stage normalization and edge tests.

EXP0344 qualifies exceptional direct inputs; this does not establish whole-app
acceptance of degenerate or nonfinite geometry. IEEE warnings may be silenced
by a caller with numpy.errstate; values are retained rather than sanitized.
"""
import numpy as np
from recovered_diagonal_lines import line_segment
F=np.float32


def guard(points,begin,end):
    points=F(points);delta=F(points[end]-points[begin]);square=F(F(delta[1]*delta[1]+delta[0]*delta[0])+delta[2]*delta[2]);length=np.sqrt(np.float64(square))
    direction=delta.copy()
    if np.isnan(length) or length<=-1e-28 or length>=1e-28:direction=F(direction.astype(np.float64)*(np.float64(1)/length))
    size=F(np.sqrt(F(F(direction[1]*direction[1]+direction[0]*direction[0])+direction[2]*direction[2])));ray_direction=np.zeros(3,dtype="<f4")
    if np.isnan(size) or size<=F(-1e-14) or size>=F(1e-14):ray_direction=F(direction*F(F(1)/size))
    ray=np.r_[points[begin],ray_direction].astype("<f4");cost=F(length);trace=[]
    for a in range(len(points)):
        b=(a+1)%len(points)
        if a in [begin,end] or b in [begin,end]:continue
        distance,s,t,branch=line_segment(ray,np.r_[points[a],points[b]].astype("<f4"));reject=F(.0001)<t<F(.9999) and float(distance)<float(cost)*.4 and float(F(-cost))*.05<float(s)<float(cost)*1.05;trace.append(dict(edge=[a,b],distance=float(distance),rayParameter=float(s),segmentFraction=float(t),branch=branch,rejected=bool(reject)))
        if reject:return True,cost,trace
    return False,cost,trace

