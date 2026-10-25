"""Locate guide-fit failures on retained candidates without changing any gates."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import hashlib,json,sys
from xml.sax.saxutils import escape
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj,guide_alignment
OUT=ROOT/'tests/toilet-path-fit-diagnostics';OUT.mkdir(exist_ok=True)
folder=ROOT/'tests/toilet-tangent-pins/captured-seed-2-weight-12'
report=json.loads((folder/'result.json').read_text());raw=json.loads((folder/'layout.json').read_text())
sv,sf=read_obj(ROOT/'assets/models/toilet.obj');surface=trimesh.Trimesh(sv,sf,process=False)
spacing=np.sqrt(surface.area/1800);edges=cq._edges(np.asarray(raw['faces']))
records=[]

def closest(points,vertices,edge_ids):
    a=vertices[edge_ids[:,0]];d=vertices[edge_ids[:,1]]-a
    t=np.clip(((points[:,None,:]-a)*d).sum(axis=2)/(d*d).sum(axis=1),0,1)
    projected=a+t[:,:,None]*d
    distances=np.linalg.norm(points[:,None,:]-projected,axis=2)
    selected=distances.argmin(axis=1);rows=np.arange(len(points))
    return distances[rows,selected],projected[rows,selected],selected,d

def svg(case,curves,paths,bad):
    all_points=np.concatenate(curves+paths);parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="540" viewBox="0 0 1440 540">',
        '<rect width="1440" height="540" fill="white"/>',
        '<g font-family="Arial" font-size="15" fill="#25334a">',
        f'<text x="24" y="24">{escape(case)} — retained experiment, not a production result</text>',
        '<text x="24" y="48">Blue/gold: authored guides · gray: fitted output paths · red: sampled tangent error above 30°</text>']
    for view,(i,j) in enumerate(((0,1),(0,2),(1,2))):
        lo=all_points[:,[i,j]].min(axis=0);hi=all_points[:,[i,j]].max(axis=0)
        scale=min(410/np.maximum(hi[0]-lo[0],1e-6),410/np.maximum(hi[1]-lo[1],1e-6))
        center=(lo+hi)/2
        def xy(p):return (view*480+240+(p[i]-center[0])*scale,300-(p[j]-center[1])*scale)
        parts.append(f'<text x="{view*480+24}" y="80">{"XYZ"[i]} / {"XYZ"[j]}</text>')
        for points,color,width in [(p,'#7b8797',1.5) for p in paths]+[(c,('#2467ce','#b1841c')[k%2],2) for k,c in enumerate(curves)]:
            coordinates=' '.join(f'{x:.3f},{y:.3f}' for x,y in map(xy,points))
            parts.append(f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="{width}"/>')
        for points in bad:
            for point in points:
                x,y=xy(point);parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="2.3" fill="#d33d36"/>')
    parts.append('</g></svg>');(OUT/(case+'.svg')).write_text('\n'.join(parts),encoding='utf-8')

for case in report['cases']:
    name=case['name'];iteration=case['attempts'][-1]['iteration'];candidate=folder/f'{name}-{iteration}.json'
    packet=json.loads(candidate.read_text());vertices=np.asarray(packet['vertices'])
    curves=[np.asarray(c) for c in json.loads((ROOT/'tests/toilet-stress'/name/'curves.json').read_text())['curves']]
    row=dict(name=name,candidate=str(candidate.relative_to(ROOT)),candidateSha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),curves=[])
    paths_for_plot=[];bad_for_plot=[]
    for curve in curves:
        path,_,_=cq._guide_path(np.asarray(raw['vertices']),edges,curve,spacing)
        path_ids=np.asarray(path['vertices']);pe=np.column_stack([path_ids[:-1],path_ids[1:]])
        sampled=cq._sample(curve);distance,projected,selected,deltas=closest(sampled,vertices,pe)
        tangent=np.roll(sampled,-1,axis=0)-np.roll(sampled,1,axis=0)
        tangent[0]=sampled[1]-sampled[0];tangent[-1]=sampled[-1]-sampled[-2]
        if path['closed']:tangent[0]=tangent[-1]=sampled[1]-sampled[-2]
        angle=np.degrees(np.arccos(np.clip(np.abs(np.einsum('ij,ij->i',tangent,deltas[selected]))/(np.linalg.norm(tangent,axis=1)*np.linalg.norm(deltas[selected],axis=1)),0,1)))
        reference=guide_alignment(vertices,pe,sampled)
        assert abs(float(np.percentile(angle,95))-reference['p95UnsignedTangentAngleDegrees'])<1e-8
        assert abs(float(np.percentile(distance,95))-reference['p95Distance'])<1e-10
        _,guide_surface_error,guide_tri=trimesh.proximity.closest_point(surface,sampled)
        _,output_surface_error,output_tri=trimesh.proximity.closest_point(surface,projected)
        normal_angle=np.degrees(np.arccos(np.clip((surface.face_normals[guide_tri]*surface.face_normals[output_tri]).sum(axis=1),-1,1)))
        _,mid_parameter=cq._nearest_curve(vertices[pe].mean(axis=1),curve)
        arc=cq._arc(curve);segment=np.clip(np.searchsorted(arc,mid_parameter,side='right')-1,0,len(curve)-2)
        desired=np.diff(curve,axis=0)[segment]
        midpoint_angle=np.degrees(np.arccos(np.clip(np.abs((deltas*desired).sum(axis=1))/(np.linalg.norm(deltas,axis=1)*np.linalg.norm(desired,axis=1)),0,1)))
        bad=np.flatnonzero(angle>30)
        vertices_on_path=vertices[path_ids[:-1] if path['closed'] else path_ids]
        authored=curve[:-1] if path['closed'] else curve
        incoming=authored-np.roll(authored,1,axis=0);outgoing=np.roll(authored,-1,axis=0)-authored
        bends=np.degrees(np.arccos(np.clip((incoming*outgoing).sum(axis=1)/(np.linalg.norm(incoming,axis=1)*np.linalg.norm(outgoing,axis=1)),-1,1)))
        if not path['closed']:bends[0]=bends[-1]=0
        corners=np.flatnonzero(bends>30)
        corner_distance=np.linalg.norm(authored[corners,None,:]-vertices_on_path,axis=2).min(axis=1)
        detail=dict(closed=path['closed'],pathVertices=len(vertices_on_path),reference=reference,
            badSamples=len(bad),badSamplesWithSourceNormalDifferenceOver60=int(np.count_nonzero(normal_angle[bad]>60)),
            allSampleNormalAngleP95=float(np.percentile(normal_angle,95)),midpointTangentAngleP95=float(np.percentile(midpoint_angle,95)),
            significantCorners=[dict(authoredIndex=int(i),angle=float(bends[i]),position=authored[i].tolist(),nearestPathVertexDistance=float(d)) for i,d in zip(corners,corner_distance)],
            samples=[dict(index=int(i),arcFraction=float(i/(len(sampled)-1)),point=sampled[i].tolist(),outputPoint=projected[i].tolist(),edge=pe[selected[i]].tolist(),distance=float(distance[i]),
                tangentAngle=float(angle[i]),sourceNormalAngle=float(normal_angle[i]),guideSurfaceDistance=float(guide_surface_error[i]),outputSurfaceDistance=float(output_surface_error[i])) for i in range(len(sampled))])
        row['curves'].append(detail);paths_for_plot.append(vertices[path_ids]);bad_for_plot.append(sampled[bad])
        print(name,'guide',len(row['curves']),'bad',len(bad),'normals>60',detail['badSamplesWithSourceNormalDifferenceOver60'],'angle p95',round(reference['p95UnsignedTangentAngleDegrees'],2),'midpoint p95',round(detail['midpointTangentAngleP95'],2),flush=True)
    svg(name,curves,paths_for_plot,bad_for_plot);records.append(row)
result=dict(cases=records,sourceHashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('curved_quad.py','assets/models/toilet.obj','tests/inspect_toilet_path_fit.py')},
    scope='Diagnostic locations on retained, explicitly experimental candidates. Per-sample distance/tangent calculations agree with the unmodified reference metric. Nearest-source normal comparisons are diagnostic, not proof of geodesic correspondence or a new acceptance gate.')
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
