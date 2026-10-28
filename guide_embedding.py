"""Embed surface polylines in a conforming triangle mesh before quad layout.

Engineering route: closest surface attachment, bounded dual-face routing,
coherent edge intersections, and per-face constrained triangulation. Original
positions stay fixed. Each inserted vertex belongs to an original face/edge.
This is not native float/order recovery or a geodesic shortest-path guarantee.
"""
from collections import defaultdict
import heapq
import numpy as np
import trimesh
import triangle

def embed(vertices,faces,curves):
    vertices=np.asarray(vertices,dtype=float)
    raw_faces=np.asarray(faces)
    if vertices.ndim!=2 or vertices.shape[1]!=3 or not len(vertices) or not np.isfinite(vertices).all():
        raise ValueError('Source vertices must be finite 3D points')
    if raw_faces.ndim!=2 or raw_faces.shape[1]!=3 or not len(raw_faces) or not np.issubdtype(raw_faces.dtype,np.integer):
        raise ValueError('Source faces must be integer triangles')
    faces=raw_faces.astype(int)
    if faces.min()<0 or faces.max()>=len(vertices):raise ValueError('Source triangle index outside vertex range')
    if np.ptp(vertices,axis=0).max()<=0:raise ValueError('Source extent must be positive')
    source=trimesh.Trimesh(vertices,faces,process=False)
    extent=float(np.ptp(vertices,axis=0).max());eps=extent*1e-9
    if np.any(source.area_faces<=extent*extent*1e-18) or not source.is_winding_consistent:
        raise ValueError('Source triangles must be nondegenerate and consistently wound')
    curves=[np.asarray(curve,dtype=float) for curve in curves]
    for curve in curves:
        if curve.ndim!=2 or curve.shape[1]!=3 or len(curve)<2 or not np.isfinite(curve).all():
            raise ValueError('Guides require at least two finite 3D samples')
        if np.any(np.linalg.norm(np.diff(curve,axis=0),axis=1)<=eps):
            raise ValueError('Consecutive guide samples must be distinct at source tolerance')
    points=list(vertices.copy());edge_points=defaultdict(list);face_points=defaultdict(list)
    constraints=defaultdict(list);adj=defaultdict(list)
    for (a,b),edge in zip(source.face_adjacency,source.face_adjacency_edges):
        edge=tuple(sorted(map(int,edge)));adj[int(a)].append((int(b),edge));adj[int(b)].append((int(a),edge))
    centers=source.triangles_center
    walks=[];attachments=[]
    def point_id(p,face):
        tri=faces[face];q=vertices[tri]
        nearest=int(np.argmin(np.linalg.norm(q-p,axis=1)))
        if np.linalg.norm(q[nearest]-p)<=eps:return int(tri[nearest])
        for a,b in zip(tri,np.roll(tri,-1)):
            a,b=sorted((int(a),int(b)));d=vertices[b]-vertices[a]
            t=np.clip(np.dot(p-vertices[a],d)/np.dot(d,d),0,1)
            projected=vertices[a]+t*d
            if np.linalg.norm(p-projected)<=eps:
                for old_t,index in edge_points[(a,b)]:
                    if np.linalg.norm(points[index]-projected)<=eps:return index
                index=len(points);points.append(projected);edge_points[(a,b)].append((float(t),index));return index
        for index in face_points[face]:
            if np.linalg.norm(points[index]-p)<=eps:return index
        index=len(points);points.append(p.copy());face_points[face].append(index);return index
    def line_distance(p,a,b):
        d=b-a;t=np.clip(np.dot(p-a,d)/np.dot(d,d),0,1)
        return np.linalg.norm(p-a-t*d)
    def route(start,end,a,b):
        if start==end:return [start],[]
        costs={start:0.};previous={};queue=[(0.,start)];visited=set()
        maxwidth=max(np.linalg.norm(b-a)*3,source.edges_unique_length.mean()*5)
        while queue:
            _,face=heapq.heappop(queue)
            if face in visited:continue
            visited.add(face)
            if face==end:break
            if len(visited)>1000:raise ValueError('Guide face routing exceeded 1000-face local budget')
            for nxt,edge in adj[face]:
                mid=vertices[list(edge)].mean(axis=0)
                distance=line_distance(mid,a,b)
                if distance>maxwidth:continue
                cost=costs[face]+np.linalg.norm(centers[nxt]-centers[face])*(1+20*(distance/maxwidth)**2)
                if cost<costs.get(nxt,np.inf):
                    costs[nxt]=cost;previous[nxt]=(face,edge)
                    heapq.heappush(queue,(cost+np.linalg.norm(centers[nxt]-b),nxt))
        if end not in visited:raise ValueError('Guide cannot be connected through local adjacent faces')
        path=[end];edges=[]
        while path[-1]!=start:
            face,edge=previous[path[-1]];path.append(face);edges.append(edge)
        return path[::-1],edges[::-1]
    def crossing(edge,a,b):
        lo,hi=vertices[list(edge)];d=hi-lo;v=b-a
        # Constrained two-segment least squares, alternately projecting the two
        # convex intervals; start from unconstrained solution when full rank.
        matrix=np.c_[d,-v];solution=np.linalg.lstsq(matrix,a-lo,rcond=None)[0]
        u,t=np.clip(solution,0,1)
        for _ in range(8):
            u=np.clip(np.dot(a+t*v-lo,d)/np.dot(d,d),0,1)
            t=np.clip(np.dot(lo+u*d-a,v)/np.dot(v,v),0,1)
        return lo+u*d
    for ci,curve in enumerate(curves):
        curve=np.asarray(curve,dtype=float)
        attached,error,owners=trimesh.proximity.closest_point(source,curve)
        if np.max(error)>extent*1e-5:raise ValueError('Guide samples lie outside declared source tolerance')
        attachments.append(dict(curve=ci,maxDistance=float(error.max()),points=len(curve)))
        for a,b,first,last in zip(attached[:-1],attached[1:],owners[:-1],owners[1:]):
            if np.linalg.norm(a-b)<=eps:continue
            path,edges=route(int(first),int(last),a,b)
            spans=[a]+[crossing(e,a,b) for e in edges]+[b]
            walks.append(dict(curve=ci,faces=path,edgeCrossings=len(edges)))
            for face,x,y in zip(path,spans[:-1],spans[1:]):
                i,j=point_id(x,face),point_id(y,face)
                if i!=j:constraints[face].append((i,j,ci))
    output=[];source_owners=[];guide_edges=defaultdict(set)
    for fi,face in enumerate(faces):
        boundary=[]
        for a,b in zip(face,np.roll(face,-1)):
            a,b=int(a),int(b);key=tuple(sorted((a,b)))
            cuts=sorted(edge_points[key],reverse=a>b)
            boundary.extend([a]+[index for t,index in cuts])
        if len(boundary)==3 and fi not in constraints:
            output.append(face.tolist());source_owners.append(fi);continue
        ids=list(dict.fromkeys(boundary+[i for a,b,c in constraints[fi] for i in (a,b)]))
        table={index:i for i,index in enumerate(ids)}
        q=vertices[face];u=q[1]-q[0];u/=np.linalg.norm(u);n=source.face_normals[fi];v=np.cross(n,u)
        basis=np.array([u,v]).T
        uv=(np.array([points[i] for i in ids])-q[0])@basis
        # Distinct guide identities may cross at a point, but a shared interval
        # needs an explicit ownership policy. Detect partial collinear overlaps
        # before Triangle can silently choose one of their segment markers.
        spans=[(uv[[table[a],table[b]]],ci) for a,b,ci in constraints[fi]]
        for si,(line,ci) in enumerate(spans):
            delta=line[1]-line[0];length=np.linalg.norm(delta);axis=delta/length
            for other,cj in spans[:si]:
                if ci==cj:continue
                displacement=other-line[0]
                perpendicular=np.abs(displacement[:,0]*axis[1]-displacement[:,1]*axis[0])
                interval=np.sort(displacement@axis)
                overlap=min(length,interval[1])-max(0.,interval[0])
                if perpendicular.max()<=eps and overlap>eps:
                    raise ValueError('Overlapping guide intervals require explicit ownership')
        segments=[(table[a],table[b]) for a,b in zip(boundary,boundary[1:]+boundary[:1])]
        markers=[1]*len(segments)
        for a,b,ci in constraints[fi]:
            segments.append((table[a],table[b]));markers.append(1000+ci)
        # Remove identical constraints, retaining the guide identity at a source
        # boundary. Shared-guide intervals of distinct identities reject.
        unique={}
        for e,m in zip(segments,markers):
            key=tuple(sorted(e));old=unique.get(key,1)
            if m>=1000 and old>=1000 and old!=m:raise ValueError('Overlapping guide intervals require explicit ownership')
            unique[key]=max(old,m)
        built=triangle.triangulate(dict(vertices=uv,segments=list(unique),segment_markers=list(unique.values())),'pQ')
        if 'triangles' not in built:raise ValueError('Empty constrained face triangulation')
        global_ids=ids.copy()
        for local in built['vertices'][len(ids):]:
            p=q[0]+basis@local
            global_ids.append(point_id(p,fi))
        for tri in built['triangles']:
            tri=[global_ids[int(i)] for i in tri]
            p=np.asarray([points[i] for i in tri]);area=np.dot(np.cross(p[1]-p[0],p[2]-p[0]),n)
            if area<0:tri[1],tri[2]=tri[2],tri[1];area=-area
            if area<=extent*extent*1e-18:raise ValueError('Embedding produced a collapsed source triangle')
            output.append(tri);source_owners.append(fi)
        for e,m in zip(built['segments'],built['segment_markers'].ravel()):
            if m>=1000:guide_edges[int(m)-1000].add(tuple(sorted(global_ids[int(i)] for i in e)))
    points=np.asarray(points);output=np.asarray(output,dtype=int)
    owners={}
    for ci,edges in guide_edges.items():
        for edge in edges:
            if edge in owners and owners[edge]!=ci:
                raise ValueError('Overlapping guide intervals require explicit ownership')
            owners[edge]=ci
    result=trimesh.Trimesh(points,output,process=False)
    if source.is_watertight!=result.is_watertight or not result.is_winding_consistent or result.euler_number!=source.euler_number:
        raise ValueError('Embedding changed closed topology or winding')
    # Every child is on its original parent triangle; summed area catches omitted
    # or overlapping cover in this local construction independently of incidence.
    areas=np.bincount(source_owners,weights=result.area_faces,minlength=len(faces))
    relative=np.max(np.abs(areas-source.area_faces)/np.maximum(source.area_faces,extent*extent*1e-18))
    if relative>1e-6:raise ValueError('Embedding changed original triangle coverage')
    return points,output,dict(attachments=attachments,walks=walks,sourceOwners=source_owners,
                              guideEdges={str(k):sorted(e) for k,e in guide_edges.items()},
                              parentAreaRelativeError=float(relative),sourceVerticesFixed=True,
                              tolerance=eps,triangleVersion=triangle.__version__)
