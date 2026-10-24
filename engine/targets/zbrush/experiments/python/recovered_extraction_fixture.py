"""Load only conditioned geometry, own final UVs, guides and initial constants."""
import json,struct
from pathlib import Path
import numpy as np
from recovered_extraction_graph import Graph
from recovered_mesh_topology import build as topology
from recovered_extraction_guide_tags import build
ROOT=Path(__file__).resolve().parents[4]


def load(root):
    inp=root/'input';read=lambda n,d,w=None:np.fromfile(inp/n,d).reshape(-1,w) if w else np.fromfile(inp/n,d)
    xyz=read('source-positions.bin','<f4',3);tri=read('source-face-indices.i32','<i4',3);pt=read('parameter-face-indices.i32','<i4',3);uv=np.fromfile(ROOT/'work/zbrush/runtime/algorithm-recovery/composed-final-parameter-positions.f32x2','<f4').reshape(-1,2);own_topology=topology(len(xyz),tri);fe=own_topology['faceEdges'].reshape(-1,3);eo=own_topology['edgeCornerOffsets'];ec=own_topology['edgeCorners'];quarters=read('quarters.i32','<i4');seeds=read('source-seeds.i32','<i4');curves=[];folder=root/'guide-tags'
    for path in sorted(folder.glob('curve-*-header.bin')):
        b=path.read_bytes();curves.append(dict(mode=struct.unpack_from('<i',b,200)[0],active=bool(b[204]),primaryPairs=np.fromfile(folder/path.name.replace('header.bin','primary.i32x2'),'<i4').reshape(-1,2)))
    tags=build(curves,own_topology['edges'],own_topology['vertexEdgeOffsets'],own_topology['vertexEdges'],len(xyz));delta=np.float32(xyz.max(axis=0)-xyz.min(axis=0));f=np.float32;length=f(np.sqrt(f(f(delta[1]*delta[1]+delta[0]*delta[0])+delta[2]*delta[2])));threshold=f(length*f(1e-7));cut_distance=f(length*f(1e-6));cut_threshold=f(cut_distance*cut_distance)
    graph=Graph(xyz,tri,pt,uv,fe,eo,ec,quarters,seeds,threshold,cut_threshold,tags)
    graph.source_edges=own_topology['edges'];o=own_topology['vertexEdgeOffsets'];flat=own_topology['vertexEdges'];graph.vertex_edges=[list(map(int,flat[a:b])) for a,b in zip(o[:-1],o[1:])]
    return graph
