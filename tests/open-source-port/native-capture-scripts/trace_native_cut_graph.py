"""Scoped Windows debugger for an owned synthetic host and its remesher child.
No command lines, authentication records, unrelated processes or installed bytes
are read/modified. One-shot software breakpoints restore original process memory.
Only reviewed geometry structures and scalar settings are captured.
"""
import argparse,ctypes as C,hashlib,json,os,shutil,struct,subprocess,time,traceback
from ctypes import wintypes as W
from pathlib import Path
import psutil
ROOT=Path('C:/dbva/code/ghidra-workbench')   # fork for retopo-1 (2026-11-13): outputs under native-captures/prep; stage script adds Keep Creases
ENGINE='0d45ea6f9331cecb55c12a10dcdb6d4bedb86cf302cd873748704dbaa82b00bc'
HOST='0fa10544438f5b7fe520a2a44b92183370001aacbd218daa96a65b179f45dff7'
k=C.WinDLL('kernel32',use_last_error=True)
def api(name,args,result=W.BOOL):
 f=getattr(k,name);f.argtypes=args;f.restype=result;return f
read=api('ReadProcessMemory',[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)])
write=api('WriteProcessMemory',[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)])
protect=api('VirtualProtectEx',[W.HANDLE,C.c_void_p,C.c_size_t,W.DWORD,C.POINTER(W.DWORD)])
flush=api('FlushInstructionCache',[W.HANDLE,C.c_void_p,C.c_size_t])
getctx=api('GetThreadContext',[W.HANDLE,C.c_void_p]);setctx=api('SetThreadContext',[W.HANDLE,C.c_void_p])
wait=api('WaitForDebugEvent',[C.c_void_p,W.DWORD]);cont=api('ContinueDebugEvent',[W.DWORD,W.DWORD,W.DWORD])
close=api('CloseHandle',[W.HANDLE]);pathof=api('GetFinalPathNameByHandleW',[W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD],W.DWORD)
kill=api('TerminateProcess',[W.HANDLE,W.UINT])
class DebugEvent(C.Structure):_fields_=[('code',W.DWORD),('pid',W.DWORD),('tid',W.DWORD),('padding',W.DWORD),('data',C.c_uint64*20)]
assert C.sizeof(DebugEvent)==176
REG={'rax':0x78,'rcx':0x80,'rdx':0x88,'rbp':0xa0,'rdi':0xb0,'r15':0xf0,'rsp':0x98,'r8':0xb8,'r9':0xc0,'rip':0xf8}
def check(ok):
 if not ok:raise C.WinError(C.get_last_error())
def mem(handle,address,n):
 if n<0 or n>32_000_000 or address<0x10000:raise ValueError('Invalid geometry read')
 b=C.create_string_buffer(n);got=C.c_size_t();check(read(handle,address,b,n,C.byref(got)));assert got.value==n;return b.raw

def u64(b,o=0):return struct.unpack_from('<Q',b,o)[0]
def i32(b,o=0):return struct.unpack_from('<i',b,o)[0]
def context(handle):
 b=C.create_string_buffer(1248+16);address=(C.addressof(b)+15)&~15
 C.memset(address,0,1232);C.c_uint32.from_address(address+0x30).value=0x10001f
 check(getctx(handle,address));return b,address,{name:C.c_uint64.from_address(address+off).value for name,off in REG.items()}
def vector(h,addr,stride,max_count=100000):
 b=mem(h,addr,24);start,end,capacity=struct.unpack('<QQQ',b)
 if not(start<=end<=capacity) or (end-start)%stride or (end-start)//stride>max_count:raise ValueError('Not a bounded vector '+hex(addr)+' '+str((start,end,capacity))+' stride='+str(stride))
 return mem(h,start,end-start) if end>start else b''
