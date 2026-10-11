#!/usr/bin/env python3
"""Bit-exact Python models of the three RNG sources.

    python3 host/models.py print single 5
    python3 host/models.py check double build/rtl_double.txt
"""
import sys

import numpy as np

MASK = 0xFFFFFFFF


def sra(v, s):
    if v & 0x80000000:
        return ((v >> s) | (MASK << (32 - s))) & MASK
    return v >> s


class SingleAttractor:
    """Single-attractor jerk system: x'=y, y'=z, z'=-z-y*B(y)-x, a=4, h=2^-6, Q10.22."""
    frac = 22

    def __init__(self):
        self.reset()

    def reset(self):
        self.x, self.y, self.z = 0, 1 << 22, 0

    def step(self):
        x, y, z = self.x, self.y, self.z
        en = not (y >> 31) & 1 and (y >> 22) & 0x1FF
        by = (y << 2) & MASK if en else 0
        zd = (z + x + by) & MASK
        self.x = (x + sra(y, 6)) & MASK
        self.y = (y + sra(z, 6)) & MASK
        self.z = (z - sra(zd, 6)) & MASK


def sawtooth(f, u, l):
    hi = (f >> 26) & 0x3F
    xhigh = (hi - ((((l >> 3) & 1) << 5) | ((l & 0xF) << 1) | 1)) & 0x3F
    x26n = 0x3F if not (f >> 26) & 1 else 0
    u2 = (u >> 2) & 1
    xu = (hi - ((u2 << 5) | (u2 << 4) | ((u & 7) << 1) | 1)) & 0x3F
    out = xhigh if xhigh & 0x20 else (x26n if xu & 0x20 else xu)
    return ((out << 26) | (f & 0x3FFFFFF)) & MASK


class DoubleAttractor:
    """Double-attractor sawtooth system: x'=y, y'=z, z'=-a(f(x)+y+z), a=15/16, h=2^-3, Q6.26."""
    frac = 26
    X_INIT, Y_INIT, Z_INIT = 0xDE78D681, 0xFEEE4640, 0xFE8E511B

    def __init__(self, x0=X_INIT, y0=Y_INIT, z0=Z_INIT, scroll=0x4D4C4B, en=0x3):
        self.init = (x0, y0, z0)
        self.en = en
        self.ly, self.uy = (scroll >> 8) & 0xF, (scroll >> 12) & 7
        self.lz, self.uz = (scroll >> 16) & 0xF, (scroll >> 20) & 7
        self.reset()

    def reset(self):
        self.x, self.y, self.z = self.init

    def step(self):
        x, y, z, en = self.x, self.y, self.z, self.en
        if not en & 1:
            return
        xo = sawtooth(x, 0b100, 0b1011) if en & 2 else x
        yo = sawtooth(y, self.uy, self.ly) if en & 4 else y
        zo = sawtooth(z, self.uz, self.lz) if en & 8 else z
        zd1 = (xo + yo + zo) & MASK
        zd = (zd1 - sra(zd1, 4)) & MASK
        self.x = (x + sra(yo, 3)) & MASK
        self.y = (y + sra(zo, 3)) & MASK
        self.z = (z - sra(zd, 3)) & MASK


class Xorshift32:
    """Software reference: xorshift32 (Marsaglia, 2003); one sample = three outputs."""
    frac = 31
    SEED = 2463534242

    def __init__(self):
        self.reset()

    def reset(self):
        self.s = self.SEED
        self.step()

    def _next(self):
        x = self.s
        x ^= (x << 13) & MASK
        x ^= x >> 17
        x ^= (x << 5) & MASK
        self.s = x
        return x

    def step(self):
        self.x, self.y, self.z = self._next(), self._next(), self._next()


DESIGNS = {"single": SingleAttractor, "double": DoubleAttractor, "software": Xorshift32}


def run(design, n, start=0, decim=1):
    m = DESIGNS[design]()
    for _ in range(start * decim):
        m.step()
    out = np.empty((n, 3), dtype=np.uint32)
    for i in range(n):
        out[i] = (m.x, m.y, m.z)
        for _ in range(decim):
            m.step()
    return out


def to_real(design, u32):
    return u32.astype(np.uint32).view(np.int32) / float(1 << DESIGNS[design].frac)


def load_hex(path):
    return np.array([[int(v, 16) for v in line.split()] for line in open(path)], dtype=np.uint32)


def main():
    if len(sys.argv) < 4 or sys.argv[1] not in ("print", "check"):
        print(__doc__)
        return
    cmd, design, arg = sys.argv[1:4]
    if cmd == "print":
        for i, (x, y, z) in enumerate(run(design, int(arg))):
            print("%6d  %08x  %08x  %08x" % (i, x, y, z))
        return
    rtl = load_hex(arg)
    ref = run(design, len(rtl))
    bad = np.nonzero((rtl != ref).any(axis=1))[0]
    if len(bad):
        print("%s: MISMATCH at step %d of %d" % (design, bad[0], len(rtl)))
        sys.exit(1)
    print("%s: model matches RTL for all %d steps" % (design, len(rtl)))


if __name__ == "__main__":
    main()
