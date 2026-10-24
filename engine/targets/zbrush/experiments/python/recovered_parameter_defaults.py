"""1e9950 literal ordinary parameter controls; nondefault setters not modeled."""
import struct


def controls():
    literals={'0x60c':0x3fa66666,'0x610':0x3fe66666,'0x614':0x3f0ccccd,'0x618':0x461c4000,'0x690':0x42200000,'0x694':0x40800000}
    return dict(scalars={offset:struct.unpack('<f',struct.pack('<I',bits))[0] for offset,bits in literals.items()},preObjectiveSmoothing=5,distortionSmoothing=10)
