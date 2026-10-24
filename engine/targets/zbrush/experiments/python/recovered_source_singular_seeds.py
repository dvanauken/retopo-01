"""27c100 closed ordinary quarter residues and angle-compatibility seed flags.

Default604=0/5b4 enabled, nonzero source normals, no symmetry metadata.
Boundary and nonmanifold behavior deliberately rejected.
"""
import math
import numpy as np
F=np.float32
PERIOD=np.frombuffer(bytes.fromhex('db0fc93f'),'<f4')[0]


def prepare(positions,triangles,normals,topology,angles,connections,quarters):
    eo=topology['edgeCornerOffsets'];ec=topology['edgeCorners'];vo=topology['vertexCornerOffsets'];vc=topology['vertexCorners'];fe=topology['faceEdges'].reshape(-1,3)
    if np.any(np.diff(eo)!=2):raise NotImplementedError('Closed two-sided ordinary source only')
    seeds=[];types=[];flags=[];geometric=[];residuals=[]
    for vertex in range(len(positions)):
        total=0;geometricSum=0.;residual=F(0)
        for corner in vc[vo[vertex]:vo[vertex+1]]:
            face,k=divmod(int(corner),3);a=F(positions[triangles[face,(k+2)%3]]-positions[vertex]);b=F(positions[triangles[face,(k+1)%3]]-positions[vertex]);n=normals[face]
            if not np.any(n):raise NotImplementedError('Zero normal branch')
            dot=lambda x,y:F(F(x[1]*y[1]+x[0]*y[0])+x[2]*y[2]);den=math.sqrt(float(dot(a,a))*float(dot(b,b)))
            angle=0. if den==0 else math.acos(max(-1.,min(1.,float(dot(a,b))/den)))
            oriented=F(F(F(a[0]*b[2]-a[2]*b[0])*n[1]+n[0]*F(a[2]*b[1]-a[1]*b[2]))+F(a[1]*b[0]-a[0]*b[1])*n[2])
            if oriented<=0:angle=0. if angle==0 else math.tau-angle
            geometricSum+=angle;edge=int(fe[face,(k+2)%3]);first,second=map(int,ec[eo[edge]:eo[edge+1]]//3);q=int(quarters[edge]);signed=q%4
            if signed==3:signed=-1
            if face!=first:signed=-signed
            total+=signed;delta=F(F(F(connections[edge]-angles[first])+angles[second])-F(F(q)*PERIOD));residual=F(residual+delta) if face==first else F(residual-delta)
        residue=total%4;difference=F(residual-F(geometricSum));special=bool(F(-.05)<difference<F(.05));geometric.append(geometricSum);residuals.append(residual)
        if residue or special:seeds.append(vertex);types.append(residue);flags.append(int(special))
    return dict(seeds=np.asarray(seeds,dtype='<i4'),types=np.asarray(types,dtype='<i4'),flags=np.asarray(flags,dtype='u1'),geometricAngles=np.asarray(geometric,dtype='<f8'),residualAngles=np.asarray(residuals,dtype='<f4'))
