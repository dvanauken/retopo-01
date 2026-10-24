"""Explicit engineering policies for a usable hard-surface clone reference.

All-sharp conditioning locks match native1020's bounded cuboid prefix. Robust
parallel skipping and general graph fallback are choices, not recovered native
stale-output/attribute policies. The qualified core is restored after each call.
"""
from collections import Counter,defaultdict
from contextlib import contextmanager
import math
import numpy as np

def sharp_edges(vertices,triangles,angle_degrees=30):
    v=np.asarray(vertices,dtype=float);f=np.asarray(triangles,dtype=int)
    normals=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
    lengths=np.linalg.norm(normals,axis=1)
    if np.any(lengths==0):raise ValueError('Zero-area source triangle')
    normals/=lengths[:,None];incident=defaultdict(list)
    for i,row in enumerate(f):
        for a,b in zip(row,np.roll(row,-1)):incident[tuple(sorted((int(a),int(b))))].append(i)
    return [edge for edge,faces in incident.items() if len(faces)==2 and
            float(normals[faces[0]]@normals[faces[1]])<=math.cos(math.radians(angle_degrees))]

def paths_from_edges(edges):
    """Deterministic complete graph decomposition, with junctions as endpoints."""
    edges=[tuple(map(int,e)) for e in edges];adj=defaultdict(list)
    for i,(a,b) in enumerate(edges):adj[a].append(i);adj[b].append(i)
    remaining=set(range(len(edges)));paths=[]
    while remaining:
        start=next((v for v in sorted(adj,reverse=True) if len(adj[v])!=2 and any(e in remaining for e in adj[v])),edges[min(remaining)][0])
        v=start;path=[v];es=[]
        while True:
            edge=next((e for e in adj[v] if e in remaining),None)
            if edge is None:break
            remaining.remove(edge);es.append(edge);a,b=edges[edge];v=b if a==v else a;path.append(v)
            if v==start or len(adj[v])!=2:break
        if not es:raise RuntimeError('Constraint graph made no progress')
        paths.append((es,path))
    return paths

def feature_curves(vertices,triangles,angle_degrees=30):
    v=np.asarray(vertices,dtype=float);edges=sharp_edges(v,triangles,angle_degrees);curves=[]
    for _,path in paths_from_edges(edges):
        # Retain all source breakpoints. Densify short paths with dyadic samples
        # so projection/walking sees more than a single long chord.
        n=1
        while n*max(1,len(path)-1)<16:n*=2
        points=[]
        for a,b in zip(path[:-1],path[1:]):points.extend(np.linspace(v[a],v[b],n+1)[:-1])
        points.append(v[path[-1]]);curves.append(np.asarray(points))
    return curves,edges

def append_unique(existing,automatic):
    curves=list(existing);seen=set()
    def keys(points):
        a=np.asarray(points,dtype='<f4');return a.tobytes(),a[::-1].tobytes()
    for curve in curves:seen.update(keys(curve))
    count=0
    for curve in automatic:
        forward,reverse=keys(curve)
        if forward not in seen:
            curves.append(curve);seen.update([forward,reverse]);count+=1
    return curves,count

