"""Strict float source face/edge/vertex classifier10bdd0, explicit topology."""
import numpy as np
F=np.float32


def dot(a,b):return F(F(F(a[1]*b[1])+F(a[0]*b[0]))+F(a[2]*b[2]))


def classify(pair,point,positions,faces,topology,snap,tolerance_squared):
    kind,index=map(int,pair);point=F(point).copy();edges=topology['edges'];faceEdges=topology['faceEdges'].reshape(-1,3)
    if snap:
        if kind!=4:return np.asarray((kind,index),dtype='<i4'),point
        for vertex in faces[index]:
            delta=F(point-positions[vertex])
            if dot(delta,delta)<tolerance_squared:kind=1;selected=int(vertex)
        if kind==1:index=selected;point=positions[index].copy()
    if kind==4:
        for edge in faceEdges[index]:
            a,b=positions[edges[edge]];delta=F(b-a);length=F(np.sqrt(dot(delta,delta)))
            if length==0:raise NotImplementedError('Degenerate classifier source edge')
            direction=F(delta*F(F(1)/length));offset=F(point-a);parameter=dot(offset,direction);residual=F(offset-F(direction*parameter));projected=F(point-residual)
            if dot(residual,residual)<tolerance_squared:kind=2;selected=int(edge);last=projected
        if kind==2:
            index=selected;point=last
            if snap:
                cursor=index
                for endpoint in range(2):
                    vertex=int(edges[cursor,endpoint]);delta=F(point-positions[vertex])
                    if dot(delta,delta)<tolerance_squared:kind,index,cursor=1,vertex,vertex
                if kind==1:point=positions[index].copy()
    return np.asarray((kind,index),dtype='<i4'),point
