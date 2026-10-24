"""Delegate only sparse numerics to independently compiled upstream CHOLMOD.

Reviewed native wrappers use the same upstream family with simplicial LDL and
default AMD ordering/postorder. This is not Maxon's DLL, a captured solution,
or a transcription of every CHOLMOD branch. Initialize before input I/O guards.
"""
import ctypes as C
import hashlib,json
import numpy as np
from probe_brush_api import ROOT
DLL=ROOT/'work/zbrush/analysis/reference-cholmod-build-0683/reference_cholmod.dll'
EXPECTED='5a45a906d5d0dc64e7b4c141166c4e164d968ba9f5dbb5356912670f3ba850eb'
_library=None
_function=None

def initialize():
 global _library,_function
 if _function is not None:return
 if hashlib.sha256(DLL.read_bytes()).hexdigest()!=EXPECTED:raise ValueError('Unqualified reference compiler epoch')
 _library=C.CDLL(str(DLL));_function=_library.reference_solve
 _function.argtypes=[C.c_int,C.c_int,*([C.c_void_p]*7)];_function.restype=C.c_int

def source_paths():
 result=ROOT/'work/zbrush/analysis/reference-cholmod-build-0683/result.json'
 r=json.loads(result.read_text(encoding='utf-8'))
 if r['passed'] is not True:raise ValueError('Reference build must be qualified')
 paths=[ROOT/x['path'] for x in r['inputs']]+[result,DLL]
 for x in r['inputs']:
  if hashlib.sha256((ROOT/x['path']).read_bytes()).hexdigest()!=x['sha256']:raise ValueError('Changed compiled upstream source')
 return paths

def solve_sparse(matrix,rhs):
 if _function is None:raise RuntimeError('Declare and initialize reference backend before construction')
 H=matrix.tocsr();H.sort_indices();n,m=H.shape;rhs=np.ascontiguousarray(rhs,dtype='<f8')
 if n!=m or not n or rhs.shape!=(n,) or not np.isfinite(rhs).all() or not np.isfinite(H.data).all():raise ValueError('Finite nonempty symmetric system required')
 if (H-H.T).nnz:raise NotImplementedError('Only exactly symmetric systems are qualified')
 p=np.ascontiguousarray(H.indptr,dtype='<i4');i=np.ascontiguousarray(H.indices,dtype='<i4');a=np.ascontiguousarray(H.data,dtype='<f8');x=np.empty(n,dtype='<f8');perm=np.empty(n,dtype='<i4');info=np.empty(11,dtype='<f8')
 if int(H.indptr[-1])!=len(a) or len(a)>2147483647:raise ValueError('32-bit sparse index range required')
 ok=_function(n,len(a),*[v.ctypes.data for v in [p,i,a,rhs,x,perm,info]])
 if ok!=1 or not np.isfinite(x).all():raise RuntimeError('Independent CHOLMOD solve failed')
 return x
