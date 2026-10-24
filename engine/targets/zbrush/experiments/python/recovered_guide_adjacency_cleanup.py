"""1c88d0 ordinary closed mode2 guide adjacency cleanup, before field production.

24c510 default midpoint inputs and24a900 triangle commit;263480 is admitted
only when every new-point incident angle is safely inside its no-candidate
limits, or the independently computed area gate admits no face. Attributes/symmetry/boundaries/all-marked faces/moving repair are guarded.
"""
from collections import Counter
import math
import numpy as np
from recovered_mesh_topology import build
from recovered_conditioning_measures import angle
from recovered_cleanup_area_gate import measure as area_gate
F=np.float32
LOWER=0.026179938779914945
UPPER=3.0543261909900767
GUARD_MARGIN=1e-4

def square(x):return F(F(F(x[0]*x[0])+F(x[1]*x[1]))+F(x[2]*x[2]))

def prepare(positions,triangles,guide_pairs):
    p=np.asarray(positions,dtype='<f4');tri=np.asarray(triangles,dtype='<i4');top=build(len(p),tri)
    if tri.ndim!=2 or tri.shape[1]!=3 or np.any(np.diff(top['edgeCornerOffsets'])!=2):raise NotImplementedError('Closed ordinary triangle geometry without external attributes/symmetry/boundaries only')
    marked_vertices=np.zeros(len(p),bool);marked_edges=np.zeros(len(top['edges']),bool);lookup={tuple(sorted(map(int,e))):i for i,e in enumerate(top['edges'])}
    for pairs in guide_pairs:
        pairs=np.asarray(pairs)
        if pairs.ndim!=2 or pairs.shape[1]!=2 or np.any(pairs[:,0]!=1) or np.any(pairs[:,1]<0) or np.any(pairs[:,1]>=len(p)):raise NotImplementedError('Ordinary existing-vertex mode1/2 primary pairs only')
        for first,last in zip(pairs[:-1,1],pairs[1:,1]):
            first,last=int(first),int(last);marked_vertices[[first,last]]=True
            edge=lookup.get(tuple(sorted((first,last))))
            if edge is not None:marked_edges[edge]=True
    fe=top['faceEdges'].reshape(-1,3)
    if np.any(np.all(marked_edges[fe],axis=1)):raise NotImplementedError('All-three-marked-edge face subdivision policy remains unqualified')
    selected=np.flatnonzero(np.all(marked_vertices[top['edges']],axis=1)&~marked_edges).astype('<i4');mapping=np.full(len(top['edges']),-1,'<i4');mapping[selected]=len(p)+np.arange(len(selected));new=F(F(p[top['edges'][selected,0]]+p[top['edges'][selected,1]])*F(.5));out=np.concatenate([p,new]);rows=[];counts=Counter()
    for row,es in zip(tri,fe):
        v=list(map(int,row));m=list(map(int,mapping[es]));count=sum(x>=0 for x in m);counts[count]+=1
        if count==0:rows.append(v)
        elif count==3:rows.extend([[v[0],m[0],m[2]],[v[1],m[1],m[0]],[v[2],m[2],m[1]],[m[0],m[1],m[2]]])
        elif count==1:
            k=next(k for k in range(3) if m[k]>=0);rows.extend([[m[k],v[(k+1)%3],v[(k+2)%3]],[m[k],v[(k+2)%3],v[k]]])
        else:
            k=2 if m[0]<0 else 0 if m[1]<0 else 1;n=(k+1)%3;q=(k+2)%3;rows.append([v[k],m[k],m[q]]);d0=square(F(out[m[q]]-p[v[n]]));d1=square(F(out[m[k]]-p[v[q]]));rows.extend([[m[k],v[n],v[q]],[m[k],v[q],m[q]]] if d1<=d0 else [[m[q],m[k],v[n]],[m[q],v[n],v[q]]])
    result=np.asarray(rows,dtype='<i4');angles=[]
    for row in result[np.any(result>=len(p),axis=1)]:
        a,b,c=out[row];first=angle(F(b-a),F(c-a));second=angle(F(b-c),F(b-a));angles.extend([first,second,(math.pi-first)-second])
    gate=None
    if angles and not (min(angles)>LOWER+GUARD_MARGIN and max(angles)<UPPER-GUARD_MARGIN):
        gate=area_gate(out,result)
        if len(gate['eligibleFaces']):raise NotImplementedError('263480 new-point candidate motion or threshold-near angles remain unqualified')
    fixed=np.ones(len(out),bool);fixed[len(p):]=False
    return out,result,dict(selectedEdges=selected,edgeMidpointMap=mapping,markedVertices=marked_vertices,markedEdges=marked_edges,fixedVertices=fixed,newStarMinimum=min(angles) if angles else None,newStarMaximum=max(angles) if angles else None,relaxationCandidateCount=0,areaGate=gate,splitCounts=dict(counts),scope='Ordinary1c88d0 no external attributes/symmetry/boundary or all-marked face. Star angles safely inside263480 limits or no face satisfies its first cached-area gate; old vertices fixed and moving repair remains guarded.')
