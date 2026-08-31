"""
leave_one_epitope_out.py
========================
The properly-powered version of the question raised in Results section 3.10.

The Malone external validation found that the in-distribution ordering reverses
-- the learned 20x20 matrix falls behind both representations introduced here.
But all 20 of its TCRs recognise ONE epitope, so the effective sample size was
about 1.3 and the atomic-vs-learned contrast could not be resolved.

This script asks the same question with many independent epitopes instead of
one. For each epitope in a length group, hold out that epitope **and all of its
TCRs**, train on the remaining epitopes, and predict the held-out epitope. One
held-out epitope contributes exactly one observation, so the paired tests run
over epitopes -- the unit that actually carries the evidence.

Because the held-out TCRs are unseen, ``pan_tcr=True`` is used throughout: a
single shared positional-weight profile, exactly as in Experiment 4 and in the
Malone validation.

What this is and is not
-----------------------
It IS   : a test of generalisation to an unseen epitope, with real replication
          (n = number of held-out epitopes rather than n = 1).
It is NOT: external data. Everything still comes from BATCAVE, with its assay
          conventions and curation choices. Malone remains the only genuinely
          independent test set; this trades that independence for statistical
          power, so the two are complementary rather than interchangeable.

Output: ``results/leave_one_epitope_out.csv``

Usage:  python3 leave_one_epitope_out.py
"""

from __future__ import annotations

# --- bootstrap: shared library lives one level up ---
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
SHRINK = 0.25
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
            print(f"L={L}: only one epitope -- skipped")
            continue

        pos = sub.mutation_position.to_numpy(dtype=int)
        idx_pep = sub.index_peptide.to_numpy()

        for held in epitopes:
            test_m = (idx_pep == held) & (pos > 0)
            train_m = (idx_pep != held) & (pos > 0)
            if test_m.sum() < MIN_TEST_ROWS or train_m.sum() < MIN_TRAIN_ROWS:
                continue
            tr, te = np.where(train_m)[0], np.where(test_m)[0]
            n_tcr_held = sub.loc[test_m, "tcr"].nunique()
            train, test = ba.subset(arrays, tr), ba.subset(arrays, te)

            t0 = time.time()
            per_model = {}
            for kind in ("fixed", "learned", "atomic"):
                post = ba.fit(ba.build_model(kind, train, D, pan_tcr=True),
                              n_iter=N_ITER, seed=0)
                d = ba.posterior_distance(kind, post, test, D, pan_tcr=True)
                per_model[kind] = ba.per_tcr_auc(test, d)
                if kind == "atomic":
                    theta = post.posterior["theta"].mean(("chain", "draw")).values
                    w = post.posterior["w"].mean(("chain", "draw")).values

            # hybrid_frozen indexes frozen_w per training TCR, so broadcast the
            # single pan-TCR profile across them
            w_tiled = np.tile(w, (train["n_tcr"], 1))
            post2 = ba.fit(
                ba.build_model("hybrid_frozen", train, D,
                               hybrid_shrinkage=SHRINK,
                               frozen_theta=theta, frozen_w=w_tiled),
                n_iter=N_ITER, seed=0)
            d2 = ba.posterior_distance("hybrid_frozen", post2, test, D,
                                       pan_tcr=True, frozen_theta=theta,
                                       frozen_w=w)
            per_model["hybrid_frozen"] = ba.per_tcr_auc(test, d2)

            for kind, aucs in per_model.items():
                for tcr, auc in aucs.items():
                    rows.append(dict(L=L, held_out_epitope=held,
                                     n_tcr=n_tcr_held, model=kind,
                                     tcr=tcr, auc=auc))
            mean_by = {k: np.mean(list(v.values())) for k, v in per_model.items()}
            print(f"  L={L} held out {held:22s} ({n_tcr_held:2d} TCR, "
                  f"{test_m.sum():4d} rows) "
                  + " ".join(f"{k}={v:.3f}" for k, v in mean_by.items())
                  + f"  [{time.time()-t0:.0f}s]", flush=True)

    return pd.DataFrame(rows)


def main():
    t0 = time.time()
    r = ex.cached("leave_one_epitope_out.csv", compute)
    print(f"\n@@@ leave_one_epitope_out FINISHED {len(r)} rows in "
          f"{(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
