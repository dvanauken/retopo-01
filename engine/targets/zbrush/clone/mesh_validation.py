"""Source-relative return checks; a completed extraction is not sufficient."""
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree
from measure_geometry import topology,surface_samples,surface_distances
from measure_polygon_geometry import triangulate
from features import paths_from_edges

def links(faces):
    edges=defaultdict(list);incident=defaultdict(set);neighbors=defaultdict(lambda:defaultdict(list));boundary=defaultdict(int);bad_winding=0
    for i,row in enumerate(faces):
        for v in row:incident[v].add(i)
        for a,b in zip(row,row[1:]+row[:1]):edges[tuple(sorted((a,b)))].append((i,a,b))
    for edge,rows in edges.items():
        if len(rows)==1:
            for v in edge:boundary[v]+=1
        elif len(rows)==2:
            (i,a,b),(j,c,d)=rows;bad_winding+=int(a!=d or b!=c)
            for v in edge:neighbors[v][i].append(j);neighbors[v][j].append(i)
        else:bad_winding+=1
    bad=[]
    for v,fs in incident.items():
        pending=[next(iter(fs))];seen=set()
        while pending:
            f=pending.pop()
            if f in seen:continue
            seen.add(f);pending.extend(neighbors[v][f])
        degrees=sorted(len(neighbors[v][f]) for f in fs)
        valid=seen==fs and (degrees==[2]*len(fs) if not boundary[v] else boundary[v]==2 and (degrees==[0] or degrees==[1,1]+[2]*(len(fs)-2)))
        if not valid:bad.append(v)
    return dict(nonmanifoldVertices=bad,inconsistentWindingEdges=bad_winding)

def validate_closed(source,triangles,positions,faces,*,target,physical_edges=()):
    s=np.asarray(source,dtype=float);v=np.asarray(positions,dtype=float);f=[list(map(int,r)) for r in faces];sf=[list(map(int,r)) for r in triangles]
    span=float(np.ptp(s,axis=0).max());center=(s.max(axis=0)+s.min(axis=0))*.5
    if not len(v) or not f or not np.isfinite(v).all():raise ValueError('Empty/nonfinite remesh')
    normalized_source=(s-center)/span;normalized_output=(v-center)/span
    base,st,_=topology(normalized_source,sf);out,ot,edges=topology(normalized_output,f);star=links(f)
    checks=dict(closed=out['boundaryEdges']==0,components=out['faceConnectedComponents']==base['faceConnectedComponents'],
                sourceEuler=out['eulerCharacteristic']==base['eulerCharacteristic'],
                noIncidenceDefects=all(out[k]==0 for k in ['unusedVertices','nonmanifoldEdges','repeatedIndexFaces','zeroAreaFanTriangles']),
                vertexManifold=not star['nonmanifoldVertices'],consistentWinding=star['inconsistentWindingEdges']==0)
    # Relative predicates and deterministic bounded samples keep source units
    # from changing the definition of a degenerate face or overwhelming memory.
    st=triangulate(normalized_source,sf);ot=triangulate(normalized_output,f)
    def samples(p,t):
        points=surface_samples(p,t);stride=max(1,int(np.ceil(len(points)/2048)));return points[::stride],stride,len(points)
    ss,source_stride,source_count=samples(normalized_source,st);os,output_stride,output_count=samples(normalized_output,ot)
    source_distance=surface_distances(normalized_output,ot,ss);output_distance=surface_distances(normalized_source,st,os)
    area=float(np.linalg.norm(np.cross(normalized_source[st[:,1]]-normalized_source[st[:,0]],normalized_source[st[:,2]]-normalized_source[st[:,0]]),axis=1).sum()*.5)
    surface_tolerance=.5*np.sqrt(area/target)
    checks['sampledSurface']=max(source_distance['sampledMax'],output_distance['sampledMax'])<=surface_tolerance
    feature={};physical_edges=[tuple(map(int,e)) for e in physical_edges]
    if physical_edges:
        degree=np.bincount(np.asarray(physical_edges).ravel(),minlength=len(s));corners=np.flatnonzero(degree>=3)
        errors=cKDTree(v).query(s[corners])[0] if len(corners) else np.array([])
        feature_tolerance=2e-6*span;checks['physicalJunctions']=float(errors.max(initial=0))<=feature_tolerance
        e=np.asarray(edges);a=v[e[:,0]];delta=v[e[:,1]]-a;den=(delta*delta).sum(axis=1);maximum=0.;straight=0
        for _,path in paths_from_edges(physical_edges):
            if path[0]==path[-1]:continue
            p,q=s[path[0]],s[path[-1]];d=q-p;length2=d@d
            if length2==0:continue
            residual=np.linalg.norm(s[path]-p-(((s[path]-p)@d)/length2)[:,None]*d,axis=1)
            if residual.max()>feature_tolerance:continue
            straight+=1
            for point in np.linspace(p,q,65):
                t=np.clip(((point-a)*delta).sum(axis=1)/den,0,1);maximum=max(maximum,float(np.linalg.norm(point-a-t[:,None]*delta,axis=1).min()))
        checks['straightPhysicalFeatures']=maximum<=feature_tolerance
        feature=dict(junctions=len(corners),cornerSampledMax=float(errors.max(initial=0)),straightPaths=straight,lineSampledMax=maximum,tolerance=feature_tolerance,
                     curvedSourceFeatureVertexFreezing=False)
    checks={key:bool(value) for key,value in checks.items()}
    result=dict(passed=all(checks.values()),checks=checks,vertexLinks=star,features=feature,
                topology={k:out[k] for k in ['vertices','faces','quads','triangles','boundaryEdges','nonmanifoldEdges','faceConnectedComponents','eulerCharacteristic']},
                sourceToOutputNormalized=source_distance,outputToSourceNormalized=output_distance,
                measurementFrame=dict(center=center.tolist(),scale=1/span,normalizationOnlyForPredicates=True),
                sampledSurfaceToleranceNormalized=float(surface_tolerance),samples=dict(sourceAvailable=source_count,sourceStride=source_stride,outputAvailable=output_count,outputStride=output_stride),
                limitations=['Sampled surface/feature errors are not a Hausdorff certificate.','Topology and vertex links do not alone certify absence of all 3D self-intersections.','Binary geometric crease preservation does not imply arbitrary source attribute transfer.'])
    return result
