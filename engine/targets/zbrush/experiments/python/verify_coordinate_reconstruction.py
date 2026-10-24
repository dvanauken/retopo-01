"""EXP-0021: executable reduced-to-full unknown reconstruction from native records."""
import argparse,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
def reconstruct(solution,indices,constraints,count):
 values=np.full(count,np.nan,dtype=np.float32);values[indices]=solution;dependencies={r['dependent']:r['terms'] for r in constraints}
 if len(dependencies)!=len(constraints):raise ValueError('Duplicate dependent variable')
 for row in reversed(constraints):
  total=0.
  for j,coefficient in row['terms']:
   if not 0<=j<count or np.isnan(values[j]):raise ValueError('Unresolved/out-of-range dependency '+str(j))
   total+=float(values[j])*coefficient
  values[row['dependent']]=np.float32(total)
 if np.any(np.isnan(values)):raise ValueError('Unspecified variables')
 return values
def main():
 ap=argparse.ArgumentParser();ap.add_argument('capture');args=ap.parse_args();root=Path(args.capture).resolve();p=next(root.glob('*-return-0x296050'))
 ids=np.fromfile(p/'reduced-to-original.i32','<i4');solution=np.fromfile(root/'solver-2-solution.f64','<f8');constraints=json.loads((p/'constraints.json').read_text());n=(p/'integer-flags.u8').stat().st_size
 assert len(ids)==len(solution) and len(set(ids))==len(ids)
 full=reconstruct(solution,ids,constraints,n);uv=np.fromfile(p/'parameter-positions.f32x2','<f4');error=float(np.max(abs(full[:len(uv)]-uv)));rounded=full[:len(uv)].astype('<f4');mismatches=int(np.count_nonzero(rounded!=uv))
 result=dict(experimentId='EXP-0021',capture=root.relative_to(ROOT).as_posix(),unknowns=n,reducedUnknowns=len(ids),dependencyEquations=len(constraints),storedUVScalars=len(uv),auxiliaryValues=full[len(uv):].tolist(),maxDoubleToStoredFloatDifference=error,float32Mismatches=mismatches,passed=mismatches==0,scope='Reconstruction from native reduced solution and final native dependency records. Does not implement seam creation or discrete solving.')
 path=root/'coordinate-reconstruction-check.json'
 import sys
 sys.path.insert(0,str(ROOT/'targets/zbrush/scripts/python'))
 from promotion_policy import write_json
 write_json(path,result);print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
