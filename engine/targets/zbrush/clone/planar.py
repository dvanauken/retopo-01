"""Engineering constrained planar-chart quadrangulation for sharp polyhedra.

This is an alternative implementation, not ZBrush parameterization recovery.
Physical source seams share samples globally; guide constraints enter planar
PSLGs. Convex triangle pairs form quads; a conforming midpoint/center split
produces only quads while retaining every physical source corner and seam.
"""
from collections import defaultdict
import math
import numpy as np
import triangle
import trimesh

def cross2(a,b):return a[...,0]*b[...,1]-a[...,1]*b[...,0]

def decompose(vertices,triangles,sharp_angle=30.):
    v=np.asarray(vertices,dtype=float);f=np.asarray(triangles,dtype=int);span=float(np.ptp(v,axis=0).max());eps=1e-8*span
    normals=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]);length=np.linalg.norm(normals,axis=1)
    if np.any(length<=0):raise ValueError('Degenerate source face')
    area=length*.5;normals/=length[:,None];incidence=defaultdict(list);adj=defaultdict(list)
    for i,row in enumerate(f):
        for a,b in zip(row,np.roll(row,-1)):incidence[tuple(sorted((int(a),int(b))))].append((i,int(a),int(b)))
    if any(len(rows)!=2 for rows in incidence.values()):raise NotImplementedError('Planar solid route requires closed two-face source edges')
    for rows in incidence.values():
        i,j=rows[0][0],rows[1][0];adj[i].append(j);adj[j].append(i)
    labels=np.full(len(f),-1,dtype=int);charts=[]
    for seed in range(len(f)):
        if labels[seed]>=0:continue
        ci=len(charts);origin=v[f[seed,0]];n=normals[seed];pending=[seed];ids=[]
        while pending:
            face=pending.pop()
            if labels[face]>=0 or normals[face]@n<1-1e-10 or np.max(abs((v[f[face]]-origin)@n))>eps:continue
            labels[face]=ci;ids.append(face);pending.extend(adj[face])
        axis=v[f[seed,1]]-origin;axis/=np.linalg.norm(axis);other=np.cross(n,axis)
        charts.append(dict(faces=ids,origin=origin,normal=n,axis=axis,other=other,area=float(area[ids].sum())))
    physical=[];pairs=[]
    for edge,rows in incidence.items():
        a,b=labels[rows[0][0]],labels[rows[1][0]]
        if a==b:continue
        if normals[rows[0][0]]@normals[rows[1][0]]>math.cos(math.radians(sharp_angle))+1e-10:
            raise NotImplementedError('Source has curved or shallow noncoplanar charts; use the field route')
        physical.append(edge);pairs.append((int(a),int(b)))
    if len(charts)<2:raise NotImplementedError('Closed solid needs multiple planar charts')
    from features import paths_from_edges
    paths=[];chart_paths=defaultdict(list)
    for ids,path in paths_from_edges(physical):
        if path[0]==path[-1]:raise NotImplementedError('Closed two-plane seam is not a finite straight polyhedral edge')
        a,b=v[path[0]],v[path[-1]];d=b-a;den=d@d
        if den==0 or np.max(np.linalg.norm(v[path]-a-(((v[path]-a)@d)/den)[:,None]*d,axis=1))>eps:raise NotImplementedError('Nonstraight physical seam needs the field route')
        involved=set(pairs[ids[0]])
        if any(set(pairs[i])!=involved for i in ids):raise NotImplementedError('Changing planar ownership inside a physical seam')
        pi=len(paths);paths.append(dict(vertices=path,edges=ids,a=a,b=b,charts=sorted(involved),parameters=[]))
        for ci in involved:
            x,y=path[:2];rows=incidence[tuple(sorted((x,y)))];oriented=next(row for row in rows if labels[row[0]]==ci)
            chart_paths[ci].append((pi,oriented[1]==x and oriented[2]==y))
    # Record physical corner count per chart, independent of tessellation.
    for ci,chart in enumerate(charts):chart['physicalPathCount']=len(chart_paths[ci])
    return dict(vertices=v,triangles=f,charts=charts,paths=paths,chartPaths=chart_paths,span=span,epsilon=eps,totalArea=float(area.sum()))

