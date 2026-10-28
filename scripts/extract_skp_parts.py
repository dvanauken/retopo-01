"""Run with Blender --background --python this_file -- source.skp output.json."""
import bpy
import hashlib
import json
import sys
from pathlib import Path

source, output = map(Path, sys.argv[sys.argv.index('--') + 1:])
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.preferences.addon_enable(module='sketchup_importer')
bpy.ops.import_scene.skp(filepath=str(source))
parts = []
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH' or not len(obj.data.polygons) or not obj.visible_get():
        continue
    obj.data.calc_loop_triangles()
    matrix = obj.matrix_world
    faces = [list(t.vertices) for t in obj.data.loop_triangles]
    if matrix.to_3x3().determinant() < 0:
        faces = [list(reversed(f)) for f in faces]
    parts.append(dict(name=obj.name, parent=obj.parent.name if obj.parent else None,
                      vertices=[list(matrix @ v.co) for v in obj.data.vertices], faces=faces))
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(dict(source=str(source), sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(), parts=parts)), encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(output.with_suffix('.blend')))
print('SKP_PARTS ' + json.dumps([dict(name=p['name'], vertices=len(p['vertices']), triangles=len(p['faces'])) for p in parts]))
