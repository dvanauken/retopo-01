"""2e8d50 initial guide edge projection, with103060 float32 record conversion."""
import numpy as np
F=np.float32

def project(point,edge,positions,edges):
    a,b=np.asarray(positions,dtype='<f4')[np.asarray(edges)[int(edge)]];delta=F(b-a);offset=F(np.asarray(point,dtype='<f4')-a);numerator=F(F(F(delta[1]*offset[1])+F(delta[0]*offset[0]))+F(delta[2]*offset[2]));denominator=F(F(F(delta[0]*delta[0])+F(delta[1]*delta[1]))+F(delta[2]*delta[2]))
    if not denominator>0 or not np.isfinite(numerator):raise NotImplementedError('Finite positive-length initial edge projection required')
    t=float(numerator)/float(denominator);t=max(0.,min(1.,t));position=F(F(a*F(1.-t))+F(b*F(t)))
    return position,F(t),t
