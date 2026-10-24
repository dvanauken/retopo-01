"""Multiple-mode2 source composition fork; native qualification is separate.
Original mesh/guide with explicit cut/seed/k inputs through initial UV solve."""
import numpy as np
from scipy import sparse
from recovered_cholmod_reference_backend import solve_sparse as spsolve
from recovered_symmetric_weighted_normal import assemble
from recovered_torus_parameter_constraints import prepare as constraints
from recovered_integer_substitution import substitute
from recovered_torus_parameter_equations import equations
from verify_initial_parameter_weights import initial_weights


def csr(rows,columns):
    rr=[];cc=[];vv=[]
    for i,row in enumerate(rows):
        for c,v in row:rr.append(i);cc.append(c);vv.append(v)
    return sparse.csr_matrix((vv,(rr,cc)),shape=(len(rows),columns))


def prepare(source,faces,target,drawn,cut,seeds,weight_control,guide_mode):
    if type(guide_mode) is not int or guide_mode not in (1,2):raise NotImplementedError('Only explicit homogeneous active guide modes1/2')
    own=constraints(source,faces,target,drawn,cut,seeds,guide_mode);g=own['geometry'];uv=own['parameterFans']['triangles'];f=own['frames'];chart=own['chart'];rows=[]
    for face in range(len(g['faces'])):
        order=(np.arange(3)+int(f['permutation'][face]))%3;p=g['positions'][g['faces'][face,order]];ids=uv[face,order];coeff=equations(p,f['basisA'][face],f['basisB'][face],f['localLength'][face],chart['directionA'][face],chart['directionB'][face],f['scaleA'][face],f['scaleB'][face])
        for axis,values in enumerate(coeff):rows.append([[2*int(v)+int(axis>=2),float(c)] for v,c in zip(ids,values) if c!=0])
    count=len(own['parameterConstraints']['mapping']);original=csr(rows,count);weights,targets=initial_weights(g['positions'],g['faces'],f['permutation'],weight_control);deps=own['parameterConstraints']['dependencies'];mapping=own['parameterConstraints']['mapping'];reduced=substitute(rows,deps,mapping,[0,-1,-1,-1,-1]);inverse=[i for i in range(count) if mapping[i]==-1];forward={v:i for i,v in enumerate(inverse)};reduced=[[[forward[c],v] for c,v in row] for row in reduced];A=csr(reduced,len(inverse));H,rhs=assemble(A,weights,targets);solution=spsolve(H,rhs)
    own['initialParameter']=dict(originalMatrix=original,reducedMatrix=A,normalMatrix=H,rhs=rhs,solution=solution,weights=weights,targets=targets,inverse=np.asarray(inverse,dtype='<i4'))
    return own
