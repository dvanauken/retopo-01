"""Prepare a reviewable unguided-dispatch patch in an isolated service copy."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'runs/frozen-boundary-source'
OUT=ROOT/'runs/frozen-boundary-service'
OUT.mkdir(parents=True,exist_ok=False)
snapshot=json.loads((FROZEN/'snapshot.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,digest in snapshot['files'].items():
    source=FROZEN/name;assert sha(source)==digest
    destination=OUT/name;destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,destination)
for name in ('assets','vendor','src'):
    # The source OBJ was already copied; copy remaining assets without removing it.
    shutil.copytree(ROOT/name,OUT/name,dirs_exist_ok=True)
for name in ('index.html','index.css','app.js','favicon.svg'):
    shutil.copyfile(ROOT/name,OUT/name)
path=OUT/'curved_quad.py';before=path.read_text()
old='''    if curves:
        from surface_guide_repair import construct as construct_sampled_guides
        recovered = construct_sampled_guides(source_mesh, curves, target=target, job=job,
                                             blender=blender, input_path=input_path, history=history)
        if recovered is not None:
            return recovered
'''
new='''    from surface_guide_repair import construct as construct_sampled_guides
    recovered = construct_sampled_guides(source_mesh, curves, target=target, job=job,
                                         blender=blender, input_path=input_path, history=history)
    if recovered is not None:
        return recovered
'''
assert before.count(old)==1
after=before.replace(old,new)
with path.open('w',newline='\r\n') as handle:handle.write(after)
patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/curved_quad.py',tofile='b/curved_quad.py'))
(OUT/'unguided-dispatch.patch').write_text(patch,newline='\n')
hashes={str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file()}
report=dict(complete=True,files=hashes,sourceRoot=str(FROZEN.relative_to(ROOT)),
    unpatchedDispatchSha256=snapshot['files']['curved_quad.py'],patchedDispatchSha256=sha(path),
    originalSourceSha256=sha(ROOT/'assets/models/toilet.obj'),
    scope='Isolated frozen service copy with only the reviewed if-curves dispatch guard removed. Shared repository dispatch, active sessions and user service state are untouched. Browser tests must distinguish this proposed integration from the live app.')
assert sha(OUT/'assets/models/toilet.obj')==report['originalSourceSha256']
(OUT/'snapshot.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(root=str(OUT),files=len(hashes),patchedDispatch=report['patchedDispatchSha256'])))
