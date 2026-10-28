"""Immutable source-face partitions and explicit, reversible repair caps."""
from pathlib import Path
from collections import defaultdict
import hashlib,json,re
import numpy as np
import trimesh
import triangle
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parent
FORMAT=1

def indices(value,count):
    if not isinstance(value,list) or not value or len(value)>count or any(type(i) is not int or not 0<=i<count for i in value) or len(set(value))!=len(value):
        raise ValueError('Select distinct source faces within the current model.')
    return sorted(value)

def extract(vertices,faces,face_ids,*,open_region=False):
    """Retain exact original coordinates; cap one simple boundary per part.

    No arbitrary hole filling: disconnected, branched or multiple boundaries
    reject with the selection unchanged. Every cap is identified for review.
    """
    v=np.asarray(vertices,float);f=np.asarray(faces,int);ids=indices(face_ids,len(f))
    selected=f[ids];used=np.unique(selected);lookup=np.full(len(v),-1,int);lookup[used]=np.arange(len(used));p=v[used].copy();q=lookup[selected]
    mesh=trimesh.Trimesh(p,q,process=False)
    if len(mesh.split(only_watertight=False))!=1:raise ValueError('The selection has disconnected islands. Select one connected part at a time.')
    if open_region:
        return dict(vertices=p.tolist(),faces=q.tolist(),sourceFaceIds=ids,originalVertexIds=used.tolist(),repair=dict(capFaceStart=len(q),capFaces=0,closed=bool(mesh.is_watertight),consistentWinding=bool(mesh.is_winding_consistent),excludedRegion=True),stats=dict(triangles=len(q),quads=0),area=float(mesh.area))
    edge_rows=defaultdict(list)
    for face in q:
        for a,b in zip(face,np.roll(face,-1)):edge_rows[tuple(sorted((int(a),int(b))))].append((int(a),int(b)))
    if any(len(rows)>2 for rows in edge_rows.values()):raise ValueError('The selected region is nonmanifold.')
    boundary=[rows[0] for rows in edge_rows.values() if len(rows)==1];cap=[];ring=[];deviation=0.
    if boundary:
        following=dict(boundary)
        if len(following)!=len(boundary) or len(set(following.values()))!=len(boundary):raise ValueError('The cut branches at a vertex. Grow or shrink the selection to make a simple boundary.')
        ring=[min(following)]
        while following[ring[-1]]!=ring[0]:
            nxt=following[ring[-1]]
            if nxt in ring:raise ValueError('The cut boundary is not a simple loop.')
            ring.append(nxt)
        if len(ring)!=len(boundary):raise ValueError('This cut creates multiple openings. Split a region with one boundary loop first.')
        # Reverse the source winding to close the opening. Triangle preserves
        # every boundary segment, including collinear vertices.
        ring=list(reversed(ring));points=p[ring];center=points.mean(0)
        _,_,basis=np.linalg.svd(points-center,full_matrices=False);uv=(points-center)@basis[:2].T
        poly=Polygon(uv)
        if not poly.is_valid or poly.area<1e-12:raise ValueError('The repair boundary folds in projection. Choose a flatter cut.')
        deviation=float(np.max(np.abs((points-center)@basis[2])))
        if deviation>float(np.linalg.norm(np.ptp(points,axis=0)))*.08:
            raise ValueError('This boundary is too curved for a safe repair cap. Choose a flatter cut.')
        segments=np.c_[np.arange(len(ring)),np.roll(np.arange(len(ring)),-1)]
        patch=triangle.triangulate(dict(vertices=uv,segments=segments),'pQY')
        if len(patch.get('vertices',[]))!=len(ring) or 'triangles' not in patch:raise ValueError('The cap could not retain its boundary vertices.')
        area=np.sum(uv[:,0]*np.roll(uv[:,1],-1)-uv[:,1]*np.roll(uv[:,0],-1))
        for tri in patch['triangles']:
            a,b,c=uv[tri];ab=b-a;ac=c-a;cross=ab[0]*ac[1]-ab[1]*ac[0]
            row=[ring[int(i)] for i in tri]
            if cross*area<0:row.reverse()
            cap.append(row)
        # A cut can contain an existing chord between boundary vertices. Cap
        # diagonals must not reuse that source edge (four incident faces).
        cap_edges=defaultdict(int)
        for row in cap:
            for a,b in zip(row,np.roll(row,-1)):cap_edges[tuple(sorted((a,b)))]+=1
        conflicts={edge for edge,n in cap_edges.items() if n==2 and edge in edge_rows}
        if conflicts:
            points=p.tolist();midpoints={}
            for a,b in sorted(conflicts):midpoints[a,b]=len(points);points.append(((p[a]+p[b])*.5).tolist())
            revised=[]
            for row in cap:
                polygon=[]
                for a,b in zip(row,np.roll(row,-1)):
                    polygon.append(a);mid=midpoints.get(tuple(sorted((a,b))))
                    if mid is not None:polygon.append(mid)
                if len(polygon)==3:revised.append(row);continue
                center_id=len(points);points.append(p[row].mean(0).tolist())
                revised.extend([[a,b,center_id] for a,b in zip(polygon,np.roll(polygon,-1))])
            p=np.asarray(points);cap=revised
        q=np.r_[q,np.asarray(cap,int)]
    closed=trimesh.Trimesh(p,q,process=False)
    if not closed.is_watertight or not closed.is_winding_consistent or np.any(closed.area_faces<=0):
        ee,cc=np.unique(np.sort(closed.edges,axis=1),axis=0,return_counts=True)
        raise ValueError(f'The repair did not produce a closed, consistently wound part (closed={closed.is_watertight}, winding={closed.is_winding_consistent}, edges={ee[cc!=2][:12].tolist()}, counts={cc[cc!=2][:12].tolist()}).')
    if closed.volume<=0:raise ValueError('The repair would produce an inverted or empty part.')
    # Check new cap contacts, without relabeling inherited source contacts.
    if cap:
        validate_cap_contacts(p,q,len(ids))
    return dict(vertices=p.tolist(),faces=q.tolist(),sourceFaceIds=ids+[-1]*len(cap),originalVertexIds=used.tolist()+[-1]*(len(p)-len(used)),
                repair=dict(capFaceStart=len(ids),capFaces=len(cap),boundaryVertexIds=ring,boundaryOriginalVertexIds=[int(used[i]) for i in ring],maxProjectionDeviation=deviation,closed=True,consistentWinding=True),
                stats=dict(triangles=len(q),quads=0,boundaryEdges=0),area=float(closed.area))

