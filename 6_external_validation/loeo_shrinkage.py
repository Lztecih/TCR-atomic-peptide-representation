"""
loeo_shrinkage.py
=================
Tests the mechanism proposed for the §3.11 reversal.

Section 3.11 found that the frozen hybrid, which beats the atomic model
in-distribution by *d* = +0.93, is significantly *worse* than it on a held-out
epitope (*d* = -0.69). The explanation offered was that the residual delta is
fitted to how substitutions behave in the training epitopes' positional
contexts, and those corrections are wrong in a new context.

That explanation makes a sharp, falsifiable prediction:

    if the damage comes from delta carrying context-specific corrections,
    then shrinking delta harder (smaller sigma) should reduce the damage,
    and in the limit sigma -> 0 the hybrid must converge to the atomic model.

If instead the hybrid stays worse at every sigma, the explanation is wrong and
something else is going on.

Stage 1 (the atomic fit) is shared across all sigma values, so sweeping four
sigmas costs little more than the original run.

Output: ``results/loeo_shrinkage.csv``

Usage:  python3 loeo_shrinkage.py
"""

from __future__ import annotations

# --- bootstrap ---
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
# --- end bootstrap ---

import time
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import batman_atomic as ba
import experiments as ex

RES = _os.path.join(ba.ROOT, "results")
N_ITER = 12000
SIGMAS = (0.02, 0.05, 0.10, 0.25)
MIN_TEST_ROWS = 20
MIN_TRAIN_ROWS = 200


def compute():
    phi = ba.build_atomic_features("base8").to_numpy()
    D = ba.load_blosum100_distance()
    df = ba.load_batcave()
    rows = []

    for L, sub, arrays in ex.length_groups(df, phi):
        epitopes = sorted(sub.index_peptide.unique())
        if len(epitopes) < 2:
            continue
        pos = sub.mutation_position.to_numpy(dtype=int)
        idx_pep = sub.index_peptide.to_numpy()

        for held in epitopes:
            test_m = (idx_pep == held) & (pos > 0)
            train_m = (idx_pep != held) & (pos > 0)
            if test_m.sum() < MIN_TEST_ROWS or train_m.sum() < MIN_TRAIN_ROWS:
                continue
            tr, te = np.where(train_m)[0], np.where(test_m)[0]
            train, test = ba.subset(arrays, tr), ba.subset(arrays, te)
            n_tcr = sub.loc[test_m, "tcr"].nunique()
            t0 = time.time()

            # ---- stage 1, shared by every sigma --------------------------
            post1 = ba.fit(ba.build_model("atomic", train, D, pan_tcr=True),
                           n_iter=N_ITER, seed=0)
            theta = post1.posterior["theta"].mean(("chain", "draw")).values
            w = post1.posterior["w"].mean(("chain", "draw")).values
            a_auc = ba.per_tcr_auc(
                test, ba.posterior_distance("atomic", post1, test, D,
                                            pan_tcr=True))
            for tcr, auc in a_auc.items():
                rows.append(dict(L=L, held_out_epitope=held, n_tcr=n_tcr,
                                 sigma=np.nan, model="atomic",
                                 tcr=tcr, auc=auc))

            # ---- stage 2, once per sigma ---------------------------------
            w_tiled = np.tile(w, (train["n_tcr"], 1))
            means = {}
            for sg in SIGMAS:
                post2 = ba.fit(
                    ba.build_model("hybrid_frozen", train, D,
                                   hybrid_shrinkage=sg,
                                   frozen_theta=theta, frozen_w=w_tiled),
                    n_iter=N_ITER, seed=0)
                d2 = ba.posterior_distance("hybrid_frozen", post2, test, D,
                                           pan_tcr=True, frozen_theta=theta,
                                           frozen_w=w)
                h_auc = ba.per_tcr_auc(test, d2)
                for tcr, auc in h_auc.items():
                    rows.append(dict(L=L, held_out_epitope=held, n_tcr=n_tcr,
                                     sigma=sg, model="hybrid_frozen",
                                     tcr=tcr, auc=auc))
                means[sg] = np.mean(list(h_auc.values()))

            print(f"  L={L} {held:22s} atomic={np.mean(list(a_auc.values())):.3f}  "
                  + " ".join(f"s{sg}={v:.3f}" for sg, v in means.items())
                  + f"  [{time.time()-t0:.0f}s]", flush=True)

    return pd.DataFrame(rows)


def main():
    t0 = time.time()
    r = ex.cached("loeo_shrinkage.csv", compute)
    print(f"\n@@@ loeo_shrinkage FINISHED {len(r)} rows in "
          f"{(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
