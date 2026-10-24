"""296050: allocate two integer period scalars per augmented cut path.

Closed nonsymmetric identity-quarter subset. A period is a translation between
paired cut sides; it is not an extra surface vertex or a supplied guide sample.
"""
from probe_quarter_matrix import quarter

def endpoint_rows(side_a,side_b,turn,period,pinned):
    if int(turn)%4:raise NotImplementedError('Nonidentity quarter period constraints require separate qualification')
    if len(side_a)!=len(side_b) or len(side_a)<2:raise ValueError('Paired nonempty side paths required')
    rows=[]
    for k in [0,-1]:
        for axis in range(2):
            terms={}
            for i,value in [(2*int(side_a[k])+axis,-1.),(2*int(side_b[k])+axis,1.),(int(period)+axis,1.)]:terms[i]=terms.get(i,0.)+value
            rows.append([[i,v] for i,v in sorted(terms.items()) if v and i not in pinned])
    return rows

def initialize(flags,denominators,path_count):
    flags=list(flags);denominators=list(denominators);start=len(flags)
    if len(denominators)!=start or start%2:raise ValueError('Paired scalar metadata required')
    return flags+[3]*(2*path_count),denominators+[1]*(2*path_count),[start+2*i for i in range(path_count)]
