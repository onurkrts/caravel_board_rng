#!/usr/bin/env python3
"""Run the official NIST SP 800-22 test suite (sts-2.1.2) on collected data.

    python3 host/nist.py setup                                # download and build into ~/nist-sts
    python3 host/nist.py run data/single_nist.bin --name single
    python3 host/nist.py table results/nist_single.txt results/nist_double.txt results/nist_software.txt

Each run uses 100 sequences of 1,000,000 bits (12.5 MB) unless --streams is given.
"""
import argparse
import math
import os
import re
import shutil
import subprocess
import sys

STS_REPO = "https://github.com/terrillmoore/NIST-Statistical-Test-Suite.git"
DEFAULT_DIR = os.path.expanduser("~/nist-sts")
SEQ_BITS = 1000000
SUBDIRS = ["Frequency", "BlockFrequency", "Runs", "LongestRun", "Rank", "FFT",
           "NonOverlappingTemplate", "OverlappingTemplate", "Universal", "LinearComplexity",
           "Serial", "ApproximateEntropy", "CumulativeSums", "RandomExcursions",
           "RandomExcursionsVariant"]
TEST_ORDER = ["Frequency", "BlockFrequency", "CumulativeSums", "Runs", "LongestRun", "Rank", "FFT",
              "NonOverlappingTemplate", "OverlappingTemplate", "Universal", "ApproximateEntropy",
              "RandomExcursions", "RandomExcursionsVariant", "Serial", "LinearComplexity"]
ROW_RE = re.compile(r"^\s*(?:\d+\s+){10}(\S+)\s*\*?\s+(\d+)/(\d+)\s*\*?\s+(\w+)")


def find_sts(path):
    for root, _, files in os.walk(path):
        if "assess.c" in files and os.path.basename(root) == "src":
            return os.path.dirname(root)
    return None


def cmd_setup(a):
    if not find_sts(a.dir):
        if shutil.which("git") is None:
            sys.exit("git is required: sudo apt install git")
        subprocess.check_call(["git", "clone", "--depth", "1", STS_REPO, a.dir])
    sts = find_sts(a.dir)
    os.makedirs(os.path.join(sts, "obj"), exist_ok=True)
    for sub in SUBDIRS:
        os.makedirs(os.path.join(sts, "experiments", "AlgorithmTesting", sub), exist_ok=True)
    subprocess.check_call(["make", "-s"], cwd=sts)
    print("NIST STS ready:", os.path.join(sts, "assess"))


