"""Local connectivity and fitting stages for independently verified feature quads."""
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from source_features import detect,segment_distances
from quad_connectivity import split_vertex_stars,split_vertex_cut
from surface_patch import repair as repair_disk
from contact_constraints import nearby_pairs
from features import output_creases
import curved_quad as cq


def witnesses(report):
    surface=report.get('surface',{});result=[]
    tolerance=surface.get('sampledSurfaceTolerance',float('inf'))
    for key in ('sourceToOutput','outputToSource'):
        item=surface.get(key,{})
        if item.get('sampledMax',0)>tolerance and item.get('witness') is not None:result.append(item['witness'])
    for bound in surface.get('wholeSurfaceDiagonals',{}).values():
        for key in ('sourceToOutput','outputToSource'):
            item=bound[key]
            if not item['passed'] and item.get('witness') is not None:result.append(item['witness'])
    return result


def refine_features(source,p,q,paths,target):
    h=float(np.sqrt(source.area/target));v=np.asarray(source.vertices);f=np.asarray(source.faces)
    feature_edges,_=detect(v,f,h)
    if not len(feature_edges):return p,q,dict(addedFaces=0)
    samples=np.concatenate([np.linspace(v[a],v[b],5) for a,b in feature_edges]);edges=cq._edges(q)
    distances=segment_distances(samples,p[edges[:,0]],p[edges[:,1]])
    protected={vertex for path in paths for vertex in path['vertices']}
    mesh=trimesh.Trimesh(p,np.r_[q[:,[0,1,2]],q[:,[0,2,3]]],process=False)
    owners=trimesh.proximity.closest_point(mesh,samples)[2]%len(q);selected=[]
    for i in np.argsort(-distances):
        if distances[i]<=.18*h:break
        face=q[owners[i]];node=int(face[np.argmin(np.linalg.norm(p[face]-samples[i],axis=1))])
        if node not in protected and node not in selected:selected.append(node)
    return split_vertex_stars(p,q,selected,int(target*1.125))


def refine_guides(p,q,paths,target,curves=None,spacing=None):
    # A conforming cut doubles the guide's edge resolution while sharing new
    # vertices with neighboring faces. Keep the same authored path identities.
    selected={v for path in paths for v in path['vertices'][:-1:2]}
    candidate,faces,detail=split_vertex_cut(p,q,selected)
    if len(faces)>target*1.15:
        # Spend a bounded face budget on the largest local guide errors. A
        # long good path must not prevent a short bad path from being refined.
        score={vertex:0. for vertex in selected}
        for index,path in enumerate(paths):
            pe=np.array(list(zip(path['vertices'][:-1],path['vertices'][1:])))
            a=p[pe[:,0]];d=p[pe[:,1]]-a;length=np.linalg.norm(d,axis=1)
            error=length.copy()
            if curves is not None and spacing is not None:
                points=cq._sample(np.asarray(curves[index]),257);tangent=np.gradient(points,axis=0)
                tangent/=np.maximum(1e-12,np.linalg.norm(tangent,axis=1))[:,None]
                t=np.clip(((points[:,None]-a)*d).sum(2)/np.maximum(1e-20,length**2),0,1)
                distance=np.linalg.norm(points[:,None]-a-t[:,:,None]*d,axis=2);ids=distance.argmin(1)
                angle=np.degrees(np.arccos(np.clip(np.abs((tangent*d[ids]/np.maximum(1e-12,length[ids,None])).sum(1)),0,1)))
                severity=np.maximum(distance[np.arange(len(points)),ids]/(.2*spacing),angle/30.)
                error=np.zeros(len(pe));np.maximum.at(error,ids,severity)
            for (a,b),value in zip(pe,error):
                for node in (a,b):
                    if node in score:score[node]=max(score[node],float(value))
        selected=set()
        for vertex in sorted(score,key=lambda node:(-score[node],node)):
            proposed=selected|{vertex};flags=np.isin(q,list(proposed));split=flags^np.roll(flags,-1,1);count=split.sum(1)
            adjacent=(split&np.roll(split,1,1)).any(1)
            extra=np.where(count==4,3,np.where(count==2,np.where(adjacent,2,1),0)).sum()
            if len(q)+extra<=target*1.15:selected=proposed
        candidate,faces,detail=split_vertex_cut(p,q,selected)
        detail['budgeted']=True
    mid={tuple(sorted((a,b))):v for a,b,v in detail.pop('edgeVertices')}
    result=[]
    for path in paths:
        old=path['vertices'];new=[old[0]]
        for a,b in zip(old[:-1],old[1:]):
            node=mid.get(tuple(sorted((a,b))))
            if node is not None:new.append(node)
            new.append(b)
        result.append(dict(vertices=new,closed=path['closed']))
    return candidate,faces,result,detail


def guide_region(q,paths,rings=2):
    active=np.unique([v for path in paths for v in path['vertices']])
    for _ in range(rings):active=np.unique(q[np.isin(q,active).any(1)])
    return active


