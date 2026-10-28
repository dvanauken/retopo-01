"""Boundary-preserving QuadriFlow generation for original manifold open parts.

Input geometry remains immutable. Layout and fitting are separate candidates;
acceptance requires quality, topology, guides, boundaries, features, surface
coverage on both quad diagonals, and face-contact checks together.
"""
from pathlib import Path
import json
import subprocess
import time
import numpy as np
import trimesh
import curved_quad as cq
from guided_layout import runtime, obj, write, sha
from feature_refine import refine
from boundary_geometry import loops, correspondence, closest, fit_ring, conform_ring
from source_features import detect, measure as measure_features, segment_distances
from quad_connectivity import dissolve_double_edges, collapse_polychords, clean_slivers, vertex_stars, weld_pinched_quads, fill_triangle_holes
from measure_geometry import read_obj
from features import output_creases
from job_progress import emit
from job_diagnostics import candidate_message, outcome, summarize


class OpenSurfaceRejected(ValueError):
    def __init__(self, rows):
        self.diagnostics = summarize(rows)
        super().__init__(self.diagnostics['message'])


def conform_boundaries(source, triangles, p, q, h):
    """Map output boundary cycles onto the source boundary without cutting its bends."""
    mapping=correspondence(source,triangles,p,q)
    for output_ring,source_ring in mapping:
        original=p[output_ring].copy();ring=source[source_ring]
        projected=closest(original,ring)[0]
        if np.any(np.linalg.norm(np.roll(projected,-1,axis=0)-projected,axis=1)<1e-12):projected=fit_ring(original,ring)
        p[output_ring]=conform_ring(projected,ring,.1*h)
    return mapping


def quad_vertex_normals(p, q):
    """Area-weighted quad normals summed at each vertex, unit length."""
    n=np.cross(p[q[:,2]]-p[q[:,0]],p[q[:,3]]-p[q[:,1]]);result=np.zeros_like(p)
    for k in range(4):np.add.at(result,q[:,k],n)
    return result/np.maximum(1e-30,np.linalg.norm(result,axis=1))[:,None]


def marked_segments(source, feature_edges, curves):
    """Source crease edges and user guide polylines as one list of segments (starts, ends)."""
    starts=[source[np.asarray(feature_edges,int).reshape(-1,2)[:,0]]]+[np.asarray(c,float)[:-1] for c in curves]
    ends=[source[np.asarray(feature_edges,int).reshape(-1,2)[:,1]]]+[np.asarray(c,float)[1:] for c in curves]
    return np.concatenate(starts),np.concatenate(ends)


def marked_edges(p, q, segments, spacing):
    """Output edges lying along a marked segment (crease or guide): both ends within 0.15 spacing of it.

    Native marks are topological (edges embedded from the guide); without
    embedding this proximity test is the stand-in, declared as such.
    """
    edges=cq._edges(q)
    if segments is None or not len(segments[0]) or not spacing:return edges,np.zeros(len(edges),bool)
    near=segment_distances(p,segments[0],segments[1])<.15*spacing
    return edges,near[edges[:,0]]&near[edges[:,1]]


def slide_to_marks(candidate, current, a, b):
    """ZRemesher 2b5330: nearer point on the two marked segments a-current and b-current."""
    best=None
    for end in (a,b):
        d=current-end;t=np.clip((candidate-end)@d/max(1e-30,d@d),0,1);point=end+t*d;distance=np.linalg.norm(candidate-point)
        if best is None or distance<best[0]:best=(distance,point)
    return best[1]


# Relaxation policy switches. Native marks are embedded edges and native projection is a
# surface walk; without those, vertices near a crease must stay put or the rim lip folds.
FREEZE_NEAR_MARKS=True     # engineering stand-in for native marks + walk
RELAX_BAND=(.5,1.2)        # native per-edge band with the field scale (2.5 variant gated by an unrecovered flag)
RELAX_EVERY_PASS=False     # native relaxes once, last; here after fit pass 1 unless set


