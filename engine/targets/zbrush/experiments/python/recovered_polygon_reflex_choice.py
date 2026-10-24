"""30db20 initial reflex candidate branch from explicit polygon geometry."""
import numpy as np
from recovered_polygon_corner_classes import classify
from recovered_diagonal_guard import guard
F=np.float32


def choose(points,mode=1):
    angles,classes,branches=classify(points);n=len(points);reflex=np.flatnonzero(classes==-1)
    #3092b0 only modifies ambiguous classes when the reflex count is zero.
    if not len(reflex):return dict(status='not-reflex',classes=classes,angles=angles,candidates=[],choice=None)
    if mode==2 and (n!=6 or len(reflex)!=1 or np.count_nonzero(classes==1)!=5):return dict(status='mode-filtered',classes=classes,angles=angles,candidates=[],choice=None)
    best=np.finfo(F).max;choice=None;candidates=[]
    for begin in reflex:
        for step in range(3,n-2):
            end=(int(begin)+step)%n;rejected,length,_=guard(points,int(begin),end);score=F(length if classes[end]==-1 else F(F(length)*F(.5)));record=dict(begin=int(begin),end=end,rejected=bool(rejected),length=float(length),score=float(score));candidates.append(record)
            if not rejected and score<best:best=score;choice=record.copy()
    return dict(status='selected' if choice else 'no-eligible-diagonal',classes=classes,angles=angles,candidates=candidates,choice=choice)
