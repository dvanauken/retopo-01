"""Supplement the accepted-export audit with the alternate quad diagonal.

Only the test copy's cyclic face start is changed, preserving winding, vertices,
polygon edges and topology. Its fan then uses diagonal 1--3 instead of 0--2.
Neither the accepted OBJ nor the original toilet is edited.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
import ast
from collections import defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import time
import numpy as np
from scipy.optimize import linprog

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj
from surface_intersections import measure as contacts
from curved_quad import find_blender
parser=argparse.ArgumentParser(); parser.add_argument('--matrix',nargs='+',type=Path,required=True); parser.add_argument('--label',default='current'); args=parser.parse_args()
OUT=ROOT/'tests/toilet-diagonal-contacts'/args.label; OUT.mkdir(parents=True,exist_ok=True)
# Reuse the exact independent LP audit, without executing its CLI/main block.
# Retain the extracted function and hash so this supplemental test is reproducible.
helper=ROOT/'tests/verify_toilet_fresh_geometry.py'; parsed=ast.parse(helper.read_text())
definition=next(n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name=='adjacent_interiors')
code=ast.get_source_segment(helper.read_text(),definition)
(OUT/'lp-function.py').write_text(code+'\n',newline='\n'); exec(compile(code,str(helper),'exec'))
cases=[]; seen=set()
for matrix in args.matrix:
    for case in json.loads(matrix.read_text())['cases']:
        if case['state']!='complete': continue
        obj=matrix.parent/case['name']/'output.obj'; digest=hashlib.sha256(obj.read_bytes()).hexdigest()
        if digest in seen: continue
        seen.add(digest); start=time.monotonic(); vertices,faces=read_obj(obj)
        shifted=np.roll(np.asarray(faces),-1,axis=1)
        test_obj=OUT/(case['name']+'-diagonal-13.obj')
        test_obj.write_text('\n'.join(['v '+' '.join(format(float(x),'.17g') for x in point) for point in vertices]+
                                    ['f '+' '.join(str(int(i)+1) for i in face) for face in shifted])+'\n',newline='\n')
        print(case['name'],'testing alternate-diagonal contacts',flush=True)
        screen=contacts(vertices,shifted); lp=adjacent_interiors(vertices,shifted.tolist())
        bvh_file=OUT/(case['name']+'-bvh.json')
        with (OUT/(case['name']+'-blender.log')).open('w',encoding='utf-8') as log:
            subprocess.run([str(find_blender()),'--background','--threads','2','--python',str(ROOT/'tests/check_toilet_overlap_blender.py'),'--',str(bvh_file),str(test_obj.resolve())],check=True,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=180)
        bvh=json.loads(bvh_file.read_text()); unchanged=hashlib.sha256(obj.read_bytes()).hexdigest()==digest
        passed=bool(screen['passed'] and lp['passed'] and bvh['passed'] and unchanged)
        cases.append(dict(name=case['name'],job=case['job'],outputSha256=digest,passed=passed,sourceUnchanged=unchanged,
                          alternateDiagonalScreen=screen,independentAdjacentInteriors=lp,independentBVH=bvh,elapsedSeconds=time.monotonic()-start))
        print(case['name'],'alternate diagonal',passed,flush=True)
        (OUT/'result.json').write_text(json.dumps(dict(complete=False,cases=cases),indent=2)+'\n',newline='\n')
result=dict(complete=True,passed=bool(cases) and all(c['passed'] for c in cases),cases=cases,
    sourceHashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('surface_intersections.py','tests/verify_toilet_fresh_geometry.py','tests/verify_toilet_diagonal_contacts.py','assets/models/toilet.obj')},
    lpFunctionSha256=hashlib.sha256((OUT/'lp-function.py').read_bytes()).hexdigest(),
    scope='Alternate quad-diagonal contact checks on explicit test copies with cyclically rotated face indices. Includes floating-point production contact screen, independent adjacent-interior LPs and separate nonadjacent Blender BVH check. Original exports and source unchanged; finite tolerances/scopes remain those stated by each detector.')
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',newline='\n')
raise SystemExit(0 if result['passed'] else 1)
