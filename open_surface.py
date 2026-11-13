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
from boundary_geometry import loops, correspondence, closest, fit_ring, conform_ring, directed_bound
from source_features import detect, measure as measure_features, segment_distances
from quad_connectivity import dissolve_double_edges, collapse_polychords, clean_slivers, vertex_stars, weld_pinched_quads, fill_triangle_holes
from measure_geometry import read_obj
from features import output_creases
from job_progress import emit
from job_diagnostics import candidate_message, outcome, summarize
from crease_rows import find_row, measure as measure_crease_rows, local_sizes
import guide_rows
import corner_zones


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
        # One pass anchors vertices as it goes and can stop with a bend still cut (a 1,500 layout thinned from 3,000:
        # one 20-degree bend 0.119 h from a 1.4 h boundary edge, 2026-11-12). A further pass starts with every vertex
        # free again. Only while the boundary check itself would fail, so a boundary that passes is never touched.
        for _ in range(3):
            try:
                if directed_bound(ring,p[output_ring],.1*h)['passed'] and directed_bound(p[output_ring],ring,.1*h)['passed']:break
                again=conform_ring(p[output_ring],ring,.1*h)
            except ValueError:break      # a degenerate boundary is for the checks that follow to report, as before
            if np.allclose(again,p[output_ring],rtol=0,atol=1e-12):break
            p[output_ring]=again
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
# With extra faces allowed the user has given permission to raise the count until the rows and corners work. When
# no layout does at the requested base size, the base faces are made smaller in steps (the face count times each
# factor) and the search is repeated; the checks stay those of the requested target. Search policy, not acceptance:
# the factors, and the time after which no further layout of each step is started. What is left of the budget then
# goes to the rows of the strict count, still without a count ceiling, with the corners reported: checking the box
# must never return less than leaving it unchecked.
EXTRA_FACES_STEPS=(1.,1.5,2.25)
EXTRA_FACES_DEADLINES=(200,250,300)
REQUESTED_FACE_SEARCH_SECONDS=400
ROW_SETTLE_PASSES=2   # a rows layout whose quad shape or crease rows still fail after this many fits is dropped for the next seed
ROW_STYLES=('rows','rows-wide')
ROW_BATCH=8   # rows layouts laid out together; each engine process keeps its four threads
# Rows layouts processed at the same time (construct(workers=...), set by worker.py; RETOPO_ROW_WORKERS overrides, 1
# is one after another). Speed only: every layout is processed alone and they are taken in plan order, so the
# accepted mesh does not depend on the number. Three, measured on the 8-core development machine with its usual
# desktop load (2026-11-10): one fit takes 4.3 s alone, 5.5 s each with three at once and 9.3 s each with six, so
# six finish little more work than three and make the layout the search is waiting for much slower.
ROW_WORKERS=3
# Search policy with extra faces allowed: every seed is laid out first and both passes try the layouts
# fewest faces first, so the result adds no more faces than its rows and corners need. (Seed order, laid
# out a batch at a time, otherwise, as before.)
EXTRA_FACES_ORDER='fewest faces first'
# ... while that is affordable. A layout takes about a second at a request of 200 and about a minute at 7,200 with
# the size field, so laying out all 64 first used the whole ten-minute limit there (job 5a80a3ff, 2026-11-10). After
# this many seconds of laying out, the seeds done so far are ordered and tried, and the rest are laid out a batch at
# a time as the search reaches them. No batch is started that the last batch's time says cannot finish in the budget.
UPFRONT_LAYOUT_SECONDS=60
SEARCH_SECONDS=420   # the admission budget of the whole search (see the loop below)


def layout_faces(folder):
    """Face count of a layout file, or None when the engine left none."""
    try:
        with (Path(folder)/'layout.obj').open() as stream:return sum(1 for line in stream if line.startswith('f '))
    except OSError:return None


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


