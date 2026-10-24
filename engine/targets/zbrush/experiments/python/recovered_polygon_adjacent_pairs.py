"""30db20 separated adjacent-right-pair selection with float arc discrepancy."""
import numpy as np
from recovered_polygon_arc_coordinates import coordinates
F=np.float32


def choose(points,classes):
    points=np.asarray(points,dtype='<f4');classes=np.asarray(classes,dtype='<i4');n=len(classes);first=second=None;index=0
    while index<n:
        if classes[index]==1 and classes[(index+1)%n]==1:
            if first is not None:second=index;break
            first=index;index+=1
        index+=1
    if first is None or second is None:return dict(status='none')
    gap=second-first;opposite=n-gap
    if gap<=2 or opposite<=2:return dict(status='none',pairStarts=[first,second])
    if sorted([gap,opposite])==[3,5]:
        anchor=(first+2 if gap==3 else second+2)%n;return dict(status='three-rings',pairStarts=[first,second],selection=[anchor,(anchor+3)%n,(anchor+5)%n])
    arcs=coordinates(points,np.arange(n,dtype='<i4'),(first+1)%n,second,np.empty(n,dtype='<f4'));arcs=coordinates(points,np.arange(n,dtype='<i4'),(second+1)%n,first,arcs);a=(first+2)%n;row=1;best=np.finfo(F).max;choice=None;alignedMaximum=F(0);candidates=[]
    with np.errstate(all='ignore'):
        while a!=second:
            b=(second+2)%n;remaining=opposite-2
            while b!=first:
                score=F(abs(F(F(F(1)-arcs[b])-arcs[a])));parity=n%2==0 and (a-b+n)%2==0;aligned=gap==opposite and remaining==row
                if parity:score=F(F(score*F(1.4))+F(.15))
                if aligned:
                    score=F(score*F(.85))
                    # MAXSS(score,old) returns old on unordered as well as ties.
                    if score>alignedMaximum:alignedMaximum=score
                entry=dict(begin=a,end=b,score=float(score),parityPenalty=parity,matchedPosition=aligned);candidates.append(entry)
                # COMISS(best,score)/CMOVBE rejects unordered and equal scores.
                if score<best:best=score;choice=entry.copy()
                b=(b+1)%n;remaining-=1
            a=(a+1)%n;row+=1
    threshold=F(F(.5)/F(gap-1));accepted=choice is not None and (gap!=opposite or alignedMaximum>=threshold)
    return dict(status='selected' if accepted else 'defer-grid',pairStarts=[first,second],choice=choice,candidates=candidates,arcBits=arcs.view('<u4').tolist(),matchedMaximum=float(alignedMaximum),acceptanceThreshold=float(threshold),equalSpans=gap==opposite)
