"""Source crease angle: the dihedral bend, in degrees, that counts as an auto guide."""
import math

DEFAULT = 30.   # ZRemesher's qualified feature threshold F(pi/6); verified on island 6 at 150/200/300 and
                # 750 + guide and on islands 2/7/10 once the layout engine carried the native size caps
MINIMUM, MAXIMUM = 10., 120.


def check(value):
    """Validated crease angle in degrees; bools and non-finite numbers are rejected."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not MINIMUM <= value <= MAXIMUM:
        raise ValueError(f'Crease angle must be a number from {MINIMUM:g} to {MAXIMUM:g} degrees.')
    return float(value)
