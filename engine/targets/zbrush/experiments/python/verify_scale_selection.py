"""EXP-0040: replay native cross-scale windows, confidence and index smoothing.
Only field mode0 main valid-window path. Fallback faces are explicit exclusions.
"""
import argparse,json,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
f32=np.float32

def bits(p,n):return np.unpackbits(np.fromfile(p,'u1'),bitorder='little')[:n].astype(bool)
def dot(a,b):return f32(f32(a[:,0]*b[:,0]+a[:,1]*b[:,1])+a[:,2]*b[:,2])
def angle(a,b):
 denominator=np.sqrt(dot(a,a).astype('f8')*dot(b,b).astype('f8'))
 ratio=np.zeros(len(a));np.divide(dot(a,b),denominator,out=ratio,where=denominator!=0)
 return np.where((denominator==0)|(abs(ratio)>=1),0,np.arccos(np.minimum(abs(ratio),1))).astype('f4')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('capture');a=ap.parse_args();root=Path(a.capture).resolve();p=next(root.glob('*-field-before-release'));initial=next(root.glob('*-field-before-scales'));h=(p/'field-structure.bin').read_bytes()
 n=len(np.fromfile(p/'face-flags.u8','u1'));num,left,right=[struct.unpack_from('<i',h,o)[0] for o in [0x84,0x8c,0x90]]
 original=np.fromfile(initial/'face-flags.u8','u1');excluded=bits(p/'excluded-faces.bits',n);eligible=(~excluded)&((original&12)==0)
 directions=np.array([np.fromfile(p/f'scale-{k}-face-direction.f32x3','<f4').reshape(-1,3) for k in range(num)])
 valid=np.array([bits(p/f'scale-{k}-valid.bits',n) for k in range(num)]);windows=np.zeros_like(valid);scores=np.zeros((num,n),dtype='f4');selected=np.full(n,-1,dtype='i4');best=np.full(n,np.inf,dtype='f4');checks=[]
 def check(name,mask,**data):checks.append(dict(name=name,passed=bool(mask),**data))
 for k in range(num):
  lo=max(0,k-left);hi=min(num-1,k+right);windows[k]=eligible&valid[lo:hi+1].all(axis=0)
  for j in range(lo,hi+1):
   if j!=k:scores[k]=f32(scores[k]+angle(directions[k],directions[j]))
  scores[k]=f32(scores[k]/f32(hi-lo+1))
  nativebits=bits(p/f'scale-{k}-window.bits',n);native=np.fromfile(p/f'scale-{k}-score.f32','<f4');err=float(np.max(abs(scores[k,windows[k]]-native[windows[k]]),initial=0))
  check(f'scale-{k}-window',np.array_equal(windows[k],nativebits),faces=int(windows[k].sum()),mismatches=int((windows[k]!=nativebits).sum()))
  check(f'scale-{k}-score',err<=1e-7,maxAbsoluteError=err,tolerance=1e-7)
  choose=windows[k]&(scores[k]<best);selected[choose]=k;best[choose]=scores[k,choose]
 mainmask=selected>=0;chosen=selected[mainmask];ids=np.flatnonzero(mainmask);native_direction=np.fromfile(p/'directions.f32x3','<f4').reshape(-1,3)
 check('main-selected-direction',np.array_equal(native_direction[ids],directions[chosen,ids]),faces=len(ids))
 mid=np.array([np.fromfile(p/f'scale-{k}-lambda-mid.f32','<f4') for k in range(num)])[chosen,ids];largest=np.array([np.fromfile(p/f'scale-{k}-lambda-max.f32','<f4') for k in range(num)])[chosen,ids]
 anisotropy=f32(f32(abs(largest)-abs(mid))/abs(largest));base=f32(struct.unpack_from('<f',h,0x40)[0]);score=best[ids]
 angular=np.where(score<0,f32(250),np.where(score<=f32(.06981316953897476),f32(f32(250)-f32(score*f32(1790.4931640625))),f32(125)))
 anisoconf=np.where(anisotropy<base,f32(375),np.where(anisotropy<=1,f32(f32(f32(f32(375)/f32(f32(1)-base))*f32(anisotropy-base))+f32(375)),f32(750)))
 weight=f32(angular+anisoconf);nativeweight=np.fromfile(p/'face-weights.f32','<f4')[ids];err=float(np.max(abs(weight-nativeweight),initial=0));check('main-confidence',err<=1e-3,maxAbsoluteError=err,tolerance=1e-3)
 for offset,want,name in [(0x430,(valid&eligible).sum(axis=0),'valid-scale-count.i32'),(0x448,windows.sum(axis=0),'window-scale-count.i32')]:
  native=np.fromfile(p/name,'<i4');check(name,np.array_equal(want,native),mismatches=int((want!=native).sum()))
 presmooth=next(root.glob('*-field-before-scale-smoothing'));seed=np.fromfile(presmooth/'selected-scale.i32','<i4')
 check('main-selected-scale-before-smoothing',np.array_equal(seed[ids],selected[ids]),faces=len(ids))
 # Replay smoothing from native pre-pass indices to isolate it from the
 # explicitly unrecovered fallback and protected scale-choice branches.
 selected=seed.copy()
 # Disassembly confirms a repeated read of the FIRST edge, three additions of
 # the SAME neighboring scale, rather than a three-neighbor face stencil.
 if h[0x94]:
  faceedges=np.fromfile(p/'source-face-edges.i32x3','<i4').reshape(-1,3);off=np.fromfile(p/'source-edge-face-offset.i32','<i4');corners=np.fromfile(p/'source-edge-face-corners.i32','<i4')
  for iteration in range(3):
   out=selected.copy()
   for face in np.flatnonzero((selected>=0)&(~excluded)):
    edge=faceedges[face,0]
    if off[edge+1]-off[edge]!=2:continue
    pair=corners[off[edge]:off[edge+1]]//3
    neighbor=int(pair[1] if pair[0]==face else pair[0] if pair[1]==face else -1)
    if neighbor<0 or selected[neighbor]<0:continue
    total=f32(selected[face])
    for _ in range(3):total=f32(total+f32(selected[neighbor]))
    target=int(f32(f32(total/f32(4))+f32(.5)))
    step=1 if target<selected[face] else -1
    while target!=selected[face]:
     if windows[target,face]:out[face]=target;break
     target+=step
   selected=out
 native=np.fromfile(p/'selected-scale.i32','<i4');bad=np.flatnonzero(native!=selected);check('three-pass-final-scale-index',len(bad)==0,mismatches=len(bad),firstMismatches=bad[:20].tolist())
 result=dict(experimentId='EXP-0040',capture=root.relative_to(ROOT).as_posix(),cases=checks,passed=all(c['passed'] for c in checks),coverage=dict(faces=n,mainWindowFaces=len(ids),protected=int(((original&12)!=0).sum()),fallback=int((eligible&~mainmask).sum()),excluded=int(excluded.sum())),scope='Main valid-window mode0 scale selection/confidence; index smoothing independently seeded with captured pre-pass values. Fallback and protected eigenpair blends remain separate.')
 dest=root/'scale-selection-check.json'
 if dest.exists():raise RuntimeError('Preserve previous result')
 dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
