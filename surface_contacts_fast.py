"""Compiled form of the reference quad contact predicates (no fast-math)."""
import numpy as np
from numba import njit
from rtree.index import Index,Property


@njit(cache=True)
def inside(point,triangle,normal,eps):
    for i in range(3):
        edge=triangle[(i+1)%3]-triangle[i]
        if np.dot(np.cross(edge,point-triangle[i]),normal)<-eps*np.linalg.norm(edge):return False
    return True


@njit(cache=True)
def triangle_contacts(a,b,eps):
    points=np.zeros((24,3));count=0
    na=np.cross(a[1]-a[0],a[2]-a[0]);nb=np.cross(b[1]-b[0],b[2]-b[0])
    la=np.linalg.norm(na);lb=np.linalg.norm(nb)
    if min(la,lb)<eps*eps:return points,0
    na/=la;nb/=lb
    da=np.empty(3);db=np.empty(3)
    for i in range(3):da[i]=np.dot(a[i]-b[0],nb);db[i]=np.dot(b[i]-a[0],na)
    if da.min()>eps or da.max()<-eps or db.min()>eps or db.max()<-eps:return points,0
    if np.max(np.abs(da))<=eps and np.max(np.abs(db))<=eps:
        points[:3]=a;count=3
        for i in range(3):
            edge=b[(i+1)%3]-b[i];inward=np.cross(nb,edge);inward/=np.linalg.norm(inward)
            clipped=np.zeros((24,3));n=0
            for j in range(count):
                previous=points[(j-1)%count];point=points[j]
                dp=np.dot(previous-b[i],inward);dc=np.dot(point-b[i],inward)
                if (dp>=-eps)!=(dc>=-eps):
                    t=min(1.,max(0.,dp/(dp-dc)));clipped[n]=previous+t*(point-previous);n+=1
                if dc>=-eps:clipped[n]=point;n+=1
            points=clipped;count=n
            if not count:break
        return points,count
    for which in range(2):
        first=a if which==0 else b;other=b if which==0 else a;normal=nb if which==0 else na
        for i in range(3):
            p=first[i];q=first[(i+1)%3];start=np.dot(p-other[0],normal);change=np.dot(q-p,normal)
            if abs(start)<=eps and inside(p,other,normal,eps):points[count]=p;count+=1
            if abs(change)>eps:
                t=-start/change;margin=eps/max(eps,np.linalg.norm(q-p));point=p+min(1.,max(0.,t))*(q-p)
                if -margin<=t<=1+margin and inside(point,other,normal,eps):points[count]=point;count+=1
    return points,count


@njit(cache=True)
def on_boundary(point,v,common,shared_edges,eps):
    for i in common:
        if np.linalg.norm(point-v[i])<=eps:return True
    for a,b in shared_edges:
        delta=v[b]-v[a];den=np.dot(delta,delta)
        if den>eps*eps:
            t=min(1.,max(0.,np.dot(point-v[a],delta)/den))
            if np.linalg.norm(point-v[a]-t*delta)<=eps:return True
    return False


@njit(cache=True)
def check_pairs(v,q,pairs,both_diagonals):
    patterns=np.array([[0,1,2],[0,2,3],[1,2,3],[1,3,0]])
    result=np.zeros(len(pairs),np.int8);eps=1e-9
    for pair_index in range(len(pairs)):
        a,b=pairs[pair_index];fa=q[a];fb=q[b]
        common=np.array([int(x) for x in fa if np.any(fb==x)],np.int64)
        edges=np.empty((4,2),np.int64);edge_count=0
        for i in range(4):
            x,y=fa[i],fa[(i+1)%4]
            for j in range(4):
                u,w=fb[j],fb[(j+1)%4]
                if (x==u and y==w) or (x==w and y==u):edges[edge_count]=np.array([x,y]);edge_count+=1;break
        shared_edges=edges[:edge_count]
        count_patterns=4 if both_diagonals else 2
        for i in range(count_patterns):
            if result[pair_index]:break
            for j in range(count_patterns):
                ia=fa[patterns[i]];ib=fb[patterns[j]];ta=v[ia];tb=v[ib]
                # Reference exclusions: non-coplanar triangles sharing an
                # actual boundary edge can meet only along that boundary.
                na=np.cross(ta[1]-ta[0],ta[2]-ta[0]);nb=np.cross(tb[1]-tb[0],tb[2]-tb[0])
                la=np.linalg.norm(na);lb=np.linalg.norm(nb)
                if la<=eps*eps or lb<=eps*eps:continue
                na/=la;nb/=lb
                da=np.array([np.dot(point-tb[0],nb) for point in ta]);db=np.array([np.dot(point-ta[0],na) for point in tb])
                if da.min()>eps or da.max()<-eps or db.min()>eps or db.max()<-eps:continue
                tri_common=np.array([int(x) for x in ia if np.any(ib==x)],np.int64)
                coplanar=np.max(np.abs(da))<=eps and np.max(np.abs(db))<=eps
                if len(tri_common)==2 and not coplanar:
                    shared=False
                    for x,y in shared_edges:
                        if (x==tri_common[0] and y==tri_common[1]) or (x==tri_common[1] and y==tri_common[0]):shared=True
                    if shared:continue
                if len(tri_common)==1:
                    if (np.sum(np.abs(da)<=eps)==1 and (da.min()>=-eps or da.max()<=eps)) or (np.sum(np.abs(db)<=eps)==1 and (db.min()>=-eps or db.max()<=eps)):continue
                points,n=triangle_contacts(ta,tb,eps)
                if not n:continue
                bad=len(common)==0
                mean=points[:n].sum(axis=0)/n
                if not bad and not on_boundary(mean,v,common,shared_edges,eps*4):bad=True
                for k in range(n):
                    if bad:break
                    if not on_boundary(points[k],v,common,shared_edges,eps*4) or not on_boundary((points[k]+points[(k+1)%n])*.5,v,common,shared_edges,eps*4):bad=True
                if bad:result[pair_index]=2 if len(common) else 1;break
    return result


def measure(vertices,faces,*,both_quad_diagonals=False):
    v=np.asarray(vertices,float);q=np.asarray(faces,np.int64)
    if q.ndim!=2 or q.shape[1]!=4:raise ValueError('Compiled contact checker expects quadrilaterals.')
    p=v[q];bounds=np.c_[p.min(1)-1e-9,p.max(1)+1e-9]
    tree=Index(((i,box,None) for i,box in enumerate(bounds)),properties=Property(dimension=3))
    pairs=np.asarray([(a,b) for a,box in enumerate(bounds) for b in tree.intersection(box) if b>a],np.int64).reshape(-1,2);tree.close()
    found=check_pairs(v,q,pairs,both_quad_diagonals)
    return dict(passed=not np.any(found),nonAdjacentIntersectingFacePairs=sorted(pairs[found==1].tolist()),adjacentIntersectingFacePairs=sorted(pairs[found==2].tolist()),
                quadDiagonalPolicy='all_pairings' if both_quad_diagonals else 'renderer_fan',
                scope='Compiled reference contact predicates, no fast-math; 1e-9 length tolerance, 4e-9 shared-boundary tolerance. Both quad diagonals with every mixed pairing when requested; separate topology and degeneracy checks.')
