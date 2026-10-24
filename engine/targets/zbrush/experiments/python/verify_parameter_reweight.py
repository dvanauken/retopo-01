"""EXP-0077: first parameter UV-distortion multipliers and seam-aware smoothing."""
import argparse,json,math,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
F=np.float32
def gradients(xyz,tri,normal,uv,uvtri):
 p0,p1,p2=[xyz[tri[:,i]] for i in range(3)];e=F(p1-p0);f=F(p2-p0);b=np.column_stack([F(normal[:,1]*e[:,2]-normal[:,2]*e[:,1]),F(normal[:,2]*e[:,0]-normal[:,0]*e[:,2]),F(normal[:,0]*e[:,1]-normal[:,1]*e[:,0])]);le=np.sqrt(F(F(e[:,1]*e[:,1]+e[:,0]*e[:,0])+e[:,2]*e[:,2]).astype('f8'));lb=np.sqrt(F(F(b[:,1]*b[:,1]+b[:,0]*b[:,0])+b[:,2]*b[:,2]).astype('f8'));assert bool((le>=1e-28).all()) and bool((lb>=1e-28).all());a=F(e.astype('f8')*(1/le)[:,None]);b=F(b.astype('f8')*(1/lb)[:,None]);x=F(F(a[:,1]*f[:,1]+a[:,0]*f[:,0])+a[:,2]*f[:,2]);y=F(F(b[:,1]*f[:,1]+b[:,0]*f[:,0])+b[:,2]*f[:,2]);L=F(le);r=F(F(1)/L);iy=F(F(1)/y);iD=F(F(1)/F(L*y));c=F(F(iD*x)-iy);q0,q1,q2=[uv[uvtri[:,i]] for i in range(3)];out=[]
 for channel in range(2):
  dx=F(F(q1[:,channel]-q0[:,channel])*r);dy=F(F(F(c*q0[:,channel])-F(F(q1[:,channel]*x)*iD))+F(iy*q2[:,channel]));out.append(F(F(a*dx[:,None])+F(b*dy[:,None])))
 return out

