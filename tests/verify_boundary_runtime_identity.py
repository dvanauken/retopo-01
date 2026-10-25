"""Prove the applied runtime matches the frozen, actually exercised service."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
SERVICE=ROOT/'runs/frozen-boundary-service'
OUT=ROOT/'tests/surface-boundary-repair/runtime-identity'
OUT.mkdir(parents=True,exist_ok=False)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
snapshot=json.loads((SERVICE/'snapshot.json').read_text())
browser=ROOT/'tests/toilet-coarse-browser/no-guides/result.json'
report=json.loads(browser.read_text())
assert report['complete'] and report['passed'] and report['frozenImplementationUnchanged']
matched={}
for name,digest in snapshot['files'].items():
    if name=='unguided-dispatch.patch':continue
    assert sha(SERVICE/name)==digest,name
    assert sha(ROOT/name)==digest,name
    matched[name]=digest
assert sha(ROOT/'assets/models/toilet.obj')==snapshot['originalSourceSha256']
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
content=(ROOT/'curved_quad.py').read_bytes();newline='\r\n' if b'\r\n' in content else '\n'
old,new=old.replace('\n',newline).encode(),new.replace('\n',newline).encode()
assert content.count(new)==1
assert hashlib.sha256(content.replace(new,old)).hexdigest()==snapshot['unpatchedDispatchSha256']
owned=ROOT/'runs/owned-boundary-candidate/tests/surface-boundary-repair/owned-candidate'
owned_report=json.loads((owned/'result.json').read_text())
assert owned_report['passed'] and not owned_report['sharedGuidePolicyChanged']
shutil.copytree(owned,ROOT/'tests/surface-boundary-repair/owned-candidate')
shutil.copyfile(ROOT/'runs/owned-boundary-candidate/owned-blobs.json',OUT/'owned-blobs.json')
proof=dict(complete=True,passed=True,matchedFiles=matched,
    browserReport=str(browser.relative_to(ROOT)),browserReportSha256=sha(browser),
    ownedCandidateReport='tests/surface-boundary-repair/owned-candidate/result.json',
    appliedDispatchSha256=sha(ROOT/'curved_quad.py'),preservedSharedDispatchSha256=snapshot['unpatchedDispatchSha256'],
    scope='Every frozen implementation/app/source asset file (excluding the patch text itself) is byte-identical in the applied worktree. Undoing only the guard dedent exactly reconstructs the other session shared dispatcher. The native browser exercised this same runtime in an isolated service directory; absolute service paths and job IDs differ. Owned code over the committed baseline separately passes25controls without the shared guide-policy changes.')
(OUT/'result.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(dict(passed=True,matchedFiles=len(matched),ownedTests=owned_report['tests'])))
