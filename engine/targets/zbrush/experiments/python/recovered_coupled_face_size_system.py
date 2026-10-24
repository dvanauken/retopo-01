"""1efb00 ordinary two-axis sizing least squares, no excluded/source classes.

Anchor weights use selected-field flag bit1 and normalized float32 twice-area.
Guide constraints omit the unaligned smoothing residual. Odd-quarter exchange
couples opposite neighbor axes; nondefault objective-weight modes stay outside
this ordinary implementation. Native qualification remains separately scoped.
"""
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve
from verify_initial_parameter_weights import initial_weights
F=np.float32

def prepare(xyz,tri,topology,flags,scale_a,scale_b,guide_edges,corner_axes,transitions,component_scale,area):
    n=len(tri);a=np.asarray(scale_a,dtype='<f4');b=np.asarray(scale_b,dtype='<f4');flags=np.asarray(flags,dtype='u1');guide=np.asarray(guide_edges,bool);axes=np.asarray(corner_axes,bool).reshape(-1,3);turns=np.asarray(transitions,dtype='<i4');off=topology['edgeCornerOffsets'];corn=topology['edgeCorners']
    if a.shape!=(n,) or b.shape!=(n,) or flags.shape!=(n,) or axes.shape!=(n,3):raise ValueError('Face-array lengths disagree')
    if np.any(np.diff(off)!=2):raise NotImplementedError('Closed manifold objective only')
    if not area>0 or not component_scale>0:raise ValueError('Positive source area/component size required')
    p=np.asarray(xyz,dtype='<f8')[tri];u=p[:,1]-p[:,0];v=p[:,2]-p[:,0];cross=np.cross(u,v);D=np.sqrt((cross[:,0]*cross[:,0]+cross[:,1]*cross[:,1])+cross[:,2]*cross[:,2]).astype('<f4');normalization=F(F(F(n)/F(F(area)*F(2)))*D).astype('<f8');base=F(component_scale);low=F(base/F(4));inverse=F(F(1)/F(base-low));active=(flags&2)!=0;wa=np.ones(n);wb=np.ones(n)
    for values,weights in [(a,wa),(b,wb)]:
        ratio=np.clip(F(F(base-values)*inverse),F(0),F(1));strength=F(F(F(100)*ratio+F(1))*F(10));weights[active]=strength[active].astype(float);weights*=normalization
    rows=[];targets=[];weights=[]
    for face in range(n):
        rows.extend([[[2*face,1.]],[[2*face+1,1.]]]);targets.extend([float(a[face]),float(b[face])]);weights.extend([float(wa[face]),float(wb[face])])
    for edge in range(len(off)-1):
        cs=corn[off[edge]:off[edge+1]];first,second=map(int,cs//3)
        for axis,anchor in [(0,wa),(1,wb)]:
            neighbor_axis=axis^(int(turns[edge])&1);neighbor_anchor=wa if neighbor_axis==0 else wb
            if guide[edge] and bool(axes.ravel()[cs[0]])!=(axis==0):continue
            rows.append([[2*first+axis,1.],[2*second+neighbor_axis,-1.]]);targets.append(0.);weights.append(max(20.,(float(anchor[first])+float(neighbor_anchor[second]))*.5*6.))
    rr=[];cc=[];vv=[]
    for i,row in enumerate(rows):
        for col,value in row:rr.append(i);cc.append(col);vv.append(value)
    A=sparse.csr_matrix((vv,(rr,cc)),shape=(len(rows),2*n));weights=np.asarray(weights,dtype='<f8');targets=np.asarray(targets,dtype='<f8');H=(A.T@A.multiply(weights[:,None])).tocsr();H.sort_indices();rhs=np.asarray(A.T@(weights*targets)).ravel();solution=np.asarray(spsolve(H,rhs),dtype='<f8')
    if not np.all(np.isfinite(solution)) or not np.all(solution>0):raise ValueError('Nonpositive/nonfinite ordinary size solution')
    stored=solution.astype('<f4').reshape(-1,2)
    return dict(rows=rows,weights=weights,targets=targets,matrix=A,normalMatrix=H,rhs=rhs,solution=solution,scaleA=stored[:,0].copy(),scaleB=stored[:,1].copy(),anchorWeightsA=wa,anchorWeightsB=wb,normalization=normalization,active=active)
