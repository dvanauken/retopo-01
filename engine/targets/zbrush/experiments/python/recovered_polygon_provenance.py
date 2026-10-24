"""314bf0/314d60 ordered sparse provenance expansion for derived vertices."""
import numpy as np
F=np.float32


class Provenance:
    def __init__(self,base):self.base=base;self.offsets=[0];self.indices=[];self.weights=[]

    def append(self,vertices,weights):
        for vertex,weight in zip(vertices,weights):
            vertex=int(vertex);weight=F(weight)
            if vertex<self.base:
                self.indices.append(vertex);self.weights.append(weight)
            else:
                index=vertex-self.base
                if not 0<=index<len(self.offsets)-1:raise ValueError('Derived source provenance not yet defined')
                for i in range(self.offsets[index],self.offsets[index+1]):self.indices.append(self.indices[i]);self.weights.append(F(self.weights[i]*weight))
        self.offsets.append(len(self.indices));return self.base+len(self.offsets)-2

    def arrays(self):return dict(offsets=np.asarray(self.offsets,dtype='<i4'),indices=np.asarray(self.indices,dtype='<i4'),weights=np.asarray(self.weights,dtype='<f4'))
