"""Ordinary four-derivative continuous parameter objective and first reweight."""
import numpy as np
from scipy import sparse
from recovered_integer_substitution import substitute
from verify_parameter_rows import equations
from verify_initial_parameter_weights import initial_weights
from verify_parameter_reweight import gradients,smooth
F=np.float32

def assemble(data,k):
    g=data['component'];tri=data['tri'];uv=data['uv'];perm=np.fromfile(g/'triangle-permutation.u8','u1');length=np.fromfile(g/'local-length.f32','<f4');su=np.fromfile(g/'scale-a.f32','<f4');sv=np.fromfile(g/'scale-b.f32','<f4');rows=[]
    for face in range(len(tri)):
        order=(np.arange(3)+int(perm[face]))%3;p=data['positions'][tri[face,order]];ids=uv[face,order];coeff=equations(p,data['basisA'][face],data['basisB'][face],length[face],data['directionA'][face],data['directionB'][face],su[face],sv[face])
        for axis,values in enumerate(coeff):rows.append([[2*int(v)+int(axis>=2),float(c)] for v,c in zip(ids,values) if c!=0])
    count=2*(int(uv.max())+1);mapping=data['constraints']['mapping'];rows=substitute(rows,data['constraints']['dependencies'],mapping,[0,-1,-1,-1,-1]);inverse=[i for i in range(count) if mapping[i]<0];forward={v:i for i,v in enumerate(inverse)};rr=[];cc=[];vv=[]
    for i,row in enumerate(rows):
        for c,v in row:rr.append(i);cc.append(forward[c]);vv.append(v)
    A=sparse.csr_matrix((vv,(rr,cc)),shape=(len(rows),len(inverse)));weights,targets=initial_weights(data['positions'],tri,perm,k)
    return A,weights,targets,inverse

def normal_system(A,weights,targets):
    H=(A.T@A.multiply(weights[:,None])).tocsr();H.data[abs(H.data)<1e-16]=0.;H.eliminate_zeros()
    return H,np.asarray(A.T@(weights*targets)).ravel()

def first_reweight(data,uv,normal,scales,iterations):
    tri=data['tri'];uvtri=data['uv'];g=gradients(data['positions'],tri,normal,uv,uvtri);initial=np.ones((len(tri),4));q0,q1,q2=[uv[uvtri[:,i]] for i in range(3)];det=F(F(F(q1[:,0]-q0[:,0])*F(q2[:,1]-q0[:,1]))-F(F(q1[:,1]-q0[:,1])*F(q2[:,0]-q0[:,0])));initial[det<0]+=5
    for j,gradient in enumerate(g):
        inverse=F(F(1)/np.sqrt(F(F(gradient[:,1]*gradient[:,1]+gradient[:,0]*gradient[:,0])+gradient[:,2]*gradient[:,2]),dtype='f4'));scale=scales[j];lo=F(scale*F(1.8));hi=F(scale*F(4));selected=inverse>lo;delta=np.full(len(tri),F(3));ramp=selected&(inverse<=hi);delta[ramp]=F(F(F(3)/F(hi[ramp]-lo[ramp]))*F(inverse[ramp]-lo[ramp]));initial[selected,j*2]+=delta[selected].astype('f8')
    initial=np.minimum(initial,10);k=data['kwargs'];tags=np.zeros(len(k['edges']),dtype=np.uint8)
    for edge,mode in data['groups']['edgeModes'].items():tags[k['sourceEdgeMap'][edge]]=mode
    return smooth(initial,k['faceEdges'],k['edgeOffsets'],k['edgeCorners'],tags,np.asarray(data['groups']['cornerAxes']),k['transitions'],iterations),initial
