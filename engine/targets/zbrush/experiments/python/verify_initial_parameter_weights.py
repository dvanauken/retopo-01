"""EXP-0119: initial per-triangle objective weights and target values."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
def initial_weights(positions,triangles,permutation,k):
 order=(np.arange(3)[None,:]+permutation[:,None])%3;p=positions[np.take_along_axis(triangles,order,axis=1)];a=np.float32(p[:,1]-p[:,0]);b=np.float32(p[:,2]-p[:,0]);cross=np.cross(a,b);D=np.sqrt(np.float32(np.float32(cross[:,0]*cross[:,0]+cross[:,1]*cross[:,1])+np.float32(cross[:,2]*cross[:,2])),dtype=np.float32)
 if not np.all(D>0):raise ValueError('Degenerate faces unsupported')
 weights=np.column_stack([np.float32(D*np.float32(k)),D,np.float32(D*np.float32(k)),D]).astype(float).ravel();targets=np.tile([1.,0.,1.,0.],len(triangles));return weights,targets

def main():
 base=ROOT/'work/zbrush/runtime/algorithm-recovery';root=base/'debug/ellipsoid-100-v54';dest=base/'initial-parameter-weights-check.json'
 if dest.exists():raise RuntimeError('Preserve historical evidence')
 trace=json.loads((root/'trace.json').read_text());k=trace['parameterWeightSettings']['0x614'];p=next(root.glob('*-parameter-solver-component'));v=np.fromfile(p/'source-positions.f32x3','<f4').reshape(-1,3);tri=np.fromfile(p/'source-triangles.i32x3','<i4').reshape(-1,3);perm=np.fromfile(p/'triangle-permutation.u8','u1');w,b=initial_weights(v,tri,perm,k);nativeW=np.fromfile(p/'weights.f64','<f8');nativeB=np.fromfile(p/'rhs.f64','<f8');checks=dict(allInitialResidualWeights=np.array_equal(w,nativeW),allInitialResidualTargets=np.array_equal(b,nativeB));report=dict(experimentId='EXP-0119',passed=all(checks.values()),checks=checks,faces=len(tri),rows=len(w),nativeWeightCoefficient=k,scalarSettings=trace['parameterWeightSettings'],smoothingPasses=trace['parameterWeightSmoothingPasses'],maxWeightError=float(abs(w-nativeW).max(initial=0)),maxTargetError=float(abs(b-nativeB).max(initial=0)),scope='Actual nondegenerate four-row-per-face hard-guide objective: float32 twice-area D, weights[D*k,D,D*k,D] promoted double and targets[1,0,1,0]. k captured directly at remesher+0x614. Native field/basis conditioning and other guide/symmetry/special weighting branches remain separate.')
 dest.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
