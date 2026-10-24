"""Immutable default field controls from2758d0 literal stores and274c70 sinf."""
import math
import numpy as np


def prepare():
    def scalar(bits):return np.frombuffer(int(bits).to_bytes(4,'little'),'<f4')[0]
    anisotropy=scalar(0x3f333333);factor=scalar(0x4073106a);angle=scalar(0x3f060a92)
    return dict(anisotropy=anisotropy,curvatureFactor=factor,normalAngle=angle,normalDotLimit=np.float32(math.sin(float(angle))))