def repair_contacts(source,p,q,paths,contact,rings=2,subdivide=0):
    failed=np.unique(contact['nonAdjacentIntersectingFacePairs']+contact['adjacentIntersectingFacePairs'])
    protected={vertex for path in paths for vertex in path['vertices']}
    protected_edges=[(a,b) for path in paths for a,b in zip(path['vertices'][:-1],path['vertices'][1:])]
    # Distant contact regions need separate source disks, not one boundary with
    # several disconnected loops. Group by overlapping local face neighborhoods.
    neighborhoods=[]
    for face in failed:
        patch={int(face)}
        for _ in range(rings):patch.update(np.flatnonzero(np.isin(q,np.unique(q[list(patch)])).any(1)).tolist())
        neighborhoods.append((patch,{int(face)}))
    groups=[]
    while neighborhoods:
        patch,seeds=neighborhoods.pop();changed=True
        while changed:
            changed=False
            for i in range(len(neighborhoods)-1,-1,-1):
                if patch&neighborhoods[i][0]:
                    other,ids=neighborhoods.pop(i);patch.update(other);seeds.update(ids);changed=True
        groups.append(seeds)
    reasons=[]
    for seeds in sorted(groups,key=lambda g:-len(g)):
        positions,faces,detail=repair_disk(source,p,q,sorted(seeds),protected,rings,subdivide,protected_edges=protected_edges,allow_guide_vertices=True)
        if not detail['applied']:reasons.append(detail['reason']);continue
        changed=np.r_[np.flatnonzero(np.linalg.norm(positions[:len(p)]-p,axis=1)>1e-12),np.arange(len(p),len(positions))]
        active=np.unique(faces[np.isin(faces,changed).any(1)])
        detail.update(contactRegions=len(groups),guideVerticesInRegion=len(set(active)&protected))
        return positions,faces,active,detail
    return p,q,np.array([],int),dict(applied=False,reason='; '.join(reasons),contactRegions=len(groups))


def contact_neighborhood(p,q,h,active=None):
    faces=None if active is None else np.flatnonzero(np.isin(q,active).any(1))
    return nearby_pairs(p,q,.1*h,faces)


def local_surface_samples(source,p,q,target,active):
    """Find multiple local distance constraints before the next global audit.

    These samples guide fitting only; independent whole-triangle bounds still
    decide acceptance. Sampling both diagonals avoids repairing one witness
    while an adjacent point on the same warped quad remains too far away.
    """
    from mesh_proximity import TriangleProximity
    faces=q[np.isin(q,active).any(1)]
    if not len(faces):return []
    triangles=np.r_[faces[:,[0,1,2]],faces[:,[0,2,3]],faces[:,[1,2,3]],faces[:,[1,3,0]]]
    bary=np.array([[a/4,b/4,1-(a+b)/4] for a in range(5) for b in range(5-a)])
    points=np.unique(np.einsum('bi,tic->tbc',bary,p[triangles]).reshape(-1,3),axis=0)
    distance,_=TriangleProximity(np.asarray(source.vertices),np.asarray(source.faces)).query(points)
    h=np.sqrt(source.area/target)
    return points[distance>.42*h].tolist()


def failure_points(source,p,q,target,report):
    """Failed source-feature samples and surface-distance witnesses."""
    h=float(np.sqrt(source.area/target));v=np.asarray(source.vertices);f=np.asarray(source.faces)
    edges,_=detect(v,f,h);points=list(witnesses(report));feature=report.get('features',{})
    if len(edges) and feature and not feature['passed']:
        samples=np.concatenate([np.linspace(v[a],v[b],max(5,int(np.ceil(np.linalg.norm(v[b]-v[a])/(h*.125)))+1)) for a,b in edges])
        oe=cq._edges(q);distance=segment_distances(samples,p[oe[:,0]],p[oe[:,1]])
        threshold=feature['limits']['edgeP95'] if 'edgeP95' in feature['failures'] else feature['limits']['edgeMax']*.9
        selected=distance>threshold
        if any(key.startswith('crease') for key in feature['failures']):
            creases=np.asarray(output_creases(p,q.tolist(),angle_degrees=30)['edges'],int).reshape(-1,2)
            d=segment_distances(samples,p[creases[:,0]],p[creases[:,1]])
            threshold=feature['limits']['creaseP95'] if 'creaseP95' in feature['failures'] else feature['limits']['creaseMax']*.9
            selected|=d>threshold
        points.extend(samples[selected])
        if 'junctionMax' in feature['failures']:
            degree=np.bincount(edges.ravel(),minlength=len(v));junctions=v[degree>=3]
            distance=cKDTree(p).query(junctions)[0]
            points.extend(junctions[distance>feature['limits']['junctionMax']*.9])
    return np.asarray(points,float).reshape(-1,3)


def refine_failures(source,p,q,paths,target,report):
    """Add local resolution where crease or whole-surface gates still fail."""
    points=failure_points(source,p,q,target,report)
    if not len(points):return p,q,dict(addedFaces=0)
    protected={vertex for path in paths for vertex in path['vertices']}
    tri=np.r_[q[:,[0,1,2]],q[:,[0,2,3]],q[:,[1,2,3]],q[:,[1,3,0]]]
    mesh=trimesh.Trimesh(p,tri,process=False)
    owners=trimesh.proximity.closest_point(mesh,points)[2]%len(q);selected=[]
    for point,owner in zip(points,owners):
        nodes=q[owner];nodes=nodes[np.argsort(np.linalg.norm(p[nodes]-point,axis=1))]
        node=next((int(node) for node in nodes if node not in protected),None)
        if node is not None and node not in selected:selected.append(node)
    return split_vertex_stars(p,q,selected,int(target*1.15))


def failure_region(source,p,q,target,report):
    """Vertices near failed source-feature samples and surface witnesses."""
    points=failure_points(source,p,q,target,report)
    if not len(points):return np.array([],int)
    tri=np.r_[q[:,[0,1,2]],q[:,[0,2,3]],q[:,[1,2,3]],q[:,[1,3,0]]]
    mesh=trimesh.Trimesh(p,tri,process=False);owners=trimesh.proximity.closest_point(mesh,np.asarray(points))[2]%len(q)
    active=np.unique(q[owners])
    for _ in range(2):active=np.unique(q[np.isin(q,active).any(1)])
    return active
