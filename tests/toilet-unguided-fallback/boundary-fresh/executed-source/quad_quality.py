"""Explicit surface-quad quality checks, separate from topology closure.

Corner Jacobian and angle conventions follow standard quadrilateral quality
definitions. edgeRatio is deliberately named as a simple edge-length ratio,
not mislabeled as a particular package's aspect-ratio implementation.
"""
import numpy as np
from collections import defaultdict

def measure(vertices,faces,target=None):
 v=np.asarray(vertices,float);f=np.asarray(faces,int)
 if f.ndim!=2 or f.shape[1]!=4:return {'passed':False,'reason':'Quality checks require quadrilateral faces','quadOnly':False}
 p=v[f];e=np.roll(p,-1,axis=1)-p;length=np.linalg.norm(e,axis=2);normal=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])+np.cross(p[:,2]-p[:,0],p[:,3]-p[:,0]);norm=np.linalg.norm(normal,axis=1)
 n=normal/np.maximum(norm[:,None],1e-30);previous=-np.roll(e,1,axis=1);den=length*np.roll(length,1,axis=1)
 cosine=np.sum(previous*e,axis=2)/np.maximum(den,1e-30);angles=np.degrees(np.arccos(np.clip(cosine,-1,1)))
 # Outgoing edge crossed with the reversed incoming edge matches the polygon
 # normal on a convex, positively oriented corner; concavity stays signed.
 corner=np.sum(np.cross(e,previous)*n[:,None,:],axis=2)/np.maximum(den,1e-30)
 ratio=length.max(axis=1)/np.maximum(length.min(axis=1),1e-30)
 area=norm*.5;edges={};neighbors=defaultdict(set);incidence=defaultdict(list)
 for fi,row in enumerate(f):
  for j,(a,b) in enumerate(zip(row,np.roll(row,-1))):
   a,b=int(a),int(b);key=tuple(sorted((a,b)));edges[key]=float(length[fi,j]);neighbors[a].add(b);neighbors[b].add(a);incidence[key].append(fi)
 adjacent=[]
 for ids in incidence.values():
  if len(ids)==2:adjacent.append(max(area[ids[0]],area[ids[1]])/max(1e-30,min(area[ids[0]],area[ids[1]])))
 valence=np.array([len(neighbors[i]) for i in range(len(v))]);relative=abs(len(f)-target)/target if target else None
 summary={'quadOnly':True,'faces':len(f),'minimumAngleDegrees':float(angles.min()),'angleP05Degrees':float(np.percentile(angles,5)),'maximumAngleDegrees':float(angles.max()),'edgeRatioP95':float(np.percentile(ratio,95)),'edgeRatioMax':float(ratio.max()),'scaledJacobianMin':float(corner.min()),'scaledJacobianP05':float(np.percentile(corner,5)),'edgeLengthCV':float(np.std(list(edges.values()))/np.mean(list(edges.values()))),'adjacentAreaRatioP95':float(np.percentile(adjacent,95)) if adjacent else 1.,'valence4Fraction':float(np.mean(valence==4)),'irregularVertices':int(np.sum(valence!=4)),'targetRelativeError':relative}
 limits={'minimumAngleDegrees':30.,'edgeRatioP95':3.5,'edgeRatioMax':6.,'scaledJacobianMin':.45,'adjacentAreaRatioP95':4.,'targetRelativeError':.15}
 reasons=[]
 for key in ['minimumAngleDegrees','scaledJacobianMin']:
  if summary[key]<limits[key]:reasons.append(key+' below limit')
 for key in ['edgeRatioP95','edgeRatioMax','adjacentAreaRatioP95']:
  if summary[key]>limits[key]:reasons.append(key+' above limit')
 if relative is not None and relative>limits['targetRelativeError']:reasons.append('face count exceeds target tolerance')
 if np.any(norm<1e-14) or not np.isfinite(p).all():reasons.append('degenerate or nonfinite face')
 return dict(summary,passed=not reasons,failures=reasons,limits=limits,method='Signed corner scaled Jacobian relative to polygon area normal; 3D included corner angles; max/min edge ratio; adjacent polygon area ratio; unique-edge length CV; graph valence; actual count error. Separate from manifold/surface validation.')
