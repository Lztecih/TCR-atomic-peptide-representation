"""
run_proteome.py
===============
Fit each model variant on the BATCAVE 20-mer group, then use it to rank a whole
proteome-scale screen for the corresponding TCR.

Every variant reduces to the same two objects -- a 20x20 substitution distance
M and a positional weight profile w -- so the ranking code is shared and the
comparison is exactly like-for-like.

Usage:  python3 run_proteome.py [screen_name]
"""



from __future__ import annotations

import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r=_os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r,"batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0,_r)
# --- end bootstrap: shared library lives one level up ---

import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import batman_atomic as ba
import experiments as ex
import proteome_screen as ps

SCREEN = sys.argv[1] if len(sys.argv) > 1 else "ctag1b_genome"
SHRINK = 0.25
RESULTS = ex.RESULTS_DIR


def atomic_matrix(theta: np.ndarray, phi: np.ndarray) -> np.ndarray:
    """Rebuild the 20x20 distance implied by the atomic feature weights."""
    return np.array([[np.sum(theta * np.abs(phi[i] - phi[j])) for j in range(20)]
                     for i in range(20)])


def fit_models(index_peptide: str, tcr: str):
    """Fit all four variants on the BATCAVE group of the right peptide length."""
    phi = ba.build_atomic_features("base8").to_numpy()
    D = ba.load_blosum100_distance()
    df = ba.load_batcave()
    L = len(index_peptide)

    sub = df[(df.index_peptide.str.len() == L) & (df.peptide.str.len() == L)]
    ok = (sub.peptide.apply(lambda s: all(c in ba.AA_IDX for c in s))
          & sub.index_peptide.apply(lambda s: all(c in ba.AA_IDX for c in s)))
    sub = sub[ok].reset_index(drop=True)
    arrays = ba.prepare(sub, phi)
    if tcr not in arrays["tcr_names"]:
        raise SystemExit(f"{tcr} not in the L={L} group: {arrays['tcr_names']}")
    ti = arrays["tcr_names"].index(tcr)
    print(f"training group: L={L}, {len(sub)} rows, "
          f"{arrays['n_tcr']} TCRs -> using weights for {tcr}", flush=True)

    out = {}

    # --- fixed BLOSUM100 -------------------------------------------------
    post = ba.fit(ba.build_model("fixed", arrays, D), n_iter=12000, seed=0)
    w = post.posterior["w"].mean(("chain", "draw")).values[ti]
    out["fixed"] = (D.copy(), w)
    print("  fitted fixed", flush=True)

    # --- learned 20x20 ---------------------------------------------------
    post = ba.fit(ba.build_model("learned", arrays, D), n_iter=12000, seed=0)
    delta = post.posterior["delta"].mean(("chain", "draw")).values
    w = post.posterior["w"].mean(("chain", "draw")).values[ti]
    M = D * (1 + delta)
    np.fill_diagonal(M, 0.0)
    out["learned"] = (M, w)
    print("  fitted learned", flush=True)

    # --- atomic ----------------------------------------------------------
    post = ba.fit(ba.build_model("atomic", arrays, D), n_iter=12000, seed=0)
    theta = post.posterior["theta"].mean(("chain", "draw")).values
    w_atomic = post.posterior["w"].mean(("chain", "draw")).values
    M_atomic = atomic_matrix(theta, phi)
    out["atomic"] = (M_atomic, w_atomic[ti])
    print("  fitted atomic", flush=True)

    # --- frozen-backbone hybrid -----------------------------------------
    post = ba.fit(
        ba.build_model("hybrid_frozen", arrays, D, hybrid_shrinkage=SHRINK,
                       frozen_theta=theta, frozen_w=w_atomic),
        n_iter=12000, seed=0)
    delta_h = post.posterior["delta"].mean(("chain", "draw")).values
    M_h = M_atomic + delta_h
    np.fill_diagonal(M_h, 0.0)
    out["hybrid_frozen"] = (M_h, w_atomic[ti])
    print("  fitted hybrid_frozen", flush=True)

    return out


def main():
    d, meta = ps.load_screen(SCREEN)
    print(f"screen: {meta['label']} | {len(d):,} peptides | "
          f"TCR {meta['tcr']} | hits(fe>2) {(d.fe > 2).sum()}", flush=True)

    models = fit_models(meta["index"], meta["tcr"])

    seqs = d.pep.tolist()
    fe = d.fe.values
    summary, tables = {}, {}
    for name, (M, w) in models.items():
        t0 = time.time()
        sc = ps.score_screen(seqs, meta["index"], M, w)
        res = ps.evaluate(sc, fe)
        summary[name] = res
        tables[name] = ps.hit_table(d, sc, meta["index"])
        np.save(os.path.join(RESULTS, f"proteome_{SCREEN}_{name}_scores.npy"), sc)
        print(f"  {name:14s} scored in {time.time()-t0:.0f}s | "
              f"best hit rank {res['best_hit_rank']:,} | "
              f"median hit rank {res['median_hit_rank']:,.0f} | "
              f"recall@100 {res['recall@100']:.2f}", flush=True)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, f"proteome_{SCREEN}_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    pd.concat({k: v for k, v in tables.items()}, names=["model"]).to_csv(
        os.path.join(RESULTS, f"proteome_{SCREEN}_hits.csv"))
    print(f"@@@ proteome({SCREEN}) FINISHED", flush=True)


if __name__ == "__main__":
    main()
