"""Original mesh/drawn guide plus explicit cut mask to parameter chart channels."""
from recovered_torus_guide_field import prepare as field
from recovered_parameter_frames import prepare as frames
from recovered_cut_gauge_directions import prepare as gauge
from recovered_parameter_fan_numbering import prepare as fans
from recovered_mesh_topology import build
from recovered_torus_size_field import prepare as size_field


def prepare(source,triangles,target,drawn,cut,guide_mode=2):
    result=field(source,triangles,target,drawn,guide_mode);geometry=result['geometry'];topology=result['edgeField']['topology'];normal=result['edgeField']['normals']
    result['frames']=frames(geometry['positions'],geometry['faces'],normal,result['settings']['componentScale'])
    result['sizing']=size_field(result,result['frames'],cut);result['frames']['scaleA']=result['sizing']['scaleA'];result['frames']['scaleB']=result['sizing']['scaleB']
    result['chart']=gauge(dict(geometry,normals=normal),topology,result['frames'],result['angular']['angles'],result['angular']['quarterTransitions'],cut)
    result['parameterFans']=fans(len(geometry['positions']),geometry['faces'],topology,cut)
    result['parameterTopology']=build(len(result['parameterFans']['sourceIds']),result['parameterFans']['triangles'])
    return result
