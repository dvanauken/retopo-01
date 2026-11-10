"""Native 0x28fe70 geometric separation policy, bounded finite inputs.

The app bundles this policy only; ordinary chart/seam row construction remains
outside this module. Native engine SHA256:
0d45ea6f9331cecb55c12a10dcdb6d4bedb86cf302cd873748704dbaa82b00bc.
Actual island6 target200 capture and prior v59 fixture qualify these branches.
"""
import numpy as np
F=np.float32

def policy(first_guide,second_guide,delta,cross):
    d=F(abs(delta));c=F(abs(cross));target=float(delta);weight=F(1);hard=soft=False
    if first_guide and second_guide:
        if d<F(1.35):hard=bool(F(d+d)>c)
        elif d<F(5):soft=bool(c<d)
    elif not first_guide and not second_guide:
        weight=F(.01)
        if float(c)*.2<=float(d):
            if d<c:weight=F(F(F(F(c/d)-F(.2))*np.array([0x3de66667],dtype=np.uint32).view(np.float32)[0])+F(.01))
            else:
                weight=F(100)
                if d>=F(1):
                    if d<F(2.5):weight=F(F(100)-F(F(d-F(1))*F(60)))
                    else:
                        weight=F(1)
                        if d<F(5):weight=F(F(10)-F(F(d-F(2.5))*F(3.6)))
    elif c<F(d+d):
        soft=bool(d<F(4.5))  # RVA0x291bc3..0x291c02: outer c<2d already checked.
    # RVA0x291a91/0x291bf5 retain the original target for larger soft gaps.
    if hard or (soft and d<F(1.35)):target=1. if delta>=0 else -1.
    return target,float(weight),hard,soft
