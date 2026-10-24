"""Source-face ordered work-node reuse, engine RVA 0x2ad390.

Buckets contain newest first. Threshold arguments are compared to squared
distance directly, including the caller's dimensionally unusual default.
"""
import numpy as np


def squared_distance(a,b):
    f=np.float32;d=[f(f(x)-f(y)) for x,y in zip(a,b)]
    return f(f(f(d[1]*d[1])+f(d[0]*d[0]))+f(d[2]*d[2]))


def lookup(face,corner,position,expand,threshold,buckets,positions,triangles,
           face_edges,edge_corners,vertex_corners,cut_edges,cut_threshold):
    visited=set();searched=[]
    def scan(f,t):
        searched.append(int(f));visited.add(int(f))
        for pointer in buckets[f]:
            if squared_distance(positions[pointer],position)<t:return pointer
        return 0
    found=scan(face,threshold)
    if found or not expand:return found,searched
    if corner>=0:
        edge=int(face_edges[face,corner]);cs=edge_corners[edge]
        if len(cs)==2:
            current=3*face+corner
            other=cs[-1] if cs[0]==current else cs[0] if cs[-1]==current else -1
            if other>=0:
                found=scan(other//3,cut_threshold if edge in cut_edges else threshold)
                if found:return found,searched
    for vertex in triangles[face]:
        for c in vertex_corners[int(vertex)]:
            f=c//3
            if f not in visited:
                found=scan(f,threshold)
                if found:return found,searched
    return 0,searched
