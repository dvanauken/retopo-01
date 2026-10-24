"""Ordinary mode1/2 multi-curve batch source candidate; native qualification separate.

1c97b0 gathers each curve's segmentation records in curve/record order before
255b10/2567b0 process the combined pool. The inherited one-chord-per-face guard
is retained: crossing/competing cut policies are not invented here.
"""
import numpy as np
from recovered_torus_preparation import prepare as source_prepare
from recovered_original_guide_projection import project
from recovered_torus_guide_segments import construct as segment
from recovered_closed_vertex_source_cut import cut

def prepare(source,faces,target,drawn_curves):
    if not drawn_curves:raise ValueError('At least one declared active mode2 curve required')
    positions,triangles,conditioning=source_prepare(source,faces,target);curves=[];records=[];offsets=[0]
    for points in drawn_curves:
        projection=project(positions,triangles,points);local,detail=segment(positions,triangles,projection['points'],projection['attachments']);curves.append(dict(projection=projection,segmentation=detail));records.extend(local);offsets.append(len(records))
    out,triangles,mapsA,mapsB,detail=cut(positions,triangles,records)
    for i,curve in enumerate(curves):
        first,last=offsets[i:i+2];ids=np.concatenate(mapsA[first:last]) if last>first else np.empty(0,dtype='<i4');curve.update(embeddedPairs=np.c_[np.ones(len(ids),dtype='<i4'),ids].astype('<i4'),embeddedPoints=out[ids],mapsA=mapsA[first:last],mapsB=mapsB[first:last])
    return dict(positions=out,faces=np.asarray(triangles,dtype='<i4'),curves=curves,recordOffsets=np.asarray(offsets,dtype='<i4'),conditioning=conditioning,cutDetail=detail)
