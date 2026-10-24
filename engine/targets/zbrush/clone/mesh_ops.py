"""Explicit engineering mesh primitives for otherwise guarded ordinary inputs.

These complete conforming edge insertion and face-fan boundary traversal. They
are not claims of recovered native allocation, cap splitting or repair policy.
"""
from collections import defaultdict
import heapq
import numpy as np
import triangle
from recovered_mesh_topology import build
from recovered_closed_fractional_vertex_maps import construct

def _guide_paths(positions,triangles,maps):
    top=build(len(positions),triangles);edges=top['edges'];lookup={tuple(map(int,e)) for e in edges}
    adjacency=defaultdict(list)
    for a,b in edges:adjacency[int(a)].append(int(b));adjacency[int(b)].append(int(a))
    epsilon=2e-6*max(float(np.ptp(positions.astype(float),axis=0).max()),1e-12);out=[]
    for row in maps:
        path=[int(row[0])] if len(row) else []
        for a,b in zip(row[:-1],row[1:]):
            a,b=int(a),int(b)
            if a==b:continue
            if tuple(sorted((a,b))) in lookup:path.append(b);continue
            p=positions[a].astype(float);d=positions[b].astype(float)-p;den=float(d@d)
            if den==0:raise ValueError('Coincident distinct guide vertices')
            values=(positions.astype(float)-p)@d/den
            distances=np.linalg.norm(positions.astype(float)-p-values[:,None]*d,axis=1)
            allowed=(values>=-1e-6)&(values<=1+1e-6)&(distances<=epsilon)
            queue=[(0.,a)];distance={a:0.};parent={}
            while queue:
                cost,v=heapq.heappop(queue)
                if v==b:break
                if cost!=distance[v]:continue
                for other in adjacency[v]:
                    if not allowed[other] or values[other]+1e-6<values[v]:continue
                    candidate=cost+float(np.linalg.norm(positions[other].astype(float)-positions[v]))
                    if candidate<distance.get(other,float('inf')):
                        distance[other]=candidate;parent[other]=v;heapq.heappush(queue,(candidate,other))
            if b not in parent:raise NotImplementedError('No conforming straight guide path after edge insertion')
            part=[b]
            while part[-1]!=a:part.append(parent[part[-1]])
            path.extend(reversed(part[:-1]))
        out.append(np.asarray(path,'<i4'))
    return out

def cut_existing_edges(positions,faces,segments,prepare_paths):
    """Insert every fractional source-edge point into both incident faces.

    Face chords are planar constrained triangulations. Original source vertices
    and input path identities are retained; map offsets describe prepared paths,
    not invented native sample maps for newly inserted intersection vertices.
    """
    source=np.asarray(positions,'<f4');faces=np.asarray(faces,'<i4');top=build(len(source),faces)
    edges=top['edges'];relocated,paths,requests,diagnostic=prepare_paths(source,edges,segments)
    if any(np.any(p['edges']<0) for p in paths):raise NotImplementedError('Free/interior point records use the recovered full face cutter')
    output,maps,starts=construct(relocated,edges,paths);edge_points=defaultdict(set);chords=defaultdict(list)
    for path,mapped,offsets in zip(paths,maps,starts):
        ids=np.empty(len(path['points']),dtype=np.int32)
        for k,start in enumerate(offsets):ids[start:offsets[k+1] if k+1<len(offsets) else len(ids)]=mapped[k]
        for edge,t,vertex in zip(path['edges'],path['parameters'],ids):
            if t not in (0,1):edge_points[int(edge)].add((float(t),int(vertex)))
        for i,face in enumerate(path['faces']):
            a,b=map(int,ids[i:i+2])
            if int(face)>=0 and a!=b:chords[int(face)].append((a,b))
    replacement={};points=[p.copy() for p in output]
    for face,row in enumerate(faces):
        perimeter=[]
        for k,a in enumerate(row):
            a=int(a);perimeter.append(a);edge=int(top['faceEdges'][3*face+k])
            ordered=sorted((t if a==int(edges[edge,0]) else 1-t,vertex) for t,vertex in edge_points[edge])
            perimeter.extend(vertex for _,vertex in ordered)
        constraints=chords[face]
        if len(perimeter)==3 and all(tuple(sorted(pair)) in {tuple(sorted((int(row[k]),int(row[(k+1)%3])))) for k in range(3)} for pair in constraints):continue
        mapping=list(dict.fromkeys(perimeter));index={v:i for i,v in enumerate(mapping)}
        if any(a not in index or b not in index for a,b in constraints):raise NotImplementedError('Face-chord endpoint is not on its original perimeter')
        p=np.asarray(points,'<f4');a,b,c=p[row].astype(float);axis=b-a;axis/=np.linalg.norm(axis);other=c-a-axis*float((c-a)@axis);other/=np.linalg.norm(other)
        delta=p[mapping].astype(float)-a;uv=np.column_stack([delta@axis,delta@other])
        if len(set(map(tuple,uv)))!=len(uv):raise NotImplementedError('Coincident boundary point identity needs separate qualification')
        pairs={tuple(sorted((index[x],index[y]))) for x,y in zip(perimeter,perimeter[1:]+perimeter[:1]) if x!=y}
        pairs.update(tuple(sorted((index[x],index[y]))) for x,y in constraints if x!=y)
        result=triangle.triangulate(dict(vertices=uv,segments=np.asarray(sorted(pairs),'<i4')),'pzQ')
        for x,y in result['vertices'][len(mapping):]:mapping.append(len(points));points.append(np.asarray(a+x*axis+y*other,'<f4'))
        if 'triangles' not in result:raise RuntimeError('Conforming source-face triangulation produced no faces')
        replacement[face]=np.asarray(mapping,dtype=np.int32)[result['triangles']].tolist()
    triangles=[row.tolist() for i,row in enumerate(faces) if i not in replacement]
    for face in sorted(replacement):triangles.extend(replacement[face])
    output=np.asarray(points,'<f4');triangles=np.asarray(triangles,'<i4');maps=_guide_paths(output,triangles,maps)
    return output,triangles.tolist(),maps,starts,dict(engineeringExistingEdgeInsertion=True,
            replacedFaces=len(replacement),fractionalSourceEdges=sum(bool(values) for values in edge_points.values()),
            relocationRequests=requests,preparation=diagnostic,
            scope='Conforming source-edge insertion plus per-face PSLG; engineering fallback, not native ordered source replacement/sample-map recovery')

