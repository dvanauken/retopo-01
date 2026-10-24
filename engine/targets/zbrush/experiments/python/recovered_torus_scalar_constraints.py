"""Bounded single-chart gauge and composed seam/guide scalar constraint construction."""
from recovered_unmarked_node_fan_scalars import initialize
from recovered_cyclic_cut_path_enumeration import enumerate_paths
from recovered_paired_cut_sides import paired_sides
from verify_paired_cut_seams import construct
from verify_seam_endpoint_equations import endpoint_rows
from recovered_augmentation_period_constraints import initialize as initialize_periods,endpoint_rows as period_rows
from recovered_initial_constraint_normalization import eliminate
from recovered_dependency_expansion import expand
from recovered_integer_substitution import substitute
from recovered_guide_equalities import build

def gauge(sourceTriangles,parameterTriangles,seeds):
 if not len(seeds):raise ValueError('Seeded gauge branch required')
 parent={int(v):int(v) for v in parameterTriangles.ravel()}
 def find(v):
  while parent[v]!=v:parent[v]=parent[parent[v]];v=parent[v]
  return v
 for triangle in parameterTriangles:
  for v in triangle[1:]:parent[find(int(v))]=find(int(triangle[0]))
 if len({find(v) for v in parent})!=1:raise ValueError('Only single parameter-component gauge qualified')
 candidates=sorted(set(int(v) for v,s in zip(parameterTriangles.ravel(),sourceTriangles.ravel()) if int(s)==int(seeds[0])))
 if not candidates:raise ValueError('Seed has no parameter fan')
 return [dict(dependent=2*candidates[0]+axis,terms=[]) for axis in range(2)]

def constraints(tri,uv,edges,faceEdges,edgeOffsets,edgeCorners,vertexOffsets,vertexEdges,selected,seeds,transitions,parameterEdges,groups,axes,modes,sourceEdgeMap,skip,augmented=None):
 paths,nodes=enumerate_paths(selected,edges,vertexOffsets,vertexEdges,seeds,[]);pins=gauge(tri,uv,seeds);pinIDs={r['dependent'] for r in pins};records=list(pins);endpointRows=[]
 _,flags,denominators,preferred=initialize(tri,uv,seeds,nodes);periodIds=[]
 if augmented is not None:
  if set(map(int,augmented))!=set(map(int,selected)):raise NotImplementedError('Mixed connector and augmented periods remain unqualified')
  flags,denominators,periodIds=initialize_periods(flags,denominators,len(paths))
 for i,(ep,vp) in enumerate(paths):
  a,b,q,_=paired_sides(ep,vp,tri,uv,faceEdges,edgeOffsets,edgeCorners,transitions);records.extend(construct(a,b,q,pinIDs));endpointRows.extend(period_rows(a,b,q,periodIds[i],pinIDs) if periodIds else endpoint_rows(a,b,q,pinIDs))
 initialSeams=list(records);mode0=eliminate(endpointRows,preferred,flags,0);mapping=[-1]*len(flags)
 def update():
  for i,r in enumerate(records):mapping[r['dependent']]=i
 initialCount=len(records);records+=mode0;update();records=expand(records,records,mapping,[0,initialCount,-1,-1,-1],True);beforeGuide=records
 guide=build(groups,axes,modes,parameterEdges,records,mapping,flags,denominators,sourceEdgeMap,skip);before=len(records);records=records+guide['dependencies'];mapping=guide['mapping'];records=expand(records,records,mapping,[0,before,len(records),0,before],True);guideRows=substitute(guide['rows'],records,mapping,[0,-1,-1,-1,-1]);mode1=eliminate(guideRows,guide['preferred'],guide['flags'],1);before=len(records);records+=mode1;update();records=expand(records,records,mapping,[0,before,len(records),0,before],True)
 return dict(periodIds=periodIds,scalarCount=len(flags),dependencies=records,gauge=pins,endpointRows=endpointRows,initialSeams=initialSeams,initialPreferred=preferred,mode0Dependencies=mode0,beforeGuide=beforeGuide,guide=guide,guideRows=guideRows,mode1Dependencies=mode1,mapping=mapping)
