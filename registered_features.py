"""Prepare exact feature-edge identities for the registered QuadriFlow experiment.

Native evidence: embedded edges, shared scalar equalities, mode-2 integer
registration and extraction ownership are separate stages. This module translates
that contract into the independent fork; embedding arithmetic and policy are not
claimed byte-exact. Geometry and all acceptance tolerances stay unchanged.
"""
from pathlib import Path
import json
import numpy as np
from guide_embedding import embed
from guide_embedding_check import verify
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
        points,faces,embedding=embed(source,triangles,curves,source_paths=crease_paths)
        checked=verify(source,triangles,points,faces,embedding,requested)
        write(folder/'embedding.json',embedding);write(folder/'embedding-check.json',checked)
        if not checked['passed']:
            raise ValueError('Registered feature embedding failed coverage or ordered graph checks')
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