def smooth(initial,edges,offsets,corners,tags,axis,transition,iterations):
 links=[]
 for face in range(len(edges)):
  choices=[]
  for k,edge in enumerate(edges[face]):
   adjacent=corners[offsets[edge]:offsets[edge+1]]
   if len(adjacent)!=2:continue
   other=int(adjacent[1] if adjacent[0]==face*3+k else adjacent[0]);assert face*3+k in adjacent
   choices.append((other//3,bool(transition[edge]&1),tags[edge]!=2 or bool(axis[face*3+k]),tags[edge]!=2 or not bool(axis[face*3+k])))
  links.append(choices)
 weights=initial.copy()
 for _ in range(iterations):
  updated=np.empty_like(weights)
  for face in range(len(edges)):
   v=weights[face].copy();cu=cv=1
   for other,swap,useU,useV in links[face]:
    if useU:
     pair=weights[other,2:4] if swap else weights[other,0:2];v[:2]+=pair;cu+=1
    if useV:
     pair=weights[other,0:2] if swap else weights[other,2:4];v[2:]+=pair;cv+=1
   updated[face,:2]=v[:2]*(1/cu);updated[face,2:]=v[2:]*(1/cv)
  weights=updated
 return weights

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--session',default='cross-50-v35');ap.add_argument('--experiment-id',default='EXP-0077');cli=ap.parse_args();base=ROOT/'work/zbrush/runtime/algorithm-recovery';root=base/'debug'/cli.session;dest=base/('parameter-reweight-check.json' if cli.session=='cross-50-v35' else cli.session+'-parameter-reweight-check.json')
 if Path(cli.session).name!=cli.session:raise ValueError('Session must be a simple retained capture name')
 if dest.exists():raise RuntimeError('Preserve previous result')
 trace=json.loads((root/'trace.json').read_text());assert trace['status']=='captured' and trace.get('timedOut') is False,'Require a completed owned native capture before checking callback presence'
 p=next(root.glob('*-entry-0x294770'));q=next(root.glob('*-return-0x294770'));geometry=next(root.glob('*-entry-0x294770-component'));before=next(root.glob('*-entry-0x293fc0-component'));after=next(root.glob('*-return-0x293fc0-component'));checks=[]
 def array(folder,name,d='<f4',w=None):
  a=np.fromfile(folder/name,d);return a.reshape(-1,w) if w else a
 def check(name,want,native):checks.append(dict(name=name,passed=np.array_equal(want,native),maxError=float(np.max(abs(want-native),initial=0)),mismatches=int(np.count_nonzero(want!=native))))
 xyz=array(geometry,'source-positions.f32x3',w=3);tri=array(geometry,'source-triangles.i32x3','<i4',3);normal=array(geometry,'source-normal.f32x3',w=3);uv=array(geometry,'parameter-positions.f32x2',w=2);uvtri=array(geometry,'parameter-triangles.i32x3','<i4',3);starts=array(p,'face-residual-start.i32','<i4');assert np.array_equal(starts,np.arange(len(tri)+1)*4)
 g=gradients(xyz,tri,normal,uv,uvtri);initial=np.ones((len(tri),4));q0,q1,q2=[uv[uvtri[:,i]] for i in range(3)];det=F(F(F(q1[:,0]-q0[:,0])*F(q2[:,1]-q0[:,1]))-F(F(q1[:,1]-q0[:,1])*F(q2[:,0]-q0[:,0])));initial[det<0]+=5
 for j,gradient in enumerate(g):
  inverse=F(F(1)/np.sqrt(F(F(gradient[:,1]*gradient[:,1]+gradient[:,0]*gradient[:,0])+gradient[:,2]*gradient[:,2]),dtype='f4'));scale=array(geometry,'scale-'+('a' if j==0 else 'b')+'.f32');lo=F(scale*F(1.8));hi=F(scale*F(4));selected=inverse>lo;delta=np.full(len(tri),F(3));ramp=selected&(inverse<=hi);delta[ramp]=F(F(F(3)/F(hi[ramp]-lo[ramp]))*F(inverse[ramp]-lo[ramp]));initial[selected,j*2]+=delta[selected].astype('f8')
 initial=np.minimum(initial,10);nativeInitial=array(p,'weight-multipliers.f64','<f8',4);check('initial-multipliers',initial,nativeInitial)
 edges=array(geometry,'source-face-edges.i32x3','<i4',3);offsets=array(geometry,'source-edge-face-offset.i32','<i4');corners=array(geometry,'source-edge-face-corners.i32','<i4');tags=array(p,'edge-constraint-tags.u8','u1');axis=np.unpackbits(array(geometry,'edge-axis.bits','u1'),bitorder='little');transition=array(geometry,'transitions.i32','<i4');iterations=struct.unpack('<I',(p/'iteration-count.u32').read_bytes())[0];weights=smooth(initial,edges,offsets,corners,tags,axis,transition,iterations)
 check('smoothed-multipliers',weights,array(q,'weight-multipliers.f64','<f8',4));check('updated-residual-weights',weights*array(before,'weights.f64','<f8',4),array(after,'weights.f64','<f8',4));result=dict(experimentId=cli.experiment_id,sourceSession=cli.session,passed=all(c['passed'] for c in checks),checks=checks,faces=len(tri),rows=len(tri)*4,flippedTriangles=int(np.count_nonzero(det<0)),nonunitInitialMultipliers=int(np.count_nonzero(initial!=1)),oddTransitions=int(np.count_nonzero(transition&1)),constrainedEdgeTags=int(np.count_nonzero(tags==2)),smoothingIterations=iterations,scope='First captured293fc0 callback: native current UVs and source geometry/scales to float distortion factors, seam/tag-aware Jacobi multipliers and residual weight products. Generic integer scheduling, retry and complete parameter solver remain separate. Finite nondegenerate geometry only; angular threshold859.4366926962348 exceeds the bounded angle deviation. Zero nonunit/tag/parity counts are not positive qualification of those branches.')
 dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
