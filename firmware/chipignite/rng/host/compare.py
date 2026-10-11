#!/usr/bin/env python3
"""Compare the single-attractor, double-attractor and software RNGs.

    python3 host/compare.py \\
        --lsb single=data/single_lsb.bin double=data/double_lsb.bin software=data/software_lsb.bin \\
        --bench data/bench_single.txt data/bench_double.txt data/bench_software.txt \\
        --image moon --out results

Outputs (in --out): randomness.csv/.tex, performance.csv/.tex, encryption.csv/.tex,
statistics.pdf, encryption.pdf
"""
import argparse
import math
import os
import re

import numpy as np

CLOCK_HZ = 10e6
SEQ_BITS = 1000000
ALPHA = 0.01


# ---------------------------------------------------------------- special functions

def igamc(a, x):
    """Regularized upper incomplete gamma Q(a, x)."""
    if x <= 0:
        return 1.0
    if x < a + 1:
        term = total = 1.0 / a
        ap = a
        for _ in range(10000):
            ap += 1
            term *= x / ap
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return 1.0 - total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b = x + 1 - a
    c = 1e300
    d = 1 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def phi(x):
    return 0.5 * math.erfc(-x / math.sqrt(2))


# ---------------------------------------------------------------- NIST SP 800-22 tests

def t_frequency(bits):
    n = len(bits)
    s = abs(2 * int(bits.sum()) - n) / math.sqrt(n)
    return math.erfc(s / math.sqrt(2))


def t_block_frequency(bits, m=128):
    nb = len(bits) // m
    pi = bits[: nb * m].reshape(nb, m).mean(axis=1)
    chi2 = 4 * m * ((pi - 0.5) ** 2).sum()
    return igamc(nb / 2, chi2 / 2)


def t_runs(bits):
    n = len(bits)
    pi = bits.mean()
    if abs(pi - 0.5) >= 2 / math.sqrt(n):
        return 0.0
    v = 1 + int((bits[1:] != bits[:-1]).sum())
    return math.erfc(abs(v - 2 * n * pi * (1 - pi)) / (2 * math.sqrt(2 * n) * pi * (1 - pi)))


def t_cusum(bits):
    n = len(bits)
    z = int(np.abs(np.cumsum(2 * bits.astype(np.int64) - 1)).max())
    sn = math.sqrt(n)
    s1 = sum(phi((4 * k + 1) * z / sn) - phi((4 * k - 1) * z / sn)
             for k in range(int(math.floor((-n / z + 1) / 4)), int(math.floor((n / z - 1) / 4)) + 1))
    s2 = sum(phi((4 * k + 3) * z / sn) - phi((4 * k + 1) * z / sn)
             for k in range(int(math.floor((-n / z - 3) / 4)), int(math.floor((n / z - 1) / 4)) + 1))
    return 1 - s1 + s2


NIST_TESTS = [("Frequency", t_frequency), ("Block frequency", t_block_frequency),
              ("Runs", t_runs), ("Cumulative sums", t_cusum)]


def self_check():
    eps = ("1100100100001111110110101010001000100001011010001100001000110100"
           "110001001100011001100010100010111000")
    b = np.array([int(c) for c in eps], dtype=np.uint8)
    got = [t_frequency(b), t_block_frequency(b, 10), t_runs(b), t_cusum(b)]
    ref = [0.109599, 0.706438, 0.500798, 0.219194]
    return all(abs(g - r) < 1e-5 for g, r in zip(got, ref))


# ---------------------------------------------------------------- randomness

def byte_stats(data):
    hist = np.bincount(data, minlength=256).astype(float)
    exp = len(data) / 256
    chi2 = ((hist - exp) ** 2 / exp).sum()
    p = hist / hist.sum()
    entropy = -(p[p > 0] * np.log2(p[p > 0])).sum()
    corr = np.corrcoef(data[:-1].astype(float), data[1:].astype(float))[0, 1]
    return chi2, igamc(127.5, chi2 / 2), entropy, corr


