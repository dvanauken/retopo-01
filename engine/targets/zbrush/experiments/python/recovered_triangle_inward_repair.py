"""253d80 ordered double2 half-plane repair, .001 opposite-vertex nudge.

Up to three passes. Caller triangle is ordinarily counterclockwise; reversed
and degenerate controls have qualified numeric behavior, no inside guarantee.
Nonfinite inputs remain unsupported rather than silently approximated.
"""
import numpy as np
NUDGE=.001

def repair(point,triangle):
    point=np.asarray(point,'<f8');triangle=np.asarray(triangle,'<f8')
    if point.shape!=(2,) or triangle.shape!=(3,2):raise ValueError('Double2 point and three triangle corners required')
    if not np.all(np.isfinite(point)) or not np.all(np.isfinite(triangle)):raise NotImplementedError('253d80 nonfinite behavior remains unqualified')
    q=list(map(float,point));tri=[list(map(float,p)) for p in triangle];actions=[]
    for iteration in range(3):
        changed=False
        for edge in range(3):
            a,b,c=[tri[(edge+i)%3] for i in range(3)];dx=b[0]-a[0];dy=b[1]-a[1];px=q[0]-a[0];py=q[1]-a[1]
            if 0<=dx*py-dy*px:continue
            changed=True;den=dy*dy+dx*dx
            if den==0:continue
            t=(dy*py+dx*px)/den
            if t<=0:t=0.
            if 1<=t:t=1.
            w=1-t;x=w*a[0]+b[0]*t;y=w*a[1]+b[1]*t
            q=[(c[0]-x)*NUDGE+x,(c[1]-y)*NUDGE+y];actions.append(dict(iteration=iteration,edge=edge,t=t))
        if not changed:return np.asarray(q,'<f8'),actions,iteration+1
    return np.asarray(q,'<f8'),actions,3
