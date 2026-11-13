"""Fork of workbench trace_native_crossing_cleanup.py for retopo-1 (2026-11-13): outputs under native-captures/prep; stage script adds Keep Creases."""
"""Crossing cleanup entry/split/relaxation observer fork; owned synthetic geometry only.

Import the identity-pinned Windows ABI helpers from trace_native_algorithm.
Do not attach user sessions or alter installed files. All breakpoints are
one-shot entry/return pairs; stream writes avoid quadratic capture manifests.
"""
import argparse,hashlib,json,shutil,struct,subprocess,time,traceback
from pathlib import Path
import psutil
import numpy as np
from trace_native_algorithm import C,DebugEvent,HOST,ENGINE,mem,vector,span,u64,i32,context,check,protect,write,flush,getctx,setctx,wait,cont,close,pathof,kill,W
ROOT=Path(r'C:\dbva\code\ghidra-workbench')   # fork for retopo-1: workbench target identity; outputs go to OUTROOT
OUTROOT=Path(__file__).resolve().parents[2]/'prep'
PHASES={0x2a7cc0:'guide-tags',0x29d240:'surface-relaxation',0x2a7360:'seed-frontier',0x2a6270:'intermediate-6270',0x2a59b0:'intermediate-59b0',0x2a3e60:'boundary-polygons',0x2a0c10:'curve-fitting'}
HOOKS={0x2a02c0:'fit-paths',0x2a9490:'seed-turn',0x2aa4c0:'slice-emit',0x2aa690:'oversize',0x2a88d0:'partition',0x2ad950:'driver',0x2aadc0:'walk',0x2a8bc0:'cycle',0x2a9ac0:'assemble',0x2aa9c0:'emit',0x2acc10:'construct',0x2ad390:'lookup',0x2acd70:'frame',**{a:'phase' for a in PHASES}}
PREP_HOOKS={0x1c9fb0:'prepare-root',0x1c6f20:'prepare-6f20',0x1cb520:'prepare-b520',0x1c7d40:'prepare-7d40',0x1c6950:'prepare-6950',0x1c2fd0:'prepare-2fd0',0x1c3d60:'prepare-3d60',0x1c2c70:'prepare-2c70',0x1cb980:'prepare-b980',0x1e79d0:'conditioning-component',0x1c97b0:'guide-embedding-component'}
PREP_HOOKS.update({0x25a990:'refine-dispatch',0x260290:'refine-260290',0x2ec0d0:'refine-2ec0d0'})
PREP_HOOKS.update({0x1c2630:'prepare-densify',0x1c53a0:'prepare-quality',0x24d0c0:'refine-subdivide'})
PREP_HOOKS.update({0x192130:'fairing',0x18eec0:'fairing-pass'})
WEIGHT_HOOKS={0x2eb320:'weight-maxmean',0x2ebba0:'weight-mean'}
PREP_HOOKS.update({0x1c88d0:'cleanup-component',0x24c510:'cleanup-split',0x263480:'cleanup-relax'})
HOOKS.update(PREP_HOOKS)
for deferred in [0x24c510,0x263480]:HOOKS.pop(deferred)
ORIGINAL_GUIDE_HOOKS={0x2e9730:'original-guide-projection',0x103060:'original-guide-segmentation'}
HOOKS.update(ORIGINAL_GUIDE_HOOKS)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--name',required=True);ap.add_argument('--timeout',type=int,default=900);ap.add_argument('--walk-steps',action='store_true');ap.add_argument('--weight-probe',action='store_true');ap.add_argument('--redistribution-probe',action='store_true');args=ap.parse_args()
 if not 60<=args.timeout<=1800:raise ValueError('Bounded dedicated timeout required')
 if any(p.info['name'].lower()=='zbrush.exe' for p in psutil.process_iter(['name'])):raise RuntimeError('Existing user session preserved')
 out=OUTROOT/args.name
 if Path(args.name).name!=args.name or out.exists():raise ValueError('Choose a fresh synthetic run name')
 local=json.loads((ROOT/'targets/zbrush/target.local.json').read_text());host=Path(local['inputs']['host']);engine=Path(local['inputs']['engine'])
 assert hashlib.sha256(host.read_bytes()).hexdigest()==HOST and hashlib.sha256(engine.read_bytes()).hexdigest()==ENGINE
 out.mkdir(parents=True);shutil.copy2(args.config,out/'config.json');shutil.copy2(Path(__file__).with_name('native_geometry_stage.py'),out/'stage.py');shutil.copy2(__file__,out/'debugger.py');shutil.copy2(Path(__file__).with_name('trace_native_algorithm.py'),out/'debugger-support.py')
 record=dict(status='running',method='Owned supported synthetic batch under DEBUG_PROCESS; geometry-only entry/return stream',hostSha256=HOST,engineSha256=ENGINE,started=time.time(),events=[],counts={},artifacts=[],timeoutSeconds=args.timeout,counterfactualWeightProbe=bool(args.weight_probe),counterfactualRedistributionProbe=bool(args.redistribution_probe))
 
 for provenance in ['config.json','stage.py','debugger.py','debugger-support.py']:
  path=out/provenance;record['artifacts'].append(dict(path=provenance,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 conditioningMeshes={};handles={};threads={};alive=set();first=set();bps={};base=0;serial=0;components={};geometrySaved=set();phaseSerial=0;stream=(out/'geometry-events.jsonl').open('w',encoding='utf-8',newline='\n');walkCurrent={};stepCount=0;stepStream=(out/'walk-steps.jsonl').open('w',encoding='utf-8',newline='\n') if args.walk_steps else None
 def save():
  temp=out/'trace.json.tmp';temp.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
  for attempt in range(21):
   try:temp.replace(out/'trace.json');break
   except PermissionError:
    if attempt==20:raise
    time.sleep(.05)  # Bounded retry for Windows readers denying delete sharing.
 def event(row):
  nonlocal serial
  serial+=1;row['ordinal']=serial;stream.write(json.dumps(row,separators=(',',':'))+'\n')
  if serial%128==0:stream.flush();save()
 def raw(relative,blob):
  path=out/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(blob);record['artifacts'].append(dict(path=relative,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest()))
 def put(pid,address,value):
  old=W.DWORD();check(protect(handles[pid],address,len(value),0x40,C.byref(old)))
  try:check(write(handles[pid],address,value,len(value),None));check(flush(handles[pid],address,len(value)))
  finally:prior=W.DWORD();check(protect(handles[pid],address,len(value),old.value,C.byref(prior)))
 def bp(pid,address,role,payload):
  if (pid,address) in bps:raise RuntimeError('Breakpoint collision '+hex(address))
  original=mem(handles[pid],address,1);put(pid,address,b'\xcc');bps[pid,address]=(original,role,payload)
 def node(pid,address):return dict(pointer=address,header=mem(handles[pid],address,0x90).hex()) if address else None
 def polygon(pid,component):
  h=handles[pid];p=u64(mem(h,component+0xcb0,8))
  if not p:return None
  offsets=vector(h,p,4);indices=vector(h,p+24,4)
  return dict(offsets=list(struct.unpack('<'+'i'*(len(offsets)//4),offsets)),indices=list(struct.unpack('<'+'i'*(len(indices)//4),indices)))
 def mesh(pid,address,prefix):
  h=handles[pid];vb=u64(mem(h,address,8));vbase=i32(mem(h,vb+0x10,4));fbase=i32(mem(h,vb+0xc,4));kind=i32(mem(h,address+fbase+0x24,4));raw(prefix+'-mesh-header.bin',mem(h,address,0x100));raw(prefix+'-vbtable.bin',mem(h,vb,32));raw(prefix+'-face-kind.i32',struct.pack('<i',kind));raw(prefix+'-positions.bin',span(h,address+vbase+8,12) if prefix.endswith('source') or prefix.endswith('output') else vector(h,u64(mem(h,address+vbase+8,8)),8));raw(prefix+'-face-indices.i32',vector(h,u64(mem(h,address+fbase+0x18,8)),4))
  if kind==0:raw(prefix+'-face-offsets.i32',vector(h,u64(mem(h,address+fbase+0x10,8)),4))
  if prefix.endswith('source'):
   topology=u64(mem(h,address+fbase+0x28,8))
   for offset,name,stride in [(0x20,'face-edges.i32x3',12),(0x38,'edges.i32x2',8),(0x58,'edge-face-offset.i32',4),(0x70,'edge-face-corners.i32',4),(0xb8,'vertex-edge-offset.i32',4),(0xd0,'vertex-edge-list.i32',4)]:raw(prefix+'-'+name,vector(h,topology+offset,stride))
 def geometry(pid,component):
  if pid in geometrySaved:return
  h=handles[pid];source=u64(mem(h,component+0x10,8));mesh(pid,source,'input/source');mesh(pid,u64(mem(h,source+0x28,8)),'input/parameter');raw('input/component.bin',mem(h,component,0xf10))
  for offset,name,stride in [(0x4b0,'source-seeds.i32',4),(0x4f8,'fallback-seeds.i32',4),(0x8d8,'quarters.i32',4)]:raw('input/'+name,vector(h,component+offset,stride))
  geometrySaved.add(pid)
 def pool(pid,component,label):
  nonlocal phaseSerial
  phaseSerial+=1;h=handles[pid];header=u64(mem(h,component+0xca8,8));heads=vector(h,header+8,8);headIds=list(struct.unpack('<'+'Q'*(len(heads)//8),heads));nodes={}
  for pointer in headIds:
   chain=set()
   while pointer:
    if pointer in chain:raise ValueError('Cyclic face work-node bucket')
    if pointer in nodes:break
    if len(nodes)>=100000:raise ValueError('Work-node pool bound')
    chain.add(pointer);b=mem(h,pointer,0x90);nodes[pointer]=b.hex();pointer=u64(b)
  result=dict(label=label,component=component,outputVertexCounter=i32(mem(h,header,4)),bucketHeads=headIds,nodes=nodes,polygon=polygon(pid,component),componentState=mem(h,component+0xc88,0x108).hex())
  for offset,name,stride in [(0xcd8,'deferredNodes',8),(0xcf0,'deferredDirections',4)]:
   pointer=u64(mem(h,component+offset,8)) if offset==0xc88 else component+offset
   result[name]=vector(h,pointer,stride).hex() if pointer else ''
  raw(f'phases/{phaseSerial:02d}-{label}.json',(json.dumps(result,separators=(',',':'))+'\n').encode())
  if label not in ['seed-frontier','guide-tags']:mesh(pid,component+0x50,f'phases/{phaseSerial:02d}-{label}/output')
  if label=='guide-tags':
   for offset,name in [(0xe30,'source-guide-vertices'),(0xe48,'source-guide-edges'),(0xef8,'source-guide-edge-forward')]:
    mask=mem(h,component+offset,24);count=u64(mask,16);assert count<100000;raw('guide-tags/'+name+'-logical-count.u64',struct.pack('<Q',count));raw('guide-tags/'+name+'.bits',mem(h,u64(mask),(count+7)//8) if count else b'')
   for offset,name in [(0xe68,'path-edge-offsets.i32'),(0xe80,'path-edges.i32'),(0xe98,'path-vertex-offsets.i32'),(0xeb0,'path-vertices.i32'),(0xec8,'edge-path.i32'),(0xee0,'edge-path-position.i32')]:raw('guide-tags/'+name,vector(h,component+offset,4))
   raw('guide-tags/edge-count.i32',mem(h,component+0xe60,4));classes=u64(mem(h,component+0x228,8));raw('guide-tags/source-vertex-classes.u8',vector(h,classes,1) if classes else b'');curves=vector(h,component+0x30,8)
   for index,address in enumerate(struct.unpack('<'+'Q'*(len(curves)//8),curves)):
    raw(f'guide-tags/curve-{index}-header.bin',mem(h,address,0x4a8));raw(f'guide-tags/curve-{index}-primary.i32x2',span(h,address+0x268,8))

 def nested(pid,pointer,prefix):
  h=handles[pid];headers=vector(h,pointer,24);begin=u64(mem(h,pointer,8))
  if len(headers)//24>1024:raise ValueError('Nested path count bound')
  raw(prefix+'/headers.bin',headers)
  for index in range(len(headers)//24):
   blob=vector(h,begin+24*index,1)
   if len(blob)>4000000:raise ValueError('Nested path byte bound')
   raw(prefix+'/item-'+str(index).zfill(3)+'.bin',blob)
 def segment(pid,address,prefix):
  h=handles[pid];raw(prefix+'-header.bin',mem(h,address,0x78))
  for offset,name,stride in [(0,'points.f32x3',12),(0x18,'edges.i32',4),(0x30,'edge-parameters.f32',4),(0x48,'faces.i32',4),(0x60,'attributes.i32',4)]:raw(prefix+'-'+name,vector(h,address+offset,stride))
 def bitset(pid,component,offset,prefix):
  h=handles[pid];header=mem(h,component+offset,24);count=u64(header,16)
  if count>10000000:raise ValueError('Logical bit count bound')
  raw(prefix+'-count.u64',struct.pack('<Q',count));raw(prefix+'.bits',mem(h,u64(header),(count+7)//8))
 originalWalkerCalls={}
 def entry(pid,address,role,regs):
  h=handles[pid];stack=regs['rsp'];data=dict(role=role,rva=hex(address-base),pid=pid,tid=tid);obj=dict(tid=tid)
  if role in ['driver','phase','walk','cycle']:component=regs['rdx'];components[pid]=component
  elif role in ['partition','fit-project','fit-redistribute','cut-pre','cut-output','quad-prep','position-driver','position-update','project-position']:component=components[pid]
  else:component=regs['rcx']
  obj['component']=component;data['component']=component
  if role=='original-direct-path':
   obj.update(prefix='original-segment-paths/direct-'+str(record['counts'].get(role,0)+1).zfill(3),record=regs['r8']);data.update(prefix=obj['prefix'],start=mem(h,regs['r9'],20).hex(),end=mem(h,u64(mem(h,stack+0x28,8)),20).hex(),sampleIndex=i32(mem(h,stack+0x30,4)),dispatchFlag=mem(h,stack+0x48,1).hex());raw(obj['prefix']+'/options.bin',mem(h,regs['rcx'],0x28));raw(obj['prefix']+'/stack-arguments.bin',mem(h,stack+0x28,0x38));segment(pid,obj['record'],obj['prefix']+'/before')
  elif role=='original-alternate-path':
   obj.update(prefix='original-segment-paths/alternate-'+str(record['counts'].get(role,0)+1).zfill(3),output=regs['rcx']);data.update(prefix=obj['prefix'],startPair=mem(h,regs['rdx'],8).hex(),startPoint=mem(h,regs['r8'],12).hex(),endPair=mem(h,regs['r9'],8).hex(),endPoint=mem(h,u64(mem(h,stack+0x28,8)),12).hex());raw(obj['prefix']+'/stack-arguments.bin',mem(h,stack+0x28,0x20))
   for offset,name,stride in [(0,'edges.i32',4),(0x18,'faces.i32',4),(0x30,'parameters.f32',4),(0x48,'points.f32x3',12)]:raw(obj['prefix']+'/before-'+name,vector(h,obj['output']+offset,stride))
  elif role=='original-walk-candidates':
   obj.update(prefix='original-walk/candidates-'+str(record['counts'].get(role,0)+1).zfill(4),candidates=regs['rcx'],output=regs['rdx']);data.update(prefix=obj['prefix'],owningWalk=originalWalkerCalls[pid],startPair=mem(h,regs['r8'],8).hex(),endPair=mem(h,regs['r9'],8).hex())
   for offset,name,stride in [(0,'edges.i32',4),(0x18,'faces.i32',4),(0x30,'parameters.f32',4),(0x48,'points.f32x3',12)]:raw(obj['prefix']+'/before-'+name,vector(h,obj['output']+offset,stride))
  elif role=='original-surface-walk':
   originalWalkerCalls[pid]=record['counts'].get(role,0)+1;bp(pid,base+0x11a470,'original-walk-candidates',None)
   obj.update(prefix='original-walk/call-'+str(record['counts'].get(role,0)+1).zfill(3),output=regs['rcx'],repair=regs['rdx'],start=regs['r8'],end=regs['r9'],context=u64(mem(h,stack+0x28,8)),positions=u64(mem(h,stack+0x30,8)));data.update(prefix=obj['prefix'],start=mem(h,obj['start'],20).hex(),end=mem(h,obj['end'],20).hex(),repairBefore=mem(h,obj['repair'],1).hex());raw(obj['prefix']+'/context.bin',mem(h,obj['context'],0x78))
   if record['counts'].get(role,0)==0:
    raw('original-walk/shared/positions.f32x3',span(h,obj['positions'],12))
    for offset,name,stride in [(0x38,'triangles.i32x3',12),(0x40,'edges.i32x2',8),(0x48,'face-edges.i32x3',12),(0x68,'normals.f32x3',12)]:raw('original-walk/shared/'+name,vector(h,u64(mem(h,obj['context']+offset,8)),stride))
    for offset,name in [(0x50,'vertex-corner'),(0x58,'edge-corner'),(0x60,'vertex-edge')]:
     channel=u64(mem(h,obj['context']+offset,8));raw('original-walk/shared/'+name+'-offsets.i32',vector(h,channel,4));raw('original-walk/shared/'+name+'-entries.i32',vector(h,channel+0x18,4))
  elif role=='original-nearest-query':
   obj.update(prefix='original-nearest/query-'+str(record['counts'].get(role,0)+1).zfill(3),queryContext=regs['rcx'],face=regs['rdx'],triangle=regs['r8'],position=regs['r9'],distance=u64(mem(h,stack+0x28,8)));data.update(prefix=obj['prefix'],point=mem(h,u64(mem(h,stack+0x30,8)),12).hex(),maximumDistance=mem(h,stack+0x38,4).hex())
   if record['counts'].get(role,0)==0:
    query=regs['rcx'];raw('original-nearest/context.bin',mem(h,query,0xb8));raw('original-nearest/face-order.i32',vector(h,query+0x38,4));source=u64(mem(h,query+0x18,8));mesh(pid,source,'original-nearest/entry-output');faceCount=len(vector(h,query+0x38,4))//4;root=u64(mem(h,query+0xa8,8));pending=[root];nodes={}
    while pending:
     pointer=pending.pop()
     if not pointer or pointer in nodes:continue
     if len(nodes)>=100000:raise ValueError('Nearest-face tree node bound')
     blob=mem(h,pointer,40);left,right=struct.unpack_from('<QQ',blob);row=dict(pointer=pointer,bytes=blob.hex(),bounds=list(struct.unpack_from('<6f',blob,16)))
     if 0<=right<left<=faceCount:row.update(kind='leaf',begin=right,end=left)
     elif left>=65536 and right>=65536:row.update(kind='branch',children=[left,right]);pending.extend([left,right])
     elif left==right==0:row.update(kind='empty')
     else:raise ValueError('Unqualified nearest-tree node layout '+str((left,right,faceCount)))
     nodes[pointer]=row
    raw('original-nearest/tree.json',(json.dumps(dict(root=root,faceCount=faceCount,nodes=list(nodes.values())),indent=2)+'\n').encode())
  elif role in ORIGINAL_GUIDE_HOOKS.values():
   obj['prefix']='original-guides/'+role+'-'+str(record['counts'].get(role,0)+1).zfill(3);data['prefix']=obj['prefix']
   if role=='original-guide-projection':
    bp(pid,base+0x2d90b0,'original-nearest-query',None)
    obj.update(output=regs['rcx'],mesh=regs['r9']);options=u64(mem(h,stack+0x28,8));raw(obj['prefix']+'/options.bin',mem(h,options,8));raw(obj['prefix']+'/input-points.f32x3',span(h,regs['rdx'],12));raw(obj['prefix']+'/input-attributes.i32',span(h,regs['r8'],4));mesh(pid,obj['mesh'],obj['prefix']+'/entry-output')
   else:
    for rva,kind in [(0x10d2e0,'original-surface-walk'),(0x10c0a0,'original-direct-path'),(0xfd6f0,'original-alternate-path')]:bp(pid,base+rva,kind,None)
    obj.update(projector=regs['rcx'],records=regs['r8'],polyline=regs['r9']);raw(obj['prefix']+'/projector-options.bin',mem(h,obj['projector'],0x28));obj['mesh']=u64(mem(h,obj['projector']+0x10,8));mesh(pid,obj['mesh'],obj['prefix']+'/entry-output')
    for offset,name,stride in [(8,'points.f32x3',12),(0x38,'attachments.i32x2',8),(0x50,'faces.i32',4),(0x68,'attributes.i32',4)]:raw(obj['prefix']+'/input-'+name,vector(h,obj['polyline']+offset,stride))
  elif role in PREP_HOOKS.values() or role in WEIGHT_HOOKS.values():
   obj['prefix']='conditioning/'+role+'-'+str(record['counts'].get(role,0)+1).zfill(3);data['prefix']=obj['prefix']
   if role in WEIGHT_HOOKS.values():
    obj['mesh']=conditioningMeshes[pid];obj['output']=regs['rcx'];raw(obj['prefix']+'/input.f32',vector(h,regs['rdx'],4));data.update(coefficient2=regs['xmm2'],coefficient3=regs['xmm3'])
    if role=='weight-maxmean':endpoints=u64(mem(h,stack+0x28,8));incidence=u64(mem(h,stack+0x30,8));mask=u64(mem(h,stack+0x38,8))
    else:endpoints=regs['r9'];incidence=u64(mem(h,stack+0x28,8));mask=u64(mem(h,stack+0x30,8))
    raw(obj['prefix']+'/edges.i32x2',vector(h,endpoints,8));raw(obj['prefix']+'/vertex-edge-offsets.i32',vector(h,incidence,4));raw(obj['prefix']+'/vertex-edge-list.i32',vector(h,incidence+24,4));bitset(pid,mask,0,obj['prefix']+'/locked')
    cache=u64(mem(h,obj['mesh']+0x50,8));raw(obj['prefix']+'/measure-cache.bin',mem(h,cache,0xe0))
    for offset,name in [(0x40,'edge-angles.f32'),(0xa0,'corner-angles.f32'),(0xc0,'vertex-channel.f32')]:raw(obj['prefix']+'/'+name,vector(h,cache+offset,4))
   elif role in ['fairing','fairing-pass']:
    obj['smoother']=regs['rcx'];obj['mesh']=u64(mem(h,obj['smoother']+0x210,8));obj['output']=regs['rdx'];raw(obj['prefix']+'/entry-smoother.bin',mem(h,obj['smoother'],0x260))
    if role=='fairing':obj['weights']=regs['r8'];obj['selected']=regs['r9']
    else:
     obj['weights']=regs['r9'];obj['selected']=u64(mem(h,stack+0x28,8));raw(obj['prefix']+'/input-positions.f32x3',vector(h,regs['r8'],12))
    raw(obj['prefix']+'/weights.f32',vector(h,obj['weights'],4));data['selectedPointer']=obj['selected']
   elif role=='prepare-quality':
    obj['mesh']=regs['rcx'];obj['qualityOptions']=regs['r8'];raw(obj['prefix']+'/entry-quality-options.bin',mem(h,obj['qualityOptions'],0x40))
   elif role=='prepare-densify':
    obj['mesh']=regs['rdx'];data['argument3Int']=C.c_int32(regs['r8']).value;data['argument4Low32']=hex(regs['r9']&0xffffffff);raw(obj['prefix']+'/preparation.bin',mem(h,regs['rcx'],0x400))
   elif role=='refine-dispatch':
    obj['mesh']=regs['rcx'];obj['options']=regs['r8'];data['mode']=C.c_int32(regs['rdx']).value;raw(obj['prefix']+'/entry-options.bin',mem(h,obj['options'],0x70))
   elif role in ['refine-260290','refine-2ec0d0','refine-subdivide']:
    obj['mesh']=u64(mem(h,regs['rcx'],8));obj['context']=regs['rcx'];raw(obj['prefix']+'/entry-context.bin',mem(h,obj['context'],0x100))
   elif role in ['conditioning-component','guide-embedding-component','cleanup-component']:
    obj['mesh']=u64(mem(h,regs['rdx']+0x10,8));raw(obj['prefix']+'/component.bin',mem(h,regs['rdx'],0x250))
    if role=='cleanup-component':
     for rva,kind in [(0x24c510,'cleanup-split'),(0x263480,'cleanup-relax')]:bp(pid,base+rva,kind,None)
    if role=='guide-embedding-component':
     components[pid]=regs['rdx']
     for rva,kind in [(0x255b10,'cut-pre'),(0x2567b0,'cut-output')]:bp(pid,base+rva,kind,None)
     obj['guideComponent']=regs['rdx'];curves=vector(h,obj['guideComponent']+0x30,8);raw(obj['prefix']+'/curve-pointers.bin',curves)
     for index,pointer in enumerate(struct.unpack('<'+'Q'*(len(curves)//8),curves)):
      raw(obj['prefix']+f'/curve-{index}-header.bin',mem(h,pointer,0x4a8))
      for offset,name,stride in [(0x118,'points.f32x3',12),(0x148,'attachments.i32x2',8),(0x160,'faces.i32',4),(0x238,'embedded-points.f32x3',12),(0x268,'embedded.i32x2',8)]:raw(obj['prefix']+f'/curve-{index}-entry-'+name,vector(h,pointer+offset,stride))
   elif role in ['cleanup-split','cleanup-relax']:
    obj.update(mesh=u64(mem(h,regs['rcx'],8)),options=regs['rcx']);raw(obj['prefix']+'/entry-options.bin',mem(h,obj['options'],0xd0 if role=='cleanup-split' else 0xe8))
    if role=='cleanup-relax':
     fixed=u64(mem(h,obj['options']+0xa8,8));bitset(pid,fixed,0,obj['prefix']+'/fixed-vertices') if fixed else None
    if role=='cleanup-split':
     obj.update(selected=regs['rdx'],outputA=regs['r8'],outputB=regs['r9']);raw(obj['prefix']+'/selected-edges.i32',vector(h,obj['selected'],4))
   else:obj['mesh']=regs['rdx']
   if role=='refine-2ec0d0':
    conditioningMeshes[pid]=obj['mesh']
    for rva,kind in WEIGHT_HOOKS.items():bp(pid,base+rva,kind,None)
   if role=='prepare-root':
    obj['preparation']=regs['rcx'];raw(obj['prefix']+'/preparation.bin',mem(h,regs['rcx'],0x400))
   mesh(pid,obj['mesh'],obj['prefix']+'/entry-output')
  elif role=='driver':geometry(pid,component);data['settings']=mem(h,regs['rcx']+0x688,0x30).hex()
  elif role=='phase':
   obj['phase']=PHASES[address-base];data['phase']=obj['phase']
   if obj['phase']=='curve-fitting':
    pending=bps.pop((pid,base+0x3157a0),None)
    if pending:put(pid,base+0x3157a0,pending[0])
    mesh(pid,component+0x50,'curve-entry/output')
    for rva,kind in [(0x2e9d40,'fit-project'),(0x2a3340,'fit-redistribute'),(0x255b10,'cut-pre'),(0x2567b0,'cut-output')]:bp(pid,base+rva,kind,None)
   if obj['phase']=='curve-fitting' and args.weight_probe:
    probePath=ROOT/'work/zbrush/runtime/algorithm-recovery/guided-output-paths-check.npz';marked=np.load(probePath)['marked'];blob=vector(h,component+0xd58,4)
    if len(blob)!=len(marked)*4:raise ValueError('Probe logical weight count mismatch')
    begin=u64(mem(h,component+0xd58,8));indices=np.flatnonzero(marked).tolist();raw('weight-probe/before.f32',blob)
    for index in indices:check(write(h,begin+index*4,struct.pack('<f',1.),4,None))
    raw('weight-probe/after.f32',vector(h,component+0xd58,4));raw('weight-probe/request.json',(json.dumps(dict(method='Owned synthetic component D58 data fields only; no installed binary modification',source=str(probePath.relative_to(ROOT)),sourceSha256=hashlib.sha256(probePath.read_bytes()).hexdigest(),indices=indices,value=1.,component=component,pid=pid),indent=2)+'\n').encode())
   if obj['phase']=='surface-relaxation':
    bp(pid,base+0x29e080,'edge-properties',None)
    for rva,kind in [(0x318680,'position-driver'),(0x317430,'position-update'),(0x12db90,'project-position')]:bp(pid,base+rva,kind,None)
    for offset,name,stride in [(0x378,'basis0.f32x3',12),(0x390,'basis1.f32x3',12),(0x6d8,'axis0-scale.f32',4),(0x6f0,'axis1-scale.f32',4),(0x890,'axis0-coefficients.f32x2',8),(0x8a8,'axis1-coefficients.f32x2',8)]:raw('relaxation-properties/'+name,vector(h,component+offset,stride))
    raw('relaxation-properties/default-scale.f32',mem(h,component+0x6c0,4));field=u64(mem(h,component+0x240,8));raw('relaxation-properties/field-face-flags.u8',vector(h,field+0x220,1))
    source=u64(mem(h,component+0x10,8));vb=u64(mem(h,source,8));fb=i32(mem(h,vb+0xc,4));topology=u64(mem(h,source+fb+0x28,8))
    for offset,name in [(0x88,'source-vertex-corner-offset.i32'),(0xa0,'source-vertex-corners.i32')]:raw('relaxation-properties/'+name,vector(h,topology+offset,4))
    for offset,name,stride in [(0xd28,'attachments.i32x2',8),(0xd58,'weights.f32',4),(0xde8,'source-faces.i32',4)]:raw('pre-relaxation/'+name,vector(h,component+offset,stride))
    bitset(pid,component,0xd70,'pre-relaxation/guide-vertices');bitset(pid,component,0xf58,'pre-relaxation/guide-edges')
  elif role in ['position-driver','position-update']:
   obj.update(context=regs['rcx'],prefix=role+'-'+str(record['counts'].get(role,0)+1).zfill(3))
   if role=='position-update':obj['requested']=regs['rdx']
   raw(obj['prefix']+'/entry-context.bin',mem(h,obj['context'],0x90));mesh(pid,component+0x50,obj['prefix']+'/entry-output')
   for offset,name,stride in [(0x20,'edge-directions.f32x3',12),(0x28,'edge-minimum.f32',4),(0x30,'edge-maximum.f32',4),(0x38,'vertex-field-blend.f32',4),(0x50,'vertex-mobility.f32',4)]:
    pointer=u64(mem(h,obj['context']+offset,8));raw(obj['prefix']+'/'+name,vector(h,pointer,stride) if pointer else b'')
   pointer=u64(mem(h,obj['context']+0x48,8));raw(obj['prefix']+'/selected-vertices.i32',vector(h,pointer,4) if pointer else b'')
   pointer=u64(mem(h,obj['context']+0x18,8));raw(obj['prefix']+'/entry-attachments.i32x2',vector(h,pointer,8))
   if role=='position-driver':
    field=u64(mem(h,component+0x240,8))+0xe0;raw(obj['prefix']+'/field-header.bin',mem(h,field,0x160))
    for offset,name,stride in [(0x68,'field-channel68.f32',4),(0x80,'field-channel80.f32',4),(0x140,'field-flags.u8',1)]:raw(obj['prefix']+'/'+name,vector(h,field+offset,stride))
    classes=u64(mem(h,component+0x228,8));raw(obj['prefix']+'/source-class-pointer.bin',struct.pack('<Q',classes));raw(obj['prefix']+'/source-classes.u8',vector(h,classes,1) if classes else b'')
    for offset,name in [(0x10,'source-guide-edges'),(0x40,'output-guide-edges')]:
     pointer=u64(mem(h,obj['context']+offset,8))
     if pointer:bitset(pid,pointer,0,obj['prefix']+'/'+name)
  elif role=='project-position':
   if record['counts'].get(role,0)==0:
    projection=u64(mem(h,regs['rcx']+0x18,8));normals=u64(mem(h,projection+0x38,8));raw('projection/source-face-normals.f32x3',vector(h,normals,12));raw('projection/context.bin',mem(h,regs['rcx'],0x20));raw('projection/cache.bin',mem(h,projection,0x48))
   obj.update(attachment=regs['r8'],point=regs['r9'],delta=u64(mem(h,stack+0x28,8)));data.update(inputAttachment=mem(h,obj['attachment'],8).hex(),inputPoint=mem(h,obj['point'],12).hex(),displacement=mem(h,obj['delta'],12).hex())
  elif role=='edge-properties':
   if component!=components[pid]:raise ValueError('Unexpected relaxation component')
   obj.update(minimum=regs['rdx'],maximum=regs['r8'],gain=regs['r9'],direction=u64(mem(h,stack+0x28,8)),valid=u64(mem(h,stack+0x30,8)))
   data.update(vertex=i32(mem(h,stack+0x38,4)),neighbor=i32(mem(h,stack+0x40,4)))
  elif role=='quad-prep':
   obj.update(options=regs['rcx'],prefix='quad-prep-'+str(record['counts'].get(role,0)+1).zfill(3));obj['mesh']=u64(mem(h,obj['options']+0x1a0,8))
   if obj['mesh']!=component+0x50:raise ValueError('Unexpected post-cap mesh identity')
   raw(obj['prefix']+'/entry-options.bin',mem(h,obj['options'],0x310));mesh(pid,obj['mesh'],obj['prefix']+'/entry-output')
  elif role in ['cut-pre','cut-output']:
   obj.update(cut=regs['rcx'],inputs=regs['r8'] if role=='cut-pre' else regs['r9'],prefix=role+'-'+str(record['counts'].get(role,0)+1).zfill(3))
   if role=='cut-pre':obj['records']=regs['rdx']
   else:obj.update(mapA=regs['rdx'],mapB=regs['r8'])
   obj['mesh']=u64(mem(h,obj['cut'],8));raw(obj['prefix']+'/options.bin',mem(h,obj['cut'],0x18));mesh(pid,obj['mesh'],obj['prefix']+'/entry-output')
   pointers=vector(h,obj['inputs'],8);raw(obj['prefix']+'/input-record-pointers.bin',pointers)
   if len(pointers)//8>10000:raise ValueError('Cut input record count bound')
   for index in range(len(pointers)//8):segment(pid,u64(pointers,index*8),obj['prefix']+'/input-'+str(index).zfill(3))
  elif role=='fit-project':
   obj.update(projector=regs['rcx'],records=regs['rdx'],polyline=regs['r8'],prefix='fit-project-'+str(record['counts'].get(role,0)+1).zfill(3))
   raw(obj['prefix']+'/options.bin',mem(h,obj['projector'],0x28))
   for offset,name,stride in [(8,'points.f32x3',12),(0x38,'attachments.i32x2',8),(0x50,'faces.i32',4),(0x68,'attributes.i32',4)]:raw(obj['prefix']+'/input-'+name,vector(h,obj['polyline']+offset,stride))
   mesh(pid,u64(mem(h,obj['projector']+0x10,8)),obj['prefix']+'/output')
  elif role=='fit-redistribute':
   obj.update(attachments=regs['rdx'],segment=regs['r8'],keys=regs['r9'],path=u64(mem(h,stack+0x28,8)),source=u64(mem(h,stack+0x30,8)),prefix='fit-redistribute-'+str(record['counts'].get(role,0)+1).zfill(3))
   if args.redistribution_probe:
    blob=vector(h,obj['segment']+0x60,4);attributes=np.frombuffer(blob,dtype='<i4');indices=[i for i in range(1,len(attributes)-1,2) if attributes[i]>=0]
    begin=u64(mem(h,obj['segment']+0x60,8));raw(obj['prefix']+'/probe-before-attributes.i32',blob)
    for index in indices:check(write(h,begin+index*4,struct.pack('<i',-1),4,None))
    raw(obj['prefix']+'/probe-after-attributes.i32',vector(h,obj['segment']+0x60,4));raw(obj['prefix']+'/probe-request.json',(json.dumps(dict(method='Owned synthetic intermediate curve segment sample attributes only; alternating interior anchors removed to exercise interpolation',pid=pid,component=component,indices=indices,value=-1),indent=2)+'\n').encode())
   raw(obj['prefix']+'/path-keys.f32',vector(h,obj['keys'],4));raw(obj['prefix']+'/path-source-vertices.i32',span(h,obj['path'],4))
   raw(obj['prefix']+'/entry-attachments.i32x2',vector(h,obj['attachments'],8));segment(pid,obj['segment'],obj['prefix']+'/entry')
  elif role=='fit-paths':
   obj.update(paths=regs['rdx'],parameters=regs['r8'],prefix='fit-paths-'+str(record['counts'].get(role,0)+1).zfill(3))
   raw(obj['prefix']+'/entry-weights.f32',vector(h,component+0xd58,4));bitset(pid,component,0xd70,obj['prefix']+'/entry-guide-vertices')
   mesh(pid,component+0x50,obj['prefix']+'/input-output')
  elif role=='walk':
   obj.update(output=regs['r8'],directionOut=regs['r9'],node=u64(mem(h,stack+0x28,8)),direction=i32(mem(h,stack+0x30,4)),face=u64(mem(h,stack+0x38,8)),uv=u64(mem(h,stack+0x40,8)),link=u64(mem(h,stack+0x50,8)));data.update(inputNode=node(pid,obj['node']),direction=obj['direction'],face=i32(mem(h,obj['face'],4)),uv=mem(h,obj['uv'],8).hex(),policy=mem(h,stack+0x48,1).hex(),frontierMode=mem(h,component+0xccc,1).hex())
  elif role=='cycle':data.update(node=node(pid,regs['r8']),direction=regs['r9']&0xffffffff,face=i32(mem(h,stack+0x28,4)),uv=mem(h,stack+0x30,8).hex())
  elif role in ['assemble','emit','slice-emit','oversize']:
   pointers=vector(h,regs['rdx'],8);data['nodes']=[node(pid,p) for p in struct.unpack('<'+'Q'*(len(pointers)//8),pointers)];data['polygon']=polygon(pid,component);obj['nodes']=list(struct.unpack('<'+'Q'*(len(pointers)//8),pointers));data['outputCounter']=i32(mem(h,u64(mem(h,component+0xca8,8)),4))
   if role=='slice-emit':
    obj['mask']=u64(mem(h,stack+0x28,8));data.update(begin=C.c_int32(regs['r8']).value,end=C.c_int32(regs['r9']).value,maskHeader=mem(h,obj['mask'],24).hex() if obj['mask'] else None)
   if role=='assemble':data.update(directions=vector(h,regs['r8'],4).hex(),faces=vector(h,regs['r9'],4).hex(),flags=vector(h,u64(mem(h,stack+0x28,8)),1).hex())
  elif role=='partition':
   obj.update(output=regs['rcx'],indices=regs['rdx'],positions=regs['r8']);data.update(indices=vector(h,obj['indices'],4).hex(),positions=vector(h,obj['positions'],12).hex())
  elif role=='construct':data.update(face=C.c_int32(regs['rdx']).value,position=mem(h,regs['r8'],12).hex(),uv=mem(h,regs['r9'],8).hex())
  elif role=='seed-turn':
   obj.update(face=regs['r8'],directionOut=regs['r9'],uv=u64(mem(h,stack+0x28,8)));data.update(vertex=C.c_int32(regs['rdx']).value,face=i32(mem(h,obj['face'],4)),direction=i32(mem(h,obj['directionOut'],4)),uv=mem(h,obj['uv'],8).hex())
  elif role=='lookup':data.update(face=C.c_int32(regs['rdx']).value,corner=C.c_int32(regs['r8']).value,position=mem(h,regs['r9'],12).hex(),options=mem(h,stack+0x28,12).hex())
  elif role=='frame':obj['directionOut']=regs['rdx'];data.update(targetFace=C.c_int32(regs['r8']).value,attachment=mem(h,regs['r9'],8).hex(),direction=i32(mem(h,stack+0x28,4)),inputFace=i32(mem(h,stack+0x30,4)))
  record['counts'][role]=record['counts'].get(role,0)+1
  if record['counts'][role]>50000:raise ValueError('Geometry event count bound')
  data['event']='entry';data['call']=record['counts'][role];obj['call']=data['call'];event(data)
  if role=='walk' and args.walk_steps:
   walkCurrent[pid]=obj;bp(pid,base+0x2ab0e0,'walk-step',None)
  return obj
 def returned(pid,address,role,obj,regs):
  assert obj['tid']==tid,'Observed cross-thread return breakpoint; reject trace'
  h=handles[pid];component=obj['component'];data=dict(event='return',role=role,call=obj['call'],rax=regs['rax'],pid=pid,tid=tid)
  if role=='original-direct-path':
   data.update(prefix=obj['prefix'],returnAl=regs['rax']&255);segment(pid,obj['record'],obj['prefix']+'/after')
  elif role=='original-alternate-path':
   data.update(prefix=obj['prefix'],returnAl=regs['rax']&255)
   for offset,name,stride in [(0,'edges.i32',4),(0x18,'faces.i32',4),(0x30,'parameters.f32',4),(0x48,'points.f32x3',12)]:raw(obj['prefix']+'/after-'+name,vector(h,obj['output']+offset,stride))
  elif role=='original-walk-candidates':
   data.update(prefix=obj['prefix'],returnAl=regs['rax']&255,candidates=list(struct.unpack('<'+'i'*(len(vector(h,obj['candidates'],4))//4),vector(h,obj['candidates'],4))))
   for offset,name,stride in [(0,'edges.i32',4),(0x18,'faces.i32',4),(0x30,'parameters.f32',4),(0x48,'points.f32x3',12)]:raw(obj['prefix']+'/after-'+name,vector(h,obj['output']+offset,stride))
  elif role=='original-surface-walk':
   pending=bps.pop((pid,base+0x11a470),None)
   if pending:put(pid,base+0x11a470,pending[0])
   originalWalkerCalls.pop(pid)
   data.update(prefix=obj['prefix'],returnAl=regs['rax']&255,repairAfter=mem(h,obj['repair'],1).hex(),startAfter=mem(h,obj['start'],20).hex(),endAfter=mem(h,obj['end'],20).hex())
   for offset,name,stride in [(0,'edges.i32',4),(0x18,'faces.i32',4),(0x30,'parameters.f32',4),(0x48,'points.f32x3',12)]:raw(obj['prefix']+'/'+name,vector(h,obj['output']+offset,stride))
  elif role=='original-nearest-query':
   data.update(prefix=obj['prefix'],face=i32(mem(h,obj['face'],4)),triangle=i32(mem(h,obj['triangle'],4)),point=mem(h,obj['position'],12).hex(),distance=mem(h,obj['distance'],4).hex())
  elif role in ORIGINAL_GUIDE_HOOKS.values():
   data['prefix']=obj['prefix']
   if role=='original-guide-projection':
    pending=bps.pop((pid,base+0x2d90b0),None)
    if pending:put(pid,base+0x2d90b0,pending[0])
    raw(obj['prefix']+'/returned-header.bin',mem(h,obj['output'],0x80))
    for offset,name,stride in [(8,'points.f32x3',12),(0x38,'attachments.i32x2',8),(0x50,'faces.i32',4),(0x68,'attributes.i32',4)]:raw(obj['prefix']+'/returned-'+name,vector(h,obj['output']+offset,stride))
   else:
    for rva in [0x10d2e0,0x10c0a0,0xfd6f0]:
     pending=bps.pop((pid,base+rva),None)
     if pending:put(pid,base+rva,pending[0])
    records=vector(h,obj['records'],0x78);raw(obj['prefix']+'/returned-segments.bin',records);begin=u64(mem(h,obj['records'],8))
    for index in range(len(records)//0x78):segment(pid,begin+index*0x78,obj['prefix']+'/segment-'+str(index).zfill(3))
  elif role in PREP_HOOKS.values() or role in WEIGHT_HOOKS.values():
   pointer=u64(mem(h,obj['preparation']+0x1e0,8)) if role=='prepare-root' else obj['mesh'];mesh(pid,pointer,obj['prefix']+'/return-output');data['prefix']=obj['prefix']
   if role in ['fairing','fairing-pass']:raw(obj['prefix']+'/returned-positions.f32x3',vector(h,obj['output'],12))
   elif role in WEIGHT_HOOKS.values():raw(obj['prefix']+'/returned.f32',vector(h,obj['output'],4))
   if role=='refine-2ec0d0':
    for rva in WEIGHT_HOOKS:
     pending=bps.pop((pid,base+rva),None)
     if pending:put(pid,base+rva,pending[0])
   if role in ['cleanup-split','cleanup-relax']:raw(obj['prefix']+'/return-options.bin',mem(h,obj['options'],0xd0 if role=='cleanup-split' else 0xe8))
   if role=='cleanup-split':
    raw(obj['prefix']+'/return-outputA.bin',vector(h,obj['outputA'],12));raw(obj['prefix']+'/return-outputB.i32',vector(h,obj['outputB'],4))
   if role=='refine-dispatch':raw(obj['prefix']+'/return-options.bin',mem(h,obj['options'],0x70))
   elif role in ['refine-260290','refine-2ec0d0','refine-subdivide']:raw(obj['prefix']+'/return-context.bin',mem(h,obj['context'],0x100))
   if role=='guide-embedding-component':
    for rva in [0x255b10,0x2567b0]:
     pending=bps.pop((pid,base+rva),None)
     if pending:put(pid,base+rva,pending[0])
    curves=vector(h,obj['guideComponent']+0x30,8)
    for index,pointer in enumerate(struct.unpack('<'+'Q'*(len(curves)//8),curves)):
     for offset,name,stride in [(0x118,'points.f32x3',12),(0x148,'attachments.i32x2',8),(0x160,'faces.i32',4),(0x238,'embedded-points.f32x3',12),(0x268,'embedded.i32x2',8)]:raw(obj['prefix']+f'/curve-{index}-return-'+name,vector(h,pointer+offset,stride))
  elif role=='walk':
   if args.walk_steps:
    walkCurrent.pop(pid)
    for rva in [0x2ab0e0,0x2abff4]:
     pending=bps.pop((pid,base+rva),None)
     if pending:put(pid,base+rva,pending[0])
   pointer=u64(mem(h,obj['output'],8));data.update(status=regs['rax']&0xffffffff,inputNode=node(pid,obj['node']),outputNode=node(pid,pointer),direction=i32(mem(h,obj['directionOut'],4)),face=i32(mem(h,obj['face'],4)),uv=mem(h,obj['uv'],8).hex(),link=mem(h,obj['link'],1).hex())
  elif role in ['construct','lookup']:data['node']=node(pid,regs['rax'])
  elif role=='frame':data.update(success=bool(regs['rax']&255),direction=i32(mem(h,obj['directionOut'],4)))
  elif role in ['position-driver','position-update']:
   data['prefix']=obj['prefix']
   if role=='position-update':raw(obj['prefix']+'/requested-positions.f32x3',vector(h,obj['requested'],12))
   else:mesh(pid,component+0x50,obj['prefix']+'/return-output')
   pointer=u64(mem(h,obj['context']+0x18,8));raw(obj['prefix']+'/return-attachments.i32x2',vector(h,pointer,8))
  elif role=='project-position':data.update(outputAttachment=mem(h,obj['attachment'],8).hex(),outputPoint=mem(h,obj['point'],12).hex())
  elif role=='edge-properties':
   data['properties']={name:mem(h,obj[name],12 if name=='direction' else 4).hex() for name in ['minimum','maximum','gain','direction','valid']}
  elif role=='quad-prep':
   raw(obj['prefix']+'/return-options.bin',mem(h,obj['options'],0x310));mesh(pid,obj['mesh'],obj['prefix']+'/return-output');data['prefix']=obj['prefix']
  elif role in ['cut-pre','cut-output']:
   mesh(pid,obj['mesh'],obj['prefix']+'/return-output');data['prefix']=obj['prefix']
   if role=='cut-pre':
    records=vector(h,obj['records'],0x78);raw(obj['prefix']+'/returned-records.bin',records);begin=u64(mem(h,obj['records'],8))
    if len(records)//0x78>10000:raise ValueError('Cut pre output record count bound')
    for index in range(len(records)//0x78):segment(pid,begin+index*0x78,obj['prefix']+'/returned-'+str(index).zfill(3))
   else:
    nested(pid,obj['mapA'],obj['prefix']+'/mapA');nested(pid,obj['mapB'],obj['prefix']+'/mapB')
  elif role=='fit-project':
   records=vector(h,obj['records'],0x78);raw(obj['prefix']+'/returned-records.bin',records);begin=u64(mem(h,obj['records'],8))
   if len(records)//0x78>10000:raise ValueError('Segment record count bound')
   for index in range(len(records)//0x78):segment(pid,begin+index*0x78,obj['prefix']+'/segment-'+str(index).zfill(3))
   data.update(prefix=obj['prefix'],segments=len(records)//0x78)
  elif role=='fit-redistribute':
   raw(obj['prefix']+'/return-attachments.i32x2',vector(h,obj['attachments'],8));segment(pid,obj['segment'],obj['prefix']+'/return');data['prefix']=obj['prefix']
  elif role=='fit-paths':
   nested(pid,obj['paths'],obj['prefix']+'/paths');nested(pid,obj['parameters'],obj['prefix']+'/parameters');data['prefix']=obj['prefix']
  elif role=='seed-turn':data.update(success=bool(regs['rax']&255),face=i32(mem(h,obj['face'],4)),direction=i32(mem(h,obj['directionOut'],4)),uv=mem(h,obj['uv'],8).hex())
  elif role in ['assemble','emit','slice-emit','oversize']:
   data.update(polygon=polygon(pid,component),nodes=[node(pid,p) for p in obj['nodes']],outputCounter=i32(mem(h,u64(mem(h,component+0xca8,8)),4)))
   if role=='slice-emit' and obj['mask']:data['maskHeader']=mem(h,obj['mask'],24).hex()
  elif role=='partition':data.update(output=vector(h,obj['output'],4).hex(),remainingIndices=vector(h,obj['indices'],4).hex(),remainingPositions=vector(h,obj['positions'],12).hex())
  elif role=='phase':
   if obj['phase']=='surface-relaxation':
    for rva in [0x318680,0x317430,0x12db90]:
     pending=bps.pop((pid,base+rva),None)
     if pending:put(pid,base+rva,pending[0])
    pending=bps.pop((pid,base+0x29e080),None)
    if pending:put(pid,base+0x29e080,pending[0])
   if obj['phase']=='curve-fitting':
    for rva in [0x2e9d40,0x2a3340,0x255b10,0x2567b0]:
     pending=bps.pop((pid,base+rva),None)
     if pending:put(pid,base+rva,pending[0])
   pool(pid,component,obj['phase'])
   if obj['phase']=='boundary-polygons':bp(pid,base+0x3157a0,'quad-prep',None)
   if obj['phase']=='intermediate-6270':
    for offset,name,stride in [(0xd28,'attachments.i32x2',8),(0xd40,'source-vertex-output.i32',4),(0xd58,'relaxation-weights.f32',4),(0xd88,'neighbors0.i32',4),(0xda0,'neighbors1.i32',4),(0xdb8,'neighbors2.i32',4),(0xdd0,'neighbors3.i32',4),(0xde8,'source-faces.i32',4)]:raw('materialized-meta/'+name,vector(h,component+offset,stride))
    for offset,name in [(0xe00,'protected-output'),(0xe18,'boundary-output')]:
     header=mem(h,component+offset,24);count=u64(header,16);raw('materialized-meta/'+name+'-count.u64',struct.pack('<Q',count));raw('materialized-meta/'+name+'.bits',mem(h,u64(header),(count+7)//8))
  elif role=='driver':mesh(pid,component+0x50,'final/output')
  event(data);bp(pid,address,role,None)
 save();child=subprocess.Popen([str(host),'-batch','-script',str(out/'stage.py')],cwd=host.parent,creationflags=1|subprocess.CREATE_NO_WINDOW,stdout=(out/'stdout.log').open('w'),stderr=subprocess.STDOUT);record['rootPid']=child.pid;deadline=time.monotonic()+args.timeout
 try:
  while time.monotonic()<deadline:
   ev=DebugEvent()
   if not wait(C.byref(ev),500):
    if C.get_last_error()==121:continue
    raise C.WinError(C.get_last_error())
   d=bytes(ev.data);pid,tid=ev.pid,ev.tid;status=0x10002
   if ev.code==3:
    handles[pid]=u64(d,8);threads[pid,tid]=u64(d,16);alive.add(pid);record['events'].append(dict(event='ownedProcessCreated',pid=pid))
    if u64(d):close(u64(d))
   elif ev.code==2:threads[pid,tid]=u64(d)
   elif ev.code==6:
    handle=u64(d);name=C.create_unicode_buffer(32768)
    if handle and pathof(handle,name,len(name),0) and Path(name.value).name.lower()=='xremeshlib2.dll':
     base=u64(d,8);record['events'].append(dict(event='engineLoaded',pid=pid,base=base))
     for rva,role in HOOKS.items():bp(pid,base+rva,role,None)
    if handle:close(handle)
   elif ev.code==1:
    code=struct.unpack_from('<I',d)[0];address=u64(d,16)
    if code==0x80000003 and (pid,address) in bps:
     original,role,payload=bps.pop((pid,address));put(pid,address,original);storage,ctxt,regs=context(threads[pid,tid]);C.c_uint64.from_address(ctxt+0xf8).value=address;check(setctx(threads[pid,tid],ctxt))
     if role=='walk-step':
      obj=walkCurrent[pid];assert obj['tid']==tid;stepCount+=1
      stepStream.write(json.dumps(dict(ordinal=stepCount,pid=pid,tid=tid,call=obj['call'],face=i32(mem(handles[pid],obj['face'],4)),uv=mem(handles[pid],obj['uv'],8).hex(),direction=i32(mem(handles[pid],obj['directionOut'],4))),separators=(',',':'))+'\n')
      bp(pid,base+0x2abff4,'walk-step-rearm',None)
     elif role=='walk-step-rearm':bp(pid,base+0x2ab0e0,'walk-step',None)
     elif role=='return':
      start,entryRole,obj=payload;returned(pid,start,entryRole,obj,regs)
     else:
      regs['xmm2']=C.string_at(ctxt+0x1c0,4).hex();regs['xmm3']=C.string_at(ctxt+0x1d0,4).hex()
      obj=entry(pid,address,role,regs);bp(pid,u64(mem(handles[pid],regs['rsp'],8)),'return',(address,role,obj))
    elif code==0x80000003 and pid not in first:first.add(pid)
    else:status=0x80010001
   elif ev.code==5:alive.discard(pid);record['events'].append(dict(event='ownedProcessExited',pid=pid,exitCode=struct.unpack_from('<I',d)[0]))
   check(cont(pid,tid,status))
   if not alive:break
  record['timedOut']=bool(alive)
  if alive:
   for pid in alive:kill(handles[pid],0xdead)
  creates={e['pid'] for e in record['events'] if e['event']=='ownedProcessCreated'};exits={e['pid']:e['exitCode'] for e in record['events'] if e['event']=='ownedProcessExited'};record['status']='captured' if creates and creates==set(exits) and all(v==0 for v in exits.values()) else 'no-complete-capture'
 except BaseException:
  record.update(status='failed',error=traceback.format_exc())
  for pid in alive:kill(handles[pid],0xdead)
  raise
 finally:
  if stepStream:
   stepStream.flush();stepStream.close();path=out/'walk-steps.jsonl';record['artifacts'].append(dict(path=path.name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()));record['walkSteps']=stepCount
  stream.flush();stream.close();path=out/'geometry-events.jsonl';record['artifacts'].append(dict(path=path.name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()));record.update(finished=time.time(),geometryEvents=serial);save()
 print(json.dumps(dict(status=record['status'],events=serial,counts=record['counts'])))
 if record['status']!='captured':raise SystemExit(1)

if __name__=='__main__':main()
