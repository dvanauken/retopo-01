"""Engineering guided heightfield route over the recovered closed-surface core.

Temporary side/bottom geometry supplies a closed support; it is never returned.
This is not recovered ZBrush open-surface processing. Initial domain contract:
one consistently upward oriented heightfield disk with a convex XY boundary.
"""
from collections import defaultdict
import math
import numpy as np
import trimesh

def _cross2(a,b):return a[...,0]*b[...,1]-a[...,1]*b[...,0]

def _simple_boundary(p,span):
    epsilon=1e-12*span*span;linear=1e-12*span;n=len(p)
    def on(a,b,x):return np.all(x>=np.minimum(a,b)-linear) and np.all(x<=np.maximum(a,b)+linear)
    for i in range(n):
        a,b=p[i],p[(i+1)%n]
        for j in range(i+2,n):
            if i==0 and j==n-1:continue
            c,d=p[j],p[(j+1)%n]
            if np.any(np.maximum(a,b)<np.minimum(c,d)-linear) or np.any(np.maximum(c,d)<np.minimum(a,b)-linear):continue
            o1,o2,o3,o4=_cross2(b-a,c-a),_cross2(b-a,d-a),_cross2(d-c,a-c),_cross2(d-c,b-c)
            if (o1*o2 < -epsilon*epsilon and o3*o4 < -epsilon*epsilon or
                abs(o1)<=epsilon and on(a,b,c) or abs(o2)<=epsilon and on(a,b,d) or
                abs(o3)<=epsilon and on(c,d,a) or abs(o4)<=epsilon and on(c,d,b)):
                raise ValueError('Projected boundary self-intersection or nonadjacent contact')

def _source(vertices,triangles):
    v=np.asarray(vertices,dtype=float);f=np.asarray(triangles)
    if v.ndim!=2 or v.shape[1:]!=(3,) or not len(v) or not np.isfinite(v).all():raise ValueError('Finite XYZ source required')
    if f.ndim!=2 or f.shape[1:]!=(3,) or not len(f) or not np.issubdtype(f.dtype,np.integer):raise ValueError('Integer source triangles required')
    if f.min()<0 or f.max()>=len(v) or len(np.unique(f))!=len(v):raise ValueError('Valid used source indices required')
    span=float(np.ptp(v[:,:2],axis=0).max())
    if span<=0 or len(np.unique(v[:,:2],axis=0))!=len(v):raise ValueError('Single-valued XY heightfield required')
    xy=v[f,:2];cross=_cross2(xy[:,1]-xy[:,0],xy[:,2]-xy[:,0])
    if np.any(cross<=1e-14*span*span):raise ValueError('Every source triangle must have positive nondegenerate XY orientation')
    incident=defaultdict(list);face_adjacency=defaultdict(set)
    for i,row in enumerate(f):
        for a,b in zip(row,np.roll(row,-1)):incident[tuple(sorted((int(a),int(b))))].append((i,int(a),int(b)))
    for rows in incident.values():
        if len(rows)>2:raise ValueError('Nonmanifold source edge')
        if len(rows)==2:
            (i,a,b),(j,c,d)=rows
            if a!=d or b!=c:raise ValueError('Inconsistent source winding')
            face_adjacency[i].add(j);face_adjacency[j].add(i)
    visited=set();pending=[0]
    while pending:
        face=pending.pop()
        if face in visited:continue
        visited.add(face);pending.extend(face_adjacency[face]-visited)
    if len(visited)!=len(f):raise ValueError('One face-connected heightfield required')
    boundary=[(rows[0][1],rows[0][2]) for rows in incident.values() if len(rows)==1]
    if not boundary or len(v)-len(incident)+len(f)!=1:raise ValueError('Heightfield must be a topological disk')
    following={a:b for a,b in boundary}
    if len(following)!=len(boundary) or len(set(following.values()))!=len(boundary):raise ValueError('Simple degree-two source boundary required')
    ring=[min(following)]
    while True:
        nxt=following[ring[-1]]
        if nxt==ring[0]:break
        if nxt in ring:raise ValueError('Source boundary failed to close simply')
        ring.append(nxt)
    if len(ring)!=len(boundary):raise ValueError('Only one source boundary loop is supported')
    p=v[ring,:2];_simple_boundary(p,span);e=np.roll(p,-1,axis=0)-p;turn=_cross2(e,np.roll(e,-1,axis=0))
    if np.any(turn < -1e-12*span*span):raise NotImplementedError('TODO TERRAIN-EDGE-01: concave/holed XY domains need a separately qualified support triangulation')
    return v,f.astype(np.int64),boundary,ring,span