def cap_face_fans(vertices,faces,protected,enabled=True):
    """Find boundary successors by walking each existing incident face fan."""
    rows=[list(map(int,row)) for row in faces];incidence=defaultdict(list)
    for face,row in enumerate(rows):
        if len(row)<3 or len(set(row))!=len(row):raise ValueError('Invalid pre-cap polygon')
        for k,(a,b) in enumerate(zip(row,row[1:]+row[:1])):incidence[tuple(sorted((a,b)))].append((face,k,a,b))
    if any(len(values)>2 for values in incidence.values()):raise NotImplementedError('Nonmanifold edge cap repair is not implemented')
    boundary={(face,k):(face,k,a,b) for values in incidence.values() if len(values)==1 for face,k,a,b in values};successor={}
    for key,(face,k,a,b) in boundary.items():
        f,j=face,(k+1)%len(rows[face])
        for _ in range(len(rows)+1):
            x,y=rows[f][j],rows[f][(j+1)%len(rows[f])]
            if x!=b:raise RuntimeError('Boundary fan lost its vertex')
            linked=incidence[tuple(sorted((x,y)))]
            if len(linked)==1:successor[key]=(f,j);break
            other=next(item for item in linked if item[0]!=f)
            if other[2]!=y or other[3]!=x:raise ValueError('Inconsistent pre-cap orientation')
            f,j=other[0],(other[1]+1)%len(rows[other[0]])
        else:raise RuntimeError('Boundary fan did not reach an outgoing boundary')
    visited=set();loops=[]
    for seed in sorted(boundary):
        if seed in visited:continue
        current=seed;loop=[]
        while current not in visited:
            visited.add(current);loop.append(boundary[current][2]);current=successor[current]
        if current!=seed:raise RuntimeError('Boundary successor merged two cycles')
        pending=[loop]
        while pending:
            part=pending.pop();seen={};split=False
            for i,v in enumerate(part):
                if v in seen:
                    j=seen[v];a,b=part[j:i],part[:j]+part[i:]
                    if min(len(a),len(b))<3:raise NotImplementedError('Boundary digon/short repeated-vertex repair')
                    pending.extend([a,b]);split=True;break
                seen[v]=i
            if not split:loops.append(part)
    events=[]
    for loop in loops:
        if not enabled or any(protected[v] for v in loop) or len(loop)>=1000:continue
        if len(loop)<3:raise NotImplementedError('Short boundary cap')
        cap=list(reversed(loop));rows.append(cap);events.append(dict(loop=loop,appended=cap,branch='engineering-face-fan-cap'))
    return rows,loops,events
