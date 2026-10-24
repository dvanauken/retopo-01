"""28fe70 weight-one residuals for free augmentation translation scalars.

These rows precede integer substitution/compression and are distinct from the
later1e-4 stabilizers. Targets are the incoming continuous solution values.
"""
import math

def append(rows,weights,targets,period_ids,outer_mapping,incoming):
    if not len(rows)==len(weights)==len(targets):raise ValueError('Residual channels disagree')
    out=[[list(t) for t in row] for row in rows];w=list(weights);b=list(targets);seen=set()
    for base in period_ids:
        for variable in [int(base),int(base)+1]:
            if variable in seen or not 0<=variable<len(outer_mapping):raise ValueError('Invalid/duplicate period scalar')
            seen.add(variable);mapped=int(outer_mapping[variable])
            if mapped<0:continue
            if mapped>=len(incoming) or not math.isfinite(float(incoming[mapped])):raise ValueError('Invalid incoming period coordinate')
            out.append([[variable,1.]]);w.append(1.);b.append(float(incoming[mapped]))
    return out,w,b
