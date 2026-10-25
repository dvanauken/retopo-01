"""Build the exact owned code candidate without staging another session's edits."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/owned-boundary-candidate'
OUT.mkdir(parents=True,exist_ok=False)
git=['git','-c','safe.directory=C:/dbva/code/retopo-1']
parent=subprocess.run([*git,'rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True).stdout.decode().strip()
assert parent=='425b1083bf8a9642bd4cf89c8a69c4563d50e7a3'
def head(name):return subprocess.run([*git,'show',parent+':'+name],cwd=ROOT,check=True,capture_output=True).stdout
def write(name,content):
    path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
sha=lambda content:hashlib.sha256(content).hexdigest()
frozen=ROOT/'runs/frozen-boundary-source'
snapshot=json.loads((frozen/'snapshot.json').read_text())
for name in snapshot['files']:
    write(name,(frozen/name).read_bytes())
tracked=subprocess.run([*git,'ls-tree','--name-only',parent],cwd=ROOT,check=True,capture_output=True).stdout.decode().splitlines()
for name in tracked:
    if name.endswith('.py'):write(name,head(name))

owned={}
for name in ('surface_guide_refine.py','surface_boundary_repair.py','tests/test_surface_boundary_repair.py','tests/verify_surface_boundary_integration.py'):
    owned[name]=(ROOT/name).read_bytes()
repair=(ROOT/'surface_guide_repair.py').read_bytes()
new=b"    guided = cq.guides_pass(fit, spacing)"
old=b"    guided = all(p['p95Distance'] <= .2 * spacing and p['p95TangentAngleDegrees'] <= 30 for p in fit)"
assert repair.count(new)==1
owned['surface_guide_repair.py']=repair.replace(new,old)
layout=(ROOT/'tests/test_surface_layout_retries.py').read_text()
external='''        # This exercises the guided retry route. An empty guide set enters the
        # separate boundary-layout fallback after all count retries fail.
        source, curves, history = object(), [object()], []
'''
assert layout.count(external)==1
layout=layout.replace(external,'        source, curves, history = object(), [], []\n')
newline='\r\n' if b'\r\n' in head('tests/test_surface_layout_retries.py') else '\n'
owned['tests/test_surface_layout_retries.py']=layout.replace('\n',newline).encode()
cq=head('curved_quad.py');newline='\r\n' if b'\r\n' in cq else '\n'
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
old,new=old.replace('\n',newline).encode(),new.replace('\n',newline).encode()
assert cq.count(old)==1
owned['curved_quad.py']=cq.replace(old,new)
for name,content in owned.items():write(name,content)
for name in ('tests/test_surface_guide_repair.py','tests/test_surface_guide_joint.py'):
    write(name,head(name))
for name in ('tests/toilet-layout-inventory/alternative-seeds-345/target-150-seed-4.json',
             'tests/toilet-boundary-bridge/coarse150-seed4/bridge-0/input.json',
             'tests/toilet-boundary-bridge/coarse150-seed4/executed-fitter.py'):
    write(name,(ROOT/name).read_bytes())
report=dict(complete=True,parent=parent,ownedBlobHashes={name:sha(content) for name,content in owned.items()},
    worktreeHashes={name:sha((ROOT/name).read_bytes()) for name in owned},
    scope='Exact proposed owned runtime/test blobs over HEAD425b108. Shared guide-policy edits in repair and the guided layout-test fixture are excluded; CQ contains only guard removal over HEAD. Worktree files and real index remain untouched. This is a concrete candidate for separate verification and scoped staging.')
(OUT/'owned-blobs.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(root=str(OUT),ownedBlobs=len(owned))))
