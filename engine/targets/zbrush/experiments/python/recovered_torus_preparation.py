"""Original closed source through ordinary admitted-feature-aware conditioning.

Closed degree-two weighted feature graphs and ordinary default quality passes.
Accepted paths/locks/default controls are source-produced; no native mask input.
"""
from recovered_quality_conditioned_densification import densify
from recovered_weighted_closed_feature_admission import prepare as admit,minimum_length_from_original
from recovered_locked_moderate_conditioning import smooth_prepared

def prepare(positions,faces,target):
    minimum=minimum_length_from_original(positions,faces,target)
    positions,faces,dense=densify(positions,faces,target)
    features=admit(positions,faces,minimum)
    positions,faces,result=smooth_prepared(positions,faces,features['lockedVertices'])
    result.update(densification=dense,sourceFeatureAdmission=features,featureLockMaskIsExplicitInput=False,scope='Ordinary closed source with default quality/ordinary midpoint passes and degree-two weighted closed feature cycles or none, default threshold/length controls and no external exclusions/protection/attributes. Open/junction/preservation/class/exceptional policies remain unsupported; full native correspondence qualifies separately.')
    return positions,faces,result
