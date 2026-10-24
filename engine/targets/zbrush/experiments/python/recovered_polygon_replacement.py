"""Independent supported30db20 polygon dispatcher including new-point operators.

Structured grids and adjacent-pair metrics are composed; fallback uses pinned independent public GLU. Embedded sweep/render internals remain separate.
"""
import numpy as np
from recovered_polygon_reflex_choice import choose as reflex
from recovered_polygon_nonreflex_choice import choose as nonreflex
from recovered_polygon_new_vertices import two_corners,three_corners,five_corners
from recovered_polygon_provenance import Provenance
from recovered_polygon_three_rings import replace as three_rings
from recovered_polygon_structured_grid import replace as structured_grid
from recovered_polygon_tessellation import replace as tessellation_fallback


def rewrite(points,faces,mode=1):
    points=np.asarray(points,dtype='<f4').copy();result=[list(map(int,x)) for x in faces];provenance=Provenance(len(points));events=[];index=0
    while index<len(result):
        if len(events)>10000:raise RuntimeError('Owned verification operation budget exceeded')
        row=result[index];n=len(row)
        if n<=4:index+=1;continue
        prediction=reflex(points[row],mode);status=prediction['status']
        if status=='mode-filtered':events.append(dict(sourceFace=index,action='filtered-reflex',inputRow=row,classes=prediction['classes'].tolist()));index+=1;continue
        if status=='no-eligible-diagonal':
            points,result,details=tessellation_fallback(points,result,index);details['projectedBits']=details.pop('projected').view('<u4').tolist();events.append(dict(sourceFace=index,action='tessellator-fallback',branch='reflex-no-diagonal',inputRow=row.copy(),classes=prediction['classes'].tolist(),details=details));continue
        if status=='selected':begin=prediction['choice']['begin'];end=prediction['choice']['end'];action='split-reflex';branch='weighted-reflex'
        else:
            prediction=nonreflex(points[row],mode,allow_new=True);status=prediction['status'];begin=prediction['begin'];end=prediction['end'];branch=prediction['branch']
            if status=='filtered':events.append(dict(sourceFace=index,action='filtered-nonreflex',inputRow=row,classes=prediction['classes'].tolist(),branch=branch));index+=1;continue
            if status=='no-eligible':
                points,result,details=tessellation_fallback(points,result,index);details['projectedBits']=details.pop('projected').view('<u4').tolist();events.append(dict(sourceFace=index,action='tessellator-fallback',branch='nonreflex-no-diagonal',inputRow=row.copy(),classes=prediction['classes'].tolist(),details=details));continue
            if status=='grid':
                points,result,details=structured_grid(points,result,index,prediction['classes'],provenance);events.append(dict(sourceFace=index,action='structured-grid',inputRow=row.copy(),classes=prediction['classes'].tolist(),branch=branch,**details));continue
            if status=='three-rings':
                points,result=three_rings(points,result,index,prediction['selection']);events.append(dict(sourceFace=index,action='three-rings',inputRow=row.copy(),selection=prediction['selection'],classes=prediction['classes'].tolist(),branch=branch));continue
            if status in ['new-two','new-three','new-five']:
                before=len(points);event=dict(sourceFace=index,action=status,inputRow=row.copy(),begin=begin,end=end,classes=prediction['classes'].tolist(),branch=branch)
                if status=='new-two':points,result=two_corners(points,result,index,begin,end,provenance)
                elif status=='new-three':points,result=three_corners(points,result,index,begin,(begin+1)%n,end,provenance)
                else:points,result=five_corners(points,result,index,[(begin+i)%n for i in range(5)],provenance)
                event.update(newVertexStart=before,newVertexCount=len(points)-before);events.append(event);continue
            action='split-nonreflex'
        a,b=sorted([begin,end]);replacement=[row[:a+1]+row[b:],row[a:b+1]];events.append(dict(sourceFace=index,action=action,inputRow=row.copy(),begin=begin,end=end,classes=prediction['classes'].tolist(),branch=branch,replacement=replacement));result=result[:index]+result[index+1:]+replacement
    return points,result,provenance.arrays(),events
