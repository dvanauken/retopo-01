"""Recheck the shell against frozen current UI bytes without touching a user server."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / 'runs/frozen-boundary-service'
OUT = ROOT / 'tests/toilet-final-audit/workspace'
OUT.mkdir(parents=True, exist_ok=False)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
names = ['app.js', 'index.html', 'index.css', 'server.py', 'src/view/WorkspaceShell.js']
hashes = {name: sha(ROOT / name) for name in names}
assert all(sha(SERVICE / name) == digest for name, digest in hashes.items())
pointer = ROOT / 'runs/server.json'
before = pointer.read_bytes()
source = ROOT / 'tests/verify_workspace_shell.py'
original = source.read_text(encoding='utf-8')
old = "ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'tests/workspace-shell';OUT.mkdir(exist_ok=True)"
assert original.count(old) == 1
replacement = f"ROOT=Path({str(SERVICE)!r});OUT=Path({str(OUT)!r});OUT.mkdir(exist_ok=True)"
executed = original.replace(old, replacement)
runner = OUT / 'executed-test.py'
runner.write_text(executed, encoding='utf-8', newline='\n')
(OUT / 'original-test.py').write_bytes(source.read_bytes())
completed = subprocess.run([sys.executable, '-X', 'utf8', str(runner)], cwd=SERVICE)
result = json.loads((OUT / 'result.json').read_text())
scope = dict(
    passed=completed.returncode == 0 and result['passed'],
    originalScript='tests/verify_workspace_shell.py', originalSha256=sha(source),
    executedScript=str(runner.relative_to(ROOT)), executedSha256=sha(runner),
    substitution='Only ROOT and OUT paths change; all browser assertions are unchanged.',
    sourceHashes=hashes,
    sourceUnchanged=all(sha(ROOT / name) == digest == sha(SERVICE / name)
                        for name, digest in hashes.items()),
    userServicePointerUnchanged=pointer.read_bytes() == before,
    scope='Generic shell controls on the hexagon, complemented by the current toilet editing/rendering/repeated-use suites. No toilet generation claim.')
scope['passed'] &= scope['sourceUnchanged'] and scope['userServicePointerUnchanged']
(OUT / 'scope.json').write_text(json.dumps(scope, indent=2) + '\n', newline='\n')
print(json.dumps(dict(passed=scope['passed'], checks=len(result['checks']))))
sys.exit(0 if scope['passed'] else 1)
