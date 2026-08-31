"""
null_baselines.py
=================
Closes the provenance gap in Path B.

``PATH_B_FINDINGS.md`` reports that a plain **Hamming distance** retrieves the
validated TCR targets as well as any fitted model -- the central negative
result of the proteome-scale analysis. That comparison was never written to
disk by any script, and the saved ``proteome_*_summary.json`` files use the
default hit threshold (fe > 2) rather than the per-screen thresholds quoted in
the text. This script regenerates the whole comparison reproducibly:

  * two learning-free nulls
        hamming          M[a,b] = 1 for a != b, uniform positional weights
        blosum_uniform   M[a,b] = D[a,b],       uniform positional weights
  * the four fitted models, re-evaluated from their cached score vectors
  * every model scored at BOTH the default threshold (fe > 2) and the
    per-screen threshold used in the text, so the two conventions can never be
    silently mixed again

Output: ``results/proteome_null_baselines.csv`` (one row per screen x model x
threshold) and ``results/proteome_null_summary.json``.

Usage:  python3 null_baselines.py
"""

from __future__ import annotations

# --- bootstrap: shared library lives one level up ---
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
_pb = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                    "4_pathB_proteome")
if _pb not in _sys.path:
    _sys.path.insert(0, _pb)
# --- end bootstrap ---

import json
import os
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import batman_atomic as ba
import proteome_screen as ps

RESULTS = os.path.join(ba.ROOT, "results")

#: hit threshold used in the text, chosen per screen to match its dynamic range
TEXT_THRESHOLD = {"ctag1b_genome": 5.0, "hiv_genome": 20.0, "hiv_virome": 5.0}

FITTED = ["fixed", "learned", "atomic", "hybrid_frozen"]


def null_scores(seqs, index_peptide, kind):
    """Score a screen with a learning-free baseline."""
    L = len(index_peptide)
    if kind == "hamming":
        M = 1.0 - np.eye(20)
    elif kind == "blosum_uniform":
        M = ba.load_blosum100_distance().copy()
        np.fill_diagonal(M, 0.0)
    else:
        raise ValueError(kind)
    w = np.ones(L)                       # every position counts the same
    return ps.score_screen(seqs, index_peptide, M, w)


def main():
    rows, summary = [], {}

    for screen in ("ctag1b_genome", "hiv_genome", "hiv_virome"):
        d, meta = ps.load_screen(screen)
        seqs, fe = d.pep.tolist(), d.fe.values
        print(f"\n=== {screen}: {len(d):,} peptides, index {meta['index']} ===",
              flush=True)

        scores = {}
        # learning-free nulls -- computed here
        for kind in ("hamming", "blosum_uniform"):
            scores[kind] = null_scores(seqs, meta["index"], kind)
            print(f"  scored {kind}", flush=True)
        # fitted models -- reuse the cached score vectors
        for name in FITTED:
            p = os.path.join(RESULTS, f"proteome_{screen}_{name}_scores.npy")
            if os.path.exists(p):
                scores[name] = np.load(p)
            else:
                print(f"  [skip] no cached scores for {name}")

        for thr_name, thr in (("default", 2.0),
                              ("text", TEXT_THRESHOLD[screen])):
            n_hits = int((fe > thr).sum())
            for name, sc in scores.items():
                r = ps.evaluate(sc, fe, threshold=thr)
                rows.append(dict(
                    screen=screen, model=name, threshold_name=thr_name,
                    threshold=thr, n_scored=r["n_scored"], n_hits=r["n_hits"],
                    best_hit_rank=r["best_hit_rank"],
                    median_hit_rank=r["median_hit_rank"],
                    **{f"recall@{k}": r[f"recall@{k}"] for k in (10, 100, 1000)},
                    **{f"precision@{k}": r[f"precision@{k}"] for k in (10, 100, 1000)},
                    enrichment_top1pct=r["enrichment@top1%"]))
                summary.setdefault(screen, {}).setdefault(thr_name, {})[name] = r
            print(f"  threshold {thr_name} (fe>{thr}): {n_hits} hits", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RESULTS, "proteome_null_baselines.csv"), index=False)
    with open(os.path.join(RESULTS, "proteome_null_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    # ---- the headline comparison, printed so the log carries it too --------
    print("\n### median hit rank (lower = better), text thresholds\n")
    piv = (out[out.threshold_name == "text"]
           .pivot(index="screen", columns="model", values="median_hit_rank"))
    cols = [c for c in ["hamming", "blosum_uniform", *FITTED] if c in piv.columns]
    print(piv[cols].to_string())
    print("\n### recall@100, text thresholds\n")
    piv2 = (out[out.threshold_name == "text"]
            .pivot(index="screen", columns="model", values="recall@100"))
    print(piv2[cols].round(3).to_string())
    print("\n@@@ null_baselines FINISHED", flush=True)


if __name__ == "__main__":
    main()
