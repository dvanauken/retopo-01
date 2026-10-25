"""Freeze only the local modules needed for an isolated source-to-mesh probe."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/frozen-boundary-source'
OUT.mkdir(parents=True,exist_ok=False)
paths=list(ROOT.glob('*.py'))
for relative in ('engine/targets/zbrush/clone','engine/targets/zbrush/experiments/python'):
    paths.extend((ROOT/relative).glob('*.py'))
paths.extend(ROOT/name for name in ('assets/models/toilet.obj','scripts/quadriflow_mesh.py','tests/probe_toilet_unguided_fallback.py'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={}
for path in sorted(set(paths)):
    relative=path.relative_to(ROOT);destination=OUT/relative
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(path,destination)
    digest=sha(path);assert sha(destination)==digest
    hashes[str(relative)]=digest
report=dict(complete=True,files=hashes,
    scope='Read-only copy of current local modules and the original source for an isolated fresh Blender/fitting probe. No retained output mesh is input. This freezes concurrent shared-session edits without changing or staging them.')
(OUT/'snapshot.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(root=str(OUT),files=len(hashes))))
