"""Package compact native integer callback boundaries, with source file hashes."""
import argparse,json,sys,struct,hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--workbench',type=Path,required=True);ap.add_argument('--capture',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--name',required=True);a=ap.parse_args();assert not a.output.exists();a.output.parent.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(a.workbench/'targets/zbrush/experiments/python'));from recovered_index_sort import sort_indices
 p=a.capture;used=[];key=lambda p:int(p.name.split('-')[0])
 def binary(d,n,t):q=d/n;used.append(q);return np.fromfile(q,t)
 def readjson(q):used.append(q);return json.loads(q.read_text())
 entries=sorted(p.glob('*-entry-0xe5af0'),key=key);returns=sorted(p.glob('*-return-0xe5af0'),key=key)
 def matrix(d,suffix):return readjson(p/(str(key(d)+1)+'-'+suffix)/'matrix-rows.json')['terms']
 nativeRows=matrix(entries[0],'entry-0xe5af0-matrix');nativeConstraints=matrix(entries[1],'entry-0xe5af0-matrix');preRows=matrix(returns[0],'return-0xe5af0-matrix');weights=binary(entries[0],'residual-weights.f64','<f8');targets=binary(entries[0],'residual-targets.f64','<f8')
 gp=next(p.glob('*-return-0x28b920'));ng=len(binary(gp,'group-axis.u8','u1'));geometry=next(p.glob('*-return-0x292aa0-component'));uv=binary(geometry,'parameter-positions.f32x2','<f4').reshape(-1,2);used.append(geometry/'component-structure.bin');header=(geometry/'component-structure.bin').read_bytes();constant=struct.unpack_from('<i',header,0x978)[0];gauge=struct.unpack_from('<i',header,0x9b0)[0];deps=readjson(entries[0]/'dependencies.json');pins=[d['dependent'] for d in deps[:gauge]]
 regionsFolder=sorted(p.glob('*-integer-regions'),key=key)[-1];pairs=binary(regionsFolder,'candidate-scalars.i32x2','<i4').reshape(-1,2);regions=binary(regionsFolder,'all-candidate-regions.i32x2','<i4').reshape(-1,2);gaps=binary(regionsFolder,'candidate-gaps.f32','<f4');pathmap=defaultdict(list)
 for d in sorted(p.glob('*-return-0x292aa0'),key=key):
  path=binary(d,'path.i32','<i4');axis=int(binary(d,'axis.i32','<i4')[0]);value=float(binary(d,'integral.f32','<f4')[0]);pathmap[(axis,int(path[0]),int(path[-1]))].append(value)
 candidates=[];consumed=defaultdict(int)
 for i in sort_indices(gaps):
  x,y=map(int,pairs[i]);owners=regions[i].tolist()
  if x<0:continue
  axis=x%2;pk=(axis,x//2,y//2);vals=pathmap.get(pk,[]);pos=consumed[pk];integral=vals[pos] if pos<len(vals) else None
  if integral is not None:consumed[pk]+=1
  candidates.append(dict(index=int(i),scalars=[x,y],firstGuide=owners[0]<ng,secondGuide=owners[1]<ng,delta=float(np.float32(uv[y//2,axis]-uv[x//2,axis])),cross=float(np.float32(uv[y//2,1-axis]-uv[x//2,1-axis])),integral=integral))
 elim=sorted(p.glob('*-entry-0x288f50'),key=key)[-1];augmented=matrix(elim,'entry-0x288f50-row-vectors');expectedDeps=readjson(entries[-1]/'dependencies.json');compressed=next(p.glob('*-return-0xe4800'));forward=binary(compressed,'original-to-reduced.i32','<i4');inverse=binary(compressed,'reduced-to-original.i32','<i4');common=next(p.glob('*-return-0x292aa0/original-to-outer-reduced.i32')).parent;outerMap=binary(common,'original-to-outer-reduced.i32','<i4');incoming=binary(next(p.glob('*-entry-0x28fe70')),'solution.f64','<f8');regularization=[]
 for original,reduced in enumerate(forward):
  if reduced<0:continue
  regularization.append([original,float(incoming[outerMap[original]]) if original<constant and outerMap[original]>=0 else (0. if original<constant else 1.)])
 tr=next(p.glob('*-entry-0x28f990'));indices=binary(tr,'outer-integer-indices.i32','<i4');outerInverse=binary(tr,'outer-reduced-to-original.i32','<i4');steps=binary(tr,'outer-integer-steps.f64','<f8');assert not len(steps);outerOriginal=outerInverse[indices].tolist();ret=next(p.glob('*-return-0x28fe70'));expectedRows=readjson(next(p.glob('*-return-0x28fe70-integer-phase-residuals'))/'matrix-rows.json')['terms'];out=next(p.glob('*-return-0x28f990'));solver=sorted(p.glob('*-entry-0xdbf90'),key=key)[-1];used.append(solver/'solver-structure.bin');budget=struct.unpack_from('<d',(solver/'solver-structure.bin').read_bytes(),0xf8)[0]
 report=dict(schema=1,name=a.name,captureName=p.name,engineSha256='0d45ea6f9331cecb55c12a10dcdb6d4bedb86cf302cd873748704dbaa82b00bc',scope='Native captured upstream boundary inputs; downstream rows/dependencies/integers/fixes are independent comparison oracles. Not an original-source or full-output fixture.',policy=dict(candidates=candidates,gaugeScalars=pins,constant=constant,candidateCount=len(pairs),expectedRows=nativeRows,expectedWeights=weights.tolist(),expectedTargets=targets.tolist(),expectedConstraintPrefix=nativeConstraints[:sum(c['integral'] is not None for c in candidates)]),callback=dict(constant=constant,dimension=len(forward),augmentedRows=augmented,expectedDependencies=expectedDeps,initialReducedRows=preRows,initialWeights=weights.tolist(),initialTargets=targets.tolist(),regularizationTargetsByOriginal=regularization,outerOriginalScalars=outerOriginal,budget=budget,expectedRows=expectedRows,expectedWeights=binary(ret,'integer-phase-weights.f64','<f8').tolist(),expectedTargets=binary(ret,'integer-phase-targets.f64','<f8').tolist(),expectedSolution=binary(tr,'nested-solution.f64','<f8').tolist(),expectedFixPositions=binary(out,'selected-outer-list-positions.i32','<i4').tolist(),expectedFixValues=binary(out,'selected-values.f64','<f8').tolist()),provenance=[dict(path=str(q.relative_to(p)).replace('\\','/'),sha256=hashlib.sha256(q.read_bytes()).hexdigest()) for q in sorted(set(used))])
 a.output.write_text(json.dumps(report,separators=(',',':'))+'\n',encoding='utf-8');print(json.dumps(dict(path=str(a.output),bytes=a.output.stat().st_size,candidates=len(candidates),constraints=len(augmented),dependencies=len(expectedDeps),nestedVariables=len(inverse),outerFixes=len(report['callback']['expectedFixPositions']))))
if __name__=='__main__':main()
