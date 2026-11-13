"""Constrained source edges for the layout engine: guide cuts and admitted creases in one list.

ZRemesher at Curves Strength 100 (curve mode 2) cuts each guide into the source
(native_guide_cut), collects the cut edges and the kept feature edges into one
constrained-edge vector with a mode per edge (0x2889c0/0x28e230), writes each
edge's direction to the field and registers mode-2 edges in the integer solve
(0x2fc0c0, 0x28b920). `constrained` prepares exactly that input for the
application's layout engine: the cut source and one ordered list, guides
first, then creases. The engine side is the `-constrained-edges` flag of the
guided QuadriFlow fork; it is an independent implementation of the native
contract, not native arithmetic.

`prepare`, `reference_paths` and `output_paths` serve the older opt-in
experiment (RETOPO_FEATURE_LAYOUT=registered, the path-provenance engine). It
now cuts guides with the same recovered rules.
"""
from pathlib import Path
import json
import numpy as np
from native_guide_cut import cut
from feature_rows import graph_paths
from guided_layout import obj, write


def reference_paths(source, feature_edges, curves):
    source=np.asarray(source,float);curves=[np.asarray(c,float) for c in curves]
    tolerance=float(np.ptp(source,axis=0).max())*1e-9
    source_paths=graph_paths(feature_edges)
    points=curves+[source[np.asarray(path,int)] for path in source_paths]
    result=[dict(id=i,kind='guide' if i<len(curves) else 'crease',points=c.tolist(),
                 closed=bool(np.linalg.norm(c[0]-c[-1])<=tolerance)) for i,c in enumerate(points)]
    for i,path in enumerate(source_paths,len(curves)):result[i]['vertices']=list(map(int,path))
    return result


def output_paths(packet, reference):
    """Validate exact engine output IDs; keep the fitter's repeated closure form."""
    if not packet.get('passed'):raise ValueError('Registered extraction did not preserve every feature path')
    incoming={int(row['id']):row for row in packet.get('paths',[])}
    if set(incoming)!={int(row['id']) for row in reference}:raise ValueError('Registered extraction feature identities do not match the input')
    result=[]
    for ref in reference:
        row=incoming[int(ref['id'])];ids=list(map(int,row['vertices']));closed=bool(row['closed'])
        if closed!=ref['closed'] or len(ids)<2:raise ValueError('Registered extraction changed feature closure')
        if closed and ids[0]!=ids[-1]:ids.append(ids[0])
        unique=ids[:-1] if closed else ids
        if len(set(unique))!=len(unique) or (closed and len(unique)<3):raise ValueError('Registered extraction collapsed a feature path')
        result.append(dict(id=ref['id'],feature=ref['id'],kind=ref['kind'],closed=closed,vertices=ids))
    return result


def prepare(source, triangles, feature_edges, curves, folder):
    source=np.asarray(source,float);triangles=np.asarray(triangles,int)
    curves=[np.asarray(c,float) for c in curves];folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    crease_paths=graph_paths(feature_edges)
    requested=curves+[source[np.asarray(path,int)] for path in crease_paths]
    if curves:
        points,faces,embedding=cut(source,triangles,curves,source_paths=crease_paths)
        write(folder/'embedding.json',embedding)
        write(folder/'embedding-check.json',dict(passed=True,method=embedding['method']+' Topology, winding and one simple chain per guide are checked by the cut itself.'))
        edge_sets=embedding['guideEdges']
    else:
        points,faces=source.copy(),triangles.copy()
        edge_sets={str(i):list(zip(path[:-1],path[1:])) for i,path in enumerate(crease_paths)}
        write(folder/'embedding-check.json',dict(passed=True,method='Existing source-edge paths; original triangulation and vertex IDs retained.'))
    tolerance=float(np.ptp(source,axis=0).max())*1e-9 # existing embedding tolerance
    paths=[];descriptors=[]
    for identity,curve in enumerate(requested):
        chains=graph_paths(edge_sets.get(str(identity),[]))
        if len(chains)!=1:raise ValueError(f'Feature {identity} did not embed as one ordered path')
        chain=list(map(int,chains[0]));closed=chain[0]==chain[-1]
        expected_closed=bool(np.linalg.norm(curve[0]-curve[-1])<=tolerance)
        if closed!=expected_closed:raise ValueError(f'Feature {identity} changed closure during embedding')
        # Open chains are oriented to the original path. Closed-chain starting
        # vertex is arbitrary: it supplies identity/period, not an XYZ anchor.
        if not closed and np.linalg.norm(points[chain[-1]]-curve[0])<np.linalg.norm(points[chain[0]]-curve[0]):chain.reverse()
        vertices=chain[:-1] if closed else chain
        kind='guide' if identity<len(curves) else 'crease'
        paths.append(dict(id=identity,kind=kind,closed=closed,vertices=vertices))
        descriptors.append(dict(id=identity,kind=kind,closed=closed,points=curve.tolist()))
    obj(folder/'source.obj',points,faces)
    with (folder/'features.txt').open('w',encoding='utf-8') as stream:
        stream.write(str(len(paths))+'\n')
        for path in paths:
            values=[path['id'],int(path['closed']),len(path['vertices']),*path['vertices']]
            stream.write(' '.join(map(str,values))+'\n')
    write(folder/'paths.json',dict(paths=paths,referencePaths=descriptors,
          sourceVertices=len(source),embeddedVertices=len(points),sourceTriangles=len(triangles),embeddedTriangles=len(faces),
          policy='Exact admitted source-edge graph; user curves embedded; no one-output-vertex-per-input-sample requirement.'))
    return dict(source=folder/'source.obj',features=folder/'features.txt',paths=paths,referencePaths=descriptors)


