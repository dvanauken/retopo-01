"""Source crease measurements, independent of output crease display counts.

The crease angle is a per-job setting. A worker process solves one job, so it
sets the angle once with use_crease_angle() and every detect()/measure() call in
the solvers, fitting and final validation then agrees on the same creases.
"""
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from features import sharp_edges, output_creases
from crease_angle import check as check_angle, DEFAULT as DEFAULT_CREASE_ANGLE

_angle = DEFAULT_CREASE_ANGLE


def use_crease_angle(value):
    """Set this process's default crease angle (one job per worker process)."""
    global _angle
    _angle = check_angle(value)


ADMISSION_BUDGET=(1000,10000)   # ZRemesher clamps the target to this range for the minimum feature length


def admission_length(source, triangles, target):
    """Minimum crease path length S = sqrt(A / clamp(target, 1000, 10000)) (ZRemesher 0x1c9fb0/0x25a990)."""
    source=np.asarray(source,float);triangles=np.asarray(triangles,int)
    area=trimesh.triangles.area(source[triangles]).sum()
    return float(np.sqrt(area/min(max(float(target),ADMISSION_BUDGET[0]),ADMISSION_BUDGET[1])))


def detect(source, triangles, spacing, angle=None, target=None):
    """Separate resolved crease chains from angular fragments too short to keep.

    A connected crease component is kept when its summed edge length reaches the
    admission length (the native rule when `target` is given; otherwise the spacing).
    """
    angle = _angle if angle is None else check_angle(angle)
    source=np.asarray(source);edges=np.asarray(sharp_edges(source,triangles,angle),int).reshape(-1,2)
    minimum=admission_length(source,triangles,target) if target else float(spacing)
    base=dict(angleDegrees=angle,minimumExtent=minimum,minimumLength=minimum)
    if not len(edges):return edges,dict(rawEdges=0,resolvedEdges=0,fragmentEdges=0,chains=0,**base)
    graph=coo_matrix((np.ones(len(edges)),(edges[:,0],edges[:,1])),shape=(len(source),len(source))).tocsr()
    _,labels=connected_components(graph,directed=False)
    keep=np.zeros(len(edges),bool);chains=0;lengths=np.linalg.norm(source[edges[:,1]]-source[edges[:,0]],axis=1)
    for group in np.unique(labels[edges[:,0]]):
        selected=np.flatnonzero(labels[edges[:,0]]==group)
        if lengths[selected].sum()>=minimum:keep[selected]=True;chains+=1
    return edges[keep],dict(rawEdges=len(edges),resolvedEdges=int(keep.sum()),fragmentEdges=int((~keep).sum()),chains=chains,**base)


def segment_distances(points, starts, ends):
    """Exact nearest segment distances; midpoint search has a radius bound."""
    points=np.asarray(points);a=np.asarray(starts);b=np.asarray(ends)
    if not len(a):return np.full(len(points),np.inf)
    centers=(a+b)*.5;tree=cKDTree(centers);radius=np.linalg.norm(b-a,axis=1).max()*.5
    _,seeds=tree.query(points)
    def distances(point,ids):
        d=b[ids]-a[ids]
        t=np.clip(((point-a[ids])*d).sum(-1)/np.maximum(1e-30,(d*d).sum(-1)),0,1)
        return np.linalg.norm(a[ids]+t[...,None]*d-point,axis=-1)
    initial=distances(points,seeds)
    # Any segment closer than the seed must have its midpoint within this
    # radius, by the triangle inequality. Include floating-point boundary ties.
    candidates=tree.query_ball_point(points,initial+radius+1e-12)
    return np.array([distances(point,np.asarray(ids,int)).min() for point,ids in zip(points,candidates)])


def spacing(source, triangles, target):
    """Requested quad edge length: the same rule every solver and check applies."""
    source=np.asarray(source,float);triangles=np.asarray(triangles,int)
    return float(np.sqrt(trimesh.triangles.area(source[triangles]).sum()/target))


def branches(edges):
    """Label crease edges by branch: a chain between junctions or ends, or a closed loop."""
    edges=np.asarray(edges,int).reshape(-1,2);adjacent={}
    for i,(a,b) in enumerate(edges):adjacent.setdefault(a,[]).append((b,i));adjacent.setdefault(b,[]).append((a,i))
    label=np.full(len(edges),-1);count=0
    # Walk from junctions and ends first, so only junction-free loops start mid-chain.
    for start in [n for n,links in adjacent.items() if len(links)!=2]+list(adjacent):
        for node,edge in adjacent[start]:
            if label[edge]>=0:continue
            label[edge]=count
            while len(adjacent[node])==2:
                node,edge=next((n,e) for n,e in adjacent[node] if e!=edge)
                if label[edge]>=0:break
                label[edge]=count
            count+=1
    return label


BAND_REACH=.5
BAND_DEGREES=30.


