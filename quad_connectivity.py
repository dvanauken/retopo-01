"""Local quad edge rotations with protected guide edges and manifold guards."""
from collections import defaultdict
import numpy as np


def dissolve_double_edges(vertices, faces):
    """Merge a two-quad disk around a valence-two interior vertex."""
    v=np.asarray(vertices);q=[list(map(int,f)) for f in faces];removed=0
    while True:
        owners=defaultdict(list)
        for i,f in enumerate(q):
            for a in f:owners[a].append(i)
        found=False
        for vertex,ids in owners.items():
            if len(ids)!=2:continue
            a,b=ids;pair=[q[a],q[b]];common=set(pair[0])&set(pair[1])
            if len(common)!=3:continue
            incident=defaultdict(list)
            for f in pair:
                for x,y in zip(f,f[1:]+f[:1]):incident[tuple(sorted((x,y)))].append((x,y))
            boundary=dict(rows[0] for rows in incident.values() if len(rows)==1)
            if len(boundary)!=4 or vertex in boundary:continue
            ring=[next(iter(boundary))]
            for _ in range(3):ring.append(boundary[ring[-1]])
            if len(set(ring))!=4 or boundary[ring[-1]]!=ring[0]:continue
            q[a]=ring;q.pop(b);removed+=1;found=True;break
        if not found:break
    q=np.asarray(q,int);used=np.unique(q);mapping=np.full(len(v),-1,int);mapping[used]=np.arange(len(used))
    return v[used],mapping[q],dict(dissolvedVertices=removed)


def polychords(faces):
    """Strips of quads joined through opposite edges: (faces, rung edges as vertex pairs, closed)."""
    q=np.asarray(faces,int);owners=defaultdict(list)
    for fi,face in enumerate(q):
        for k in range(4):owners[tuple(sorted((int(face[k]),int(face[(k+1)%4]))))].append((fi,k))
    seen=set();result=[]
    def walk(edge,fi,k):
        strip=[];rungs=[]
        while True:
            strip.append(fi);face=q[fi];k2=(k+2)%4
            nxt=tuple(sorted((int(face[k2]),int(face[(k2+1)%4]))));rungs.append(nxt)
            if nxt==edge:return strip,rungs,True
            others=[(g,j) for g,j in owners[nxt] if g!=fi]
            if not others:return strip,rungs,False
            fi,k=others[0]
    for edge,users in owners.items():
        if edge in seen:continue
        strip,rungs,closed=walk(edge,*users[0])
        if not closed and len(users)==2:
            back,back_rungs,_=walk(edge,*users[1])
            strip=back[::-1]+strip;rungs=back_rungs[::-1]+[edge]+rungs
        elif not closed:rungs=[edge]+rungs
        seen.update(rungs);result.append((strip,rungs,closed))
    return result


