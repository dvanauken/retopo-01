"""Run inside ZBrush only; stage results require external geometry measurement."""
from pathlib import Path
import json
import hashlib
import shutil
import time
import traceback
import sys
import os

OUT=Path(__file__).resolve().parent
(OUT/'entered.txt').write_text('entered')
import zbrush.commands as zbc
CONFIG=json.loads((OUT/'config.json').read_text())
PREFIX='Tool:Geometry:ZRemesher:'
result=dict(started=time.time(),stage=CONFIG['stage'],operations=[],status='running')

def flush(): (OUT/'result.json').write_text(json.dumps(result,indent=2))
def press(path):
    if not zbc.exists(path):raise RuntimeError('Missing UI path '+path)
    result['operations'].append(dict(action='press',path=path,time=time.time()));flush();zbc.press(path)
def choose(paths):
    for path in paths:
        if zbc.exists(path):return path
    raise RuntimeError('Missing all UI aliases '+str(paths))
def set_value(path,value):
    if not zbc.exists(path):raise RuntimeError('Missing '+path)
    old=zbc.get(path);zbc.set(path,value);actual=zbc.get(path)
    result['operations'].append(dict(action='set',path=path,before=old,requested=value,actual=actual));flush()
    if abs(actual-value)>1e-5:raise RuntimeError('Value not accepted '+path)
def snapshot():
    names=['Target Polygons Count','Target Polygon Count','TargetPolygonsCount','Curves Strength','Curve Strength','CurvesStrength','AdaptiveSize','Adaptive Size','Adapt','Half','Same','Double','KeepGroups','Keep Groups','FreezeGroups','Freeze Groups','Freeze Border','FreezeBorder','FreezeBorders','SmoothGroups','Smooth Groups','KeepCreases','Keep Creases','DetectEdges','Detect Edges','Use Polypaint','Use PolyPaint','Keep Polypaint','Keep PolyPaint','Color Density','ColorDensity','Retry']
    paths=[PREFIX+n for n in names]+['Transform:Activate Symmetry','Transform:X','Transform:Y','Transform:Z','Transform:Local Symmetry','Tool:Export:Scale','Tool:Export:X Offset','Tool:Export:Y Offset','Tool:Export:Z Offset','Tool:Export:XOffset','Tool:Export:YOffset','Tool:Export:ZOffset','Tool:Import','Tool:Export','Tool:SimpleBrush','Tool:PolyMesh3D','Brush:ZRemesherGuides']
    rows=[]
    for path in paths:
        row=dict(path=path,exists=zbc.exists(path))
        if row['exists']:
            for key,fn in [('value',zbc.get),('enabled',zbc.is_enabled),('id',zbc.get_id)]:
                try:row[key]=fn(path)
                except Exception as e:row[key+'Error']=str(e)
        rows.append(row)
    return rows
def mesh_info():
    return dict(points=zbc.query_mesh3d(0),faces=zbc.query_mesh3d(1),bounds=zbc.query_mesh3d(2),transform=zbc.get_transform(),activeTool=zbc.get_active_tool_path())
def export(path):
    path=Path(path)
    if path.exists():raise RuntimeError('Output already exists '+str(path))
    zbc.set_next_filename(str(path));press('Tool:Export')
    if not path.exists():raise RuntimeError('No export '+str(path))
