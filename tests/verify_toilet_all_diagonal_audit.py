"""Audit every retained accepted export against all quad-diagonal pairings.

The candidate enumeration is the production all-pairings screen, supported by
the independent analytic mixed-diagonal control. Every reported face pair also
gets separate HiGHS interior-feasibility tests; those witness tests do not cover
boundary-only contacts and do not convert an unwitnessed screen into a pass.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
from scipy.optimize import linprog
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj
from surface_intersections import measure
parser=argparse.ArgumentParser(); parser.add_argument('--matrix',nargs='+',type=Path,required=True); parser.add_argument('--label',default='current'); args=parser.parse_args()
OUT=ROOT/'tests/toilet-all-diagonal-audit'/args.label; OUT.mkdir(parents=True,exist_ok=True)
cases=[]; seen=set()
inequality=np.r_[np.c_[-np.eye(4),np.ones(4)],[[1,1,0,0,1],[0,0,1,1,1]]]
for matrix in args.matrix:
    for case in json.loads(matrix.read_text())['cases']:
        if case['state']!='complete': continue
        obj=matrix.parent/case['name']/'output.obj'; digest=hashlib.sha256(obj.read_bytes()).hexdigest()
        if digest in seen: continue
        seen.add(digest); vertices,faces=read_obj(obj); result=measure(vertices,faces,both_quad_diagonals=True)
        pairs=result['nonAdjacentIntersectingFacePairs']+result['adjacentIntersectingFacePairs']; witnesses=[]
        for a,b in pairs:
            found=None; unresolved=[]
            for ia in ([0,1,2],[0,2,3],[1,2,3],[1,3,0]):
                for ib in ([0,1,2],[0,2,3],[1,2,3],[1,3,0]):
                    ta=vertices[np.asarray(faces[a])[ia]]; tb=vertices[np.asarray(faces[b])[ib]]
                    eq=np.c_[ta[1]-ta[0],ta[2]-ta[0],-(tb[1]-tb[0]),-(tb[2]-tb[0]),np.zeros(3)]
                    program=linprog([0,0,0,0,-1],A_eq=eq,b_eq=tb[0]-ta[0],A_ub=inequality,b_ub=[0,0,0,0,1,1],bounds=[(0,None)]*4+[(0,1/3)],method='highs')
                    if program.status not in (0,2): unresolved.append(program.status)
                    if program.success and program.x[-1]>1e-7 and np.linalg.norm(eq@program.x-(tb[0]-ta[0]))<=1e-9:
                        found=dict(triangles=[ia,ib],minimumBarycentric=float(program.x[-1]),point=(ta[0]+program.x[0]*(ta[1]-ta[0])+program.x[1]*(ta[2]-ta[0])).tolist()); break
                if found: break
            witnesses.append(dict(faces=[a,b],strictInteriorWitness=found,unresolved=unresolved))
        record=dict(name=case['name'],job=case['job'],matrix=str(matrix),outputSha256=digest,passed=result['passed'],screen=result,witnesses=witnesses)
        cases.append(record); print(case['name'],'all diagonal pairings',result['passed'],'reported pairs',len(pairs),flush=True)
        (OUT/'result.json').write_text(json.dumps(dict(complete=False,cases=cases),indent=2)+'\n',newline='\n')
report=dict(complete=True,passed=bool(cases) and all(c['passed'] for c in cases),cases=cases,
    sourceHashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('surface_intersections.py','curved_quad.py','tests/verify_toilet_all_diagonal_audit.py','assets/models/toilet.obj')},
    scope='Retained actual exports evaluated under all combinations of quad diagonals, with independent strict-interior LP witnesses for reported face pairs. This screen uses floating-point tolerances; witness absence does not clear boundary contacts or unresolved programs.')
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
raise SystemExit(0 if report['passed'] else 1)
