"""
hybrid_full.py
==============
Full-scale evaluation of the frozen-backbone hybrid.

Stage 1 fits the atomic model and keeps BOTH theta and the positional weights
w at their posterior means. Stage 2 learns only a shrunk per-cell residual on
top of that frozen backbone.

Three earlier variants failed, and each failure narrowed the design:

  1. multiplicative  base * (1 + delta)  -- theta and delta are multiplicatively
     non-identifiable; ADVI diverged at every learning rate tried.
  2. additive, joint fit                 -- the residual cannibalises the atomic
     signal, theta underfits, and OOD accuracy drops *below* atomic-only
     (0.7797 vs 0.7940, p < 1e-6).
  3. additive, theta frozen only         -- stage 2 still re-learned w, so the
     weights no longer matched the frozen backbone and OOD still fell
     (0.8199 vs 0.8494 on held-out aromatics).

Freezing theta AND w is the first variant whose OOD guarantee actually holds:
when every test row mutates to a residue absent from training, the residual is
~0 on those cells, the distance reduces to the atomic model's distance, and
AUC -- being rank-based -- is identical to atomic by construction.

Usage:  python3 hybrid_full.py [shrinkage]
"""



from __future__ import annotations

import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r=_os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r,"batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0,_r)
# --- end bootstrap: shared library lives one level up ---

import sys
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import batman_atomic as ba
import experiments as ex

SHRINK = float(sys.argv[1]) if len(sys.argv) > 1 else 0.25
TAG = f"s{SHRINK}".replace(".", "")


def _staged(arrays, tr, te, seed=0, n_iter=12000):
    """Fit stage 1 (atomic) + stage 2 (frozen-backbone residual)."""
    train = ba.subset(arrays, tr)
    test = ba.subset(arrays, te)

    post1 = ba.fit(ba.build_model("atomic", train, D), n_iter=n_iter, seed=seed)
    theta = post1.posterior["theta"].mean(("chain", "draw")).values
    w = post1.posterior["w"].mean(("chain", "draw")).values
    atomic_auc = ba.per_tcr_auc(
        test, ba.posterior_distance("atomic", post1, test, D))

    # Freeze BOTH theta and w, so an unseen substitution reduces the distance
    # to the atomic model's distance exactly and AUC cannot drop below it.
    post2 = ba.fit(
        ba.build_model("hybrid_frozen", train, D, hybrid_shrinkage=SHRINK,
                       frozen_theta=theta, frozen_w=w),
        n_iter=n_iter, seed=seed)
    staged_auc = ba.per_tcr_auc(
        test, ba.posterior_distance("hybrid_frozen", post2, test, D,
                                    frozen_theta=theta, frozen_w=w))
    return atomic_auc, staged_auc


def main():
    phi = ba.build_atomic_features("base8").to_numpy()
    df = ba.load_batcave()

    def compute():
        rows = []
        for L, sub, arrays in ex.length_groups(df, phi):
            # ---- in-distribution: 5-fold CV ----
            fold = sub.training_fold.to_numpy()
            is_index = sub.mutation_position.to_numpy() == 0
            for f in range(5):
                test_m = fold == f
                if test_m.sum() < 10:
                    continue
                tr = np.where(~test_m | is_index)[0]
                te = np.where(test_m)[0]
                a_auc, s_auc = _staged(arrays, tr, te, seed=f)
                for tcr, v in a_auc.items():
                    rows.append(dict(setting="in_distribution", model="atomic",
                                     L=L, fold=f, tcr=tcr, auc=v))
                for tcr, v in s_auc.items():
                    rows.append(dict(setting="in_distribution", model="hybrid_frozen",
                                     L=L, fold=f, tcr=tcr, auc=v))
            # ---- OOD: leave-chemistry-out ----
            mut_aa = ex._mutant_residue(sub)
            pos = sub.mutation_position.to_numpy(dtype=int)
            for gname, held in ex.CHEM_GROUPS.items():
                test_m = np.array([m in held for m in mut_aa])
                train_m = (~test_m) & (pos > 0)
                if test_m.sum() < 20 or train_m.sum() < 50:
                    continue
                tr, te = np.where(train_m)[0], np.where(test_m)[0]
                a_auc, s_auc = _staged(arrays, tr, te, seed=0)
                for tcr, v in a_auc.items():
                    rows.append(dict(setting="leave_chemistry_out", model="atomic",
                                     L=L, group=gname, tcr=tcr, auc=v))
                for tcr, v in s_auc.items():
                    rows.append(dict(setting="leave_chemistry_out",
                                     model="hybrid_frozen",
                                     L=L, group=gname, tcr=tcr, auc=v))
            print(f"  L={L} done", flush=True)
        return pd.DataFrame(rows)

    t0 = time.time()
    r = ex.cached(f"hybrid_frozen_{TAG}.csv", compute)
    print(f"@@@ hybrid_full({SHRINK}) FINISHED {len(r)} rows "
          f"in {(time.time()-t0)/60:.1f} min", flush=True)


D = ba.load_blosum100_distance()

if __name__ == "__main__":
    main()
