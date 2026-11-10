"""Boundary-preserving QuadriFlow generation for original manifold open parts.

Input geometry remains immutable. Layout and fitting are separate candidates;
acceptance requires quality, topology, guides, boundaries, features, surface
coverage on both quad diagonals, and face-contact checks together.
"""
from pathlib import Path
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
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
from crease_rows import find_row, measure as measure_crease_rows
import guide_rows


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
            pairs=[(0,2),(1,3)];counts=[int(marks[i])+int(marks[j]) for i,j in pairs]
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


ENGINE_SHARP_DEGREES=60.   # QuadriFlow's own sharp-edge dihedral (ComputeSharpEdges), kept for creases outside row bands
# Search budget for layouts with constrained guide and crease edges; engineering policy, not an
# acceptance rule. One engine layout takes about a second and most seeds do not put a row on every
# crease and guide that needs one, so layouts are screened before fitting and the seeds are tried
# in order, twice: 'rows' fits the layouts whose rows already meet the quarter-face row limit
# unfitted, then 'rows-wide' fits the remaining ones whose rows are within the half-face row
# maximum. 64 seeds: with the guide of job 483afe83, island 6 at 200 is first accepted at seed 52,
# and the first pass, which mostly screens, reaches it in about a minute.
ROW_LAYOUT_SEEDS=64
ROW_SEARCH_SECONDS=360
ROW_SETTLE_PASSES=2   # a rows layout whose quad shape or crease rows still fail after this many fits is dropped for the next seed
ROW_STYLES=('rows','rows-wide')
ROW_BATCH=8   # rows layouts laid out together; each engine process keeps its four threads


def run_engine(command, env, folder, requests, layout_target, timeout, extra_faces=False):
    """Run the layout engine: (timed out, exit code). `command` is updated in place when the count is asked again.

    Guides and sizing both move the count, so up to `requests` runs ask for the
    request that would have hit the target. `timeout` is seconds or a callable.
    With `extra_faces` the size field may go over the request, so only a shortfall is corrected.
    """
    requested=layout_target;returncode=None
    for retry in range(requests):
        try:
            with (folder/'native.log').open('a') as log:
                returncode=subprocess.run(command,env=env,stdout=log,stderr=log,timeout=timeout() if callable(timeout) else timeout,
                                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).returncode
        except subprocess.TimeoutExpired:
            return True,None
        if returncode or retry==requests-1:break
        actual=sum(1 for line in (folder/'layout.obj').open() if line.startswith('f '))
        if actual and (layout_target-actual if extra_faces else abs(actual-layout_target))>.12*layout_target:
            requested=max(1,round(requested*layout_target/actual));command[command.index('-f')+1]=str(requested);write(folder/'command.json',command)
        else:break
    return False,returncode


def row_plan(source, triangles, feature_edges, h, guided=False):
    """Constrained crease edges for the layout engine and the fit, or None when nothing needs a row.

    crease_rows names one representative crease per band of parallel creases.
    The layout engine's `-sharp` rule only hardens creases of 60 degrees or
    more, so a gentler representative (island 6's 33-54 degree upper rim) got no
    edge row while its sharper band partner did. Here the representatives that
    must carry rows are preserved constrained edges (`hard`), their band
    partners are left out, and the remaining creases keep their old strength:
    preserved at 60 degrees or more, direction only (`soft`) below. Which
    creases are admitted, and the one-row-per-band rule, are this
    application's policies (source_features, crease_rows), not native ones.

    A plan is also returned when the part has authored guides (`guided`) and no
    crease row: the guides alone then go through the same constrained-edge list.
    """
    from crease_rows import representatives, band_edges
    feature_edges=np.asarray(feature_edges,int).reshape(-1,2)
    if not len(feature_edges) and not guided:return None
    rows,_,_=representatives(source,triangles,feature_edges,h) if len(feature_edges) else ([],None,None)
    if not rows and not guided:return None
    own,partner=band_edges(source,feature_edges,rows,h)
    mesh=trimesh.Trimesh(source,triangles,process=False)
    dihedral={tuple(e):a for e,a in zip(map(tuple,np.sort(mesh.face_adjacency_edges,1)),np.degrees(mesh.face_adjacency_angles))}
    sharp=np.array([dihedral.get(tuple(sorted(map(int,e))),0.)>=ENGINE_SHARP_DEGREES for e in feature_edges],bool)
    hard=own|(sharp&~partner);soft=~hard&~partner
    return dict(chains=rows,curves=[source[np.asarray(row['vertices'],int)] for row in rows],closed=[row['closed'] for row in rows],
                hard=feature_edges[hard],soft=feature_edges[soft],
                bands={tuple(sorted(map(int,e))) for e in feature_edges[own|partner]},
                detail=dict(rows=len(rows),rowEdges=int(own.sum()),bandPartnerEdges=int(partner.sum()),hardEdges=int(hard.sum()),softEdges=int(soft.sum()),
                            rowLengthsInFaces=[row['length']/h for row in rows]))