# Modes of the engine's -constrained-edges list (guide-constraints.hpp).
GUIDE_MODE=2              # native mode 2: direction, lattice line (integer registration), preserved edge
CREASE_ROW_MODE=3         # engine mode: direction and preserved edge, no lattice line
CREASE_DIRECTION_MODE=1   # native mode 1: direction only


def constrained(source, triangles, curves, hard, soft, folder, sizes=None):
    """Cut source and ONE constrained-edge list for the layout engine.

    Guides are always native mode 2 here: Curves Strength 100 is the only
    strength this application implements. `hard` and `soft` are admitted
    crease edges as source vertex pairs. Hard ones are preserved edges with
    the direction write (engine mode 3); soft ones only direct the field
    (native mode 1). List order is the native write order: guide edges first,
    then the feature edges, so a crease has the last word where the two meet
    (0x276080). Returns the file paths, the cut mesh, the guide chains as
    cut-mesh vertex ids and the cut report.

    Engineering: native registers its kept features as mode 2 as well. Here
    crease rows are not given the lattice line, because this application
    admits creases closer together than native's integer solve would merge:
    with mode 2 on creases, island 6's front crease, half a face from the rim
    row at a request of 750, got no row in any of 64 layouts.

    `sizes` (the user's 'Add faces where the shape needs them' option only):
    for each crease edge, hard ones first and then soft ones, the largest face
    size at that edge as a fraction of the requested size, or 1 for none. It
    is written as a fourth column the engine reads with `-size-caps` (build
    constrained-sizes-19 or later). The rule that sets the sizes is
    crease_rows.local_sizes; it is this application's, not a native field.
    """
    source=np.asarray(source,float);triangles=np.asarray(triangles,int)
    curves=[np.asarray(c,float) for c in curves];folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    creases=[(int(a),int(b),CREASE_ROW_MODE) for a,b in np.asarray(hard,int).reshape(-1,2)]+[(int(a),int(b),CREASE_DIRECTION_MODE) for a,b in np.asarray(soft,int).reshape(-1,2)]
    rows=[];chains=[]
    sizes=None if sizes is None else np.asarray(sizes,float).reshape(-1)
    if sizes is not None and (len(sizes)!=len(creases) or not np.all((sizes>0)&(sizes<=1))):
        raise ValueError('Crease face sizes must be one fraction in (0, 1] per crease edge.')
    if curves:
        # Every crease edge is its own identity, so each keeps its mode where a guide cuts it in two.
        points,faces,report=cut(source,triangles,curves,source_paths=[[a,b] for a,b,_ in creases])
        for index in range(len(curves)):
            chain=[int(v) for v in report['chains'][str(index)]];chains.append(chain)
            rows.extend((a,b,GUIDE_MODE,index) for a,b in zip(chain[:-1],chain[1:]))
        for index,(_,_,mode) in enumerate(creases,len(curves)):
            rows.extend((int(a),int(b),mode,index) for a,b in report['guideEdges'][str(index)])
    else:
        points,faces,report=source.copy(),triangles.copy(),None
        rows=[(a,b,mode,index) for index,(a,b,mode) in enumerate(creases)]
    if not rows:raise ValueError('No constrained edges: the part has neither guides nor admitted creases.')
    obj(folder/'source.obj',points,faces)
    with (folder/'constrained-edges.txt').open('w',encoding='utf-8') as stream:
        stream.write(str(len(rows))+'\n')
        for a,b,mode,index in rows:
            # A crease edge keeps its size where a guide cuts it in two; guide edges carry none.
            size=sizes[index-len(curves)] if sizes is not None and index>=len(curves) else 1.
            stream.write(f'{a} {b} {mode}\n' if size>=1 else f'{a} {b} {mode} {float(size):.9g}\n')
    summary=dict(guides=len(curves),guideEdges=sum(len(c)-1 for c in chains),registeredCreaseEdges=sum(1 for *_,mode,i in rows if mode!=1 and i>=len(curves)),
                 directedCreaseEdges=sum(1 for *_,mode,i in rows if mode==1),listedEdges=len(rows),
                 sourceVertices=len(source),cutVertices=len(points),sourceTriangles=len(triangles),cutTriangles=len(faces),
                 order='Guide cut edges first, then admitted crease edges; a later edge overwrites an earlier direction at a shared vertex.',
                 modes='2 = direction, lattice line and preserved edge: native mode 2 (guides at strength 100); 3 = direction and preserved edge, no lattice line: engine mode (row and sharp creases); 1 = direction only: native mode 1 (gentle short creases).')
    if sizes is not None:
        summary.update(sizedCreaseEdges=int((sizes<1).sum()),smallestCreaseFaceSize=float(sizes.min()) if len(sizes) else 1.,
                       sizes='Fourth column: largest face size at a crease edge as a fraction of the requested size (crease_rows.local_sizes; application policy).')
    if report is not None:
        summary.update(relocatedSourceVertices=report['relocatedVertices'],spans=report['spans'],attachments=report['attachments'],
                       guideSampleMaxDistance=report['guideSampleMaxDistance'],method=report['method'],constants=report['constants'])
        write(folder/'guide-cut.json',report)
    write(folder/'constrained-edges.json',summary)
    return dict(source=folder/'source.obj',edges=folder/'constrained-edges.txt',points=points,faces=faces,chains=chains,summary=summary)