def row_plan(source, triangles, feature_edges, h, guided=False, sizes=None):
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

    `sizes` (crease_rows.local_sizes; only when the user allows extra faces):
    the local face at each crease edge. The band rule and the two-face minimum
    are then measured with it, so the short creases of a corner get rows of
    their own, and `edgeSizes` carries the sizes of the listed edges (hard,
    then soft) to the engine as face-size caps.
    """
    from crease_rows import representatives, band_edges
    feature_edges=np.asarray(feature_edges,int).reshape(-1,2)
    if not len(feature_edges) and not guided:return None
    rows,_,_=representatives(source,triangles,feature_edges,h,sizes) if len(feature_edges) else ([],None,None)
    if not rows and not guided:return None
    own,partner=band_edges(source,feature_edges,rows,h,sizes)
    mesh=trimesh.Trimesh(source,triangles,process=False)
    dihedral={tuple(e):a for e,a in zip(map(tuple,np.sort(mesh.face_adjacency_edges,1)),np.degrees(mesh.face_adjacency_angles))}
    sharp=np.array([dihedral.get(tuple(sorted(map(int,e))),0.)>=ENGINE_SHARP_DEGREES for e in feature_edges],bool)
    hard=own|(sharp&~partner);soft=~hard&~partner
    detail=dict(rows=len(rows),rowEdges=int(own.sum()),bandPartnerEdges=int(partner.sum()),hardEdges=int(hard.sum()),softEdges=int(soft.sum()),
                rowLengthsInFaces=[row['length']/h for row in rows])
    plan=dict(chains=rows,curves=[source[np.asarray(row['vertices'],int)] for row in rows],closed=[row['closed'] for row in rows],
              hard=feature_edges[hard],soft=feature_edges[soft],rowSizes=[row.get('sizes') for row in rows],
              bands={tuple(sorted(map(int,e))) for e in feature_edges[own|partner]},detail=detail)
    if sizes is not None:
        sizes=np.asarray(sizes,float)
        plan['edgeSizes']=np.r_[sizes[hard],sizes[soft]]
        detail.update(localFaces=True,sizedEdges=int((plan['edgeSizes']<1).sum()),smallestLocalFace=float(plan['edgeSizes'].min()) if len(plan['edgeSizes']) else 1.,
                      rowLocalFaces=[float(min(row['sizes'])) for row in rows])
    return plan


def row_paths(plan, p, q, h):
    """One connected output edge path per crease row, as fitter paths; raises when a row has no path."""
    edges=cq._edges(q);paths=[]
    for curve,closed,local in zip(plan['curves'],plan['closed'],plan['rowSizes']):
        ids=find_row(p,edges,curve,closed,h,local)
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


def settle(mesh, p, q, curves, fine_target):
    """Fit a finer layout onto its creases and guides at its own face size (two passes, boundary fixed)."""
    fine_h=float(np.sqrt(mesh.area/fine_target))
    boundary=np.unique(np.concatenate(loops(q)));active=np.setdiff1d(np.arange(len(p)),boundary)
    for _ in range(2):
        paths=[cq._guide_path(p,cq._edges(q),curve,fine_h)[0] for curve in curves]
        p,_=refine(mesh,p,q,curves,fine_target,paths,active_vertices=active,allow_boundary=True,dense_features=True)
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
    p=settle(mesh,p,q,curves,fine_target)
    guides=[v for curve in curves for v in cq._guide_path(p,cq._edges(q),curve,fine_h)[0]['vertices']]
    protected=np.union1d(np.flatnonzero(distance(p)<.15*fine_h),np.asarray(guides,int))
    p,q,detail=collapse_polychords(p,q,target,protected=protected,keep_apart=protected,spacing=h,feature_distance=distance)
    p,q,_=dissolve_double_edges(p,q);q=np.asarray(q,int)
    conform_boundaries(source,triangles,p,q,h)
    fixed=np.zeros(len(p),bool);fixed[np.concatenate(loops(q))]=True;fixed[distance(p)<.15*h]=True
    return relax(mesh,p,q,fixed,rounds=3,segments=marked_segments(source,feature_edges,curves),spacing=h),q,detail


def process_layout(ctx, attempt, seed, layout_target, style, layout_folder, folder):
    """One layout, from the engine's file to an accepted mesh or its recorded failures.

    The search in `construct` calls this for every layout. It touches nothing outside `folder`
    and returns all it found: dict(rows = its history rows, events = its log and progress lines
    in order, fitted, screen = what the first pass learned for the second, accepted = (points,
    quads, metadata) or None, passing = a ranked candidate of the opt-in policies). A layout's
    outcome depends on that layout alone, so rows layouts can be processed in other processes,
    several at a time, and taken in plan order: the accepted mesh is the one the layouts give
    one after another. `ctx['live']`: log and progress lines are written as they happen (the
    search is running this layout itself) instead of being returned.
    """
    source=ctx['source'];triangles=ctx['triangles'];curves=ctx['curves'];target=ctx['target'];h=ctx['h']
    feature_edges=ctx['feature_edges'];rows=ctx['rows'];sizes=ctx['sizes'];local_faces=ctx['local_faces'];extra_faces=ctx['extra_faces']
    policy=ctx['policy'];rings=ctx['rings'];job=ctx['job'];hashes=ctx['hashes'];engine=ctx['engine'];registration_skipped=ctx['registration_skipped']
    row_context=ctx.get('row_context');reference=ctx.get('reference')
    mesh=ctx.get('mesh')
    if mesh is None:mesh=trimesh.Trimesh(source,triangles,process=False)
    hard=style.startswith('registered')
    coarse=layout_target!=target and style not in ROW_STYLES   # a rows layout with smaller base faces keeps its faces
    if hard or row_context is not None:
        from registered_features import output_paths
        from feature_rows import measure as measure_rows, rank_key
    history=[];events=[];result=dict(rows=history,events=events,fitted=False,screen=None,accepted=None,passing=None)
    def say(message,**keywords):
        if ctx['live']:emit(job,message,**keywords)
        else:events.append(('emit',message,keywords))
    def progress(message):
        if ctx['live']:cq._progress(job,message)
        else:events.append(('progress',message,{}))
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
            p,q,pinched=weld_pinched_quads(p,q);p,q,holes=fill_triangle_holes(p,q,rings);connectivity.update(pinched,**holes);q=np.asarray(q,int)
        # Put boundary vertices on the source's bends so coarse layouts do not cut them.
        conform_boundaries(source,triangles,p,q,float(np.sqrt(mesh.area/layout_target)))
        if coarse and rows is not None:
            # Strip collapse keeps the edge loops it does not remove and makes none: a finer
            # layout without a path along every crease row is not worth coarsening.
            if any(not find_row(p,cq._edges(q),curve,closed,h,local) for curve,closed,local in zip(rows['curves'],rows['closed'],rows['rowSizes'])):
                raise ValueError('The finer layout has no connected edge path along a crease that needs a row.')
        if coarse:
            progress(f'Coarsening open-part layout {attempt+1} from {len(q):,} quads by whole strips')
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
                progress(f'Fitting open part, pass {iteration}; boundaries fixed')
                # Fit creases at the verifier's 1/8-spacing sampling, so no
                # unfitted point between sparse samples decides the maximum.
                # Each crease row is fit like an authored guide: its connected edge path is
                # held on the representative crease, and its band is fit through that row only.
                crease_paths=row_paths(rows,p,q,h) if fit_rows else []
                p,detail=refine(mesh,p,q,fit_curves+(rows['curves'] if fit_rows else []),target,fit_paths+crease_paths,contacts=sorted(contacts),witnesses=witnesses,
                                active_vertices=active,allow_boundary=True,dense_features=True,
                                row_bands=dict(edges=rows['bands'],rows=len(crease_paths)) if fit_rows else None,feature_sizes=sizes)
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
                screen=measure_crease_rows(source,triangles,feature_edges,p,q,h,sizes)
                # The same screen for authored guides: a continuous loop already within reach of each one.
                guide_screen=guide_rows.measure(p,q,curves,h)['guides'] if curves else []
                miscount=style in ROW_STYLES and any('face count' in reason for reason in quality['failures'])
                def verdict(reach,near):
                    off=sum(not chain['vertices'] or chain['values']['rowP95']>reach for chain in screen['chains'])
                    stray=sum(not guide['vertices'] or guide['values']['turns']>0 or guide['values']['rowP95']>reach for guide in guide_screen)
                    if not (off or stray or miscount):return None,None
                    return ((f"Layout not fitted: {off} of {screen['required']} crease rows have no connected edge path within {near} face." if off
                             else f"Layout not fitted: {stray} of {len(curves)} guides have no continuous edge loop within {near} face." if stray
                             else f"Layout not fitted: {len(q):,} faces is outside the count tolerance."),
                            dict(required=screen['required'],off=int(off),guidesOff=int(stray),faces=int(len(q))))
                if style=='rows':
                    # The second pass asks the same of this layout with the half-face reach: keep the answer.
                    wide,wide_screen=verdict(screen['limits']['rowMax'],'half a')
                    result['screen']=dict(error=wide,quality=quality,rowScreen=wide_screen)
                failure,row_screen=verdict(screen['limits']['rowP95' if style=='rows' else 'rowMax'],'a quarter' if style=='rows' else 'half a')
                if failure:
                    row['error']=failure;row['rowScreen']=row_screen
                    say(candidate_message(row),level='warning',kind='candidate',details=outcome(row))
                    break
                if style in ROW_STYLES:result['fitted']=True
            if quality['passed']:
                progress('Checking open-part boundaries, features, coverage and contacts')
                feature=measure_features(source,triangles,p,q,target,extra_faces=local_faces)
                contact=cq.surface_intersections(p,q,both_quad_diagonals=True)
                surface=cq.validate_surface(source,triangles,p,q,target,accelerated=True,allow_boundary=True)
                # Corner zones (corner_zones): the source against the output where crease branches meet. Reported for
                # every result; a failing corner rejects the candidate while the local-face rules are in force.
                corners=corner_zones.measure(source,triangles,feature_edges,p,q,h)
                # A guide passes when it is followed by one continuous edge loop within the row limits
                # (guide_rows) and its path meets the older connected-path limits as well.
                loops_report=guide_rows.measure(p,q,curves,h) if curves else None
                row.update(feature=feature,contacts=contact,surface=surface,guidesPassed=bool(cq.guides_pass(fit,h) and (loops_report is None or loops_report['passed'])))
                if loops_report is not None:row['guideRows']=loops_report
                row['corners' if local_faces else 'cornerReport']=corners
                row['passed']=bool(feature['passed'] and contact['passed'] and surface['passed'] and row['guidesPassed'] and (corners['passed'] or not local_faces))
                flow=measure_rows(row_context,p,q,paths=registered_paths) if row['passed'] and row_context is not None else None
                if flow is not None:
                    row['featureRows']=flow
                    if hard:row['passed']=bool(row['passed'] and flow['passed'])
                if row['passed']:
                    say(candidate_message(row),kind='candidate',details=outcome(row))
                    metadata=dict(backend=cq.BACKEND,target=int(target),extraFaces=bool(extra_faces),guideMode=2,closedValidation=surface,guidePaths=fit,
                                  intersectionValidation=contact,featureValidation=feature,outputCreases=output_creases(p,q.tolist()),
                                  boundaryValidation=surface['boundaryValidation'],sourceHashes=hashes,layoutEngine=engine,
                                  openSurface=True,elapsedSeconds=None,
                                  limitations=['Original boundary topology is preserved; no caps are added.','Boundary and whole-surface deviations are bounded relative to requested spacing.'])
                    fallback=bool(extra_faces and policy=='default' and len(feature_edges) and not local_faces)
                    metadata.update(cornerZones=dict(corners,enforced=bool(local_faces),extraFacesFallback=fallback))
                    if extra_faces:metadata.update(localFaces=bool(local_faces))
                    if corners['zones']:
                        worst=f"worst 95th percentile {corners['worstP95InFaces']:.2f} h, worst maximum {corners['worstMaxInFaces']:.2f} h (limits {corners['limits']['p95InFaces']:g} h and {corners['limits']['maxInFaces']:g} h)"
                        if corners['passed']:say(f"Corners: {len(corners['zones'])} corner zones follow the source; {worst}.",kind='stage',details=corners)
                        else:say(f"Corners: {len(corners['failures'])} corner measures are over their limit; {worst}. {'Extra faces were allowed, but no layout gave every short crease chain a row of its own; this result uses the rows of the strict count.' if fallback else 'The count was kept within tolerance of the target; allow extra faces to give the corners the faces they need.'}",level='warning',kind='stage',details=corners)
                    if registration_skipped:metadata.update(registeredFeatures=False,registrationSkipped=registration_skipped)
                    if rows:metadata.update(layoutStyle=style,creaseRows=dict(rows['detail'],layoutSeed=int(seed),layoutAttempt=int(attempt)))
                    if rows and ctx['ordered']:metadata['creaseRows'].update(layoutOrder=EXTRA_FACES_ORDER,layoutFaces=layout_faces(layout_folder))
                    if rows and extra_faces and style in ROW_STYLES:metadata['creaseRows'].update(baseFaces=int(layout_target))
                    if loops_report is not None:metadata.update(guideRows=loops_report)
                    if ctx['constrained_summary'] is not None:metadata.update(constrainedEdges=ctx['constrained_summary'])
                    if policy=='default':
                        result['accepted']=(p,q,metadata)
                        return result
                    key=tuple(rank_key(flow,target=target,face_count=len(q)))
                    metadata.update(featureRows=flow,registeredFeatures=hard,layoutStyle=style)
                    result['passing']=dict(entry=dict(attempt=attempt,iteration=iteration,style=style,faces=len(q),rank=list(key)),key=key,p=p.copy(),q=q.copy(),metadata=metadata)
                    # One passing fit per layout; compare different layouts instead
                    # of spending the search budget repeating an accepted fit.
                    break
                contacts.update(tuple(pair) for key in ('nonAdjacentIntersectingFacePairs','adjacentIntersectingFacePairs') for pair in contact[key])
                for bounds in surface.get('wholeSurfaceDiagonals',{}).values():
                    for item in (bounds['sourceToOutput'],bounds['outputToSource']):
                        if not item['passed'] and item.get('witness') is not None:witnesses.append(item['witness'])
                if not surface.get('checks',{}).get('sampledSurface',True):
                    witnesses.extend(surface[key]['witness'] for key in ('sourceToOutput','outputToSource') if surface.get(key,{}).get('witness') is not None)
            say(candidate_message(row),level='warning',kind='candidate',details=outcome(row))
            if style in ROW_STYLES and iteration>=ROW_SETTLE_PASSES and not (quality['passed'] and row['feature']['rows']['passed']):break
            # Search policy: the boundary is fixed from the first fit on, so a layout whose boundary check fails cannot pass later.
            if style in ROW_STYLES and iteration>=1 and 'surface' in row and not row['surface'].get('checks',{}).get('boundaryPreserved',True):break
    except ValueError as error:
        history.append(dict(attempt=attempt,style=style,error=str(error)))
        say(f'Layout {attempt+1} could not be used: {error}',level='warning',kind='candidate')
        # The same layout fails the same way in the second pass, unless it failed while being fitted in this one.
        if style=='rows' and not result['fitted']:result['screen']=dict(error=str(error))
    return result


def _pool_start(crease_angle):
    """A layout process: the job's crease angle is process-wide state (source_features.use_crease_angle)."""
    from source_features import use_crease_angle
    use_crease_angle(crease_angle)
    # Loaded now, while the engine is still laying out, instead of inside the first fit of each process.
    import torch,scipy.optimize,source_projection,feature_refine,surface_intersections
    torch.set_num_threads(1)