def row_paths(plan, p, q, h):
    """One connected output edge path per crease row, as fitter paths; raises when a row has no path."""
    edges=cq._edges(q);paths=[]
    for curve,closed in zip(plan['curves'],plan['closed']):
        ids=find_row(p,edges,curve,closed,h)
        if not ids:
            # An unfitted layout can hold its row more than a face off the crease. The fit may
            # still pull the authored-guide path onto it; the crease check then decides.
            try:ids=cq._guide_path(p,edges,curve,h)[0]['vertices']
            except ValueError:raise ValueError('The layout has no connected edge path along a crease that needs a row.')
        paths.append(dict(vertices=[int(v) for v in ids],closed=bool(closed)))
    return paths


def guide_paths(p, q, curves, h, strict):
    """One output edge path per authored guide, as fitter paths.

    A guide is followed by one continuous edge loop: the path never turns from
    one loop onto another (guide_rows). `strict` layouts, whose guides were cut
    into the source and registered, raise when a guide has no such loop; the
    older layouts fall back to the nearest connected path, which the guide
    check then judges.
    """
    paths=[]
    for curve in curves:
        closed=bool(np.linalg.norm(curve[0]-curve[-1])<1e-8)
        ids=find_row(p,cq._edges(q),curve,True,h) if closed else guide_rows.find_loop(p,q,curve,h)
        if ids:paths.append(dict(vertices=[int(v) for v in ids],closed=closed))
        elif strict:raise ValueError('The layout has no continuous edge loop along a guide.')
        else:paths.append(cq._guide_path(p,cq._edges(q),curve,h)[0])
    return paths


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


