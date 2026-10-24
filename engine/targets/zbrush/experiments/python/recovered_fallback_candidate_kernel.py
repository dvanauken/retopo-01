"""271a90 fallback candidate kernel; caller must select actual fallback faces.

This kernel computes fallback candidates only; valid-window caller overrides unused faces. The
historical NumPy powf approximation is separately qualified by numerical error.
"""
import math
import numpy as np
from verify_scale_selection import f32,dot,angle


def prepare(field,unordered_selection=False,native_arithmetic=False):
 normal=field['edgeField']['normals'];num=len(field['radii']);n=len(normal);ids=np.arange(n);base=field['controls']['anisotropy'];direction=field['directions'];mid=field['middle'];largest=field['largest'];threshold=field['candidateGate']['curvatureThreshold'];protected=(field['constraints']['flags']&12)!=0
 def literal(bits):return np.frombuffer(int(bits).to_bytes(4,'little'),'<f4')[0]
 lowAngle=literal(0x3edf66f3);highAngle=literal(0x3f860a92)
 limits={0x2b4:f32(math.sin(float(lowAngle))),0x2b8:f32(math.sin(float(f32(f32(highAngle+lowAngle)*f32(.5))))),0x2bc:f32(math.sin(float(highAngle)))}
 f=lambda offset:limits[offset]
 aniso=np.zeros_like(mid);np.divide(f32(abs(largest)-abs(mid)),abs(largest),out=aniso,where=largest!=0);best=np.full(len(ids),np.finfo('f4').max,dtype='f4');chosen=np.full(len(ids),-1,dtype='i4');costs=[];candidateCosts=[]
 for s in range(num):
  t=threshold[s];curv=largest[s];an=aniso[s]
  ac=np.where(an<f32(.3),f32(1),np.where(an<=f32(.7),f32(f32(1)-f32(f32(an-f32(.3))*f32(2.500000238418579))),f32(0)));ac=f32(ac+np.where(an<f32(.05),f32(2),f32(0)))
  lower=f32(t*f32(.2));half=f32(t*f32(.5))
  with np.errstate(divide='ignore',invalid='ignore'):
   cc=np.where(curv>=half,np.where(curv<=t,f32(f32(1.5)-f32(f32(f32(1.5)/f32(t-half))*f32(curv-half))),f32(0)),np.where((curv>=lower)&(curv<=half),f32(f32(4)-f32(f32(f32(2.5)/f32(half-lower))*f32(curv-lower))),f32(4)))
  gc=np.zeros(len(ids),dtype='f4');den=np.zeros(len(ids),dtype='f4')
  qualify=(an.astype('f8')>=.3)&(f32(cc+ac)<f32(1.5))
  for j in range(num):
   if j!=s:gc=f32(gc+np.where(qualify,angle(direction[s],direction[j]),f32(0)));den=f32(den+qualify.astype('f4'))
  with np.errstate(divide='ignore',invalid='ignore'):gc=np.where(f32(cc+ac)<f32(1.5),f32(f32(gc/den)*f32(.6366197466850281)),f32(1))
  pnormal=abs(dot(normal[ids],direction[s]));b4,b8,bc=f(0x2b4),f(0x2b8),f(0x2bc)
  penalty=np.where(pnormal>bc,f32(100),np.where(pnormal>b8,f32(f32(f32(f32(15)/f32(bc-b8))*f32(pnormal-b8))+f32(5)),np.where(pnormal>b4,f32(f32(f32(5)/f32(b8-b4))*f32(pnormal-b4)),f32(0))))
  factor=f32(f32(1.5)-f32(f32(s)/f32(num-1)))
  combined=f32(gc+f32(cc+ac)) if native_arithmetic else f32(f32(gc+cc)+ac)
  value=f32(f32(combined+penalty)*factor)
  if s==num-2:value=f32(value*f32(.5))
  elif s==num-1:value=f32(value*f32(.25))
  improves=(value<best)
  if unordered_selection:improves=improves|np.isnan(value)|np.isnan(best)
  accept=((curv>=lower)|(s==num-1))&improves;chosen[accept]=s;best[accept]=value[accept];costs.append(dict(scale=s,chosenAtStep=int(accept.sum())));candidateCosts.append(value.copy())
 if np.any(chosen<0):raise NotImplementedError('No-selection weighted eigenpair branch')
 live=chosen>=0;j=np.arange(n);wanted=direction[chosen,j].copy();wanted[protected]=field['constraints']['directions'][protected]
 sel=chosen;av=aniso[sel,j];cv=largest[sel,j];tv=threshold[sel];score=best;pn=abs(dot(normal,wanted))
 floor=f32(9.999999974752427e-7)
 aw=np.where(av<f32(.3),floor,np.where(av<base,f32(f32(f32(f32(.9)/f32(base-f32(.3)))*f32(av-f32(.3)))+f32(.1)),np.where(av<=1,f32(f32(f32(f32(59)/f32(f32(1)-base))*f32(av-base))+f32(1)),f32(60))))
 low=f32(tv*f32(.4));cw=np.where(cv<low,f32(.1),np.where(cv<=tv,f32(f32(f32(f32(59.900001525878906)/f32(tv-low))*f32(cv-low))+f32(.1)),f32(60)))
 gw=np.where((av>=f32(.3))&(cv>=f32(tv*f32(.2))),np.where(score<0,f32(60),np.where(score<=f32(.13962633907794952),f32(f32(60)-f32(score*f32(429.0021667480469))),f32(.1))),floor)
 powerInput=f32(f32(gw*aw)*cw)
 if native_arithmetic:weight=np.asarray([f32(math.pow(float(value),float(f32(.3330000042915344)))) for value in powerInput],dtype='f4')
 else:weight=np.power(powerInput,f32(.3330000042915344)).astype('f4')
 divisor=np.where(pn>bc,f32(1),np.where(pn>b8,f32(f32(f32(f32(990)/f32(bc-b8))*f32(pn-b8))+f32(10)),np.where(pn>b4,f32(f32(f32(f32(9)/f32(b8-b4))*f32(pn-b4))+f32(1)),f32(1))))
 weight=f32(weight/divisor);weight=np.where((av<f32(.1))|(cv<f32(tv*f32(.05)))|(pn>bc),floor,weight)
 weight=np.where(protected,f32(50000),weight).astype('f4')
 flags=field['constraints']['flags']|np.uint8(1)
 flags[(cv.astype(float)<tv.astype(float)*(2/3))&(av>f32(.5))]|=np.uint8(2)
 return dict(candidateCosts=np.asarray(candidateCosts),selected=chosen,directions=wanted,middle=mid[chosen,j],largest=largest[chosen,j],weights=weight,flags=flags,best=best,limits=np.asarray([limits[o] for o in [0x2b4,0x2b8,0x2bc]],dtype='<f4'),selectionSteps=costs)
