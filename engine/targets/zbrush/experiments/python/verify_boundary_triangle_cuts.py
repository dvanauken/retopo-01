"""EXP-0071: all149 ordinary boundary-chord splits in the diagonal capture."""
import json,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
def split(triangle,s,t,a,b):
 if not 0<=s<t<3 or int(s)==int(t):raise RuntimeError('Unqualified same-edge, degenerate or sentinel branch')
 i,j=int(s),int(t)
 first=triangle[:i+1]+([a] if s!=i else [])+[b]+triangle[j+1:]
 second=[a]+triangle[i+1:j+1]+([b] if t!=j else [])
 if min(len(first),len(second))<3:raise RuntimeError('Degenerate split')
 return [first,second]
def main():
 base=ROOT/'work/zbrush/runtime/algorithm-recovery';root=base/'debug/diagonal-patch-100-v33';dest=base/'boundary-triangle-cut-check.json'
 if dest.exists():raise RuntimeError('Preserve previous result')
 key=lambda p:int(p.name.split('-')[0]);inputs=sorted(root.glob('*-entry-0x254210'),key=key);outputs=sorted(root.glob('*-return-0x254210'),key=key);trace=json.loads((root/'trace.json').read_text());assert trace['status']=='captured' and not trace['timedOut'] and trace['boundaryCutsCaptured']==len(inputs)==len(outputs)<512;cases=[]
 for p,q in zip(inputs,outputs):
  try:
   triangle=np.fromfile(p/'polygon-indices.i32','<i4').tolist();constraints=list(struct.iter_unpack('<ddii',(p/'constraints.f64x2-i32x2').read_bytes()));assert len(triangle)==3 and len(constraints)==1;s,t,a,b=constraints[0];polygons=split(triangle,s,t,a,b);flat=[v for poly in polygons for v in poly];offsets=[0,len(polygons[0]),len(flat)];checks=dict(offsets=offsets==np.fromfile(q/'polygon-offsets.i32','<i4').tolist(),indices=flat==np.fromfile(q/'polygon-indices.i32','<i4').tolist(),positionsUnchanged=(p/'new-positions.f32x3').read_bytes()==(q/'new-positions.f32x3').read_bytes());cases.append(dict(inputCapture=p.name,triangle=triangle,constraint=constraints[0],polygons=polygons,checks=checks,passed=all(checks.values())))
  except Exception as e:cases.append(dict(inputCapture=p.name,passed=False,error=type(e).__name__+': '+str(e)))
 result=dict(experimentId='EXP-0071',passed=bool(cases) and all(c['passed'] for c in cases),cases=cases,scope='All149 captured outer boundary-only calls: single triangle, one ordered nondegenerate chord joining different boundary edges/corners, no intersections, no recursive multiple constraints. Exact face order, winding, vertex reuse and offsets; no new position allocation.')
 dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(cases=len(cases),passed=result['passed'],failed=[c for c in cases if not c['passed']])))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
