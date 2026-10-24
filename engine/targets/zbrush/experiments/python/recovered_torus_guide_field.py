"""Original-input active mode2 multiple-curve field/angular candidate.

Source embedding is pooled in curve order. Influence seeds retain curve/sample
identity with first-zero seed ownership; initial incident-edge directions use
ordered overwrite. Native qualification is separate and ordinary guards remain.
"""
from collections import deque
import numpy as np
from recovered_torus_guided_source import prepare as source_prepare
from recovered_guide_adjacency_cleanup import prepare as guide_cleanup
from recovered_source_edge_tensors import prepare as edge_field
from recovered_radius_field import guide_marks,integrate
from recovered_default_field_radii import prepare as sizing
from recovered_field_candidates import prepare as candidates
from recovered_guide_field_constraints import prepare as constraints
from recovered_guide_influence import distance
from recovered_field_defaults import prepare as defaults
from recovered_field_candidate_gate import prepare as gate
from recovered_window_field_selection import prepare as select
from recovered_torus_angular_fallback import solve
F=np.float32

def prepare(source,faces,target,drawn_curves,guide_mode=2):
    if type(guide_mode) is not int or guide_mode not in (1,2):raise NotImplementedError("Explicit homogeneous active guide modes1/2 required")
    g=source_prepare(source,faces,target,drawn_curves);xyz,tri,cleanup=guide_cleanup(g['positions'],g['faces'],[c['embeddedPairs'] for c in g['curves']]);g=dict(g,positions=xyz,faces=tri,guideCleanup=cleanup);curves=g['curves'];ef=edge_field(xyz,tri,cached_lengths=True);top=ef['topology'];settings=sizing(xyz,tri,target);marks=np.zeros(len(xyz),bool);scales=[];lengths=[];directions=np.zeros((len(tri),3),dtype='<f4');flags=np.zeros(len(tri),dtype='u1');selected=[]
    for curve in curves:
        marks|=guide_marks(len(xyz),top['edges'],ef['angles'],curve['embeddedPairs'],mode=guide_mode,active=True);length=F(0)
        for a,b in zip(curve['embeddedPoints'],curve['embeddedPoints'][1:]):length=F(distance(a,b)+length)
        scales.append(F(min(F(length*F(.25)),F(settings['maximum']))*F(.75)));lengths.append(length);local=constraints(dict(positions=xyz,faces=tri,embeddedPairs=curve['embeddedPairs']),top);active=local['flags']!=0;directions[active]=local['directions'][active];flags[active]=local['flags'][active];selected.extend(local['selectedEdges'].tolist())
    if any(not scale>0 for scale in scales):raise NotImplementedError('Positive active mode2 scales required')
    values=np.full(len(xyz),np.finfo('f4').max,dtype='<f4');association=np.full(len(xyz),-1,dtype='<i4');seed_curve=[];seed_sample=[];queue=deque();queued=np.zeros(len(xyz),bool)
    for curve_index,curve in enumerate(curves):
        for sample,(_,vertex) in enumerate(curve['embeddedPairs']):
            vertex=int(vertex)
            if values[vertex]==0:continue
            values[vertex]=0;association[vertex]=len(seed_sample);seed_curve.append(curve_index);seed_sample.append(sample);queue.append(vertex);queued[vertex]=True
    offsets=top['vertexEdgeOffsets'];incident=top['vertexEdges'];edges=top['edges'];pops=updates=0
    while queue:
        current=queue.popleft();queued[current]=False;pops+=1;owner=association[current];ci=seed_curve[owner];sample=seed_sample[owner]
        for edge in incident[offsets[current]:offsets[current+1]]:
            a,b=edges[edge];neighbor=int(b if a==current else a);candidate=distance(xyz[neighbor],curves[ci]['embeddedPoints'][sample]);floor=F(values[current]*F(1.005))
            if candidate<=floor:candidate=floor
            if candidate<values[neighbor] and candidate<F(scales[ci]+scales[ci]):
                values[neighbor]=candidate;association[neighbor]=owner;updates+=1
                if not queued[neighbor]:queue.append(neighbor);queued[neighbor]=True
    normalized=np.full(len(tri),np.finfo('f4').max,dtype='<f4')
    for face,(a,b,c) in enumerate(tri):
        if association[a]>=0 and association[b]>=0 and association[c]>=0:normalized[face]=F(F(F(F(values[b]/scales[seed_curve[association[b]]])+F(values[a]/scales[seed_curve[association[a]]]))+F(values[c]/scales[seed_curve[association[c]]]))*F(1/3))
    tensors=[];counts=[]
    for radius in settings['radii']:
        x,n=integrate(xyz,edges,offsets,incident,ef['tensors'],ef['angles'],marks,F(radius));tensors.append(x);counts.append(n)
    integrated=dict(tensors=np.asarray(tensors,dtype='<f8'),counts=np.asarray(counts,dtype='<i4'),marks=marks);direction,middle,largest=candidates(tri,integrated['tensors'],marks);controls=defaults();field=dict(geometry=g,edgeField=ef,settings=settings,integrated=integrated,directions=direction,middle=middle,largest=largest,radii=settings['radii'],controls=controls,influence=dict(normalized=normalized,scales=np.asarray(scales,dtype='<f4'),lengths=np.asarray(lengths,dtype='<f4'),vertexDistance=values,association=association,seedCurve=np.asarray(seed_curve,dtype='<i4'),seedSample=np.asarray(seed_sample,dtype='<i4'),pops=pops,updates=updates),constraints=dict(directions=directions,flags=flags,weights=np.ones(len(tri),dtype='<f4'),selectedEdges=np.asarray(sorted(set(selected)),dtype='<i4')));field['candidateGate']=gate(field,field['influence'],controls['anisotropy'],controls['curvatureFactor'],controls['normalDotLimit']);selected=select(field,unordered_selection=True,native_arithmetic=True);field['selection']=selected;field['angular']=solve(xyz,tri,ef['normals'],top['faceEdges'].reshape(-1,3),top['edgeCornerOffsets'],top['edgeCorners'],selected['directions'],selected['weights'])
    return field
