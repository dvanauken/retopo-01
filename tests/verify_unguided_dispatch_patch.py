"""Check the separately requested dispatch patch without changing the worktree."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests/toilet-final-audit/dispatch-separation'
OUT.mkdir(parents=True, exist_ok=True)
GIT = ['git', '-c', 'safe.directory=C:/dbva/code/retopo-1']
sha = lambda value: hashlib.sha256(value).hexdigest()
current = (ROOT / 'curved_quad.py').read_bytes()
tested = (ROOT / 'tests/toilet-coarse-browser/no-guides/executed-source/curved_quad.py').read_bytes()
assert sha(current) == 'a460fb64a92e0a68c33a638dda2cd2fec56c0bcc347a3a50d98347cb007ac6f2'
assert sha(tested) == 'c59473c8e1f69c890e92eb6f18619c4082ddeb2dd201afd7fb73b9fa4068355c'
patch_path = ROOT / 'patches/enable-unguided-fallback.patch'
patch_path.parent.mkdir(exist_ok=True)
patch = ''.join(difflib.unified_diff(current.decode().splitlines(True), tested.decode().splitlines(True), fromfile='a/curved_quad.py', tofile='b/curved_quad.py'))
patch_path.write_bytes(patch.encode())
scratch = ROOT / 'runs/dispatch-patch-verification'
scratch.mkdir(exist_ok=False)
(scratch / 'curved_quad.py').write_bytes(current)
command = GIT + ['apply', '--directory=runs/dispatch-patch-verification', str(patch_path)]
subprocess.run(command[:4] + ['--check'] + command[4:], cwd=ROOT, check=True)
subprocess.run(command, cwd=ROOT, check=True)
assert (scratch / 'curved_quad.py').read_bytes() == tested
assert (ROOT / 'curved_quad.py').read_bytes() == current
subprocess.run(GIT + ['apply', '--check', str(patch_path)], cwd=ROOT, check=True)
owned = subprocess.check_output(GIT + ['show', '425b1083bf8a9642bd4cf89c8a69c4563d50e7a3:curved_quad.py'], cwd=ROOT)
assert (ROOT / 'runs/owned-dispatch-separated.py').read_bytes() == owned
report = dict(passed=True, baseline='23a8818cf7cdccd04b98f8944df0dc9cfce87cb8',
    reason='User explicitly requested keeping the fallback patch separate while another session edits curved_quad.py.',
    patch=str(patch_path.relative_to(ROOT)), patchSha256=sha(patch_path.read_bytes()),
    sharedBeforeSha256=sha(tested), sharedAfterSha256=sha(current),
    ownedAfterSha256=sha(owned), exactTestedDispatcherRecoveredByPatch=True,
    otherSessionDispatcherRecoveredExactly=True, worktreeUnchangedDuringVerification=True,
    scope='The owned dispatch guard removal is reverted. Applying the standalone patch to the shared file reconstructs the exact dispatcher tested in native 150/600 browser solves. Those successful cases require this patch; the unpatched app is not claimed to solve them.')
(OUT / 'result.json').write_text(json.dumps(report, indent=2)+'\n', newline='\n')
print(json.dumps(report))
