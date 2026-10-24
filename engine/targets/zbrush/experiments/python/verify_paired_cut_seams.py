"""EXP-0098: bounded paired-cut-path interior seam dependency construction."""
import json
from pathlib import Path
import numpy as np
from probe_quarter_matrix import quarter
ROOT=Path(__file__).resolve().parents[4]
def construct(sideA,sideB,q,pinned):
 if len(sideA)!=len(sideB):raise ValueError('Mismatched side lengths')
 c,s,minusS,d=quarter(q);out=[]
 for a,b in zip(sideA[1:-1],sideB[1:-1]):
  for axis,row in enumerate([[c,minusS],[s,d]]):
   terms={}
   for j,value in enumerate(row):
    if value:
     for variable,coefficient in [(2*int(b)+j,value),(2*int(sideB[0])+j,-value)]:terms[variable]=terms.get(variable,0.)+coefficient
   variable=2*int(sideA[0])+axis;terms[variable]=terms.get(variable,0.)+1.
   out.append(dict(dependent=2*int(a)+axis,terms=[[i,v] for i,v in sorted(terms.items()) if v!=0 and i not in pinned]))
 return out

def main():
 base=ROOT/'work/zbrush/runtime/algorithm-recovery';root=base/'debug/ellipsoid-100-v48';dest=base/'paired-cut-seam-check.json'
 if dest.exists():raise RuntimeError('Preserve historical result')
 trace=json.loads((root/'trace.json').read_text());assert trace['status']=='captured' and not trace['timedOut'];p=next(root.glob('*-entry-0x28adf0'));native=json.loads((p/'constraints.json').read_text());pins=[r for r in native if not r['terms']];assert len(pins)==2;turns=np.fromfile(p/'cut-path-quarter-turns.f32','<f4');result=list(pins);counts=[]
 for i,q in enumerate(turns):
  a=np.fromfile(p/f'cut-path-side-a-{i}.i32','<i4');b=np.fromfile(p/f'cut-path-side-b-{i}.i32','<i4');records=construct(a,b,q,{r['dependent'] for r in pins});result.extend(records);counts.append(dict(path=i,verticesA=len(a),verticesB=len(b),quarter=float(q),dependencies=len(records)))
 mismatch=[i for i,(a,b) in enumerate(zip(result,native)) if a!=b];report=dict(experimentId='EXP-0098',passed=result==native,checks=dict(allDependencyRecords=result==native),paths=counts,gaugePins=len(pins),recoveredSeamRecords=len(result)-len(pins),mismatchedRecords=mismatch,scope='All304 ordinary paired-path interior seam dependencies and ordered term records from native19 side lists/quarter turns, plus two native gauge pins as inputs. Path side construction, gauge-pin selection, skip flags/symmetry/degeneracies and later expansion/elimination remain upstream/downstream separate.')
 dest.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