def relax(mesh, p, q, fixed, rounds=3, segments=None, spacing=None):
    """Output relaxation by the rules recovered from ZRemesher (0x317430, 0x29e080, 0x29d240).

    Regular (valence-four) vertices move 0.33 toward the mean of the balanced
    candidates of their two opposite-neighbor pairs, each edge length clamped to
    [0.5, 1.2] times the spacing (native per-edge band with the field scale; the
    2.5 upper variant is gated by an unrecovered face flag). Irregular vertices
    move 0.4 toward their neighbor average. A vertex with two marked edges keeps
    to the nearer of those edges; other nonzero mark counts and vertices in
    `fixed` do not move; a regular vertex whose marked edges are not one
    opposite pair does not move. Moves are projected to the source surface
    (nearest point on the facing sheet; the native surface walk is not ported).
    """
    p=np.asarray(p,float).copy();q=np.asarray(q,int);fixed=np.asarray(fixed,bool).copy()
    if FREEZE_NEAR_MARKS and segments is not None and len(segments[0]) and spacing:
        fixed|=segment_distances(p,segments[0],segments[1])<.15*spacing
    edges,marked=marked_edges(p,q,segments,spacing);mark_lookup={tuple(e):m for e,m in zip(map(tuple,np.sort(edges,1)),marked)}
    stars=vertex_stars(q);regular=[];irregular=[];guided={}
    for vertex,star in stars.items():
        if fixed[vertex] or not star:continue
        ring,closed=star;marks=[mark_lookup[tuple(sorted((vertex,n)))] for n in ring]
        if closed and len(ring)==4:
            pairs=[(0,2),(1,3)];counts=[marks[i]+marks[j] for i,j in pairs]
            if tuple(counts) not in ((0,0),(2,0),(0,2)):continue
            regular.append([vertex,*ring])
            if any(counts):i,j=pairs[counts.index(2)];guided[vertex]=(ring[i],ring[j])
        else:
            count=sum(marks)
            if count not in (0,2):continue
            irregular.append((vertex,ring))
            if count==2:guided[vertex]=tuple(n for n,m in zip(ring,marks) if m)
    regular=np.asarray(regular,int).reshape(-1,5)
    low,high=(RELAX_BAND[0]*spacing,RELAX_BAND[1]*spacing) if spacing else (0.,np.inf)
    from source_projection import OrientedSurface
    projector=OrientedSurface(mesh)
    for _ in range(rounds):
        goal=p.copy()
        if len(regular):
            v=regular[:,0];candidate=np.zeros((len(v),3))
            for i,j in ((1,3),(2,4)):
                n0,n1=p[regular[:,i]],p[regular[:,j]]
                l0=np.clip(np.linalg.norm(p[v]-n0,axis=1),low,high);l1=np.clip(np.linalg.norm(p[v]-n1,axis=1),low,high)
                w=(l0/np.maximum(1e-30,l0+l1))[:,None];candidate+=(n0*(1-w)+n1*w)*.5
            goal[v]=p[v]+.33*(candidate-p[v])
        for vertex,ring in irregular:
            goal[vertex]=p[vertex]+.4*(p[ring].mean(0)-p[vertex])
        for vertex,(a,b) in guided.items():
            goal[vertex]=slide_to_marks(goal[vertex],p[vertex],p[a],p[b])
        goal[fixed]=p[fixed];ids=np.flatnonzero((goal!=p).any(1)&~np.isin(np.arange(len(p)),list(guided)))
        if len(ids):
            normals=quad_vertex_normals(p,q);goal[ids]=projector.closest(goal[ids],normals[ids])[0]
        p=goal
    return p


