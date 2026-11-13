"""Package the constrained-sizes-19 build as the application's layout engine.

Keeps the previous executable, archive and manifest (constrained-edges-18) in the
folder given as argv[1]. The new source archive is the previous one with the
src/ files of the build record.
"""
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

BUILD = 'constrained-sizes-19'
PREVIOUS = 'constrained-edges-18'
RECORD = Path(r'C:\dbva\code\ghidra-workbench\work\retopo-guided-layout\build-records') / BUILD
ENGINE = Path(r'C:\dbva\code\retopo-1\engine\guided-quadriflow')
backup = Path(sys.argv[1])
backup.mkdir(parents=True, exist_ok=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


manifest = json.loads((ENGINE / 'manifest.json').read_text())
if manifest['build'] != PREVIOUS:
    raise SystemExit('Unexpected packaged build: ' + manifest['build'])
for name in ('quadriflow.exe', 'source.zip', 'manifest.json'):
    shutil.copy2(ENGINE / name, backup / name)
sources = {p.name: p.read_bytes() for p in (RECORD / 'src').iterdir() if p.is_file()}
recorded = {row['path']: row['sha256'] for row in json.loads((RECORD / 'source-hashes.json').read_text())}
if any(hashlib.sha256(data).hexdigest() != recorded[name] for name, data in sources.items()):
    raise SystemExit('Build record sources differ from their recorded hashes')
temporary = backup / 'source-new.zip'
with zipfile.ZipFile(backup / 'source.zip') as old, zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as new:
    seen = set()
    for item in old.infolist():
        data = old.read(item.filename)
        if item.filename.startswith('src/') and not item.is_dir():
            name = item.filename[4:]
            if name not in sources:
                raise SystemExit('Archive source missing from the build record: ' + name)
            data = sources[name]
            seen.add(name)
        new.writestr(item, data)
    if seen != set(sources):
        raise SystemExit('Build record has sources the archive lacks: ' + str(sorted(set(sources) - seen)))
executable = RECORD / 'quadriflow.exe'
if sha(executable) != json.loads((RECORD / 'executable.json').read_text())['sha256']:
    raise SystemExit('Build record executable differs from its recorded hash')
shutil.copy2(executable, ENGINE / 'quadriflow.exe')
shutil.copy2(temporary, ENGINE / 'source.zip')
manifest.update(build=BUILD, executableSha256=sha(ENGINE / 'quadriflow.exe'), sourceArchiveSha256=sha(ENGINE / 'source.zip'),
                capabilities=['constrained-edges', 'constrained-edge-sizes'],
                previousBuild=PREVIOUS, previousExecutableSha256=sha(backup / 'quadriflow.exe'), previousSourceArchiveSha256=sha(backup / 'source.zip'))
(ENGINE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: manifest[k] for k in ('build', 'executableSha256', 'sourceArchiveSha256', 'capabilities', 'previousBuild')}, indent=1))