def collapse_polychords(vertices, faces, target, protected=(), keep_apart=None, spacing=None, feature_distance=None):
    """Coarsen toward `target` faces by collapsing whole quad strips, thinnest first.

    A collapse merges each rung of the strip into one vertex, so the grid stays
    regular and the edge loops beside the strip survive. A protected vertex keeps
    its position when merged. A rung joining two `keep_apart` vertices farther
    apart than half the coarse spacing is not collapsed when it crosses between
    two feature lines; with `feature_distance` (points -> distance to features),
    a rung whose midpoint lies on a feature runs along it and may shorten it.
    Collapses that would repeat a vertex in a face, create a nonmanifold edge,
    pinch the boundary or change its loop count are skipped.
    """
    from boundary_geometry import loops
    p=np.asarray(vertices,float).copy();q=np.asarray(faces,int);protected=set(map(int,protected))
    keep_apart=set(map(int,() if keep_apart is None else keep_apart));count=len(loops(q));collapsed=0
    def boundary_vertices(faces):
        edges=defaultdict(int)
        for face in faces:
            for a,b in zip(face,np.roll(face,-1)):edges[tuple(sorted((int(a),int(b))))]+=1
        return {v for e,c in edges.items() if c==1 for v in e},edges
    def collapse(strip,rungs,border):
        merge={};moved=p.copy()
        for a,b in rungs:
            a,b=merge.get(a,a),merge.get(b,b)
            if a==b:continue
            # Protected features outrank the boundary, which outranks free vertices.
            rank_a=2 if a in protected else int(a in border);rank_b=2 if b in protected else int(b in border)
            keep,drop=(b,a) if rank_b>rank_a else (a,b)
            if not rank_a and not rank_b:moved[keep]=(moved[a]+moved[b])*.5
            merge={k:(keep if v==drop else v) for k,v in merge.items()};merge[drop]=keep
        removed=set(strip);candidate=np.array([[merge.get(int(v),int(v)) for v in face] for i,face in enumerate(q) if i not in removed])
        if not len(candidate) or any(len(set(face))<4 for face in candidate):return None
        if max(boundary_vertices(candidate)[1].values())>2:return None
        try:
            if len(loops(candidate))!=count:return None
        except ValueError:return None
        return candidate,moved,merge
    while len(q)>target*1.05:
        border,_=boundary_vertices(q);options=[]
        for strip,rungs,closed in polychords(q):
            # A strip crossing itself would also merge the loops it crosses, including crease loops.
            if len(set(strip))!=len(strip) or len(q)-len(strip)<target*.85:continue
            ends={rungs[0],rungs[-1]} if not closed else set()
            # Interior rungs may not pinch the boundary; separate crease loops stay apart.
            if any(r not in ends and r[0] in border and r[1] in border for r in rungs):continue
            if spacing:
                across=[r for r in rungs if r[0] in keep_apart and r[1] in keep_apart and np.linalg.norm(p[r[0]]-p[r[1]])>.5*spacing]
                if across and feature_distance is not None:
                    middle=np.array([(p[a]+p[b])*.5 for a,b in across]);across=[r for r,d in zip(across,feature_distance(middle)) if d>.25*spacing]
                if across:continue
            # Relative width: collapsing the strips that are thinnest for their length squares neighbors up.
            width=np.mean([np.linalg.norm(p[a]-p[b]) for a,b in rungs])
            length=np.mean([np.linalg.norm(p[face[(k+1)%4]]-p[face[k]]) for face in q[strip] for k in range(4)
                            if tuple(sorted((int(face[k]),int(face[(k+1)%4])))) not in set(rungs)])
            options.append((float(width/max(length,1e-12)),strip,rungs))
        result=next((r for r in (collapse(strip,rungs,border) for _,strip,rungs in sorted(options,key=lambda o:o[0])) if r is not None),None)
        if result is None:break
        q,p,merge=result;collapsed+=1
        protected={merge.get(v,v) for v in protected};keep_apart={merge.get(v,v) for v in keep_apart}
    used=np.unique(q);mapping=np.full(len(p),-1,int);mapping[used]=np.arange(len(used))
    return p[used],mapping[q],dict(collapsedStrips=collapsed,faces=len(q),protectedVertices=sorted(mapping[[v for v in protected if mapping[v]>=0]].tolist()))


def vertex_stars(faces):
    """Cyclic neighbor order around each vertex: (neighbors in order, closed) per vertex.

    An open star (boundary vertex) starts at the neighbor on one boundary edge.
    Returns None for a vertex whose incident faces do not chain into one fan.
    """
    q=np.asarray(faces,int);around=defaultdict(list)
    for face in q:
        for k in range(4):around[int(face[k])].append((int(face[k-1]),int(face[(k+1)%4])))
    stars={}
    for vertex,pairs in around.items():
        following={a:b for a,b in pairs};incoming={b for _,b in pairs}
        if len(following)!=len(pairs):stars[vertex]=None;continue
        starts=[a for a,_ in pairs if a not in incoming];closed=not starts
        if len(starts)>1:stars[vertex]=None;continue
        ring=[starts[0] if starts else pairs[0][0]]
        while len(ring)<=len(pairs):
            nxt=following.get(ring[-1])
            if nxt is None or (closed and nxt==ring[0]):break
            ring.append(nxt)
        expected=len(pairs) if closed else len(pairs)+1
        stars[vertex]=(ring,closed) if len(ring)==expected else None
    return stars


