"""
harmonized_protocol.py
======================
Closes review item **R6** (protocol inconsistency).

In the original benchmark, Experiment 1 (in-distribution CV) kept the index-
peptide rows in the training set, while Experiments 2-4 dropped them
(`mutation_position > 0`). That is fine *within* an experiment -- every model
saw the same rows, so the model comparison stayed fair -- but it makes numbers
**incomparable across experiments**: the in-distribution and OOD columns of the
summary table were computed on different row populations.

This script re-runs both settings under ONE rule:

    only single-amino-acid mutant rows (mutation_position > 0) are used,
    for training AND testing, in BOTH settings.

All four models are evaluated in the same pass so every cell of the resulting
table comes from an identical protocol:

    fixed          M = D              (BLOSUM100, 0 free parameters)
    learned        M = D * (1+delta)  (BATMAN, ~380 free parameters)
    atomic         M = sum_k theta_k |dphi_k|          (8 free parameters)
    hybrid_frozen  M = atomic backbone (frozen) + shrunk residual

Usage:  python3 harmonized_protocol.py [shrinkage]
"""

from __future__ import annotations

# --- bootstrap: shared library lives one level up ---
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
# --- end bootstrap ---

import sys
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import batman_atomic as ba
import experiments as ex

SHRINK = float(sys.argv[1]) if len(sys.argv) > 1 else 0.25
N_ITER = 12000
D = ba.load_blosum100_distance()


def _fit_atomic_and_hybrid(arrays, tr, te, seed):
    """Fit atomic (stage 1), then the frozen-backbone residual (stage 2).

    Returns (atomic_per_tcr_auc, hybrid_per_tcr_auc). Stage 1 is shared, so the
    hybrid never costs a second atomic fit.
    """
    train, test = ba.subset(arrays, tr), ba.subset(arrays, te)

    post1 = ba.fit(ba.build_model("atomic", train, D), n_iter=N_ITER, seed=seed)
    theta = post1.posterior["theta"].mean(("chain", "draw")).values
    w = post1.posterior["w"].mean(("chain", "draw")).values
    atomic_auc = ba.per_tcr_auc(
        test, ba.posterior_distance("atomic", post1, test, D))

    post2 = ba.fit(
        ba.build_model("hybrid_frozen", train, D, hybrid_shrinkage=SHRINK,
                       frozen_theta=theta, frozen_w=w),
        n_iter=N_ITER, seed=seed)
    hybrid_auc = ba.per_tcr_auc(
        test, ba.posterior_distance("hybrid_frozen", post2, test, D,
                                    frozen_theta=theta, frozen_w=w))
    return atomic_auc, hybrid_auc


def _fit_plain(kind, arrays, tr, te, seed):
    per_tcr, _, _ = ex._fit_predict(kind, arrays, tr, te, D,
                                    n_iter=N_ITER, seed=seed)
    return per_tcr


def compute():
    phi = ba.build_atomic_features("base8").to_numpy()
    df = ba.load_batcave()
    rows = []

    for L, sub, arrays in ex.length_groups(df, phi):
        pos = sub.mutation_position.to_numpy(dtype=int)
        is_mutant = pos > 0                       # <-- the single, shared rule
        fold = sub.training_fold.to_numpy()
        mut_aa = ex._mutant_residue(sub)

        # ---------------- in-distribution: 5-fold CV, mutants only ----------
        for f in range(5):
            test_m = (fold == f) & is_mutant
            train_m = (fold != f) & is_mutant
            if test_m.sum() < 10 or train_m.sum() < 50:
                continue
            tr, te = np.where(train_m)[0], np.where(test_m)[0]

            for kind in ("fixed", "learned"):
                for tcr, v in _fit_plain(kind, arrays, tr, te, f).items():
                    rows.append(dict(setting="in_distribution", model=kind,
                                     L=L, fold=f, group="", tcr=tcr, auc=v))
            a_auc, h_auc = _fit_atomic_and_hybrid(arrays, tr, te, seed=f)
            for tcr, v in a_auc.items():
                rows.append(dict(setting="in_distribution", model="atomic",
                                 L=L, fold=f, group="", tcr=tcr, auc=v))
            for tcr, v in h_auc.items():
                rows.append(dict(setting="in_distribution", model="hybrid_frozen",
                                 L=L, fold=f, group="", tcr=tcr, auc=v))
            print(f"  L={L} fold={f} done", flush=True)

        # ---------------- OOD: leave-chemistry-out, mutants only ------------
        for gname, held in ex.CHEM_GROUPS.items():
            test_m = np.array([m in held for m in mut_aa]) & is_mutant
            train_m = (~np.array([m in held for m in mut_aa])) & is_mutant
            if test_m.sum() < 20 or train_m.sum() < 50:
                continue
            tr, te = np.where(train_m)[0], np.where(test_m)[0]

            for kind in ("fixed", "learned"):
                for tcr, v in _fit_plain(kind, arrays, tr, te, 0).items():
                    rows.append(dict(setting="leave_chemistry_out", model=kind,
                                     L=L, fold=-1, group=gname, tcr=tcr, auc=v))
            a_auc, h_auc = _fit_atomic_and_hybrid(arrays, tr, te, seed=0)
            for tcr, v in a_auc.items():
                rows.append(dict(setting="leave_chemistry_out", model="atomic",
                                 L=L, fold=-1, group=gname, tcr=tcr, auc=v))
            for tcr, v in h_auc.items():
                rows.append(dict(setting="leave_chemistry_out",
                                 model="hybrid_frozen",
                                 L=L, fold=-1, group=gname, tcr=tcr, auc=v))
            print(f"  L={L} {gname} done", flush=True)

    return pd.DataFrame(rows)


def main():
    t0 = time.time()
    r = ex.cached("exp8_harmonized_protocol.csv", compute)
    print(f"@@@ harmonized_protocol FINISHED {len(r)} rows "
          f"in {(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
