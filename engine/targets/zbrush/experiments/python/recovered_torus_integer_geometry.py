"""Multiple-mode2 source composition fork; native qualification is separate.
Original default continuous parameter solve through geometric integer rows."""
import numpy as np
from recovered_torus_default_continuous_parameter import prepare as continuous
from recovered_integer_geometric_front import initialize,propagate,candidates
from recovered_torus_integer_geometric_rows import construct_arrays,optional_seam_constraints
from verify_coordinate_reconstruction import reconstruct


def prepare(source,faces,target,drawn,cut,seeds,guide_mode):
    if type(guide_mode) is not int or guide_mode not in (1,2):raise NotImplementedError('Only explicit homogeneous active guide modes1/2')
    own=continuous(source,faces,target,drawn,cut,seeds,guide_mode);g=own['geometry'];frames=own['frames'];chart=own['chart'];top=own['parameterTopology'];edges=top['edges'];initial=own['initialParameter'];uv=reconstruct(own['continuousParameter']['solution'],initial['inverse'],own['parameterConstraints']['dependencies'],len(own['parameterConstraints']['mapping']))[:2*len(own['parameterFans']['sourceIds'])].reshape(-1,2)
    data=dict(positions=g['positions'],tri=g['faces'],uv=own['parameterFans']['triangles'],kwargs=own['parameterKwargs'],groups=own['parameterGroups'],constraints=own['parameterConstraints'],basisA=frames['basisA'],basisB=frames['basisB'],directionA=chart['directionA'],directionB=chart['directionB']);axes=[]
    for axis in range(2):
        init=initialize(data['tri'],data['uv'],edges,data['groups']['groups'],data['groups']['axes'],seeds,axis);front=propagate(uv,edges,top['vertexEdgeOffsets'],top['vertexEdges'],init['distance'],init['owner'],init['root'],init['parent'],init['queue']);records=candidates(uv,edges,front['distance'],front['owner'],init['marked']);pairs=[];gaps=[]
        for row in records:
            if row['edge']<0:raise NotImplementedError('Sentinel candidate branch')
            a,b=map(int,edges[row['edge']]);a,b=int(front['root'][a]),int(front['root'][b]);pairs.append([2*a+axis,2*b+axis]);gaps.append(float(abs(np.float32(uv[b,axis]-uv[a,axis]))))
        axes.append(dict(axis=axis,records=records,pairs=pairs,gaps=gaps,front=front))
    generated=construct_arrays(data,uv,edges,axes,own['parameterFans']['sourceIds'],top['vertexEdgeOffsets'],top['vertexEdges'],top['edgeCornerOffsets'],top['edgeCorners'],frames['scaleA']);extra,selected=optional_seam_constraints(data,uv)
    own['integerGeometry']=dict(data=data,uv=uv,edges=edges,axes=axes,generated=generated,extra=extra,selectedSeams=selected)
    return own