def cmd_run(a):
    sts = find_sts(a.dir)
    if not sts or not os.path.exists(os.path.join(sts, "assess")):
        sys.exit("NIST STS not found, run: python3 host/nist.py setup")
    path = os.path.abspath(a.data)
    have = os.path.getsize(path) * 8 // SEQ_BITS
    if have < a.streams:
        sys.exit("%s has %d x 1 Mbit, %d needed (collect %d bytes)"
                 % (a.data, have, a.streams, a.streams * SEQ_BITS // 8))
    answers = "0\n%s\n1\n0\n%d\n1\n" % (path, a.streams)
    print("running %d sequences on %s (about %d min) ..." % (a.streams, a.data, max(1, a.streams * 4 // 60)))
    final = os.path.join(sts, "experiments", "AlgorithmTesting", "finalAnalysisReport.txt")
    if os.path.exists(final):
        os.remove(final)
    proc = subprocess.run(["./assess", str(SEQ_BITS)], cwd=sts, input=answers.encode(),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if not os.path.exists(final) or not parse(final):
        sys.exit("assess failed:\n" + proc.stdout.decode("ascii", "replace")[-1500:])
    os.makedirs(a.out, exist_ok=True)
    report = os.path.join(a.out, "nist_%s.txt" % a.name)
    shutil.copy(final, report)
    print("report:", report)
    summarize([report], os.path.join(a.out, "nist_%s" % a.name))


def parse(report):
    tests = {}
    for line in open(report, errors="replace"):
        m = ROW_RE.match(line)
        if not m:
            continue
        pval, passed, total, name = m.groups()
        p = float(pval) if pval != "----" else float("nan")
        tests.setdefault(name, []).append((p, int(passed), int(total)))
    return tests


def min_pass(total, alpha=0.01):
    p = 1 - alpha
    return int(math.floor(total * (p - 3 * math.sqrt(p * (1 - p) / total))))


def judge(rows):
    ok = 0
    for p, passed, total in rows:
        uniform = math.isnan(p) or total < 55 or p >= 0.0001
        if total and passed >= min_pass(total) and uniform:
            ok += 1
    worst = min(rows, key=lambda r: r[1] / r[2] if r[2] else 1)
    pvals = [r[0] for r in rows if not math.isnan(r[0])]
    return {"instances": len(rows), "passed": ok, "worst": "%d/%d" % (worst[1], worst[2]),
            "min p": min(pvals) if pvals else float("nan")}


def summarize(reports, prefix):
    names = [os.path.splitext(os.path.basename(r))[0].replace("nist_", "") for r in reports]
    parsed = [parse(r) for r in reports]
    lines_csv = ["test," + ",".join("%s result,%s worst proportion,%s min uniformity p" % (n, n, n) for n in names)]
    lines_tex = []
    total_ok = [0] * len(reports)
    width = max(len(t) for t in TEST_ORDER)
    print("\n%s  %s" % ("test".ljust(width), "  ".join(n.ljust(24) for n in names)))
    for test in TEST_ORDER:
        cells_csv, cells_txt, cells_tex = [], [], []
        for k, tests in enumerate(parsed):
            if test not in tests:
                cells_csv.append("-,-,-")
                cells_txt.append("-".ljust(24))
                cells_tex.append("-")
                continue
            j = judge(tests[test])
            verdict = "PASS" if j["passed"] == j["instances"] else "FAIL"
            if verdict == "PASS":
                total_ok[k] += 1
            label = verdict if j["instances"] == 1 else "%s %d/%d" % (verdict, j["passed"], j["instances"])
            pstr = "-" if math.isnan(j["min p"]) else "%.4f" % j["min p"]
            cells_csv.append("%s,%s,%s" % (label, j["worst"], pstr))
            cells_txt.append(("%s (%s)" % (label, j["worst"])).ljust(24))
            cells_tex.append("%s (%s)" % (label, j["worst"]))
        lines_csv.append(test + "," + ",".join(cells_csv))
        lines_tex.append("    %s & %s \\\\" % (test, " & ".join(cells_tex)))
        print("%s  %s" % (test.ljust(width), "  ".join(cells_txt)))
    print("%s  %s" % ("passed tests".ljust(width), "  ".join(("%d/15" % t).ljust(24) for t in total_ok)))

    with open(prefix + ".csv", "w") as f:
        f.write("\n".join(lines_csv) + "\n")
    with open(prefix + ".tex", "w") as f:
        f.write("\\begin{table}[H]\n  \\caption{NIST SP 800-22 test results (result and worst proportion)}\n")
        f.write("  \\centering\n  \\small\n  \\begin{tabular}{@{}l%s@{}}\n    \\toprule\n" % ("c" * len(names)))
        f.write("    Test & %s \\\\\n    \\midrule\n" % " & ".join(names))
        f.write("\n".join(lines_tex) + "\n")
        f.write("    \\midrule\n    Passed & %s \\\\\n" % " & ".join("%d/15" % t for t in total_ok))
        f.write("    \\bottomrule\n  \\end{tabular}\n\\end{table}\n")
    print("\nsaved %s.csv and %s.tex" % (prefix, prefix))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd")
    s = sp.add_parser("setup")
    s.add_argument("--dir", default=DEFAULT_DIR)
    r = sp.add_parser("run")
    r.add_argument("data")
    r.add_argument("--name", required=True)
    r.add_argument("--streams", type=int, default=100)
    r.add_argument("--dir", default=DEFAULT_DIR)
    r.add_argument("--out", default="results")
    t = sp.add_parser("table")
    t.add_argument("reports", nargs="+")
    t.add_argument("--out", default="results/nist")
    a = ap.parse_args()
    if a.cmd == "setup":
        cmd_setup(a)
    elif a.cmd == "run":
        cmd_run(a)
    elif a.cmd == "table":
        summarize(a.reports, a.out)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
