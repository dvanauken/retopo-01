"""Read-only GLB import; write an evaluated source mesh as JSON."""
import bpy,sys,json
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:]
source,destination=map(Path,args)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
vertices=[];faces=[]
for obj in bpy.context.scene.objects:
 if obj.type!='MESH':continue
 evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh();mesh.calc_loop_triangles();offset=len(vertices)
 vertices.extend([list(obj.matrix_world@v.co) for v in mesh.vertices])
 faces.extend([[offset+i for i in t.vertices] for t in mesh.loop_triangles])
 evaluated.to_mesh_clear()
destination.write_text(json.dumps({'vertices':vertices,'faces':faces}),encoding='utf-8')
print('EXTRACTED',len(vertices),len(faces))
