"""EXP-0072: default triangle/quad polygon conversion and exact diagonal choice."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
F=np.float32
def squared(v):return F(F(F(v[0]*v[0])+F(v[1]*v[1]))+F(v[2]*v[2]))
def triangulate(polygons,positions):
 output=[];flipped=0
 for p in polygons:
  if len(p)==3:output.append(p.copy())
  elif len(p)==4:
   d0=F(positions[p[0]]-positions[p[2]]);d1=F(positions[p[1]]-positions[p[3]]);start=1 if squared(d1)<squared(d0) else 0;flipped+=start
   if start:output.extend([[p[1],p[2],p[3]],[p[1],p[3],p[0]]])
   else:output.extend([[p[0],p[1],p[2]],[p[0],p[2],p[3]]])
  else:raise RuntimeError('Unqualified general polygon conversion')
 return np.asarray(output,dtype='i4'),flipped
def main():
 base=ROOT/'work/zbrush/runtime/algorithm-recovery';root=base/'debug/diagonal-patch-100-v33';dest=base/'cut-polygon-conversion-check.json'
 if dest.exists():raise RuntimeError('Preserve previous result')
 p=next(root.glob('*-entry-0x24ea90'));q=next(root.glob('*-return-0x24ea90'));options=(p/'conversion-options.bin').read_bytes();assert options[:4]==bytes(4);v=np.fromfile(p/'input-positions.f32x3','<f4').reshape(-1,3);offsets=np.fromfile(p/'input-face-offsets.i32','<i4');flat=np.fromfile(p/'input-face-indices.i32','<i4');polygons=[flat[a:b].tolist() for a,b in zip(offsets[:-1],offsets[1:])];wanted,flipped=triangulate(polygons,v);native=np.fromfile(q/'output-face-indices.i32','<i4').reshape(-1,3);checks=dict(orderedTriangleIds=np.array_equal(wanted,native),positionsUnchanged=(p/'input-positions.f32x3').read_bytes()==(q/'output-positions.f32x3').read_bytes(),triangleStorage=int(np.fromfile(q/'output-face-kind.i32','<i4')[0])==2);result=dict(experimentId='EXP-0072',passed=all(checks.values()),checks=checks,sourceSession='diagonal-patch-100-v33',polygons=len(polygons),triangles=len(native),inputTriangles=sum(len(p)==3 for p in polygons),inputQuads=sum(len(p)==4 for p in polygons),shorterSecondDiagonal=flipped,scope='Options bytes0..3 allzero. All306 captured triangle/quad polygons become437 ordered triangles, using float32 squared shorter-diagonal rule and strict tie keeping diagonal0-2; general ngons/alternate flags/attributes unsupported.')
 dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
