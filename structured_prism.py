"""Guide-directed periodic quad grids on detected convex prismatic annuli.

Geometry-class recognition, not an asset ID or stored-output lookup. Polygon
corners, physical seams and both cap holes are preserved; all cells are quads
from the start. No triangle pairing / midpoint conversion is used.
"""
import math,itertools,hashlib
from pathlib import Path
import numpy as np
from quad_quality import measure

TAU=2*np.pi
def cross2(a,b):return a[...,0]*b[...,1]-a[...,1]*b[...,0]

def _loops(v,f,face_ids,origin,u,w):
 edges={}
 for fi in face_ids:
  row=f[fi]
  for a,b in zip(row,np.roll(row,-1)):
   key=tuple(sorted((int(a),int(b))))
   if key in edges:edges[key]=None
   else:edges[key]=(int(a),int(b))
 follow=dict(e for e in edges.values() if e is not None);visited=set();loops=[]
 for seed in sorted(follow):
  if seed in visited:continue
  loop=[];i=seed
  while i not in visited:loop.append(i);visited.add(i);i=follow[i]
  if i!=seed:raise NotImplementedError('Pinched cap loop')
  q=np.column_stack(((v[loop]-origin)@u,(v[loop]-origin)@w));keep=[]
  for j in range(len(q)):
   a=q[j]-q[j-1];b=q[(j+1)%len(q)]-q[j]
   if abs(cross2(a,b))>1e-6*np.linalg.norm(a)*np.linalg.norm(b):keep.append(j)
  q=q[keep]
  if len(q)<3:raise NotImplementedError('Degenerate cap outline')
  if np.sum(cross2(q,np.roll(q,-1,axis=0)))<0:q=q[::-1]
  loops.append(q)
 return loops

def detect(vertices,triangles):
 from planar import decompose
 v=np.asarray(vertices,float);f=np.asarray(triangles,int);domain=decompose(v,f);charts=domain['charts'];candidate=[]
 for i,c in enumerate(charts):
  n=c['normal'];main=int(np.argmax(abs(n)))
  if n[main]<0:continue
  loops=_loops(v,f,c['faces'],c['origin'],c['axis'],c['other'])
  if len(loops)!=2:continue
  opposite=[j for j,b in enumerate(charts) if n@b['normal']<-1+1e-9]
  for j in opposite:
   other=_loops(v,f,charts[j]['faces'],c['origin'],c['axis'],c['other'])
   if len(other)==2:candidate.append((c['area'],i,j,loops,other))
 if not candidate:raise NotImplementedError('Source is not a closed prismatic annulus')
 _,top,bottom,loops,other=max(candidate,key=lambda x:x[0]);c=charts[top];n=c['normal'];u=c['axis'];w=c['other'];origin=c['origin'];height=float((origin-charts[bottom]['origin'])@n)
 if height<=0:raise NotImplementedError('Invalid extrusion height')
 loops.sort(key=lambda q:abs(np.sum(cross2(q,np.roll(q,-1,axis=0)))));inner,outer=loops
 for q in loops:
  delta=np.roll(q,-1,axis=0)-q
  if np.any(cross2(delta,np.roll(delta,-1,axis=0))<-1e-10):raise NotImplementedError('Nonconvex annular outlines require general chart meshing')
 for q in loops:
  if not any(len(q)==len(r) and max(np.min(np.linalg.norm(q[:,None]-r[None],axis=2),axis=1))<domain['epsilon'] for r in other):raise NotImplementedError('End caps are not coincident extruded outlines')
 center=inner.mean(axis=0);inner=inner-center;outer=outer-center;base=origin+center[0]*u+center[1]*w-height*n
 for q in [inner,outer]:
  delta=np.roll(q,-1,axis=0)-q
  if np.any(cross2(delta,-q)<=0):raise NotImplementedError('Annular center is not strictly inside both outlines')
 angular=np.sort(np.mod(np.concatenate([np.arctan2(q[:,1],q[:,0]) for q in [inner,outer]]),TAU));mandatory=[]
 for a in angular:
  if not mandatory or a-mandatory[-1]>1e-5:mandatory.append(float(a))
 if len(mandatory)>1 and mandatory[0]+TAU-mandatory[-1]<1e-5:mandatory.pop()
 d={'base':base,'u':u,'v':w,'normal':n,'height':height,'inner':inner,'outer':outer,'mandatory':np.asarray(mandatory),'area':domain['totalArea'],'span':domain['span'],'epsilon':domain['epsilon'],'sourceVertices':len(v),'sourceTriangles':len(f)}
 # Every source vertex must lie on a cap or one of the extruded outlines.
 local=np.column_stack(((v-base)@u,(v-base)@w,(v-base)@n));angle=np.arctan2(local[:,1],local[:,0]);radius=np.linalg.norm(local[:,:2],axis=1);ri=_radius(inner,angle);ro=_radius(outer,angle)
 interior=(local[:,2]>1e-7)&(local[:,2]<height-1e-7)
 if np.any(np.minimum(abs(radius[interior]-ri[interior]),abs(radius[interior]-ro[interior]))>1e-7*d['span']):raise NotImplementedError('Source side walls are not straight extrusions')
 return d

