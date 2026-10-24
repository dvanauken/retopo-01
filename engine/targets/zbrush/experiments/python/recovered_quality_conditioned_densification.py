"""Ordinary closed source through default quality passes and densification.

1c2c70 preliminary mode3 bound5,1c2630 initial mode0 bound7, reviewed
XMM1 subdivision thresholds, ordinary midpoint path and final mode2.
No native geometry, quality schedule, selected edges or iterates are loaded.
"""
import numpy as np
from recovered_original_densification import threshold_from_geometry
from recovered_triangle_quality_pass import produce_pass
from recovered_coalesced_triangle_subdivision import split
F=np.float32

def densify(positions,faces,target):
    p=np.asarray(positions,dtype='<f4').copy();tri=np.asarray(faces,dtype='<i4').copy();quality=[];subdivision=[]
    def apply_quality(mode,iteration,phase):
        nonlocal tri
        before=tri.copy();result=produce_pass(p,tri,mode,iteration);tri=result['triangles'];quality.append(dict(mode=mode,iteration=iteration,phase=phase,positions=p.copy(),inputTriangles=before,result=result));return result['continueQuality']
    for i in range(5):
        if not apply_quality(3,i,'preliminary'):break
    for i in range(7):
        if not apply_quality(0,i,'initial'):break
    area,budget,scale=threshold_from_geometry(p,tri,target)
    for i in range(4):
        threshold=F(scale+scale) if i in [0,3] else scale;before_positions=p.copy();before_triangles=tri.copy();p,new_faces,diagnostic=split(p,tri,threshold);tri=np.asarray(new_faces,dtype='<i4');added=len(p)-len(before_positions);subdivision.append(dict(iteration=i,threshold=threshold,inputPositions=before_positions,inputTriangles=before_triangles,positions=p.copy(),triangles=tri.copy(),addedVertices=added,diagnostic=diagnostic))
        if i>=1 and added==0:break
        #1c2630 runs mode1 after the first split or a nonempty special-point
        #range before its fourth split. Empty/default protection only here.
        if i==0 or i<3 and diagnostic['specialPoints']>0:apply_quality(1,i,'subdivision')
    apply_quality(2,0,'final')
    return p,tri,dict(area=area,auxiliaryBudget=budget,baseScale=scale,qualityHistory=quality,subdivisionHistory=subdivision,scope='Ordinary closed source, empty initial excluded/protected masks, default quality controls, ordinary midpoint-only subdivisions. No attribute/symmetry/class/exceptional midpoint policies or general repair.')
