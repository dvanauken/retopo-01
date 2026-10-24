"""2fc0c0 ordinary embedded mode1/2 edge directions on incident source faces."""
import math
import numpy as np
F=np.float32


def prepare(geometry,topology):
    positions=geometry['positions'];pairs=geometry['embeddedPairs'];triangles=geometry['faces']
    if np.any(pairs[:,0]!=1):raise NotImplementedError('Nonvertex guide constraints')
    lookup={tuple(map(int,row)):i for i,row in enumerate(topology['edges'])};directions=np.zeros((len(triangles),3),dtype='<f4');flags=np.zeros(len(triangles),dtype=np.uint8);selected=[]
    for a,b in zip(pairs[:-1,1],pairs[1:,1]):
        edge=lookup.get(tuple(sorted((int(a),int(b)))))
        if edge is None:continue
        direction=F(positions[b]-positions[a]);squared=F(F(direction[0]*direction[0]+direction[1]*direction[1])+direction[2]*direction[2]);length=math.sqrt(float(squared))
        if not length>=1e-28:raise NotImplementedError('Tiny/zero embedded guide direction policy')
        direction=np.asarray([F(float(c)*(1/length)) for c in direction],dtype='<f4');corners=topology['edgeCorners'][topology['edgeCornerOffsets'][edge]:topology['edgeCornerOffsets'][edge+1]]
        for corner in corners:directions[int(corner)//3]=direction;flags[int(corner)//3]=5
        selected.append(edge)
    return dict(directions=directions,flags=flags,weights=np.ones(len(triangles),dtype='<f4'),selectedEdges=np.asarray(selected,dtype='<i4'))
