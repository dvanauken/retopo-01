"""Prepare a separate multipart fixture from extract_skp_parts.py output.

No welding, hole filling, remeshing, or surface deletion is performed.
Disconnected vertex islands become independent objects, including the CAD reference.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mesh_parts import store_part


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    raw = ROOT / 'assets/raw/toilet-skp'
    source = json.loads((raw / 'source-parts.json').read_text())
    pieces = []
    for obj in source['parts']:
        v = np.asarray(obj['vertices']); f = np.asarray(obj['faces'])
        # Vertex connectivity preserves every triangle, including degenerate faces.
        parent = list(range(len(v)))
        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]; i = parent[i]
            return i
        for face in f:
            for i in face[1:]: parent[find(int(i))] = find(int(face[0]))
        groups = {}
        for i, face in enumerate(f): groups.setdefault(find(int(face[0])), []).append(i)
        for n, ids in enumerate(groups.values(), 1):
            used, mapped = np.unique(f[ids], return_inverse=True)
            pieces.append(dict(name=f"{obj['name']} island {n}", sourceObject=obj['name'],
                               sourceFaceIds=ids, vertices=v[used], faces=mapped.reshape(-1, 3)))
    all_v = np.concatenate([p['vertices'] for p in pieces])
    center = (all_v.min(0) + all_v.max(0)) / 2
    scale = 2 / np.ptp(all_v, axis=0).max()
    vertices, faces, lines = [], [], ['# Fresh SW_Toilet.skp: separate source islands, normalized Z-up.']
    manifest = []
    for i, p in enumerate(pieces):
        p['vertices'] = (p['vertices'] - center) * [-scale, -scale, scale]
        offset = len(vertices); start = len(faces)
        vertices.extend(p['vertices'].tolist()); faces.extend((p['faces'] + offset).tolist())
        lines.append('o part_' + str(i + 1))
        lines.extend('v ' + ' '.join(format(float(x), '.17g') for x in row) for row in p['vertices'])
        lines.extend('f ' + ' '.join(str(int(x) + offset + 1) for x in row) for row in p['faces'])
        p['assemblyFaceIds'] = list(range(start, len(faces)))
    obj_path = ROOT / 'assets/models/toilet-skp.obj'
    obj_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    entry = dict(id='toilet-skp', title='White toilet — original SKP parts',
                 description='Fresh SketchUp source with separate connected parts and its CAD reference. Open surfaces are preserved.',
                 source=dict(asset='SW_Toilet.skp', author='User-provided SW_Toilet', license='Original source attribution not recorded', url=''),
                 sourceSha256=hashlib.sha256(obj_path.read_bytes()).hexdigest(), target=7200,
                 maxTargetQuads=12000, displayColor='#f5f5f2', displaySmooth=True, wireOpacity=.22,
                 surface='open', canRemesh=False, requiresGuides=False, solver='surface-quads', featureLayout=True,
                 solverNotice='Select one part and Generate selected, or Work on selected to edit its guides first. Failed attempts retain the source and last accepted result.')
    model = dict(entry, vertices=vertices, faces=faces, creases=[], presets=[],
                 repair=dict(closed=False), stats=dict(triangles=len(faces), quads=0))
    model_path = ROOT / 'assets/models/toilet-skp.json'
    write(model_path, model)
    for i, p in enumerate(pieces):
        m = trimesh.Trimesh(p['vertices'], p['faces'], process=False)
        data = dict(vertices=p['vertices'].tolist(), faces=p['faces'].tolist(),
                    sourceFaceIds=p['assemblyFaceIds'], area=float(m.area),
                    repair=dict(closed=bool(m.is_watertight), consistentWinding=bool(m.is_winding_consistent), capFaces=0, capFaceStart=len(m.faces)),
                    stats=dict(triangles=len(m.faces), quads=0))
        part = store_part(entry, geometry=data, recipe=dict(kind='skp-connected-island', sourceSha256=source['sourceSha256'], object=p['sourceObject'], island=i))
        manifest.append(dict(id=f'skp-{i + 1}', name=p['name'][:80], partSource=part['partSource'],
                             closed=bool(m.is_watertight), excluded=False, triangles=len(m.faces)))
    model['initialParts'] = manifest
    write(model_path, model)
    catalog_path = ROOT / 'assets/catalog.json'
    catalog = json.loads(catalog_path.read_text())
    write(catalog_path, [e for e in catalog if e['id'] != entry['id']] + [entry])
    write(raw / 'preparation.json', dict(source=source['source'], sourceSha256=source['sourceSha256'],
          center=center.tolist(), scale=scale, rotation='180 degrees around Z',
          triangles=len(faces), parts=manifest, edits='Coordinate similarity only; source vertex connectivity retained; no caps, welding, or deleted triangles.'))
    print(json.dumps(dict(parts=len(manifest), triangles=len(faces), closedParts=sum(p['closed'] for p in manifest)), indent=2))


if __name__ == '__main__':
    main()
