"""Multiple-mode2 source composition fork; native qualification is separate.
Default guided continuous solve with only original input and cut/seed channels."""
from recovered_torus_continuous_parameter import prepare as continuous
from recovered_parameter_defaults import controls


def prepare(source,faces,target,drawn,cut,seeds,guide_mode):
    if type(guide_mode) is not int or guide_mode not in (1,2):raise NotImplementedError('Only explicit homogeneous active guide modes1/2')
    defaults=controls();own=continuous(source,faces,target,drawn,cut,seeds,defaults['scalars']['0x614'],defaults['distortionSmoothing'],guide_mode);own['parameterDefaults']=defaults
    return own
