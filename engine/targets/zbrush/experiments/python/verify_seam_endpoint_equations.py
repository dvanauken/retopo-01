"""EXP-0110: all ordinary path-endpoint chart closure equations."""
import json
from pathlib import Path
import numpy as np
from probe_quarter_matrix import quarter
ROOT=Path(__file__).resolve().parents[4]
def endpoint_rows(a,b,q,pins):
 c,s,t,d=quarter(q);out=[]
 for axis,row in enumerate([[c,t],[s,d]]):
  terms={}
  for scalar,value in [(2*int(a[0])+axis,1.),(2*int(a[-1])+axis,-1.)]:terms[scalar]=terms.get(scalar,0.)+value
  for j,value in enumerate(row):
   if value:
    for scalar,coef in [(2*int(b[-1])+j,value),(2*int(b[0])+j,-value)]:terms[scalar]=terms.get(scalar,0.)+coef
  out.append([[i,v] for i,v in sorted(terms.items()) if v!=0 and i not in pins])
 return out

def main():
 base=ROOT/'work/zbrush/runtime/algorithm-recovery';root=base/'debug/ellipsoid-100-v52';dest=base/'seam-endpoint-equations-check.json'
 if dest.exists():raise RuntimeError('Preserve historical result')
 p=next(root.glob('*-entry-0x28adf0'));pins={r['dependent'] for r in json.loads((p/'constraints.json').read_text()) if not r['terms']};turns=np.fromfile(p/'cut-path-quarter-turns.f32','<f4');rows=[]
 for i,q in enumerate(turns):rows.extend(endpoint_rows(np.fromfile(p/f'cut-path-side-a-{i}.i32','<i4'),np.fromfile(p/f'cut-path-side-b-{i}.i32','<i4'),q,pins))
 call=sorted(root.glob('*-entry-0x288f50'),key=lambda p:int(p.name.split('-')[0]))[0];native=json.loads(next(root.glob(str(int(call.name.split('-')[0])+1)+'-entry-0x288f50-row-vectors/matrix-rows.json')).read_text())['terms'];result=dict(experimentId='EXP-0110',passed=rows==native,checks=dict(allEndpointResidualTerms=rows==native),paths=len(turns),endpointRows=len(rows),scope='All38 ordinary endpoint closure equations R*(Bend-Bstart)+Astart-Aend=0 in native row/term order, substituting two supplied zero gauge pins. Native side paths/quarters are inputs; alternate path endpoint policies/symmetry remain outside.')
 dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
