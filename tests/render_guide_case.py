"""Top-view pictures of quad meshes with an authored guide and the edge path that follows it.

Usage: python tests/render_guide_case.py --source S.obj --curves curves.json --target 200 --out picture.png
           --mesh "ZBrush=native.obj" --mesh "App=output.obj"
Each panel shows the faces seen from +Z (triangles tinted), the authored guide in red and the
output edge path guide_rows measures in blue, with turn vertices marked. The JSON written beside
the picture holds, per mesh, the guide report, the crease-row (rim) report measured on its quads,
the old connected-path guide measure and the 2026-10-28 rim witness distances.
"""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / 'engine/targets/zbrush/experiments/python', ROOT / 'engine/targets/zbrush/clone'):
    sys.path.insert(0, str(extra))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, LineCollection
import trimesh
from measure_geometry import read_obj
import guide_rows
from crease_rows import find_row, measure as measure_crease_rows
from source_features import detect, segment_distances, use_crease_angle
import curved_quad as cq

WITNESS_EDGE = (1308, 1309)                                             # island 6 rim witness (GUIDED_LAYOUT.md)
WITNESS_POINT = (-0.4193387256636727, -0.5726395985644704, 0.18908541434501042)


def numbers(source, triangles, points, faces, curves, spacing, guide_report, angle, target):
    """Face count, guide loop, old guide measure and rim rows for one mesh, distances in requested faces."""
    points = np.asarray(points, float)
    quads = np.asarray([f for f in faces if len(f) == 4], int)
    use_crease_angle(angle)
    edges, _ = detect(source, triangles, spacing, target=target)
    rows = measure_crease_rows(source, triangles, edges, points, quads, spacing)
    every = np.asarray(sorted(guide_rows.edge_faces(faces)), int)
    a, b = points[every[:, 0]], points[every[:, 1]]
    result = dict(faces=len(faces), quads=int(len(quads)), triangles=sum(len(f) == 3 for f in faces),
                  guides=[dict(passed=g['passed'], failures=g['failures'], pathVertices=g.get('pathVertices'), turns=g.get('values', {}).get('turns'),
                               p95OverH=g.get('valuesInFaces', {}).get('rowP95'), maxOverH=g.get('valuesInFaces', {}).get('rowMax'),
                               endMaxOverH=g.get('valuesInFaces', {}).get('rowEndMax'), tangentP95Degrees=g.get('values', {}).get('rowTangentP95Degrees'))
                          for g in guide_report['guides']],
                  rimRows=dict(required=rows['required'], realized=rows['realized'], passed=rows['passed'],
                               chains=[dict(lengthFaces=c['lengthFaces'], passed=c['passed'], failures=c['failures'],
                                            p95OverH=c.get('values', {}).get('rowP95', float('nan')) / spacing, maxOverH=c.get('values', {}).get('rowMax', float('nan')) / spacing,
                                            endMaxOverH=c.get('values', {}).get('rowEndMax', float('nan')) / spacing,
                                            tangentP95Degrees=c.get('values', {}).get('rowTangentP95Degrees')) for c in rows['chains']]))
    if len(source) > max(WITNESS_EDGE):
        samples = np.linspace(source[WITNESS_EDGE[0]], source[WITNESS_EDGE[1]], 33)
        result['rimWitness'] = dict(pointToNearestEdgeOverH=float(segment_distances(np.array([WITNESS_POINT]), a, b)[0] / spacing),
                                    edgeMaxToNearestEdgeOverH=float(segment_distances(samples, a, b).max() / spacing))
    old = []
    for curve in curves:
        try:
            path = cq._guide_path(points, every, curve, spacing)[0]
            fit = cq._guide_fit(points, [path], [curve], spacing)[0]
            old.append(dict(p95OverH=fit['p95Distance'] / spacing, tangentP95Degrees=fit['p95TangentAngleDegrees'],
                            passed=bool(cq.guides_pass([fit], spacing)), turns=len(guide_rows.turns(path['vertices'], guide_rows.edge_faces(faces)))))
        except ValueError as error:
            old.append(dict(error=str(error)))
    result['oldConnectedPathCheck'] = old
    return result


