"""Old and new layout engine on inputs without face sizes: outputs must be byte-identical.

Usage: python engine-parity.py OLD.exe NEW.exe INPUTS OUT
INPUTS is an open-surface folder of a job (source.obj, segments.txt, guide-segments.txt,
crease-band.txt, constrained/source.obj, constrained/constrained-edges.txt with three columns).
The inputs are copied into OUT/inputs so the record stands on its own.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
for extra in (ROOT, ROOT / 'engine/targets/zbrush/experiments/python', ROOT / 'engine/targets/zbrush/clone'):
    sys.path.insert(0, str(extra))
from guided_layout import runtime

OLD, NEW, INPUTS, OUT = (Path(x).resolve() for x in sys.argv[1:5])
OUT.mkdir(parents=True, exist_ok=True)
J = OUT / 'inputs'
(J / 'constrained').mkdir(parents=True, exist_ok=True)
for name in ('source.obj', 'segments.txt', 'guide-segments.txt', 'crease-band.txt', 'constrained/source.obj', 'constrained/constrained-edges.txt'):
    shutil.copy2(INPUTS / name, J / name)
if any(len(line.split()) != 3 for line in (J / 'constrained/constrained-edges.txt').read_text().splitlines()[1:] if line.strip()):
    raise SystemExit('The control list must have three columns')
_, env, _ = runtime(None)
env['OMP_NUM_THREADS'] = '4'
base = ['-i', str(J / 'source.obj'), '-f', '200', '-seed', '2', '-boundary']
guides = ['-guides', str(J / 'segments.txt'), '-guide-width', '.75', '-orientation-weight', '1', '-position-weight', '0']
band = ['-guides', str(J / 'crease-band.txt'), '-guide-width', '.75', '-orientation-weight', '1', '-position-weight', '0']
listed = ['-i', str(J / 'constrained/source.obj'), '-boundary', '-constrained-edges', str(J / 'constrained/constrained-edges.txt')]
cases = {'caps': base + ['-sharp', '-size-caps-exact'] + guides, 'sharp': base + ['-sharp'] + guides,
         'adaptive': base + ['-adaptive', '-guides', str(J / 'guide-segments.txt'), '-guide-width', '.75', '-orientation-weight', '1', '-position-weight', '0'],
         'plain': ['-i', str(J / 'source.obj'), '-f', '300', '-seed', '1', '-boundary'],
         'rows-strict-seed0': listed + ['-f', '200', '-seed', '0'] + band,
         'rows-strict-seed52': listed + ['-f', '200', '-seed', '52'] + band,
         'rows-size-caps-seed2': listed + ['-f', '200', '-seed', '2', '-size-caps'] + band,
         'rows-size-caps-seed3': listed + ['-f', '200', '-seed', '3', '-size-caps'] + band}
rows = []
for name, arguments in cases.items():
    digests = []
    for tag, exe in (('old', OLD), ('new', NEW)):
        target = OUT / f'{name}-{tag}.obj'
        result = subprocess.run([str(exe)] + arguments + ['-o', str(target)], env=env, capture_output=True, timeout=600)
        digests.append(hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() and not result.returncode else f'exit {result.returncode}')
    rows.append(dict(case=name, old=digests[0], new=digests[1], identical=digests[0] == digests[1]))
    print(name, digests[0][:16], digests[1][:16], 'IDENTICAL' if digests[0] == digests[1] else 'DIFFERENT', flush=True)
(OUT / 'parity.json').write_text(json.dumps(dict(old=hashlib.sha256(OLD.read_bytes()).hexdigest(), new=hashlib.sha256(NEW.read_bytes()).hexdigest(), cases=rows), indent=1))
sys.exit(0 if all(row['identical'] for row in rows) else 1)
