"""Localize the remaining coarse-fit contacts against the original source."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj

OUT = ROOT / 'tests/toilet-coarse-contacts/layout172'
OUT.mkdir(parents=True, exist_ok=False)
(OUT / 'executed-test.py').write_bytes(Path(__file__).read_bytes())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
sv, sf = read_obj(ROOT / 'assets/models/toilet.obj')
source = trimesh.Trimesh(sv, sf, process=False)
path = ROOT / 'tests/toilet-objective-controls/coarse150-layout172-ratio34/coarse-150/final-candidate.json'
packet = json.loads(path.read_text())
v, f = np.asarray(packet['vertices']), np.asarray(packet['faces'])
contacts = cq.surface_intersections(v, f, both_quad_diagonals=True)
quality = cq.quad_quality(v, f, 150)
centers = v[f].mean(axis=1)
near, distance, owners = trimesh.proximity.closest_point(source, centers)
normal = np.cross(v[f[:, 2]] - v[f[:, 0]], v[f[:, 3]] - v[f[:, 1]])
normal /= np.maximum(np.linalg.norm(normal, axis=1), 1e-12)[:, None]
pairs = contacts['nonAdjacentIntersectingFacePairs'] + contacts['adjacentIntersectingFacePairs']
records = []
for a, b in pairs:
    records.append(dict(faces=[a,b], sharedVertices=sorted(set(map(int,f[a])) & set(map(int,f[b]))),
                        centers=centers[[a,b]].tolist(), sourceAnchors=near[[a,b]].tolist(),
                        sourceAnchorDistances=distance[[a,b]].tolist(),
                        sourceNormalDot=float(source.face_normals[owners[a]] @ source.face_normals[owners[b]]),
                        fittedNormalDot=float(normal[a] @ normal[b]),
                        orientationToSource=np.einsum('ij,ij->i', normal[[a,b]], source.face_normals[owners[[a,b]]]).tolist()))
fig = plt.figure(figsize=(14,6))
bad = {i for pair in pairs for i in pair}
colors = ['#ed704b' if i in bad else '#cbd9e7' for i in range(len(f))]
for i, (elev, azim) in enumerate(((22,-58),(20,35))):
    ax = fig.add_subplot(1,2,i+1,projection='3d')
    ax.add_collection3d(Poly3DCollection(v[f], facecolors=colors, edgecolors='#304b66', linewidths=.6, alpha=.82))
    for index in sorted(bad):
        ax.text(*centers[index], str(index), fontsize=8, color='#8a1b00')
    low, high = sv.min(axis=0), sv.max(axis=0)
    ax.set(xlim=(low[0],high[0]),ylim=(low[1],high[1]),zlim=(low[2],high[2]),xlabel='X',ylabel='Y',zlabel='Z')
    ax.set_box_aspect(high-low)
    ax.view_init(elev=elev,azim=azim)
fig.suptitle('Target 150: shape passes, intersecting faces highlighted (134 quads)')
fig.tight_layout()
fig.savefig(OUT / 'contact-faces.png', dpi=150)
plt.close(fig)
report = dict(complete=True, productionResult=False, qualified=False,
              inputFile=str(path.relative_to(ROOT)), inputSha256=sha(path), quality=quality,
              intersections=contacts, contactLocations=records,
              sourceHashes={name:sha(ROOT/name) for name in ('assets/models/toilet.obj','surface_intersections.py','quad_quality.py','tests/inspect_toilet_coarse_contacts.py')},
              scope='Exact all-diagonal contact pairs localized on a retained shape-passing coarse candidate. Nearest centroid normals are diagnostic only; they are not a certified surface correspondence. Original geometry and acceptance gates are unchanged.')
(OUT / 'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(shapePassed=quality['passed'], faces=len(f), contacts=len(pairs), pairs=records)))
inventory=json.loads((ROOT/'tests/toilet-layout-inventory/alternative-seeds-345/result.json').read_text())
print(json.dumps([dict(name=c['name'],faces=c['quality']['faces'],connectivity=c['connectivityScreenPassed'],
                      contacts=len(c['contacts']['nonAdjacentIntersectingFacePairs'])+len(c['contacts']['adjacentIntersectingFacePairs']))
                  for c in inventory['cases'] if c['target']==150]))