def _inside(chart,p,domain):
    v=domain['vertices'];f=domain['triangles'][chart['faces']]
    if abs((p-chart['origin'])@chart['normal'])>domain['epsilon']:return False
    p2=np.array([(p-chart['origin'])@chart['axis'],(p-chart['origin'])@chart['other']]);q=np.stack([(v[f]-chart['origin'])@chart['axis'],(v[f]-chart['origin'])@chart['other']],axis=-1)
    a,b,c=q[:,0],q[:,1],q[:,2];den=cross2(b-a,c-a);u=cross2(p2-a,c-a)/den;w=cross2(b-a,p2-a)/den
    return bool(np.any((u>=-1e-8)&(w>=-1e-8)&(u+w<=1+1e-8)))

def _simplify(points,tolerance):
    p=np.asarray(points,dtype=float)
    if len(p)<=2:return p
    d=p[-1]-p[0];den=d@d
    if den==0:distance=np.linalg.norm(p-p[0],axis=1)
    else:
        t=np.clip((p-p[0])@d/den,0,1);distance=np.linalg.norm(p-p[0]-t[:,None]*d,axis=1)
    i=int(np.argmax(distance))
    if distance[i]<=tolerance:return p[[0,-1]]
    return np.vstack([_simplify(p[:i+1],tolerance)[:-1],_simplify(p[i:],tolerance)])

def _blocks(domain,curves):
    v=domain['vertices'];f=domain['triangles'];charts=domain['charts'];surface=trimesh.Trimesh(vertices=v,faces=f,process=False);by_chart=defaultdict(list);projected=[]
    def add(ci,p,q,curve):
        blocks=by_chart[ci]
        if blocks and blocks[-1]['curve']==curve and np.linalg.norm(blocks[-1]['points'][-1]-p)<=domain['epsilon']:blocks[-1]['points'].append(q)
        else:blocks.append(dict(curve=curve,points=[p,q]))
    for curve,points in enumerate(curves):
        points=np.asarray(points,dtype=float);p,_,_=trimesh.proximity.closest_point_naive(surface,points);projected.append(p)
        for a,b in zip(p[:-1],p[1:]):
            if np.linalg.norm(b-a)<=domain['epsilon']:continue
            aa=[i for i,c in enumerate(charts) if _inside(c,a,domain)];bb=[i for i,c in enumerate(charts) if _inside(c,b,domain)]
            common=[ci for ci in set(aa)&set(bb) if _inside(charts[ci],(a+b)*.5,domain)]
            if common:
                for ci in sorted(common):add(ci,a,b,curve)
                continue
            options=[]
            for path in domain['paths']:
                x,y=path['charts']
                if x in bb and y in aa:x,y=y,x
                if x not in aa or y not in bb:continue
                ca,cb=charts[x],charts[y];s,t=path['a'],path['b'];axis=(t-s)/np.linalg.norm(t-s);angle=math.atan2(axis@np.cross(cb['normal'],ca['normal']),cb['normal']@ca['normal'])
                q=b-s;rot=q*math.cos(angle)+np.cross(axis,q)*math.sin(angle)+axis*(axis@q)*(1-math.cos(angle));unfold=s+rot
                u=np.array([(a-s)@ca['axis'],(a-s)@ca['other']]);d=np.array([(unfold-a)@ca['axis'],(unfold-a)@ca['other']]);edge=np.array([(t-s)@ca['axis'],(t-s)@ca['other']]);matrix=np.column_stack([d,-edge])
                if abs(np.linalg.det(matrix))<1e-15*domain['span']**2:continue
                alpha,beta=np.linalg.solve(matrix,-u)
                if -1e-8<=alpha<=1+1e-8 and -1e-8<=beta<=1+1e-8:
                    c=s+np.clip(beta,0,1)*(t-s)
                    if _inside(ca,(a+c)*.5,domain) and _inside(cb,(b+c)*.5,domain):options.append((float(np.linalg.norm(a-c)+np.linalg.norm(b-c)),x,y,c))
            if not options:raise NotImplementedError('Planar guide step crosses nonadjacent facets or leaves its domain; provide intermediate surface samples')
            _,x,y,c=min(options,key=lambda item:item[0]);add(x,a,c,curve);add(y,c,b,curve)
    return by_chart,projected

