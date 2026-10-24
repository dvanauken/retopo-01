"""Multiple-mode2 source composition fork; native qualification is separate.
Original guided chart/initial solve through ordinary first distortion reweight."""
from recovered_cholmod_reference_backend import solve_sparse as spsolve
from recovered_torus_initial_parameter import prepare as initial
from recovered_parameter_system import first_reweight
from recovered_symmetric_weighted_normal import assemble as normal_system
from verify_coordinate_reconstruction import reconstruct


def prepare(source,faces,target,drawn,cut,seeds,weight_control,smoothing_iterations,guide_mode):
    if type(guide_mode) is not int or guide_mode not in (1,2):raise NotImplementedError('Only explicit homogeneous active guide modes1/2')
    own=initial(source,faces,target,drawn,cut,seeds,weight_control,guide_mode);g=own['geometry'];r=own['initialParameter'];full=reconstruct(r['solution'],r['inverse'],own['parameterConstraints']['dependencies'],len(own['parameterConstraints']['mapping']))[:2*len(own['parameterFans']['sourceIds'])].reshape(-1,2)
    data=dict(positions=g['positions'],tri=g['faces'],uv=own['parameterFans']['triangles'],kwargs=own['parameterKwargs'],groups=own['parameterGroups']);f=own['frames'];multipliers,unsmoothed=first_reweight(data,full,own['edgeField']['normals'],[f['scaleA'],f['scaleB']],smoothing_iterations);weights=r['weights']*multipliers.ravel();H,rhs=normal_system(r['reducedMatrix'],weights,r['targets']);solution=spsolve(H,rhs)
    own['continuousParameter']=dict(initialUV=full,multipliers=multipliers,unsmoothed=unsmoothed,weights=weights,normalMatrix=H,rhs=rhs,solution=solution)
    return own
