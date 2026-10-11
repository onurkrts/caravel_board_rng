#!/usr/bin/env python3
"""Collect the random byte stream from the board over UART (9600 8N1, jumper J2 on).

    python3 host/collect.py --bytes 12500000 --out data/single_nist   # 100 x 1 Mbit for NIST
"""
import argparse
import os
import struct
import time

import numpy as np

BAUD = 9600
PAYLOAD = 192
HEADER = 10
PACKET = HEADER + PAYLOAD + 1
PKT_FULL = 0x01


def source_of(typ):
    return "software" if typ & 0x40 else "double" if typ & 0x20 else "single"


def open_port(name):
    if name.startswith("ftdi://"):
        from pyftdi.serialext import serial_for_url
        return serial_for_url(name, baudrate=BAUD, timeout=2)
    import serial
    return serial.Serial(name, BAUD, timeout=2)


class PacketReader:
    def __init__(self, port):
        self.port = port
        self.buf = bytearray()

    def _fill(self, n):
        while len(self.buf) < n:
            chunk = self.port.read(max(256, n - len(self.buf)))
            if not chunk:
                raise TimeoutError("no data from board (is J2 on? press RESET)")
            self.buf += chunk

    def next(self):
        while True:
            self._fill(3)
            i = self.buf.find(b"RNG")
            if i < 0:
                del self.buf[:-2]
                continue
            del self.buf[:i]
            self._fill(PACKET)
            typ, dec = self.buf[3], self.buf[4]
            seq = struct.unpack_from("<I", self.buf, 6)[0]
            payload = bytes(self.buf[HEADER:HEADER + PAYLOAD])
            xs = 0
            for b in payload:
                xs ^= b
            if typ & 0x0F not in (1, 2) or xs != self.buf[HEADER + PAYLOAD]:
                del self.buf[:1]
                continue
            del self.buf[:PACKET]
            return typ, dec, seq, payload


def collect_full(reader, first, n):
    typ, dec, seq, payload = first
    rows, seqs, lost, expect, t0 = [], [], 0, seq, time.time()
    while True:
        lost += max(0, (seq - expect) // 16)
        rows.append(np.frombuffer(payload, dtype="<u4").reshape(16, 3))
        seqs.append(np.arange(seq, seq + 16, dtype=np.int64))
        expect = seq + 16
        got = 16 * len(rows)
        if got % 320 == 0 or got >= n:
            print("\r%d/%d samples  %.0f/s  lost packets: %d"
                  % (min(got, n), n, got / max(time.time() - t0, 1e-9), lost), end="", flush=True)
        if got >= n:
            break
        _, _, seq, payload = reader.next()
    print()
    return np.vstack(rows)[:n], np.concatenate(seqs)[:n]


def collect_lsb(reader, first, target, path):
    _, _, seq, payload = first
    got, lost, expect, t0 = 0, 0, seq, time.time()
    with open(path, "wb") as f:
        while got < target:
            lost += max(0, (seq - expect) // 64)
            f.write(payload)
            got += len(payload)
            expect = seq + 64
            if got % (PAYLOAD * 50) == 0 or got >= target:
                rate = got / max(time.time() - t0, 1e-9)
                print("\r%d/%d bytes  %.0f B/s  eta %.1f min  lost packets: %d"
                      % (got, target, rate, (target - got) / max(rate, 1e-9) / 60, lost),
                      end="", flush=True)
            if got < target:
                _, _, seq, payload = reader.next()
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="ftdi://ftdi:232h/1", help="ftdi://ftdi:232h/1 or /dev/ttyUSB0")
    ap.add_argument("--bytes", type=int, default=12500000, help="random bytes to collect")
    ap.add_argument("--out", default="data/rng", help="output file prefix (.bin is added)")
    a = ap.parse_args()

    port = open_port(a.port)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    reader = PacketReader(port)
    first = reader.next()
    while first[0] & PKT_FULL:
        first = reader.next()
    print("stream: source=%s, %d bytes (about %.1f h)"
          % (source_of(first[0]), a.bytes, a.bytes / 908.0 / 3600))
    collect_lsb(reader, first, a.bytes, a.out + ".bin")
    print("saved %s.bin" % a.out)
    port.close()


if __name__ == "__main__":
    main()
