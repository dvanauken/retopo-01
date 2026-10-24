"""Ordinary25b350 binned quality selection and disjoint triangle flips.

Input is closed triangle geometry and mode/iteration. Default source subset
requires no initial blocked/protected edges, attributes or excluded faces.
Caches, candidate order, decisions and output triangles are independently made.
"""
import numpy as np
from recovered_conditioning_measures import produce
from recovered_index_sort import sort_indices
from recovered_quality_edge_eligibility import evaluate
from recovered_disjoint_triangle_edge_flips import flip
F=np.float32
BIN_LIMIT=F(0.3490658402442932)
EDGE_LIMIT=F(0.01745329238474369)
SMALL_LIMIT=F(0.008726646192371845)
CONTINUE_LIMIT=0.017453292519943295

def produce_pass(positions,triangles,mode,iteration):
    p=np.asarray(positions,dtype='<f4');tri=np.asarray(triangles,dtype='<i4')
    if mode not in [0,1,2,3] or not isinstance(iteration,int) or iteration<0:raise ValueError('Ordinary quality mode and nonnegative iteration required')
    g=produce(p,tri);top=g['topology'];ne=len(top['edges']);blocked=np.zeros(ne,bool);small=np.any(g['corners'].reshape(-1,3)<SMALL_LIMIT,axis=1);limits=[F(F(F(i)*BIN_LIMIT)/F(3)) for i in range(4)];bins=[[] for _ in range(3)];values=[[] for _ in range(3)];minimum=F(np.finfo(F).max) if len(g['corners']) else F(-1)
    for corner,value in enumerate(g['corners']):
        if value<=limits[3]:
            bucket=0 if value<=limits[1] else 1 if value<=limits[2] else 2;bins[bucket].append(corner);values[bucket].append(value);minimum=min(minimum,value)
    calls=[];selected=[];orders=[];face_edges=top['faceEdges'].reshape(-1,3)
    def eligible(edge,threshold):
        begin,end=top['edgeCornerOffsets'][edge:edge+2];cs=top['edgeCorners'][begin:end]
        if len(cs)!=2:raise NotImplementedError('Closed ordinary two-triangle edge required')
        c0,c1=map(int,cs);f0,k0=divmod(c0,3);f1,k1=divmod(c1,3);ids=[tri[f0,k0],tri[f1,k1],tri[f0,(k0+2)%3],tri[f1,(k1+2)%3]];answer=evaluate(p[ids],g['normals'][[f0,f1]],small[[f0,f1]],g['edgeAngles'][edge],threshold);calls.append(dict(edge=edge,threshold=threshold,accepted=answer['accepted'],score=answer['score'],corners=cs.copy()));return answer
    for bucket in range(3):
        keys=np.asarray(values[bucket],'<f4');order=np.asarray(sort_indices(keys.tolist()),'<i4');orders.append(dict(corners=np.asarray(bins[bucket],'<i4'),values=keys,indices=order))
        for local in order:
            corner=bins[bucket][local];threshold=keys[local];face,k=divmod(corner,3);e0=int(face_edges[face,k]);e1=int(face_edges[face,(k+2)%3]);a=b=None
            if not blocked[e0] and (g['edgeAngles'][e0]<=EDGE_LIMIT or small[face]):a=eligible(e0,threshold)
            if not blocked[e1] and (g['edgeAngles'][e1]<=EDGE_LIMIT or small[face]):b=eligible(e1,threshold)
            if a is not None and a['accepted']:
                chosen=e1 if b is not None and b['accepted'] and a['score']<b['score'] else e0
            elif b is not None and b['accepted']:chosen=e1
            else:continue
            begin,end=top['edgeCornerOffsets'][chosen:chosen+2]
            for c in top['edgeCorners'][begin:end]:
                f,k=divmod(int(c),3);blocked[int(face_edges[f,(k+1)%3])]=True;blocked[int(face_edges[f,(k+2)%3])]=True
            blocked[chosen]=True;selected.append(chosen)
    selected=np.asarray(selected,'<i4');output,changes=flip(len(p),tri,selected);cont=bool(len(selected)>0 and (mode==0 and (float(minimum)<CONTINUE_LIMIT or iteration<4) or mode==3 and (float(minimum)<CONTINUE_LIMIT or iteration<1)))
    return dict(triangles=output,selectedEdges=selected,blocked=blocked,calls=calls,orders=orders,minimumCandidateAngle=minimum,continueQuality=cont,sourceMeasures=g,smallFaces=small,changes=changes,scope='Ordinary closed default no external/protected/excluded/attribute quality pass; not full quality/repair or source remesher.')