def panel(axis, title, points, faces, curves, spacing, window):
    points = np.asarray(points, float)
    polygons, colors, depth = [], [], []
    for face in faces:
        corners = points[list(face)]
        normal = np.cross(corners[1] - corners[0], corners[2] - corners[0])
        if len(face) == 4:
            normal = np.cross(corners[2] - corners[0], corners[3] - corners[1])
        if normal[2] <= 0:
            continue
        polygons.append(corners[:, :2])
        colors.append('#f3d9a4' if len(face) == 3 else '#e9edf2')
        depth.append(corners[:, 2].mean())
    order = np.argsort(depth)
    axis.add_collection(PolyCollection([polygons[i] for i in order], facecolors=[colors[i] for i in order], edgecolors='#39424e', linewidths=.6))
    report = guide_rows.measure(points, faces, curves, spacing)
    owners = guide_rows.edge_faces(faces)
    edges = np.asarray(sorted(owners), int)
    notes = []
    for curve, item in zip(curves, report['guides']):
        axis.plot(curve[:, 0], curve[:, 1], color='#d62728', linewidth=1.4, zorder=5)
        path = item.get('vertices') or []
        if path:
            axis.plot(points[path, 0], points[path, 1], color='#1f4fd6', linewidth=2.6, alpha=.85, zorder=6)
            turned = [path[i] for i in item.get('turnPositions', [])]
            if turned:
                axis.scatter(points[turned, 0], points[turned, 1], s=46, facecolors='none', edgecolors='#d62728', linewidths=1.6, zorder=7)
            values = item['valuesInFaces']
            notes.append(f"guide path: {item['pathVertices']} vertices, {item['values']['turns']} turns, "
                         f"P95 {values['rowP95']:.2f} h, max {values['rowMax']:.2f} h, {'PASS' if item['passed'] else 'FAIL'}")
        else:
            notes.append('guide path: none')
    arity = {n: sum(len(f) == n for f in faces) for n in (3, 4)}
    axis.set_title(f"{title}\n{len(faces)} faces ({arity[4]} quads, {arity[3]} triangles)\n" + '\n'.join(notes), fontsize=9)
    axis.set_xlim(window[0], window[1])
    axis.set_ylim(window[2], window[3])
    axis.set_aspect('equal')
    axis.set_axis_off()
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--curves', required=True)
    parser.add_argument('--target', type=int, required=True)
    parser.add_argument('--mesh', action='append', required=True, help='Title=path.obj')
    parser.add_argument('--out', required=True)
    parser.add_argument('--crease-angle', type=float, default=30.)
    arguments = parser.parse_args()
    source, triangles = read_obj(arguments.source)
    source = np.asarray(source, float)
    spacing = float(np.sqrt(trimesh.Trimesh(source, np.asarray(triangles, int), process=False).area / arguments.target))
    curves = [np.asarray(c, float) for c in json.loads(Path(arguments.curves).read_text())['curves']]
    low, high = source.min(0), source.max(0)
    pad = .03 * (high - low).max()
    window = (low[0] - pad, high[0] + pad, low[1] - pad, high[1] + pad)
    figure, axes = plt.subplots(1, len(arguments.mesh), figsize=(6.2 * len(arguments.mesh), 8.6), dpi=130)
    reports = {}
    for axis, entry in zip(np.atleast_1d(axes), arguments.mesh):
        title, path = entry.split('=', 1)
        points, faces = read_obj(path)
        faces = [list(map(int, f)) for f in faces]
        report = panel(axis, title, points, faces, curves, spacing, window)
        reports[title] = dict(file=str(path), numbers=numbers(source, np.asarray(triangles, int), points, faces, curves, spacing, report, arguments.crease_angle, arguments.target), guideRows=report)
    figure.tight_layout()
    figure.savefig(arguments.out)
    Path(arguments.out).with_suffix('.json').write_text(json.dumps(dict(spacing=spacing, target=arguments.target, meshes=reports), indent=1))
    for title, report in reports.items():
        print(title, json.dumps(report['numbers']))
    print(arguments.out)


if __name__ == '__main__':
    main()
