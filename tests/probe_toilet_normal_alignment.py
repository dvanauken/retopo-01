"""Detached source-normal fitting experiment; no production or gate edits."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
import surface_guide_repair as repair
from retopo import read_obj,write_obj

parser=argparse.ArgumentParser()
parser.add_argument('--label',required=True)
parser.add_argument('--input',type=Path,required=True)
parser.add_argument('--weights',type=float,nargs='+',default=[8.,32.])
args=parser.parse_args()
if not args.label.replace('-','').isalnum() or any(not 0<w<=100 for w in args.weights):
    raise ValueError('Invalid label or weight')
input_path=args.input.resolve();input_path.relative_to(ROOT)
OUT=ROOT/'tests/toilet-normal-alignment'/args.label
OUT.mkdir(parents=True,exist_ok=False)
(OUT/'executed-probe.py').write_bytes(Path(__file__).read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=['curved_quad.py','surface_guide_refine.py','surface_guide_repair.py','surface_distance.py','surface_intersections.py','quad_quality.py','assets/models/toilet.obj','tests/probe_toilet_normal_alignment.py']
hashes={name:sha(ROOT/name) for name in files}
sv,sf=read_obj(ROOT/'assets/models/toilet.obj');source=trimesh.Trimesh(sv,sf,process=False)
packet=json.loads(input_path.read_text());initial=np.asarray(packet['vertices']);faces=np.asarray(packet['faces'])
edges=cq._edges(faces);cases=[];errors=[];started=time.monotonic()
definition=(ROOT/'surface_guide_refine.py').read_text()
helper='''
def source_alignment(points, polygons, expected):
    normals = np.cross(points[polygons[:, 2]] - points[polygons[:, 0]], points[polygons[:, 3]] - points[polygons[:, 1]])
    normals /= np.maximum(np.linalg.norm(normals, axis=1), 1e-12)[:, None]
    return np.einsum('ij,ij->i', normals, expected)

'''
definition=definition.replace('def refine(',helper+'def refine(',1)
marker='    vertex_anchor, vertex_error, vertex_triangles = trimesh.proximity.closest_point(source_mesh, positions)'
assert definition.count(marker)==1
definition=definition.replace(marker,marker+'''
    face_owners = trimesh.proximity.closest_point(source_mesh, positions[faces].mean(axis=1))[2]
    expected_normals = source_mesh.face_normals[face_owners]
    bad |= source_alignment(positions, faces, expected_normals) < .5
''')
marker='    local_faces = faces[np.any(np.isin(faces, ids), axis=1)]'
assert definition.count(marker)==1
definition=definition.replace(marker,marker+'''
    local_expected_normals = expected_normals[np.any(np.isin(faces, ids), axis=1)]
''')
marker='    groups += [(len(memory_tri) * 3, memory_tri), (len(memory_tri), memory_tri)]'
assert definition.count(marker)==1
definition=definition.replace(marker,marker+'\n    groups += [(len(local_faces), local_faces)]')
marker='                     sampled_path_residual(q), memory_residual(q)]'
assert definition.count(marker)==1
definition=definition.replace(marker,'''                     sampled_path_residual(q), memory_residual(q),
                     np.maximum(.5 - source_alignment(q, local_faces, local_expected_normals), 0) * NORMAL_WEIGHT]''')
if 'np.maximum(ratio - 3.5, 0) * 10' in definition:
    definition=definition.replace('np.maximum(ratio - 3.5, 0) * 10','np.maximum(ratio - 3.4, 0) * 10')
else:
    assert definition.count('edge_ratio_aim=3.5')==1
    definition=definition.replace('edge_ratio_aim=3.5','edge_ratio_aim=3.4')

def save(complete):
    (OUT/'result.json').write_text(json.dumps(dict(complete=complete,productionResult=False,cases=cases,errors=errors,
        inputFile=str(input_path.relative_to(ROOT)),inputSha256=sha(input_path),sourceHashes=hashes,
        implementationUnchanged=all(sha(ROOT/name)==digest for name,digest in hashes.items()),elapsedSeconds=time.monotonic()-started,
        scope='Detached fitting adds a hinge penalty for face normals opposing the nearest source centroid normal; those faces become active. Shape objective aims3.4 while acceptance stays3.5. Nearest-source normals update each fitting pass; no correspondence or qualification is assumed. All ordinary gates remain mandatory.'),indent=2)+'\n')

try:
    for weight in args.weights:
        name='weight-'+str(weight).replace('.','-');folder=OUT/name;folder.mkdir()
        path=folder/'executed-fitter.py';path.write_text(definition.replace('NORMAL_WEIGHT',repr(weight)))
        spec=importlib.util.spec_from_file_location(name,path);fitter=importlib.util.module_from_spec(spec);sys.modules[spec.name]=fitter;spec.loader.exec_module(fitter)
        repair.fitter=fitter;p=initial.copy();guides=fitter.prepare(p,edges,[],np.sqrt(source.area/150))
        case=dict(name=name,target=150,job=None,state='running',producerKind='isolated-source-normal-fit',weight=weight,
                  fitterSha256=sha(path),attempts=[]);cases.append(case)
        (folder/'curves.json').write_text(json.dumps(dict(coordinateFrame='source',curves=[])))
        (folder/'settings.json').write_text(json.dumps(dict(meshId='toilet',target=150)))
        begin=time.monotonic()
        def record(assessment,**details):
            contacts=cq.surface_intersections(p,faces,both_quad_diagonals=True)
            count=len(contacts['nonAdjacentIntersectingFacePairs'])+len(contacts['adjacentIntersectingFacePairs'])
            case['attempts'].append(dict(assessment,measuredContactPairs=count,**details))
            print(name,details.get('iteration',details.get('phase')),'shape',assessment['quality']['passed'],'contacts',count,'qualified',assessment['qualified'],flush=True)
            save(False)
        for iteration in range(8):
            p,refinement=fitter.refine(source,p,faces,edges,guides,150)
            current=repair._assess(source,p,faces,guides,150)
            (folder/f'candidate-{iteration}.json').write_text(json.dumps(dict(vertices=p.tolist(),faces=faces.tolist())))
            record(current,iteration=iteration,refinement=refinement)
            if current['qualified']:break
        # Any full repair is evaluated by the same complete acceptance gate.
        if current['eligibleForRepair'] and not current['qualified']:
            p,current=repair._repair(source,p,faces,edges,guides,150,current,lambda assessment,**kw:case['attempts'].append(dict(assessment,**kw)),folder,edge_ratio_aim=3.4)
        case.update(state='complete' if current['qualified'] else 'failed',elapsedSeconds=time.monotonic()-begin)
        (folder/'final-candidate.json').write_text(json.dumps(dict(vertices=p.tolist(),faces=faces.tolist())))
        if current['qualified']:
            write_obj(folder/'output.obj',p,faces.tolist());case.update(faces=len(faces),outputSha256=sha(folder/'output.obj'))
            (folder/'mesh.json').write_text(json.dumps(dict(vertices=p.tolist(),faces=faces.tolist(),guidePaths=current['guideFit'])))
            (folder/'report.json').write_text(json.dumps(dict(producerKind=case['producerKind'],outputSha256=case['outputSha256'],sourceSha256=hashes['assets/models/toilet.obj'],assessment=current)))
        save(False)
except Exception:
    errors.append(traceback.format_exc());print(errors[-1],flush=True)
    if cases and cases[-1]['state']=='running':cases[-1]['state']='probe-error'
finally:save(True)
raise SystemExit(1 if errors else 0)
