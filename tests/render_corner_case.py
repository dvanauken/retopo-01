"""Side-view pictures of a part's corner zone for several quad meshes, with the corner-zone numbers.

Usage: python tests/render_corner_case.py --source S.obj --target 200 --out picture.png
           --mesh "Strict=a.obj" --mesh "Extra faces=b.obj" --mesh "ZBrush=c.obj"
           [--zone-axis 1 --zone-above 0.05] [--crease-angle 30]

Each row is one mesh; the columns are the two corners of the zone (x < 0, x > 0), each seen from
the side and from behind and below, plus the source with its admitted creases in the first row.
Faces and the admitted source creases (magenta) are painted back to front, so a crease shows on a
surface that follows it and is hidden by one that covers it; an edge row on a crease shows as a
dark line under a magenta one. The JSON written beside the
picture holds corner_zones.measure_zone for the fixed zone and corner_zones.measure for the
automatic zones, in requested faces (h).
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
from matplotlib.patches import Polygon
import trimesh
from measure_geometry import read_obj
from source_features import detect, use_crease_angle
import corner_zones


def camera(azimuth, elevation):
    """Orthographic basis (right, up, toward the viewer) for a view direction in degrees."""
    a, e = np.radians(azimuth), np.radians(elevation)
    toward = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    right = np.cross([0., 0., 1.], toward)
    right /= np.linalg.norm(right)
    return right, np.cross(toward, right), toward


def panel(axis, title, points, faces, keep, creases, view, spacing, window=None, light=(.3, -.4, .85)):
    """One view: faces and source creases painted back to front, so a crease behind a face is hidden.

    A crease is drawn 0.15 of a face nearer the viewer than it lies, so it shows on a surface that
    follows it and disappears behind one that covers it from farther away.
    """
    points = np.asarray(points, float)
    right, up, toward = camera(*view)
    items = []
    for face in faces:
        corners = points[list(face)]
        if not keep(corners.mean(0)):
            continue
        normal = np.cross(corners[1] - corners[0], corners[2] - corners[0]) if len(face) == 3 else np.cross(corners[2] - corners[0], corners[3] - corners[1])
        length = np.linalg.norm(normal)
        shade = .5 + .5 * abs(float(normal @ np.asarray(light)) / length) if length > 0 else .5
        base = np.array([.98, .86, .62]) if len(face) == 3 else np.array([.84, .88, .93])
        items.append((float((corners @ toward).mean()), 0, np.c_[corners @ right, corners @ up], tuple(base * (.55 + .45 * shade))))
    if creases is not None:
        for pair in creases:
            if keep(pair.mean(0)):
                items.append((float((pair @ toward).mean()) + .15 * spacing, 1, np.c_[pair @ right, pair @ up], None))
    items.sort(key=lambda item: (item[0], item[1]))
    every = [item[2] for item in items if item[1] == 0]
    for rank, (_, kind, shape, colour) in enumerate(items):
        if kind == 0:
            axis.add_patch(Polygon(shape, closed=True, facecolor=colour, edgecolor='#20262e', linewidth=.7, zorder=rank))
        else:
            axis.plot(shape[:, 0], shape[:, 1], color='#e0189a', linewidth=1.3, zorder=rank, solid_capstyle='round')
    every = np.concatenate(every) if every else np.zeros((1, 2))
    if window is None:
        low, high = every.min(0), every.max(0)
        pad = .04 * (high - low).max()
        window = (low[0] - pad, high[0] + pad, low[1] - pad, high[1] + pad)
    axis.set_xlim(window[0], window[1])
    axis.set_ylim(window[2], window[3])
    axis.set_aspect('equal')
    axis.set_axis_off()
    axis.set_title(title, fontsize=9)
    return window


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--target', type=int, required=True)
    parser.add_argument('--mesh', action='append', required=True, help='Title=path.obj')
    parser.add_argument('--out', required=True)
    parser.add_argument('--zone-axis', type=int, default=1)
    parser.add_argument('--zone-above', type=float, default=.05)
    parser.add_argument('--crease-angle', type=float, default=30.)
    parser.add_argument('--elevation', type=float, default=18.)
    arguments = parser.parse_args()
    source, triangles = read_obj(arguments.source)
    source, triangles = np.asarray(source, float), np.asarray(triangles, int)
    spacing = float(np.sqrt(trimesh.Trimesh(source, triangles, process=False).area / arguments.target))
    use_crease_angle(arguments.crease_angle)
    edges, _ = detect(source, triangles, spacing, target=arguments.target)
    creases = source[edges]
    axis_id, above = arguments.zone_axis, arguments.zone_above
    margin = above - .9 * spacing   # show a little of the surface in front of the zone
    side = 1.6 * spacing   # the corners: the outer part of each half
    halves = (('x < 0 corner, side view', lambda c: c[axis_id] > margin and c[0] < -side, (190., arguments.elevation)),
              ('x > 0 corner, side view', lambda c: c[axis_id] > margin and c[0] > side, (-10., arguments.elevation)),
              ('x < 0 corner, from behind and below', lambda c: c[axis_id] > margin and c[0] < -side, (120., -30.)),
              ('x > 0 corner, from behind and below', lambda c: c[axis_id] > margin and c[0] > side, (60., -30.)))
    meshes = [('Source (admitted creases in magenta)', source, [list(map(int, t)) for t in triangles])]
    for entry in arguments.mesh:
        title, path = entry.split('=', 1)
        points, faces = read_obj(path)
        meshes.append((title, np.asarray(points, float), [list(map(int, f)) for f in faces]))
    figure, axes = plt.subplots(len(meshes), len(halves), figsize=(5.4 * len(halves), 4.3 * len(meshes)), dpi=130, squeeze=False)
    report, windows = {}, {}
    for row, (title, points, faces) in enumerate(meshes):
        note = ''
        if row:
            zone = corner_zones.measure_zone(source, points, faces, spacing, source[:, axis_id] > above)
            centres = np.array([points[f].mean(0) for f in faces])
            zone['facesInZone'] = int((centres[:, axis_id] > above).sum())
            auto = corner_zones.measure(source, triangles, edges, points, faces, spacing)
            report[title] = dict(file=str(arguments.mesh[row - 1].split('=', 1)[1]), faces=len(faces), quads=sum(len(f) == 4 for f in faces),
                                 triangles=sum(len(f) == 3 for f in faces), fixedZone=zone, automaticZones=auto)
            note = f"\n{len(faces)} faces, {zone['facesInZone']} in zone; source-to-output P95 {zone['p95InFaces']:.3f} h, max {zone['maxInFaces']:.3f} h"
        for column, (name, keep, view) in enumerate(halves):
            windows[column] = panel(axes[row][column], f'{title}: {name}{note if column == 0 else ""}', points, faces, keep, creases, view, spacing, windows.get(column))
    figure.tight_layout()
    figure.savefig(arguments.out)
    Path(arguments.out).with_suffix('.json').write_text(json.dumps(dict(
        spacing=spacing, target=arguments.target, zone=f'source coordinate {axis_id} > {above:g}', meshes=report), indent=1))
    for title, item in report.items():
        print(title, json.dumps(dict(faces=item['faces'], fixedZone=item['fixedZone'], automaticZones=[{k: z[k] for k in ('sourceVertices', 'p95InFaces', 'maxInFaces')} for z in item['automaticZones']['zones']])))
    print(arguments.out)


if __name__ == '__main__':
    main()
