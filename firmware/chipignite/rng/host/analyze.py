#!/usr/bin/env python3
"""Phase portraits from chip data or from the bit-exact models.

    python3 host/analyze.py data/single_full.npz --out figures/phase_single_chip.pdf
    python3 host/analyze.py double --n 20000 --skip 2000 --out figures/phase_double.pdf
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models  # noqa: E402


def load_xyz(src, n, skip):
    if src in models.DESIGNS:
        xyz = models.run(src, (n or 20000) + skip)[skip:]
        return models.to_real(src, xyz), src + " model"
    d = np.load(src)
    design = str(d["design"])
    xyz = d["xyz"][skip:]
    return models.to_real(design, xyz[:n] if n else xyz), design + " chip"


def plot_phase(r, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.size": 10, "mathtext.fontset": "stix"})

    fig, ax = plt.subplots(1, 3, figsize=(10, 3.3))
    for k, (i, j) in enumerate([(0, 1), (0, 2), (1, 2)]):
        ax[k].plot(r[:, i], r[:, j], lw=0.25, color="#1f3b73")
        ax[k].set_xlabel("$%s$" % "xyz"[i])
        ax[k].set_ylabel("$%s$" % "xyz"[j])
        ax[k].set_title("(%s) $%s$-$%s$" % ("abc"[k], "xyz"[i], "xyz"[j]), fontsize=10)
        ax[k].grid(alpha=0.25, lw=0.5)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    fig.savefig(out, dpi=300)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="NAME_full.npz from suite.py, or single / double for the model")
    ap.add_argument("--n", type=int, default=0, help="number of samples (model default: 20000)")
    ap.add_argument("--skip", type=int, default=0, help="initial samples to drop")
    ap.add_argument("--out", default="figures/phase.pdf")
    a = ap.parse_args()
    r, label = load_xyz(a.src, a.n, a.skip)
    plot_phase(r, a.out)
    print("%s: %d samples -> %s" % (label, len(r), a.out))


if __name__ == "__main__":
    main()
