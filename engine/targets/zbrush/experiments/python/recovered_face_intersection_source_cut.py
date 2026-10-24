"""2567b0 bounded free-endpoint allocation, per-face coalescing and chord cuts.

Original segmented records are explicit inputs. Free interior path entries,
near boundary identity merges and general fallback policies remain guarded.
"""
import numpy as np
from recovered_mesh_topology import build
from recovered_closed_incident_cut_preparation import prepare
from recovered_closed_fractional_vertex_maps import fractional_closed
from recovered_boundary_multiple_cut import cut as boundary_cut
from recovered_face_planar_cut import cut as face_cut
from recovered_cut_guide_adjacency_repair import repair
from recovered_source_polygon_conversion import triangulate
F=np.float32

def constraints(positions,faces,segments):
    faces=np.asarray(faces,'<i4');count=len(positions);top=build(count,faces);edges=top['edges']
    relocated,paths,requests,diagnostic=prepare(positions,edges,segments)
    output=[p.copy() for p in relocated];all_ids=[];maps=[];starts=[];fractional=set()
    for p in paths:
        ids=[];closed=fractional_closed(p)
        if len(p['attributes']):raise NotImplementedError('Source cut attributes')
        for i,(point,edge,t) in enumerate(zip(p['points'],p['edges'],p['parameters'])):
            if edge==-1:
                if i not in (0,len(p['points'])-1):raise NotImplementedError('Free nonterminal guide point')
                vertex=len(output);output.append(point.copy())
            elif not 0<=edge<len(edges) or not 0<=t<=1:raise ValueError('Source edge/parameter range')
            elif t in (0,1):vertex=int(edges[int(edge),int(t)])
            elif closed and i==len(p['parameters'])-1:vertex=ids[0]
            else:
                key=(int(edge),F(t).tobytes())
                if key in fractional:raise NotImplementedError('Nonclosing repeated fractional allocation')
                fractional.add(key);vertex=len(output);output.append(point.copy())
            ids.append(vertex)
        all_ids.append(ids);indices=[i for i in range(len(ids)) if i==0 or ids[i]!=ids[i-1]]
        maps.append(np.asarray([ids[i] for i in indices],'<i4'));starts.append(np.asarray(indices,'<i4'))
    output=np.asarray(output,'<f4');records={}
    def scalar(path,index,face):
        edge=int(path['edges'][index]);t=float(path['parameters'][index]);tri=faces[face].tolist()
        if edge<0:return -1.
        a,b=map(int,edges[edge])
        if t in (0,1):
            vertex=a if t==0 else b
            if vertex not in tri:raise NotImplementedError('Interval endpoint not in face')
            return float(tri.index(vertex))
        for k,(x,y) in enumerate(zip(tri,tri[1:]+tri[:1])):
            if (x,y)==(a,b):s=k+t;return 0. if s==3 else s
            if (x,y)==(b,a):s=k+(1-t);return 0. if s==3 else s
        raise NotImplementedError('Interval source edge incidence')
    def add(face,s,t,a,b):
        if 0<=t<s:s,t,a,b=t,s,b,a
        records.setdefault(int(face),[]).append([s,t,int(a),int(b)])
    for path,ids in zip(paths,all_ids):
        for i,face in enumerate(path['faces']):
            face=int(face);a,b=ids[i:i+2]
            if face<0 or max(a,b)<count:continue
            if i>0 and face==int(path['faces'][i-1]) and path['edges'][i]>=0:
                edge=int(path['edges'][i]);neighbors=top['edgeCorners'][top['edgeCornerOffsets'][edge]:top['edgeCornerOffsets'][edge+1]]//3
                if len(neighbors)!=2:raise NotImplementedError('Fractional boundary incidence')
                other=next(int(f) for f in neighbors if f!=face);s=scalar(path,i,other);add(other,s,s,a,a)
            add(face,scalar(path,i,face),scalar(path,i+1,face),a,b)
    # Per-face free endpoint coalescing uses float subtraction/squared sum and
    # strict double1e-16. Boundary scalar1e-5 coalescing is explicitly guarded.
    representatives=np.arange(len(output),dtype='<i4');welds=[]
    for face in sorted(records):
        free=[];boundary=[]
        for s,t,a,b in records[face]:
            for value,vertex in [(s,a),(t,b)]:
                if value<0:
                    if vertex not in free:free.append(vertex)
                else:boundary.append((value,vertex))
        boundary.sort(key=lambda x:x[0])
        for (s,a),(t,b) in zip(boundary,boundary[1:]):
            if int(s)==int(t) and t-s<=1e-5 and min(a,b)>=count and a!=b:raise NotImplementedError('Near-boundary point identity coalescing')
        for i,a in enumerate(free):
            for b in free[i+1:]:
                if representatives[b]!=b:continue
                d=F(output[a]-output[b]);sq=F(F(d[0]*d[0]+d[1]*d[1])+d[2]*d[2])
                if float(sq)<1e-16:representatives[b]=representatives[a];welds.append(dict(face=face,source=b,destination=int(representatives[a]),squaredDistance=float(sq)))
    for rs in records.values():
        for r in rs:r[2]=int(representatives[r[2]]);r[3]=int(representatives[r[3]])
    #255910 removes redundant boundary arcs or retains their fractional point
    #as an equal-coordinate constraint, so the adjacent face shares that split.
    for face in list(records):
        if any(min(r[0],r[1])<0 for r in records[face]):continue
        cleaned=[];extra=[]
        for s,t,a,b in records[face]:
            if s==t:
                if a==b:cleaned.append([s,t,a,b])
            elif t<=int(s)+1 or (t==0 and int(s)==2):
                if s==int(s) and t==int(t):continue
                if s==int(s):cleaned.append([t,t,b,b])
                else:
                    cleaned.append([s,s,a,a])
                    if t!=int(t):extra.append([t,t,b,b])
            else:cleaned.append([s,t,a,b])
        records[face]=cleaned+extra
        if not records[face]:del records[face]
    maps=[representatives[m] for m in maps]
    return output,records,maps,starts,dict(originalCount=count,relocationRequests=requests,preparation=diagnostic,welds=welds,relocated=relocated)

def cut(positions,faces,segments):
    output,records,maps,starts,detail=constraints(positions,faces,segments);count=detail['originalCount'];polygons={};new=[]
    for face in sorted(records):
        rs=records[face];current=np.concatenate([output,np.asarray(new,'<f4').reshape(-1,3)])
        if any(min(r[0],r[1])<0 for r in rs):
            ps,extra,_=face_cut(np.asarray(faces[face],'<i4'),current,rs);ps=ps.tolist()
        else:ps,extra=boundary_cut(faces[face],current,rs)
        polygons[face]=ps;new.extend(extra)
    output=np.concatenate([output,np.asarray(new,'<f4').reshape(-1,3)])
    replacement=[list(map(int,f)) for i,f in enumerate(faces) if i not in polygons]
    for face in sorted(polygons):replacement.extend(polygons[face])
    triangles,_=triangulate(replacement,output)
    # Unreferenced appended points (e.g. welded duplicate free endpoints) are
    # removed in stable order; original source points keep their IDs.
    used=np.zeros(len(output),bool);used[:count]=True;used[triangles.ravel()]=True
    remap=np.cumsum(used,dtype='<i4')-1;removed=np.flatnonzero(~used).tolist()
    output=output[used];triangles=remap[triangles];maps=[remap[m] for m in maps]
    maps,repairs=repair(output,triangles,maps,count)
    return output,triangles.tolist(),maps,starts,dict(detail,guideRepairs=repairs,removedUnusedAppended=removed,constraints=records)