def clean_slivers(vertices, faces, protected=(), angle_degrees=15., ratio=5., rounds=20):
    """Remove needle and sliver quads by the collapse that leaves the best corner angles.

    For each offending quad the candidates are its two diagonal collapses and
    its shortest-edge collapse. A collapse merges two vertices (a protected or
    boundary vertex keeps its position), drops the quads that degenerate, and is
    kept only if every face stays a valid quad, every edge stays manifold, the
    boundary keeps its loop count and the worst corner angle among the touched
    faces improves. Repeats until no quad offends or nothing improves.
    """
    from boundary_geometry import loops
    p=np.asarray(vertices,float).copy();q=np.asarray(faces,int);protected=set(map(int,protected));loop_count=len(loops(q));removed=0
    def corner_angles(points,polys):
        P=points[polys];a=P-np.roll(P,1,1);b=np.roll(P,-1,1)-P
        return np.degrees(np.arccos(np.clip(-(a*b).sum(2)/np.maximum(1e-30,np.linalg.norm(a,axis=2)*np.linalg.norm(b,axis=2)),-1,1)))
    def border_of(polys):
        count=defaultdict(int)
        for face in polys:
            for a,b in zip(face,np.roll(face,-1)):count[tuple(sorted((int(a),int(b))))]+=1
        return {v for e,c in count.items() if c==1 for v in e},count
    for _ in range(rounds):
        angles=corner_angles(p,q);lengths=np.linalg.norm(p[np.roll(q,-1,1)]-p[q],axis=2)
        bad=np.flatnonzero((angles.min(1)<angle_degrees)|(lengths.max(1)/np.maximum(lengths.min(1),1e-30)>ratio))
        if not len(bad):break
        border,_=border_of(q);applied=False
        for fi in bad[np.argsort(angles.min(1)[bad])]:
            face=q[fi];options=[(int(face[0]),int(face[2])),(int(face[1]),int(face[3]))]
            k=int(np.argmin(lengths[fi]));options.append((int(face[k]),int(face[(k+1)%4])))
            touched=np.flatnonzero(np.isin(q,face).any(1));before=corner_angles(p,q[touched]).min()
            best=None
            for a,b in options:
                rank=lambda v:2 if v in protected else int(v in border)
                keep,drop=(b,a) if rank(b)>rank(a) else (a,b)
                if rank(keep)==2 and rank(drop)==2:continue
                moved=p.copy()
                if rank(keep)==0:moved[keep]=(p[a]+p[b])*.5
                # Faces left with a repeated vertex are the ones the collapse flattens; they go.
                candidate=np.where(q==drop,keep,q);alive=np.array([len(set(f))==4 for f in candidate])
                if (~alive).sum()>2:continue
                candidate=candidate[alive]
                _,count=border_of(candidate)
                if max(count.values())>2:continue
                try:
                    if len(loops(candidate))!=loop_count:continue
                except ValueError:continue
                changed=np.flatnonzero(np.isin(candidate,[keep]).any(1)|np.isin(candidate,face).any(1))
                after=corner_angles(moved,candidate[changed]).min() if len(changed) else 180.
                if after>before and (best is None or after>best[0]):best=(after,candidate,moved,drop,keep)
            if best is None:continue
            _,q,p,drop,keep=best;protected={keep if v==drop else v for v in protected};removed+=1;applied=True;break
        if not applied:break
    used=np.unique(q);mapping=np.full(len(p),-1,int);mapping[used]=np.arange(len(used))
    return p[used],mapping[q],dict(collapsedSlivers=removed,faces=len(q),protected=sorted(int(mapping[v]) for v in protected if mapping[v]>=0))


def split_strips(vertices, faces, selected_faces, maximum_faces):
    """Conforming quad subdivision: propagate opposite-edge splits to closure."""
    v=np.asarray(vertices);q=np.asarray(faces,int)
    edges=np.sort(np.stack([q,np.roll(q,-1,1)],axis=2),axis=2)
    unique,inverse=np.unique(edges.reshape(-1,2),axis=0,return_inverse=True);ids=inverse.reshape(-1,4)
    mask=np.zeros(len(unique),bool)
    for face in selected_faces:
        proposed=mask.copy();proposed[ids[face]]=True
        while True:
            flags=proposed[ids];expanded=flags|np.roll(flags,2,1)
            before=proposed.sum();proposed[ids[expanded]]=True
            if before==proposed.sum():break
        counts=proposed[ids].sum(1)
        total=len(q)+np.count_nonzero(counts==2)+3*np.count_nonzero(counts==4)
        if total<=maximum_faces:mask=proposed
    values=v.tolist();mid={}
    for ei in np.flatnonzero(mask):
        mid[ei]=len(values);values.append(v[unique[ei]].mean(0).tolist())
    result=[]
    for face,eids in zip(q,ids):
        split=np.flatnonzero(mask[eids])
        if len(split)==0:result.append(face.tolist())
        elif len(split)==2:
            k=int(split[0]);a,b,c,d=np.roll(face,-k);ea,eb=np.roll(eids,-k)[[0,2]]
            result.extend([[int(a),mid[ea],mid[eb],int(d)],[mid[ea],int(b),int(c),mid[eb]]])
        else:
            center=len(values);values.append(v[face].mean(0).tolist())
            result.extend([[int(face[k]),mid[eids[k]],center,mid[eids[(k-1)%4]]] for k in range(4)])
    return np.asarray(values),np.asarray(result),dict(splitEdges=int(mask.sum()),addedFaces=len(result)-len(q))