def construct(source, triangles, curves, *, target, job, extra_faces=False):
    source=np.asarray(source,float); triangles=np.asarray(triangles,int); curves=[np.asarray(c,float) for c in curves]
    mesh=trimesh.Trimesh(source,triangles,process=False); rings=loops(triangles)
    if not rings or not mesh.is_winding_consistent or np.any(mesh.area_faces<=0):
        raise ValueError('Open-part generation requires a nondegenerate, consistently wound manifold source with boundary loops.')
    if isinstance(target,bool) or not isinstance(target,(int,np.integer)) or not 150<=target<=12000:
        raise ValueError('Target must be an integer from 150 to 12,000.')
    # 'default': guides and creases enter the layout as one constrained-edge list (registered_features.constrained).
    # 'registered', 'compare' and 'ranked' are the older opt-in path-provenance experiment.
    policy=os.environ.get('RETOPO_FEATURE_LAYOUT','default')
    if policy=='legacy':policy='default'   # former name of the default route
    if policy not in ('default','registered','compare','ranked'):
        raise ValueError('Unknown feature layout policy: '+policy)
    requested_policy=policy;registration_skipped=None
    job=Path(job); out=job/'open-surface';out.mkdir()
    h=float(np.sqrt(mesh.area/target)); feature_edges,detection=detect(source,triangles,h,target=target); segments=[]
    if policy in ('registered','compare') and not len(feature_edges) and not curves:
        policy='default';registration_skipped='No admitted crease paths or user guides; using the shipped solver.'
    vendor=os.environ.get('RETOPO_REGISTERED_ENGINE') if policy in ('registered','compare') else None
    executable,env,engine=runtime(vendor);env['OMP_NUM_THREADS']='4'
    if extra_faces:
        # The user's 'Add faces where the shape needs them' option: ZRemesher's own size field (recovered
        # 0x1efb00 caps, the engine's -size-caps) decides the face size beside the requested base size,
        # and nothing scales the count back down to the request. Only a shortfall is corrected.
        emit(job,'Extra faces allowed: the ZRemesher size field may add faces where the shape needs them; the target is the base size, not a ceiling.',kind='stage',details=dict(extraFaces=True))
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
    files=[Path(__file__),Path(cq.__file__),Path(refine.__code__.co_filename),Path(__file__).with_name('boundary_geometry.py'),Path(__file__).with_name('quad_connectivity.py'),
           Path(__file__).with_name('crease_rows.py'),Path(__file__).with_name('source_features.py')]
    files.extend(Path(__file__).with_name(name) for name in ('registered_features.py','native_guide_cut.py','guide_rows.py'))
    if policy!='default':files.append(Path(__file__).with_name('feature_rows.py'))
    hashes={str(f):sha(f) for f in files};history=[];started=time.monotonic()
    best=None;passing=[];registered=None;row_context=None
    if policy!='default':
        from registered_features import prepare as prepare_registered, reference_paths, output_paths
        from feature_rows import prepare as prepare_rows, measure as measure_rows, rank_key
        reference=reference_paths(source,feature_edges,curves)
        row_context=prepare_rows(source,triangles,feature_edges,curves,h,
                                 max_distance=.5*h,sample_spacing=.125*h,paths=reference)
        if policy in ('registered','compare'):
            if 'registered-features' not in engine.get('capabilities',[]):
                raise ValueError('This engine does not implement registered features; select the reviewed experimental build')
            try:registered=prepare_registered(source,triangles,feature_edges,curves,out/'registered')
            except ValueError as error:
                history.append(dict(stage='embedding',error=str(error),passed=False));write(out/'history.json',history)
                if policy=='registered':raise OpenSurfaceRejected(history)
                emit(job,'Feature embedding rejected; comparing the remaining layouts',kind='candidate',level='warning')
    write(out/'settings.json',dict(target=int(target),extraFaces=bool(extra_faces),sourceBoundaryLoops=len(rings),sourceHashes=hashes,features=detection,engine=engine,layoutPolicy=policy,requestedLayoutPolicy=requested_policy,registrationSkipped=registration_skipped,searchSeconds=420 if policy!='default' else None))
    # Size-capped layouts first, then crease-constrained ones at uniform size, then
    # QuadriFlow's own adaptive scale without crease constraints, and last finer layouts
    # coarsened by strip collapse. Engineering plan, not a native stage.
    fine=min(12000,max(2*int(target),700))
    # 'caps' = ZRemesher's anisotropic curvature size caps inside the layout engine (-size-caps),
    # measured beside the admitted creases as native does; the caps raise the count above the
    # request, so the request is corrected twice from the counts actually returned.
    plan=[(seed,int(target),'caps') for seed in (2,0)]+[(seed,int(target),'constrained') for seed in (2,0,1)]+[(seed,int(target),'adaptive') for seed in (2,0,1,3)]
    plan+=[(seed,fine,'constrained') for seed in (2,0,1)] if fine>=1.5*target else []
    # Creases that must carry an edge row (crease_rows) are embedded in the layout first; the
    # older layouts follow and are held to the same row check.
    rows=row_plan(source,triangles,feature_edges,h,guided=bool(curves)) if policy=='default' else None
    prepared=None
    if rows:
        # Guides are cut into the source by the recovered ZRemesher rules; the cut edges and the admitted
        # crease edges go to the engine as ONE constrained-edge list (guides first, mode per edge).
        # Guide edges are registered (native mode 2). Crease edges are preserved edges with the direction
        # write but without the lattice line (engine mode 3), or direction only (mode 1): see constrained().
        if 'constrained-edges' not in engine.get('capabilities',[]):
            raise RuntimeError('The layout engine does not take a constrained-edge list. Restore engine/guided-quadriflow (build constrained-edges-17 or later).')
        from registered_features import constrained
        try:prepared=constrained(source,triangles,curves,rows['hard'],rows['soft'],out/'constrained')
        except ValueError as error:
            history.append(dict(stage='guide-cut',error=str(error),passed=False));write(out/'history.json',history)
            raise OpenSurfaceRejected(history)
        # Engineering, kept from the crease-row work: the listed crease edges also orient the field over a band
        # 0.75 h wide (exact source coordinates; nothing is hardened by coincidence any more). Native locks
        # nothing by distance. Without the band no layout of 64 put rows on island 6's creases at 750 beside a guide.
        band=[(a,b,mesh.vertex_normals[[a,b]].mean(0)) for a,b in np.r_[rows['hard'],rows['soft']].reshape(-1,2)]
        band=[(a,b,n/np.linalg.norm(n)) for a,b,n in band if np.linalg.norm(n)>1e-12]
        if band:
            with (out/'crease-band.txt').open('w') as stream:
                stream.write(str(len(band))+chr(10))
                for index,(a,b,n) in enumerate(band):stream.write(' '.join(format(float(x),'.17g') for x in [index,*source[a],*source[b],*n])+chr(10))
        write(out/'crease-rows.json',dict(rows['detail'],chains=[dict(sourceVertices=row['vertices'],closed=row['closed']) for row in rows['chains']]))
        if curves:
            cut=prepared['summary']
            emit(job,f"Guides: {len(curves)} cut into the source as {cut['guideEdges']} edges ({cut['cutVertices']-cut['sourceVertices']} new vertices, {len(cut['relocatedSourceVertices'])} source vertices moved onto a guide); each must carry one continuous edge loop.",kind='stage',details={k:cut[k] for k in ('guideEdges','listedEdges','cutVertices','cutTriangles','guideSampleMaxDistance')})
        if rows['chains']:
            emit(job,f"Crease rows: {len(rows['chains'])} crease chains of two faces or more must each carry one connected edge row; {rows['detail']['bandPartnerEdges']} parallel crease edges within half a face share those rows.",kind='stage',details=rows['detail'])
        plan=[(seed,int(target),style) for style in ROW_STYLES for seed in range(ROW_LAYOUT_SEEDS)]+plan
    row_seeds_fitted=set();row_layouts={}
    if policy in ('registered','compare'):
        hard=[(seed,int(target),style) for style in ('registered-caps','registered') for seed in (2,0)] if registered else []
        plan=hard+(plan if policy=='compare' else [])
    for attempt,(seed,layout_target,style) in enumerate(plan):
        # The same 420-second admission budget as guided_layout leaves room for
        # final worker validation inside the server's existing ten-minute limit.
        # It now also bounds the default policy when crease rows lengthen the plan.
        if (policy!='default' or rows) and time.monotonic()-started>=420:break
        if style in ROW_STYLES and (time.monotonic()-started>=ROW_SEARCH_SECONDS or (style=='rows-wide' and seed in row_seeds_fitted)):continue
        hard=style.startswith('registered')
        folder=out/f'layout-{attempt}';folder.mkdir()
        command=[str(executable),'-i',str(registered['source'] if hard else out/'source.obj'),'-o',str(folder/'layout.obj'),'-f',str(layout_target),'-seed',str(seed),'-boundary']
        guides=out/('segments.txt' if style!='adaptive' else 'guide-segments.txt')
        if hard:
            command+=['-registered-features',str(registered['features']),'-registered-output',str(folder/'registered-paths.json')]
            if style=='registered-caps':command+=['-size-caps-exact']
        elif style in ROW_STYLES:
            command[command.index('-i')+1]=str(prepared['source']);command+=['-constrained-edges',str(prepared['edges'])]
            if extra_faces:command+=['-size-caps']
            if (out/'crease-band.txt').exists():command+=['-guides',str(out/'crease-band.txt'),'-guide-width','.75','-orientation-weight','1','-position-weight','0']
        else:
            command+=['-sharp'] if style=='constrained' else ['-sharp','-size-caps' if extra_faces else '-size-caps-exact'] if style=='caps' else ['-adaptive']
            if segments if style!='adaptive' else curves:command+=['-guides',str(guides),'-guide-width','.75','-orientation-weight','1','-position-weight','0']
        coarse=layout_target!=target
        write(folder/'command.json',command)
        cq._progress(job,f'Building open-part layout {attempt+1}'+(f' at {layout_target:,} quads to coarsen to {target:,}' if coarse else ' with registered feature rows' if hard else ' with registered guide and crease edges' if style in ROW_STYLES else ' with curvature size caps' if style=='caps' else ' with curvature-adaptive sizing' if style=='adaptive' else '')+f'; preserving {len(rings)} boundary loops')
        requests=3 if style in ('caps','registered-caps')+ROW_STYLES else 2
        if style in ROW_STYLES:
            # Rows layouts differ only in their seed, so a batch of seeds is laid out together
            # and both passes read the same files.
            if seed not in row_layouts:
                batch=[s for s in range(seed-seed%ROW_BATCH,min(ROW_LAYOUT_SEEDS,seed-seed%ROW_BATCH+ROW_BATCH)) if s not in row_layouts]
                def lay_out(s):
                    place=out/'row-layouts'/f'seed-{s}';place.mkdir(parents=True)
                    order=[str(place/'layout.obj') if x==str(folder/'layout.obj') else str(s) if i and command[i-1]=='-seed' else x for i,x in enumerate(command)]
                    write(place/'command.json',order)
                    return s,(place,)+run_engine(order,env,place,requests,layout_target,150,extra_faces)
                with ThreadPoolExecutor(len(batch)) as pool:row_layouts.update(pool.map(lay_out,batch))
            layout_folder,timed_out,returncode=row_layouts[seed]
            write(folder/'command.json',json.loads((layout_folder/'command.json').read_text()))
        else:
            layout_folder=folder
            timed_out,returncode=run_engine(command,env,folder,requests,layout_target,
                                            (lambda:150) if policy=='default' else (lambda:min(150,max(.001,420-(time.monotonic()-started)))),extra_faces)
        if timed_out or returncode:
            row=dict(attempt=attempt,style=style,error='Layout process timed out' if timed_out else f'Layout process failed (exit {returncode})',passed=False)
            if (folder/'registered-paths.json').exists():
                packet=json.loads((folder/'registered-paths.json').read_text());row['registeredPaths']=packet
                if packet.get('error'):row['error']=packet['error'];row['stage']=packet.get('stage','integer-registration')
            history.append(row)
            write(out/'history.json',history);emit(job,candidate_message(row),level='warning',kind='candidate');continue
        try:
            p,q=read_obj(layout_folder/'layout.obj');q=np.asarray(q,int)
            if q.ndim!=2 or q.shape[1]!=4:raise ValueError('The native layout did not return quads.')
            registered_paths=None
            if hard:
                packet=json.loads((folder/'registered-paths.json').read_text())
                registered_paths=output_paths(packet,reference)
                edge_set={tuple(e) for e in cq._edges(q)}
                if any(tuple(sorted((a,b))) not in edge_set for path in registered_paths for a,b in zip(path['vertices'][:-1],path['vertices'][1:])):
                    raise ValueError('Registered extraction refers to an absent output edge')
                connectivity=dict(policy='Preserve exact extracted feature vertex IDs; no post-extraction topology repair')
            else:
                p,q,connectivity=dissolve_double_edges(p,q)
                # Existing engineering repairs are retained for the comparison.
                p,q,pinched=weld_pinched_quads(p,q);p,q,holes=fill_triangle_holes(p,q,len(rings));connectivity.update(pinched,**holes);q=np.asarray(q,int)
            # Put boundary vertices on the source's bends so coarse layouts do not cut them.
            conform_boundaries(source,triangles,p,q,float(np.sqrt(mesh.area/layout_target)))
            if coarse and rows is not None:
                # Strip collapse keeps the edge loops it does not remove and makes none: a finer
                # layout without a path along every crease row is not worth coarsening.
                if any(not find_row(p,cq._edges(q),curve,closed,h) for curve,closed in zip(rows['curves'],rows['closed'])):
                    raise ValueError('The finer layout has no connected edge path along a crease that needs a row.')
            if coarse:
                cq._progress(job,f'Coarsening open-part layout {attempt+1} from {len(q):,} quads by whole strips')
                p,q,detail=coarsen(mesh,source,triangles,p,q,curves,target,layout_target,feature_edges)
                write(folder/'coarsened.json',detail)
            if row_context is not None:
                raw_rows=measure_rows(row_context,p,q,paths=registered_paths)
                write(folder/'layout-feature-rows.json',raw_rows)
            marked=marked_segments(source,feature_edges,curves)
            mapping=correspondence(source,triangles,p,q)
            boundary=np.unique(np.concatenate([r for r,_ in mapping]));active=np.setdiff1d(np.arange(len(p)),boundary)
            fixed=p[boundary].copy();contacts=set();witnesses=[]
            fit_rows=rows is not None and not hard
            for iteration in range(5):
                paths=registered_paths[:len(curves)] if hard else guide_paths(p,q,curves,h,style in ROW_STYLES)
                fit_curves=[np.asarray(ref['points'],float) for ref in reference] if hard else curves
                fit_paths=registered_paths if hard else paths
                if iteration:
                    cq._progress(job,f'Fitting open part, pass {iteration}; boundaries fixed')
                    # Fit creases at the verifier's 1/8-spacing sampling, so no
                    # unfitted point between sparse samples decides the maximum.
                    # Each crease row is fit like an authored guide: its connected edge path is
                    # held on the representative crease, and its band is fit through that row only.
                    crease_paths=row_paths(rows,p,q,h) if fit_rows else []
                    p,detail=refine(mesh,p,q,fit_curves+(rows['curves'] if fit_rows else []),target,fit_paths+crease_paths,contacts=sorted(contacts),witnesses=witnesses,
                                    active_vertices=active,allow_boundary=True,dense_features=True,
                                    row_bands=dict(edges=rows['bands'],rows=len(crease_paths)) if fit_rows else None)
                    if not np.array_equal(p[boundary],fixed):raise ValueError('A fit moved a fixed source boundary.')
                    if iteration==1 and not hard:
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
                        paths=registered_paths[:len(curves)] if hard else guide_paths(p,q,curves,h,style in ROW_STYLES)
                quality=cq.quad_quality(p,q,target,extra_faces=extra_faces);fit=cq._guide_fit(p,paths,curves,h)
                row=dict(attempt=attempt,style=style,iteration=iteration,quality=quality,guideFit=fit,passed=False);history.append(row)
                obj(folder/f'candidate-{iteration}.obj',p,q)
                if fit_rows and iteration==0:
                    # Search policy, not acceptance: fitting moves a vertex by a fraction of a face and
                    # cannot create a row, so a layout is fitted only if every crease row already has a
                    # connected path within the half-face row maximum (the quarter-face row limit in the
                    # first 'rows' pass), and a rows layout only if its face count is within tolerance.
                    screen=measure_crease_rows(source,triangles,feature_edges,p,q,h)
                    reach=screen['limits']['rowP95' if style=='rows' else 'rowMax'];near='a quarter' if style=='rows' else 'half a'
                    off=sum(not chain['vertices'] or chain['values']['rowP95']>reach for chain in screen['chains'])
                    # The same screen for authored guides: a continuous loop already within reach of each one.
                    stray=sum(not guide['vertices'] or guide['values']['turns']>0 or guide['values']['rowP95']>reach
                              for guide in guide_rows.measure(p,q,curves,h)['guides']) if curves else 0
                    miscount=style in ROW_STYLES and any('face count' in reason for reason in quality['failures'])
                    if off or stray or miscount:
                        row['error']=(f"Layout not fitted: {off} of {screen['required']} crease rows have no connected edge path within {near} face." if off
                                      else f"Layout not fitted: {stray} of {len(curves)} guides have no continuous edge loop within {near} face." if stray
                                      else f"Layout not fitted: {len(q):,} faces is outside the count tolerance.")
                        row['rowScreen']=dict(required=screen['required'],off=int(off),guidesOff=int(stray),faces=int(len(q)))
                        emit(job,candidate_message(row),level='warning',kind='candidate',details=outcome(row));write(out/'history.json',history)
                        break
                    if style in ROW_STYLES:row_seeds_fitted.add(seed)
                if quality['passed']:
                    cq._progress(job,'Checking open-part boundaries, features, coverage and contacts')
                    feature=measure_features(source,triangles,p,q,target)
                    contact=cq.surface_intersections(p,q,both_quad_diagonals=True)
                    surface=cq.validate_surface(source,triangles,p,q,target,accelerated=True,allow_boundary=True)
                    # A guide passes when it is followed by one continuous edge loop within the row limits
                    # (guide_rows) and its path meets the older connected-path limits as well.
                    loops_report=guide_rows.measure(p,q,curves,h) if curves else None
                    row.update(feature=feature,contacts=contact,surface=surface,guidesPassed=bool(cq.guides_pass(fit,h) and (loops_report is None or loops_report['passed'])))
                    if loops_report is not None:row['guideRows']=loops_report
                    row['passed']=bool(feature['passed'] and contact['passed'] and surface['passed'] and row['guidesPassed'])
                    flow=measure_rows(row_context,p,q,paths=registered_paths) if row['passed'] and row_context is not None else None
                    if flow is not None:
                        row['featureRows']=flow
                        if hard:row['passed']=bool(row['passed'] and flow['passed'])
                    if row['passed']:
                        emit(job,candidate_message(row),kind='candidate',details=outcome(row))
                        metadata=dict(backend=cq.BACKEND,target=int(target),extraFaces=bool(extra_faces),guideMode=2,closedValidation=surface,guidePaths=fit,
                                      intersectionValidation=contact,featureValidation=feature,outputCreases=output_creases(p,q.tolist()),
                                      boundaryValidation=surface['boundaryValidation'],sourceHashes=hashes,layoutEngine=engine,
                                      openSurface=True,elapsedSeconds=time.monotonic()-started,
                                      limitations=['Original boundary topology is preserved; no caps are added.','Boundary and whole-surface deviations are bounded relative to requested spacing.'])
                        if registration_skipped:metadata.update(registeredFeatures=False,registrationSkipped=registration_skipped)
                        if rows:metadata.update(layoutStyle=style,creaseRows=dict(rows['detail'],layoutSeed=int(seed),layoutAttempt=int(attempt)))
                        if loops_report is not None:metadata.update(guideRows=loops_report)
                        if prepared is not None:metadata.update(constrainedEdges=prepared['summary'])
                        if policy=='default':
                            write(out/'history.json',history);write(job/'surface-solver.json',metadata)
                            return p,q.tolist(),metadata
                        key=tuple(rank_key(flow,target=target,face_count=len(q)))
                        metadata.update(featureRows=flow,registeredFeatures=hard,layoutStyle=style)
                        passing.append(dict(attempt=attempt,iteration=iteration,style=style,faces=len(q),rank=list(key)))
                        if best is None or key<best[0]:best=(key,p.copy(),q.copy(),metadata)
                        write(out/'history.json',history);write(out/'passing-candidates.json',passing)
                        # One passing fit per layout; compare different layouts instead
                        # of spending the search budget repeating an accepted fit.
                        break
                    contacts.update(tuple(pair) for key in ('nonAdjacentIntersectingFacePairs','adjacentIntersectingFacePairs') for pair in contact[key])
                    for bounds in surface.get('wholeSurfaceDiagonals',{}).values():
                        for item in (bounds['sourceToOutput'],bounds['outputToSource']):
                            if not item['passed'] and item.get('witness') is not None:witnesses.append(item['witness'])
                    if not surface.get('checks',{}).get('sampledSurface',True):
                        witnesses.extend(surface[key]['witness'] for key in ('sourceToOutput','outputToSource') if surface.get(key,{}).get('witness') is not None)
                emit(job,candidate_message(row),level='warning',kind='candidate',details=outcome(row))
                write(out/'history.json',history)
                if style in ROW_STYLES and iteration>=ROW_SETTLE_PASSES and not (quality['passed'] and row['feature']['rows']['passed']):break
        except ValueError as error:
            history.append(dict(attempt=attempt,style=style,error=str(error)));write(out/'history.json',history)
            emit(job,f'Layout {attempt+1} could not be used: {error}',level='warning',kind='candidate')
    if best is not None:
        _,p,q,metadata=best
        metadata['elapsedSeconds']=time.monotonic()-started
        metadata['candidateSelection']=dict(policy='Lexicographic feature-row rank; all passing layouts admitted within the search budget.',
                                             considered=passing,selectedStyle=metadata['layoutStyle'],searchSeconds=420)
        write(out/'history.json',history);write(job/'surface-solver.json',metadata)
        return p,q.tolist(),metadata
    raise OpenSurfaceRejected(history)
