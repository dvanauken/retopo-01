"""26f400 default candidate gate; scalar field controls remain explicit."""
import numpy as np
F=np.float32


def prepare(field,influence,anisotropy,curvature_factor,normal_limit):
    largest=field['largest'];middle=field['middle'];directions=field['directions'];normal=field['edgeField']['normals'];distance=influence['normalized'];radii=field['radii']
    ratio=np.full(len(normal),F(anisotropy),dtype='<f4');blend=(distance>=F(.5))&(distance<F(1.5));t=F(distance[blend]-F(.5));ratio[blend]=F(F(ratio[blend]-F(1))*t+F(1))
    threshold=F(F(1)/F(radii*F(curvature_factor)));valid=[]
    for scale in range(len(radii)):
        maximum=abs(largest[scale]);minimum=abs(middle[scale]);a=np.zeros_like(maximum);np.divide(F(maximum-minimum),maximum,out=a,where=maximum!=0)
        dot=abs(F(F(normal[:,1]*directions[scale,:,1]+normal[:,0]*directions[scale,:,0])+normal[:,2]*directions[scale,:,2]));valid.append((a>=ratio)&(maximum>=threshold[scale])&(dot<=F(normal_limit)))
    return dict(valid=np.asarray(valid,dtype=bool),curvatureThreshold=threshold,anisotropyThreshold=ratio)
