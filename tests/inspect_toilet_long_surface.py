"""Measure full surface bounds even though the retained long guide still fails."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj
candidate=ROOT/'tests/toilet-sampled-paths/captured-seed2-401/two-guides-long-1800-4.json';packet=json.loads(candidate.read_text())
sv,sf=read_obj(ROOT/'assets/models/toilet.obj')
result=cq.validate_surface(np.asarray(sv),np.asarray(sf),np.asarray(packet['vertices']),np.asarray(packet['faces']),1800)
report=dict(complete=True,geometryQualified=False,surface=result,
 sourceHashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('curved_quad.py','surface_distance.py','assets/models/toilet.obj','tests/inspect_toilet_long_surface.py')},
 candidate=str(candidate.relative_to(ROOT)),candidateSha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
 scope='Diagnostic full surface evaluation of an unchanged retained candidate that still fails guide tangent alignment. Passing surface bounds alone does not qualify this mesh or change production acceptance.')
out=ROOT/'tests/toilet-long-surface-diagnostics';out.mkdir(exist_ok=False)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
print(json.dumps(dict(surfacePassed=result['passed'],bounds={name:{key:dict(passed=value[key]['passed'],sampledMax=value[key]['sampledMax'],witness=value[key]['witness']) for key in ('sourceToOutput','outputToSource')} for name,value in result['wholeSurfaceDiagonals'].items()})))
