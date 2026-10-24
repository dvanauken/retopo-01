"""Ordinary projected original guides with own source boxes/normals/query/snap."""
import numpy as np
from recovered_face_box_tree import build as build_tree
from recovered_mesh_topology import build as build_topology
from recovered_surface_normals import triangle_normals
from recovered_triangle_projection import closest
F=np.float32


def project(positions,faces,points):
    positions=F(positions);faces=np.asarray(faces,dtype='<i4');points=F(points);tree,order,treeDiagnostic=build_tree(positions,faces);normals=triangle_normals(positions,faces);topology=build_topology(len(positions),faces);nodes=tree['nodes'];extent=F(positions.max(axis=0)-positions.min(axis=0));diagonal=F(np.sqrt(F(F(extent[0]*extent[0]+extent[1]*extent[1])+extent[2]*extent[2])));maximum=F(diagonal*F(.025));snapSquared=F(F(diagonal*diagonal)*np.frombuffer(bytes.fromhex('fb9bee33'),'<f4')[0]);closed=len(points)>1 and bool((points[0]==points[-1]).all());out=[];attachments=[];projectFaces=[];queryPoints=[];queryFaces=[];queryDistances=[];candidateCalls=0
    for query in points[:-1] if closed else points:
        pending=[tree['root']];distance=maximum;face=-1;point=None
        while pending:
            node=nodes[pending.pop()];bounds=F(node['bounds'])
            if not bool(((F(bounds[:3]-distance)<=query)&(query<=F(bounds[3:]+distance))).all()):continue
            if node['kind']=='branch':pending.extend(node['children']);continue
            for candidate in order[node['begin']:node['end']]:
                p,d,_=closest(query,positions[faces[candidate]],normals[candidate]);candidateCalls+=1
                if d<distance:point,face,distance=p,int(candidate),d
        queryPoints.append(point.copy() if point is not None else F([0,0,0]));queryFaces.append(face);queryDistances.append(distance)
        if face<0:continue
        pair=(4,face);best=F(np.finfo(np.float32).max)
        for vertex in faces[face]:
            delta=F(positions[vertex]-point);d=F(F(delta[0]*delta[0]+delta[1]*delta[1])+delta[2]*delta[2])
            if d<=snapSquared and d<best:pair=(1,int(vertex));best=d
        if pair[0]==1:point=positions[pair[1]].copy()
        out.append(point);attachments.append(pair);projectFaces.append(face)
    if closed and out:out.append(out[0].copy());attachments.append(attachments[0]);projectFaces.append(projectFaces[0])
    curveFaces=projectFaces.copy()
    for i,(kind,index) in enumerate(attachments):
        if kind==1:curveFaces[i]=int(topology['vertexCorners'][topology['vertexCornerOffsets'][index]])//3
    return dict(points=np.asarray(out,dtype='<f4').reshape(-1,3),attachments=np.asarray(attachments,dtype='<i4').reshape(-1,2),projectionFaces=np.asarray(projectFaces,dtype='<i4'),curveFaces=np.asarray(curveFaces,dtype='<i4'),queryPoints=np.asarray(queryPoints,dtype='<f4'),queryFaces=np.asarray(queryFaces,dtype='<i4'),queryDistances=np.asarray(queryDistances,dtype='<f4'),snapSquared=snapSquared,treeDiagnostic=treeDiagnostic,candidateCalls=candidateCalls)
