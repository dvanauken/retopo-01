"""Bounded triangle paired-corner transport for0x060b30/0x287370."""
def paired_sides(pathEdges,pathVertices,triangles,parameterTriangles,faceEdges,offsets,corners,transitions):
 flat=triangles.ravel();uv=parameterTriangles.ravel();fe=faceEdges.ravel()
 if len(pathVertices)!=len(pathEdges)+1 or not len(pathEdges):raise ValueError('Expected nonempty oriented edge path')
 adjacent=lambda edge:[int(v) for v in corners[offsets[edge]:offsets[edge+1]]]
 first=adjacent(pathEdges[0])
 if len(first)!=2:raise ValueError('Bounded two-sided manifold path required')
 A=[first[0]];B=[first[1]];maxSteps=0
 for index,edge in enumerate(pathEdges[1:],1):
  target=adjacent(edge)
  if len(target)!=2:raise ValueError('Target edge is not manifold')
  current=A[-1];seen=set()
  for count in range(1,300):
   face,corner=divmod(current,3);neighbor=face*3+((corner-1)%3 if flat[current]==pathVertices[index] else (corner+1)%3);incident=adjacent(fe[neighbor])
   if len(incident)!=2 or neighbor not in incident:raise ValueError('Invalid corner adjacency')
   opposite=incident[1] if incident[0]==neighbor else incident[0]
   if neighbor in target:
    A.append(neighbor);B.append(target[1] if target[0]==neighbor else target[0]);maxSteps=max(maxSteps,count);break
   if opposite in seen:raise ValueError('Corner fan cycle before target')
   seen.add(opposite);current=opposite
  else:raise ValueError('Unqualified long walk')
 def output(side):
  out=[]
  for i,vertex in enumerate(pathVertices):
   c=side[min(i,len(side)-1)]
   if flat[c]!=vertex:c=(c//3)*3+(c%3+1)%3
   if flat[c]!=vertex:raise ValueError('Path corner endpoint mismatch')
   out.append(int(uv[c]))
  return out
 quarter=int(transitions[pathEdges[0]])
 if A[0]!=first[0]:quarter=-quarter
 return output(A),output(B),quarter,maxSteps
