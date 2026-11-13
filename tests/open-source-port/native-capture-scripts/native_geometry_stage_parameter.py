"""Remesh retopo-1 island 6 in an owned ZBrush batch child and export the result.

The controller copies source.obj and case.json beside this payload. This script
records UI readback, packets and exported geometry only; qualification is done
afterwards by the retopo-1 measurements.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
import traceback

OUT = Path(__file__).resolve().parent
(OUT / 'entered.txt').write_text('Python entered\n', encoding='utf-8')
P = 'Tool:Geometry:ZRemesher:'
result = {'passed': False, 'status': 'running', 'operations': [], 'nativeAcquisitionOnly': True}


def flush():
    (OUT / 'stages.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


try:
    import zbrush.commands as zbc

    def press(path):
        if not zbc.exists(path):
            raise RuntimeError('Missing UI ' + path)
        result['operations'].append({'action': 'press', 'path': path})
        flush()
        zbc.press(path)

    def setval(paths, value):
        path = next((p for p in paths if zbc.exists(p)), None)
        if path is None:
            raise RuntimeError('Missing UI alternatives ' + repr(paths))
        before = zbc.get(path)
        zbc.set(path, value)
        actual = zbc.get(path)
        result['operations'].append({'action': 'set', 'path': path, 'before': before, 'requested': value, 'actual': actual})
        flush()
        if abs(actual - value) > 1e-5:
            raise RuntimeError('UI value rejected ' + path)

    def control(names, value):
        setval([P + n for n in names], value)

    def export(name):
        path = OUT / name
        if path.exists():
            raise RuntimeError('Existing export ' + str(path))
        zbc.set_next_filename(str(path))
        press('Tool:Export')
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError('Export missing/empty ' + name)
        result.setdefault('exports', []).append({'name': name, 'sha256': sha(path), 'bytes': path.stat().st_size})
        flush()

    def obj_points(path):
        with path.open(encoding='utf-8', errors='replace') as stream:
            return [[float(c) for c in line.split()[1:4]] for line in stream if line.startswith('v ')]

    case = json.loads((OUT / 'config.json').read_text(encoding='utf-8'))
    source = OUT / 'source.obj'
    shutil.copy2(case['input'], source)
    if sha(source) != case['sourceSha256']:
        raise RuntimeError('Pinned source hash mismatch')
    if case['scenario'] not in ('baseline', 'keep-creases', 'detect-edges'):
        raise RuntimeError('Unknown scenario')
    result.update(scenario=case['scenario'], target=case['targetThousands'], sourceSha256=sha(source))
    flush()

    zbc.set_next_filename(str(source))
    press('Tool:Import')
    # Record the import similarity so outputs can be mapped back to source units.
    names = ['Tool:Export:Scale'] + ['Tool:Export:' + axis + ' Offset' for axis in 'XYZ']
    names = [next((p for p in [n, n.replace(' Offset', 'Offset')] if zbc.exists(p)), None) for n in names]
    if any(n is None for n in names):
        raise RuntimeError('Export transform controls missing')
    old = [zbc.get(n) for n in names]
    for path, value in zip(names, [1, 0, 0, 0]):
        setval([path], value)
    export('internal.obj')
    for path, value in zip(names, old):
        setval([path], value)
    original, internal = obj_points(source), obj_points(OUT / 'internal.obj')
    if len(original) != len(internal):
        raise RuntimeError('Import vertex count/correspondence changed')
    low0 = [min(p[i] for p in original) for i in range(3)]
    high0 = [max(p[i] for p in original) for i in range(3)]
    low1 = [min(p[i] for p in internal) for i in range(3)]
    high1 = [max(p[i] for p in internal) for i in range(3)]
    # A flat source has one zero extent (open plane): that axis takes the mean scale of the others.
    # Import is a uniform similarity; the ordered residual below still checks every axis.
    scales = [(high1[i] - low1[i]) / (high0[i] - low0[i]) if high0[i] > low0[i] else None for i in range(3)]
    known = [s for s in scales if s is not None]
    if not known:
        raise RuntimeError('Source has no extent')
    scales = [sum(known) / len(known) if s is None else s for s in scales]
    offsets = [low1[i] - scales[i] * low0[i] for i in range(3)]
    residual = max(math.dist([s[i] * scales[i] + offsets[i] for i in range(3)], t) for s, t in zip(original, internal))
    result['sourceToTool'] = {'diagonal': scales, 'offset': offsets, 'maxOrderedResidual': residual, 'vertices': len(original)}
    flush()

    setval(['Transform:Activate Symmetry'], 0)
    settings = [(('Target Polygons Count', 'Target Polygon Count', 'TargetPolygonsCount'), case['targetThousands']),
                (('KeepCreases', 'Keep Creases'), 0), (('DetectEdges', 'Detect Edges'), 0),
                (('KeepGroups', 'Keep Groups'), 0), (('FreezeGroups', 'Freeze Groups'), 0),
                (('SmoothGroups', 'Smooth Groups'), 0), (('FreezeBorder', 'Freeze Border', 'FreezeBorders'), 0)]
    for aliases, value in settings:
        control(aliases, value)
    if case['scenario'] == 'keep-creases':
        setval(['Tool:Geometry:Crease:CTolerance'], case['creaseDegrees'])
        press('Tool:Geometry:Crease:Crease')
        control(('KeepCreases', 'Keep Creases'), 1)
    elif case['scenario'] == 'detect-edges':
        control(('DetectEdges', 'Detect Edges'), 1)
    controls = [P + n for n in ['AdaptiveSize', 'Adaptive Size', 'Adapt', 'Retry', 'KeepCreases', 'Keep Creases',
                                  'DetectEdges', 'KeepGroups', 'FreezeGroups', 'FreezeBorder', 'Target Polygons Count']]
    result['effectiveControls'] = {p: zbc.get(p) for p in controls if zbc.exists(p)}
    result['beforeCounts'] = [zbc.query_mesh3d(0), zbc.query_mesh3d(1)]
    flush()
    started = time.time()
    press(P + 'ZRemesher')
    result['remeshSeconds'] = time.time() - started
    result['afterCounts'] = [zbc.query_mesh3d(0), zbc.query_mesh3d(1)]
    export('after.obj')
    temp = Path(os.environ['LOCALAPPDATA']) / 'Temp/ZBrushData2026'
    packets = []
    for name in ['remeshsettings.txt', 'objIn.goz', 'objOut.goz', 'zprogress.txt']:
        matches = [p for p in temp.rglob(name) if p.is_file() and p.stat().st_mtime >= started - 2]
        if len(matches) > 1:
            raise RuntimeError('Ambiguous fresh packet ' + name)
        if matches:
            dest = OUT / name
            shutil.copy2(matches[0], dest)
            packets.append({'name': name, 'sha256': sha(dest)})
    result.update(passed=True, status='exported-unqualified', packets=packets)
except BaseException:
    result.update(status='failed', error=traceback.format_exc())
flush()
sys.exit(0 if result['passed'] else 1)
