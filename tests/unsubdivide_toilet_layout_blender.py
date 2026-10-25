"""Isolated Blender topology probe; never changes the original toilet asset.

Operator reference: https://docs.blender.org/api/5.1/bpy.ops.mesh.html#bpy.ops.mesh.unsubdivide
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import bpy

parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
args.output.mkdir(parents=True, exist_ok=False)
packet = json.loads(args.input.read_text())
cases = []
for iterations in (1, 2, 3):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    mesh = bpy.data.meshes.new('Qualified intermediate layout')
    mesh.from_pydata(packet['vertices'], [], packet['faces'])
    mesh.update()
    obj = bpy.data.objects.new('Unsubdivision experiment', mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    status = bpy.ops.mesh.unsubdivide(iterations=iterations)
    bpy.ops.object.mode_set(mode='OBJECT')
    vertices = [list(v.co) for v in obj.data.vertices]
    faces = [list(p.vertices) for p in obj.data.polygons]
    path = args.output / f'iterations-{iterations}.json'
    path.write_text(json.dumps(dict(vertices=vertices, faces=faces, blenderVersion=bpy.app.version_string)))
    cases.append(dict(iterations=iterations, operatorResult=list(status), vertices=len(vertices), faces=len(faces),
                      faceSizes=dict(Counter(map(len, faces))), outputFile=path.name,
                      outputSha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    print(json.dumps(cases[-1]), flush=True)
report = dict(complete=True, productionResult=False, cases=cases,
              inputFile=str(args.input), inputSha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
              blenderVersion=bpy.app.version_string,
              scope='Blender unsubdivision of a retained qualified intermediate quad layout. No original-source mutation and no final mesh qualification; counts/topology/shape/surface/contacts require further evaluation.')
(args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
