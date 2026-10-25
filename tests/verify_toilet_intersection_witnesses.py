"""Independent linear-program witnesses for detected adjacent-face overlaps."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'engine/targets/zbrush/experiments/python'))
from measure_geometry import read_obj


def witness(a, b):
    # Equal points in the two triangles, maximizing the minimum barycentric
    # coordinate. Positive margin proves an intersection inside BOTH triangles.
    equality = np.c_[a[1]-a[0], a[2]-a[0], -(b[1]-b[0]), -(b[2]-b[0]), np.zeros(3)]
    inequality = np.r_[np.c_[-np.eye(4), np.ones(4)], [[1,1,0,0,1], [0,0,1,1,1]]]
    result = linprog([0,0,0,0,-1], A_eq=equality, b_eq=b[0]-a[0], A_ub=inequality, b_ub=[0,0,0,0,1,1],
                     bounds=[(0,None)]*4+[(0,1/3)], method='highs')
    if not result.success or result.x[-1] < 1e-5:
        return None
    u,v,s,t,margin = result.x
    pa, pb = a[0]+u*(a[1]-a[0])+v*(a[2]-a[0]), b[0]+s*(b[1]-b[0])+t*(b[2]-b[0])
    error = float(np.linalg.norm(pa-pb))
    if error > 1e-9:
        return None
    return dict(point=pa.tolist(), barycentricA=[float(1-u-v),float(u),float(v)],
                barycentricB=[float(1-s-t),float(s),float(t)], minimumBarycentric=float(margin), equalityError=error)


records = []
for case in json.loads((ROOT/'tests/toilet-adjacent-contacts/result.json').read_text())['cases']:
    obj = ROOT/'tests/toilet-stress'/case['name']/'output.obj'
    assert hashlib.sha256(obj.read_bytes()).hexdigest() == case['outputSha256']
    vertices, faces = read_obj(obj)
    proofs = []
    for a,b in case['intersectingInteriorPairs']:
        found = None
        for i in range(1,len(faces[a])-1):
            for j in range(1,len(faces[b])-1):
                ta, tb = [faces[a][0],faces[a][i],faces[a][i+1]], [faces[b][0],faces[b][j],faces[b][j+1]]
                found = witness(vertices[ta], vertices[tb])
                if found:
                    proofs.append(dict(faces=[a,b], triangles=[ta,tb], **found)); break
            if found:
                break
    record = dict(name=case['name'], reportedPairs=len(case['intersectingInteriorPairs']), independentlyConfirmedPairs=len(proofs), witnesses=proofs)
    records.append(record)
    print(case['name'], 'confirmed', len(proofs), 'of', record['reportedPairs'], flush=True)
out = ROOT/'tests/toilet-adjacent-contacts/lp-witnesses.json'
out.write_text(json.dumps(dict(allReportedPairsConfirmed=all(c['reportedPairs']==c['independentlyConfirmedPairs'] for c in records),
    cases=records, verifierSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    scope='Independent HiGHS linear programs find equal XYZ points strictly inside both original triangles, minimum barycentric coordinate >=1e-5 and point equality error <=1e-9. Confirms reported positive contacts; does not search unreported pairs.'), indent=2)+'\n')
if not all(c['reportedPairs']==c['independentlyConfirmedPairs'] for c in records):
    raise SystemExit(1)
