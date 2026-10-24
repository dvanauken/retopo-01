"""Ordinary103060 guide segmentation from own projected samples/source geometry."""
import numpy as np
from recovered_mesh_topology import build
from recovered_surface_normals import triangle_normals
from recovered_surface_attachment_classification import classify
from recovered_face_corner_direct_paths import direct
from recovered_closed_segment_reconciliation import reconcile
from recovered_initial_edge_attachment import project as initial_edge
from recovered_final_face_attachment import retain as retain_face
from recovered_original_surface_walk_parallel import walk
from recovered_alternate_vertex_path import fallback,lengths
F=np.float32


def construct(positions,faces,projected_points,projected_pairs):
    positions=F(positions);faces=np.asarray(faces,dtype='<i4');topology=build(len(positions),faces);normals=triangle_normals(positions,faces);edge_lengths=lengths(positions,topology['edges']);extent=F(positions.max(axis=0)-positions.min(axis=0));diagonal=F(np.sqrt(F(F(extent[0]*extent[0]+extent[1]*extent[1])+extent[2]*extent[2])));absolute=F(diagonal*F(1e-6));tolerance=F(absolute*absolute);points=[];pairs=[]
    for point,pair in zip(projected_points,projected_pairs):
        out,p=classify(pair,point,positions,faces,topology,True,tolerance);points.append(p);pairs.append(out)
    points=np.asarray(points,dtype='<f4');pairs=np.asarray(pairs,dtype='<i4');records=[];diagnostics=[];before=[]
    def empty():return dict(points=np.empty((0,3),dtype='<f4'),edges=np.empty(0,dtype='<i4'),parameters=np.empty(0,dtype='<f4'),faces=np.empty(0,dtype='<i4'),attributes=np.empty(0,dtype='<i4'))
    record=empty()
    def endpoint_edge(vertex):return int(topology['vertexEdges'][topology['vertexEdgeOffsets'][vertex]])
    if pairs[0,0]==1:
        vertex=int(pairs[0,1]);edge=endpoint_edge(vertex);record['points']=positions[[vertex]].copy();record['edges']=np.asarray([edge],dtype='<i4');record['parameters']=np.asarray([0 if topology['edges'][edge,0]==vertex else 1],dtype='<f4')
    elif pairs[0,0]==2:
        edge=int(pairs[0,1]);point,parameter,_=initial_edge(points[0],edge,positions,topology['edges']);record['points']=point.reshape(1,3);record['edges']=np.asarray([edge],'<i4');record['parameters']=np.asarray([parameter],'<f4')
    elif pairs[0,0]==4:record['points']=points[:1].copy();record['edges']=np.asarray([-1],dtype='<i4');record['parameters']=np.asarray([0],dtype='<f4')
    else:raise NotImplementedError('Initial projected edge-attachment parameter producer')
    for i in range(1,len(points)):
        if pairs[i-1,0]==pairs[i,0]==1 and pairs[i-1,1]==pairs[i,1]:continue
        before.append({key:value.copy() for key,value in record.items()});handled,updated,detail=direct(record,points[i-1],pairs[i-1],points[i],pairs[i],positions,faces,topology);row=dict(sourceSpan=i-1,direct=handled,directDetail=detail)
        if handled:record=updated;diagnostics.append(row);continue
        moved=walk(positions,faces,topology,normals,points[i-1],pairs[i-1],points[i],pairs[i],absolute=absolute);row['walkStatus']=moved['status']
        if moved['repair']:raise NotImplementedError('Repair-marked competing path length selection')
        if not moved['status']:
            moved=fallback(positions,faces,topology,points[i-1],pairs[i-1],points[i],pairs[i],edge_lengths);row['alternateStatus']=moved['status']
        if moved['status']:
            n=len(moved['edges'])
            if n:
                incoming=moved['faces'] if len(record['edges']) else moved['faces'][1:];record['faces']=np.r_[record['faces'],incoming].astype('<i4');record['points']=np.concatenate([record['points'],moved['points']]);record['edges']=np.r_[record['edges'],moved['edges']].astype('<i4');record['parameters']=np.r_[record['parameters'],moved['parameters']].astype('<f4')
        else:
            if len(record['edges'])>=2:records.append(record)
            record=empty();row['flush']=True
        diagnostics.append(row)
    if len(record['edges']):
        if pairs[-1,0]==4:record,final_face_detail=retain_face(record,projected_points[-1],int(pairs[-1,1]))
        closed=projected_points[0].tobytes()==projected_points[-1].tobytes() and projected_pairs[0].tobytes()==projected_pairs[-1].tobytes()
        if closed and record['edges'][0]>=0 and record['edges'][-1]>=0:
            a,b=map(int,(record['edges'][0],record['edges'][-1]));ea=topology['edgeCorners'][topology['edgeCornerOffsets'][a]:topology['edgeCornerOffsets'][a+1]]//3;eb=topology['edgeCorners'][topology['edgeCornerOffsets'][b]:topology['edgeCornerOffsets'][b+1]]//3
            record,closure=reconcile(record,topology)
        records.append(record)
    return records,dict(classifiedPoints=points,classifiedPairs=pairs,beforeDirect=before,spans=diagnostics)
