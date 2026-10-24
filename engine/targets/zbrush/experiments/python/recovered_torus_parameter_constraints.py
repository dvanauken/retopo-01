"""Multiple-mode2 source composition fork; native qualification is separate.
Original input chart plus explicit cuts/forced source seeds to constraints."""
import numpy as np
from recovered_torus_parameter_chart import prepare as chart
from recovered_embedded_guide_edges import collect
from recovered_guide_groups import construct_groups
from recovered_torus_scalar_constraints import constraints
from recovered_source_singular_seeds import prepare as singular_seeds


def prepare(source,triangles,target,drawn,cut,seeds,guide_mode):
    if type(guide_mode) is not int or guide_mode not in (1,2):raise NotImplementedError('Only explicit homogeneous active guide modes1/2')
    own=chart(source,triangles,target,drawn,cut,guide_mode);g=own['geometry'];topology=own['edgeField']['topology'];uv=own['parameterFans']['triangles'];edges=topology['edges'];pe=own['parameterTopology']['edges'];frames=own['frames'];direction=own['chart'];curves=[dict(mode=guide_mode,active=True,primaryPairs=curve['embeddedPairs'],alternatePoints=[],alternatePairs=[]) for curve in g['curves']]
    selected,modes=collect(curves,edges,topology['vertexEdgeOffsets'],topology['vertexEdges']);sourceModes=np.zeros(len(edges),dtype=np.uint8)
    for e,m in modes.items():sourceModes[e]=m
    skip=np.zeros(len(edges),dtype=bool);groups=construct_groups(g['positions'],g['faces'],uv,topology['faceEdges'].reshape(-1,3),selected,sourceModes,frames['basisA'],frames['basisB'],direction['directionA'],direction['directionB'],pe,skip);modeArray=np.zeros(len(pe),dtype=np.uint8)
    for e,m in groups['edgeModes'].items():modeArray[e]=m
    sourceMap={}
    for corner,edge in enumerate(own['parameterTopology']['faceEdges']):sourceMap[int(edge)]=int(topology['faceEdges'][corner])
    kwargs=dict(tri=g['faces'],uv=uv,edges=edges,faceEdges=topology['faceEdges'].reshape(-1,3),edgeOffsets=topology['edgeCornerOffsets'],edgeCorners=topology['edgeCorners'],vertexOffsets=topology['vertexEdgeOffsets'],vertexEdges=topology['vertexEdges'],selected=np.flatnonzero(cut),seeds=seeds,transitions=direction['transitions'],parameterEdges=pe,groups=groups['groups'],axes=groups['axes'],modes=modeArray,sourceEdgeMap=[sourceMap[e] for e in range(len(pe))],skip=skip)
    singular=singular_seeds(g['positions'],g['faces'],own['edgeField']['normals'],topology,own['angular']['angles'],own['angular']['connections'],own['angular']['quarterTransitions']);augmented=np.flatnonzero(cut) if len(singular['seeds'])==0 else None
    own['parameterConstraints']=constraints(**kwargs,augmented=augmented);own['parameterGroups']=groups;own['parameterKwargs']=kwargs
    return own
