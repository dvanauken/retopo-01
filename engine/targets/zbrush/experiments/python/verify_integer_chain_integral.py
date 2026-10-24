"""EXP-0090: recovered geometric path integral0x292aa0."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
f=np.float32

def integral(path,axis,positions,mapping,edges,vo,ve,eo,ec,basisA,basisB,directionA,directionB,scale):
 total=f(0);directions=directionA if axis==0 else directionB
 for source,target in zip(path[:-1],path[1:]):
  matches=[int(e) for e in ve[vo[source]:vo[source+1]] if target in edges[e]]
  if not matches:continue
  edge=matches[0];a=int(mapping[source]);b=int(mapping[target])
  if a<0 or b<0:continue
  delta=f(positions[b]-positions[a]);value=f(0);corners=ec[eo[edge]:eo[edge+1]]
  if len(corners)>3:raise ValueError('Unqualified unrolled nonmanifold integral summation')
  if not len(corners):raise ValueError('Zero-incidence edge')
  for corner in corners:
   face=int(corner)//3;d=directions[face];v=f(f(d[1]*basisB[face])+f(d[0]*basisA[face]));dot=f(f(f(v[1]*delta[1])+f(v[0]*delta[0]))+f(v[2]*delta[2]));value=f(value+f(dot/scale[face]))
  total=f(f(value/f(len(corners)))+total)
 return total

def main():
 base=ROOT/'work/zbrush/runtime/algorithm-recovery';root=base/'debug/ellipsoid-100-v45';dest=base/'integer-chain-integral-check.json'
 if dest.exists():raise RuntimeError('Preserve historical result')
 trace=json.loads((root/'trace.json').read_text());assert trace['status']=='captured' and not trace['timedOut'];common=next(root.glob('*-return-0x292aa0/parameter-to-source.i32')).parent;component=next(root.glob('*-return-0x292aa0-component'));array=lambda p,n,d:np.fromfile(p/n,d);positions=array(component,'source-positions.f32x3','<f4').reshape(-1,3);mapping=array(common,'parameter-to-source.i32','<i4');edges=array(common,'parameter-edges.i32x2','<i4').reshape(-1,2);vo=array(common,'parameter-vertex-edge-offset.i32','<i4');ve=array(common,'parameter-vertex-edge-list.i32','<i4');eo=array(common,'parameter-edge-face-offset.i32','<i4');ec=array(common,'parameter-edge-face-corners.i32','<i4');a=array(component,'basis-a.f32x3','<f4').reshape(-1,3);b=array(component,'basis-b.f32x3','<f4').reshape(-1,3);da=array(component,'uv-direction-a.f32x2','<f4').reshape(-1,2);db=array(component,'uv-direction-b.f32x2','<f4').reshape(-1,2);scale=array(component,'scale-a.f32','<f4');cases=[]
 for p in sorted(root.glob('*-return-0x292aa0'),key=lambda p:int(p.name.split('-')[0])):
  path=array(p,'path.i32','<i4');axis=int(array(p,'axis.i32','<i4')[0]);native=array(p,'integral.f32','<f4')[0];expected=integral(path,axis,positions,mapping,edges,vo,ve,eo,ec,a,b,da,db,scale);cases.append(dict(name=p.name,axis=axis,pathVertices=len(path),native=float(native),recovered=float(expected),passed=bool(native==expected)))
 result=dict(experimentId='EXP-0090',passed=bool(cases) and all(c['passed'] for c in cases),cases=cases,scope='All captured ordinary manifold0x292aa0 chains, source displacement projected onto transported target direction, incident-face mean divided by scale-a for both axes, float32 accumulation. Inputs include native geometry/frames/directions/mapping; path producer remains upstream.')
 dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
