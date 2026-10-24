"""Float32 grouping at2eb320/2ebba0; explicit unlocked closed adjacency inputs."""
import numpy as np
from recovered_conditioning_weights import neighbors
F=np.float32
def diffuse(values,topology,average_weight,max_weight=None):
    out=values.copy();one=F(1);average_weight=F(average_weight)
    for vertex,value in enumerate(values):
        total=F(0);maximum=value;count=0
        for _,neighbor in neighbors(topology,vertex):total=F(total+values[neighbor]);maximum=max(maximum,values[neighbor]);count+=1
        if count==0:raise NotImplementedError('Unused source vertex')
        mean=F(total/F(count))
        if max_weight is None:out[vertex]=F(F(mean*average_weight)+F(value*F(one-average_weight)))
        else:
            maximum_weight=F(max_weight);center=F(F(one-average_weight)-maximum_weight);out[vertex]=F(F(mean*average_weight)+F(F(value*center)+F(maximum*maximum_weight)))
    return out