def _pair_cells(uv,triangles,constrained,guide_segments):
    incidence=defaultdict(list)
    for i,row in enumerate(triangles):
        for a,b in zip(row,np.roll(row,-1)):incidence[tuple(sorted((int(a),int(b))))].append(i)
    candidates={};adj=defaultdict(list)
    for edge,ids in incidence.items():
        if len(ids)!=2 or edge in constrained:continue
        directed=[]
        for face in ids:
            row=triangles[face].tolist();directed.extend((a,b) for a,b in zip(row,row[1:]+row[:1]) if tuple(sorted((a,b)))!=edge)
        following=dict(directed)
        if len(following)!=4:continue
        row=[min(following)]
        for _ in range(3):row.append(following[row[-1]])
        if len(set(row))!=4 or following[row[-1]]!=row[0]:continue
        p=uv[row];delta=np.roll(p,-1,axis=0)-p;length=np.linalg.norm(delta,axis=1)
        if min(length)<=0 or np.any(cross2(delta,np.roll(delta,-1,axis=0))<=1e-16):continue
        cosine=np.sum(-np.roll(delta,1,axis=0)*delta,axis=1)/(np.roll(length,1)*length);score=2*(1-float(np.mean(abs(cosine))))-.1*math.log(float(max(length)/min(length)))
        if guide_segments:
            center=p.mean(axis=0);best=None
            for a,b in guide_segments:
                d=b-a;den=d@d
                if den==0:continue
                t=np.clip((center-a)@d/den,0,1);distance=float(np.linalg.norm(center-a-t*d))
                if best is None or distance<best[0]:best=(distance,d/math.sqrt(den))
            if best:
                g=best[1];normal=np.array([-g[1],g[0]]);unit=delta/length[:,None];score+=.5*float(np.mean(np.maximum(abs(unit@g),abs(unit@normal))))
        key=tuple(sorted(ids));candidates[key]=(score,row);adj[ids[0]].append(ids[1]);adj[ids[1]].append(ids[0])
    partner={}
    for pair,(score,row) in sorted(candidates.items(),key=lambda item:(-item[1][0],item[0])):
        a,b=pair
        if a not in partner and b not in partner:partner[a]=b;partner[b]=a
    # Length-three augmentations improve coverage without adding dependencies.
    changed=True
    while changed:
        changed=False
        for a in range(len(triangles)):
            if a in partner:continue
            choice=None
            for b in adj[a]:
                if b not in partner:continue
                c=partner[b]
                for d in adj[c]:
                    if d==a or d in partner:continue
                    gain=candidates[tuple(sorted((a,b)))][0]+candidates[tuple(sorted((c,d)))][0]-candidates[tuple(sorted((b,c)))][0]
                    if choice is None or gain>choice[0]:choice=(gain,b,c,d)
            if choice:
                _,b,c,d=choice;partner[a]=b;partner[b]=a;partner[c]=d;partner[d]=c;changed=True
    cells=[];used=set()
    for i,row in enumerate(triangles):
        if i in used:continue
        if i in partner:
            j=partner[i];cells.append(candidates[tuple(sorted((i,j)))][1]);used.update([i,j])
        else:cells.append(row.tolist());used.add(i)
    return cells

