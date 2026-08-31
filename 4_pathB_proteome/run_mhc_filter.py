"""
run_mhc_filter.py
=================
Does an MHC-II presentation score separate the true genome-wide targets from the
sequence-similar decoys that the TCR model cannot distinguish?

Three tests per screen:
  1. Can the MHC surrogate ALONE rank the true hits? (AUC on the top TCR
     candidates, where hits and decoys are all sequence-similar).
  2. Does rank-fusing TCR distance with MHC score beat TCR distance alone
     (precision@k, median hit rank)?
  3. Position decomposition -- do decoys differ from the index more at
     MHC-sensitive core positions or at TCR-contact positions?

Usage:  python3 run_mhc_filter.py
"""

from __future__ import annotations

import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r=_os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r,"batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0,_r)


import json
import os
import warnings

warnings.filterwarnings("ignore")

import numpy as np
from scipy.stats import rankdata
from sklearn.metrics import roc_auc_score

import batman_atomic as ba
import proteome_screen as ps
import mhc_filter as mf


def analyse(screen: str, threshold: float, topN: int = 2000):
    d, meta = ps.load_screen(screen)
    index = meta["index"]
    allele = mf.SCREEN_ALLELE[screen]
    pssm, core = mf.build_core_pssm(allele)

    tcr = np.load(os.path.join(ba.ROOT, "results",
                               f"proteome_{screen}_hybrid_frozen_scores.npy"))
    finite = np.isfinite(tcr)
    hit = (d.fe.values > threshold) & finite

    # restrict to the top-N most TCR-plausible constructs: here hits and decoys
    # are all sequence-similar, so this is where an MHC filter must earn its keep
    order = np.argsort(np.where(finite, tcr, np.inf), kind="stable")
    cand = order[:topN]
    cand = cand[finite[cand]]

    wins = [mf.best_window(d.pep.iloc[i], index) for i in cand]
    mhc = np.array([mf.mhc_el_score(w, pssm, core) if w else np.nan for w in wins])
    keep = np.isfinite(mhc)
    cand, mhc = cand[keep], mhc[keep]
    y = hit[cand].astype(int)
    tcr_c = tcr[cand]

    out = {"screen": screen, "allele": allele, "threshold": threshold,
           "n_candidates": int(len(cand)), "n_hits_in_candidates": int(y.sum())}

    if y.sum() >= 3 and y.sum() < len(y):
        # (1) MHC alone  (higher EL score = more likely presented = better)
        out["auc_mhc_alone"] = float(roc_auc_score(y, mhc))
        # (2) TCR alone   (smaller distance = better -> negate)
        out["auc_tcr_alone"] = float(roc_auc_score(y, -tcr_c))
        # (3) rank fusion: average of the two rank positions
        r_tcr = rankdata(tcr_c)            # small distance -> small rank -> good
        r_mhc = rankdata(-mhc)             # high EL -> small rank -> good
        fused = r_tcr + r_mhc
        out["auc_fused"] = float(roc_auc_score(y, -fused))
        # precision@k for each ranking
        for k in (5, 10, 20):
            for tag, sc in [("tcr", tcr_c), ("mhc", -mhc), ("fused", fused)]:
                topk = np.argsort(sc)[:k]
                out[f"precision@{k}_{tag}"] = float(y[topk].mean())

    # (4) position decomposition on the hits vs the top decoys
    #     how sensitive is each core position (std of NetMHCIIpan EL across aa)?
    sens = np.nanstd(pssm, axis=1)                     # per index position
    core_sens = {int(p): float(sens[p]) for p in core}
    out["core_positions"] = list(core_sens.keys())
    out["core_mhc_sensitivity"] = core_sens
    return out


def main():
    thresholds = {"ctag1b_genome": 5, "hiv_genome": 20, "hiv_virome": 5}
    results = {}
    for screen, thr in thresholds.items():
        try:
            results[screen] = analyse(screen, thr)
            r = results[screen]
            line = (f"{screen:15s} n={r['n_candidates']:5d} hits={r['n_hits_in_candidates']:3d}")
            if "auc_mhc_alone" in r:
                line += (f" | AUC  tcr {r['auc_tcr_alone']:.3f}"
                         f"  mhc {r['auc_mhc_alone']:.3f}"
                         f"  fused {r['auc_fused']:.3f}")
            print(line, flush=True)
        except Exception as e:
            print(f"{screen}: ERROR {e}", flush=True)
    with open(os.path.join(ba.ROOT, "results", "mhc_filter_summary.json"), "w") as fh:
        json.dump(results, fh, indent=2)
    print("@@@ mhc_filter FINISHED", flush=True)


if __name__ == "__main__":
    main()
