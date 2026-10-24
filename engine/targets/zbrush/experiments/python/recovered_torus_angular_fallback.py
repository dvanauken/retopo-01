"""Recovered mode0 angular stage, nonsymmetric positive-weight component only.
This accepts preprocessed geometry/field channels, NOT original guide curves.
Includes reviewed mode102 local-failure full direct fallback and periodic direct refresh.
"""
import collections,math
import numpy as np
from scipy import sparse
from recovered_cholmod_reference_backend import solve_sparse as spsolve
from probe_transport_helpers import f32,dot,cross,oriented,rotation
from verify_angular_transport import normalize,perpendicular
from recovered_local_cg import correct

def solve(xyz,tri,normal,faceedges,offset,corners,directions,weights,max_callbacks=512,on_full=None):
 n=len(tri);ne=len(offset)-1
 if not n or len(weights)!=n or not np.all(weights>0):raise ValueError('Nonempty positive-weight component required')
 A=[];tau=[]
 for face,t in enumerate(tri):
  aa,_=normalize(f32(xyz[t[1]]-xyz[t[0]]));A.append(aa);projected=f32(directions[face]-f32(normal[face]*dot(directions[face],normal[face])));angle=float(f32(oriented(aa,projected,normal[face])))
  tau.append(angle-2*math.pi if angle>float(f32(math.pi)) else angle)
 A=np.asarray(A,dtype='f4');tau=np.asarray(tau);connection=np.zeros(ne,dtype='f4');pairs=[]
 for edge in range(ne):
  pair=(corners[offset[edge]:offset[edge+1]]//3).tolist();pairs.append(pair)
  if len(pair)!=2:continue
  i,j=pair;axis=cross(normal[j],normal[i])
  if float(dot(axis,axis))>=1e-7:axis,_=normalize(axis);M=rotation(axis,f32(oriented(normal[j],normal[i],axis)))
  elif dot(normal[i],normal[j])<0:M=rotation(perpendicular(normal[j]),f32(math.pi))
  else:M=np.eye(3,dtype='f4')
  moved=np.array([f32(float(M[k,1])*float(A[j,1])+float(M[k,0])*float(A[j,0])+float(M[k,2])*float(A[j,2])) for k in range(3)]);angle=f32(oriented(A[i],moved,normal[i]));connection[edge]=f32(angle+f32(-2*math.pi)) if angle>f32(math.pi) else angle
 weights=np.asarray(weights,dtype='f4').copy();anchors=weights>=f32(500)
 if not anchors.any():anchors[0]=True;weights[0]=f32(500)
 centers=(xyz[tri].astype('f8').sum(axis=1)/3).astype('f4');distance=np.full(n,np.finfo('f4').max,dtype='f4');parent=np.full(n,-1,dtype='i4');queue=collections.deque(np.flatnonzero(anchors).tolist());queued=np.zeros(n,dtype=bool);queued[list(queue)]=True;distance[list(queue)]=0
 while queue:
  face=queue.popleft();queued[face]=False
  for edge in faceedges[face]:
   pair=pairs[edge]
   if len(pair)!=2:continue
   other=pair[1] if pair[0]==face else pair[0];d=f32(centers[face]-centers[other]);length=np.sqrt(dot(d,d),dtype=f32);value=f32(distance[face]+length)
   if value<distance[other]:
    distance[other]=value;parent[other]=edge
    if not queued[other]:queue.append(other);queued[other]=True
 mask=np.ones(ne,dtype=bool);mask[parent[parent>=0]]=False
 for edge,pair in enumerate(pairs):
  if len(pair)!=2 or anchors[pair].all():mask[edge]=False
 if not np.isfinite(distance).all() or (distance==np.finfo('f4').max).any():raise ValueError('Input must be one connected traversable component')
 H=[{} for _ in range(n)];rhs=np.zeros(n);period=1.5707963705062866;factor=.6366197546520227;w=200.;quarter=np.zeros(ne,dtype='i4')
 def quant(v):return int(v+.5 if v>=0 else v-.5)
 def quarter32(v):v=f32(v);return int(f32(v+f32(.5) if v>=0 else v-f32(.5)))
 def add(i,j,v):H[i][j]=H[i].get(j,0)+v
 def add_edge(edge,k):
  i,j=pairs[edge];c=float(connection[edge])-k*period;add(i,i,w);add(j,j,w);add(i,j,-w);add(j,i,-w);rhs[i]+=w*c;rhs[j]-=w*c
 for edge,pair in enumerate(pairs):
  if len(pair)!=2:continue
  i,j=pair
  if anchors[pair].all():quarter[edge]=quarter32((float(connection[edge])+(tau[j]-tau[i]))*(2/math.pi))
  if not mask[edge]:add_edge(edge,int(quarter[edge]))
 for i in np.flatnonzero(anchors):add(i,i,float(weights[i]));rhs[i]+=float(weights[i])*tau[i]
 row=[];col=[];values=[]
 for i,terms in enumerate(H):
  for j,v in sorted(terms.items()):row.append(i);col.append(j);values.append(v)
 matrix=sparse.csr_matrix((values,(row,col)),shape=(n,n));x=np.asarray(spsolve(matrix,rhs),dtype='f8');active_edges=np.flatnonzero(mask).tolist();active_faces=np.flatnonzero((~anchors)&(weights>f32(1.9999999949504854e-6))).tolist();thresholds=.5235987755982988*np.array([.0001,.001,.01,.03,.07,.1,.25]);budget=.5235987755982988;history=[];localAttempts=0;localSuccesses=0;fullSolves=1;sinceFull=0;fullHistory=[]
 if on_full is not None:on_full(0,H,rhs,x)
 for iteration in range(max_callbacks):
  ebins=[[] for _ in range(8)];fbins=[[] for _ in range(8)];eq={};fq={};ee={};fe={}
  for edge in active_edges:
   i,j=pairs[edge];v=(x[j]+(float(connection[edge])-x[i]))*factor;k=quant(v);error=abs(v-k);eq[edge]=k;ee[edge]=error;ebins[int(np.searchsorted(thresholds,error,side='right'))].append(edge)
  for face in active_faces:
   v=(x[face]-tau[face])*factor;k=quant(v);error=abs(v-k);fq[face]=k;fe[face]=error;fbins[int(np.searchsorted(thresholds,error,side='right'))].append(face)
  if iteration==0:
   for i in np.flatnonzero(anchors):
    value=x[i]
    for j in list(H[i]):
     if i==j:continue
     rhs[j]-=H[j].get(i,0)*value;H[j].pop(i,None)
    H[i]={int(i):1.};rhs[i]=value
  selected_edges=[];cumulative=0.
  for bucket in ebins:
   error=sum(ee[e] for e in bucket)
   if cumulative+error<=budget:selected_edges.extend(bucket);cumulative+=error;continue
   remaining=bucket.copy()
   while remaining:
    edge=min(remaining,key=lambda e:ee[e]);cumulative+=ee[edge]
    if cumulative>budget:
     if not selected_edges:selected_edges.append(edge)
     break
    selected_edges.append(edge);remaining.remove(edge)
   break
  selected_faces=[];cumulative=0.
  for bucket in fbins:
   selected_faces.extend(bucket);cumulative+=sum(fe[f] for f in bucket)
   if cumulative>2*budget:break
  changed=[]
  for edge in selected_edges:add_edge(edge,eq[edge]);changed.extend(pairs[edge])
  for face in selected_faces:add(face,face,1.);rhs[face]+=fq[face]*period+tau[face];changed.append(face)
  taken=set(selected_edges);active_edges=[e for e in active_edges if e not in taken];taken=set(selected_faces);active_faces=[f for f in active_faces if f not in taken];seeds=list(dict.fromkeys(changed))[::-1]
  if seeds:
   sinceFull+=1;periodic=sinceFull%250==0
   if not periodic:
    localAttempts+=1;update=correct([sorted(row.items()) for row in H],x,rhs,seeds)
    if update['success']:localSuccesses+=1;x=update['values']
   if periodic or not update['success']:
    fullHistory.append(dict(iteration=iteration,localAttempts=localAttempts,localSuccesses=localSuccesses,previousFullSolves=fullSolves,periodic=periodic));rows=[];columns=[];values=[]
    for i,row in enumerate(H):
     for j,value in row.items():rows.append(i);columns.append(j);values.append(value)
    matrix=sparse.csr_matrix((values,(rows,columns)),shape=(n,n));x=np.asarray(spsolve(matrix,rhs),dtype='f8');fullSolves+=1;sinceFull=0
    if on_full is not None:on_full(fullSolves-1,H,rhs,x)
  history.append(dict(iteration=iteration,edges=len(selected_edges),faces=len(selected_faces),remainingEdges=len(active_edges),remainingFaces=len(active_faces)))
  if not seeds or (not active_edges and not active_faces):break
 else:raise RuntimeError('Bounded callback limit reached without native-style completion')
 theta=x.astype('f4')
 for edge,pair in enumerate(pairs):
  if len(pair)==2:
   i,j=pair;quarter[edge]=quarter32((float(connection[edge])+(float(theta[j])-float(theta[i])))*(2/math.pi))
 return dict(angles=theta,quarterTransitions=quarter,callbackHistory=history,fullSolveHistory=fullHistory,localAttempts=localAttempts,localSuccesses=localSuccesses,fullSolves=fullSolves,targetAngles=tau,connections=connection,deferredEdges=mask)
