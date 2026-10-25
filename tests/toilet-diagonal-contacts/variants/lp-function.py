def adjacent_interiors(vertices,faces):
    incidence=defaultdict(list)
    for i,face in enumerate(faces):
        for vertex in face: incidence[vertex].append(i)
    pairs=sorted({(a,b) for connected in incidence.values() for a in connected for b in connected if a<b})
    triangles=[[vertices[[f[0],f[i],f[i+1]]] for i in range(1,len(f)-1)] for f in faces]
    inequality=np.r_[np.c_[-np.eye(4),np.ones(4)],[[1,1,0,0,1],[0,0,1,1,1]]]
    overlaps,unresolved,tested=[],[],0
    for index,(a,b) in enumerate(pairs):
        found=False
        for ta in triangles[a]:
            for tb in triangles[b]:
                if np.any(ta.max(axis=0)<tb.min(axis=0)) or np.any(tb.max(axis=0)<ta.min(axis=0)): continue
                equality=np.c_[ta[1]-ta[0],ta[2]-ta[0],-(tb[1]-tb[0]),-(tb[2]-tb[0]),np.zeros(3)]
                result=linprog([0,0,0,0,-1],A_eq=equality,b_eq=tb[0]-ta[0],A_ub=inequality,b_ub=[0,0,0,0,1,1],bounds=[(0,None)]*4+[(0,1/3)],method='highs')
                tested+=1
                if result.status not in (0,2): unresolved.append(dict(faces=[a,b],status=result.status))
                if result.success and result.x[-1]>1e-7:
                    error=float(np.linalg.norm(equality@result.x-(tb[0]-ta[0])))
                    if error<=1e-9:
                        overlaps.append(dict(faces=[a,b],minimumBarycentric=float(result.x[-1]),equalityError=error)); found=True; break
                    unresolved.append(dict(faces=[a,b],equalityError=error))
            if found: break
        if (index+1)%2500==0: print('  independent adjacent-face LPs:',index+1,'of',len(pairs),flush=True)
    return dict(passed=not overlaps and not unresolved,adjacentFacePairs=len(pairs),trianglePrograms=tested,overlaps=overlaps,unresolved=unresolved,
                scope='Independent HiGHS feasibility/maximum-interior-margin problems for every shared-vertex face pair after triangle AABB pruning. Reports strict interior contacts above 1e-7 barycentric margin; boundary-only contacts and smaller margins are outside this supplemental test.')
