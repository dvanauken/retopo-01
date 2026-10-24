"""Bounded ordinary extraction through final relaxation and stable compaction.

Consumes explicit conditioned source/embedded guide/field/chart inputs. No native
operation schedule, output mesh, constraint vector or later iterate is read.
"""
import struct
import numpy as np
from recovered_extraction_fixture import load
from recovered_long_cycle_cap_pre_relaxation import prepare as geometry
from recovered_guided_output_paths import prepare,collect
from recovered_mesh_topology import build
from recovered_relaxation_edge_properties import directed
from recovered_relaxation_aggregation import aggregate
from recovered_relaxation_constraints import produce
from recovered_relaxation_requests import requested
from recovered_surface_normals import triangle_normals
from recovered_zero_attachment_move import move
F=np.float32


def run(root,iterations=3):
    g=load(root);field=root/'relaxation-properties';upstream=root/'position-driver-001'
    def read(folder,name,dtype='<f4',width=None):
        a=np.fromfile(folder/name,dtype);return a.reshape(-1,width) if width else a
    basis=np.stack([read(field,'basis0.f32x3',width=3),read(field,'basis1.f32x3',width=3)],axis=1);coeff=np.stack([read(field,'axis0-coefficients.f32x2',width=2),read(field,'axis1-coefficients.f32x2',width=2)],axis=1);scales=np.column_stack([read(field,'axis0-scale.f32'),read(field,'axis1-scale.f32')]);flags=read(field,'field-face-flags.u8','u1');default=read(field,'default-scale.f32')[0];classes=read(upstream,'source-classes.u8','u1');pointer=struct.unpack('<Q',(upstream/'source-class-pointer.bin').read_bytes())[0]
    if pointer==0:
        if len(classes):raise ValueError('Null class array with retained bytes')
        classes=None
    else:raise NotImplementedError('Nonnull source class producer not qualified')
    return run_arrays(g,basis,coeff,scales,flags,default,classes,read(upstream,'field-channel68.f32'),read(upstream,'field-channel80.f32'),read(upstream,'field-flags.u8','u1'),iterations)


def run_arrays(g,basis,coeff,scales,flags,default,classes,channel68,channel80,field_flags,iterations=3):
    """Actual extraction/relaxation body with explicit arrays and no file I/O."""
    if iterations!=3:raise NotImplementedError('Only qualified ordinary three-iteration caller')
    positions,faces,metadata,quadrangulation=geometry(g);marked,weights,adjacent=prepare(positions,faces,metadata,g.tags);paths,_=collect(g,positions,metadata,marked,adjacent);topology=build(len(positions),faces);edges=topology['edges'];lookup={tuple(row):i for i,row in enumerate(edges)};guide_edges=np.zeros(len(edges),dtype=bool)
    for path in paths:
        for a,b in zip(path,path[1:]):
            if a==b:continue
            edge=lookup.get(tuple(sorted((a,b))))
            if edge is None:raise NotImplementedError('Noncoincident guide projection/cutting')
            guide_edges[edge]=True
    targets=[]
    for a,b in edges:
        for vertex,neighbor in [(int(a),int(b)),(int(b),int(a))]:
            q=directed(g,vertex,neighbor,positions,metadata['attachments'],metadata['sourceFaces'],metadata['neighbors'].T,basis,coeff,scales,flags,default,g.vertex_corners,g.cs);targets.append([q['minimum'],q['maximum'],q['gain'],*q['direction'],q['valid']])
    targets=np.asarray(targets,dtype='<f4');undirected=aggregate(positions,edges,targets,guide_edges);sourceTopology=build(len(g.xyz),g.tri)
    if classes is not None:raise NotImplementedError('Nonnull source class producer not qualified')
    mobility,blend,contrast=produce(g.xyz,g.tri,sourceTopology,metadata['attachments'],g.tags['edges'],classes,channel68,channel80,field_flags);normal=triangle_normals(g.xyz,g.tri);attachments=metadata['attachments'].copy();history=[]
    for iteration in range(iterations):
        request,branches=requested(positions,faces,undirected['minimum'],undirected['maximum'],undirected['directions'],guide_edges,mobility,blend);nextPositions=positions.copy();nextAttachments=attachments.copy();steps=0
        for vertex in range(len(positions)):
            point,at,walk=move(g.xyz,g.tri,sourceTopology,normal,g.tags['edges'],attachments[vertex],positions[vertex],F(request[vertex]-positions[vertex]));nextPositions[vertex]=point;nextAttachments[vertex]=at;steps+=len(walk)
        history.append(dict(requested=request,positions=nextPositions.copy(),attachments=nextAttachments.copy(),branches=branches,walkStates=steps));positions,attachments=nextPositions,nextAttachments
    used=np.asarray(sorted(set(v for face in faces for v in face)),dtype='<i4');remap=np.full(len(positions),-1,dtype='<i4');remap[used]=np.arange(len(used),dtype='<i4');finalFaces=[[int(remap[v]) for v in face] for face in faces]
    return dict(positions=positions[used],faces=finalFaces,history=history,fullPositions=positions,fullAttachments=attachments,used=used,sourceNormals=normal,mobility=mobility,blend=blend,directedTargets=targets,undirected=undirected,quadrangulation=quadrangulation)