def band_widths(source, edges, samples, owners, spacing):
    """How far each crease sample's band of nearly parallel creases extends.

    The layout rounds edge lines to a lattice of the requested spacing, so
    creases closer than half of it share one edge loop; creases meeting below
    the 30-degree minimum quad corner cannot both own an edge either. Such a
    band is one feature at this resolution: the width is the farthest other
    branch within reach, and 0 for a crease with no parallel neighbor.
    """
    source=np.asarray(source,float);edges=np.asarray(edges,int).reshape(-1,2);samples=np.asarray(samples,float);owners=np.asarray(owners,int)
    width=np.zeros(len(samples))
    if not len(edges) or not len(samples):return width
    label=branches(edges);a=source[edges[:,0]];d=source[edges[:,1]]-a;length=np.linalg.norm(d,axis=1)
    unit=d/np.maximum(1e-30,length)[:,None];reach=BAND_REACH*spacing
    pairs=cKDTree(a+d*.5).query_ball_point(samples,reach+.5*length.max())
    counts=np.fromiter(map(len,pairs),int,len(pairs))
    i=np.repeat(np.arange(len(samples)),counts);j=np.fromiter((k for ids in pairs for k in ids),int,counts.sum())
    keep=(label[j]!=label[owners[i]])&(np.abs((unit[j]*unit[owners[i]]).sum(1))>=np.cos(np.radians(BAND_DEGREES)))
    i,j=i[keep],j[keep]
    t=np.clip(((samples[i]-a[j])*d[j]).sum(1)/np.maximum(1e-30,length[j]**2),0,1)
    distance=np.linalg.norm(samples[i]-a[j]-t[:,None]*d[j],axis=1)
    # Nearest point of each other branch, then the farthest such branch in reach.
    key=i*(label.max()+1)+label[j];order=np.lexsort((distance,key))
    first=order[np.r_[True,key[order][1:]!=key[order][:-1]]] if len(order) else order
    first=first[distance[first]<reach]
    np.maximum.at(width,i[first],distance[first])
    return width


def measure(source, triangles, vertices, faces, target, angle=None):
    source=np.asarray(source,float);vertices=np.asarray(vertices,float)
    triangles=np.asarray(triangles,int);faces=np.asarray(faces,int)
    h=spacing(source,triangles,target)
    edges,detection=detect(source,triangles,h,angle,target)
    # Limits are in requested faces at every count: 95% of each crease lies within a
    # quarter face of an edge loop and of an output crease, no crease point runs
    # through the middle of a face, and an output crease and a vertex lie within one
    # face of every crease point and junction.
    limits=dict(edgeP95=.25*h,edgeMax=.5*h,creaseP95=.25*h,creaseMax=1.*h,junctionMax=1.*h)
    if not len(edges):return dict(passed=True,detection=detection,sourceFeatureEdges=0,limits=limits,failures=[],scope=f"No {detection['angleDegrees']:g}-degree source crease components at or above one requested edge spacing; smaller angular fragments are reported separately.")
    counts=[max(5,int(np.ceil(np.linalg.norm(source[b]-source[a])/(h*.125)))+1) for a,b in edges]
    samples=np.concatenate([np.linspace(source[a],source[b],count) for (a,b),count in zip(edges,counts)])
    band=band_widths(source,edges,samples,np.repeat(np.arange(len(edges)),counts),h)
    output_edges=np.unique(np.sort(np.stack([faces,np.roll(faces,-1,1)],axis=2).reshape(-1,2),axis=1),axis=0)
    creases=np.asarray(output_creases(vertices,faces.tolist(),angle_degrees=30)['edges'],int).reshape(-1,2)
    # An edge anywhere across a sub-spacing band of parallel creases represents it.
    distance=np.maximum(0,segment_distances(samples,vertices[output_edges[:,0]],vertices[output_edges[:,1]])-band)
    crease_distance=np.maximum(0,segment_distances(samples,vertices[creases[:,0]],vertices[creases[:,1]])-band)
    degree=np.bincount(edges.ravel(),minlength=len(source));junctions=source[degree>=3]
    junction_distance=cKDTree(vertices).query(junctions)[0] if len(junctions) else np.array([0.])
    values=dict(edgeP95=float(np.percentile(distance,95)),edgeMax=float(distance.max()),
                creaseP95=float(np.percentile(crease_distance,95)),creaseMax=float(crease_distance.max()),junctionMax=float(junction_distance.max()))
    failures=[key for key,value in values.items() if value>limits[key]]
    # JSON must stay finite even if the output has no detectable crease edges.
    values={key:value if np.isfinite(value) else None for key,value in values.items()}
    return dict(passed=not failures,detection=detection,sourceFeatureEdges=len(edges),outputCreaseEdges=len(creases),samples=len(samples),
                bandSamples=int((band>0).sum()),bandWidthMax=float(band.max()),
                sourceJunctions=len(junctions),values=values,limits=limits,failures=failures,
                scope=f"Sampled {detection['angleDegrees']:g}-degree source crease components whose extent is at least one requested edge spacing, to output edges and 30-degree output creases; retained source junctions to output vertices. Smaller angular fragments are counted separately. Creases within {BAND_REACH:g} spacing of another crease branch running within {BAND_DEGREES:g} degrees of parallel form one band; their distances are measured beyond the band's local width. Exact point-to-segment distances; sampling does not certify every point of each feature. Whole-surface, topology, guide and contact checks are separate.")