def _radius(polygon,angle):
 direction=np.stack([np.cos(angle),np.sin(angle)],axis=-1);a=polygon;edge=np.roll(a,-1,axis=0)-a;den=cross2(direction[...,None,:],edge)
 t=np.divide(cross2(a,edge),den,out=np.full_like(den,np.nan),where=abs(den)>1e-14);s=np.divide(cross2(a,direction[...,None,:]),den,out=np.full_like(den,np.nan),where=abs(den)>1e-14)
 t=np.where((t>0)&(s>=-1e-8)&(s<=1+1e-8),t,np.inf);result=np.min(t,axis=-1)
 if not np.isfinite(result).all():raise NotImplementedError('A ray does not cross the convex outline')
 return result

def _profile(theta,values):
 theta=np.unwrap(theta)
 if theta[-1]<theta[0]:theta=theta[::-1];values=values[::-1]
 covered=float(theta.max()-theta.min());periodic=covered>5.0
 if periodic:
  count=min(8,max(2,len(theta)//12));columns=[np.ones(len(theta))];penalty=[0.]
  for k in range(1,count+1):columns.extend([np.cos(k*theta),np.sin(k*theta)]);penalty.extend([len(theta)*.04*(k/count)**4]*2)
  matrix=np.array(columns).T;coef=np.linalg.solve(matrix.T@matrix+np.diag(penalty),matrix.T@values)
  def evaluate(angle,base):
   out=np.ones_like(angle)*coef[0]
   for k in range(1,count+1):out+=coef[2*k-1]*np.cos(k*angle)+coef[2*k]*np.sin(k*angle)
   return out
 else:
  order=np.argsort(theta);x=theta[order];y=values[order];center=.5*(x[0]+x[-1])
  def evaluate(angle,base):
   a=center+np.angle(np.exp(1j*(angle-center)));out=np.interp(a,x,y);distance=np.maximum(x[0]-a,np.maximum(a-x[-1],0));blend=np.exp(-(distance/.3)**2);return out*blend+np.asarray(base)*(1-blend)
 return {'evaluate':evaluate,'coverageRadians':covered,'periodicContinuation':periodic,'mean':float(np.mean(values)),'samples':len(values)}

def _guides(d,curves):
 contours={'top':[],'bottom':[],'outer':[],'inner':[]};spokes={'top':[],'bottom':[],'outer':[],'inner':[]};diagnostics=[]
 for ci,curve in enumerate(curves):
  p=np.asarray(curve,float)-d['base'];q=np.column_stack((p@d['u'],p@d['v'],p@d['normal']));angle=np.arctan2(q[:,1],q[:,0]);radius=np.linalg.norm(q[:,:2],axis=1);ri=_radius(d['inner'],angle);ro=_radius(d['outer'],angle);t=(radius-ri)/(ro-ri);labels=[]
  for j in range(len(q)):
   if abs(q[j,2]-d['height'])<1e-5*d['span']:label='top'
   elif abs(q[j,2])<1e-5*d['span']:label='bottom'
   elif abs(t[j])<1e-5:label='inner'
   elif abs(t[j]-1)<1e-5:label='outer'
   else:raise NotImplementedError('Guide sample is not on the recognized prism surface')
   labels.append(label)
  start=0
  while start<len(q)-1:
   end=start+1
   while end<len(q) and labels[end]==labels[start]:end+=1
   ids=np.arange(start,end);label=labels[start]
   if len(ids)>=2:
    phi=np.unwrap(angle[ids]);span=float(np.ptp(phi));vertical=t[ids] if label in ('top','bottom') else q[ids,2]/d['height'];cross_span=float(np.ptp(vertical))
    if span>.35 and span>cross_span*2:
     value=radius[ids] if label in ('top','bottom') else q[ids,2];profile=_profile(angle[ids],value);profile.update(curve=ci,label=label,meanFraction=float(np.mean(vertical)),sourcePoints=np.asarray(curve)[ids]);contours[label].append(profile);kind='contour'
    elif cross_span>.12 and span<1.0:
     order=np.argsort(vertical);spokes[label].append({'curve':ci,'label':label,'angle':float(np.mean(phi)),'fraction':vertical[order],'angles':phi[order]});kind='spoke'
    else:raise NotImplementedError('Guide needs a clear contour or radial/axial flow for this structured surface class')
    diagnostics.append({'curve':ci,'surface':label,'kind':kind,'samples':len(ids),'angularSpan':span,'crossSpan':cross_span})
   start=end
 return contours,spokes,diagnostics

def _angles(d,count,spokes):
 mandatory=list(d['mandatory'])
 for items in spokes.values():
  for p in items:
   a=p['angle']%TAU
   if min(abs(np.angle(np.exp(1j*(a-np.asarray(mandatory))))))>.10:mandatory.append(a)
 mandatory=np.sort(mandatory);gaps=np.diff(np.r_[mandatory,mandatory[0]+TAU]);counts=np.maximum(1,np.floor(count*gaps/TAU).astype(int))
 while counts.sum()<count:counts[int(np.argmax(count*gaps/TAU-counts))]+=1
 while counts.sum()>count and np.any(counts>1):counts[int(np.argmax(np.where(counts>1,counts-count*gaps/TAU,-1e9)))]-=1
 return np.concatenate([np.linspace(a,a+gap,int(n),endpoint=False) for a,gap,n in zip(mandatory,gaps,counts)])

def _slots(count,profiles,slots=None):
 profiles=sorted(profiles,key=lambda p:p['meanFraction'])
 if len(profiles)>=count:raise ValueError('Too many guide contours for radial/axial allocation')
 if slots is None:
  slots=[]
  for k,p in enumerate(profiles):slots.append(int(np.clip(round(p['meanFraction']*count),k+1,count-(len(profiles)-k))))
  for j in range(1,len(slots)):slots[j]=max(slots[j],slots[j-1]+1)
 return slots

def _rows(angle,low,high,count,profiles,slots=None):
 low=np.broadcast_to(low,angle.shape);high=np.broadcast_to(high,angle.shape);anchors={0:low,count:high};profiles=sorted(profiles,key=lambda p:p['meanFraction']);slots=_slots(count,profiles,slots)
 for p,j in zip(profiles,slots):
  base=low+(high-low)*j/count;target=p['evaluate'](angle,base);margin=(high-low)*.035
  anchors[j]=np.clip(target,low+margin*j,high-margin*(count-j))
 order=sorted(anchors)
 if any(np.any(anchors[b]-anchors[a]<1e-7) for a,b in zip(order[:-1],order[1:])):raise ValueError('Contour guide ordering crosses in this parameterization')
 rows=[]
 for j in range(count+1):
  a=max(k for k in order if k<=j);b=min(k for k in order if k>=j)
  rows.append(anchors[a] if a==b else anchors[a]+(anchors[b]-anchors[a])*(j-a)/(b-a))
 return np.array(rows)

def _build(d,angle,nz,nr,contours,spokes,cap_slot=None):
 count=len(angle);ri=_radius(d['inner'],angle);ro=_radius(d['outer'],angle);vertices=[];faces=[];lookup={};guide_paths=[]
 def add(uv,z):
  uv=np.asarray(uv)
  for outline in [d['inner'],d['outer']]:
   distance=np.linalg.norm(outline-uv,axis=1);nearest=int(np.argmin(distance))
   if distance[nearest]<1e-6*d['span']:uv=outline[nearest];break
  p=d['base']+uv[0]*d['u']+uv[1]*d['v']+z*d['normal'];key=tuple(np.round(p/d['span'],11))
  if key not in lookup:lookup[key]=len(vertices);vertices.append(p)
  return lookup[key]
 for label,z,reverse in [('top',d['height'],False),('bottom',0.,True)]:
  slot=[cap_slot] if cap_slot and len(contours[label])==1 else None;radial=_rows(angle,ri,ro,nr,contours[label],slot);ids=[]
  for j,row in enumerate(radial):
   phi=angle.copy();fraction=j/nr
   for guide in spokes[label]:
    index=int(np.argmin(abs(np.angle(np.exp(1j*(angle-guide['angle']))))));desired=float(np.interp(fraction,guide['fraction'],guide['angles']));delta=float(np.angle(np.exp(1j*(desired-angle[index]))));phi[index]+=delta*np.sin(np.pi*fraction)
   if np.any(np.diff(np.r_[phi,phi[0]+TAU])<=.01):raise ValueError('Crossing spoke guides invert angular ordering')
   # Re-evaluate outline bounds at warped columns; preserve exact seams at j=0/nr.
   frac=(row-ri)/(ro-ri);rad=_radius(d['inner'],phi)+frac*(_radius(d['outer'],phi)-_radius(d['inner'],phi));ids.append([add([r*np.cos(a),r*np.sin(a)],z) for r,a in zip(rad,phi)])
  for j in range(nr):
   for i in range(count):
    k=(i+1)%count;f=[ids[j][i],ids[j+1][i],ids[j+1][k],ids[j][k]];faces.append(f[::-1] if reverse else f)
  for profile,row in zip(sorted(contours[label],key=lambda p:p['meanFraction']),_slots(nr,contours[label],slot)):
   guide_paths.append({'curve':profile['curve'],'surface':label,'vertices':ids[row]+[ids[row][0]],'sourcePoints':profile['sourcePoints']})
 for label,radius,reverse in [('outer',ro,False),('inner',ri,True)]:
  heights=_rows(angle,0.,d['height'],nz,contours[label]);ids=[]
  for j,row in enumerate(heights):
   fraction=j/nz;phi=angle.copy()
   for guide in spokes[label]:
    index=int(np.argmin(abs(np.angle(np.exp(1j*(angle-guide['angle']))))));desired=float(np.interp(fraction,guide['fraction'],guide['angles']));delta=float(np.angle(np.exp(1j*(desired-angle[index]))));phi[index]+=delta*np.sin(np.pi*fraction)
   rad=_radius(d[label],phi);ids.append([add([r*np.cos(a),r*np.sin(a)],z) for r,a,z in zip(rad,phi,row)])
  for j in range(nz):
   for i in range(count):
    k=(i+1)%count;f=[ids[j][i],ids[j][k],ids[j+1][k],ids[j+1][i]];faces.append(f[::-1] if reverse else f)
  for profile,row in zip(sorted(contours[label],key=lambda p:p['meanFraction']),_slots(nz,contours[label])):
   guide_paths.append({'curve':profile['curve'],'surface':label,'vertices':ids[row]+[ids[row][0]],'sourcePoints':profile['sourcePoints']})
 return np.asarray(vertices),faces,guide_paths

def _path_fit(v,paths):
 reports=[]
 for path in paths:
  p=np.asarray(path['sourcePoints']);p=p[np.linspace(0,len(p)-1,min(129,len(p))).astype(int)];q=v[path['vertices']];a=q[:-1];delta=np.diff(q,axis=0);length2=np.sum(delta*delta,axis=1);t=np.clip(np.sum((p[:,None]-a)*delta,axis=2)/np.maximum(length2,1e-30),0,1);dist=np.linalg.norm(p[:,None]-a-t[:,:,None]*delta,axis=2);nearest=np.argmin(dist,axis=1);distance=dist[np.arange(len(p)),nearest];tangent=np.gradient(p,axis=0);unit_t=tangent/np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-30);unit_e=delta/np.maximum(np.linalg.norm(delta,axis=1)[:,None],1e-30);angle=np.degrees(np.arccos(np.clip(abs(np.sum(unit_t*unit_e[nearest],axis=1)),0,1)))
  reports.append({'curve':path['curve'],'surface':path['surface'],'vertexIds':path['vertices'],'closedCycle':path['vertices'][0]==path['vertices'][-1],'samples':len(p),'p95Distance':float(np.percentile(distance,95)),'maxDistance':float(distance.max()),'p95TangentAngleDegrees':float(np.percentile(angle,95))})
 return reports

def construct(vertices,triangles,curves,*,target=500):
 d=detect(vertices,triangles);contours,spokes,guide_diagnostics=_guides(d,curves);base=len(d['mandatory']);candidates=[];rejected=[]
 # Search count allocation and the guide's radial row instead of accepting a
 # large count overshoot or inheriting arbitrary source triangulation density.
 for per_sector in range(1,10):
  angle=_angles(d,base*per_sector,spokes);count=len(angle)
  for nr in range(max(1,1+max(len(contours['top']),len(contours['bottom']))),7):
   desired=target/(2*count)-nr
   for nz in sorted(set([max(1,int(np.floor(desired))),max(1,int(np.ceil(desired)))])):
    if nz<=max(len(contours['outer']),len(contours['inner'])):continue
    total=2*count*(nr+nz)
    if abs(total-target)>.16*target:continue
    choices=range(1,nr) if max(len(contours['top']),len(contours['bottom']))==1 else [None]
    for slot in choices:
     try:v,f,paths=_build(d,angle,nz,nr,contours,spokes,slot);q=measure(v,f,target);fit=_path_fit(v,paths)
     except ValueError as error:rejected.append(str(error));continue
     # Shape-first allocation with count as a bounded secondary objective.
     cost=2*(max(0,.7-q['scaledJacobianP05']))**2+.12*q['edgeRatioP95']+.06*q['edgeRatioMax']+.25*q['edgeLengthCV']+.5*q['targetRelativeError']+.03*q['adjacentAreaRatioP95']
     h=math.sqrt(d['area']/target)
     if fit:cost+=3*max(p['p95Distance'] for p in fit)/h+.6*max(p['p95TangentAngleDegrees'] for p in fit)/90
     if not q['passed']:cost+=10+len(q['failures'])
     candidates.append((cost,v,f,q,{'circumferential':count,'height':nz,'radial':nr,'guideRow':slot},fit))
 if not candidates:raise ValueError('No valid structured allocation for these guides and density: '+repr(rejected[:3])+'; corners='+str(len(d['mandatory'])))
 cost,v,f,q,allocation,fit=min(candidates,key=lambda x:x[0]);
 if not q['passed']:raise ValueError('Guide/density cannot satisfy quad shape limits: '+', '.join(q['failures']))
 from features import output_creases
 meta={'backend':'engineering-structured-prismatic-annulus','nativeComparisonPerformed':False,'generalAlgorithmRecovered':False,'target':target,'guideMode':2,'outputCreases':output_creases(v,f),'sourceHashes':{str(Path(__file__).resolve()):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'quadQuality':q,'guidePaths':fit,'structuredPolicy':{'recognition':'Opposite congruent planar annular caps, convex nested outlines, straight extruded source walls; actual source geometry only. No model ID or cached output lookup.','allocation':allocation,'candidateCount':len(candidates),'objective':cost,'guideClassification':guide_diagnostics,'guideFitting':'Smoothed periodic radial/axial profiles or partial-profile continuation; radial/axial spokes bend interior columns. Guide data is retained unchanged.','regularGrid':'Continuous circumferential cycles; axial wall strips; radial cap strips; globally shared boundary vertices; all quads constructed directly.','sourceCornerAngles':d['mandatory'].tolist(),'frame':{'origin':d['base'].tolist(),'u':d['u'].tolist(),'v':d['v'].tolist(),'normal':d['normal'].tolist(),'height':d['height']}},'limitations':['Geometry-class-specific structured mesher, not general native retopology recovery.','Contour ordering changes, nonconvex holes, intersecting constraints and arbitrary multiple holes need another layout strategy.','Guides influence regular grid paths through smoothing/continuation; exact every-sample interpolation is not promised.']}
 return v,f,meta