@contextmanager
def override_core(angle_degrees=30):
    import recovered_torus_guided_source as guided
    import recovered_torus_cap_finished_mesh as finish
    import recovered_attached_surface_move as movement
    import recovered_closed_vertex_source_cut as cutting
    import recovered_long_cycle_cap_pre_relaxation as caps
    from mesh_ops import cut_existing_edges,cap_face_fans
    from recovered_quality_conditioned_densification import densify
    from recovered_conditioning_measures import produce
    from recovered_locked_moderate_conditioning import smooth_prepared
    from recovered_embedded_guide_edges import collect
    from recovered_junction_network_path_enumeration import enumerate_stack
    F=np.float32
    diagnostics=dict(parallelIntersectionsSkipped=0,generalGraphFallbacks=0,
                     sharpConditioningVertexCounts=[],collinearGuideSamplesRemoved=0,
                     guideSimplificationRelativeTolerance=1e-7,conformingEdgeInsertionFallbacks=0,
                     faceFanCapFallbacks=[],nativeGeneralPolicyRecovered=False)
    old_prepare=guided.source_prepare;old_tags=finish.tags;old_line=movement.line_edge;old_cut=cutting.prepare;old_source_cut=guided.cut;old_cap=caps.cap
    def condition(source,faces,target):
        p,tri,dense=densify(source,faces,target);g=produce(p,tri)
        selected=g['edgeAngles']>=F(math.radians(angle_degrees));locked=np.zeros(len(p),bool)
        locked[g['topology']['edges'][selected].ravel()]=True
        # The recovered moderate smoother requires every >40-degree endpoint
        # locked. Larger requested thresholds must not silently violate this.
        required=g['edgeAngles']>F(math.radians(40))
        locked[g['topology']['edges'][required].ravel()]=True
        p,tri,result=smooth_prepared(p,tri,locked)
        diagnostics['sharpConditioningVertexCounts'].append(int(locked.sum()))
        result.update(densification=dense,featureLockMaskIsExplicitInput=False,
                      engineeringPolicy='All angular-feature endpoints locked, plus recovered >40-degree precondition; general native path admission not implied')
        return p,tri,result
    def tags(curves,edges,vo,ve,nv):
        active=[dict(c,alternatePoints=[],alternatePairs=[]) for c in curves if c['active'] and int(c['mode'])==2]
        vertices=np.zeros(nv,bool)
        for c in active:
            pairs=np.asarray(c['primaryPairs'])
            if np.any(pairs[:,0]!=1):raise NotImplementedError('Fully embedded vertex guide pairs required')
            vertices[pairs[:,1]]=True
        sequence,_=collect(active,edges,vo,ve);selected=sorted(set(map(int,sequence)))
        try:paths,_=enumerate_stack(selected,edges,vo,ve)
        except NotImplementedError:
            diagnostics['generalGraphFallbacks']+=1
            # Complete each component without inventing native ordering.
            paths=[([selected[e] for e in local],vs) for local,vs in paths_from_edges(edges[selected])]
        marked=np.zeros(len(edges),bool);marked[selected]=True
        owner=np.full(len(edges),-1,'<i4');ordinal=owner.copy();forward=np.zeros(len(edges),bool)
        eo=[0];po=[0];ee=[];vv=[]
        for group,(es,vs) in enumerate(paths):
            ee.extend(es);vv.extend(vs);eo.append(len(ee));po.append(len(vv))
            for j,e in enumerate(es):owner[e]=group;ordinal[e]=j;forward[e]=vs[j]==int(edges[e,0])
        return dict(vertices=vertices,edges=marked,selected=selected,edgeOffsets=eo,vertexOffsets=po,
                    pathEdges=ee,pathVertices=vv,owner=owner,ordinal=ordinal,forward=forward)
    def line(point,direction,a,b):
        try:return old_line(point,direction,a,b)
        except NotImplementedError as exc:
            if str(exc)!='Nearly parallel305ee0 stale output branch':raise
            diagnostics['parallelIntersectionsSkipped']+=1
            return float('nan'),float('nan')
    def pooled_cut(vertices,edges,paths,fraction=F(.05),reset_positions=True):
        # Each record sees the same original source. This composes existing
        # qualified open/closed leaves without the old pool-shape restriction.
        records=[];requests=[];details=[]
        for path in paths:
            # Engineering simplification: remove a strictly interior collinear
            # sample only when all three descriptors share an existing edge
            # and both intervals lie on that edge. Keep endpoints, corners,
            # backtracking, face-crossing intervals and attribute cases intact.
            path={key:value.copy() for key,value in path.items()}
            changed=True
            while changed and not len(path['attributes']):
                changed=False
                for i in range(1,len(path['edges'])-1):
                    ids=path['edges'];t=path['parameters']
                    if ids[i]<0 or not ids[i-1]==ids[i]==ids[i+1] or np.any(path['faces'][i-1:i+1]!=-1):continue
                    if not (t[i-1]<=t[i]<=t[i+1] or t[i-1]>=t[i]>=t[i+1]):continue
                    a,m,b=path['points'][i-1:i+2].astype(float);d=b-a;den=float(d@d)
                    if den==0:continue
                    weight=float((m-a)@d/den)
                    if not 0<weight<1 or np.linalg.norm(m-a-weight*d)>1e-7*math.sqrt(den):continue
                    for key in ['points','edges','parameters']:path[key]=np.delete(path[key],i,axis=0)
                    path['faces']=np.delete(path['faces'],i-1)
                    diagnostics['collinearGuideSamplesRemoved']+=1;changed=True;break
            _,local,ordered,diagnostic=old_cut(vertices,edges,[path],fraction,reset_positions)
            records.extend(local);requests.extend(ordered);details.extend(diagnostic)
        result=vertices.copy()
        for vertex,point in requests:result[vertex]=point
        return result,records,requests,details
    def source_cut(positions,faces,segments):
        try:return old_source_cut(positions,faces,segments)
        except NotImplementedError as exc:
            if str(exc)!='Fractional existing-edge interval':raise
            diagnostics['conformingEdgeInsertionFallbacks']+=1
            return cut_existing_edges(positions,faces,segments,pooled_cut)
    def cap(vertices,faces,protected,enabled=True):
        try:return old_cap(vertices,faces,protected,enabled)
        except NotImplementedError as exc:
            if str(exc) not in ['Shared/branch boundary splitting','Three-corner and shorter boundary policies','Short-diagonal absolute threshold/collapse policy']:raise
            output,loops,events=cap_face_fans(vertices,faces,protected,enabled)
            diagnostics['faceFanCapFallbacks'].append(dict(originalGuard=str(exc),loops=[len(row) for row in loops]))
            return output,loops,events
    guided.source_prepare=condition;finish.tags=tags;movement.line_edge=line;cutting.prepare=pooled_cut;guided.cut=source_cut;caps.cap=cap
    try:yield diagnostics
    finally:guided.source_prepare=old_prepare;finish.tags=old_tags;movement.line_edge=old_line;cutting.prepare=old_cut;guided.cut=old_source_cut;caps.cap=old_cap

