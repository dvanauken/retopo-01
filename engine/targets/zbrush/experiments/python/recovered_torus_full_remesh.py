"""Original-input active mode2 multiple-guide full candidate, qualification separate."""
from recovered_torus_source_cut_graph import prepare as cuts
from recovered_torus_cap_finished_mesh import prepare as finish

def prepare(source,faces,target,drawn_curves,guide_mode=2):
    if type(guide_mode) is not int or guide_mode not in (1,2):raise NotImplementedError("Explicit homogeneous active guide modes1/2 required")
    upstream=cuts(source,faces,target,drawn_curves,guide_mode);own=finish(source,faces,target,drawn_curves,upstream['sourceCutGraph']['cut'],upstream['sourceSeeds']['seeds'],guide_mode)
    for a,b in [(own['geometry']['positions'],upstream['geometry']['positions']),(own['geometry']['faces'],upstream['geometry']['faces']),(own['angular']['angles'],upstream['angular']['angles']),(own['angular']['quarterTransitions'],upstream['angular']['quarterTransitions'])]:
        if a.tobytes()!=b.tobytes():raise RuntimeError('Repeated original-input multi-guide upstream changed')
    own['sourceCutGraph']=upstream['sourceCutGraph'];own['sourceSeeds']=upstream['sourceSeeds'];own['upstreamReplayStable']=True
    return own