def packets(case_dir,after):
    # Read only named remesher artifacts written during our exclusive session.
    base=Path(os.environ['LOCALAPPDATA'])/'Temp/ZBrushData2026'
    saved=[]
    allowed={'ProgressFile','Caching_Id','Caching_AutoDetectUseCacheMode','Caching_UseCache','Caching_CachePath','FileIn','FileOut','NumQuad','SymMode','LocalSym','FreezeBorders','KeepGroups','FreezeBordersCoef','KeepHardEdges','AutoDetectHardEdges','Exact','MaxQuadRatio','VarDensityRatio','NumPointCirc','UsePolyPainting','MaxNumThread','HostApp','KeepPolyPainting','FileCurves','CurvesStrength'}
    for name in ['remeshsettings.txt','RemeshGuides.zpl','objIn.obj','objOut.obj','objIn.goz','objOut.goz','objIn.cache','zprogress.txt']:
        for path in base.rglob(name):
            if path.stat().st_mtime<after-2:continue
            dest=case_dir/name
            if name=='remeshsettings.txt':
                data=path.read_bytes();settings={};unknown=[]
                for line in data.decode('utf-8',errors='replace').splitlines():
                    if '=' in line:
                        key,value=line.split('=',1)
                        if key in allowed:settings[key]=value
                        else:unknown.append(key)
                dest=case_dir/'settings.json';dest.write_text(json.dumps(dict(sourceSha256=hashlib.sha256(data).hexdigest(),settings=settings,omittedKeys=unknown),indent=2))
            else:shutil.copy2(path,dest)
            saved.append(dict(source=str(path),artifact=str(dest),sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
    return saved

try:
    result['initialUI']=snapshot();flush()
    source=CONFIG['input'];zbc.set_next_filename(source);press('Tool:Import')
    result['imported']=mesh_info();result['afterImportUI']=snapshot();flush()
    export(OUT/'roundtrip.obj')
    # Explicit export scale/offsets expose the tool-coordinate mesh for mapping.
    export_paths=[choose(['Tool:Export:Scale'])]+[choose(['Tool:Export:'+axis+' Offset','Tool:Export:'+axis+'Offset']) for axis in 'XYZ']
    old_values={p:zbc.get(p) for p in export_paths}
    set_value(export_paths[0],1)
    for path in export_paths[1:]:set_value(path,0)
    export(OUT/'internal.obj');result['internalExportUI']=snapshot()
    for path,value in old_values.items():set_value(path,value)
    if CONFIG['stage']=='import':result['status']='import-exported-unqualified'
    else:
        target=choose([PREFIX+'Target Polygons Count',PREFIX+'Target Polygon Count',PREFIX+'TargetPolygonsCount'])
        strength=choose([PREFIX+'Curves Strength',PREFIX+'Curve Strength',PREFIX+'CurvesStrength'])
        set_value(target,CONFIG.get('target',1));set_value(strength,CONFIG.get('strength',0))
        # retopo-1 fork: symmetry off and optional Keep Creases at CTolerance (as runs/native-rim-investigation island6_payload.py).
        set_value('Transform:Activate Symmetry',0)
        for aliases,value in [(('KeepCreases','Keep Creases'),0),(('DetectEdges','Detect Edges'),0),(('KeepGroups','Keep Groups'),0),(('FreezeGroups','Freeze Groups'),0),(('FreezeBorder','Freeze Border','FreezeBorders'),0)]:
            set_value(choose([PREFIX+n for n in aliases]),value)
        if CONFIG.get('keepCreases'):
            set_value('Tool:Geometry:Crease:CTolerance',CONFIG['creaseDegrees']);press('Tool:Geometry:Crease:Crease')
            set_value(choose([PREFIX+'KeepCreases',PREFIX+'Keep Creases']),1)
        if CONFIG.get('curves'):
            if not CONFIG.get('coordinateMappingQualified'):raise RuntimeError('Curve mapping gate not qualified')
            press('Brush:ZRemesherGuides');zbc.new_curves()
            for curve in CONFIG['curves']:
                index=zbc.add_new_curve()
                if index<0:raise RuntimeError('Curve allocation')
                for point in curve:
                    if zbc.add_curve_point(index,*point)<0:raise RuntimeError('Curve point')
            result['curveTransferCode']=zbc.curves_to_ui()
            if result['curveTransferCode']!=0:raise RuntimeError('Curve UI transfer')
        result['beforeRemesh']=mesh_info();result['effectiveUI']=snapshot();flush()
        started=time.time();press(PREFIX+'ZRemesher')
        result['remeshSeconds']=time.time()-started;result['afterRemesh']=mesh_info();flush()
        export(OUT/'output.obj');result['packets']=packets(OUT,started);result['status']='exported-unqualified'
except BaseException:
    result['status']='failed';result['error']=traceback.format_exc()
finally:
    result['finished']=time.time();flush()
sys.exit(1 if result['status']=='failed' else 0)