def construct_planar(vertices,triangles,curves,*,target=500,sharp_angle=30.,domain=None):
    d=decompose(vertices,triangles,sharp_angle) if domain is None else domain;charts=d['charts'];paths=d['paths'];h=math.sqrt(d['totalArea']/target);eps=d['epsilon']
    blocks,projected=_blocks(d,curves);prepared=defaultdict(list)
    for path in paths:path['parameters']=list(np.linspace(0,1,max(1,int(math.ceil(np.linalg.norm(path['b']-path['a'])/(2*h))))+1))
    for ci,items in blocks.items():
        for item in items:
            p=_simplify(item['points'],.05*h);samples=[]
            for a,b in zip(p[:-1],p[1:]):samples.extend(np.linspace(a,b,max(1,int(math.ceil(np.linalg.norm(b-a)/(2*h))))+1)[:-1])
            samples.append(p[-1]);samples=np.asarray(samples);prepared[ci].append(samples)
            for point in samples:
                for path in paths:
                    delta=path['b']-path['a'];den=delta@delta;t=float((point-path['a'])@delta/den)
                    if -1e-8<=t<=1+1e-8 and np.linalg.norm(point-path['a']-t*delta)<=eps:path['parameters'].append(float(np.clip(t,0,1)))
    output=[];corners={}
    def corner(i):
        if i not in corners:corners[i]=len(output);output.append(d['vertices'][i].copy())
        return corners[i]
    for path in paths:
        parameters=[]
        for t in sorted(path['parameters']):
            if not parameters or abs(t-parameters[-1])*np.linalg.norm(path['b']-path['a'])>eps:parameters.append(t)
        path['parameters']=parameters;ids=[]
        for t in parameters:
            if t<=1e-12:ids.append(corner(path['vertices'][0]))
            elif t>=1-1e-12:ids.append(corner(path['vertices'][-1]))
            else:ids.append(len(output));output.append(path['a']+t*(path['b']-path['a']))
        path['ids']=ids
    cells=[];chart_stats=[]
    for ci,chart in enumerate(charts):
        local=[];global_ids=[];by_global={};segments=set();boundary=[]
        def add(point,gid=None):
            if gid is not None and gid in by_global:return by_global[gid]
            uv=np.array([(point-chart['origin'])@chart['axis'],(point-chart['origin'])@chart['other']])
            for i,previous in enumerate(local):
                if np.linalg.norm(uv-previous)<=eps:
                    if gid is not None and global_ids[i] not in (None,gid):raise ValueError('Distinct physical seam vertices coincide')
                    if gid is not None:global_ids[i]=gid;by_global[gid]=i
                    return i
            i=len(local);local.append(uv);global_ids.append(gid)
            if gid is not None:by_global[gid]=i
            return i
        directed=[]
        for pi,forward in d['chartPaths'][ci]:
            ids=paths[pi]['ids'] if forward else paths[pi]['ids'][::-1]
            local_ids=[add(output[i],i) for i in ids];directed.extend(zip(local_ids[:-1],local_ids[1:]));segments.update(tuple(sorted(pair)) for pair in zip(local_ids[:-1],local_ids[1:]))
        following=dict(directed)
        if len(following)!=len(directed):raise NotImplementedError('Pinched planar chart boundary')
        visited=set();holes=[]
        for seed in sorted(following):
            if seed in visited:continue
            loop=[];v=seed
            while v not in visited:visited.add(v);loop.append(v);v=following[v]
            if v!=seed:raise ValueError('Planar chart boundary failed closure')
            q=np.asarray(local)[loop];signed=float(np.sum(cross2(q,np.roll(q,-1,axis=0)))*.5)
            if signed<0:
                marker=triangle.triangulate(dict(vertices=q,segments=np.array([[i,(i+1)%len(q)] for i in range(len(q))])),'pzQ')
                holes.append(np.asarray(marker['vertices'])[marker['triangles'][0]].mean(axis=0))
        guide_segments=[]
        for points in prepared[ci]:
            ids=[]
            for point in points:
                gid=None
                for pi,_ in d['chartPaths'][ci]:
                    path=paths[pi];delta=path['b']-path['a'];t=float((point-path['a'])@delta/(delta@delta))
                    if -1e-8<=t<=1+1e-8 and np.linalg.norm(point-path['a']-t*delta)<=eps:
                        k=int(np.argmin(abs(np.asarray(path['parameters'])-t)));gid=path['ids'][k];point=output[gid];break
                ids.append(add(point,gid))
            for a,b in zip(ids[:-1],ids[1:]):
                if a==b:continue
                guide_segments.append((local[a],local[b]))
                # A guide on a physical seam is already represented by its
                # conforming boundary chain, including all intervening samples.
                ga,gb=global_ids[a],global_ids[b]
                if ga is not None and gb is not None and any(ga in paths[pi]['ids'] and gb in paths[pi]['ids'] for pi,_ in d['chartPaths'][ci]):continue
                segments.add(tuple(sorted((a,b))))
        # Node near-collinear existing points before calling exact predicates.
        # Bend an interior guide by at most epsilon through the existing point;
        # never invent an unshared physical-boundary vertex.
        uv_input=np.asarray(local);boundary_keys={tuple(sorted(pair)) for pair in directed};refined=set()
        for a,b in segments:
            delta=uv_input[b]-uv_input[a];den=float(delta@delta)
            if den==0:continue
            values=(uv_input-uv_input[a])@delta/den
            distances=np.linalg.norm(uv_input-uv_input[a]-values[:,None]*delta,axis=1)
            middle=[i for i in range(len(local)) if i not in (a,b) and 0<values[i]<1 and distances[i]<=eps]
            if (a,b) in boundary_keys and any(global_ids[i] is None for i in middle):raise RuntimeError('Guide point needs registration on the shared physical seam')
            chain=[a]+sorted(middle,key=lambda i:(values[i],i))+[b]
            refined.update(tuple(sorted((x,y))) for x,y in zip(chain[:-1],chain[1:]) if x!=y)
        data=dict(vertices=uv_input,segments=np.asarray(sorted(refined),dtype=np.int32))
        if holes:data['holes']=np.asarray(holes)
        result=triangle.triangulate(data,f'pYq20a{3*h*h:.17g}S{max(1000,target*8)}Qz')
        uv=np.asarray(result['vertices']);tris=np.asarray(result.get('triangles',[]),dtype=int)
        if len(tris)==0 or len(uv)<len(local) or not np.allclose(uv[:len(local)],local,rtol=0,atol=eps):raise RuntimeError('Planar triangulator changed original input identity')
        area=float(np.abs(cross2(uv[tris[:,1]]-uv[tris[:,0]],uv[tris[:,2]]-uv[tris[:,0]])).sum()*.5)
        if abs(area-chart['area'])>max(1e-8*d['totalArea'],1e-12):raise RuntimeError('Planar chart triangulation changed domain area')
        for i,p in enumerate(uv):
            if i>=len(global_ids):global_ids.append(None)
            if global_ids[i] is None:
                point=chart['origin']+p[0]*chart['axis']+p[1]*chart['other']
                for pi,_ in d['chartPaths'][ci]:
                    path=paths[pi];delta=path['b']-path['a'];t=float((point-path['a'])@delta/(delta@delta))
                    if -1e-8<=t<=1+1e-8 and np.linalg.norm(point-path['a']-t*delta)<=eps:raise RuntimeError('Unregistered Steiner point split a shared physical seam')
                global_ids[i]=len(output);output.append(point)
        constrained={tuple(sorted(map(int,pair))) for pair in result.get('segments',data['segments'])}
        local_cells=_pair_cells(uv,tris,constrained,guide_segments)
        cells.extend([[global_ids[i] for i in row] for row in local_cells]);chart_stats.append(dict(sourceTriangles=len(chart['faces']),area=chart['area'],triangles=len(tris),pairedQuads=sum(len(row)==4 for row in local_cells),remainingTriangles=sum(len(row)==3 for row in local_cells)))
    midpoints={};faces=[]
    for row in cells:
        center=len(output);output.append(np.asarray([output[i] for i in row]).mean(axis=0));middle=[]
        for a,b in zip(row,row[1:]+row[:1]):
            key=tuple(sorted((a,b)))
            if key not in midpoints:midpoints[key]=len(output);output.append((output[a]+output[b])*.5)
            middle.append(midpoints[key])
        for k,v in enumerate(row):faces.append([v,middle[k],center,middle[k-1]])
    used=np.unique([i for row in faces for i in row]);remap=np.full(len(output),-1,dtype=int);remap[used]=np.arange(len(used));positions=np.asarray(output)[used];faces=[[int(remap[i]) for i in row] for row in faces]
    from features import output_creases
    return positions,faces,dict(backend='engineering-planar-pslg-quads',nativeComparisonPerformed=False,generalAlgorithmRecovered=False,
        target=target,guideMode=2,vertices=len(positions),faces=len(faces),sourceVertices=len(d['vertices']),sourceTriangles=len(d['triangles']),
        featurePolicy='preserve-sharp',outputCreases=output_creases(positions,faces,sharp_angle),
        planarPolicy=dict(charts=len(charts),physicalSeams=len(paths),chartStatistics=chart_stats,projection='Nearest original source triangle per input sample; adjacent facet crossings unfolded onto their shared edge',
                          normalTolerance=1e-10,planeTolerance=eps,pslgNodingTolerance=eps,boundaryPrecursorSpacing=2*h,guideSimplificationTolerance=.05*h,triangleMaximumArea=3*h*h,triangleOptions='pYq20a<area>S<budget>Qz',
                          quadrangulation='Convex adjacent-triangle pairing with guide-tangent score and length-three augmentations, then globally conforming edge-midpoint/cell-center subdivision',
                          projectedCurvePoints=[p.tolist() for p in projected]),
        coordinateMap=dict(sourceToCore='source coordinates, float64 planar charts',center=[0,0,0],scale=1,nativeHostTransform=False,float32Narrowing=False),
        limitations=['Engineering alternative, not native field/parameterization/extraction equivalence.','Target count is approximate and constrained by physical seams/guide sampling.','Arbitrary source attributes/partial crease strengths are not transferred.','Sparse curve steps across nonadjacent facets need additional surface samples.'])
