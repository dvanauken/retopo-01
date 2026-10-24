"""Ordinary original-segment to source cut mesh with one boundary chord per face.

Original projection/walk records are explicit inputs, not recovered by this helper.
"""
import numpy as np
from recovered_mesh_topology import build
from recovered_closed_incident_cut_preparation import prepare
from recovered_closed_fractional_vertex_maps import construct
from recovered_cut_guide_adjacency_repair import repair
from verify_cut_polygon_conversion import triangulate
from verify_boundary_triangle_cuts import split


def cut(positions,faces,segments):
    if any(np.any(p["edges"]<0) for p in segments):
        from recovered_face_intersection_source_cut import cut as interior_cut
        return interior_cut(positions,faces,segments)
    faces=[list(map(int,f)) for f in faces]
    if any(len(f)!=3 for f in faces):raise NotImplementedError('Triangle source required')
    count=len(positions);edges=build(count,faces)['edges'];relocated,paths,requests,diagnostic=prepare(positions,edges,segments);out,mapsA,mapsB=construct(relocated,edges,paths);constraints={}
    for path,a,b in zip(paths,mapsA,mapsB):
        ids=np.empty(len(path['points']),dtype='<i4')
        for k,start in enumerate(b):ids[start:b[k+1] if k+1<len(b) else len(ids)]=a[k]
        def scalar(index,face):
            vertex=int(ids[index]);tri=faces[face]
            if vertex<count:
                if vertex not in tri:raise NotImplementedError('Endpoint not in interval face')
                return float(tri.index(vertex))
            edge=int(path['edges'][index]);parameter=float(path['parameters'][index]);u,v=map(int,edges[edge])
            for k,(x,y) in enumerate(zip(tri,tri[1:]+tri[:1])):
                if (x,y)==(u,v):s=k+parameter;return 0. if s==3 else s
                if (x,y)==(v,u):s=k+(1-parameter);return 0. if s==3 else s
            raise NotImplementedError('Fractional source edge not in interval face')
        for i,face in enumerate(path['faces']):
            x,y=map(int,ids[i:i+2]);face=int(face)
            if x==y or max(x,y)<count:continue
            if face<0:raise NotImplementedError('Fractional existing-edge interval')
            if face in constraints:raise NotImplementedError('Multiple cut chords in one source face')
            s,t=scalar(i,face),scalar(i+1,face)
            if t<s:s,t,x,y=t,s,y,x
            polygons=split(faces[face],s,t,x,y)
            constraints[face]=dict(s=s,t=t,left=x,right=y,polygons=polygons)
    # Native mesh-change consumer retains original unmodified faces, then appends
    # per-face replacement polygons in ascending original source-face order.
    output=[f.copy() for i,f in enumerate(faces) if i not in constraints]
    for i in sorted(constraints):output.extend(constraints[i]['polygons'])
    output,_=triangulate(output,out);mapsA,repairs=repair(out,output,mapsA,count)
    return out,output.tolist(),mapsA,mapsB,dict(constraints=constraints,relocationRequests=requests,preparation=diagnostic,guideRepairs=repairs)
