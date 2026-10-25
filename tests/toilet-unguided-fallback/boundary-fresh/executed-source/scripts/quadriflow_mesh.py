"""Owned Blender subprocess: fresh source geometry to a fresh QuadriFlow layout."""
import argparse
import json
import sys
from pathlib import Path

import bpy

parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--target', type=int, required=True)
parser.add_argument('--seed', type=int, default=0)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
source = json.loads(args.input.read_text(encoding='utf-8'))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
mesh = bpy.data.meshes.new('Submitted source')
mesh.from_pydata(source['vertices'], [], source['faces'])
mesh.update()
obj = bpy.data.objects.new('Generated quad layout', mesh)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
result = bpy.ops.object.quadriflow_remesh(
    target_faces=args.target, seed=args.seed, use_mesh_symmetry=False,
    use_preserve_sharp=False, use_preserve_boundary=True,
)
if 'FINISHED' not in result or not obj.data.polygons or any(len(p.vertices) != 4 for p in obj.data.polygons):
    raise RuntimeError('QuadriFlow did not return a quadrilateral layout.')
args.output.write_text(json.dumps({
    'vertices': [list(v.co) for v in obj.data.vertices],
    'faces': [list(p.vertices) for p in obj.data.polygons],
    'blenderVersion': bpy.app.version_string, 'seed': args.seed,
}), encoding='utf-8')
