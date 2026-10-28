"""Independent parent coverage and explicit guide-chain verification.

No final-quad or exact-predicate claim. Shapely union plus barycentric checks
detect holes/overlap that a summed-area-only check could hide.
"""
from pathlib import Path
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,hashlib,shutil,argparse
from collections import Counter,defaultdict
import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union
HERE=Path(__file__).resolve().parent

def verify(v,f,p,t,meta,curves):
    v,f,p,t=map(np.asarray,(v,f,p,t))
    extent=float(np.ptp(v,axis=0).max());tol=extent*1e-8
    groups=defaultdict(list)
    for i,parent in enumerate(meta['sourceOwners']):groups[parent].append(i)
    worst=dict(plane=0.,outside=0.,unionRelative=0.,overlapRelative=0.)
    defects=[]
    for i,tri in enumerate(f):
        q=v[tri];u=q[1]-q[0];u/=np.linalg.norm(u)
        n=np.cross(q[1]-q[0],q[2]-q[0]);n/=np.linalg.norm(n);basis=np.array([u,np.cross(n,u)]).T
        parent=Polygon((q-q[0])@basis)
        children=p[t[groups[i]]]
        if not len(children):defects.append(dict(face=i,reason='missing parent'));continue
        worst['plane']=max(worst['plane'],float(np.max(np.abs((children-q[0])@n))))
        polygons=[Polygon((c-q[0])@basis) for c in children]
        union=unary_union(polygons)
        outside=union.difference(parent).area
        missing=parent.symmetric_difference(union).area
        overlap=sum(poly.area for poly in polygons)-union.area
        worst['outside']=max(worst['outside'],outside)
        worst['unionRelative']=max(worst['unionRelative'],missing/max(parent.area,1e-20))
        worst['overlapRelative']=max(worst['overlapRelative'],overlap/max(parent.area,1e-20))
        if missing>max(parent.area*1e-6,tol**2) or overlap>max(parent.area*1e-6,tol**2):
            defects.append(dict(face=i,symmetricDifference=missing,overlap=overlap,area=parent.area))
    edge_set={tuple(sorted((int(a),int(b)))) for tri in t for a,b in zip(tri,np.roll(tri,-1))}
    guide_rows=[]
    for ci,curve in enumerate(curves):
        curve=np.asarray(curve);edges=np.asarray(meta['guideEdges'].get(str(ci),[]),dtype=int).reshape(-1,2)
        graph=defaultdict(set)
        for a,b in edges:graph[int(a)].add(int(b));graph[int(b)].add(int(a))
        seen=set();components=0
        for start in graph:
            if start in seen:continue
            components+=1;stack=[start]
            while stack:
                vtx=stack.pop()
                if vtx in seen:continue
                seen.add(vtx);stack.extend(graph[vtx]-seen)
        degrees=Counter(len(x) for x in graph.values())
        closed=np.linalg.norm(curve[0]-curve[-1])<=tol
        valid=components==1 and set(degrees)<=({2} if closed else {1,2}) and (closed or degrees[1]==2)
        valid &= all(tuple(sorted(e)) in edge_set for e in edges)
        # All submitted samples must attach to the actual retained guide edges.
        maximum=0.
        if not len(edges):maximum=float(extent)
        else:
            a=p[edges[:,0]];d=p[edges[:,1]]-a
            for q in curve:
                tt=np.clip(((q-a)*d).sum(axis=1)/(d*d).sum(axis=1),0,1)
                maximum=max(maximum,float(np.linalg.norm(q-a-tt[:,None]*d,axis=1).min()))
        valid &= maximum<=extent*1e-5+tol
        guide_rows.append(dict(curve=ci,passed=bool(valid),components=components,closed=bool(closed),degrees=dict(degrees),sampleMaxDistance=maximum,edges=len(edges)))
    checks=dict(originalVerticesFixed=bool(np.array_equal(v,p[:len(v)])),parentCount=len(groups)==len(f),
                inParentPlanes=worst['plane']<=tol,coverage=not defects,guides=all(r['passed'] for r in guide_rows))
    return dict(passed=all(checks.values()),checks=checks,worst=worst,coverageDefects=defects,guides=guide_rows,
                method='Per-parent plane residual, polygon union symmetric difference and overlap; original vertex equality; explicit guide edge incidence, component/degree checks and every authored sample distance.',
                tolerance=dict(plane=tol,areaRelative=1e-6,areaAbsolute=tol**2,guide=extent*1e-5+tol))