def construct_heightfield(vertices,triangles,curves,*,target=500,normalize=False,
                          sharp_angle=30.,solid_method='auto',surface_tolerance=None,
                          boundary_tolerance=None,guide_tolerance=None):
    """Return only a measured visible terrain mesh and explicit policy provenance.

    All user and automatic support-feature curves use strict mode two. Tolerances
    are declared before the solve; failures raise without returning a good mesh.
    Surface error is sampled, not a Hausdorff certificate. No native data is used.
    """
    from retopo import construct
    from measure_geometry import topology,surface_samples,surface_distances,guide_alignment
    from measure_polygon_geometry import triangulate
    v,f,boundary,ring,span=_source(vertices,triangles)
    if type(target) is not int or not 1<=target<=1_000_000:raise ValueError('Positive integer target at most one million required')
    if not isinstance(curves,(list,tuple)):raise ValueError('Curve list required')
    zbase=float(v[:,2].min()-.1*span);points=list(v.copy());bottom={}
    for vertex in ring:
        bottom[vertex]=len(points);points.append(np.array([v[vertex,0],v[vertex,1],zbase]))
    center=len(points);points.append(np.array([v[ring,0].mean(),v[ring,1].mean(),zbase]))
    closed_faces=f.tolist()
    for a,b in boundary:closed_faces.extend([[b,a,bottom[a]],[b,bottom[a],bottom[b]],[center,bottom[b],bottom[a]]])
    closed=np.asarray(points);closed_faces=np.asarray(closed_faces,dtype=np.int64)
    area=lambda p,t:float(np.linalg.norm(np.cross(p[t[:,1]]-p[t[:,0]],p[t[:,2]]-p[t[:,0]]),axis=1).sum()*.5)
    top_area=area(v,f);closed_area=area(closed,closed_faces);support_target=int(round(target*closed_area/top_area))
    tolerance=dict(surfaceSampledMax=.02*span if surface_tolerance is None else float(surface_tolerance),
                   boundarySampledMax=.002*span if boundary_tolerance is None else float(boundary_tolerance),
                   guideInteriorP95=.1*math.sqrt(top_area/target) if guide_tolerance is None else float(guide_tolerance))
    if any(not np.isfinite(x) or x<=0 for x in tolerance.values()):raise ValueError('Finite positive tolerances required')
    ov,of,metadata=construct(closed,closed_faces,curves,target=support_target,guide_mode=2,
                             normalize=normalize,feature_policy='preserve-sharp',sharp_angle=sharp_angle,solid_method=solid_method)
    centers=np.asarray([ov[row].mean(axis=0) for row in of]);source_mesh=trimesh.Trimesh(vertices=closed,faces=closed_faces,process=False);nearest=[]
    for offset in range(0,len(centers),16):
        _,_,ids=trimesh.proximity.closest_point_naive(source_mesh,centers[offset:offset+16]);nearest.extend(map(int,ids))
    selected=[row for row,face in zip(of,nearest) if face<len(f)]
    if not selected:raise RuntimeError('Support remesh produced no visible terrain')
    used=np.unique([i for row in selected for i in row]);remap=np.full(len(ov),-1,dtype=int);remap[used]=np.arange(len(used))
    output=ov[used];faces=[[int(remap[i]) for i in row] for row in selected]
    stats,_,edges=topology(output,faces)
    if not (stats['faceConnectedComponents']==1 and stats['eulerCharacteristic']==1 and stats['boundaryComponents']==1 and stats['closedBoundaryLoops']==1):raise RuntimeError('Cropped terrain is not one disk')
    if any(stats[k]!=0 for k in ['unusedVertices','nonmanifoldEdges','repeatedIndexFaces','zeroAreaFanTriangles']):raise RuntimeError('Cropped terrain contains incidence or area defects')
    # Validate a positive XY triangulation, independently of the 3D polygon
    # measurement convention. A fold must not be accepted as a valid heightfield.
    xy=(output[:,:2]-v[:,:2].mean(axis=0))/span;xy3=np.column_stack([xy,np.zeros(len(xy))]);xy_tri=triangulate(xy3,faces)
    q=xy[xy_tri]
    if np.any(_cross2(q[:,1]-q[:,0],q[:,2]-q[:,0])<=1e-14):raise RuntimeError('Cropped terrain folds or degenerates in XY')
    source_tri=triangulate(v,f.tolist());output_tri=triangulate(output,faces)
    source_distance=surface_distances(output,output_tri,surface_samples(v,source_tri))
    output_distance=surface_distances(v,source_tri,surface_samples(output,output_tri))
    if max(source_distance['sampledMax'],output_distance['sampledMax'])>tolerance['surfaceSampledMax']:raise RuntimeError('Visible terrain exceeds declared sampled surface tolerance')
    guide_metrics=[]
    for curve in curves:
        curve=np.asarray(curve,dtype=float)
        interior=curve[1:-1] if len(curve)>3 else curve
        metrics=guide_alignment(output,edges,interior);guide_metrics.append(metrics)
        if metrics['p95Distance']>tolerance['guideInteriorP95']:raise RuntimeError('Visible terrain exceeds declared interior guide registration tolerance')
    output_incident=defaultdict(int)
    for row in faces:
        for a,b in zip(row,row[1:]+row[:1]):output_incident[tuple(sorted((a,b)))]+=1
    be=np.asarray([e for e,count in output_incident.items() if count==1]);a=output[be[:,0]];delta=output[be[:,1]]-a;den=(delta*delta).sum(axis=1)
    boundary_adj=defaultdict(list)
    for x,y in be:boundary_adj[int(x)].append(int(y));boundary_adj[int(y)].append(int(x))
    out_ring=[min(boundary_adj)];previous=-1
    while True:
        nxt=next(x for x in boundary_adj[out_ring[-1]] if x!=previous)
        if nxt==out_ring[0]:break
        if nxt in out_ring:raise RuntimeError('Output boundary is not simple')
        previous=out_ring[-1];out_ring.append(nxt)
    _simple_boundary(output[out_ring,:2],span)
    boundary_samples=np.vstack([np.linspace(v[x],v[y],9) for x,y in boundary]);dist=[]
    for point in boundary_samples:
        t=np.clip(((point-a)*delta).sum(axis=1)/den,0,1);dist.append(float(np.linalg.norm(point-a-t[:,None]*delta,axis=1).min()))
    boundary_error=max(dist)
    if boundary_error>tolerance['boundarySampledMax']:raise RuntimeError('Visible terrain exceeds declared sampled border tolerance')
    # Do not expose support-only vertex IDs or crease bytes as visible metadata.
    support_metadata=metadata.pop('outputCreases',None)
    support_features=metadata.pop('sourceAngularFeatureEdges',[])
    support_validation=metadata.pop('closedValidation',None)
    support_backend=metadata.pop('backend')
    import features
    metadata.update(backend='heightfield-enclosure',nativeOpenAlgorithmRecovered=False,
                    sourceVertices=len(v),sourceTriangles=len(f),target=target,
                    vertices=len(output),faces=len(faces),faceSizes=stats['faceSizes'],
                    outputCreases=features.output_creases(output,faces,sharp_angle),
                    enclosure=dict(backend=support_backend,closedValidation=support_validation,
                                   bottomZ=zbase,supportVertices=len(closed),supportTriangles=len(closed_faces),
                                   supportTarget=support_target,topArea=top_area,supportArea=closed_area,
                                   supportOutputVertices=len(ov),supportOutputFaces=len(of),
                                   removedFaces=len(of)-len(faces),supportCreaseCount=len(support_metadata['edges']) if support_metadata else 0,
                                   sourceAngularFeatureEdges=support_features,
                                   regionRule='Nearest original support triangle to output face centroid belongs to original top surface; no output coordinate fit'),
                    validation=dict(topology=stats,positiveXYTriangles=True,sourceToOutput=source_distance,
                                    outputToSource=output_distance,interiorGuideAlignment=guide_metrics,
                                    boundarySamples=len(boundary_samples),boundarySampledMax=boundary_error,tolerances=tolerance,
                                    limitations=['Sampled deviations are not Hausdorff certificates.','Convex XY disk and strict curves only; support geometry influences the solved field.','Original boundary vertex count is not frozen; border shape is measured within tolerance.']))
    return output,faces,metadata