def coarsen(mesh, source, triangles, p, q, curves, target, fine_target, feature_edges):
    """Fit a finer layout onto its creases and guides, then collapse whole quad strips to the target.

    Direct coarse layouts often have no edge loop on a crease; the finer layout
    has one, and strip collapse keeps every loop it does not remove.
    """
    fine_h=float(np.sqrt(mesh.area/fine_target));h=float(np.sqrt(mesh.area/target))
    def distance(points):
        if not len(feature_edges):return np.full(len(points),np.inf)
        return segment_distances(points,source[feature_edges[:,0]],source[feature_edges[:,1]])
    boundary=np.unique(np.concatenate(loops(q)));active=np.setdiff1d(np.arange(len(p)),boundary)
    for _ in range(2):
        paths=[cq._guide_path(p,cq._edges(q),curve,fine_h)[0] for curve in curves]
        p,_=refine(mesh,p,q,curves,fine_target,paths,active_vertices=active,allow_boundary=True,dense_features=True)
    guides=[v for curve in curves for v in cq._guide_path(p,cq._edges(q),curve,fine_h)[0]['vertices']]
    protected=np.union1d(np.flatnonzero(distance(p)<.15*fine_h),np.asarray(guides,int))
    p,q,detail=collapse_polychords(p,q,target,protected=protected,keep_apart=protected,spacing=h,feature_distance=distance)
    p,q,_=dissolve_double_edges(p,q);q=np.asarray(q,int)
    conform_boundaries(source,triangles,p,q,h)
    fixed=np.zeros(len(p),bool);fixed[np.concatenate(loops(q))]=True;fixed[distance(p)<.15*h]=True
    return relax(mesh,p,q,fixed,rounds=3,segments=marked_segments(source,feature_edges,curves),spacing=h),q,detail


