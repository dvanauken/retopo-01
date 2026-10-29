"""Repeat registered-path mechanism checks in a new output directory.

These checks establish source/output path topology, not the app's complete shape,
contact, distance or low-count acceptance gates. Optional real-source folders must
contain source.obj and features.txt and are recorded even when rejected.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess


def write_fixture(folder, vertices, faces, paths):
    folder.mkdir(parents=True)
    (folder / 'source.obj').write_text(
        ''.join('v ' + ' '.join(format(c, '.17g') for c in v) + '\n' for v in vertices)
        + ''.join('f ' + ' '.join(str(i + 1) for i in f) + '\n' for f in faces), encoding='utf-8')
    (folder / 'features.txt').write_text(str(len(paths)) + '\n' + ''.join(
        f'{identity} {int(closed)} {len(vertices)} ' + ' '.join(map(str, vertices)) + '\n'
        for identity, closed, vertices in paths), encoding='utf-8')


def inspect_graph(mesh, report):
    faces = []
    for line in mesh.read_text(encoding='utf-8').splitlines():
        columns = line.split()
        if columns and columns[0] == 'f':
            faces.append([int(v.split('/')[0]) - 1 for v in columns[1:]])
    edges = {tuple(sorted((a, b))) for f in faces for a, b in zip(f, f[1:] + f[:1])}
    checks = []
    for path in report['paths']:
        vertices = path['vertices']
        pairs = list(zip(vertices, vertices[1:] + vertices[:1])) if path['closed'] else list(zip(vertices, vertices[1:]))
        checks.append(dict(id=path['id'], vertexCount=len(vertices),
                           simple=len(set(vertices)) == len(vertices),
                           actualEdges=all(tuple(sorted(e)) in edges for e in pairs),
                           noncollapsed=len(vertices) >= (3 if path['closed'] else 2)))
    return dict(faceCount=len(faces), paths=checks,
                passed=all(c['simple'] and c['actualEdges'] and c['noncollapsed'] for c in checks))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New directory; an existing directory is rejected')
    parser.add_argument('--engine', type=Path)
    parser.add_argument('--real-source', action='append', default=[], metavar='LABEL=FOLDER')
    parser.add_argument('--real-target', type=int, default=200)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    output = args.output or here / 'validation-runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = output.resolve()
    if output.exists():
        raise ValueError('Refusing to overwrite existing validation evidence')
    output.mkdir(parents=True)
    manifest = json.loads((here / 'manifest.json').read_text(encoding='utf-8'))
    engine = (args.engine or here / 'quadriflow.exe').resolve()
    engine_hash = hashlib.sha256(engine.read_bytes()).hexdigest()
    if not args.engine and engine_hash != manifest['executableSha256']:
        raise ValueError('Engine hash differs from the frozen manifest')
    environment = os.environ.copy()
    environment['PATH'] = manifest['runtimeDirectory'] + os.pathsep + environment['PATH']
    n = 21
    plane_vertices = [(i / (n - 1), j / (n - 1), 0) for j in range(n) for i in range(n)]
    plane_faces = []
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i
            plane_faces.extend([(a, a + 1, a + n + 1), (a, a + n + 1, a + n)])
    write_fixture(output / 'sources/plane', plane_vertices, plane_faces, [(7, False, [10 * n + i for i in range(n)])])
    n, m = 64, 9
    cylinder_vertices = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), j / (m - 1))
                         for j in range(m) for i in range(n)]
    cylinder_faces = []
    for j in range(m - 1):
        for i in range(n):
            a, b = j * n + i, j * n + (i + 1) % n
            cylinder_faces.extend([(a, b, b + n), (a, b + n, a + n)])
    write_fixture(output / 'sources/cylinder', cylinder_vertices, cylinder_faces, [(7, True, [4 * n + i for i in range(n)])])
    write_fixture(output / 'sources/close-cylinder', cylinder_vertices, cylinder_faces,
                  [(identity, True, [j * n + i for i in range(n)]) for identity, j in enumerate([3, 4])])
    cases = [(f'{name}-{target}', output / 'sources' / name, target, [], True)
             for name in ['plane', 'cylinder', 'close-cylinder'] for target in [100, 200]]
    for item in args.real_source:
        label, folder = item.split('=', 1)
        if not label or any(c in label for c in '/\\:'):
            raise ValueError('Real-source labels must be plain directory names')
        cases.append((label, Path(folder).resolve(), args.real_target, ['-size-caps-exact'], False))
    results = []
    for label, source, target, flags, synthetic in cases:
        destination = output / label
        destination.mkdir()
        command = [str(engine), '-i', str(source / 'source.obj'), '-o', str(destination / 'output.obj'),
                   '-f', str(target), '-seed', '0', '-boundary', '-registered-features', str(source / 'features.txt'),
                   '-registered-output', str(destination / 'features.json')] + flags
        result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=60,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (destination / 'process.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        sidecar_path = destination / 'features.json'
        report = json.loads(sidecar_path.read_text(encoding='utf-8')) if sidecar_path.exists() else None
        row = dict(case=label, synthetic=synthetic, target=target, command=command, exitCode=result.returncode,
                   sourceSha256=hashlib.sha256((source / 'source.obj').read_bytes()).hexdigest(),
                   pathsSha256=hashlib.sha256((source / 'features.txt').read_bytes()).hexdigest(), report=report)
        if (destination / 'output.obj').exists() and report:
            row['independentGraph'] = inspect_graph(destination / 'output.obj', report)
        row['passed'] = result.returncode == 0 and report is not None and report['passed'] and row.get('independentGraph', {}).get('passed', False)
        results.append(row)
        (output / 'results.json').write_text(json.dumps(dict(engineSha256=engine_hash, cases=results), indent=2), encoding='utf-8')
        print(json.dumps(dict(case=label, passed=row['passed'], exitCode=result.returncode)), flush=True)
    controls_pass = all(row['passed'] for row in results if row['synthetic'])
    print(json.dumps(dict(output=str(output), allSyntheticPassed=controls_pass)))
    return 0 if controls_pass else 1


if __name__ == '__main__':
    raise SystemExit(main())
