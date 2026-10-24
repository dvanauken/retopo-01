"""Default torus size composition from source-produced geometry and field.

No native sizes, normal systems or helper arrays are inputs. This composes the
qualified ordinary cap/diffusion/objective subset. The additional low-confidence
and zero-curvature cap leaves have controlled native qualification; naturally
produced full-source cases exercising those branches remain separate.
"""
import numpy as np
from recovered_cut_gauge_directions import prepare as gauge
from recovered_ordinary_curvature_size_caps import prepare as caps
from recovered_directional_size_diffusion import pass_once,ratio_clamp
from recovered_coupled_face_size_system import prepare as objective
F=np.float32

def prepare(field,reference_frames,cut=None):
    g=field['geometry'];ef=field['edgeField'];top=ef['topology'];edges=top['edges'];n=len(g['faces']);cut=np.zeros(len(edges),bool) if cut is None else np.asarray(cut,bool);chart=gauge(dict(g,normals=ef['normals']),top,reference_frames,field['angular']['angles'],field['angular']['quarterTransitions'],cut);selected=field['selection'];base=field['settings']['componentScale'];initial=caps(selected['middle'],selected['largest'],selected['weights'],chart['gauge'],float(base));guide=np.zeros(len(edges),bool);guide[field['constraints']['selectedEdges']]=True;axes=np.zeros((n,3),bool);fe=top['faceEdges'].reshape(-1,3);co=top['edgeCornerOffsets'];corn=top['edgeCorners'];fa=reference_frames['basisA'];fb=reference_frames['basisB']
    def dot(a,b):return F(F(a[1]*b[1]+a[0]*b[0])+a[2]*b[2])
    for edge in np.flatnonzero(guide):
        for corner in corn[co[edge]:co[edge+1]]:
            face,k=divmod(int(corner),3);direction_a=F(chart['directionA'][face,0]*fa[face]+chart['directionA'][face,1]*fb[face]);direction_b=F(chart['directionB'][face,0]*fa[face]+chart['directionB'][face,1]*fb[face]);delta=F(g['positions'][g['faces'][face,(k+1)%3]]-g['positions'][g['faces'][face,k]]);axes[face,k]=abs(dot(direction_b,delta))<abs(dot(direction_a,delta))
    x=initial['scaleA'];y=initial['scaleB'];history=[]
    for op,count in [('mean',1),('minimum',2),('mean',1),('minimum',3),('mean',1),('minimum',2),('mean',1)]:
        for _ in range(count):x,y=pass_once(x,y,top,guide,axes,chart['transitions'],op)
        history.append(dict(operation=op,iterations=count,scaleA=x.copy(),scaleB=y.copy()))
    x,y=ratio_clamp(x,y,float(initial['lowerScale']),4.);result=objective(g['positions'],g['faces'],top,selected['flags'],x,y,guide,axes,chart['transitions'],base,field['settings']['area']);result.update(initialCaps=initial,diffusionHistory=history,preSolveA=x,preSolveB=y,guideEdges=guide,cornerAxes=axes,gauge=chart['gauge'],transitions=chart['transitions'])
    return result