def span(h,addr,stride,max_count=100000):
 start,end=struct.unpack('<QQ',mem(h,addr,16))
 if start>end or (end-start)%stride or (end-start)//stride>max_count:raise ValueError('Invalid span '+str((start,end,stride)))
 return mem(h,start,end-start) if end>start else b''

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--name',required=True);ap.add_argument('--angular-callbacks',type=int,default=1);ap.add_argument('--guide-walks',type=int,default=1);ap.add_argument('--triangle-cuts',type=int,default=1);ap.add_argument('--boundary-cuts',type=int,default=1);args=ap.parse_args()
 if not 1<=args.boundary_cuts<=512:raise ValueError('Bounded boundary cut capture count required')
 if not 1<=args.triangle_cuts<=512:raise ValueError('Bounded triangle cut capture count required')
 if not 1<=args.guide_walks<=64:raise ValueError('Bounded guide walk capture count required')
 if not 1<=args.angular_callbacks<=512:raise ValueError('Bounded callback capture count required')
 if any(p.info['name'].lower()=='zbrush.exe' for p in psutil.process_iter(['name'])):raise RuntimeError('Existing user session preserved')
 parent=Path(__file__).resolve().parents[2]/'prep';out=parent/args.name
 if Path(args.name).name!=args.name or out.exists():raise ValueError('Choose new owned run name')
 local=json.loads((ROOT/'targets/zbrush/target.local.json').read_text());host=Path(local['inputs']['host']);engine=Path(local['inputs']['engine'])
 assert hashlib.sha256(host.read_bytes()).hexdigest()==HOST and hashlib.sha256(engine.read_bytes()).hexdigest()==ENGINE
 out.mkdir(parents=True);shutil.copy2(args.config,out/'config.json');shutil.copy2(Path(__file__).with_name('native_geometry_stage.py'),out/'stage.py');shutil.copy2(__file__,out/'debugger.py')
 record=dict(hostSha256=HOST,engineSha256=ENGINE,method='DEBUG_PROCESS on owned supported -batch -script launch; one-shot geometry breakpoints only',events=[],captures=[],started=time.time(),status='running')
 handles={};threads={};bps={};first=set();alive=set();serial=0;solver_calls=0;angular_calls=0;components={};integer_phase=set();integer_batches=0;angular_direct_phase=set();angular_solvers={};grid_current={}
 def save():
  temp=out/'trace.json.tmp';temp.write_text(json.dumps(record,indent=2)+'\n')
  for attempt in range(21):
   try:temp.replace(out/'trace.json');break
   except PermissionError:
    if attempt==20:raise
    time.sleep(.05)  # Windows readers may briefly deny rename/delete sharing.
 def put(pid,addr,value):
  h=handles[pid];old=W.DWORD();check(protect(h,addr,len(value),0x40,C.byref(old)))
  try:check(write(h,addr,value,len(value),None));check(flush(h,addr,len(value)))
  finally:prior=W.DWORD();check(protect(h,addr,len(value),old.value,C.byref(prior)))
 def breakpoint(pid,addr,tag,payload=None):
  if (pid,addr) in bps:raise RuntimeError('Breakpoint collision')
  original=mem(handles[pid],addr,1);put(pid,addr,b'\xcc');bps[pid,addr]=(original,tag,payload)
 def dump(pid,label,obj,kind):
  nonlocal serial
  serial+=1;h=handles[pid];folder=out/(f'{serial:02d}-'+label);folder.mkdir();meta=dict(pid=pid,label=label,object=hex(obj) if isinstance(obj,int) else {key:hex(value) for key,value in obj.items()},kind=kind,files=[],errors=[])
  def raw(name,blob):
   dest=folder/name;dest.write_bytes(blob);meta['files'].append(dict(file=name,sha256=hashlib.sha256(blob).hexdigest(),bytes=len(blob)))
  def vec(name,offset,stride):
   try:raw(name,vector(h,obj+offset,stride))
   except Exception as e:meta['errors'].append(name+': '+str(e))
  def mesh_channels(mesh,prefix,dim):
   try:
    vb=u64(mem(h,mesh,8));vbase=i32(mem(h,vb+0x10,4));fbase=i32(mem(h,vb+0xc,4))
    raw(prefix+'mesh-header.bin',mem(h,mesh,0x100));raw(prefix+'vbtable.bin',mem(h,vb,32));raw(prefix+'position-header.bin',mem(h,mesh+vbase,64))
    raw(prefix+'positions.f32x'+str(dim),span(h,mesh+vbase+8,12) if dim==3 else vector(h,u64(mem(h,mesh+vbase+8,8)),8))
    raw(prefix+'triangles.i32x3',vector(h,u64(mem(h,mesh+fbase+0x18,8)),12))
    if dim==3:
     topology=u64(mem(h,mesh+fbase+0x28,8))
     for offset,name,stride in [(0x38,'edges.i32x2',8),(0x58,'edge-face-offset.i32',4),(0x70,'edge-face-corners.i32',4),(0x20,'face-edges.i32x3',12),(0xb8,'vertex-edge-offset.i32',4),(0xd0,'vertex-edge-list.i32',4)]:raw(prefix+name,vector(h,topology+offset,stride))
     face_geometry=u64(mem(h,mesh+0x58,8));raw(prefix+'normal.f32x3',vector(h,face_geometry+0x20,12))
   except Exception as e:meta['errors'].append(prefix+': '+str(e))
  if kind=='field':
   raw('field-structure.bin',mem(h,obj,0x510))
   mesh_channels(u64(mem(h,obj+8,8)),'source-',3)
   mark=mem(h,obj+0x340,24);nbits=u64(mark,16)
   if nbits<100000:raw('vertex-marks.bits',mem(h,u64(mark),(nbits+7)//8))
   excluded=mem(h,obj+0x2c0,24);nbits=u64(excluded,16)
   if nbits<100000:raw('excluded-faces.bits',mem(h,u64(excluded),(nbits+7)//8))
   excluded=mem(h,obj+0x2d8,24);nbits=u64(excluded,16)
   if nbits<100000:raw('excluded-vertices.bits',mem(h,u64(excluded),(nbits+7)//8) if nbits else b'')
   scales=vector(h,obj+0xc8,0x1a0)
   for j in range(0,len(scales),0x1a0):
    raw(f'scale-{j//0x1a0}-header.bin',scales[j:j+0x1a0])
    valid=mem(h,u64(mem(h,obj+0xc8,8))+j+0xc8,24);nbits=u64(valid,16)
    if nbits<100000:raw(f'scale-{j//0x1a0}-valid.bits',mem(h,u64(valid),(nbits+7)//8))
    window=mem(h,u64(mem(h,obj+0xc8,8))+j+0x110,24);nbits=u64(window,16)
    if nbits<100000:raw(f'scale-{j//0x1a0}-window.bits',mem(h,u64(window),(nbits+7)//8) if nbits else b'')
    for off,name,stride in [(8,'vertex-tensor.f64x6',48),(0x38,'face-direction.f32x3',12),(0x68,'lambda-mid.f32',4),(0x80,'lambda-max.f32',4)]:
     try:raw(f'scale-{j//0x1a0}-'+name,vector(h,u64(mem(h,obj+0xc8,8))+j+off,stride))
     except Exception as e:meta['errors'].append('scale '+name+': '+str(e))
   scores=vector(h,obj+0x280,24)
   for j in range(0,len(scores),24):raw(f'scale-{j//24}-score.f32',vector(h,u64(mem(h,obj+0x280,8))+j,4))
   curveptrs=vector(h,obj+0x98,8)
   for j in range(0,len(curveptrs),8):
    curve=u64(curveptrs,j)
    if curve:
     raw(f'curve-{j//8}-structure.bin',mem(h,curve,0x4a8))
     for offset,name,stride in [(0x118,'source-points.f32x3',12),(0x238,'projected-points.f32x3',12),(0x268,'embedded.i32x2',8),(0x280,'mode0-indices.i32',4),(0x460,'alternate-points.f32x3',12),(0x490,'alternate-embedded.i32x2',8)]:
      try:raw(f'curve-{j//8}-'+name,span(h,curve+offset,stride))
      except Exception as e:meta['errors'].append('curve '+name+': '+str(e))
   for offset,name,stride in [(0x418,'selected-scale.i32',4),(0x430,'valid-scale-count.i32',4),(0x448,'window-scale-count.i32',4),(0x118,'directions.f32x3',12),(0x148,'lambda-mid.f32',4),(0x160,'lambda-max.f32',4),(0x220,'face-flags.u8',1),(0x238,'face-weights.f32',4),(0x298,'scale-curvature-threshold.f32',4),(0x3b8,'normalized-guide-distance.f32',4),(0x2f8,'edge-angle.f32',4),(0x310,'edge-tangent.f32x3',12),(0x328,'edge-tensor.f64x6',48)]:vec(name,offset,stride)
  elif kind in ['cutpre','cuttri']:
   raw('cut-options.bin',mem(h,obj['cut'],0x18));mesh_channels(u64(mem(h,obj['cut'],8)),'source-',3);pointers=vector(h,obj['inputRecords'],8);raw('input-record-pointers.bin',pointers)
   for j in range(0,len(pointers),8):
    address=u64(pointers,j);raw(f'input-{j//8}-record.bin',mem(h,address,0x78))
    for offset,name,stride in [(0,'points.f32x3',12),(0x18,'edges.i32',4),(0x30,'edge-parameters.f32',4),(0x48,'faces.i32',4)]:raw(f'input-{j//8}-'+name,vector(h,address+offset,stride))
   if kind=='cutpre':
    records=vector(h,obj['outputRecords'],0x78);raw('output-records.bin',records);begin=u64(mem(h,obj['outputRecords'],8))
    for j in range(0,len(records),0x78):
     for offset,name,stride in [(0,'points.f32x3',12),(0x18,'edges.i32',4),(0x30,'edge-parameters.f32',4),(0x48,'faces.i32',4)]:raw(f'output-{j//0x78}-'+name,vector(h,begin+j+offset,stride))
   else:
    for name in ['mapA','mapB']:
     records=vector(h,obj[name],24);begin=u64(mem(h,obj[name],8))
     for j in range(0,len(records),24):raw(f'{name}-{j//24}.i32',vector(h,begin+j,4))
  elif kind=='planar-triangulation':
   raw('triangulator-output-header.bin',mem(h,obj['output'],0x38));raw('input-points.f64x2',vector(h,obj['points'],16));raw('input-segments.i32x2',vector(h,obj['segments'],8));raw('output-triangles.i32x3',vector(h,obj['output'],12));raw('output-points.f64x2',vector(h,obj['output']+0x18,16))
  elif kind=='angular-full-direct':
   raw('solution.f64',vector(h,obj['output'],8));raw('rhs.f64',vector(h,obj['rhs'],8));raw('driver-counters.bin',mem(h,obj['solver']+0x1ac,0x14));dump(pid,label+'-matrix',obj['matrix'],'matrix')
  elif kind=='guide-group-builder':
   component=obj['component'];dump(pid,label+'-component',component,'component')
   for offset,name,stride in [(0x9b8,'constrained-source-edges.i32',4),(0x9d0,'source-edge-modes.u8',1),(0x9e8,'group-offsets.i32',4),(0xa00,'group-parameter-edges.i32',4),(0xa18,'group-roots.i32',4),(0xa30,'group-axis.u8',1),(0xa48,'edge-guide-mode.u8',1)]:raw(name,vector(h,component+offset,stride))
   mask=mem(h,component+0xa60,24);nbits=u64(mask,16);assert nbits<100000;raw('skip-source-edge-logical-count.u64',struct.pack('<Q',nbits));raw('skip-source-edge.bits',mem(h,u64(mask),(nbits+7)//8) if nbits else b'')
  elif kind=='guide-equality-builder':
   component=obj['component'];raw('component-structure.bin',mem(h,component,0xc48))
   for offset,name,stride in [(0x9e8,'group-offsets.i32',4),(0xa00,'group-parameter-edges.i32',4),(0xa18,'group-roots.i32',4),(0xa30,'group-axis.u8',1),(0xa48,'edge-guide-mode.u8',1),(0xa98,'scalar-flags.u8',1),(0xab0,'scalar-denominators.i32',4)]:raw(name,vector(h,component+offset,stride))
   mask=mem(h,component+0xa60,24);nbits=u64(mask,16);assert nbits<100000;raw('skip-endpoint-logical-count.u64',struct.pack('<Q',nbits));raw('skip-endpoint-marks.bits',mem(h,u64(mask),(nbits+7)//8) if nbits else b'')
   raw('preferred-original-scalars.i32',vector(h,obj['preferred'],4));raw('original-to-existing-dependency.i32',vector(h,obj['mapping'],4));dump(pid,label+'-constraint-rows',obj['rows'],'matrix')
   for key,prefix in [('output','direct'),('existing','existing')]:
    records=vector(h,obj[key],32);begin=u64(mem(h,obj[key],8));constraints=[]
    for j in range(0,len(records),32):
     terms=vector(h,begin+j+8,16);constraints.append(dict(dependent=i32(records,j),terms=[[i32(terms,i),struct.unpack_from('<d',terms,i+8)[0]] for i in range(0,len(terms),16)]))
    raw(prefix+'-dependencies.json',json.dumps(constraints).encode())
   if label.startswith('entry-'):dump(pid,label+'-component',component,'component')
  elif kind=='dependency-expansion':
   raw('policy.i32x5',mem(h,obj['policy'],20));raw('original-to-dependency.i32',vector(h,obj['mapping'],4))
   for key,prefix in [('target','target'),('provider','provider')]:
    records=vector(h,obj[key],32);begin=u64(mem(h,obj[key],8));constraints=[]
    for j in range(0,len(records),32):
     terms=vector(h,begin+j+8,16);constraints.append(dict(dependent=i32(records,j),terms=[[i32(terms,i),struct.unpack_from('<d',terms,i+8)[0]] for i in range(0,len(terms),16)]))
    raw(prefix+'-dependencies.json',json.dumps(constraints).encode())
   raw('self-alias.u8',bytes([obj['target']==obj['provider']]))
  elif kind=='cut-path-enumeration':
   raw('selected-edge-ids.i32',vector(h,obj['selected'],4));raw('options.bin',mem(h,obj['options'],32));seed=u64(mem(h,obj['options'],8));nodes=u64(mem(h,obj['options']+0x10,8))
   if seed:raw('forced-vertex-seeds.i32',vector(h,seed,4))
   if nodes:raw('output-node-ids.i32',vector(h,nodes,4))
   for key,prefix in [('edgeGroups','edge'),('vertexGroups','vertex')]:
    raw(prefix+'-offsets.i32',vector(h,obj[key],4));raw(prefix+'-list.i32',vector(h,obj[key]+0x18,4))
  elif kind=='paired-cut-path':
   raw('source-edges.i32',span(h,obj['edges'],4));raw('source-vertices.i32',span(h,obj['vertices'],4));raw('side-a.i32',vector(h,obj['sideA'],4));raw('side-b.i32',vector(h,obj['sideB'],4))
   if label.startswith('return-'):raw('quarter.i32',mem(h,obj['quarter'],4))
   if not any(c['kind']=='paired-cut-path-common' for c in record['captures']):dump(pid,label+'-component',obj['component'],'component');meta['kind']='paired-cut-path-common'
  elif kind=='integer-constraint-elimination':
   raw('policy.bin',mem(h,obj['policy'],48));raw('preferred-original-scalars.i32',vector(h,obj['policy']+0x10,4));raw('dimension.i32',struct.pack('<i',obj['dimension']));records=vector(h,obj['dependencies'],32);begin=u64(mem(h,obj['dependencies'],8));constraints=[]
   for j in range(0,len(records),32):
    terms=vector(h,begin+j+8,16);constraints.append(dict(dependent=i32(records,j),terms=[[i32(terms,i),struct.unpack_from('<d',terms,i+8)[0]] for i in range(0,len(terms),16)]))
   raw('dependencies.json',json.dumps(constraints).encode());dump(pid,label+'-row-vectors',obj['rows'],'matrix')
  elif kind=='chain-integral':
   raw('path.i32',span(h,obj['path'],4));raw('axis.i32',struct.pack('<i',obj['axis']))
   if label.startswith('return-'):
    raw('integral.f32',mem(h,obj['output'],4))
    if not any(c['kind']=='chain-integral-common' for c in record['captures']):
     component=obj['component'];dump(pid,label+'-component',component,'component');mesh=u64(mem(h,component+0x10,8));uv=u64(mem(h,mesh+0x28,8));vb=u64(mem(h,uv,8));facebase=i32(mem(h,vb+0xc,4));topology=u64(mem(h,uv+facebase+0x28,8))
     for offset,name,stride in [(0x38,'parameter-edges.i32x2',8),(0x58,'parameter-edge-face-offset.i32',4),(0x70,'parameter-edge-face-corners.i32',4),(0xb8,'parameter-vertex-edge-offset.i32',4),(0xd0,'parameter-vertex-edge-list.i32',4)]:raw(name,vector(h,topology+offset,stride))
     raw('parameter-to-source.i32',vector(h,uv+0x28,4));raw('original-to-outer-reduced.i32',vector(h,component+0xb98,4));meta['kind']='chain-integral-common'
  elif kind=='grid-step':
   meta['walkOrdinal']=obj['ordinal'];raw('face.i32',mem(h,obj['face'],4));raw('uv.f32x2',mem(h,obj['uv'],8));raw('direction.i32',mem(h,obj['outputDirection'],4))
  elif kind=='grid-walk':
   raw('input-node.bin',mem(h,obj['node'],0x90));raw('input-direction.i32',struct.pack('<I',obj['direction']));raw('face.i32',mem(h,obj['face'],4));raw('uv.f32x2',mem(h,obj['uv'],8));raw('policy.u8',bytes([obj['policy']]));raw('link-flag.u8',mem(h,obj['link'],1))
   if label.startswith('return-'):
    raw('output-node-pointer.bin',mem(h,obj['output'],8));raw('output-direction.i32',mem(h,obj['outputDirection'],4));destination=u64(mem(h,obj['output'],8))
    if destination:raw('output-node.bin',mem(h,destination,0x90))
   if not any(c['kind']=='grid-walk-common' for c in record['captures']):
    component=obj['component'];dump(pid,'grid-walk-component',component,'component');raw('extraction-component.bin',mem(h,component,0xd10));raw('walk-settings.bin',mem(h,obj['remesher']+0x6a0,16));meta['kind']='grid-walk-common'
  elif kind=='integer-geometric-regions':
   frame=obj['frame'];raw('axis.i64',mem(h,frame-0x28,8))
   for offset,name,stride in [(0,'candidate-regions.i32x2',8),(0x38,'candidate-edges.i32',4),(-0x88,'candidate-costs.f32',4),(0x130,'all-candidate-regions.i32x2',8),(0x110,'all-candidate-edges.i32',4),(0x208,'all-candidate-costs.f32',4),(0x18,'candidate-scalars.i32x2',8),(0x80,'candidate-gaps.f32',4)]:raw(name,vector(h,frame+offset,stride))
  elif kind=='integer-geometric-front':
   frame=obj['frame'];raw('axis.i64',mem(h,frame-0x28,8));raw('queue-head-tail.i32x2',mem(h,frame-0xa8,8))
   for offset,name in [(-0xb0,'distance.f32'),(-0x10,'owner.i32'),(-0x30,'root.i32'),(0xc0,'parent-edge.i32')]:raw(name,vector(h,u64(mem(h,frame+offset,8)),4))
   raw('queue-next.i32',vector(h,frame-0xa0,4));raw('component-structure.bin',mem(h,components[pid],0xc48))
  elif kind=='integer-dependency-substitution':
   raw('residual-targets.f64',vector(h,components[pid]+0x960,8));raw('residual-weights.f64',vector(h,components[pid]+0x918,8));raw('policy.i32x5',mem(h,obj['policy'],20));raw('original-to-dependency.i32',vector(h,obj['mapping'],4));records=vector(h,obj['dependencies'],32);begin=u64(mem(h,obj['dependencies'],8));constraints=[]
   for j in range(0,len(records),32):
    terms=vector(h,begin+j+8,16);constraints.append(dict(dependent=i32(records,j),terms=[[i32(terms,i),struct.unpack_from('<d',terms,i+8)[0]] for i in range(0,len(terms),16)]))
   raw('dependencies.json',json.dumps(constraints).encode());dump(pid,label+'-matrix',obj['matrix'],'matrix')
  elif kind=='integer-column-compression':
   raw('original-dimension.i32',struct.pack('<i',obj['dimension']));dump(pid,label+'-matrix',obj['matrix'],'matrix')
   for key,name in [('forward','original-to-reduced.i32'),('inverse','reduced-to-original.i32')]:
    if obj[key]:raw(name,vector(h,obj[key],4))
  elif kind=='integer-back-transfer':
   raw('component-structure.bin',mem(h,obj['component'],0xc48));raw('reserved-constant.i32',mem(h,obj['component']+0x978,4));raw('outer-reduced-to-original.i32',vector(h,obj['component']+0xbb0,4));solver=u64(mem(h,obj['component']+0xa78,8));raw('outer-integer-indices.i32',vector(h,solver+0x18,4));raw('outer-integer-steps.f64',vector(h,solver+0x30,8))
   for key,name,stride in [('solution','nested-solution.f64',8),('forward','original-to-reduced.i32',4),('dependencyMap','original-to-dependency.i32',4)]:raw(name,vector(h,obj[key],stride))
   raw('selected-outer-list-positions.i32',vector(h,obj['request']+0x18,4));raw('selected-values.f64',vector(h,obj['request']+0x30,8));records=vector(h,obj['dependencies'],32);begin=u64(mem(h,obj['dependencies'],8));constraints=[]
   for j in range(0,len(records),32):
    terms=vector(h,begin+j+8,16);constraints.append(dict(dependent=i32(records,j),terms=[[i32(terms,i),struct.unpack_from('<d',terms,i+8)[0]] for i in range(0,len(terms),16)]))
   raw('dependencies.json',json.dumps(constraints).encode())
  elif kind=='integer-batch':
   for key,name,stride in [('solution','solution.f64',8),('indices','integer-indices.i32',4),('steps','integer-steps.f64',8),('selected','selected-list-indices.i32',4),('values','selected-values.f64',8)]:raw(name,vector(h,obj[key],stride))
   raw('budget.f64',mem(h,obj['budget'],8));raw('threshold.f64',mem(h,obj['threshold'],8));mask=mem(h,obj['fixed'],24);nbits=u64(mask,16);assert nbits<100000;raw('fixed-logical-count.u64',struct.pack('<Q',nbits));raw('fixed-list-positions.bits',mem(h,u64(mask),(nbits+7)//8) if nbits else b'')
  elif kind=='positive-integer-callback':
   raw('callback-request.bin',mem(h,obj['request'],0x68));raw('driver-base.bin',mem(h,obj['driver'],0x40));solver=u64(mem(h,obj['driver']+8,8));component=u64(mem(h,obj['driver']+0x10,8));mapping=u64(mem(h,obj['driver']+0x28,8));raw('reduced-to-original.i32',vector(h,mapping,4));raw('reserved-positive-start.i32',mem(h,component+0x97c,4));raw('solution.f64',vector(h,u64(mem(h,obj['request']+8,8)),8));raw('integer-indices.i32',vector(h,solver+0x18,4));raw('integer-steps.f64',vector(h,solver+0x68,8));raw('selected-list-indices.i32',vector(h,obj['request']+0x18,4));raw('selected-values.f64',vector(h,obj['request']+0x30,8))
  elif kind=='uv-gradient':
   raw('source-face.i32',struct.pack('<i',obj['face']));mesh_channels(obj['mesh'],'source-',3);mesh_channels(u64(mem(h,obj['mesh']+0x28,8)),'parameter-',2)
   if label.startswith('return-'):raw('gradient-u.f32x3',mem(h,obj['u'],12));raw('gradient-v.f32x3',mem(h,obj['v'],12))
  elif kind=='parameter-weight-smoothing':
   raw('weight-multipliers.f64',vector(h,obj['weights'],8));raw('face-residual-start.i32',vector(h,obj['component']+0xb80,4));raw('edge-constraint-tags.u8',vector(h,obj['component']+0x9d0,1));raw('iteration-count.u32',struct.pack('<I',obj['iterations']));dump(pid,label+'-component',obj['component'],'component')
  elif kind=='parameter-callback':
   raw('callback-request.bin',mem(h,obj['request'],0x68));raw('parameter-settings.bin',mem(h,obj['remesher']+0x688,0x40));raw('solution.f64',vector(h,u64(mem(h,obj['request']+8,8)),8));raw('face-residual-start.i32',vector(h,obj['component']+0xb80,4));dump(pid,label+'-component',obj['component'],'component')
   for offset,name,stride in [(0,'normal-offsets.i32',4),(0x18,'normal-indices.i32',4),(0x30,'normal-values.f64',8)]:raw(name,vector(h,obj['component']+0xbc8+offset,stride,1000000))
   raw('normal-rhs.f64',vector(h,obj['component']+0xc20,8))
   raw('requested-fixed-indices.i32',vector(h,obj['request']+0x18,4));raw('requested-fixed-values.f64',vector(h,obj['request']+0x30,8))
   component=obj['component'];dump(pid,label+'-integer-phase-residuals',component+0x8f0,'matrix')
   for offset,name,stride in [(0x918,'integer-phase-weights.f64',8),(0x930,'integer-phase-channel930.i32',4),(0x960,'integer-phase-targets.f64',8),(0x9e8,'integer-chain-offsets.i32',4),(0xa00,'integer-chain-list.i32',4)]:raw(name,vector(h,component+offset,stride))
  elif kind=='polygon-conversion':
   raw('conversion-options.bin',mem(h,obj['options'],0x20))
   for key in ['input','output']:
    mesh=obj[key];vb=u64(mem(h,mesh,8));vbase=i32(mem(h,vb+0x10,4));fbase=i32(mem(h,vb+0xc,4));face=mesh+fbase;raw(key+'-face-kind.i32',mem(h,face+0x24,4));raw(key+'-positions.f32x3',span(h,mesh+vbase+8,12));raw(key+'-face-indices.i32',vector(h,u64(mem(h,face+0x18,8)),4))
    if i32(mem(h,face+0x24,4))==0:raw(key+'-face-offsets.i32',vector(h,u64(mem(h,face+0x10,8)),4))
  elif kind in ['triangle-cut','boundary-cut']:
   raw('polygon-offsets.i32',vector(h,obj['polygon'],4));raw('polygon-indices.i32',vector(h,obj['polygon']+0x18,4));raw('new-positions.f32x3',vector(h,obj['newPositions'],12));raw('source-positions.f32x3',span(h,obj['sourcePositions'],12));raw('constraints.f64x2-i32x2',span(h,obj['constraints'],24))
  elif kind=='guide-walk':
   raw('walk-context.bin',mem(h,obj['context'],0x78));raw('start-point-attachment.bin',mem(h,obj['start'],20));raw('end-point-attachment.bin',mem(h,obj['end'],20));raw('walk-repair-flag.bin',mem(h,obj['flag'],1));raw('source-positions.f32x3',span(h,obj['positions'],12))
   for offset,name,stride in [(0x38,'source-triangles.i32x3',12),(0x40,'source-edges.i32x2',8),(0x48,'source-face-edges.i32x3',12),(0x68,'source-normal.f32x3',12)]:raw(name,vector(h,u64(mem(h,obj['context']+offset,8)),stride))
   for offset,name in [(0x50,'vertex-corner'),(0x58,'edge-corner'),(0x60,'vertex-edge')]:
    channel=u64(mem(h,obj['context']+offset,8));raw(name+'-offsets.i32',vector(h,channel,4));raw(name+'-entries.i32',vector(h,channel+0x18,4))
   for offset,name,stride in [(0,'walk-edges.i32',4),(0x18,'walk-faces.i32',4),(0x30,'walk-parameters.f32',4),(0x48,'walk-points.f32x3',12)]:raw(name,vector(h,obj['output']+offset,stride))
  elif kind=='guide-relocate':
   mesh_channels(obj['mesh'],'source-',3);raw('update-options.bin',mem(h,obj['update'],0x30));raw('requested-positions.f32x3',vector(h,u64(mem(h,obj['update'],8)),12));raw('requested-vertices.i32',vector(h,u64(mem(h,obj['update']+8,8)),4))
  elif kind=='projection':
   raw('projection-options.bin',mem(h,obj['options'],8));raw('input-points.f32x3',span(h,obj['points'],12));raw('input-attributes.i32',span(h,obj['attributes'],4));mesh_channels(obj['mesh'],'source-',3)
   target=obj['output'];raw('attached-polyline-header.bin',mem(h,target,0x80))
   for offset,name,stride in [(8,'output-points.f32x3',12),(0x38,'output-attachments.i32x2',8),(0x50,'output-faces.i32',4),(0x68,'output-attributes.i32',4)]:raw(name,vector(h,target+offset,stride))
  elif kind=='segmentation':
   raw('projector-options.bin',mem(h,obj['projector'],0x28));mesh_channels(u64(mem(h,obj['projector']+0x10,8)),'source-',3);raw('attached-polyline-header.bin',mem(h,obj['polyline'],0x80))
   for offset,name,stride in [(8,'input-points.f32x3',12),(0x38,'input-attachments.i32x2',8),(0x50,'input-faces.i32',4)]:raw(name,vector(h,obj['polyline']+offset,stride))
   records=vector(h,obj['records'],0x78);raw('segment-records.bin',records);baseRecords=u64(mem(h,obj['records'],8))
   for j in range(0,len(records),0x78):
    for offset,name,stride in [(0,'points.f32x3',12),(0x18,'edges.i32',4),(0x30,'edge-parameters.f32',4),(0x48,'faces.i32',4),(0x60,'attributes.i32',4)]:raw(f'segment-{j//0x78}-'+name,vector(h,baseRecords+j+offset,stride))
  elif kind=='guideprep':
   mesh_channels(u64(mem(h,obj+0x10,8)),'source-',3);curves=vector(h,obj+0x30,8);raw('curve-pointers.bin',curves)
   for j in range(0,len(curves),8):
    curve=u64(curves,j)
    if not curve:continue
    raw(f'curve-{j//8}-structure.bin',mem(h,curve,0x4a8))
    for offset,name,stride in [(0x118,'points.f32x3',12),(0x148,'attachments.i32x2',8),(0x160,'faces.i32',4),(0x238,'embedded-points.f32x3',12),(0x268,'embedded.i32x2',8)]:raw(f'curve-{j//8}-'+name,vector(h,curve+offset,stride))
  elif kind=='pcg':
   raw('pcg-settings.bin',mem(h,obj['settings'],0x30))
   for key,stride,suffix in [('solution',8,'f64'),('seeds',4,'i32'),('rhs',8,'f64')]:raw(key+'.'+suffix,vector(h,obj[key],stride))
   dump(pid,label+'-matrix',obj['matrix'],'matrix')
  elif kind=='angular':
   raw('callback-request.bin',mem(h,obj,0x68));component=u64(mem(h,obj+0x60,8));raw('angular-component.bin',mem(h,component,0xc48));state=u64(mem(h,component+0x4a8,8));raw('angular-state.bin',mem(h,state,0x180))
   raw('solution.f64',vector(h,u64(mem(h,obj+8,8)),8));raw('face-to-variable.i32',vector(h,u64(mem(h,component+0xa88,8)),4))
   for offset,name,stride in [(0x360,'target-angle.f64',8),(0x3d8,'connection-angle.f32',4),(0x478,'fixed-angle.f32',4)]:raw(name,vector(h,component+offset,stride))
   field=u64(mem(h,component+0x240,8));raw('constraint-weights.f32',vector(h,field+0x238,4));raw('quarter-transitions.i32',vector(h,component+0x490,4))
   for offset,name in [(0x268,'target-constrained-faces.bits'),(0x348,'excluded-smoothing-edges.bits')]:
    mask=mem(h,component+offset,24);nbits=u64(mask,16);assert nbits<100000
    raw(name,mem(h,u64(mask),(nbits+7)//8) if nbits else b'')
   for offset,name,stride in [(0x90,'edge-next.i32',4),(0xa8,'edge-prev.i32',4),(0xc0,'face-next.i32',4),(0xd8,'face-prev.i32',4),(0xf8,'edge-fraction.f64',8),(0x110,'edge-round.f64',8),(0x128,'face-fraction.f64',8),(0x140,'face-round.f64',8),(0x168,'changed-variables.i32',4)]:raw(name,vector(h,state+offset,stride))
   raw('active-edge-map.i32',vector(h,u64(mem(h,state+0x88,8)),4));raw('bin-thresholds.f64',mem(h,u64(mem(h,state+8,8)),56))
   topology=u64(mem(h,state+0xf0,8));raw('edge-corner-offset.i32',vector(h,topology,4));raw('edge-corners.i32',vector(h,topology+0x18,4))
   for offset,prefix in [(0x20,'edge'),(0x38,'face')]:
    bins=u64(mem(h,state+offset,8))
    for j in range(8):raw(f'{prefix}-bin-{j}.i32',vector(h,bins+j*24,4))
   dump(pid,label+'-system',u64(mem(h,component+0xa78,8)),'solver')
  elif kind=='component':
   raw('component-structure.bin',mem(h,obj,0xc48))
   for offset,name in [(0x558,'cut-edges.bits'),(0x848,'edge-axis.bits')]:
    mask=mem(h,obj+offset,24);nbits=u64(mask,16)
    if nbits<100000:raw(name,mem(h,u64(mask),(nbits+7)//8))
   vec('face-gauge.i32',0x8c0,4);vec('constrained-edges.i32',0x9b8,4)
   for offset,name,stride in [(0x378,'basis-a.f32x3',12),(0x390,'basis-b.f32x3',12),(0x3c0,'local-length.f32',4),(0x478,'solved-angle.f32',4),(0x490,'quarter-transitions.i32',4),(0x890,'uv-direction-a.f32x2',8),(0x8a8,'uv-direction-b.f32x2',8),(0x3a8,'triangle-permutation.u8',1),(0x360,'target-angle.f64',8),(0x3d8,'connection-angle.f32',4),(0x6d8,'scale-a.f32',4),(0x6f0,'scale-b.f32',4),(0x8d8,'transitions.i32',4),(0xa98,'integer-flags.u8',1),(0xab0,'integer-denominators.i32',4),(0xbb0,'reduced-to-original.i32',4),(0xb50,'rhs.f64',8),(0xb68,'weights.f64',8)]:vec(name,offset,stride)
   for offset,name,stride in [(0x4b0,'source-seed-vertices.i32',4),(0x4c8,'source-seed-types.i32',4),(0x4e0,'source-seed-flags.u8',1),(0x600,'cut-path-source-nodes.i32',4),(0x618,'cut-path-edge-offset.i32',4),(0x630,'cut-path-source-edges.i32',4),(0x678,'cut-path-quarter-turns.f32',4),(0x5a0,'extra-cut-edges.i32',4),(0x4f8,'fallback-seeds.i32',4)]:vec(name,offset,stride)
   for offset,name in [(0x648,'cut-path-side-a'),(0x660,'cut-path-side-b')]:
    groups=vector(h,obj+offset,24);begin=u64(mem(h,obj+offset,8))
    for j in range(0,len(groups),24):raw(name+'-'+str(j//24)+'.i32',vector(h,begin+j,4))
   records=vector(h,obj+0x980,32);raw('constraint-records.bin',records);rowbase=u64(mem(h,obj+0x980,8));constraints=[]
   for j in range(0,len(records),32):
    terms=vector(h,rowbase+j+8,16);constraints.append(dict(dependent=i32(records,j),terms=[[i32(terms,i),struct.unpack_from('<d',terms,i+8)[0]] for i in range(0,len(terms),16)]))
   raw('constraints.json',json.dumps(constraints).encode())
   mesh=u64(mem(h,obj+0x10,8));mesh_channels(mesh,'source-',3);mesh_channels(u64(mem(h,mesh+0x28,8)),'parameter-',2)
  elif kind=='cutgraph':
   raw('cutgraph-structure.bin',mem(h,obj,0x210));mesh_channels(u64(mem(h,obj,8)),'source-',3)
   costs=u64(mem(h,obj+0x18,8));raw('edge-costs.f32',vector(h,costs,4))
   for offset,name,stride in [(0x38,'seed-vertices.i32',4),(0x80,'vertex-distance.f32',4),(0x98,'vertex-owner.i32',4),(0xb0,'vertex-parent-edge.i32',4),(0xc8,'vertex-source.i32',4),(0xe0,'candidate-regions.i32x2',8),(0xf8,'candidate-edge.i32',4),(0x110,'candidate-cost.f32',4),(0x160,'selected-regions.i32x2',8),(0x178,'selected-cost.f32',4),(0x190,'selected-edge.i32',4),(0x1c0,'output-seed-vertices.i32',4),(0x1d8,'output-seed-types.i32',4),(0x1f0,'output-seed-owner.i32',4)]:vec(name,offset,stride)
   mask=mem(h,obj+0x68,24);nbits=u64(mask,16)
   if nbits<100000:raw('output-cut-edges.bits',mem(h,u64(mask),(nbits+7)//8))
   spans=vector(h,obj+0x50,16);raw('seed-spans.bin',spans);groups=[]
   for j in range(0,len(spans),16):
    begin,end=struct.unpack_from('<QQ',spans,j);assert begin<=end and (end-begin)%4==0 and end-begin<1000000
    groups.append(list(struct.unpack('<'+'i'*((end-begin)//4),mem(h,begin,end-begin))) if end>begin else [])
   raw('seed-groups.json',json.dumps(groups).encode())
  elif kind=='solver':
   header=mem(h,obj,0x300);raw('solver-structure.bin',header)
   callback=u64(header,0x48)
   if callback:
    raw('callback-object.bin',mem(h,callback,0x80));table=u64(mem(h,callback,8));raw('callback-vtable.bin',mem(h,table,32));meta['callbackFunctionRvas']=[hex(a-base) for a in struct.unpack('<4Q',mem(h,table,32)) if base<=a<base+0x500000]
   rhs=u64(header,0x10)
   if rhs:raw('solver-rhs.f64',vector(h,rhs,8))
   for offset,name,stride in [(0x18,'integer-indices.i32',4),(0x30,'solver-values.f64',8)]:vec(name,offset,stride)
   csr=u64(header);direct=u64(header,8)
   if csr:
    raw('normal-matrix-header.bin',mem(h,csr,0x58))
    for off,name,stride in [(0,'normal-offsets.i32',4),(0x18,'normal-indices.i32',4),(0x30,'normal-values.f64',8)]:raw(name,vector(h,csr+off,stride,1000000))
   if direct:dump(pid,label+'-direct-matrix',direct,'matrix')
  elif kind=='matrix':
   header=mem(h,obj,40);raw('matrix-header.bin',header);start,end,cap=struct.unpack_from('<QQQ',header);count=(end-start)//24
   assert start<=end<=cap and (end-start)%24==0 and count<100000
   rows=[]
   for i in range(count):
    terms=vector(h,start+i*24,16);rows.append([[i32(terms,j),struct.unpack_from('<d',terms,j+8)[0]] for j in range(0,len(terms),16)])
   raw('matrix-rows.json',json.dumps(dict(columns=i32(header,24),rows=i32(header,28),orientation=header[32],terms=rows)).encode())
  (folder/'capture.json').write_text(json.dumps(meta,indent=2)+'\n');record['captures'].append(meta);save()
 save()
 child=subprocess.Popen([str(host),'-batch','-script',str(out/'stage.py')],cwd=host.parent,creationflags=1|subprocess.CREATE_NO_WINDOW,stdout=(out/'stdout.log').open('w'),stderr=subprocess.STDOUT)
 record['rootPid']=child.pid;deadline=time.monotonic()+900
 try:
  while time.monotonic()<deadline:
   event=DebugEvent()
   if not wait(C.byref(event),500):
    if C.get_last_error()==121:continue
    raise C.WinError(C.get_last_error())
   data=bytes(event.data);pid,tid=event.pid,event.tid;status=0x10002
   if event.code==3:
    handles[pid]=u64(data,8);threads[pid,tid]=u64(data,16);alive.add(pid)
    if u64(data):close(u64(data))
    record['events'].append(dict(event='ownedProcessCreated',pid=pid))
   elif event.code==2:threads[pid,tid]=u64(data)
   elif event.code==6:
    handle=u64(data);name=C.create_unicode_buffer(32768)
    if handle and pathof(handle,name,len(name),0) and Path(name.value).name.lower()=='xremeshlib2.dll':
     base=u64(data,8);record['events'].append(dict(event='engineLoaded',pid=pid,base=hex(base)))
     for rva in [0x27c100,0x2fe700,0x2ff03e,0x300fd0,0x304d40,0x29ad50,0x284ef0,0x29b5b0,0x29b880]:breakpoint(pid,base+rva,hex(rva))
    if handle:close(handle)
   elif event.code==1:
    code=struct.unpack_from('<I',data)[0];addr=u64(data,16)
    if code==0x80000003 and (pid,addr) in bps:
     original,tag,payload=bps.pop((pid,addr));put(pid,addr,original)
     storage,ctxt,regs=context(threads[pid,tid]);C.c_uint64.from_address(ctxt+0xf8).value=addr;check(setctx(threads[pid,tid],ctxt))
     record['events'].append(dict(event='geometryBreakpoint',pid=pid,tag=tag))
     if tag=='0x274c70':dump(pid,'field-before-scales',regs['rcx'],'field')
     elif tag=='0x2740d0':dump(pid,'field-before-scale-smoothing',regs['rcx'],'field')
     elif tag=='0x274e34':dump(pid,'field-before-release',regs['rdi'],'field')
     elif tag=='0x2ab0e0':
      dump(pid,'grid-step',grid_current[pid],'grid-step')
      if (pid,base+0x2abff4) not in bps:breakpoint(pid,base+0x2abff4,'0x2abff4')
     elif tag=='0x2abff4':
      if (pid,base+0x2ab0e0) not in bps:breakpoint(pid,base+0x2ab0e0,'0x2ab0e0')
     elif tag=='0x29139a':dump(pid,'integer-regions',dict(frame=regs['rbp']),'integer-geometric-regions')
     elif tag in ['0x290d2a','0x290e70']:
      dump(pid,'integer-geometric-'+tag,dict(frame=regs['rbp']),'integer-geometric-front')
      key='geometric'+tag;record[key]=record.get(key,0)+1
      if tag=='0x290e70' and record[key]<2:breakpoint(pid,base+0x290d2a,'0x290d2a')
      if tag=='0x290d2a' and record[key]>1:
       breakpoint(pid,base+0x290e70,'0x290e70');breakpoint(pid,base+0x29139a,'0x29139a')
     elif tag=='0x2ff03e':
      dump(pid,'cutgraph-before-relaxation',regs['r15'],'cutgraph');mask=mem(handles[pid],regs['rbp']+0x48,24);nbits=u64(mask,16);assert nbits<100000
      (out/'connector-forbidden-header.bin').write_bytes(mask)
      (out/'connector-forbidden-vertices.bits').write_bytes(mem(handles[pid],u64(mask),(nbits+7)//8) if nbits else b'')
      record['connectorForbiddenLogicalBits']=nbits
     elif tag.startswith('return:'):
      kind,obj=payload[:2];label=tag.replace(':','-')
      if kind=='angular' and angular_calls>1:label='return-call-'+str(angular_calls)+'-0x281020'
      dump(pid,label,obj,kind)
      if tag in ('return:0x2fe700','return:0x304d40','return:0x27c100','return:0x300fd0','return:0x29ad50','return:0x284ef0','return:0x29b5b0','return:0x29b880'):
       # retopo-1 fork: capture repeated calls (the cut stage can run more than once)
       key='rearm-'+tag;record[key]=record.get(key,0)+1
       if record[key]<6:breakpoint(pid,base+int(tag.split(':')[1],16),tag.split(':')[1])
      if kind=='grid-walk':
       grid_current.pop(pid,None)
       for internal in [0x2ab0e0,0x2abff4]:
        if (pid,base+internal) in bps:
         prior,_,_=bps.pop((pid,base+internal));put(pid,base+internal,prior)
       record.setdefault('gridWalkReturnCodes',[]).append(regs['rax']&0xffffffff);record['gridWalksCaptured']=record.get('gridWalksCaptured',0)+1
       if record['gridWalksCaptured']<64:breakpoint(pid,base+0x2aadc0,'0x2aadc0')
      if kind=='pcg':record['pcgReturnRax']=regs['rax']
      if kind=='guide-walk':
       record['guideWalkReturnAl']=regs['rax']&255;record['guideWalksCaptured']=record.get('guideWalksCaptured',0)+1
       if record['guideWalksCaptured']<args.guide_walks:breakpoint(pid,base+0x10d2e0,'0x10d2e0')
      if kind in ['triangle-cut','planar-triangulation']:record[kind+'ReturnAl']=regs['rax']&255
      if kind=='triangle-cut':
       record['triangleCutsCaptured']=record.get('triangleCutsCaptured',0)+1
       if record['triangleCutsCaptured']<args.triangle_cuts:
        breakpoint(pid,base+0x252e50,'0x252e50');breakpoint(pid,base+0x2d0490,'0x2d0490')
      if kind=='boundary-cut':
       record['boundaryCutsCaptured']=record.get('boundaryCutsCaptured',0)+1
       if record['boundaryCutsCaptured']<args.boundary_cuts:breakpoint(pid,base+0x254210,'0x254210')
      if kind=='angular':record['angularCallbacksCaptured']=angular_calls;record['angularTerminalSeen']=mem(handles[pid],obj+0x58,1)==b'\x01'
      if kind=='angular' and angular_calls<args.angular_callbacks and mem(handles[pid],obj+0x58,1)!=b'\x01':breakpoint(pid,payload[2],'0x281020')
      if kind=='solver':
       call_id=payload[4]
       if call_id==1:
        angular_direct_phase.discard(pid)
        if (pid,base+0x2aeb70) in bps:
         old,_,_=bps.pop((pid,base+0x2aeb70));put(pid,base+0x2aeb70,old)
       call_id=payload[4];result=vector(handles[pid],payload[2],8);(out/f'solver-{call_id}-solution.f64').write_bytes(result)
       if solver_calls<3 and call_id<3 and (pid,payload[3]) not in bps:breakpoint(pid,payload[3],'0xdbf90')
      if kind=='integer-batch':
       integer_batches+=1;record['integerBatchesCaptured']=integer_batches
       if integer_batches<64 and pid in integer_phase:breakpoint(pid,base+0xdd470,'0xdd470')
      if kind=='cut-path-enumeration':
       record['pathEnumerationsCaptured']=record.get('pathEnumerationsCaptured',0)+1
       if record['pathEnumerationsCaptured']<3:breakpoint(pid,base+0x1651f0,'0x1651f0')
      if kind=='angular-full-direct':
       record['angularDirectSolvesCaptured']=record.get('angularDirectSolvesCaptured',0)+1;record.setdefault('angularDirectReturnCodes',[]).append(regs['rax']&255)
       if record['angularDirectSolvesCaptured']<32 and pid in angular_direct_phase:breakpoint(pid,base+0x2aeb70,'0x2aeb70')
      if kind=='dependency-expansion':
       record['dependencyExpansionsCaptured']=record.get('dependencyExpansionsCaptured',0)+1
       if record['dependencyExpansionsCaptured']<16:breakpoint(pid,base+0x2954b0,'0x2954b0')
      if kind=='paired-cut-path':
       record['pairedCutPathsCaptured']=record.get('pairedCutPathsCaptured',0)+1
       if record['pairedCutPathsCaptured']<128:breakpoint(pid,base+0x287370,'0x287370')
      if kind=='integer-constraint-elimination':
       record['constraintEliminationsCaptured']=record.get('constraintEliminationsCaptured',0)+1
       if pid not in integer_phase and record['constraintEliminationsCaptured']<2:breakpoint(pid,base+0x288f50,'0x288f50')
      if kind=='chain-integral':
       record['chainIntegralsCaptured']=record.get('chainIntegralsCaptured',0)+1
       if record['chainIntegralsCaptured']<128 and pid in integer_phase:breakpoint(pid,base+0x292aa0,'0x292aa0')
      if kind=='integer-dependency-substitution':
       record['integerSubstitutionsCaptured']=record.get('integerSubstitutionsCaptured',0)+1
       if record['integerSubstitutionsCaptured']<4 and pid in integer_phase:breakpoint(pid,base+0xe5af0,'0xe5af0')
      if tag=='return:0x28fe70':integer_phase.discard(pid)
     else:
      kind='cutpre' if tag=='0x255b10' else 'cuttri' if tag=='0x2567b0' else 'guide-relocate' if tag=='0x1703f0' else 'projection' if tag=='0x2e9730' else 'segmentation' if tag=='0x103060' else 'guideprep' if tag=='0x1c97b0' else 'pcg' if tag=='0xdec90' else 'angular' if tag=='0x281020' else 'field' if tag=='0x276080' else 'solver' if tag=='0xdbf90' else 'cutgraph' if tag=='0x2fe700' else 'matrix' if tag=='0x2992d0' else 'component'
      obj=regs['rdx'] if kind=='angular' else regs['rcx'] if kind in ['field','solver','cutgraph'] else regs['r8'] if kind=='matrix' else regs['rdx']
      if kind=='cutpre':obj=dict(cut=regs['rcx'],outputRecords=regs['rdx'],inputRecords=regs['r8']);breakpoint(pid,base+0x1703f0,'0x1703f0')
      if kind=='cuttri':
       obj=dict(cut=regs['rcx'],mapA=regs['rdx'],mapB=regs['r8'],inputRecords=regs['r9']);breakpoint(pid,base+0x254210,'0x254210');breakpoint(pid,base+0x24ea90,'0x24ea90')
      if kind=='guide-relocate':obj=dict(mesh=regs['rcx'],update=regs['rdx'])
      if tag=='0x10d2e0':kind='guide-walk';obj=dict(output=regs['rcx'],flag=regs['rdx'],start=regs['r8'],end=regs['r9'],context=u64(mem(handles[pid],regs['rsp']+0x28,8)),positions=u64(mem(handles[pid],regs['rsp']+0x30,8)))
      if tag=='0x252e50':kind='triangle-cut';obj=dict(polygon=regs['rcx'],newPositions=regs['rdx'],sourcePositions=regs['r8'],constraints=regs['r9'])
      if tag=='0x254210':kind='boundary-cut';obj=dict(polygon=regs['rcx'],newPositions=regs['rdx'],sourcePositions=regs['r8'],constraints=regs['r9'])
      if tag=='0x24ea90':kind='polygon-conversion';obj=dict(output=regs['rcx'],input=regs['rdx'],options=regs['r8'])
      if tag in ['0x293fc0','0x28fe70','0x28ecb0','0x28eae0']:kind='parameter-callback';obj=dict(remesher=regs['rcx'],request=regs['rdx'],component=u64(mem(handles[pid],regs['rdx']+0x60,8)))
      if tag=='0x28fe70':
       integer_phase.add(pid)
       breakpoint(pid,base+0x290d2a,'0x290d2a');breakpoint(pid,base+0x290e70,'0x290e70');breakpoint(pid,base+0x29139a,'0x29139a')
       if (pid,base+0x288f50) not in bps:breakpoint(pid,base+0x288f50,'0x288f50')
       breakpoint(pid,base+0x292aa0,'0x292aa0')
       breakpoint(pid,base+0xe5af0,'0xe5af0')
       breakpoint(pid,base+0xe4800,'0xe4800');breakpoint(pid,base+0x28f990,'0x28f990')
       if (pid,base+0xdbf90) not in bps:breakpoint(pid,base+0xdbf90,'0xdbf90')
      if tag=='0x2aadc0':kind='grid-walk';obj=dict(remesher=regs['rcx'],component=regs['rdx'],output=regs['r8'],outputDirection=regs['r9'],node=u64(mem(handles[pid],regs['rsp']+0x28,8)),direction=i32(mem(handles[pid],regs['rsp']+0x30,4)),face=u64(mem(handles[pid],regs['rsp']+0x38,8)),uv=u64(mem(handles[pid],regs['rsp']+0x40,8)),policy=mem(handles[pid],regs['rsp']+0x48,1)[0],link=u64(mem(handles[pid],regs['rsp']+0x50,8)))
      if tag=='0x2aadc0':
       obj['ordinal']=record.get('gridWalksCaptured',0)+1;grid_current[pid]=obj;breakpoint(pid,base+0x2ab0e0,'0x2ab0e0')
      if tag=='0x293fc0':breakpoint(pid,base+0x300950,'0x300950')
      if tag=='0x294770':kind='parameter-weight-smoothing';obj=dict(component=regs['rcx'],weights=regs['rdx'],iterations=regs['r8']&0xffffffff)
      if tag=='0x300950':kind='uv-gradient';obj=dict(u=regs['rcx'],v=regs['rdx'],mesh=regs['r8'],face=regs['r9']&0xffffffff)
      if tag=='0x2aeb70':kind='angular-full-direct';obj=dict(output=regs['rdx'],matrix=regs['r8'],rhs=regs['r9'],solver=angular_solvers[pid])
      if tag=='0x28c410':kind='guide-group-builder';obj=dict(component=regs['rdx'])
      if tag=='0x28b920':kind='guide-equality-builder';obj=dict(component=regs['rdx'],output=regs['r8'],rows=regs['r9'],preferred=u64(mem(handles[pid],regs['rsp']+0x28,8)),existing=u64(mem(handles[pid],regs['rsp']+0x30,8)),mapping=u64(mem(handles[pid],regs['rsp']+0x38,8)))
      if tag=='0x2954b0':kind='dependency-expansion';obj=dict(target=regs['rdx'],provider=regs['r8'],mapping=regs['r9'],policy=u64(mem(handles[pid],regs['rsp']+0x28,8)))
      if tag=='0x1651f0':kind='cut-path-enumeration';obj=dict(edgeGroups=regs['rcx'],vertexGroups=regs['rdx'],selected=regs['r8'],options=u64(mem(handles[pid],regs['rsp']+0x28,8)))
      if tag=='0x287370':kind='paired-cut-path';obj=dict(component=regs['rdx'],quarter=regs['r8'],sideA=regs['r9'],sideB=u64(mem(handles[pid],regs['rsp']+0x28,8)),edges=u64(mem(handles[pid],regs['rsp']+0x30,8)),vertices=u64(mem(handles[pid],regs['rsp']+0x38,8)))
      if tag=='0x288f50':kind='integer-constraint-elimination';obj=dict(component=regs['rdx'],dependencies=regs['r8'],rows=regs['r9'],dimension=i32(mem(handles[pid],regs['rsp']+0x28,4)),policy=u64(mem(handles[pid],regs['rsp']+0x30,8)))
      if tag=='0x292aa0':kind='chain-integral';obj=dict(component=regs['rcx'],output=regs['rdx'],path=regs['r8'],axis=regs['r9']&0xffffffff)
      if tag=='0xe5af0':kind='integer-dependency-substitution';obj=dict(matrix=regs['rcx'],dependencies=regs['rdx'],mapping=regs['r8'],policy=regs['r9'])
      if tag=='0xe4800':kind='integer-column-compression';obj=dict(matrix=regs['rcx'],dimension=regs['rdx']&0xffffffff,forward=regs['r8'],inverse=regs['r9'])
      if tag=='0x28f990':kind='integer-back-transfer';obj=dict(component=regs['rdx'],request=regs['r8'],solution=regs['r9'],forward=u64(mem(handles[pid],regs['rsp']+0x28,8)),dependencies=u64(mem(handles[pid],regs['rsp']+0x30,8)),dependencyMap=u64(mem(handles[pid],regs['rsp']+0x38,8)))
      if tag=='0xeb040':kind='positive-integer-callback';obj=dict(driver=regs['rcx']-i32(mem(handles[pid],regs['rcx']-4,4))-0x40,request=regs['rdx'])
      if tag=='0xdd470':kind='integer-batch';obj=dict(selected=regs['rcx'],values=regs['rdx'],solution=regs['r8'],indices=regs['r9'],steps=u64(mem(handles[pid],regs['rsp']+0x28,8)),fixed=u64(mem(handles[pid],regs['rsp']+0x30,8)),budget=regs['rsp']+0x38,threshold=u64(mem(handles[pid],regs['rsp']+0x40,8)))
      if tag=='0x2d0490':kind='planar-triangulation';obj=dict(output=regs['rcx'],points=regs['rdx'],segments=regs['r8'])
      if kind=='projection':obj=dict(output=regs['rcx'],points=regs['rdx'],attributes=regs['r8'],mesh=regs['r9'],options=u64(mem(handles[pid],regs['rsp']+0x28,8)))
      if kind=='segmentation':obj=dict(projector=regs['rcx'],records=regs['r8'],polyline=regs['r9'])
      if kind=='pcg':obj=dict(settings=regs['rcx'],solution=regs['rdx'],seeds=regs['r8'],matrix=regs['r9'],rhs=u64(mem(handles[pid],regs['rsp']+0x28,8)))
      if tag=='0x296050':
       components[pid]=obj
       record['parameterWeightSettings']={hex(offset):struct.unpack('<f',mem(handles[pid],regs['rcx']+offset,4))[0] for offset in [0x60c,0x610,0x614,0x618,0x690,0x694]};record['parameterWeightSmoothingPasses']=i32(mem(handles[pid],regs['rcx']+0x698,4))
       breakpoint(pid,base+0x28c410,'0x28c410')
       breakpoint(pid,base+0x28b920,'0x28b920')
       breakpoint(pid,base+0x2954b0,'0x2954b0')
       breakpoint(pid,base+0x1651f0,'0x1651f0')
       breakpoint(pid,base+0x287370,'0x287370')
       if (pid,base+0x288f50) not in bps:breakpoint(pid,base+0x288f50,'0x288f50')
      if kind=='solver' and solver_calls==0:
       angular_direct_phase.add(pid);angular_solvers[pid]=obj;breakpoint(pid,base+0x2aeb70,'0x2aeb70')
      if kind=='solver' and solver_calls==1 and pid in components:
       dump(pid,'parameter-solver-component',components[pid],'component')
       dump(pid,'parameter-reduced-residual-matrix',components[pid]+0xad0,'matrix')
      if kind=='solver' and pid in integer_phase:
       dump(pid,'integer-solver-component-'+str(solver_calls+1),components[pid],'component');dump(pid,'integer-solver-residuals-'+str(solver_calls+1),components[pid]+0x8f0,'matrix')
       breakpoint(pid,base+0xeb040,'0xeb040');breakpoint(pid,base+0xdd470,'0xdd470')
      if tag=='0x281020':record['angularSettings']={hex(o):struct.unpack('<d',mem(handles[pid],regs['rcx']+o,8))[0] for o in [0x5e8,0x5f0,0x5f8]};record['angularOptions']=list(mem(handles[pid],regs['rcx']+0x600,2))
      if tag=='0x1e6990':record['smoothingMode']=i32(mem(handles[pid],regs['rcx']+0x5c4,4))
      if kind=='angular':angular_calls+=1
      label='entry-call-'+str(angular_calls)+'-'+tag if kind=='angular' and angular_calls>1 else 'entry-'+tag
      if kind in ['grid-walk','angular-full-direct','guide-group-builder','guide-equality-builder','dependency-expansion','cut-path-enumeration','paired-cut-path','integer-constraint-elimination','chain-integral','integer-dependency-substitution','integer-column-compression','integer-back-transfer','integer-batch','positive-integer-callback','uv-gradient','parameter-weight-smoothing','parameter-callback','polygon-conversion','boundary-cut','triangle-cut','planar-triangulation','guide-walk','cutpre','cuttri','guide-relocate','projection','segmentation','guideprep','pcg','angular','component','solver','cutgraph']:dump(pid,label,obj,kind)
      if kind=='solver':solver_calls+=1
      returnaddr=u64(mem(handles[pid],regs['rsp'],8));breakpoint(pid,returnaddr,'return:'+tag,(kind,obj,regs['rdx'],addr,solver_calls) if kind=='solver' else (kind,obj,addr) if kind=='angular' else (kind,obj))
     save()
    elif code==0x80000003 and pid not in first:first.add(pid)
    else:status=0x80010001
   elif event.code==5:
    alive.discard(pid);record['events'].append(dict(event='ownedProcessExited',pid=pid,exitCode=struct.unpack_from('<I',data)[0]))
   check(cont(pid,tid,status))
   if not alive:break
  record['timedOut']=bool(alive)
  if alive:
   for pid in alive:kill(handles[pid],0xdead)
  record['status']='captured' if record['captures'] and not alive else 'no-complete-capture'
 except BaseException:
  record['error']=traceback.format_exc();record['status']='failed'
  for pid in alive:kill(handles[pid],0xdead)
  raise
 finally:record['finished']=time.time();save()
 print(json.dumps(dict(status=record['status'],captures=len(record['captures']),smoothingMode=record.get('smoothingMode'))))
 if record['status']!='captured':raise SystemExit(1)
if __name__=='__main__':main()

