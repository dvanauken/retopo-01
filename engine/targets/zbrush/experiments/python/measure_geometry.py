"""OBJ topology, sampled surface deviation and guide/edge alignment measurements.

No file-existence or exit-code inference is made about successful remeshing.
All coordinates must already share a qualified frame; this tool never auto-fits
away native error. A fixed vertex-zero fan defines the piecewise planar surface
for convex nontriangles; projected nonconvex polygons are rejected for deviation.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import numpy as np
import trimesh


def read_obj(path):
    vertices=[];faces=[]
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        words=line.split()
        if not words or words[0].startswith('#'):continue
        if words[0]=='v':
            if len(words)<4:raise ValueError('Incomplete vertex')
            vertices.append([float(x) for x in words[1:4]])
        elif words[0]=='f':
            face=[]
            for token in words[1:]:
                i=int(token.split('/')[0]);i=i-1 if i>0 else len(vertices)+i
                if i<0 or i>=len(vertices):raise ValueError('Invalid OBJ index')
                face.append(i)
            if len(face)<3:raise ValueError('Face has fewer than three vertices')
            faces.append(face)
    points=np.asarray(vertices,dtype=float)
    if points.shape!=(len(vertices),3) or not np.isfinite(points).all() or not len(faces):raise ValueError('Empty/nonfinite mesh')
    return points,faces


def components(nodes,adjacency):
    todo=set(nodes);groups=[]
    while todo:
        pending=[todo.pop()];group=[]
        while pending:
            node=pending.pop();group.append(node)
            for other in adjacency[node]:
                if other in todo:todo.remove(other);pending.append(other)
        groups.append(group)
    return groups


def topology(vertices,faces):
    edges=defaultdict(list);face_graph=defaultdict(set);used=set()
    for index,face in enumerate(faces):
        used.update(face)
        for a,b in zip(face,face[1:]+face[:1]):edges[tuple(sorted((a,b)))].append(index)
    for incident in edges.values():
        for a in incident:face_graph[a].update(set(incident)-{a})
    groups=components(range(len(faces)),face_graph)
    boundary=[e for e,incident in edges.items() if len(incident)==1]
    boundary_graph=defaultdict(set)
    for a,b in boundary:boundary_graph[a].add(b);boundary_graph[b].add(a)
    boundary_groups=components(boundary_graph,boundary_graph)
    counts=Counter(map(len,faces));n=len(faces)
    lengths=np.array([np.linalg.norm(vertices[a]-vertices[b]) for a,b in edges])
    degenerate=sum(len(set(f))!=len(f) for f in faces)
    triangles=np.array([[face[0],face[i],face[i+1]] for face in faces for i in range(1,len(face)-1)])
    positions=vertices[triangles]
    areas=np.linalg.norm(np.cross(positions[:,1]-positions[:,0],positions[:,2]-positions[:,0]),axis=1)/2
    # Face signatures ignore ordering and winding, but retain exact coordinates.
    canonical=sorted(tuple(sorted(tuple(float(x) if x!=0 else 0.0 for x in vertices[i]) for i in face)) for face in faces)
    signature=hashlib.sha256(repr(canonical).encode()).hexdigest()
    nonplanar=[];nonconvex=0
    for face in faces:
        if len(face)>=4:
            polygon=vertices[face];_,_,basis=np.linalg.svd(polygon-polygon.mean(axis=0),full_matrices=False);uv=polygon@basis[:2].T
            e=np.roll(uv,-1,axis=0)-uv;next_e=np.roll(e,-1,axis=0);turn=e[:,0]*next_e[:,1]-e[:,1]*next_e[:,0]
            if np.any(turn>1e-12) and np.any(turn < -1e-12):nonconvex+=1
        if len(face)==4:
            p=vertices[face];normal=np.cross(p[1]-p[0],p[2]-p[0]);norm=np.linalg.norm(normal)
            if norm>0:nonplanar.append(abs(float(np.dot(p[3]-p[0],normal)))/norm)
    return dict(vertices=len(vertices),usedVertices=len(used),unusedVertices=len(vertices)-len(used),faces=n,edges=len(edges),faceSizes=dict(counts),triangles=counts[3],quads=counts[4],triangleFraction=counts[3]/n,quadFraction=counts[4]/n,otherPolygonFraction=sum(v for k,v in counts.items() if k not in [3,4])/n,faceConnectedComponents=len(groups),componentFaceCounts=sorted(map(len,groups)),boundaryEdges=len(boundary),boundaryComponents=len(boundary_groups),closedBoundaryLoops=sum(all(len(boundary_graph[v])==2 for v in group) for group in boundary_groups),nonmanifoldEdges=sum(len(incident)>2 for incident in edges.values()),repeatedIndexFaces=degenerate,zeroAreaFanTriangles=int(np.count_nonzero(areas<=1e-14)),nonconvexProjectedPolygons=nonconvex,maxQuadFourthPointPlaneDistance=float(max(nonplanar,default=0)),eulerCharacteristic=len(used)-len(edges)+n,bounds=[vertices.min(axis=0).tolist(),vertices.max(axis=0).tolist()],edgeLengths=dict(min=float(lengths.min()),median=float(np.median(lengths)),max=float(lengths.max())),canonicalGeometrySignature=signature),triangles,list(edges)


def surface_samples(vertices,triangles):return np.vstack([vertices[np.unique(triangles)],vertices[triangles].mean(axis=1)])


def surface_distances(vertices,triangles,samples):
    mesh=trimesh.Trimesh(vertices=vertices,faces=triangles,process=False)
    distances=[]
    for i in range(0,len(samples),16):
        _,values,_=trimesh.proximity.closest_point_naive(mesh,samples[i:i+16]);distances.extend(values)
    values=np.asarray(distances)
    return dict(samples=len(values),rms=float(np.sqrt(np.mean(values**2))),mean=float(values.mean()),p95=float(np.percentile(values,95)),sampledMax=float(values.max()))


def window_chords(points,window,closed=False):
    """Chord spanning `window` of arc length around each polyline sample.

    Near the ends of an open polyline the window shifts inward instead of
    shrinking, so every chord spans the same length (or the whole curve).
    """
    points=np.asarray(points,dtype=float)
    arc=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))];total=arc[-1]
    def at(s):return np.array([np.interp(s,arc,points[:,k]) for k in range(3)]).T
    if closed:return at(np.mod(arc+window*.5,total))-at(np.mod(arc-window*.5,total))
    low=np.clip(arc-window*.5,0,max(0.,total-window));high=np.minimum(low+window,total)
    return at(high)-at(low)


def guide_alignment(vertices,edges,guide,tangent_window=None):
    """Nearest-edge distance and unsigned tangent angle per guide sample.

    With tangent_window, the guide direction is the chord spanning that arc length
    around each sample (wrapping on closed guides), so detail of the authored
    curve finer than the window is not counted as a direction error.
    """
    guide=np.asarray(guide,dtype=float)
    if len(guide)<2:raise ValueError('Guide needs two or more samples')
    start=vertices[np.array(edges)[:,0]];delta=vertices[np.array(edges)[:,1]]-start
    denominator=np.einsum('ij,ij->i',delta,delta);valid=denominator>0;valid_edges=np.array(edges)[valid];start=start[valid];delta=delta[valid];denominator=denominator[valid]
    if not len(start):raise ValueError('No nonzero edges')
    closed=np.linalg.norm(guide[0]-guide[-1])<1e-10 and len(guide)>3
    if tangent_window:
        windowed=window_chords(guide,tangent_window,closed)
    distances=[];angles=[];selected=[]
    for i,point in enumerate(guide):
        t=np.clip(np.einsum('ij,ij->i',point-start,delta)/denominator,0,1)
        ds=np.linalg.norm(point-start-t[:,None]*delta,axis=1);nearest=int(np.argmin(ds))
        tangent=guide[min(i+1,len(guide)-1)]-guide[max(0,i-1)]
        if i in [0,len(guide)-1] and closed:tangent=guide[1]-guide[-2]
        if tangent_window and np.linalg.norm(windowed[i])>0:tangent=windowed[i]
        norm=np.linalg.norm(tangent)
        if norm==0:raise ValueError('Undefined guide tangent')
        cosine=abs(np.dot(tangent,delta[nearest]))/(norm*np.sqrt(denominator[nearest]))
        distances.append(float(ds[nearest]));angles.append(float(np.degrees(np.arccos(np.clip(cosine,0,1)))));selected.append(nearest)
    values=np.asarray(distances);median_edge=float(np.median(np.sqrt(denominator)))
    graph=defaultdict(set)
    for edge in set(selected):
        a,b=map(int,valid_edges[edge]);graph[a].add(b);graph[b].add(a)
    groups=components(graph,graph)
    return dict(samples=len(guide),meanDistance=float(values.mean()),p95Distance=float(np.percentile(values,95)),maxDistance=float(values.max()),meanDistanceOverMedianEdge=float(values.mean()/median_edge),meanUnsignedTangentAngleDegrees=float(np.mean(angles)),p95UnsignedTangentAngleDegrees=float(np.percentile(angles,95)),selectedEdgeCount=len(set(selected)),selectedEdgeGraphComponents=len(groups),selectedEdgeGraphDegreeHistogram=dict(Counter(map(len,graph.values()))),selectedEdgesFormSingleCycle=len(groups)==1 and all(len(neighbors)==2 for neighbors in graph.values()),loopContinuity='Nearest-edge selection graph only; not a global topological guarantee or certified curve correspondence.')


def measure(source,output=None,guides=None,coordinate_frame_qualified=False):
    v,f=read_obj(source);base,tri,edges=topology(v,f)
    result=dict(schemaVersion=1,method='Face-edge incidence topology; vertices and triangle centroids sampled against exact nearest points on all target triangles; unsigned tangent alignment to nearest nonzero edge.',coordinateFrameQualified=coordinate_frame_qualified,source=dict(path=str(source),sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),metrics=base),remeshingQualified=False,tolerances=dict(analyticRegressionAbsolute=1e-7,zeroAreaFanTriangle=1e-14),limitations=['Sampled surface deviation is not a certified Hausdorff bound.','Polygon triangulation uses a fan; convexity/planarity must be inspected for nontriangles.','Closest edge distance can improve merely with greater density; compare angle, density and an unguided baseline.','This measurement alone cannot prove a remesher was invoked.'])
    result['toolchain']=dict(numpy=np.__version__,trimesh=trimesh.__version__,measurementSourceSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    result['limitations'][1]='Fixed vertex-zero fan defines nontriangle interpolation; nonplanarity is measured. Projected nonconvex or degenerate polygons are rejected for surface comparison.'
    if output:
        if not coordinate_frame_qualified:raise ValueError('Coordinate mapping must be qualified before comparing native output')
        ov,of=read_obj(output);out,ot,oe=topology(ov,of)
        if any(m[k]>0 for m in [base,out] for k in ['nonconvexProjectedPolygons','repeatedIndexFaces','zeroAreaFanTriangles']):raise ValueError('Nonconvex or degenerate polygons require another surface measurement method')
        result['output']=dict(path=str(output),sha256=hashlib.sha256(Path(output).read_bytes()).hexdigest(),metrics=out)
        result['canonicalGeometryChanged']=base['canonicalGeometrySignature']!=out['canonicalGeometrySignature']
        result['sourceToOutput']=surface_distances(ov,ot,surface_samples(v,tri))
        result['outputToSource']=surface_distances(v,tri,surface_samples(ov,ot))
        if guides:result['guideAlignment']=[guide_alignment(ov,oe,curve) for curve in guides]
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--native-output');ap.add_argument('--guides');ap.add_argument('--coordinate-frame-qualified',action='store_true');ap.add_argument('--report',required=True);args=ap.parse_args()
    guides=json.loads(Path(args.guides).read_text()) if args.guides else None
    result=measure(args.input,args.native_output,guides,args.coordinate_frame_qualified)
    Path(args.report).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(faces=result['source']['metrics']['faces'],nativeOutputMeasured=bool(args.native_output),remeshingQualified=False)))

if __name__=='__main__':main()
