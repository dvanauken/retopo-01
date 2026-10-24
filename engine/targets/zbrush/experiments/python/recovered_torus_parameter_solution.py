"""Multiple-mode2 source composition fork; native qualification is separate.
Original default guided input and cuts/seeds through full ordinary UV solve."""
import numpy as np
from scipy import sparse
from recovered_cholmod_reference_backend import solve_sparse as spsolve
from recovered_torus_integer_geometry import prepare as geometry
from recovered_integer_substitution import substitute
from recovered_unit_constraint_elimination import eliminate_unit
from recovered_integer_transfer import compress,transfer
from recovered_integer_system import solve
from verify_coordinate_reconstruction import reconstruct
from recovered_period_integer_rows import append as period_rows


def prepare(source,faces,target,drawn,cut,seeds,guide_mode):
    if type(guide_mode) is not int or guide_mode not in (1,2):raise NotImplementedError('Only explicit homogeneous active guide modes1/2')
    own=geometry(source,faces,target,drawn,cut,seeds,guide_mode);ig=own['integerGeometry'];data=ig['data'];generated=ig['generated'];constant=len(own['parameterConstraints']['mapping']);mainDeps=data['constraints']['dependencies'];mainMap=data['constraints']['mapping'];outerInverse=own['initialParameter']['inverse'];outerMap=np.full(constant,-1,dtype=int);outerMap[outerInverse]=np.arange(len(outerInverse));incoming=own['continuousParameter']['solution'];constraints=generated['constraints']+ig['extra'];targets=generated['constraintTargets']+[0.]*len(ig['extra']);dimension=constant+1+len(generated['order']);originalRows,originalWeights,originalTargets=period_rows(generated['rows'],generated['weights'],generated['targets'],own['parameterConstraints']['periodIds'],outerMap,incoming);rows=substitute(originalRows,mainDeps,mainMap,[0,-1,-1,-1,-1]);constraintRows=substitute(constraints,mainDeps,mainMap,[0,-1,-1,-1,-1]);augmented=[sorted(row+([[constant,t]] if t else [])) for row,t in zip(constraintRows,targets) if len(row)>1];dependencies=eliminate_unit(augmented,constant);depMap=[-1]*dimension
    for i,d in enumerate(dependencies):depMap[d['dependent']]=i
    rows=substitute(rows,dependencies,depMap,[0,-1,-1,-1,-1]);weights=list(originalWeights);rhs=list(originalTargets)
    for i,row in enumerate(rows):
        for c,v in row:
            if c==constant:rhs[i]+=v
    rows=[[term for term in row if term[0]!=constant] for row in rows];rows,forward,inverse=compress(rows,dimension)
    for original,reduced in enumerate(forward):
        if reduced<0:continue
        rows.append([[reduced,1.]]);weights.append(9.999999747378752e-05);rhs.append(float(incoming[outerMap[original]]) if original<constant and outerMap[original]>=0 else (0. if original<constant else 1.))
    flags=data['constraints']['guide']['flags'];outerIndices=[i for i,original in enumerate(outerInverse) if flags[original]!=0];integerIndices=[forward[outerInverse[v]] for v in outerIndices if forward[outerInverse[v]]>=0]+[forward[i] for i in range(constant,dimension) if forward[i]>=0];rr=[];cc=[];vv=[]
    for i,row in enumerate(rows):
        for c,v in row:rr.append(i);cc.append(c);vv.append(v)
    A=sparse.csr_matrix((vv,(rr,cc)),shape=(len(rows),len(inverse)));replay=solve(A,np.asarray(weights),np.asarray(rhs),integerIndices,[],inverse,constant+1,.5);positions,values=transfer(replay['solution'],outerIndices,outerInverse,forward,dependencies,depMap,constant,[]);H=own['continuousParameter']['normalMatrix'];outerRhs=own['continuousParameter']['rhs'];fixed=[outerIndices[i] for i in positions];mask=np.zeros(len(outerInverse),bool);mask[fixed]=True;M=sparse.diags((~mask).astype(float));HF=(M@H@M+sparse.diags(mask.astype(float))).tocsr();fixedRhs=outerRhs-np.asarray(H[:,fixed]@np.asarray(values)).ravel();fixedRhs[fixed]=values;final=spsolve(HF,fixedRhs);uv=reconstruct(final,outerInverse,mainDeps,constant)[:2*len(own['parameterFans']['sourceIds'])].reshape(-1,2)
    own['parameterSolution']=dict(uv=uv,solution=final,nestedSolution=replay['solution'],fixPositions=np.asarray(positions,dtype='<i4'),fixValues=np.asarray(values,dtype='<f8'),rows=rows,weights=np.asarray(weights),targets=np.asarray(rhs),augmented=augmented,dependencies=dependencies,batches=replay['batches'],outerIndices=outerIndices,nestedMatrix=A)
    return own
