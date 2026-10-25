"""Fit both quad diagonals with source vertex and triangle-centroid support.

This isolated experiment replaces one-midpoint-per-edge alignment with 401
arc-spaced point-to-segment and tangent residuals. The unchanged acceptance
metric independently uses 257 samples. No production geometry is published.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
import argparse,hashlib,inspect,json,sys,time,traceback
from pathlib import Path
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj
parser=argparse.ArgumentParser()
parser.add_argument('--layout',type=Path,required=True)
parser.add_argument('--label',required=True)
parser.add_argument('--weight',type=float,default=12.)
parser.add_argument('--cases',nargs='+',default=['bowl-only-1800','two-guides-short-1800','two-guides-long-1800'])
args=parser.parse_args()
if not args.label.replace('-','').isalnum(): raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-both-diagonal-support'/args.label;OUT.mkdir(parents=True,exist_ok=True)
raw=json.loads(args.layout.read_text()); seed=raw['seed']
(OUT/'layout.json').write_bytes(args.layout.read_bytes())
source,triangles=read_obj(ROOT/'assets/models/toilet.obj'); source=np.asarray(source);triangles=np.asarray(triangles)
mesh=trimesh.Trimesh(source,triangles,process=False);spacing=np.sqrt(mesh.area/1800)
faces=np.asarray(raw['faces']); edges=cq._edges(faces)
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('curved_quad.py','surface_distance.py','surface_intersections.py','quad_quality.py','assets/models/toilet.obj','tests/probe_toilet_sampled_paths.py','tests/probe_toilet_both_diagonal_support.py')}
results,errors=[],[]

def pin_residual(points):
    nearest=[]
    for curve,begin,end in pin_groups:
        _,parameters=cq._nearest_curve(points[begin:end],curve)
        arc=cq._arc(curve)
        projected=np.array([np.interp(parameters,arc,curve[:,i]) for i in range(3)]).T
        if np.linalg.norm(curve[0]-curve[-1])>=1e-8:
            projected[0],projected[-1]=curve[0],curve[-1]
        nearest.extend(projected)
    return ((points-np.asarray(nearest))*80+(points-targets)*4).ravel()/spacing

def sampled_path_residual(points):
    a=points[sample_edges[:,0]];delta=points[sample_edges[:,1]]-a
    denominator=np.maximum(1e-18,(delta*delta).sum(axis=1))
    t=np.clip(((sample_points-a)*delta).sum(axis=1)/denominator,0,1)
    near=a+t[:,None]*delta
    unit=delta/np.sqrt(denominator)[:,None]
    return np.r_[((near-sample_points)/spacing*32*sample_weights[:,None]).ravel(),
                 (np.cross(unit,sample_tangents)*args.weight*sample_weights[:,None]).ravel()]

source_code=inspect.getsource(cq._refine)
# Source triangle-centroid witnesses and the alternate quad diagonal failed the
# previous experiment. Fit both triangulations separately, not their union.
support_begin = source_code.index('    out_tri = ')
support_end = source_code.index('    active.update(support.ravel())', support_begin)
support_code = """    source_samples = np.r_[source_mesh.vertices, source_mesh.triangles_center]
    supports, barycentrics, support_targets = [], [], []
    for first, second in (([0, 1, 2], [0, 2, 3]), ([0, 1, 3], [1, 2, 3])):
        out_tri = np.r_[faces[:, first], faces[:, second]]
        out_surface = trimesh.Trimesh(positions, out_tri, process=False)
        near, error, owners = trimesh.proximity.closest_point(out_surface, source_samples)
        selected = error > spacing * .25
        owned = out_tri[owners[selected]]
        supports.append(owned)
        barycentrics.append(trimesh.triangles.points_to_barycentric(positions[owned], near[selected]))
        support_targets.append(source_samples[selected])
    support = np.concatenate(supports)
    barycentric = np.concatenate(barycentrics)
    support_target = np.concatenate(support_targets)
