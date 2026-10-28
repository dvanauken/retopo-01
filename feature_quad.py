"""Feature and guide field layout with bounded fitting and independent gates.

The original source and every authored guide remain inputs to independent gates.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import shutil
import time
import numpy as np
import trimesh
import curved_quad as cq
from features import output_creases
from measure_geometry import read_obj
from guided_layout import runtime, obj
from quad_connectivity import dissolve_double_edges, split_vertex_stars
from source_features import detect, measure as measure_features
from feature_refine import refine
from feature_repair import witnesses as surface_witnesses,refine_features,refine_guides,guide_region,repair_contacts,contact_neighborhood,refine_failures,failure_region,local_surface_samples


def write(path, value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def construct(source, triangles, curves, *, target, job):
    if isinstance(target,bool) or not isinstance(target,(int,np.integer)) or not 150<=target<=12000:
        raise ValueError('Feature layout target must be an integer from 150 to 12,000.')
    target=int(target)
    job=Path(job);out=job/'feature-layout';out.mkdir()
    files=[Path(__file__),Path(refine.__code__.co_filename),Path(cq.__file__),Path(measure_features.__code__.co_filename),Path(dissolve_double_edges.__code__.co_filename),Path(__file__).with_name('contact_constraints.py'),Path(__file__).with_name('source_projection.py')]
    files.extend(Path(__file__).with_name(name) for name in ('surface_intersections.py','surface_contacts_fast.py','surface_distance.py','mesh_proximity.py','quad_quality.py','feature_repair.py','surface_patch.py','guide_embedding.py','guide_ordered_targets.py'))
    dependencies=out/'dependencies';dependencies.mkdir()
    source_hashes={str(file):hashlib.sha256(file.read_bytes()).hexdigest() for file in files}
    for file in files:shutil.copy2(file,dependencies/file.name)
    source=np.asarray(source,float);triangles=np.asarray(triangles,int);curves=[np.asarray(c,float) for c in curves]
    for curve in curves:
        if curve.ndim!=2 or curve.shape[1]!=3 or len(curve)<2 or not np.isfinite(curve).all() or np.any(np.linalg.norm(np.diff(curve,axis=0),axis=1)==0):
            raise ValueError('Guides need distinct consecutive finite surface samples.')
    mesh=trimesh.Trimesh(source,triangles,process=False);h=float(np.sqrt(mesh.area/target));start=time.monotonic()
    if not mesh.is_watertight or not mesh.is_winding_consistent or np.any(mesh.area_faces==0):
        raise ValueError('Feature layout requires a closed, consistently wound, nondegenerate source.')
    executable,env,engine=runtime();env['OMP_NUM_THREADS']='4'
    feature_edges,detection=detect(source,triangles,h);segments=[]
    for ci,curve in enumerate(curves):
        a,b=curve[:-1],curve[1:];owners=trimesh.proximity.closest_point(mesh,(a+b)*.5)[2]
        segments.extend([[ci,*x,*y,*n] for x,y,n in zip(a,b,mesh.face_normals[owners])])
    for i,(a,b) in enumerate(feature_edges,len(curves)):
        n=mesh.vertex_normals[[a,b]].mean(0);length=np.linalg.norm(n)
        if length>1e-12:segments.append([i,*source[a],*source[b],*(n/length)])
    with (out/'segments.txt').open('w') as stream:
        stream.write(str(len(segments))+'\n')
        for row in segments:stream.write(' '.join(format(float(x),'.17g') for x in row)+'\n')
    obj(out/'source.obj',source,triangles)
    command=[str(executable),'-i',str(out/'source.obj'),'-o',str(out/'layout.obj'),'-f',str(target),'-seed','2','-sharp']
    if segments:command+=['-guides',str(out/'segments.txt'),'-guide-width','.75','-orientation-weight','1','-position-weight','0']
    write(out/'settings.json',dict(target=target,guideCount=len(curves),features=detection,command=command,engine=engine))
    cq._progress(job,'Building source-feature and guide orientation fields')
    tic=time.monotonic()
    with (out/'layout.log').open('w') as log:
        process=subprocess.run(command,env=env,stdout=log,stderr=log,timeout=150,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if process.returncode:raise ValueError('Feature layout failed; its calculation log was retained.')
    layout_seconds=time.monotonic()-tic
    p,q=read_obj(out/'layout.obj');q=np.asarray(q,int)
    if q.ndim!=2 or q.shape[1]!=4:raise ValueError('Feature layout did not return only quads.')
    p,q,dissolved=dissolve_double_edges(p,q)
    if len(feature_edges):
        samples=np.r_[source[np.unique(feature_edges)],source[feature_edges].mean(1)]
        tri=np.r_[q[:,[0,1,2]],q[:,[0,2,3]]];raw=trimesh.Trimesh(p,tri,process=False)
        _,distance,owner=trimesh.proximity.closest_point(raw,samples);selected=[]
        for i in np.argsort(-distance):
            if distance[i]<=h*.20:break
            face=q[owner[i]%len(q)];vertex=int(face[np.argmin(np.linalg.norm(p[face]-samples[i],axis=1))])
            if vertex not in selected:selected.append(vertex)
        p,q,subdivision=split_vertex_stars(p,q,selected,int(target*1.14))
    else:subdivision=dict(addedFaces=0,refinedVertexStars=0)
    write(out/'connectivity.json',dict(dissolved=dissolved,subdivision=subdivision))
    edges=cq._edges(q);paths=[cq._guide_path(p,edges,c,h)[0] for c in curves]
    history=[];contact_pairs=set();witnesses=[];witness_keys=set()
    for iteration in range(10):
        if time.monotonic()-start>900:break
        cq._progress(job,f'Fitting source features and guide paths · pass {iteration+1}')
        p,detail=refine(mesh,p,q,curves,target,paths,contacts=sorted(contact_pairs),witnesses=witnesses,witness_policy='oriented')
        obj(out/f'candidate-{iteration}.obj',p,q)
        fit=cq._guide_fit(p,paths,curves,h);quality=cq.quad_quality(p,q,target)
        row=dict(iteration=iteration,refinement=detail,quality=quality,guideFit=fit,passed=False);history.append(row)
        if iteration>=1 and quality['passed']:
            cq._progress(job,'Checking source features, surface distance and face contacts')
            tic=time.monotonic();feature=measure_features(source,triangles,p,q,target)
            contact=cq.surface_intersections(p,q,both_quad_diagonals=True)
            surface=cq.validate_surface(source,triangles,p,q,target,accelerated=True)
            row.update(features=feature,contacts=contact,surface=surface,verificationSeconds=time.monotonic()-tic)
            contact_pairs.update(tuple(pair) for key in ('nonAdjacentIntersectingFacePairs','adjacentIntersectingFacePairs') for pair in contact[key])
            for bound in surface['wholeSurfaceDiagonals'].values():
                for item in (bound['sourceToOutput'],bound['outputToSource']):
                    if not item['passed'] and item.get('witness') is not None:
                        point=item['witness'];key=tuple(np.round(point,8))
                        if key not in witness_keys:witnesses.append(point);witness_keys.add(key)
            row['passed']=bool(feature['passed'] and contact['passed'] and surface['passed'] and cq.guides_pass(fit,h))
            if row['passed']:
                metadata=dict(backend=cq.BACKEND,target=target,guideMode=2,closedValidation=surface,guidePaths=fit,
                              intersectionValidation=contact,featureValidation=feature,outputCreases=output_creases(p,q.tolist()),
                              refinementHistory=history,layoutEngine=dict(name='Feature and guide orientation QuadriFlow',**engine),
                              timings=dict(layout=layout_seconds,refinement=sum(r['refinement']['seconds'] for r in history),verification=sum(r.get('verificationSeconds',0) for r in history)),
                              sourceHashes=source_hashes,
                              limitations=['Feature components smaller than one requested edge spacing are reported as angular fragments; source surface bounds still apply.','Guide and feature fields plus discrete connectivity refinement; no native parity claim.','Double-precision bounded surface and contact checks.'])
                write(out/'history.json',history);write(job/'surface-solver.json',metadata)
                return p,q.tolist(),metadata
        write(out/'history.json',history)
        if iteration>1 and not quality['passed'] and detail['evaluations']<40:break
    # A feature fit must not be allowed to trade creases for guide accuracy or
    # remove contacts by rounding the source. Local repairs have their own
    # records and every returned result passes all independent gates together.
    candidates=[row for row in history if row['quality']['passed'] and 'contacts' in row]
    if candidates:
        chosen=min(candidates,key=lambda row:(len(row['contacts']['nonAdjacentIntersectingFacePairs'])+len(row['contacts']['adjacentIntersectingFacePairs']),not row.get('surface',{}).get('passed'),-row['iteration']))
        p,q=read_obj(out/f"candidate-{chosen['iteration']}.obj");q=np.asarray(q,int)
        fit=chosen['guideFit'];latest=chosen;witnesses=surface_witnesses(chosen)

        def check(label,detail,*,full=True):
            nonlocal latest
            obj(out/f'{label}.obj',p,q)
            quality=cq.quad_quality(p,q,target);fit=cq._guide_fit(p,paths,curves,h)
            feature=measure_features(source,triangles,p,q,target)
            contact=cq.surface_intersections(p,q,both_quad_diagonals=True)
            latest=dict(stage=label,refinement=detail,quality=quality,guideFit=fit,features=feature,contacts=contact,passed=False)
            if full and quality['passed'] and contact['passed']:
                latest['surface']=cq.validate_surface(source,triangles,p,q,target,accelerated=True)
                witnesses.extend(surface_witnesses(latest))
            latest['passed']=bool(quality['passed'] and feature['passed'] and contact['passed'] and latest.get('surface',{}).get('passed') and cq.guides_pass(fit,h))
            history.append(latest);write(out/'history.json',history)
            return latest['passed']

        if not latest['contacts']['passed']:
            for region in range(4):
                original=(p.copy(),q.copy(),latest);improved=False
                for rings,subdivide in ((2,0),(1,0),(3,0),(1,1),(2,1),(3,1)):
                    repaired,faces,active,detail=repair_contacts(mesh,p,q,paths,latest['contacts'],rings,subdivide)
                    write(out/f'contact-patch-{region}-{rings}-{subdivide}.json',detail)
                    if not detail['applied']:continue
                    if len(faces)>target*1.15:continue
                    p,q=repaired,faces
                    for iteration in range(5):
                        cq._progress(job,f'Repairing local surface crossings · region {region+1}, pass {iteration+1}')
                        pairs=contact_neighborhood(p,q,h,active)
                        p,detail=refine(mesh,p,q,curves,target,paths,contacts=pairs,active_vertices=active,witnesses=witnesses,compact_active_terms=True)
                        check(f'contact-patch-{region}-{rings}-{subdivide}-{iteration}',detail)
                        if latest['quality']['passed']:break
                    previous=len(original[2]['contacts']['nonAdjacentIntersectingFacePairs'])+len(original[2]['contacts']['adjacentIntersectingFacePairs'])
                    current=len(latest['contacts']['nonAdjacentIntersectingFacePairs'])+len(latest['contacts']['adjacentIntersectingFacePairs'])
                    if latest['quality']['passed'] and current<previous:improved=True;break
                    p,q,latest=original
                if not improved or latest['contacts']['passed']:break

        if latest['quality']['passed'] and latest['contacts']['passed']:
            if not (latest['features']['passed'] and latest.get('surface',{}).get('passed')):
                p,q,subdivision=refine_features(mesh,p,q,paths,target)
                write(out/'feature-refinement.json',subdivision)
                for iteration in range(8):
                    if time.monotonic()-start>1400:break
                    if iteration==4 and not latest['features']['passed']:
                        p,q,extra=refine_features(mesh,p,q,paths,target)
                        write(out/'feature-refinement-extra.json',extra)
                    cq._progress(job,f'Preserving source creases and face clearance · pass {iteration+1}')
                    p,detail=refine(mesh,p,q,curves,target,paths,contacts=contact_neighborhood(p,q,h),witnesses=witnesses,feature_strength=1.4,guide_tangent_strength=12)
                    check(f'preserve-features-{iteration}',detail)
                    if latest['quality']['passed'] and latest['contacts']['passed'] and latest['features']['passed'] and latest.get('surface',{}).get('passed'):break
            if latest['quality']['passed'] and latest['contacts']['passed'] and not (latest['features']['passed'] and latest.get('surface',{}).get('passed')):
                before=len(p);p,q,subdivision=refine_failures(mesh,p,q,paths,target,latest)
                write(out/'remaining-feature-refinement.json',subdivision)
                active=np.unique(np.r_[failure_region(mesh,p,q,target,latest),np.arange(before,len(p))])
                for iteration in range(8):
                    if time.monotonic()-start>1400 or not len(active):break
                    active=np.unique(np.r_[active,failure_region(mesh,p,q,target,latest)])
                    cq._progress(job,f'Fitting remaining local creases and surface details · pass {iteration+1}')
                    p,detail=refine(mesh,p,q,curves,target,paths,contacts=contact_neighborhood(p,q,h,active),witnesses=witnesses,active_vertices=active,
                                    feature_strength=2.,guide_tangent_strength=12,compact_active_terms=True,dense_features=True)
                    check(f'remaining-features-{iteration}',detail)
                    if latest['quality']['passed'] and latest['contacts']['passed'] and latest['features']['passed'] and latest.get('surface',{}).get('passed'):break
            if not latest['passed'] and curves:
                p,q,paths,subdivision=refine_guides(p,q,paths,target,curves,h)
                write(out/'guide-refinement.json',subdivision);active=guide_region(q,paths)
                for iteration in range(6):
                    if time.monotonic()-start>1400:break
                    cq._progress(job,f'Fitting distinct guide and source-crease paths · pass {iteration+1}')
                    p,detail=refine(mesh,p,q,curves,target,paths,contacts=contact_neighborhood(p,q,h,active),witnesses=witnesses,active_vertices=active,
                                    feature_strength=2.,guide_tangent_strength=12,guide_position_strength=110,guide_vertex_strength=30,compact_active_terms=True)
                    if check(f'preserve-guides-{iteration}',detail):break
                # Nearby source creases and authored guides can compete for the
                # same output edge. Fit distinct paths when that compromise
                # fails the independent feature or guide gates.
                if not latest['passed']:
                    for iteration in range(8):
                        if time.monotonic()-start>1400:break
                        active=np.unique(np.r_[active,failure_region(mesh,p,q,target,latest)])
                        cq._progress(job,f'Separating guide paths from nearby source creases · pass {iteration+1}')
                        p,detail=refine(mesh,p,q,curves,target,paths,contacts=contact_neighborhood(p,q,h,active),witnesses=witnesses,active_vertices=active,
                                        feature_strength=2.,guide_tangent_strength=30,guide_position_strength=110,guide_vertex_strength=30,
                                        compact_active_terms=True,separate_guide_features=True,dense_features=True)
                        if check(f'separate-guides-{iteration}',detail):break
            if (not latest['passed'] and latest['quality']['passed'] and latest['contacts']['passed']
                    and latest['features']['passed'] and cq.guides_pass(latest['guideFit'],h)):
                active=failure_region(mesh,p,q,target,latest)
                for iteration in range(8):
                    if time.monotonic()-start>1400 or not len(active):break
                    active=np.unique(np.r_[active,failure_region(mesh,p,q,target,latest)])
                    witnesses.extend(local_surface_samples(mesh,p,q,target,active))
                    cq._progress(job,f'Checking and fitting remaining surface details · pass {iteration+1}')
                    p,detail=refine(mesh,p,q,curves,target,paths,contacts=contact_neighborhood(p,q,h,active),witnesses=witnesses,active_vertices=active,
                                    feature_strength=2.,guide_tangent_strength=30,guide_position_strength=110,guide_vertex_strength=30 if curves else 0,
                                    compact_active_terms=True,separate_guide_features=bool(curves),dense_features=True)
                    if check(f'remaining-surface-{iteration}',detail):break
        if latest['passed']:
            metadata=dict(backend=cq.BACKEND,target=target,guideMode=2,closedValidation=latest['surface'],guidePaths=latest['guideFit'],
                          intersectionValidation=latest['contacts'],featureValidation=latest['features'],outputCreases=output_creases(p,q.tolist()),
                          refinementHistory=history,layoutEngine=dict(name='Feature and guide orientation QuadriFlow',**engine),
                          timings=dict(layout=layout_seconds,total=time.monotonic()-start),sourceHashes=source_hashes,
                          limitations=['Small angular source fragments are reported separately; full source surface bounds still apply.',
                                       'Feature and guide field constraints with conforming local quad refinement; no native parity claim.',
                                       'Reference contact predicates and bounded surface distances use double precision.'])
            write(job/'surface-solver.json',metadata)
            return p,q.tolist(),metadata
    write(job/'failed-feature-candidate.json',dict(vertices=p.tolist(),faces=q.tolist(),history=history))
    raise ValueError('The feature-aware layout did not pass every source-feature, guide, surface and contact check. No new result was accepted.')
