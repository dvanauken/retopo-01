"""Reviewed29d240 mobility and274870 incident-face contrast blend."""
import numpy as np
from recovered_reflex_hexagon import norm
F=np.float32


def produce(source_positions,source_triangles,source_topology,attachments,source_guides,source_classes,channel68,channel80,face_flags):
    result=np.ones(len(attachments),dtype='<f4');blend=np.zeros(len(attachments),dtype='<f4');magnitude68=np.abs(channel68);magnitude80=np.abs(channel80);contrast=np.zeros(len(channel80),dtype='<f4');nonzero=magnitude80!=0;contrast[nonzero]=F(F(magnitude80[nonzero]-magnitude68[nonzero])/magnitude80[nonzero]);edges=source_topology['edges']
    for vertex,(kind,index) in enumerate(attachments):
        kind,index=int(kind),int(index)
        if kind==1:
            if source_classes is not None and source_classes[index]==1:result[vertex]=F(0)
            es=source_topology['vertexEdges'][source_topology['vertexEdgeOffsets'][index]:source_topology['vertexEdgeOffsets'][index+1]];marked=[int(e) for e in es if source_guides[e]]
            if len(marked)>2:result[vertex]=F(0)
            elif len(marked)==2:
                neighbors=[int(edges[e,1] if edges[e,0]==index else edges[e,0]) for e in marked];a=norm(F(source_positions[neighbors[0]]-source_positions[index]));b=norm(F(source_positions[index]-source_positions[neighbors[1]]));dot=F(F(F(a[0]*b[0])+F(a[1]*b[1]))+F(a[2]*b[2]))
                if float(dot)<.7:result[vertex]=F(0)
        if kind==4:incident=[index]
        elif kind==1:incident=(source_topology['vertexCorners'][source_topology['vertexCornerOffsets'][index]:source_topology['vertexCornerOffsets'][index+1]]//3).tolist()
        elif kind==2:incident=(source_topology['edgeCorners'][source_topology['edgeCornerOffsets'][index]:source_topology['edgeCornerOffsets'][index+1]]//3).tolist()
        else:continue
        value=F(0)
        for face in incident:
            if face_flags[face]&1:value=F(value+contrast[face])
        if kind!=4 and incident:value=F(value/F(len(incident)))
        if float(value)<.2:value=F(0)
        elif float(value)>.85:value=F(1)
        blend[vertex]=value
    return result,blend,contrast