def split_vertex_stars(vertices, faces, selected_vertices, maximum_faces):
    """Three-quad transition per incident face, with conforming shared midpoints."""
    values=np.asarray(vertices).tolist();result=np.asarray(faces).tolist();count=0
    for vertex in selected_vertices:
        incident=[i for i,f in enumerate(result) if vertex in f]
        if len(result)+2*len(incident)>maximum_faces:continue
        mids={};replacements=[];p=np.asarray(values)
        for i in incident:
            f=result[i];k=f.index(vertex);a,b,c,d=f[k:]+f[:k]
            for neighbor in (b,d):
                edge=tuple(sorted((vertex,neighbor)))
                if edge not in mids:mids[edge]=len(values);values.append(((p[vertex]+p[neighbor])*.5).tolist())
            ab=mids[tuple(sorted((a,b)))];da=mids[tuple(sorted((a,d)))];center=len(values)
            values.append(p[[a,b,c,d]].mean(0).tolist())
            replacements.extend([[center,da,a,ab],[center,ab,b,c],[center,c,d,da]])
        excluded=set(incident);result=[f for i,f in enumerate(result) if i not in excluded]+replacements;count+=1
    return np.asarray(values),np.asarray(result),dict(refinedVertexStars=count,addedFaces=len(result)-len(faces))


def split_vertex_cut(vertices, faces, selected_vertices):
    """Split edges crossing a vertex cut; every quad has 0, 2 or 4 splits.

    A cut wholly inside a patch leaves its boundary untouched. Adjacent split
    edges use a three-quad transition, so no hanging vertices are introduced.
    """
    p=np.asarray(vertices);q=np.asarray(faces,int);selected=set(map(int,selected_vertices))
    values=p.tolist();midpoints={};result=[]
    for face in q:
        flags=[(int(a) in selected)!=(int(b) in selected) for a,b in zip(face,np.roll(face,-1))]
        split=np.flatnonzero(flags)
        if not len(split):result.append(face.tolist());continue
        mids={}
        for k in split:
            edge=tuple(sorted((int(face[k]),int(face[(k+1)%4]))))
            if edge not in midpoints:
                midpoints[edge]=len(values);values.append(p[list(edge)].mean(0).tolist())
            mids[int(k)]=midpoints[edge]
        if len(split)==4:
            center=len(values);values.append(p[face].mean(0).tolist())
            result.extend([[int(face[k]),mids[k],center,mids[(k-1)%4]] for k in range(4)])
        elif (split[1]-split[0])==2:
            k=int(split[0]);a,b,c,d=map(int,np.roll(face,-k));ab=mids[k];cd=mids[(k+2)%4]
            result.extend([[a,ab,cd,d],[ab,b,c,cd]])
        else:
            # Rotate to make the shared selected corner the first vertex.
            k=next(k for k in range(4) if flags[k] and flags[(k-1)%4])
            a,b,c,d=map(int,np.roll(face,-k));ab=mids[k];da=mids[(k-1)%4]
            center=len(values);values.append(p[face].mean(0).tolist())
            result.extend([[center,da,a,ab],[center,ab,b,c],[center,c,d,da]])
    return np.asarray(values),np.asarray(result),dict(splitEdges=len(midpoints),addedFaces=len(result)-len(q),
                                                     edgeVertices=[[a,b,vertex] for (a,b),vertex in midpoints.items()])