def validate_cap_contacts(p,q,start):
    from rtree.index import Index,Property
    from surface_contacts_fast import triangle_contacts,on_boundary
    tri=p[q];bounds=np.c_[tri.min(1)-1e-9,tri.max(1)+1e-9]
    tree=Index(((i,box,None) for i,box in enumerate(bounds)),properties=Property(dimension=3))
    try:
        for a in range(start,len(q)):
            for b in tree.intersection(bounds[a]):
                if b==a or (b>=start and b<a):continue
                common=np.intersect1d(q[a],q[b]);shared=[]
                if len(common)==2:shared=[common]
                points,count=triangle_contacts(tri[a],tri[b],1e-9)
                points=points[:count]
                if count:points=np.r_[points,points.mean(0)[None,:],(points+np.roll(points,1,axis=0))*.5]
                for point in points:
                    if not on_boundary(point,p,common,np.asarray(shared,dtype=np.int64).reshape(-1,2),4e-9):raise ValueError('The repair cap crosses the retained surface. Choose another boundary.')
    finally:tree.close()

def store_part(spec,face_ids=None,*,parent=None,geometry=None,recipe=None,open_region=False):
    source=ROOT/'assets/models'/(spec['id']+'.obj')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=spec['sourceSha256']:raise ValueError('The source has changed. Reload before preparing parts.')
    original=json.loads((ROOT/'assets/models'/(spec['id']+'.json')).read_text())
    model=load_part(parent,spec['id'])[0] if parent else original
    ids=indices(face_ids,len(model['faces'])) if face_ids is not None else None
    identity=dict(format=FORMAT,meshId=spec['id'],sourceSha256=spec['sourceSha256'],parent=parent,faceIds=ids,recipe=recipe,openRegion=open_region)
    part_id=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    directory=ROOT/'runs'/'parts'/part_id;ready=directory/'mesh.json'
    if ready.exists():return json.loads(ready.read_text())
    data=geometry if geometry is not None else extract(model['vertices'],model['faces'],ids,open_region=open_region)
    directory.mkdir(parents=True,exist_ok=True)
    obj=''.join('v '+' '.join(format(x,'.17g') for x in p)+'\n' for p in data['vertices'])+''.join('f '+' '.join(str(i+1) for i in row)+'\n' for row in data['faces'])
    digest=hashlib.sha256(obj.encode()).hexdigest()
    target=max(150,min(spec.get('maxTargetQuads',1800),round(spec['target']*data['area']/trimesh.Trimesh(original['vertices'],original['faces'],process=False).area/50)*50))
    result=dict(model,**data)
    result.update(id=spec['id']+'--part-'+part_id,baseMeshId=spec['id'],partSource=part_id,sourceSha256=digest,originalSourceSha256=spec['sourceSha256'],partRecipe=identity,title='Source part',target=target,recommendedTarget=target,presets=[],previewUrl=None,requiresGuides=False,solver='surface-quads',featureLayout=True,description='A selected source region. Gold faces identify the repair cap; original coordinates are retained.',solverNotice='Generate this part independently. Repair caps are part of its working source. Assembly export keeps parts separate.')
    (directory/'source.obj').write_bytes(obj.encode());(directory/'selection.json').write_text(json.dumps(identity))
    temporary=directory/('mesh-'+__import__('uuid').uuid4().hex+'.tmp');temporary.write_text(json.dumps(result,allow_nan=False));temporary.replace(ready)
    return result

