"""Ordinary mesh edge numbering and incidence from ordered polygon indices."""
import numpy as np


def packed(rows):
    offsets=np.cumsum([0]+[len(row) for row in rows],dtype=np.int32)
    return offsets,np.asarray([v for row in rows for v in row],dtype='<i4')


def build(vertex_count,faces):
    rows=[list(map(int,row)) for row in faces];corners=[[] for _ in range(vertex_count)];corner=0
    for face,row in enumerate(rows):
        if len(row)<3 or len(set(row))!=len(row):raise NotImplementedError('Short/repeated-index polygon')
        for k,vertex in enumerate(row):
            if not 0<=vertex<vertex_count:raise ValueError('Vertex index outside logical count')
            corners[vertex].append((corner,row[(k+1)%len(row)],row[(k-1)%len(row)]));corner+=1
    edges=[]
    for vertex,incident in enumerate(corners):
        seen=set()
        for _,following,previous in incident:
            for neighbor in [following,previous]:
                if neighbor>vertex and neighbor not in seen:seen.add(neighbor);edges.append((vertex,neighbor))
    lookup={edge:i for i,edge in enumerate(edges)};edge_corners=[[] for _ in edges];face_edges=[];corner=0
    for row in rows:
        for a,b in zip(row,row[1:]+row[:1]):
            edge=lookup[tuple(sorted((a,b)))];face_edges.append(edge);edge_corners[edge].append(corner);corner+=1
    if any(len(row)>2 for row in edge_corners):raise NotImplementedError('Nonmanifold edge identity policy')
    vertex_edges=[[] for _ in range(vertex_count)]
    for edge,(a,b) in enumerate(edges):vertex_edges[a].append(edge);vertex_edges[b].append(edge)
    eo,ec=packed(edge_corners);vo,vc=packed([[item[0] for item in row] for row in corners]);veo,ve=packed(vertex_edges)
    return dict(edges=np.asarray(edges,dtype='<i4').reshape(-1,2),faceEdges=np.asarray(face_edges,dtype='<i4'),edgeCornerOffsets=eo,edgeCorners=ec,vertexCornerOffsets=vo,vertexCorners=vc,vertexEdgeOffsets=veo,vertexEdges=ve)