def construct(source, triangles, curves, *, target, job):
    source=np.asarray(source,float); triangles=np.asarray(triangles,int); curves=[np.asarray(c,float) for c in curves]
    mesh=trimesh.Trimesh(source,triangles,process=False); rings=loops(triangles)
    if not rings or not mesh.is_winding_consistent or np.any(mesh.area_faces<=0):
        raise ValueError('Open-part generation requires a nondegenerate, consistently wound manifold source with boundary loops.')
    if isinstance(target,bool) or not isinstance(target,(int,np.integer)) or not 150<=target<=12000:
        raise ValueError('Target must be an integer from 150 to 12,000.')
    job=Path(job); out=job/'open-surface';out.mkdir(); executable,env,engine=runtime();env['OMP_NUM_THREADS']='4'
    h=float(np.sqrt(mesh.area/target)); feature_edges,detection=detect(source,triangles,h,target=target); segments=[]
    emit(job,f"Auto guides: {detection['resolvedEdges']} crease edges in {detection['chains']} chains at {detection['angleDegrees']:g}° or sharper guide the layout; {detection['fragmentEdges']} edges in fragments smaller than one quad are ignored.",kind='stage',details=detection)
    for ci,curve in enumerate(curves):
        if curve.ndim!=2 or curve.shape[1]!=3 or len(curve)<2 or not np.isfinite(curve).all() or np.any(np.linalg.norm(np.diff(curve,axis=0),axis=1)==0):
            raise ValueError('Guides need distinct consecutive finite surface samples.')
        owners=trimesh.proximity.closest_point(mesh,(curve[:-1]+curve[1:])*.5)[2]
        segments.extend([[ci,*a,*b,*n] for a,b,n in zip(curve[:-1],curve[1:],mesh.face_normals[owners])])
    for ci,(a,b) in enumerate(feature_edges,len(curves)):
        normal=mesh.vertex_normals[[a,b]].mean(0); length=np.linalg.norm(normal)
        if length>1e-12:segments.append([ci,*source[a],*source[b],*(normal/length)])
    obj(out/'source.obj',source,triangles)
    for name,rows in (('segments.txt',segments),('guide-segments.txt',[row for row in segments if row[0]<len(curves)])):
        with (out/name).open('w') as stream:
            stream.write(str(len(rows))+'\n')
            for row in rows:stream.write(' '.join(format(float(x),'.17g') for x in row)+'\n')
    files=[Path(__file__),Path(cq.__file__),Path(refine.__code__.co_filename),Path(__file__).with_name('boundary_geometry.py'),Path(__file__).with_name('quad_connectivity.py')]
    hashes={str(f):sha(f) for f in files};history=[];started=time.monotonic()
    write(out/'settings.json',dict(target=int(target),sourceBoundaryLoops=len(rings),sourceHashes=hashes,features=detection,engine=engine))
    # Size-capped layouts first, then crease-constrained ones at uniform size, then
    # QuadriFlow's own adaptive scale without crease constraints, and last finer layouts
    # coarsened by strip collapse. Engineering plan, not a native stage.
    fine=min(12000,max(2*int(target),700))
    # 'caps' = ZRemesher's anisotropic curvature size caps inside the layout engine (-size-caps),
    # measured beside the admitted creases as native does; the caps raise the count above the
    # request, so the request is corrected twice from the counts actually returned.
    plan=[(seed,int(target),'caps') for seed in (2,0)]+[(seed,int(target),'constrained') for seed in (2,0,1)]+[(seed,int(target),'adaptive') for seed in (2,0,1,3)]
    plan+=[(seed,fine,'constrained') for seed in (2,0,1)] if fine>=1.5*target else []
    for attempt,(seed,layout_target,style) in enumerate(plan):
        folder=out/f'layout-{attempt}';folder.mkdir()
        command=[str(executable),'-i',str(out/'source.obj'),'-o',str(folder/'layout.obj'),'-f',str(layout_target),'-seed',str(seed),'-boundary']
        guides=out/('segments.txt' if style!='adaptive' else 'guide-segments.txt')
        command+=['-sharp'] if style=='constrained' else ['-sharp','-size-caps-exact'] if style=='caps' else ['-adaptive']
        if segments if style!='adaptive' else curves:command+=['-guides',str(guides),'-guide-width','.75','-orientation-weight','1','-position-weight','0']
        coarse=layout_target!=target
        write(folder/'command.json',command)
        cq._progress(job,f'Building open-part layout {attempt+1}'+(f' at {layout_target:,} quads to coarsen to {target:,}' if coarse else ' with curvature size caps' if style=='caps' else ' with curvature-adaptive sizing' if style=='adaptive' else '')+f'; preserving {len(rings)} boundary loops')
        requests=3 if style=='caps' else 2;requested=layout_target
        for retry in range(requests):
            with (folder/'native.log').open('a') as log:
                process=subprocess.run(command,env=env,stdout=log,stderr=log,timeout=150,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if process.returncode or retry==requests-1:break
            # Guides and sizing both move the count; ask again for the request that would have hit the target.
            actual=sum(1 for line in (folder/'layout.obj').open() if line.startswith('f '))
            if actual and abs(actual-layout_target)>.12*layout_target:
                requested=max(1,round(requested*layout_target/actual));command[command.index('-f')+1]=str(requested);write(folder/'command.json',command)
            else:break
        if process.returncode:
            row=dict(attempt=attempt,error=f'Native layout failed (exit {process.returncode})');history.append(row)
            write(out/'history.json',history);emit(job,candidate_message(row),level='warning',kind='candidate');continue
        try:
            p,q=read_obj(folder/'layout.obj');q=np.asarray(q,int)
            if q.ndim!=2 or q.shape[1]!=4:raise ValueError('The native layout did not return quads.')
            p,q,connectivity=dissolve_double_edges(p,q)
            # Engine extraction artefacts: a zero-area quad pinched between the copies of a split
            # vertex, and three-sided holes where no quad was extracted (engineering repairs).
            p,q,pinched=weld_pinched_quads(p,q);p,q,holes=fill_triangle_holes(p,q,len(rings));connectivity.update(pinched,**holes);q=np.asarray(q,int)
            # Put boundary vertices on the source's bends so coarse layouts do not cut them.
            conform_boundaries(source,triangles,p,q,float(np.sqrt(mesh.area/layout_target)))
            if coarse:
                cq._progress(job,f'Coarsening open-part layout {attempt+1} from {len(q):,} quads by whole strips')
                p,q,detail=coarsen(mesh,source,triangles,p,q,curves,target,layout_target,feature_edges)
                write(folder/'coarsened.json',detail)
            marked=marked_segments(source,feature_edges,curves)
            mapping=correspondence(source,triangles,p,q)
            boundary=np.unique(np.concatenate([r for r,_ in mapping]));active=np.setdiff1d(np.arange(len(p)),boundary)
            fixed=p[boundary].copy();contacts=set();witnesses=[]
            for iteration in range(5):
                paths=[cq._guide_path(p,cq._edges(q),curve,h)[0] for curve in curves]
                if iteration:
                    cq._progress(job,f'Fitting open part, pass {iteration}; boundaries fixed')
                    # Fit creases at the verifier's 1/8-spacing sampling, so no
                    # unfitted point between sparse samples decides the maximum.
                    p,detail=refine(mesh,p,q,curves,target,paths,contacts=sorted(contacts),witnesses=witnesses,
                                    active_vertices=active,allow_boundary=True,dense_features=True)
                    if not np.array_equal(p[boundary],fixed):raise ValueError('A fit moved a fixed source boundary.')
                    if iteration==1:
                        # Needle quads, which no fit can shape, are collapsed once vertices sit on
                        # their creases and guides (engineering step; native has no such cleanup).
                        on_marked=segment_distances(p,marked[0],marked[1])<.15*h if len(marked[0]) else np.zeros(len(p),bool)
                        p,q,cleaned=clean_slivers(p,q,protected=np.flatnonzero(on_marked),ratio=np.inf);write(folder/'cleanup.json',dict(cleaned,**connectivity))
                        if cleaned['collapsedSlivers']:
                            conform_boundaries(source,triangles,p,q,h);mapping=correspondence(source,triangles,p,q)
                            boundary=np.unique(np.concatenate([r for r,_ in mapping]));active=np.setdiff1d(np.arange(len(p)),boundary);contacts=set()
                    if iteration==1 or RELAX_EVERY_PASS:
                        still=np.zeros(len(p),bool);still[boundary]=True
                        p=relax(mesh,p,q,still,rounds=3,segments=marked,spacing=h);fixed=p[boundary].copy()
                        paths=[cq._guide_path(p,cq._edges(q),curve,h)[0] for curve in curves]
                quality=cq.quad_quality(p,q,target);fit=cq._guide_fit(p,paths,curves,h)
                row=dict(attempt=attempt,iteration=iteration,quality=quality,guideFit=fit,passed=False);history.append(row)
                obj(folder/f'candidate-{iteration}.obj',p,q)
                if quality['passed']:
                    cq._progress(job,'Checking open-part boundaries, features, coverage and contacts')
                    feature=measure_features(source,triangles,p,q,target)
                    contact=cq.surface_intersections(p,q,both_quad_diagonals=True)
                    surface=cq.validate_surface(source,triangles,p,q,target,accelerated=True,allow_boundary=True)
                    row.update(feature=feature,contacts=contact,surface=surface,guidesPassed=bool(cq.guides_pass(fit,h)))
                    row['passed']=bool(feature['passed'] and contact['passed'] and surface['passed'] and row['guidesPassed'])
                    if row['passed']:
                        emit(job,candidate_message(row),kind='candidate',details=outcome(row))
                        metadata=dict(backend=cq.BACKEND,target=int(target),guideMode=2,closedValidation=surface,guidePaths=fit,
                                      intersectionValidation=contact,featureValidation=feature,outputCreases=output_creases(p,q.tolist()),
                                      boundaryValidation=surface['boundaryValidation'],sourceHashes=hashes,layoutEngine=engine,
                                      openSurface=True,elapsedSeconds=time.monotonic()-started,
                                      limitations=['Original boundary topology is preserved; no caps are added.','Boundary and whole-surface deviations are bounded relative to requested spacing.'])
                        write(out/'history.json',history);write(job/'surface-solver.json',metadata)
                        return p,q.tolist(),metadata
                    contacts.update(tuple(pair) for key in ('nonAdjacentIntersectingFacePairs','adjacentIntersectingFacePairs') for pair in contact[key])
                    for bounds in surface['wholeSurfaceDiagonals'].values():
                        for item in (bounds['sourceToOutput'],bounds['outputToSource']):
                            if not item['passed'] and item.get('witness') is not None:witnesses.append(item['witness'])
                    if not surface['checks']['sampledSurface']:
                        witnesses.extend(surface[key]['witness'] for key in ('sourceToOutput','outputToSource') if surface[key].get('witness') is not None)
                emit(job,candidate_message(row),level='warning',kind='candidate',details=outcome(row))
                write(out/'history.json',history)
        except ValueError as error:
            history.append(dict(attempt=attempt,error=str(error)));write(out/'history.json',history)
            emit(job,f'Layout {attempt+1} could not be used: {error}',level='warning',kind='candidate')
    raise OpenSurfaceRejected(history)