def output_creases(vertices,faces,angle_degrees=30):
    """Binary geometric crease intent and bounded native low-slot encoding.

    This export policy detects actual output dihedrals. It does not claim to
    transfer arbitrary source tags, partial strengths or flat tagged seams.
    """
    v=np.asarray(vertices,dtype=float);normals=[];incident=defaultdict(list)
    for i,row in enumerate(faces):
        p=v[row];n=np.cross(p,np.roll(p,-1,axis=0)).sum(axis=0);length=np.linalg.norm(n)
        if length==0:raise ValueError('Zero-normal output face')
        normals.append(n/length)
        for j,(a,b) in enumerate(zip(row,row[1:]+row[:1])):incident[tuple(sorted((a,b)))].append((i,j))
    selected=[];flags=[0]*len(faces);encodable=all(len(row)<=4 for row in faces)
    for edge,rows in incident.items():
        if len(rows)!=2:continue
        if normals[rows[0][0]]@normals[rows[1][0]]<=math.cos(math.radians(angle_degrees)):
            selected.append(list(edge))
            if encodable:
                for face,ordinal in rows:flags[face]|=1<<(2*ordinal)
    return dict(policy='Binary output geometric dihedral threshold; engineering export policy',angleDegrees=angle_degrees,
                edges=selected,faceLowSlotBytes=flags if encodable else None,
                nativeSlotEncodingScope='Low bit of each two-bit face-edge slot, measured by998; no high-bit/partial-strength/decay semantics',
                arbitrarySourceTagsTransferred=False)
