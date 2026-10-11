#!/usr/bin/env python3
"""Capture the full output of the APP=suite firmware in one run.

    python3 host/suite.py                       # then press RESET on the board
    python3 host/suite.py --lsb-bytes 2000000

Writes, for source NAME (detected from the board):
    data/NAME_suite.log      selftest and benchmark text
    data/bench_NAME.txt      benchmark lines for compare.py
    data/NAME_full.npz/.csv  20000 full samples (verified against the RTL model)
    data/NAME_lsb.bin        random byte stream for compare.py
    figures/phase_NAME.pdf   phase portrait (chaotic sources)
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze  # noqa: E402
import collect  # noqa: E402
import models  # noqa: E402

NAMES = {"single-attractor": "single", "double-attractor": "double", "software": "software"}


def read_text(port):
    buf, start = b"", -1
    while True:
        chunk = port.read(256)
        if not chunk:
            continue
        buf += chunk
        if start < 0:
            start = buf.find(b"\n== ")
            if start < 0:
                buf = buf[-8:]
                continue
            buf, start = buf[start + 1:], 0
        end = buf.find(b"STAGE,full")
        if end >= 0 and b"\n" in buf[end:]:
            cut = buf.index(b"\n", end) + 1
            return buf[:cut].decode("ascii", "replace").replace("\r", ""), buf[cut:]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="ftdi://ftdi:232h/1", help="ftdi://ftdi:232h/1 or /dev/ttyUSB0")
    ap.add_argument("--samples", type=int, default=20000, help="full samples to keep")
    ap.add_argument("--lsb-bytes", type=int, default=1000000, help="random bytes to collect")
    ap.add_argument("--data", default="data")
    ap.add_argument("--figures", default="figures")
    a = ap.parse_args()

    port = collect.open_port(a.port)
    os.makedirs(a.data, exist_ok=True)

    print("waiting for the board, press RESET ...")
    text, rest = read_text(port)
    name = next((v for k, v in NAMES.items() if k in text.splitlines()[0]), "unknown")
    print(text, end="")

    with open(os.path.join(a.data, "%s_suite.log" % name), "w") as f:
        f.write(text)
    with open(os.path.join(a.data, "bench_%s.txt" % name), "w") as f:
        f.write("".join(l + "\n" for l in text.splitlines() if l.startswith(("BENCH,", "CROSSCHECK"))))
    selftest = "SELFTEST PASS" in text
    crosscheck = "n/a" if name == "software" else ("OK" if "CROSSCHECK sw==hw OK" in text else "FAIL")

    reader = collect.PacketReader(port)
    reader.buf += rest
    first = reader.next()
    while not first[0] & collect.PKT_FULL:
        first = reader.next()
    t0 = time.time()
    data, seq = collect.collect_full(reader, first, a.samples)
    prefix = os.path.join(a.data, "%s_full" % name)
    np.savez(prefix + ".npz", xyz=data, seq=seq, decim=first[1], design=name)
    np.savetxt(prefix + ".csv", np.column_stack([seq, data]), fmt="%d", delimiter=",",
               header="seq,x,y,z", comments="")
    ref = models.run(name, int(seq[-1]) + 1, decim=first[1])[seq]
    mismatches = int((ref != data).any(axis=1).sum())
    print("verify: %s (%d mismatches in %d samples, %.0f s)"
          % ("PASS" if mismatches == 0 else "FAIL", mismatches, len(data), time.time() - t0))
    if name != "software":
        out = os.path.join(a.figures, "phase_%s.pdf" % name)
        analyze.plot_phase(models.to_real(name, data), out)
        print("phase portrait:", out)

    first = reader.next()
    while first[0] & collect.PKT_FULL:
        first = reader.next()
    lsb = os.path.join(a.data, "%s_lsb.bin" % name)
    collect.collect_lsb(reader, first, a.lsb_bytes, lsb)
    port.close()

    print("\n== summary: %s ==" % name)
    print("selftest    %s" % ("PASS" if selftest else "FAIL"))
    print("crosscheck  %s" % crosscheck)
    print("verify      %s" % ("PASS" if mismatches == 0 else "FAIL"))
    print("files       %s_suite.log, bench_%s.txt, %s_full.npz, %s_lsb.bin" % (name, name, name, name))


if __name__ == "__main__":
    main()