def _pool_layout(arguments):
    return process_layout(*arguments)


def construct(source, triangles, curves, *, target, job, extra_faces=False, workers=1):
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
    files.extend(Path(__file__).with_name(name) for name in ('registered_features.py','native_guide_cut.py','guide_rows.py','corner_zones.py'))
    if policy!='default':files.append(Path(__file__).with_name('feature_rows.py'))
    hashes={str(f):sha(f) for f in files};history=[];started=time.monotonic()
    best=None;passing=[];registered=None;row_context=None;reference=None
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
    # With extra faces allowed a face is the local face at each crease edge (crease_rows.local_sizes): in the band
    # rule, in the row check and, as face-size caps on the constrained edges, in the engine's size field.
    sizes=local_sizes(source,feature_edges,h,detection['minimumLength']) if extra_faces and policy=='default' and len(feature_edges) else None

    def prepare_rows(sizes,folder,band_name,record_name,base=1.):
        """Row plan, cut source and constrained-edge list for one set of rules: (rows, prepared, band file).

        `base`: the engine's base face size as a fraction of the requested one (a step of EXTRA_FACES_STEPS). The
        local sizes stay fractions of the requested face; the list carries them as fractions of the engine's base.
        """
        rows=row_plan(source,triangles,feature_edges,h,guided=bool(curves),sizes=sizes)
        if not rows:return rows,None,out/band_name
        # Guides are cut into the source by the recovered ZRemesher rules; the cut edges and the admitted
        # crease edges go to the engine as ONE constrained-edge list (guides first, mode per edge).
        # Guide edges are registered (native mode 2). Crease edges are preserved edges with the direction
        # write but without the lattice line (engine mode 3), or direction only (mode 1): see constrained().
        if 'constrained-edges' not in engine.get('capabilities',[]):
            raise RuntimeError('The layout engine does not take a constrained-edge list. Restore engine/guided-quadriflow (build constrained-edges-17 or later).')
        if sizes is not None and 'constrained-edge-sizes' not in engine.get('capabilities',[]):
            raise RuntimeError('The layout engine does not take face sizes on constrained edges. Restore engine/guided-quadriflow (build constrained-sizes-19 or later).')
        from registered_features import constrained
        try:prepared=constrained(source,triangles,curves,rows['hard'],rows['soft'],out/folder,sizes=None if rows.get('edgeSizes') is None else np.minimum(1.,rows['edgeSizes']/base))
        except ValueError as error:
            history.append(dict(stage='guide-cut',error=str(error),passed=False));write(out/'history.json',history)
            raise OpenSurfaceRejected(history)
        # Engineering, kept from the crease-row work: the listed crease edges also orient the field over a band
        # 0.75 h wide (exact source coordinates; nothing is hardened by coincidence any more). Native locks
        # nothing by distance. Without the band no layout of 64 put rows on island 6's creases at 750 beside a guide.
        band=[(a,b,mesh.vertex_normals[[a,b]].mean(0)) for a,b in np.r_[rows['hard'],rows['soft']].reshape(-1,2)]
        band=[(a,b,n/np.linalg.norm(n)) for a,b,n in band if np.linalg.norm(n)>1e-12]
        if band:
            with (out/band_name).open('w') as stream:
                stream.write(str(len(band))+chr(10))
                for index,(a,b,n) in enumerate(band):stream.write(' '.join(format(float(x),'.17g') for x in [index,*source[a],*source[b],*n])+chr(10))
        write(out/record_name,dict(rows['detail'],chains=[dict(sourceVertices=row['vertices'],closed=row['closed']) for row in rows['chains']]))
        if curves and folder=='constrained':
            cut=prepared['summary']
            emit(job,f"Guides: {len(curves)} cut into the source as {cut['guideEdges']} edges ({cut['cutVertices']-cut['sourceVertices']} new vertices, {len(cut['relocatedSourceVertices'])} source vertices moved onto a guide); each must carry one continuous edge loop.",kind='stage',details={k:cut[k] for k in ('guideEdges','listedEdges','cutVertices','cutTriangles','guideSampleMaxDistance')})
        if rows['chains'] and sizes is not None and base<1:pass
        elif rows['chains'] and sizes is not None:
            emit(job,f"Crease rows: {len(rows['chains'])} crease chains must each carry one connected edge row. Faces are sized down to {rows['detail']['smallestLocalFace']:.2f} of the requested size at {rows['detail']['sizedEdges']} crease edges so that short creases get rows; {rows['detail']['bandPartnerEdges']} parallel crease edges within half a local face share a row.",kind='stage',details=rows['detail'])
        elif rows['chains']:
            emit(job,f"Crease rows: {len(rows['chains'])} crease chains of two faces or more must each carry one connected edge row; {rows['detail']['bandPartnerEdges']} parallel crease edges within half a face share those rows.",kind='stage',details=rows['detail'])
        return rows,prepared,out/band_name

    rows,prepared,band_file=prepare_rows(sizes,'constrained','crease-band.txt','crease-rows.json') if policy=='default' else (None,None,out/'crease-band.txt')
    # With extra faces allowed the rules ask for more (a row on every short crease chain, corner zones). Checking the box
    # must never do worse than leaving it unchecked, so when no layout meets them the search goes on with the
    # requested-face rules of the strict count, still without a count ceiling, and the corners are reported.
    local_faces=sizes is not None;row_folder='row-layouts';row_deadline=EXTRA_FACES_DEADLINES[0] if local_faces else ROW_SEARCH_SECONDS
    if rows:
        def searches(count):return [(seed,int(count),style) for style in ROW_STYLES for seed in range(ROW_LAYOUT_SEEDS)]
        more=[]
        if local_faces:
            for step in EXTRA_FACES_STEPS[1:]:
                count=min(12000,int(round(target*step)))
                if count>target and not any(entry[1]==count for entry in more):more+=[(None,count,'more-faces')]+searches(count)
            # The last resort starts with what the unchecked mode ends with: finer layouts thinned to the target by
            # strip collapse. They are the layouts that carry rows on close parallel creases at higher targets
            # (island 6 at 1,500: every row, where no rows layout had them), and three of them cost little. Then
            # the rows layouts of the strict count.
            thinned=[entry for entry in plan if entry[1]!=target]
            plan=[entry for entry in plan if entry[1]==target]
            more+=[(None,int(target),'requested-faces')]+thinned+searches(target)
        plan=searches(target)+more+plan
    # row_screens: what the first pass found for each seed, so the second pass does not measure the same layout again.
    row_seeds_fitted=set();row_layouts={};row_order=None;row_screens={}
    batch_cost=None   # (seconds, faces requested) of the last batch of rows layouts laid out
    layout_processes=None;tasks={}
    def context(live):
        """What process_layout needs for the rules now in force; `live` for this process, plain data for another."""
        from source_features import _angle as crease_angle
        base=dict(source=source,triangles=triangles,curves=curves,target=int(target),h=h,feature_edges=feature_edges,rows=rows,sizes=sizes,local_faces=local_faces,
                  extra_faces=bool(extra_faces),policy=policy,rings=len(rings),job=job,live=live,hashes=hashes,engine=engine,registration_skipped=registration_skipped,
                  ordered=row_order is not None,constrained_summary=None if prepared is None else prepared['summary'],crease_angle=crease_angle)
        if live:base.update(mesh=mesh,row_context=row_context,reference=reference)
        return base
    def schedule(first):
        """Hand layouts to idle processes: plan entries from `first` on, in plan order, whose layout files exist.

        The scan covers the rest of this pass and the second pass of the same rules. A second-pass layout is started
        as soon as the first pass has settled what it needs to know about that seed (its half-face screen, and that
        it was not fitted there), also when the search itself has not come to it yet: its outcome is its own.
        """
        for index in [i for i in tasks if i<first]:del tasks[index]      # layouts the search passed without taking (out of time)
        count=plan[first][1];last=first
        while last+1<len(plan) and plan[last+1][2] in ROW_STYLES and plan[last+1][1]==count:last+=1
        earlier={plan[i][0]:i for i in range(first,last+1) if plan[i][2]=='rows'}     # first-pass entries still ahead, by seed
        def settled(s):
            """What the first pass says about seed `s` for the second: True to try it, False to skip it, None when not known yet."""
            if s in row_seeds_fitted:return False
            known=row_screens.get(s)
            if known is None and s in earlier:
                task=tasks.get(earlier[s])
                if task is None or not task.ready():return None
                outcome_=task.get()
                if outcome_['fitted']:return False
                known=outcome_['screen']
            return None if known is None else not known.get('error')
        # While seeds are still being laid out the engine needs the processors, and the first pass comes first: second-pass
        # layouts started ahead of the search are then held to a third of the processes.
        early=plan[first][2]=='rows';ahead=workers if len(row_layouts)>=ROW_LAYOUT_SEEDS else max(1,workers//3)
        for index in range(first,last+1):
            s,_,name=plan[index]
            if index in tasks or s not in row_layouts:continue
            if index>first and sum(1 for task in tasks.values() if not task.ready())>=workers:break
            if row_layouts[s][1] or row_layouts[s][2]:continue                                                      # the engine left no layout
            if name=='rows-wide' and index>first and not settled(s):continue                                        # skipped, or not known yet
            if name=='rows-wide' and early and sum(1 for i,task in tasks.items() if plan[i][2]=='rows-wide' and not task.ready())>=ahead:break
            place=out/f'layout-{index}';place.mkdir(exist_ok=True)
            tasks[index]=layout_processes.apply_async(_pool_layout,((context(False),index,s,count,name,row_layouts[s][0],place),))
    def stop_pool():
        nonlocal layout_processes
        if layout_processes is not None:layout_processes.terminate();layout_processes.join();layout_processes=None
        tasks.clear()
    if policy in ('registered','compare'):
        hard=[(seed,int(target),style) for style in ('registered-caps','registered') for seed in (2,0)] if registered else []
        plan=hard+(plan if policy=='compare' else [])
    for attempt,(seed,layout_target,style) in enumerate(plan):
        # The same 420-second admission budget as guided_layout leaves room for
        # final worker validation inside the server's existing ten-minute limit.
        # It now also bounds the default policy when crease rows lengthen the plan.
        if (policy!='default' or rows) and time.monotonic()-started>=SEARCH_SECONDS:break
        if style in ('more-faces','requested-faces') and any(not task.ready() for task in tasks.values()):stop_pool()   # layouts of the rules left behind
        tasks.clear() if style in ('more-faces','requested-faces') else None
        if style=='more-faces':
            emit(job,f"No layout at the requested face size gave every short crease chain a row of its own and followed every corner. Extra faces are allowed, so the base faces are made smaller: {layout_target:,} faces before the features add theirs (target {target:,}). The checks stay those of the target.",kind='stage',details=dict(baseFaces=int(layout_target),target=int(target)))
            row_seeds_fitted=set();row_layouts={};row_order=None;row_screens={};row_folder=f'row-layouts-{layout_target}'
            row_deadline=EXTRA_FACES_DEADLINES[min(range(len(EXTRA_FACES_STEPS)),key=lambda k:abs(target*EXTRA_FACES_STEPS[k]-layout_target))]
            _,prepared,_=prepare_rows(sizes,f'constrained-{layout_target}','crease-band.txt','crease-rows.json',base=float(np.sqrt(target/layout_target)))
            continue
        if style=='requested-faces':
            emit(job,"No layout gave every short crease chain a row of its own and followed every corner in the time allowed, at the requested face size or with smaller base faces. Continuing with the rows of the strict count, still without a count ceiling; the corners will be reported.",level='warning',kind='stage')
            sizes=None;local_faces=False;row_seeds_fitted=set();row_layouts={};row_order=None;row_screens={};row_folder='row-layouts-requested';row_deadline=REQUESTED_FACE_SEARCH_SECONDS
            rows,prepared,band_file=prepare_rows(None,'constrained-requested','crease-band-requested.txt','crease-rows-requested.json')
            continue
        if style in ROW_STYLES and (time.monotonic()-started>=row_deadline or (style=='rows-wide' and seed in row_seeds_fitted)):continue
        if style in ROW_STYLES and seed not in row_layouts and batch_cost is not None and time.monotonic()-started+batch_cost[0]*layout_target/batch_cost[1]>min(SEARCH_SECONDS,row_deadline):
            continue   # the last batch's time says this seed's batch cannot be laid out before this step's time is up
        hard=style.startswith('registered')
        if layout_processes is None and workers>1 and policy=='default' and style in ROW_STYLES:
            # Started before the layouts are laid out, so the processes are ready when the first layout is.
            import multiprocessing
            from source_features import _angle as crease_angle
            layout_processes=multiprocessing.get_context('spawn').Pool(int(workers),initializer=_pool_start,initargs=(crease_angle,))
        folder=out/f'layout-{attempt}';folder.mkdir(exist_ok=True)
        command=[str(executable),'-i',str(registered['source'] if hard else out/'source.obj'),'-o',str(folder/'layout.obj'),'-f',str(layout_target),'-seed',str(seed),'-boundary']
        guides=out/('segments.txt' if style!='adaptive' else 'guide-segments.txt')
        if hard:
            command+=['-registered-features',str(registered['features']),'-registered-output',str(folder/'registered-paths.json')]
            if style=='registered-caps':command+=['-size-caps-exact']
        elif style in ROW_STYLES:
            command[command.index('-i')+1]=str(prepared['source']);command+=['-constrained-edges',str(prepared['edges'])]
            if extra_faces:command+=['-size-caps']
            if band_file.exists():command+=['-guides',str(band_file),'-guide-width','.75','-orientation-weight','1','-position-weight','0']
        else:
            command+=['-sharp'] if style=='constrained' else ['-sharp','-size-caps' if extra_faces else '-size-caps-exact'] if style=='caps' else ['-adaptive']
            if segments if style!='adaptive' else curves:command+=['-guides',str(guides),'-guide-width','.75','-orientation-weight','1','-position-weight','0']
        coarse=layout_target!=target and style not in ROW_STYLES   # a rows layout with smaller base faces keeps its faces
        write(folder/'command.json',command)
        cq._progress(job,f'Building open-part layout {attempt+1}'+(f' at {layout_target:,} quads to coarsen to {target:,}' if coarse else ' with registered feature rows' if hard else ' with registered guide and crease edges' if style in ROW_STYLES else ' with curvature size caps' if style=='caps' else ' with curvature-adaptive sizing' if style=='adaptive' else '')+f'; preserving {len(rings)} boundary loops')
        requests=3 if style in ('caps','registered-caps')+ROW_STYLES else 2
        if style in ROW_STYLES:
            # Rows layouts differ only in their seed, so a batch of seeds is laid out together
            # and both passes read the same files.
            if seed not in row_layouts:
                def lay_out(s):
                    place=out/row_folder/f'seed-{s}';place.mkdir(parents=True)
                    order=[str(place/'layout.obj') if x==str(folder/'layout.obj') else str(s) if i and command[i-1]=='-seed' else x for i,x in enumerate(command)]
                    write(place/'command.json',order)
                    return s,(place,)+run_engine(order,env,place,requests,layout_target,150,extra_faces)
                # One batch of seeds; with extra faces allowed, every batch while that is affordable, so the layouts can be
                # ordered by face count. (Not for the steps with smaller base faces: each batch is tried as it comes.)
                upfront=bool(extra_faces and layout_target==target and row_order is None);laying=time.monotonic()
                for first in (range(0,ROW_LAYOUT_SEEDS,ROW_BATCH) if upfront else [seed-seed%ROW_BATCH]):
                    if upfront and first and time.monotonic()-laying>=UPFRONT_LAYOUT_SECONDS:break
                    batch=[s for s in range(first,min(ROW_LAYOUT_SEEDS,first+ROW_BATCH)) if s not in row_layouts]
                    if batch:
                        began=time.monotonic()
                        with ThreadPoolExecutor(len(batch)) as pool:row_layouts.update(pool.map(lay_out,batch))
                        batch_cost=(time.monotonic()-began,layout_target)
            if extra_faces and layout_target==target and row_order is None:
                counts={s:layout_faces(item[0]) for s,item in row_layouts.items() if not item[1] and not item[2]}
                counts={s:n for s,n in counts.items() if n}
                row_order=sorted(counts,key=lambda s:(counts[s],s))+[s for s in range(ROW_LAYOUT_SEEDS) if s not in counts]
                for name in ROW_STYLES:
                    for i,s in zip([i for i in range(attempt,len(plan)) if plan[i][2]==name],row_order):plan[i]=(s,plan[i][1],name)
                seed=plan[attempt][0]
                emit(job,f"Laid out {len(counts)} layouts of {min(counts.values()) if counts else 0:,} to {max(counts.values()) if counts else 0:,} faces; trying them {EXTRA_FACES_ORDER}."+(f" The other {ROW_LAYOUT_SEEDS-len(row_layouts)} are laid out as the search reaches them: layouts of this size take long." if len(row_layouts)<ROW_LAYOUT_SEEDS else ''),kind='stage',details=dict(order=row_order,faces=[counts.get(s) for s in row_order]))
            layout_folder,timed_out,returncode=row_layouts[seed]
            write(folder/'command.json',json.loads((layout_folder/'command.json').read_text()))
            known=row_screens.get(seed) if style=='rows-wide' else None
            if known is not None and known.get('error'):
                # The first pass already measured this layout; its verdict for the second pass is known.
                row=dict(attempt=attempt,style=style,error=known['error'],fromFirstPass=True)
                if 'quality' in known:row.update(iteration=0,quality=known['quality'],rowScreen=known['rowScreen'],passed=False)
                history.append(row);write(out/'history.json',history)
                emit(job,candidate_message(row) if 'quality' in known else f"Layout {attempt+1} could not be used: {known['error']}",level='warning',kind='candidate',**(dict(details=outcome(row)) if 'quality' in known else {}))
                continue
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
        if layout_processes is not None and style in ROW_STYLES:
            # This layout and the ones after it are processed at the same time; they are taken here in plan order.
            schedule(attempt)
            while not tasks[attempt].ready():
                tasks[attempt].wait(.25);schedule(attempt)      # processes that came free take the next layouts
            result=tasks.pop(attempt).get()
            for kind,message,keywords in result['events']:
                if kind=='emit':emit(job,message,**keywords)
                else:cq._progress(job,message)
        else:
            result=process_layout(context(True),attempt,seed,layout_target,style,layout_folder,folder)
        history.extend(result['rows'])
        if result['fitted']:row_seeds_fitted.add(seed)
        if result['screen'] is not None:row_screens[seed]=result['screen']
        write(out/'history.json',history)
        if result['passing'] is not None:
            passing.append(result['passing']['entry'])
            if best is None or result['passing']['key']<best[0]:best=(result['passing']['key'],result['passing']['p'],result['passing']['q'],result['passing']['metadata'])
            write(out/'passing-candidates.json',passing)
        if result['accepted'] is not None:
            p,q,metadata=result['accepted'];metadata['elapsedSeconds']=time.monotonic()-started
            stop_pool();write(job/'surface-solver.json',metadata)
            return p,q.tolist(),metadata
    stop_pool()
    if best is not None:
        _,p,q,metadata=best
        metadata['elapsedSeconds']=time.monotonic()-started
        metadata['candidateSelection']=dict(policy='Lexicographic feature-row rank; all passing layouts admitted within the search budget.',
                                             considered=passing,selectedStyle=metadata['layoutStyle'],searchSeconds=420)
        write(out/'history.json',history);write(job/'surface-solver.json',metadata)
        return p,q.tolist(),metadata
    raise OpenSurfaceRejected(history)
