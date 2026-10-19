"""Collect the arm results into the comparison tables.

Aggregation order throughout: the three pairwise AUCs -> folds -> receptors.
Comparisons are paired by receptor, two-sided Wilcoxon signed-rank, with a
20,000-sample bootstrap interval on the mean difference.

Two things this module insists on, because both can silently decide the answer:

  * The unit of analysis. With a fixed substitution matrix the predicted
    distance contains no receptor term, so receptors sharing an index peptide
    are scored by an identical vector. A paired test over all of them is
    pseudo-replicated. The default panel is therefore one receptor per index
    peptide.

  * The reference arm. Every route must be compared against
    "positional weights with no amino-acid information at all" (matrix:hamming),
    not against chance. That rung is what tells you whether a representation
    adds anything over simply knowing WHICH position changed.
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data as D      # noqa: E402
import metric as MT   # noqa: E402

LABEL = {
    "matrix:hamming":    "positional weights only (no aa identity)",
    "matrix:blosum100":  "+ BLOSUM100 substitution matrix",
    "batman:blosum100":  "+ learned matrix corrections (BATMAN)",
    "matrix:peptideclm": "ROUTE A: PeptideCLM-2 aa matrix",
    "feature:desc":      "ROUTE C ablation: 24 chemical descriptors",
    "feature:plm":       "ROUTE C ablation: 50 language-model features",
    "feature:full":      "ROUTE C: 50 language-model + 24 chemical",
    "peptide":           "ROUTE B: learned metric on whole-peptide embedding",
}
ORDER = list(LABEL)


def collect(protocol="within", lengths="L9", panel="one_per_index"):
    want_L = int(lengths[1:]) if lengths and lengths.startswith("L") else None
    out = {}
    for f in sorted(glob.glob(os.path.join(D.RESULTS, "*.csv"))):
        b = os.path.basename(f)[:-4]
        if panel not in b:
            continue
        r = pd.read_csv(f)
        if "auc" not in r.columns or not len(r):
            continue
        # Filter the protocol and the length on the COLUMNS run.py writes, never
        # on the filename: "loo" is a substring of "gloo" and "L9" of "L910", so
        # a filename test files a gloo run under loo -- and since sorted() puts
        # gloo first and both key the same arm, it corrupts exactly the arms that
        # have no loo run of their own, which is the hardest case to notice.
        if "protocol" in r.columns and str(r.protocol.iloc[0]) != protocol:
            continue
        if want_L is not None and "L" in r.columns and set(r.L) != {want_L}:
            continue
        out[r.arm.iloc[0]] = r
    return out


def table(runs: dict[str, pd.DataFrame], base="matrix:hamming") -> pd.DataFrame:
    per = {a: MT.per_receptor(r) for a, r in runs.items()}
    rows = []
    for a in [x for x in ORDER if x in per] + [x for x in per if x not in ORDER]:
        s = per[a]
        rec = dict(arm=a, what=LABEL.get(a, a), mean_auc=s.mean(), sd=s.std(),
                   n_receptors=len(s))
        for k in ("WS", "NS", "NW"):
            rec[k] = runs[a].groupby("tcr")[k].mean().mean()
        if base in per and a != base:
            rec.update({f"vs_base_{k}": v for k, v in
                        MT.paired(s, per[base]).items()
                        if k in ("delta", "ci_low", "ci_high", "p", "wins", "n")})
        rows.append(rec)
    return pd.DataFrame(rows)


def main():
    protocol = sys.argv[1] if len(sys.argv) > 1 else "within"
    lengths = sys.argv[2] if len(sys.argv) > 2 else "L9"
    runs = collect(protocol, lengths)
    if not runs:
        print("no results yet"); return
    t = table(runs)
    pd.set_option("display.width", 240)
    cols = ["what", "mean_auc", "sd", "n_receptors", "WS", "NS", "NW"]
    print(f"=== {protocol} | {lengths} | {len(runs)} arms ===")
    print(t[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    vs = [c for c in t.columns if c.startswith("vs_base_")]
    if vs:
        print("\n=== paired vs 'positional weights only' (same receptors) ===")
        # Rename by MAPPING, never positionally. MT.paired returns its keys in
        # the order n, delta, ci_low, ci_high, p, wins, so a positional
        # assignment of ["delta", "ci_low", "ci_high", "p", "wins", "n"] shifts
        # every statistic by one and prints the CI upper bound as the p-value.
        sub = (t[t.vs_base_delta.notna()][["what"] + vs]
               .rename(columns={c: c[len("vs_base_"):] for c in vs}))
        order = ["what"] + [k for k in ("n", "delta", "ci_low", "ci_high",
                                        "p", "wins") if k in sub.columns]
        print(sub[order].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    t.to_csv(os.path.join(D.RESULTS, f"table_{protocol}_{lengths}.csv"), index=False)
    print(f"\n[written] results/table_{protocol}_{lengths}.csv")


if __name__ == "__main__":
    main()
