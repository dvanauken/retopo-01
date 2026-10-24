"""30db20 supported non-reflex patterns and +3 quality-diagonal fallback."""
import numpy as np
from recovered_polygon_corner_classes import classify
from recovered_polygon_corner_refinement import counters,refine
from recovered_polygon_diagonal_score import adjust
from recovered_diagonal_guard import guard
from recovered_polygon_adjacent_pairs import choose as adjacent_pairs
F=np.float32


def choose(points,mode=1,allow_new=False):
    angles,classes,branches=classify(points);n=len(points);stats=counters(classes)
    if np.any(classes==3):classes,stats,_,events=refine(angles,classes,stats,0,n)
    if stats[2]:raise ValueError('Reflex dispatch required')
    def answer(status,branch,begin=None,end=None,candidates=None):return dict(status=status,branch=branch,angles=angles,classes=classes,stats=stats,begin=begin,end=end,candidates=candidates or [])
    if n==5 and mode==2:return answer('filtered','five-gon-mode-two')
    if n==5 and stats[0]==4 and stats[1]==1:
        begin=int(stats[5]);return answer('selected','pentagon-flat-corner',begin,(begin+3)%n)
    if stats[0]==4 and n==4+stats[1]:
        pairs=adjacent_pairs(points,classes)
        if pairs['status']=='three-rings':return dict(answer('three-rings','four-corner-three-five-spans'),selection=pairs['selection'],pairDetails=pairs)
        if pairs['status']=='selected':return dict(answer('selected','four-corner-arc-metric',pairs['choice']['begin'],pairs['choice']['end'],pairs['candidates']),pairDetails=pairs)
        corners=np.flatnonzero(classes==1);spans=np.diff(np.r_[corners,corners[0]+n])
        if spans[0]==spans[2] and spans[1]==spans[3]:return answer('grid','four-corner-opposite-span-grid')

    if n>=6:
        if mode!=2:
            for begin in range(n):
                end=(begin+3)%n
                if classes[begin] not in [1,2] and classes[end] not in [1,2] and classes[(begin+1)%n]==1 and classes[(begin+2)%n]==1 and (classes[begin]!=0 or classes[end]!=0):return answer('selected','nonright-two-right-nonright',begin,end)
        for begin in range(n):
            if [int(classes[(begin+i)%n]) for i in range(5)]==[0,1,1,1,0]:
                if allow_new:return answer('new-five','zero-three-right-zero',begin,(begin+4)%n)
                raise NotImplementedError('Five-corner point construction not integrated')
        for begin in range(n):
            if classes[begin]!=1:continue
            zeros=0
            for step in range(1,n-2):
                kind=classes[(begin+step)%n]
                if kind==1:
                    if (zeros==2 if mode==2 else zeros>1):
                        if allow_new:return answer('new-two','right-flat-run-right',begin,(begin+step)%n)
                        raise NotImplementedError('Two-corner point rewrite not integrated')
                    break
                if kind!=0:break
                zeros+=1
        if n==6 if mode==2 else n>5:
            for middle in range(n):
                if classes[middle]==1 and classes[(middle-1)%n]==0 and classes[(middle+1)%n]==0:
                    if allow_new:return answer('new-three','zero-right-zero',(middle-1)%n,(middle+1)%n)
                    raise NotImplementedError('Three-corner point rewrite not integrated')
    if mode==2:return answer('filtered','mode-two-no-pattern')
    best=np.finfo(F).max;choice=None;candidates=[]
    for begin in range(n):
        end=(begin+3)%n;rejected,length,_=guard(points,begin,end);score=F(length);factors=[]
        if not rejected:
            if classes[begin]==1:score=F(score*F(1.5))
            if classes[end]==1:score=F(score*F(1.5))
            score,factors=adjust(points,begin,end,length,score)
        row=dict(begin=begin,end=end,rejected=bool(rejected),length=float(length),score=float(score),factors=np.asarray(factors).tolist());candidates.append(row)
        if not rejected and score<best:best=score;choice=row
    if choice:return answer('selected','quality-diagonal',choice['begin'],choice['end'],candidates)
    return answer('no-eligible','quality-to-tessellator',candidates=candidates)
