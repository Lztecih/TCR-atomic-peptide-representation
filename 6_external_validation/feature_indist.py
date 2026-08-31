"""
feature_indist.py
=================
Completes the picture for the feature-tied residual.

Leave-one-epitope-out showed the feature-tied residual removes the transfer
penalty that the per-cell residual suffers. The remaining question is what it
costs in-distribution: a residual that transfers perfectly but adds nothing on
the epitopes it was trained on would be a hollow win.

This runs the same 5-fold in-distribution protocol as Experiment 8, per-TCR
weights and all, for atomic / hybrid_frozen / hybrid_feature so the two axes
can be plotted against each other.

Output: ``results/feature_indist.csv``
Usage:  python3 feature_indist.py
"""
from __future__ import annotations
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
import time, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import batman_atomic as ba, experiments as ex

N_ITER = 12000

def compute():
    phi = ba.build_atomic_features("base8").to_numpy()
    D = ba.load_blosum100_distance(); df = ba.load_batcave()
    rows = []
    for L, sub, arrays in ex.length_groups(df, phi):
        pos = sub.mutation_position.to_numpy(int)
        fold = sub.training_fold.to_numpy()
        for f in range(5):
            te_m = (fold == f) & (pos > 0); tr_m = (fold != f) & (pos > 0)
            if te_m.sum() < 10 or tr_m.sum() < 50:
                continue
            tr, te = np.where(tr_m)[0], np.where(te_m)[0]
            train, test = ba.subset(arrays, tr), ba.subset(arrays, te)
            fs = ba.feature_scale(train)
            t0 = time.time()

            p1 = ba.fit(ba.build_model("atomic", train, D), n_iter=N_ITER, seed=f)
            th = p1.posterior["theta"].mean(("chain","draw")).values
            w  = p1.posterior["w"].mean(("chain","draw")).values
            for tcr, a in ba.per_tcr_auc(
                    test, ba.posterior_distance("atomic", p1, test, D)).items():
                rows.append(dict(L=L, fold=f, variant="atomic", tcr=tcr, auc=a))

            for kind in ("hybrid_frozen", "hybrid_feature"):
                kw = dict(hybrid_shrinkage=0.25, frozen_theta=th, frozen_w=w)
                dk = dict(frozen_theta=th, frozen_w=w)
                if kind == "hybrid_feature":
                    kw["feat_scale"] = fs; dk["feat_scale"] = fs
                p2 = ba.fit(ba.build_model(kind, train, D, **kw),
                            n_iter=N_ITER, seed=f)
                d2 = ba.posterior_distance(kind, p2, test, D, **dk)
                for tcr, a in ba.per_tcr_auc(test, d2).items():
                    rows.append(dict(L=L, fold=f, variant=kind, tcr=tcr, auc=a))
            print(f"  L={L} fold={f} done [{time.time()-t0:.0f}s]", flush=True)
    return pd.DataFrame(rows)

def main():
    t0=time.time(); r=ex.cached("feature_indist.csv", compute)
    print(f"\n@@@ feature_indist FINISHED {len(r)} rows in {(time.time()-t0)/60:.1f} min",flush=True)

if __name__ == "__main__":
    main()