"""
source_code = source_code[:support_begin] + support_code + source_code[support_end:]
old='(q[pins] - targets).ravel() / spacing * 80'
assert source_code.count(old)==1
source_code=source_code.replace(old,'pin_residual(q[pins])')
owner_anchor='    sparsity = lil_matrix('
assert source_code.count(owner_anchor)==1
source_code=source_code.replace(owner_anchor,'    groups += [(len(sample_edges)*3,sample_edges)]*2\n'+owner_anchor)
residual_anchor='np.maximum(np.linalg.norm(surface_delta, axis=1) / spacing - .35, 0) * 40]'
assert source_code.count(residual_anchor)==1
source_code=source_code.replace(residual_anchor,residual_anchor[:-1]+', sampled_path_residual(q)]')
(OUT/'executed-refine.py').write_text(inspect.getsource(pin_residual)+'\n'+inspect.getsource(sampled_path_residual)+'\n'+source_code)
namespace=dict(vars(cq),pin_residual=pin_residual,sampled_path_residual=sampled_path_residual);exec(source_code,namespace)

def save(complete):
    (OUT/'result.json').write_text(json.dumps(dict(complete=complete,cases=results,errors=errors,seed=seed,optimizationSamples=401,validationSamples=257,distanceWeight=32,tangentWeight=args.weight,
        sourceHashes=hashes,layoutSha256=hashlib.sha256(args.layout.read_bytes()).hexdigest(),layoutSource=str(args.layout),
        executedRefinementSha256=hashlib.sha256((OUT/'executed-refine.py').read_bytes()).hexdigest(),
        implementationUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),
        scope='Isolated fitting experiment on a retained genuine layout. Pin residual is distance to authored polyline (80) plus original target anchor (4), with open endpoints fixed. All original acceptance gates including full surface bounds and mixed quad diagonals remain unchanged. Distributed 401-sample guide-to-edge distance (32) and cross-tangent ('+str(args.weight)+') residuals replace the midpoint term. Each sample owns its closest connected path edge, updated between passes. Per-guide residual mass is normalized by square root of edge-count/sample-count. Validation still uses the original 257 samples. Source support samples are all source vertices and triangle centroids, fitted separately against both output quad diagonals. The support threshold and every residual weight remain unchanged. No production publication.'),indent=2)+'\n')

try:
    for name in args.cases:
        curve_file=ROOT/'tests/toilet-stress'/name/'curves.json'
        curves=[np.asarray(c) for c in json.loads(curve_file.read_text())['curves']]
        positions=np.asarray(raw['vertices']);paths=[];pin_rows=[];target_rows=[];pin_groups=[]
        for curve in curves:
            path,pins,targets=cq._guide_path(positions,edges,curve,spacing)
            pin_groups.append((curve,len(pin_rows),len(pin_rows)+len(pins)))
            paths.append(path);pin_rows.extend(pins);target_rows.extend(targets)
        pins=np.asarray(pin_rows,dtype=int); targets=np.asarray(target_rows).reshape(-1,3)
        for pin in set(pin_rows):
            shared=targets[pins==pin]
            assert np.max(np.linalg.norm(shared-shared[0],axis=1))<=spacing*.1, 'Competing pins'
        record=dict(name=name,curvesSha256=hashlib.sha256(curve_file.read_bytes()).hexdigest(),attempts=[],qualified=False)
        results.append(record)
        for iteration in range(5):
            sample_edges=[];sample_points=[];sample_tangents=[];sample_weights=[]
            for path,curve in zip(paths,curves):
                pe=np.array(list(zip(path['vertices'][:-1],path['vertices'][1:])),dtype=int)
                points=cq._sample(curve,401)
                tangent=np.roll(points,-1,axis=0)-np.roll(points,1,axis=0)
                tangent[0]=points[1]-points[0];tangent[-1]=points[-1]-points[-2]
                if path['closed']:tangent[0]=tangent[-1]=points[1]-points[-2]
                tangent/=np.maximum(1e-12,np.linalg.norm(tangent,axis=1))[:,None]
                a=positions[pe[:,0]];delta=positions[pe[:,1]]-a
                t=np.clip(((points[:,None,:]-a)*delta).sum(axis=2)/np.maximum(1e-18,(delta*delta).sum(axis=1)),0,1)
                error=points[:,None,:]-a-t[:,:,None]*delta
                selected=(error*error).sum(axis=2).argmin(axis=1)
                sample_edges.extend(pe[selected]);sample_points.extend(points);sample_tangents.extend(tangent)
                sample_weights.extend([np.sqrt(len(pe)/len(points))]*len(points))
            sample_edges=np.asarray(sample_edges,dtype=int);sample_points=np.asarray(sample_points)
            sample_tangents=np.asarray(sample_tangents);sample_weights=np.asarray(sample_weights)
            namespace['sample_edges']=sample_edges
            start=time.monotonic(); positions,refinement=namespace['_refine'](mesh,positions,faces,edges,pins,targets,1800)
            quality=cq.quad_quality(positions,faces,1800);fit=cq._guide_fit(positions,paths,curves)
            contacts=cq.surface_intersections(positions,faces,both_quad_diagonals=True)
            guided=all(p['p95Distance']<=.2*spacing and p['p95TangentAngleDegrees']<=30 for p in fit)
            eligible=quality['passed'] and contacts['passed'] and guided
            surface=cq.validate_surface(source,triangles,positions,faces,1800,whole_surface=eligible)
            qualified=bool(eligible and surface['passed']);record['qualified']=qualified
            record['attempts'].append(dict(iteration=iteration,refinement=refinement,quality=quality,guideFit=fit,contacts=contacts,surface=surface,qualified=qualified,elapsedSeconds=time.monotonic()-start))
            (OUT/f'{name}-{iteration}.json').write_text(json.dumps(dict(vertices=positions.tolist(),faces=faces.tolist())))
            save(False)
            print(name,iteration,'quality',quality['passed'],'contacts',contacts['passed'],'guide',guided,'surface',surface['passed'],'qualified',qualified,'seconds',round(time.monotonic()-start,1),flush=True)
            if qualified: break
except Exception:
    errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:save(True)

raise SystemExit(1 if errors else 0)
