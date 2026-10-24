"""EXP-0097: owned native integer-quarter float matrix producer0xe2f50."""
import ctypes as C,json,hashlib,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
SHA='0d45ea6f9331cecb55c12a10dcdb6d4bedb86cf302cd873748704dbaa82b00bc'
def quarter(q):
 k=int(q)%4;return [[1.,0.,0.,1.],[0.,1.,-1.,0.],[-1.,0.,0.,-1.],[0.,-1.,1.,0.]][k]
def main():
 out=ROOT/'work/zbrush/runtime/algorithm-recovery/quarter-matrix';dest=out/'result.json'
 if dest.exists():raise RuntimeError('Preserve prior result')
 path=Path(json.loads((ROOT/'targets/zbrush/target.local.json').read_text())['inputs']['engine']);assert hashlib.sha256(path.read_bytes()).hexdigest()==SHA
 with os.add_dll_directory(str(path.parent)):dll=C.CDLL(str(path))
 native=C.CFUNCTYPE(C.c_void_p,C.c_void_p,C.c_float)(dll._handle+0xe2f50);cases=[]
 for v in [float(i)+fraction for i in range(-16,17) for fraction in [0.,.25,.75]]:
  q=C.c_float(v).value;result=(C.c_float*4)();returned=native(C.addressof(result),q);got=list(result);expected=quarter(q);cases.append(dict(input=q,native=got,recovered=expected,passed=got==expected and returned==C.addressof(result)))
 result=dict(experimentId='EXP-0097',passed=all(c['passed'] for c in cases),engineSha256=SHA,cases=cases,scope='99 bounded finite positive/negative/integer/fractional float quarter inputs; integer truncation then normalized mod4, column-major exact unit rotation matrix and output pointer identity. Nonfinite/out-of-int32 range unsupported.')
 out.mkdir();dest.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],cases=len(cases))))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