def randomness(name, path):
    data = np.fromfile(path, dtype=np.uint8)
    bits = np.unpackbits(data)
    nseq = max(1, len(bits) // SEQ_BITS)
    row = {"source": name, "bytes": len(data), "sequences": nseq}
    for tname, fn in NIST_TESTS:
        ps = [fn(bits[i * SEQ_BITS:(i + 1) * SEQ_BITS] if len(bits) >= SEQ_BITS else bits)
              for i in range(nseq)]
        row[tname + " pass"] = "%d/%d" % (sum(p >= ALPHA for p in ps), nseq)
        row[tname + " p"] = float(np.median(ps))
    chi2, pchi, ent, corr = byte_stats(data)
    row.update({"ones ratio": float(bits.mean()), "byte chi2": chi2, "byte chi2 p": pchi,
                "entropy/byte": ent, "lag-1 corr": corr})
    return row, data


# ---------------------------------------------------------------- performance

BENCH_RE = re.compile(r"BENCH,([A-Za-z0-9-]+),(\d+),(\d+)")
CROSS_RE = re.compile(r"CROSSCHECK sw==hw (OK|FAIL)")


def performance(paths):
    seen = {}
    for path in paths:
        text = open(path, errors="replace").read()
        for name, cycles, n in BENCH_RE.findall(text):
            if int(n) > 0 and int(cycles) > 0:
                seen.setdefault(name, []).append(int(cycles) / int(n))
        for result in CROSS_RE.findall(text):
            print("%s: CROSSCHECK sw==hw %s" % (path, result))
    overhead = float(np.mean(seen.pop("loop-overhead", [0.0])))
    rows = []
    for name, values in seen.items():
        cps = float(np.mean(values))
        rows.append({"source": name, "runs": len(values), "cycles/sample": cps,
                     "min": min(values), "max": max(values),
                     "samples/s": CLOCK_HZ / cps, "Mbit/s (96 bit)": CLOCK_HZ / cps * 96 / 1e6})
    return rows, overhead


# ---------------------------------------------------------------- image encryption

TEST_IMAGES = ("moon", "chelsea", "coffee", "camera", "brick")


def test_image(src, size=256):
    if src in TEST_IMAGES:
        try:
            from skimage import data
        except ImportError:
            raise SystemExit("--image %s needs scikit-image: pip install scikit-image" % src)
        img = getattr(data, src)()
    elif src:
        import matplotlib.image as mpimg
        img = mpimg.imread(src)
    else:
        yy, xx = np.mgrid[0:size, 0:size]
        img = 96 + 64 * np.sin(xx / 23.0) * np.cos(yy / 31.0) + 0.25 * xx
        img[(xx - 90) ** 2 + (yy - 110) ** 2 < 45 ** 2] = 220
        img[160:220, 150:230] = 40
        return np.clip(img, 0, 255).astype(np.uint8)
    img = np.asarray(img, dtype=float)
    if img.ndim == 3:
        img = img[..., :3] @ np.array([0.299, 0.587, 0.114])
    if img.max() <= 1.0:
        img = img * 255
    f = max(1, min(img.shape) // size)
    h, w = img.shape[0] // f * f, img.shape[1] // f * f
    img = img[:h, :w].reshape(h // f, f, w // f, f).mean(axis=(1, 3))
    top, left = (img.shape[0] - size) // 2, (img.shape[1] - size) // 2
    return np.clip(img[max(top, 0):max(top, 0) + size, max(left, 0):max(left, 0) + size], 0, 255).astype(np.uint8)


def encrypt(img, key):
    n = img.size
    words = np.frombuffer(key[: 4 * n].tobytes(), dtype="<u4")
    perm = np.arange(n)
    for i in range(n - 1, 0, -1):
        j = int(words[i]) % (i + 1)
        perm[i], perm[j] = perm[j], perm[i]
    stream = key[4 * n: 5 * n]
    return (img.reshape(-1)[perm] ^ stream).reshape(img.shape)


def adjacent_corr(img):
    a = img.astype(float)
    pairs = [(a[:, :-1], a[:, 1:]), (a[:-1, :], a[1:, :]), (a[:-1, :-1], a[1:, 1:])]
    return [np.corrcoef(p.ravel(), q.ravel())[0, 1] for p, q in pairs]


def npcr_uaci(c1, c2):
    return (c1 != c2).mean() * 100, (np.abs(c1.astype(int) - c2.astype(int)) / 255).mean() * 100


def encryption(img, keys):
    rows, ciphers = [], {}
    need = 5 * img.size + 3
    hv = adjacent_corr(img)
    rows.append({"source": "plain image", "entropy": byte_stats(img.ravel())[2],
                 "chi2": byte_stats(img.ravel())[0], "corr H": hv[0], "corr V": hv[1], "corr D": hv[2],
                 "NPCR %": float("nan"), "UACI %": float("nan")})
    for name, key in keys.items():
        if len(key) < need:
            print("skip %s: needs %d bytes, has %d" % (name, need, len(key)))
            continue
        c = encrypt(img, key)
        c2 = encrypt(img, key[3:])
        chi2, _, ent, _ = byte_stats(c.ravel())
        h, v, d = adjacent_corr(c)
        npcr, uaci = npcr_uaci(c, c2)
        rows.append({"source": name, "entropy": ent, "chi2": chi2, "corr H": h, "corr V": v,
                     "corr D": d, "NPCR %": npcr, "UACI %": uaci})
        ciphers[name] = c
    return rows, ciphers


# ---------------------------------------------------------------- output

def fmt(v):
    if isinstance(v, str):
        return v
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if math.isnan(v):
        return "-"
    if abs(v) >= 1e5:
        return "%.3g" % v
    if abs(v) >= 100:
        return "%.1f" % v
    return "%.4f" % v


def save_table(rows, path, caption, transpose=False):
    cols = list(rows[0].keys())
    with open(path + ".csv", "w") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(fmt(r.get(c, "")) for c in cols) + "\n")
    if transpose:
        rows = [dict([("metric", c)] + [(r[cols[0]], r.get(c, "")) for r in rows]) for c in cols[1:]]
        cols = list(rows[0].keys())
    with open(path + ".tex", "w") as f:
        f.write("\\begin{table}[H]\n  \\caption{%s}\n  \\centering\n  \\small\n" % caption)
        f.write("  \\begin{tabular}{@{}l%s@{}}\n    \\toprule\n" % ("c" * (len(cols) - 1)))
        f.write("    " + " & ".join(c.replace("%", "\\%").replace("_", "\\_") for c in cols) + " \\\\\n    \\midrule\n")
        for r in rows:
            f.write("    " + " & ".join(fmt(r.get(c, "")).replace("%", "\\%") for c in cols) + " \\\\\n")
        f.write("    \\bottomrule\n  \\end{tabular}\n\\end{table}\n")
    width = [max([len(c)] + [len(fmt(r.get(c, ""))) for r in rows]) for c in cols]
    print("  ".join(c.ljust(w) for c, w in zip(cols, width)))
    for r in rows:
        print("  ".join(fmt(r.get(c, "")).ljust(w) for c, w in zip(cols, width)))
    print()


def plot_statistics(datas, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.size": 9})
    fig, ax = plt.subplots(2, len(datas), figsize=(3.3 * len(datas), 5), squeeze=False)
    for k, (name, data) in enumerate(datas.items()):
        ax[0, k].bar(np.arange(256), np.bincount(data, minlength=256), width=1.0, color="#1f3b73")
        ax[0, k].set_title(name)
        ax[0, k].set_xlabel("byte value")
        ax[0, k].set_xlim(0, 255)
        x = data.astype(float) - data.mean()
        lags = np.arange(1, 65)
        ac = [np.dot(x[:-l], x[l:]) / np.dot(x, x) for l in lags]
        ax[1, k].stem(lags, ac, basefmt=" ")
        ax[1, k].axhline(2 / math.sqrt(len(x)), ls="--", lw=0.8, color="gray")
        ax[1, k].axhline(-2 / math.sqrt(len(x)), ls="--", lw=0.8, color="gray")
        ax[1, k].set_xlabel("lag")
    ax[0, 0].set_ylabel("count")
    ax[1, 0].set_ylabel("autocorrelation")
    fig.tight_layout()
    fig.savefig(path, dpi=300)


def plot_encryption(img, ciphers, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.size": 9})
    items = [("plain image", img)] + list(ciphers.items())
    fig, ax = plt.subplots(2, len(items), figsize=(2.6 * len(items), 5), squeeze=False)
    for k, (name, im) in enumerate(items):
        ax[0, k].imshow(im, cmap="gray", vmin=0, vmax=255)
        ax[0, k].set_title(name)
        ax[0, k].axis("off")
        ax[1, k].bar(np.arange(256), np.bincount(im.ravel(), minlength=256), width=1.0, color="#1f3b73")
        ax[1, k].set_xlim(0, 255)
        ax[1, k].set_xlabel("pixel value")
    fig.tight_layout()
    fig.savefig(path, dpi=300)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lsb", nargs="+", default=[], metavar="NAME=FILE", help="random byte files from suite.py")
    ap.add_argument("--bench", nargs="+", default=[], metavar="FILE", help="bench_NAME.txt files from suite.py")
    ap.add_argument("--image", help="moon | chelsea | coffee | camera | brick | path to an image file (default: synthetic)")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    print("NIST reference example check: %s\n" % ("PASS" if self_check() else "FAIL"))

    datas = {}
    if a.lsb:
        rows = []
        for item in a.lsb:
            name, path = item.split("=", 1)
            row, data = randomness(name, path)
            rows.append(row)
            datas[name] = data
        print("== randomness ==")
        save_table(rows, os.path.join(a.out, "randomness"), "Randomness test results", transpose=True)
        plot_statistics(datas, os.path.join(a.out, "statistics.pdf"))

    if a.bench:
        rows, overhead = performance(a.bench)
        print("== performance (10 MHz, loop overhead %.1f cycles) ==" % overhead)
        save_table(rows, os.path.join(a.out, "performance"), "Random number generation performance")

    if datas:
        img = test_image(a.image)
        rows, ciphers = encryption(img, datas)
        print("== image encryption (%dx%d) ==" % img.shape)
        save_table(rows, os.path.join(a.out, "encryption"), "Image encryption analysis")
        if ciphers:
            plot_encryption(img, ciphers, os.path.join(a.out, "encryption.pdf"))

    print("results saved in", a.out)


if __name__ == "__main__":
    main()
