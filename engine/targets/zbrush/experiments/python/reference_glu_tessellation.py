"""Pinned independent Windows GLU reference; contains no ZBrush native entry calls."""
import ctypes as C
import hashlib,os
from pathlib import Path
import numpy as np
SHA='06c1d64c1fc3788d40b8ad65b365f653f75b8a0f06129760a783c225814d16ae'


def tessellate(points,offset=0):
    points=np.asarray(points,dtype='<f4');path=Path(os.environ['SystemRoot'])/'System32/glu32.dll'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SHA:raise RuntimeError('Reference GLU identity changed')
    dll=C.WinDLL(str(path));new=dll.gluNewTess;new.argtypes=[];new.restype=C.c_void_p;delete=dll.gluDeleteTess;delete.argtypes=[C.c_void_p];delete.restype=None;prop=dll.gluTessProperty;prop.argtypes=[C.c_void_p,C.c_uint32,C.c_double];prop.restype=None;callback=dll.gluTessCallback;callback.argtypes=[C.c_void_p,C.c_uint32,C.c_void_p];callback.restype=None
    for name in ['gluTessBeginContour','gluTessEndContour','gluTessEndPolygon']:
        fn=getattr(dll,name);fn.argtypes=[C.c_void_p];fn.restype=None
    begin=dll.gluTessBeginPolygon;begin.argtypes=[C.c_void_p,C.c_void_p];begin.restype=None;vertex=dll.gluTessVertex;vertex.argtypes=[C.c_void_p,C.POINTER(C.c_double),C.c_void_p];vertex.restype=None
    streams=[];triangles=[];errors=[];combines=[];current=[];mode=None;callbackErrors=[]
    def on_begin(kind,data):
        nonlocal current,mode
        current=[];mode=int(kind)
    def on_vertex(value,data):current.append(int(value or 0))
    def on_end(data):
        streams.append(dict(mode=mode,vertices=current.copy()))
        if mode==4:
            if len(current)%3:callbackErrors.append('Triangle list not multiple of3')
            triangles.extend([[offset+x for x in current[i:i+3]] for i in range(0,len(current),3)])
        elif mode==5:
            for i in range(len(current)-2):
                a,b,c=current[i:i+3];triangles.append([offset+a,offset+(c if i%2 else b),offset+(b if i%2 else c)])
        elif mode==6:triangles.extend([[offset+current[0],offset+current[i-1],offset+current[i]] for i in range(2,len(current))])
        else:callbackErrors.append('Unexpected primitive '+str(mode))
    def on_error(code,data):errors.append(int(code))
    def on_combine(coords,data,weights,result,user):
        combines.append(dict(coords=[coords[i] for i in range(3)],sources=[int(data[i] or 0) for i in range(4)],weights=[float(weights[i]) for i in range(4)]));result[0]=len(points)+1
    signatures=[(100106,C.WINFUNCTYPE(None,C.c_uint32,C.c_void_p),on_begin),(100107,C.WINFUNCTYPE(None,C.c_void_p,C.c_void_p),on_vertex),(100108,C.WINFUNCTYPE(None,C.c_void_p),on_end),(100109,C.WINFUNCTYPE(None,C.c_uint32,C.c_void_p),on_error),(100111,C.WINFUNCTYPE(None,C.POINTER(C.c_double),C.POINTER(C.c_void_p),C.POINTER(C.c_float),C.POINTER(C.c_void_p),C.c_void_p),on_combine)];callbacks=[];tess=new()
    if not tess:raise RuntimeError('Reference tessellator allocation failed')
    try:
        prop(tess,100140,100131.);prop(tess,100141,0.)
        for kind,typ,fn in signatures:
            cb=typ(fn);callbacks.append(cb);callback(tess,kind,C.cast(cb,C.c_void_p))
        begin(tess,None);dll.gluTessBeginContour(tess);keep=[]
        for i,point in enumerate(points):
            coords=(C.c_double*3)(float(point[0]),float(point[1]),0.);keep.append(coords);vertex(tess,coords,C.c_void_p(i))
        dll.gluTessEndContour(tess);dll.gluTessEndPolygon(tess)
    finally:delete(tess)
    return dict(triangles=triangles,streams=streams,combine=bool(combines),combineEvents=combines,error=bool(errors),errorCodes=errors,callbackErrors=callbackErrors,referenceSha256=SHA,scope='Independent public system GLU reference. Callback results only, not embedded library equivalence or complete tessellator recovery.')
