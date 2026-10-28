"""Local disk parameterization for untangling on a curved source surface."""
from collections import defaultdict
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix,lil_matrix
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import spsolve
from guide_embedding import embed
from quad_connectivity import improve,split_vertex_cut


def harmonic(vertices,edges,boundary,uv,weights=None):
    interior=np.setdiff1d(vertices,boundary);lookup={int(v):i for i,v in enumerate(interior)}
    adjacency=defaultdict(set)
    for a,b in edges:adjacency[int(a)].add(int(b));adjacency[int(b)].add(int(a))
    matrix=lil_matrix((len(interior),len(interior)));rhs=np.zeros((len(interior),2))
    for v,i in lookup.items():
        matrix[i,i]=sum(weights.get((v,n),0.) if weights is not None else 1. for n in adjacency[v])
        for neighbor in adjacency[v]:
            weight=weights.get((v,neighbor),0.) if weights is not None else 1.
            if neighbor in lookup:matrix[i,lookup[neighbor]]=-weight
            else:rhs[i]+=weight*uv[neighbor]
    if len(interior):uv[interior]=spsolve(matrix.tocsr(),rhs)
    return interior


def repair(source_mesh,positions,faces,failed_faces,protected_vertices=(),rings=2,subdivide=0,*,protected_edges=(),allow_guide_vertices=False):
    p=np.asarray(positions,float);q=np.asarray(faces,int).copy();patch=set(map(int,failed_faces))
    if not patch:return p,q,dict(applied=False,reason='No failed faces')
    for _ in range(rings):
        vertices=np.unique(q[list(patch)]);patch.update(np.flatnonzero(np.isin(q,vertices).any(1)).tolist())
    ids=np.array(sorted(patch));edges=defaultdict(list)
    for fi in ids:
        for a,b in zip(q[fi],np.roll(q[fi],-1)):edges[tuple(sorted((int(a),int(b))))].append((int(a),int(b)))
    boundary={rows[0][0]:rows[0][1] for rows in edges.values() if len(rows)==1}
    def rejected(reason):return p,np.asarray(faces,int).copy(),dict(applied=False,reason=reason)
    if not boundary:return rejected('No disk boundary')
    ring=[next(iter(boundary))]
    for _ in range(len(boundary)-1):
        if ring[-1] not in boundary:return rejected('Branched boundary')
        ring.append(boundary[ring[-1]])
    if len(set(ring))!=len(boundary) or boundary.get(ring[-1])!=ring[0]:return rejected('Multiple boundary loops')
    vertices=np.unique(q[ids]);interior=np.setdiff1d(vertices,ring)
    if not allow_guide_vertices and set(interior)&set(protected_vertices):return rejected('Protected guide in patch')
    if len(vertices)-len(edges)+len(ids)!=1:return rejected('Output patch is not a disk')
    attached=trimesh.proximity.closest_point(source_mesh,p[ring])[0]
    try:sv,sf,embedding=embed(source_mesh.vertices,source_mesh.faces,[np.r_[attached,attached[:1]]])
    except ValueError as error:return rejected('Source boundary embedding: '+str(error))
    cut={tuple(e) for e in embedding['guideEdges']['0']};edge_faces=defaultdict(list);graph=defaultdict(set)
    for a,b in cut:graph[a].add(b);graph[b].add(a)
    if any(len(neighbors)!=2 for neighbors in graph.values()):return rejected('Source boundary is not a simple cycle')
    distance,attached_ids=cKDTree(sv).query(attached)
    if distance.max()>1e-7 or any(int(v) not in graph for v in attached_ids):return rejected('Boundary samples do not match source cut')
    order=[int(attached_ids[0])]
    while len(order)<len(graph):
        available=graph[order[-1]]-set(order[-2:])
        if not available:return rejected('Source cycle ended early')
        following=min(available)
        if following in order:return rejected('Source boundary has multiple cycles')
        order.append(following)
    if order[0] not in graph[order[-1]]:return rejected('Source cycle does not close')
    if order.index(int(attached_ids[1]))>len(order)/2:order=order[:1]+order[:0:-1]
    ordinal={v:i for i,v in enumerate(order)};mapped=np.array([ordinal[int(v)] for v in attached_ids])
    if np.any(np.diff(mapped)<=0):return rejected('Source boundary order differs from output boundary')
    for i,tri in enumerate(sf):
        for a,b in zip(tri,np.roll(tri,-1)):edge_faces[tuple(sorted((int(a),int(b))))].append(i)
    adjacency=[rows for edge,rows in edge_faces.items() if edge not in cut and len(rows)==2]
    rows=np.array(adjacency);dual=coo_matrix((np.ones(len(rows)),(rows[:,0],rows[:,1])),shape=(len(sf),len(sf))).tocsr()
    count,labels=connected_components(dual,directed=False)
    if count!=2:return rejected('Projected boundary does not separate a source disk')
    candidates=[]
    for group in range(count):
        candidate=np.flatnonzero(labels==group);local=sf[candidate];ve=np.unique(local)
        ee=np.unique(np.sort(np.stack([local,np.roll(local,-1,1)],axis=2).reshape(-1,2),axis=1),axis=0)
        if len(ve)-len(ee)+len(local)==1:candidates.append(candidate)
    if not candidates:return rejected('Neither source component is a disk')
    chosen=min(candidates,key=lambda candidate:trimesh.triangles.area(sv[sf[candidate]]).sum())
    local=sf[chosen];ve=np.unique(local);ee=np.unique(np.sort(np.stack([local,np.roll(local,-1,1)],axis=2).reshape(-1,2),axis=1),axis=0)
    points=sv[order];length=np.linalg.norm(np.roll(points,-1,axis=0)-points,axis=1);angles=2*np.pi*np.r_[0,np.cumsum(length[:-1])]/length.sum()
    source_uv=np.zeros((len(sv),2));source_uv[order]=np.c_[np.cos(angles),np.sin(angles)]
    weights=defaultdict(float)
    for i in range(3):
        a,b,c=local[:,i],local[:,(i+1)%3],local[:,(i+2)%3]
        u=sv[b]-sv[a];w=sv[c]-sv[a];lu=np.linalg.norm(u,axis=1);lw=np.linalg.norm(w,axis=1)
        half=np.linalg.norm(np.cross(u,w),axis=1)/np.maximum(1e-20,lu*lw+(u*w).sum(1))
        for x,y,value in zip(a,b,half/lu):weights[int(x),int(y)]+=value
        for x,y,value in zip(a,c,half/lw):weights[int(x),int(y)]+=value
    harmonic(ve,ee,order,source_uv,weights)
    output_uv=np.zeros((len(p),2));output_uv[ring]=source_uv[attached_ids]
    harmonic(vertices,list(edges),ring,output_uv)
    uv3=np.c_[output_uv,np.zeros(len(p))];local_q=q[ids]
    refinement=[]
    for level in range(subdivide):
        adjacency=defaultdict(set)
        for face in local_q:
            for a,b in zip(face,np.roll(face,-1)):adjacency[int(a)].add(int(b));adjacency[int(b)].add(int(a))
        color={int(local_q[0,0]):0};pending=list(color)
        while pending:
            a=pending.pop()
            for b in adjacency[a]:
                if b not in color:color[b]=1-color[a];pending.append(b)
                elif color[b]==color[a]:return rejected('Patch quad graph is not bipartite')
        selected=[a for a in color if color[a]==level%2 and a not in ring and a not in protected_vertices]
        uv3,local_q,detail=split_vertex_cut(uv3,local_q,selected);refinement.append(detail)
    repaired,flips=improve(uv3,local_q,protected=protected_edges,passes=8);local_q=repaired
    corners=uv3[local_q,:2];following=np.roll(corners,-1,1)-corners;previous=np.roll(corners,1,1)-corners
    cross=following[:,:,0]*previous[:,:,1]-following[:,:,1]*previous[:,:,0]
    if not (np.all(cross>1e-12) or np.all(cross<-1e-12)):return rejected('Output patch UV contains nonconvex quads')
    interior=np.setdiff1d(np.unique(local_q),ring)
    planar=trimesh.Trimesh(np.c_[source_uv,np.zeros(len(sv))],local,process=False)
    closest,distance,owner=trimesh.proximity.closest_point(planar,uv3[interior])
    if distance.max()>1e-7:return rejected('Output samples lie outside source UV patch')
    bary=trimesh.triangles.points_to_barycentric(planar.triangles[owner],closest)
    result=np.zeros((len(uv3),3));result[:len(p)]=p;result[interior]=(sv[local[owner]]*bary[:,:,None]).sum(1)
    result_faces=np.r_[np.delete(q,ids,axis=0),local_q]
    return result,result_faces,dict(applied=True,patchFaces=len(ids),sourcePatchFaces=len(local),interiorVertices=len(interior),edgeRotations=flips,refinement=refinement)
