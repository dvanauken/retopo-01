"""Differentiable fitting of source features, guides and rejected contacts.

Only fitting lives here. Acceptance uses independent geometry measurements.
Tensor/list conversion avoids reliance on the optional Torch/NumPy ABI bridge.
"""
import time
import numpy as np
import trimesh
from scipy.optimize import minimize, linear_sum_assignment
from scipy.spatial import cKDTree
from contact_constraints import planes
from source_features import detect, band_widths
from quad_connectivity import vertex_stars

BALANCE_WEIGHT=10.  # Laplacian pull toward the star midpoint: engineering policy (native has no fit objective); without it the fit degrades quads after relaxation
from measure_geometry import window_chords
import curved_quad as cq


def nearest_segments(points, a, b, tangents=None, spacing=1., point_normals=None, edge_normals=None, forbidden_edges=None, separate_points=None):
    count=min(24,len(a));_,ids=cKDTree((a+b)*.5).query(points,k=count)
    ids=np.asarray(ids).reshape(len(points),count);start=a[ids];d=b[ids]-start
    t=np.clip(((points[:,None]-start)*d).sum(2)/np.maximum(1e-20,(d*d).sum(2)),0,1)
    distance=np.linalg.norm(points[:,None]-start-t[:,:,None]*d,axis=2)**2
    if tangents is not None:
        unit=d/np.maximum(1e-12,np.linalg.norm(d,axis=2))[:,:,None]
        cosine=np.abs((unit*tangents[:,None]).sum(2))
        distance+=(.5*spacing)**2*(1-cosine*cosine)
    if point_normals is not None:
        aligned=(point_normals[:,None]*edge_normals[ids]).sum(2)>0
        aligned[~aligned.any(1)]=True
        distance=np.where(aligned,distance,np.inf)
    if forbidden_edges is not None:
        blocked=np.asarray(separate_points)[:,None]&np.asarray(forbidden_edges)[ids]
        distance=np.where(blocked,np.inf,distance)
        if np.any(~np.isfinite(distance).any(1)):raise ValueError('No separate edge is available for a source crease near an authored guide.')
    return ids[np.arange(len(points)),distance.argmin(1)]


