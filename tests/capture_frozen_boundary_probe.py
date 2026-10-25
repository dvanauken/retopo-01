"""Retain the frozen fresh-source results and the exact executed modules."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'runs/frozen-boundary-source'
source=FROZEN/'tests/toilet-unguided-fallback/boundary-fresh'
OUT=ROOT/'tests/toilet-unguided-fallback/boundary-fresh'
report=json.loads((source/'result.json').read_text())
assert report['complete'] and report['generationPassed'] and report['implementationUnchanged']
shutil.copytree(source,OUT)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,digest in report['sourceHashes'].items():
    path=FROZEN/name;assert sha(path)==digest
    destination=OUT/'executed-source'/name;destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(path,destination)
snapshot=json.loads((FROZEN/'snapshot.json').read_text())
assert all(sha(FROZEN/name)==digest for name,digest in snapshot['files'].items())
(OUT/'frozen-snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
links=[]
for case,label,reference in ((report['cases'][0],'coarse150-bridge-seed4','tests/toilet-boundary-bridge/coarse150-seed4/bridge-0'),
                             (report['cases'][1],'coarse600-neighbor','tests/toilet-target-neighborhood/coarse600-upper-neighbors/none-600-layout-660')):
    actual=OUT/case['name'];old=ROOT/reference
    assert (actual/'output.obj').read_bytes()==(old/'output.obj').read_bytes()
    packet=json.loads((actual/'mesh.json').read_text());expected=json.loads((old/'mesh.json').read_text())
    assert all(packet[key]==expected[key] for key in ('vertices','faces','guidePaths'))
    assert json.loads((actual/'curves.json').read_text())['curves']==[]
    assert json.loads((actual/'settings.json').read_text())['target']==case['target']
    audits={}
    for family in ('toilet-fresh-geometry','toilet-all-diagonal-audit'):
        path=ROOT/'tests'/family/label/'result.json';data=json.loads(path.read_text())
        assert data['complete'] and any(c['passed'] and c['outputSha256']==case['outputSha256'] for c in data['cases'])
        audits[family]=dict(report=str(path.relative_to(ROOT)),sha256=sha(path))
    links.append(dict(name=case['name'],passed=True,outputSha256=case['outputSha256'],target=case['target'],faces=case['faces'],audits=audits))
(OUT/'independent-identity.json').write_text(json.dumps(dict(complete=True,passed=True,cases=links,
    scope='Fresh original-source results from frozen current modules are byte-identical to independently audited150/600 experimental exports. Source, target, empty guide list, positions, faces and paths match; the shared application dispatch is still unchanged.'),indent=2)+'\n')
print(json.dumps(dict(passed=True,cases=len(links),files=len(snapshot['files']))))
