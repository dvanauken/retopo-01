"""Bounded guide scalar equalities and mode-two integer flags0x28b920."""
import copy
from recovered_dependency_expansion import expand

def build(groups,axes,edgeModes,parameterEdges,existing,originalMap,flags,denominators,sourceEdgeMap,skip):
 mapping=list(originalMap);flags=list(flags);denominators=list(denominators);base=len(existing);direct=[];rows=[];preferred=[];roots=[-1]*len(groups);details=[]
 for groupIndex,(group,axis) in enumerate(zip(groups,axes)):
  axis=int(axis)
  if axis==-1:continue
  group=list(map(int,group))
  if group and skip[sourceEdgeMap[group[0]]]:group=group[1:]
  if group and skip[sourceEdgeMap[group[-1]]]:group=group[:-1]
  if not group:continue
  seen=set();vertices=[]
  for edge in group:
   for vertex in parameterEdges[edge]:
    vertex=int(vertex)
    if vertex not in seen:seen.add(vertex);vertices.append(vertex)
  if not vertices:continue
  anchor=next((2*v+axis for v in vertices if mapping[2*v+axis]==-1),None);roots[groupIndex]=anchor if anchor is not None else -1
  if anchor is None:anchor=2*vertices[0]+axis;anchorMap=mapping[anchor]
  else:anchorMap=-1
  mode=int(edgeModes[group[0]]);before=len(direct);beforeRows=len(rows)
  def mark(scalar):
   if mode==2 and flags[scalar]==0:flags[scalar]=1;denominators[scalar]=1
  mark(anchor)
  for vertex in vertices:
   scalar=2*vertex+axis
   if scalar==anchor:continue
   mark(scalar);dep=mapping[scalar]
   if dep==-1:
    mapping[scalar]=base+len(direct);direct.append(dict(dependent=scalar,terms=[[anchor,1.]]))
   else:
    terms=copy.deepcopy(existing[dep]['terms']) if dep<base else [[scalar,1.]]
    if anchorMap==-1:terms.append([anchor,-1.])
    else:
     provider=existing[anchorMap] if anchorMap<base else direct[anchorMap-base]
     terms.extend([[c,-v] for c,v in provider['terms']])
    rows.append(terms)
    if not preferred or preferred[-1]!=anchor:preferred.append(anchor)
  details.append(dict(group=groupIndex,vertices=len(vertices),newDependencies=len(direct)-before,newConstraintRows=len(rows)-beforeRows,mode=mode,axis=int(axis)))
 if direct:direct=expand(direct,direct,mapping,[base,-1,-1,len(direct)-1,0],True)
 return dict(dependencies=direct,rows=rows,preferred=preferred,roots=roots,mapping=mapping,flags=flags,denominators=denominators,groups=details)
