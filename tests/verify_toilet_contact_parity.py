"""Compare compiled and reference predicates on actual accepted toilet exports."""
from pathlib import Path
import hashlib,json,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj
from surface_intersections import measure,measure_reference
paths=['tests/toilet-sampled-worker/integrated-fallback/bowl-only-1800/output.obj',
       'tests/toilet-sampled-worker/integrated-fallback/two-guides-short-1800/output.obj',
       'runs/30f50797ab8f44f5a9d60995d8cdbe72/output.obj']
records=[]
for name in paths:
    path=ROOT/name;v,f=read_obj(path);start=time.perf_counter();reference=measure_reference(v,f,both_quad_diagonals=True);reference_seconds=time.perf_counter()-start
    start=time.perf_counter();actual=measure(v,f,both_quad_diagonals=True);compiled_seconds=time.perf_counter()-start
    for key in ('passed','nonAdjacentIntersectingFacePairs','adjacentIntersectingFacePairs','quadDiagonalPolicy'):assert actual[key]==reference[key],(name,key)
    assert actual['passed'],name
    records.append(dict(path=name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),referenceSeconds=reference_seconds,compiledSeconds=compiled_seconds,passed=True))
    print(name,round(reference_seconds,2),'->',round(compiled_seconds,2),'seconds; exact pair parity',flush=True)
out=ROOT/'runs/feature-contact-parity.json';out.write_text(json.dumps(records,indent=2)+'\n')