def supports_open_remesh(part):
    """Only original imported islands qualify; excluded cut regions keep their policy."""
    return (part.get('partRecipe',{}).get('recipe') or {}).get('kind')=='skp-connected-island' and not part.get('repair',{}).get('closed',True)

def load_part(part_id,mesh_id=None):
    if not isinstance(part_id,str) or not re.fullmatch('[a-f0-9]{64}',part_id):raise ValueError('Invalid prepared part ID.')
    directory=ROOT/'runs'/'parts'/part_id
    try:result=json.loads((directory/'mesh.json').read_text())
    except FileNotFoundError:raise ValueError('This prepared part is unavailable. Prepare it again from the original source.')
    if mesh_id is not None and result['baseMeshId']!=mesh_id:raise ValueError('The prepared part belongs to a different model.')
    if hashlib.sha256((ROOT/'assets/models'/(result['baseMeshId']+'.obj')).read_bytes()).hexdigest()!=result['originalSourceSha256']:raise ValueError('The original source has changed. Prepare the part again.')
    if hashlib.sha256((directory/'source.obj').read_bytes()).hexdigest()!=result['sourceSha256']:raise ValueError('The prepared source failed its integrity check.')
    result['canRemesh']=bool(result['repair']['closed'] or supports_open_remesh(result))
    if supports_open_remesh(result):
        result.update(solver='open-surface-quads',description='Original open source part. Boundaries are retained; no repair caps are added.',solverNotice='Generate this part with its original open boundaries. Your target and guides control its layout; results must pass boundary, surface and quality checks.')
    return result,directory

def split(spec,data):
    parent=data.get('partSource')
    if 'partSource' in data and (not isinstance(parent,str) or not re.fullmatch('[a-f0-9]{64}',parent)):raise ValueError('Invalid prepared parent part.')
    model=load_part(parent,spec['id'])[0] if parent else json.loads((ROOT/'assets/models'/(spec['id']+'.json')).read_text())
    if data.get('sourceSha256')!=spec['sourceSha256']:raise ValueError('The selection belongs to a different source revision.')
    if data.get('plane') is not None:
        plane=data['plane']
        if not isinstance(plane,dict) or type(plane.get('axis')) is not int or plane['axis'] not in (0,1,2) or type(plane.get('value')) not in (float,int) or not np.isfinite(plane['value']):raise ValueError('Choose an axis and a finite cut position.')
        parts=plane_split(model,plane['axis'],plane['value'])
        return {key:store_part(spec,parent=parent,geometry=part,recipe=dict(plane=plane,side=key)) for key,part in zip(('selected','remainder'),parts)}
    selected=indices(data.get('selectedFaces'),len(model['faces']))
    if len(selected)==len(model['faces']):raise ValueError('Select part of the active region, leaving a nonempty remainder.')
    remainder=sorted(set(range(len(model['faces'])))-set(selected))
    if type(data.get('exclude',False)) is not bool:raise ValueError('Exclusion must be a boolean.')
    return dict(selected=store_part(spec,selected,parent=parent,open_region=data.get('exclude',False)),remainder=store_part(spec,remainder,parent=parent))

def plane_split(model,axis,value):
    mesh=trimesh.Trimesh(model['vertices'],model['faces'],process=False)
    if not mesh.is_watertight:raise ValueError('Plane splitting requires a closed working part.')
    if not mesh.bounds[0,axis]+1e-7<value<mesh.bounds[1,axis]-1e-7:raise ValueError('Place the cut inside the active part.')
    output=[]
    for sign in (1,-1):
        part=trimesh.intersections.slice_mesh_plane(mesh,np.eye(3)[axis]*sign,np.eye(3)[axis]*value,cap=True,engine='triangle')
        if not part.is_watertight or not part.is_winding_consistent or np.any(part.area_faces<=0) or part.volume<=0:raise ValueError('This plane did not produce closed parts. Adjust the cut position.')
        if len(part.split(only_watertight=False))!=1:raise ValueError('The plane produces disconnected pieces. Adjust it to isolate one part.')
        cap=np.all(np.abs(part.vertices[part.faces][:,:,axis]-value)<1e-9,axis=1)
        order=np.r_[np.flatnonzero(~cap),np.flatnonzero(cap)];q=part.faces[order];start=int((~cap).sum())
        validate_cap_contacts(part.vertices,q,start)
        output.append(dict(vertices=part.vertices.tolist(),faces=q.tolist(),sourceFaceIds=[-1]*len(q),originalVertexIds=[-1]*len(part.vertices),area=float(part.area),stats=dict(triangles=len(q),quads=0,boundaryEdges=0),repair=dict(capFaceStart=start,capFaces=int(cap.sum()),closed=True,consistentWinding=True,plane=dict(axis=axis,value=value),newVerticesAtCut=True)))
    if abs(sum(trimesh.Trimesh(p['vertices'],p['faces'],process=False).volume for p in output)-mesh.volume)>max(1,abs(mesh.volume))*1e-7:raise ValueError('The split failed volume conservation.')
    return output