def refine(source_mesh, positions, faces, curves, target, paths, *, contacts=(), witnesses=(), active_vertices=None, feature_strength=1., guide_tangent_strength=8., guide_position_strength=40., guide_vertex_strength=0., separate_guide_features=False, witness_policy='both-diagonals', compact_active_terms=False, dense_features=False, allow_boundary=False):
    import torch
    torch.set_num_threads(1)
    start=time.perf_counter()
    def T(x):
        a=np.asarray(x);return torch.tensor(a.tolist(),dtype=torch.float64).reshape(a.shape)
    def I(x):
        a=np.asarray(x);return torch.tensor(a.tolist(),dtype=torch.int64).reshape(a.shape)
    v=np.asarray(source_mesh.vertices);f=np.asarray(source_mesh.faces);p=np.asarray(positions);q=np.asarray(faces)
    active=np.arange(len(p)) if active_vertices is None else np.asarray(active_vertices,int)
    base=T(p);active_ids=I(active)
    h=np.sqrt(source_mesh.area/target);edges=cq._edges(q);Q=I(q);E=I(edges)
    guide_nodes={int(v) for path in paths for v in path['vertices']}
    guide_edges={tuple(sorted((int(a),int(b)))) for path in paths for a,b in zip(path['vertices'][:-1],path['vertices'][1:])}
    settled=bool(cq.quad_quality(p,q,target)['passed'])
    fe,detection=detect(v,f,h,target=target)
    degree=np.bincount(fe.ravel(),minlength=len(v));corners=np.flatnonzero(degree>=3)
    corner_cost=np.linalg.norm(v[corners,None,:]-p[None,:,:],axis=2)
    if separate_guide_features and curves and len(corners):
        separate=np.min([cq._nearest_curve(v[corners],np.asarray(c))[0] for c in curves],axis=0)>h*.1
        corner_cost[np.ix_(separate,np.array(sorted(guide_nodes),int))]+=100*h
    _,corner_ids=linear_sum_assignment(corner_cost)
    C=I(corner_ids);corner_goal=T(v[corners])
    sample_counts=np.array([max(5,int(np.ceil(np.linalg.norm(v[b]-v[a])/(h*.125)))+1) if dense_features else 5 for a,b in fe],int)
    samples=np.concatenate([np.linspace(v[a],v[b],count) for (a,b),count in zip(fe,sample_counts)]) if len(fe) else np.empty((0,3))
    FS=T(samples)
    # The verifier lets one edge loop anywhere across a sub-spacing band of parallel creases
    # represent all of them; pulling every line onto its own loop would pin thin quad rows.
    BW=T(band_widths(v,fe,samples,np.repeat(np.arange(len(fe)),sample_counts),h)) if len(fe) else T(np.empty(0))
    feature_tangents=v[fe[:,1]]-v[fe[:,0]]
    feature_tangents/=np.maximum(1e-12,np.linalg.norm(feature_tangents,axis=1))[:,None]
    feature_tangents=np.repeat(feature_tangents,sample_counts,axis=0);FT=T(feature_tangents)
    edge_lookup={tuple(e):i for i,e in enumerate(edges)};edge_faces=[[] for _ in edges]
    for fi,face in enumerate(q):
        for a,b in zip(face,np.roll(face,-1)):edge_faces[edge_lookup[tuple(sorted((a,b)))]].append(fi)
    if any(len(ids) not in ((1,2) if allow_boundary else (2,)) for ids in edge_faces):raise ValueError('Feature fitting requires manifold quad edges.')
    if allow_boundary:
        boundary_vertices=np.unique([edges[i] for i,ids in enumerate(edge_faces) if len(ids)==1])
        if np.intersect1d(active,boundary_vertices).size:raise ValueError('Open-surface fitting requires fixed boundary vertices.')
        edge_faces=[ids if len(ids)==2 else [ids[0],ids[0]] for ids in edge_faces]
    tri=np.r_[q[:,[0,1,2]],q[:,[0,2,3]]];mesh=trimesh.Trimesh(p,tri,process=False)
    quad_normals=np.cross(p[q[:,1]]-p[q[:,0]],p[q[:,2]]-p[q[:,0]])+np.cross(p[q[:,2]]-p[q[:,0]],p[q[:,3]]-p[q[:,0]])
    quad_normals/=np.maximum(1e-12,np.linalg.norm(quad_normals,axis=1))[:,None]
    anchors,_,owners=trimesh.proximity.closest_point(source_mesh,p)
    A=T(anchors);N=T(source_mesh.face_normals[owners])
    face_owner=trimesh.proximity.closest_point(source_mesh,p[q].mean(1))[2]
    face_normals=T(source_mesh.face_normals[face_owner])
    feature_normals=np.repeat(source_mesh.vertex_normals[fe].mean(1),sample_counts,axis=0)
    separate=np.min([cq._nearest_curve(samples,np.asarray(c))[0] for c in curves],axis=0)>h*.1 if separate_guide_features and curves and len(samples) else np.zeros(len(samples),bool)
    forbidden=np.array([tuple(e) in guide_edges for e in edges])
    selected=nearest_segments(samples,p[edges[:,0]],p[edges[:,1]],feature_tangents,h,feature_normals,quad_normals[np.asarray(edge_faces)].mean(1),forbidden,separate) if len(samples) else np.array([],int)
    FE=I(edges[selected]);CF=I(np.asarray(edge_faces)[np.unique(selected)])
    weights=T(1/np.sqrt(np.maximum(1,np.bincount(selected,minlength=len(edges))[selected]/5)))
    # Balance each movable vertex between its opposite star neighbors (regular) or at its
    # neighbor average (irregular), as ZRemesher's relaxation does; this keeps strips even.
    pairs=[];irregular=[];active_set=set(map(int,active))
    for vertex,star in vertex_stars(q).items():
        if vertex not in active_set or not star:continue
        ring,closed=star
        if closed and len(ring)==4:pairs+=[[vertex,ring[0],ring[2]],[vertex,ring[1],ring[3]]]
        else:irregular.append((vertex,ring))
    PV=I(np.asarray(pairs,int).reshape(-1,3));width=max([len(r) for _,r in irregular],default=1)
    IV=I([v for v,_ in irregular]);IN=I([r+[r[0]]*(width-len(r)) for _,r in irregular]).reshape(-1,width)
    IW=T(np.asarray([[1/len(r)]*len(r)+[0.]*(width-len(r)) for _,r in irregular],float).reshape(-1,width))
    if len(fe):
        selected=nearest_segments(p,v[fe[:,0]],v[fe[:,1]]);a=v[fe[selected,0]];d=v[fe[selected,1]]-a
        t=np.clip(((p-a)*d).sum(1)/np.maximum(1e-20,(d*d).sum(1)),0,1);goal=a+t[:,None]*d
        mask=np.linalg.norm(p-goal,axis=1)<h*.45
        if separate_guide_features:mask&=~np.isin(np.arange(len(p)),list(guide_nodes))
        ids=np.flatnonzero(mask);FI=I(ids);FA=T(goal[ids])
    else:FI=I([]);FA=T(np.empty((0,3)))
    alltri=np.r_[tri,q[:,[1,2,3]],q[:,[1,3,0]]];AT=I(alltri)
    IG=T(trimesh.proximity.closest_point(source_mesh,p[alltri].mean(1))[0])
    near,dist,owner=trimesh.proximity.closest_point(mesh,v)
    selected=dist>h*.15;support=tri[owner[selected]]
    S=I(support);B=T(trimesh.triangles.points_to_barycentric(p[support],near[selected]));SG=T(v[selected])
    contact_terms=[];contact_planes=planes(p,q,contacts)
    scalar_contacts=[(I(a),I(b),I(c),T(n)) for a,b,c,n in contact_planes] if len(contact_planes)<128 else []
    for common_count in (0,1,2):
        if scalar_contacts:break
        group=[row for row in contact_planes if len(row[2])==common_count]
        if not group:continue
        def padded(row,column):return np.pad(row[column],(0,4-len(row[column])),mode='edge')
        contact_terms.append((I([padded(row,0) for row in group]),I([padded(row,1) for row in group]),
                              I(np.asarray([row[2] for row in group]).reshape(len(group),common_count)),T([row[3] for row in group])))
    witness_terms=[]
    if len(witnesses):
        points=np.asarray(witnesses);source_near,source_distance,source_owner=trimesh.proximity.closest_point(source_mesh,points)
        if witness_policy=='oriented':
            from source_projection import OrientedSurface
            near,_,owner=trimesh.proximity.closest_point(mesh,points);on_source=source_distance<1e-8
            if on_source.any():near[on_source],_,owner[on_source]=OrientedSurface(mesh).closest(points[on_source],source_mesh.face_normals[source_owner[on_source]])
            if (~on_source).any():source_near[~on_source]=OrientedSurface(source_mesh).closest(points[~on_source],mesh.face_normals[owner[~on_source]])[0]
            ids=tri[owner]
        elif witness_policy=='both-diagonals':
            witness_mesh=trimesh.Trimesh(p,alltri,process=False)
            near,_,owner=trimesh.proximity.closest_point(witness_mesh,points)
            # A failure can lie on either quad diagonal. Bind to that actual
            # triangle and the same nearest source surface used by the verifier.
            ids=alltri[owner]
        else:raise ValueError('Unknown surface fitting correspondence policy')
        witness_terms=[(I(ids),T(trimesh.triangles.points_to_barycentric(p[ids],near)),T(source_near))]
    guide_terms=[];guide_vertices=[]
    for path,curve in zip(paths,curves):
        points=cq._sample(np.asarray(curve),401)
        # Fit the guide's direction over one face, as the guide check measures it, not sub-face wiggles.
        tangent=window_chords(points,h,np.linalg.norm(points[0]-points[-1])<1e-10);tangent/=np.maximum(1e-12,np.linalg.norm(tangent,axis=1))[:,None]
        pe=np.array(list(zip(path['vertices'][:-1],path['vertices'][1:])))
        selected=nearest_segments(points,p[pe[:,0]],p[pe[:,1]])
        guide_terms.append((I(pe[selected]),T(points),T(tangent)))
        if guide_vertex_strength:
            from guide_ordered_targets import targets
            ids=np.asarray(path['vertices'][:-1] if path['closed'] else path['vertices'])
            guide_vertices.append((I(ids),T(targets(p[ids],curve,path['closed']))))

    local=active_vertices is not None and compact_active_terms
    if local:
        active_faces=np.isin(q,active).any(1);Q=I(q[active_faces]);face_normals=face_normals[I(np.flatnonzero(active_faces))]
        edge_mask=torch.isin(E,active_ids).any(1);E=E[edge_mask]
        A=A[active_ids];N=N[active_ids]
        mask=torch.isin(C,active_ids);C=C[mask];corner_goal=corner_goal[mask]
        mask=torch.isin(FE,active_ids).any(1);FE=FE[mask];FS=FS[mask];FT=FT[mask];weights=weights[mask];BW=BW[mask]
        mask=I(active_faces.astype(int))[CF].any(1);CFQ=I(q)[CF[mask]]
        mask=torch.isin(FI,active_ids);FI=FI[mask];FA=FA[mask]
        mask=torch.isin(PV[:,0],active_ids);PV=PV[mask]
        mask=torch.isin(IV,active_ids);IV=IV[mask];IN=IN[mask];IW=IW[mask]
        mask=torch.isin(AT,active_ids).any(1);AT=AT[mask];IG=IG[mask]
        mask=torch.isin(S,active_ids).any(1);S=S[mask];B=B[mask];SG=SG[mask]
        def relevant(rows):
            result=[]
            for ids,values,extra in rows:
                mask=torch.isin(ids,active_ids).any(1)
                if mask.any():result.append((ids[mask],values[mask],extra[mask]))
            return result
        guide_terms=relevant(guide_terms);witness_terms=relevant(witness_terms)

    def objective(flat):
        variable=T(flat.reshape(-1,3)).requires_grad_(True)
        if active_vertices is None:X=variable
        else:X=base.clone();X[active_ids]=variable
        P=X[Q];D=torch.roll(P,-1,1)-P
        L=torch.linalg.vector_norm(D,dim=2).clamp_min(1e-10);previous=-torch.roll(D,1,1);den=L*torch.roll(L,1,1)
        cosine=(previous*D).sum(2)/den;corner=torch.linalg.cross(D,previous)/den[:,:,None]
        pn=torch.stack([torch.linalg.cross(P[:,b]-P[:,a],P[:,c]-P[:,a]) for a,b,c in ((0,1,2),(0,2,3),(1,2,3),(1,3,0))],dim=1)
        normal=pn[:,0]+pn[:,1];normal=normal/torch.linalg.vector_norm(normal,dim=1).clamp_min(1e-12)[:,None]
        pn=pn/torch.linalg.vector_norm(pn,dim=2).clamp_min(1e-12)[:,:,None]
        projected=torch.einsum('fci,fni->fcn',corner,pn)
        jac=(corner*normal[:,None]).sum(2);alignment=(corner*face_normals[:,None]).sum(2)
        length=torch.linalg.vector_norm(X[E[:,1]]-X[E[:,0]],dim=1);delta=((X[active_ids] if local else X)-A)/h
        a=X[FE[:,0]];d=X[FE[:,1]]-a;t=((FS-a)*d).sum(1)/(d*d).sum(1).clamp_min(1e-15);near=a+t.clamp(0,1)[:,None]*d
        gap=torch.linalg.vector_norm(near-FS,dim=1).clamp_min(1e-15);slack=(1-BW/gap).clamp_min(0)
        reach=(near-FS)*slack[:,None];beyond=(gap-BW).clamp_min(0)
        warpage=((P[:,3]-P[:,0])*pn[:,0]).sum(1)/h
        if local:
            cp=X[CFQ]
            cn=torch.linalg.cross(cp[:,:,1]-cp[:,:,0],cp[:,:,2]-cp[:,:,0])+torch.linalg.cross(cp[:,:,2]-cp[:,:,0],cp[:,:,3]-cp[:,:,0])
            cn=cn/torch.linalg.vector_norm(cn,dim=2).clamp_min(1e-12)[:,:,None]
            crease_cos=(cn[:,0]*cn[:,1]).sum(1)
        else:crease_cos=(normal[CF[:,0]]*normal[CF[:,1]]).sum(1)
        terms=[torch.relu(.60-jac).ravel()*135,torch.relu(.35-alignment).ravel()*30,
               torch.relu(.58-projected).ravel()*180,torch.relu(torch.abs(cosine)-.78).ravel()*45,cosine.ravel()*.2,
               torch.relu(L.max(1).values/L.min(1).values-3.2)*12,
               torch.relu(L.max(1).values/L.min(1).values-5.5)*100,
               (delta*N).sum(1)*18,delta.ravel()*4,torch.relu(torch.linalg.vector_norm(delta,dim=1)-.2)*50,warpage*25,
               torch.relu(.35-length/h)*5,torch.relu(length/h-1.8)*2,
               ((X[PV[:,0]]-(X[PV[:,1]]+X[PV[:,2]])*.5)/h*BALANCE_WEIGHT).ravel(),((X[IV]-(X[IN]*IW[:,:,None]).sum(1))/h*BALANCE_WEIGHT).ravel(),
               (reach/h*55*feature_strength*weights[:,None]).ravel(),torch.relu(beyond/h-.18)*weights*(80 if settled else 0)*feature_strength,
               (torch.linalg.cross(d/torch.linalg.vector_norm(d,dim=1).clamp_min(1e-12)[:,None],FT)*weights[:,None]).ravel()*(15 if settled else 8),
               ((X[C]-corner_goal)/h*65).ravel(),((X[FI]-FA)/h*12).ravel(),
               ((X[S]*B[:,:,None]).sum(1)-SG).ravel()/h*6,((X[AT].mean(1)-IG)/h).ravel()*20,
               torch.relu(crease_cos-.70710678)*(100 if settled else 45)]
        for a,b,common,n in scalar_contacts:
            if len(common)==2:
                edge=X[common[1]]-X[common[0]];edge=edge/torch.linalg.vector_norm(edge).clamp_min(1e-12)
                n=n-(n@edge)*edge;n=n/torch.linalg.vector_norm(n).clamp_min(1e-12)
            lo=(X[a]@n).min();hi=(X[b]@n).max()
            if len(common):
                middle=(X[common]@n).mean();terms.extend([torch.relu(.003-(lo-middle)/h)*2500,torch.relu(.003-(middle-hi)/h)*2500])
            else:terms.append(torch.relu(.005-(lo-hi)/h)*2500)
        for a,b,common,n in contact_terms:
            if common.shape[1]==2:
                edge=X[common[:,1]]-X[common[:,0]];edge=edge/torch.linalg.vector_norm(edge,dim=1).clamp_min(1e-12)[:,None]
                n=n-(n*edge).sum(1)[:,None]*edge;n=n/torch.linalg.vector_norm(n,dim=1).clamp_min(1e-12)[:,None]
            lo=(X[a]*n[:,None]).sum(2).min(1).values;hi=(X[b]*n[:,None]).sum(2).max(1).values
            if common.shape[1]:
                middle=(X[common]*n[:,None]).sum(2).mean(1);terms.extend([torch.relu(.003-(lo-middle)/h)*2500,torch.relu(.003-(middle-hi)/h)*2500])
            else:terms.append(torch.relu(.005-(lo-hi)/h)*2500)
        for ids,bary,goal in witness_terms:terms.append(torch.relu(torch.linalg.vector_norm((X[ids]*bary[:,:,None]).sum(1)-goal,dim=1)/h-.40)*300)
        for ids,points,tangent in guide_terms:
            a=X[ids[:,0]];d=X[ids[:,1]]-a;length=torch.linalg.vector_norm(d,dim=1).clamp_min(1e-12)
            t=((points-a)*d).sum(1)/(length*length);near=a+t.clamp(0,1)[:,None]*d
            terms.extend([((near-points)/h*guide_position_strength).ravel(),(torch.linalg.cross(d/length[:,None],tangent)*guide_tangent_strength).ravel()])
        for ids,goal in guide_vertices:terms.append(((X[ids]-goal)/h*guide_vertex_strength).ravel())
        value=sum((r*r).sum() for r in terms);value.backward()
        return float(value.detach()),np.asarray(variable.grad.tolist()).ravel()
    opt=minimize(objective,p[active].ravel(),jac=True,method='L-BFGS-B',options=dict(maxiter=250,ftol=1e-10,gtol=1e-5,maxls=25,maxcor=15))
    result=p.copy();result[active]=opt.x.reshape(-1,3)
    return result,dict(seconds=time.perf_counter()-start,evaluations=opt.nfev,converged=bool(opt.success),message=str(opt.message),features=detection,contactConstraints=len(contact_planes),surfaceWitnesses=len(witnesses),activeVertices=len(active))
