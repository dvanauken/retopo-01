"""Bounded geometric candidate policy from engine0x28fe70; checkers qualify scope."""
import numpy as np
from recovered_index_sort import sort_indices
from verify_integer_chain_integral import integral
from recovered_cyclic_cut_path_enumeration import enumerate_paths
from recovered_paired_cut_sides import paired_sides
F=np.float32

def policy(first_guide,second_guide,delta,cross):
    d=F(abs(delta));c=F(abs(cross));target=float(delta);weight=F(1);hard=soft=False
    if first_guide and second_guide:
        if d<F(1.35):hard=bool(F(d+d)>c)
        elif d<F(5):soft=bool(c<d)
    elif not first_guide and not second_guide:
        weight=F(.01)
        if float(c)*.2<=float(d):
            if d<c:weight=F(F(F(F(c/d)-F(.2))*np.array([0x3de66667],dtype=np.uint32).view(np.float32)[0])+F(.01))
            else:
                weight=F(100)
                if d>=F(1):
                    if d<F(2.5):weight=F(F(100)-F(F(d-F(1))*F(60)))
                    else:
                        weight=F(1)
                        if d<F(5):weight=F(F(10)-F(F(d-F(2.5))*F(3.6)))
    elif c<F(d+d):
        soft=bool(d<F(1.35) or (d<F(4.5) and c<d))
    if hard or (soft and d<F(1.35)):target=1. if delta>=0 else -1.
    return target,float(weight),hard,soft

def parent_path(vertex,parent,edges):
    path=[int(vertex)];seen=set(path)
    while parent[vertex]>=0:
        a,b=map(int,edges[parent[vertex]]);vertex=b if a==vertex else a
        if vertex in seen:raise ValueError('Cyclic predecessor path')
        path.append(vertex);seen.add(vertex)
    return path

def construct(data,common,geometry,uv,edges,axes):
    read=lambda p,n,d='<i4',w=None:np.fromfile(p/n,d).reshape(-1,w) if w else np.fromfile(p/n,d)
    mapping=read(common,'parameter-to-source.i32');vo=read(common,'parameter-vertex-edge-offset.i32');ve=read(common,'parameter-vertex-edge-list.i32');eo=read(common,'parameter-edge-face-offset.i32');ec=read(common,'parameter-edge-face-corners.i32');scale=read(geometry,'scale-a.f32','<f4')
    return construct_arrays(data,uv,edges,axes,mapping,vo,ve,eo,ec,scale)


def construct_arrays(data,uv,edges,axes,mapping,vo,ve,eo,ec,scale):
    """Same qualified policy with explicit computed arrays and no file access."""
    ngroups=len(data['groups']['groups']);constant=len(data['constraints']['mapping']);pins={r['dependent'] for r in data['constraints']['gauge']};items=[]
    for axis in axes:
        for i,row in enumerate(axis['records']):items.append((axis,i,row))
    gaps=[axis['gaps'][i] for axis,i,row in items];order=sort_indices(gaps);rows=[];targets=[];weights=[];constraints=[];constraintTargets=[];paths=[];decisions=[]
    for index in order:
        axis,i,record=items[index];a,b=axis['pairs'][i];channel=axis['axis'];delta=F(uv[b//2,channel]-uv[a//2,channel]);cross=F(uv[b//2,1-channel]-uv[a//2,1-channel]);target,weight,hard,soft=policy(record['regions'][0]<ngroups,record['regions'][1]<ngroups,delta,cross)
        if hard or soft:
            left,right=map(int,edges[record['edge']]);lp=parent_path(left,axis['front']['parent'],edges);rp=parent_path(right,axis['front']['parent'],edges);path=list(reversed(lp))+rp if lp[-1]==a//2 else list(reversed(rp))+lp
            value=integral(path,channel,data['positions'],mapping,edges,vo,ve,eo,ec,data['basisA'],data['basisB'],data['directionA'],data['directionB'],scale)
            if F(value*delta)<0:target=-target
            paths.append(dict(candidate=index,axis=channel,path=path,integral=float(value)))
        row=[[b,1.],[a,-1.]];row=[term for term in row if term[0] not in pins]
        if hard:
            if len(row)>1:constraints.append(sorted(row));constraintTargets.append(target)
        else:
            rows.append(row);weights.append(weight);targets.append(target)
            if soft:
                auxiliary=sorted([[c,v*(1 if target>0 else -1)] for c,v in row]);auxiliary.append([constant+index+1,-1.])
                if len(auxiliary)>1:constraints.append(auxiliary);constraintTargets.append(0.)
        decisions.append(dict(candidate=index,hard=hard,soft=soft,target=target,weight=weight))
    return dict(rows=rows,weights=weights,targets=targets,constraints=constraints,constraintTargets=constraintTargets,paths=paths,decisions=decisions,order=order)

def optional_seam_constraints(data,uv):
    """0x293b10 ordinary empty special-edge mask branch, zero RHS rows."""
    k=data['kwargs'];paths,_=enumerate_paths(k['selected'],k['edges'],k['vertexOffsets'],k['vertexEdges'],k['seeds'],[]);rows=[];selected=[]
    if data['constraints'].get('periodIds'):
        if len(data['constraints']['periodIds'])!=len(paths):raise NotImplementedError('Mixed augmented optional seam mask requires separate qualification')
        return [],[]  #293b10 skips every path whose first edge is augmented (+588).
    for index,(edge_path,vertex_path) in enumerate(paths):
        a,b,q,_=paired_sides(edge_path,vertex_path,k['tri'],k['uv'],k['faceEdges'],k['edgeOffsets'],k['edgeCorners'],k['transitions'])
        if q%4 or not a:continue
        delta=F(uv[b[0]]-uv[a[0]]);dx,dy=map(abs,delta);length=F(uv[a[-1]]-uv[a[0]]);axis=int(dy<=dx);along=abs(length[axis]);lo=min(dx,dy);hi=max(dx,dy);accept=False
        if lo>=F(1):
            if lo<F(2) and hi>F(14) and along>F(10):accept=float(F(lo/F(F(hi*F(.75))+F(along*F(.25)))))<.08
        elif (hi>F(4) and along>F(6)) or (hi>F(6) and along>F(4)):accept=True
        elif hi>F(2) and along>F(2):accept=float(F(lo/F(F(hi*F(.75))+F(along*F(.25)))))<.02
        if accept:
            rows.append([[2*int(a[0])+axis,1.],[2*int(b[0])+axis,-1.]])
            selected.append(dict(path=index,axis=axis,minimum=float(lo),maximum=float(hi),along=float(along)))
    return rows,selected
