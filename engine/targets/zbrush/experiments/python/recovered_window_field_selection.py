"""271a90 ordinary valid windows/protected blends/fallback and2740d0 smoothing.

Explicit defaults: radius window1 each side, three index passes, no excluded
faces, known mode0 field selection. General exclusions/no-choice remain guarded.
Native guide mode is a separate setting; no native arrays are read here.
"""
import numpy as np
from recovered_fallback_candidate_kernel import prepare as fallback
from verify_scale_selection import angle,dot
F=np.float32
def prepare(field,unordered_selection=True,native_arithmetic=True):
    out=fallback(field,unordered_selection,native_arithmetic);valid=field['candidateGate']['valid'];num,n=valid.shape;directions=field['directions'];middle=field['middle'];largest=field['largest'];protected=(field['constraints']['flags']&12)!=0;rawWindows=np.asarray([valid[max(0,s-1):min(num-1,s+1)+1].all(axis=0) for s in range(num)]);windows=rawWindows&~protected;selected=np.full(n,-1,dtype='<i4');scores=np.zeros((num,n),dtype='<f4');best=np.full(n,np.finfo('f4').max,dtype='<f4')
    for s in range(num):
        lo=max(0,s-1);hi=min(num-1,s+1)
        for j in range(lo,hi+1):
            if j!=s:scores[s]=F(scores[s]+angle(directions[s],directions[j]))
        scores[s]=F(scores[s]/F(hi-lo+1));accept=windows[s]&(scores[s]<best);selected[accept]=s;best[accept]=scores[s,accept]
    ids=np.flatnonzero(selected>=0);chosen=selected[ids];out['directions'][ids]=directions[chosen,ids];out['middle'][ids]=middle[chosen,ids];out['largest'][ids]=largest[chosen,ids];out['flags'][ids]=field['constraints']['flags'][ids]|np.uint8(3);aniso=np.zeros(len(ids),dtype='<f4');np.divide(F(abs(out['largest'][ids])-abs(out['middle'][ids])),abs(out['largest'][ids]),out=aniso,where=out['largest'][ids]!=0);score=best[ids];base=F(field['controls']['anisotropy']);angular=np.where(score<0,F(250),np.where(score<=F(.06981316953897476),F(F(250)-F(score*F(1790.4931640625))),F(125)));confidence=np.where(aniso<base,F(375),np.where(aniso<=1,F(F(F(F(375)/F(F(1)-base))*F(aniso-base))+F(375)),F(750)));out['weights'][ids]=F(angular+confidence);out['selected'][ids]=chosen
    protectedIds=np.flatnonzero(protected&rawWindows.any(axis=0));target=field['constraints']['directions'][protectedIds];mid=middle[:,protectedIds];large=largest[:,protectedIds];aniso=np.zeros_like(mid);np.divide(F(abs(large)-abs(mid)),abs(large),out=aniso,where=large!=0);aniso=F(aniso+aniso);choice=np.full(len(protectedIds),-1,dtype='<i4');costBest=np.full(len(protectedIds),np.finfo('f4').max,dtype='<f4')
    for s in range(num):
        av=angle(target,directions[s,protectedIds]);cost=np.where(av.astype(float)>.08726646259971647,F(av*F(.6366197466850281)),F(0));cost=np.where(av.astype(float)>.3490658503988659,((av.astype(float)-.3490658503988659)*1.909859263956068+cost.astype(float)).astype('<f4'),cost);cost=F(cost+aniso[s])
        if s==0:cost=F(cost*F(.5))
        elif s>num//2:cost=F(cost*F(.6666666865348816 if s==num-1 else 1.5))
        accept=rawWindows[s,protectedIds]&(cost<costBest);choice[accept]=s;costBest[accept]=cost[accept]
    if np.any(choice<0):raise NotImplementedError('Protected valid-window no-choice branch')
    j=np.arange(len(protectedIds));lm=mid[choice,j];lx=large[choice,j];dp=abs(dot(directions[choice,protectedIds],target));average=F(F(lm+lx)*F(.5));swap=dp<F(.5);a=np.where(swap,lx,lm);b=np.where(swap,lm,lx);v=F(np.where(swap,F(F(1)-dp),dp)-F(1));temp=F(F(average-a)*v);out['middle'][protectedIds]=F(a-F(temp+temp));temp=F(F(average-b)*v);out['largest'][protectedIds]=F(b-F(temp+temp));out['directions'][protectedIds]=target;out['weights'][protectedIds]=F(50000);out['selected'][protectedIds]=-1;out['flags'][protectedIds]=field['constraints']['flags'][protectedIds]|np.uint8(2)
    before=out['selected'].copy();top=field['edgeField']['topology'];faceEdges=top['faceEdges'].reshape(-1,3);offset=top['edgeCornerOffsets'];corners=top['edgeCorners']
    for _ in range(3):
        values=out['selected'];updated=values.copy()
        for face in np.flatnonzero(values>=0):
            edge=int(faceEdges[face,0]);a,b=map(int,offset[edge:edge+2])
            if b-a!=2:continue
            pair=corners[a:b]//3;neighbor=int(pair[1] if pair[0]==face else pair[0] if pair[1]==face else -1)
            if neighbor<0 or values[neighbor]<0:continue
            total=F(values[face])
            for _ in range(3):total=F(total+F(values[neighbor]))
            target=int(F(F(total/F(4))+F(.5)));step=1 if target<values[face] else -1
            while target!=values[face]:
                if windows[target,face]:updated[face]=target;break
                target+=step
        out['selected']=updated
    out.update(preSmoothSelected=before,mainSelected=selected,mainScores=scores,windows=windows,rawWindows=rawWindows,validScaleCounts=(valid&~protected).sum(axis=0).astype('<i4'),windowScaleCounts=windows.sum(axis=0).astype('<i4'),protectedChoice=choice,mainFaces=ids,protectedWindowFaces=protectedIds,scope='Composed bounded valid-window/protected/fallback/index selection. Kernel fallback predictions for nonfallback faces are overwritten; no all-invalid native-gate claim follows.')
    return out
