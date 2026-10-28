"""Fit existing path vertices to ordered curve parameters with bounded spacing.

Targets minimize squared parameter displacement subject to monotonicity. This
replaces shape-only point deletion, which can relocate a vertex far along a
curve even when it already lies close to that curve. It does not choose topology.
"""
import numpy as np

def isotonic(values,weights):
    blocks=[]
    for i,(value,weight) in enumerate(zip(values,weights)):
        blocks.append([i,i+1,float(weight),float(value*weight)])
        while len(blocks)>1 and blocks[-2][3]/blocks[-2][2]>blocks[-1][3]/blocks[-1][2]:
            b=blocks.pop();a=blocks.pop()
            blocks.append([a[0],b[1],a[2]+b[2],a[3]+b[3]])
    result=np.empty(len(values))
    for begin,end,weight,total in blocks:result[begin:end]=total/weight
    return result

def targets(points,curve,closed,min_spacing_fraction=.2):
    points=np.asarray(points,dtype=float);curve=np.asarray(curve,dtype=float)
    d=np.diff(curve,axis=0);lengths=np.linalg.norm(d,axis=1)
    if np.any(lengths<=0) or len(points)<2:
        raise ValueError('Distinct curve segments and at least two path vertices required')
    arc=np.r_[0,np.cumsum(lengths)];L=arc[-1]
    delta=points[:,None]-curve[:-1]
    t=np.clip((delta*d).sum(axis=2)/(lengths*lengths),0,1)
    residual=delta-t[:,:,None]*d
    nearest=(residual*residual).sum(axis=2).argmin(axis=1)
    params=arc[nearest]+t[np.arange(len(points)),nearest]*lengths[nearest]
    if closed:
        phase=params[0]
        expected=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
        expected=expected/(expected[-1]+np.linalg.norm(points[-1]-points[0]))*L
        params-=phase
        params+=np.round((expected-params)/L)*L
        desired=np.r_[params,L]
    else:
        phase=0.
        desired=params.copy();desired[0]=0.;desired[-1]=L
    step=L/(len(desired)-1)*min_spacing_fraction
    indices=np.arange(len(desired))
    reduced=desired-step*indices
    weights=np.ones(len(desired));weights[[0,-1]]=1e12
    reduced[0]=0.;reduced[-1]=L-step*(len(desired)-1)
    ordered=np.clip(isotonic(reduced,weights),0,reduced[-1])+step*indices
    ordered[0]=0.;ordered[-1]=L
    if closed:ordered=(ordered[:-1]+phase)%L
    return np.array([np.interp(ordered,arc,curve[:,i]) for i in range(3)]).T
