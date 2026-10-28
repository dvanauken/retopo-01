"""Untangle a local disk using its fixed boundary and visible source surface."""
from collections import defaultdict
import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve
from shapely.geometry import Polygon


def repair(source_mesh,positions,faces,failed_faces,protected_vertices=(),rings=2):
    p=np.asarray(positions,float);q=np.asarray(faces,int);patch=set(map(int,failed_faces))
    for _ in range(rings):
        vertices=np.unique(q[list(patch)]);patch.update(np.flatnonzero(np.isin(q,vertices).any(1)).tolist())
    ids=np.array(sorted(patch));edges=defaultdict(list)
    for fi in ids:
        for a,b in zip(q[fi],np.roll(q[fi],-1)):edges[tuple(sorted((int(a),int(b))))].append((int(a),int(b)))
    boundary={rows[0][0]:rows[0][1] for rows in edges.values() if len(rows)==1}
    if not boundary:return p,dict(applied=False,reason='No disk boundary')
    ring=[next(iter(boundary))]
    for _ in range(len(boundary)-1):
        if ring[-1] not in boundary:return p,dict(applied=False,reason='Branched boundary')
        ring.append(boundary[ring[-1]])
    if len(set(ring))!=len(boundary) or boundary.get(ring[-1])!=ring[0]:return p,dict(applied=False,reason='Multiple boundary loops')
    vertices=np.unique(q[ids]);interior=np.setdiff1d(vertices,ring)
    if set(interior)&set(protected_vertices):return p,dict(applied=False,reason='Protected guide in patch')
    if len(vertices)-len(edges)+len(ids)!=1:return p,dict(applied=False,reason='Patch is not a disk')
    center=p[ring].mean(0);_,_,basis=np.linalg.svd(p[ring]-center,full_matrices=False);normal=basis[2]
    uv=(p-center)@basis[:2].T
    polygon=Polygon(uv[ring])
    if not polygon.is_valid:return p,dict(applied=False,reason='Boundary projection is not simple')
    adjacency=defaultdict(set)
    for a,b in edges:adjacency[a].add(b);adjacency[b].add(a)
    local={int(vertex):i for i,vertex in enumerate(interior)};matrix=lil_matrix((len(interior),len(interior)));rhs=np.zeros((len(interior),2))
    for vertex,i in local.items():
        neighbors=adjacency[vertex];matrix[i,i]=len(neighbors)
        for neighbor in neighbors:
            if neighbor in local:matrix[i,local[neighbor]]=-1
            else:rhs[i]+=uv[neighbor]
    uv[interior]=spsolve(matrix.tocsr(),rhs)
    corners=uv[q[ids]];following=np.roll(corners,-1,1)-corners;previous=np.roll(corners,1,1)-corners
    cross=following[:,:,0]*previous[:,:,1]-following[:,:,1]*previous[:,:,0]
    if not (np.all(cross>1e-12) or np.all(cross<-1e-12)):return p,dict(applied=False,reason='Patch projection contains folded quads')
    # Use the source normals at the boundary to orient the viewing direction.
    import trimesh
    owners=trimesh.proximity.closest_point(source_mesh,p[ring])[2]
    if normal@source_mesh.face_normals[owners].sum(0)<0:normal=-normal
    distance=(np.asarray(source_mesh.vertices)-center)@normal
    origins=center+uv[interior]@basis[:2]+normal*(distance.max()+1.)
    hit,rays,_=source_mesh.ray.intersects_location(origins,np.tile(-normal,(len(interior),1)),multiple_hits=True)
    selected={}
    for index,point in zip(rays,hit):
        d=np.linalg.norm(point-origins[index])
        if index not in selected or d<selected[index][0]:selected[index]=(d,point)
    if len(selected)!=len(interior):return p,dict(applied=False,reason='Some rays miss the source')
    result=p.copy()
    for i,vertex in enumerate(interior):result[vertex]=selected[i][1]
    return result,dict(applied=True,patchFaces=len(ids),interiorVertices=len(interior),normal=normal.tolist())
