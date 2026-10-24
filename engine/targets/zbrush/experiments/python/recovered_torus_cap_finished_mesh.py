"""Multiple-mode2 source composition fork; native qualification is separate.
Original incoming guided fixture with explicit cuts/seeds through output mesh."""
import numpy as np
from recovered_torus_parameter_solution import prepare as parameter
from recovered_torus_extraction_graph import Graph
from recovered_closed_guide_tags import build as tags
from recovered_long_cycle_cap_finished_mesh import run_arrays
F=np.float32


def prepare(source,faces,target,drawn,cut,seeds,guide_mode):
    if type(guide_mode) is not int or guide_mode not in (1,2):raise NotImplementedError('Only explicit homogeneous active guide modes1/2')
    own=parameter(source,faces,target,drawn,cut,seeds,guide_mode);g=own['geometry'];top=own['edgeField']['topology'];xyz=g['positions'];tri=g['faces'];pt=own['parameterFans']['triangles'];uv=own['parameterSolution']['uv'];curves=[dict(mode=guide_mode,active=True,primaryPairs=curve['embeddedPairs']) for curve in g['curves']];guide=tags(curves,top['edges'],top['vertexEdgeOffsets'],top['vertexEdges'],len(xyz));delta=F(xyz.max(axis=0)-xyz.min(axis=0));length=F(np.sqrt(F(F(delta[1]*delta[1]+delta[0]*delta[0])+delta[2]*delta[2])));threshold=F(length*F(1e-7));distance=F(length*F(1e-6));cut_threshold=F(distance*distance)
    graph=Graph(xyz,tri,pt,uv,top['faceEdges'].reshape(-1,3),top['edgeCornerOffsets'],top['edgeCorners'],own['chart']['transitions'],seeds,threshold,cut_threshold,guide);graph.source_edges=top['edges'];o=top['vertexEdgeOffsets'];flat=top['vertexEdges'];graph.vertex_edges=[list(map(int,flat[a:b])) for a,b in zip(o[:-1],o[1:])];f=own['frames'];chart=own['chart'];selected=own['selection'];basis=np.stack([f['basisA'],f['basisB']],axis=1);coeff=np.stack([chart['directionA'],chart['directionB']],axis=1);scales=np.column_stack([f['scaleA'],f['scaleB']])
    own['finishedMesh']=run_arrays(graph,basis,coeff,scales,selected['flags'],F(own['settings']['componentScale']),None,selected['middle'],selected['largest'],selected['flags'])
    return own