def corner_scores(vertices, faces):
    p = np.asarray(vertices)[np.asarray(faces)]
    d = np.roll(p, -1, axis=1)-p
    previous = -np.roll(d, 1, axis=1)
    den = np.maximum(1e-20, np.linalg.norm(d, axis=2)*np.linalg.norm(previous, axis=2))
    corners = np.cross(d, previous)/den[:, :, None]
    a = np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0])
    b = np.cross(p[:, 2]-p[:, 0], p[:, 3]-p[:, 0])
    c = np.cross(p[:, 2]-p[:, 1], p[:, 3]-p[:, 1])
    e = np.cross(p[:, 3]-p[:, 1], p[:, 0]-p[:, 1])
    normals = np.stack([a, b, c, e, a+b], axis=1)
    normals /= np.maximum(1e-20, np.linalg.norm(normals, axis=2))[:, :, None]
    return np.einsum('fci,fni->fcn', corners, normals).min(axis=(1, 2))


def improve(vertices, faces, protected=(), passes=4):
    faces = np.asarray(faces, dtype=int).copy()
    protected = {tuple(sorted(map(int,e))) for e in protected}
    history=[]
    for step in range(passes):
        incidence=defaultdict(set)
        for i, face in enumerate(faces):
            for a,b in zip(face,np.roll(face,-1)):incidence[tuple(sorted((int(a),int(b))))].add(i)
        scores=corner_scores(vertices,faces);changed=set();flips=0
        for i in np.argsort(scores):
            if scores[i]>=.5:break
            if i in changed:continue
            for a,b in zip(faces[i],np.roll(faces[i],-1)):
                edge=tuple(sorted((int(a),int(b))))
                if edge in protected or len(incidence[edge])!=2:continue
                j=next(k for k in incidence[edge] if k!=i)
                if j in changed:continue
                pair=faces[[i,j]]
                if len(set(pair.ravel()))!=6:continue
                boundary={int(x):int(y) for f in pair for x,y in zip(f,np.roll(f,-1)) if tuple(sorted((int(x),int(y))))!=edge}
                if len(boundary)!=6:continue
                ring=[next(iter(boundary))]
                for _ in range(5):ring.append(boundary[ring[-1]])
                if len(set(ring))!=6 or boundary[ring[-1]]!=ring[0]:continue
                old=min(scores[i],scores[j]);best=None
                for offset in range(3):
                    r=ring[offset:]+ring[:offset];diagonal=tuple(sorted((r[0],r[3])))
                    if diagonal in incidence:continue
                    proposal=np.array([r[:4],[r[3],r[4],r[5],r[0]]])
                    score=corner_scores(vertices,proposal).min()
                    if score>old+.02 and (best is None or score>best[0]):best=(score,proposal)
                if best is None:continue
                for k,face in zip((i,j),pair):
                    for x,y in zip(face,np.roll(face,-1)):
                        key=tuple(sorted((int(x),int(y))));incidence[key].discard(k)
                        if not incidence[key]:del incidence[key]
                faces[[i,j]]=best[1]
                for k,face in zip((i,j),best[1]):
                    for x,y in zip(face,np.roll(face,-1)):incidence[tuple(sorted((int(x),int(y))))].add(k)
                changed.update((i,j));flips+=1;break
        history.append(dict(step=step,flips=flips,minimumProjectedJacobian=float(corner_scores(vertices,faces).min())))
        if not flips:break
    return faces,history


def weld_pinched_quads(vertices, faces, tolerance=1e-9):
    """Merge coincident vertex copies that share a quad and drop the quads left with fewer
    than four distinct corners. The layout engine splits a non-manifold vertex into one copy
    per fan; a quad pinched between two copies has zero area and no fit can open it."""
    v=np.asarray(vertices,float);q=np.asarray(faces,int);mapping=np.arange(len(v));welded=0
    for face in q:
        for i in range(4):
            for j in range(i+1,4):
                a,b=mapping[face[i]],mapping[face[j]]
                if a!=b and np.linalg.norm(v[a]-v[b])<=tolerance:
                    mapping[(mapping==a)|(mapping==b)]=min(a,b);welded+=1
    q=mapping[q];keep=np.array([len(set(f.tolist()))==4 for f in q],bool);q=q[keep]
    used=np.unique(q);remap=np.full(len(v),-1,int);remap[used]=np.arange(len(used))
    return v[used],remap[q],dict(weldedVertices=int(welded),droppedPinchedQuads=int((~keep).sum()))


def fill_triangle_holes(vertices, faces, keep_loops):
    """Close three-sided holes the layout engine leaves where no quad could be extracted.

    The hole and the quad across one of its edges form a pentagon, which becomes two quads
    once that quad's far edge is split; the split continues through the polychord until it
    reaches a boundary or returns to itself (a quad the chord crosses twice is split four
    ways), so the result stays a conforming quad mesh. `keep_loops` boundary loops (the
    source's) are left alone. Raises ValueError when a chord would re-enter the hole's quad."""
    v=np.asarray(vertices,float).tolist();q=[list(map(int,f)) for f in faces];filled=0;added=0
    while True:
        owners=defaultdict(list)
        for i,f in enumerate(q):
            for k in range(4):owners[tuple(sorted((f[k],f[(k+1)%4])))].append((i,k))
        adjacency=defaultdict(list)
        for (a,b),users in owners.items():
            if len(users)==1:adjacency[a].append(b);adjacency[b].append(a)
        loops=[];seen=set()
        for start in adjacency:
            if start in seen:continue
            stack=[start];component=[]
            while stack:
                x=stack.pop()
                if x in seen:continue
                seen.add(x);component.append(x);stack.extend(adjacency[x])
            loops.append(component)
        holes=[c for c in loops if len(c)==3]
        if len(loops)<=keep_loops or not holes:break
        hole=holes[0];choice=None
        for a,b in ((hole[0],hole[1]),(hole[1],hole[2]),(hole[2],hole[0])):
            (fi,k),=owners[tuple(sorted((a,b)))];face=q[fi];x0,x1,x2,x3=face[k:]+face[:k]
            apex=(set(hole)-{x0,x1}).pop()
            if apex in (x2,x3):continue
            # Walk the polychord through the quad's far edge, collecting the edges to split;
            # of the three hole edges, the one with the shortest chord is used.
            chord=[tuple(sorted((x2,x3)))];previous=fi;valid=True
            while True:
                users=[(g,j) for g,j in owners[chord[-1]] if g!=previous]
                if not users:break   # a boundary edge: its midpoint becomes a boundary vertex
                gi,j=users[0]
                if gi==fi:valid=False;break   # the chord would re-enter the hole's own quad
                face=q[gi];opposite=tuple(sorted((face[(j+2)%4],face[(j+3)%4])))
                if opposite in chord:break   # the polychord closed on itself
                chord.append(opposite);previous=gi
            if valid and (choice is None or len(chord)<len(choice[0])):choice=(chord,fi,x0,x1,x2,x3,apex)
        if choice is None:raise ValueError('A three-sided layout hole could not be repaired.')
        chord,fi,x0,x1,x2,x3,apex=choice
        chord=set(chord);mids={}
        for a,b in chord:mids[(a,b)]=len(v);v.append(((np.asarray(v[a])+np.asarray(v[b]))*.5).tolist())
        result=[]
        for i,face in enumerate(q):
            split=[k for k in range(4) if tuple(sorted((face[k],face[(k+1)%4]))) in chord]
            if i==fi:
                if split!=[(k for k in range(4) if {face[k],face[(k+1)%4]}=={x2,x3}).__next__()]:raise ValueError('A three-sided layout hole could not be repaired.')
                m=mids[tuple(sorted((x2,x3)))];result+=[[x1,x2,m,apex],[apex,m,x3,x0]];added+=1
            elif not split:result.append(face)
            elif len(split)==2:
                k=split[0];a,b,c,d=face[k:]+face[:k];m1=mids[tuple(sorted((a,b)))];m2=mids[tuple(sorted((c,d)))]
                result+=[[a,m1,m2,d],[m1,b,c,m2]];added+=1
            else:
                centre=len(v);v.append(np.mean([v[x] for x in face],axis=0).tolist())
                result+=[[face[k],mids[tuple(sorted((face[k],face[(k+1)%4])))],centre,mids[tuple(sorted((face[k],face[(k-1)%4])))]] for k in range(4)];added+=3
        q=result;filled+=1
    return np.asarray(v),np.asarray(q,int),dict(filledTriangleHoles=filled,addedQuads=added)
