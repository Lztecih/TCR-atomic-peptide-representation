"""
loeo_feature_residual.py
========================
Does a residual tied to physicochemical features transfer across epitopes,
when a per-cell residual does not?

Section 3.12 showed the per-cell residual delta_ab memorises the training
epitopes: its penalty on a held-out epitope is monotone in how much freedom it
is given, and no shrinkage level lets it beat the atomic backbone. The proposed
fix is to keep extra capacity but tie it to the axes the backbone already uses,
so the residual can only say things about amino-acid *properties*:

    per-cell   M = base + delta_ab                       400 parameters
    feature    M = base + sum_{k<=l} Lambda_kl u_k u_l    36 parameters
               (u = |dphi| / feature_scale)

Prediction: if the per-cell residual fails because it addresses individual
residue pairs in one epitope's context, the feature-tied residual should
degrade less -- or not at all -- on a held-out epitope.

Each held-out epitope is fitted once for the shared atomic stage, then the two
residual types are fitted on top of it.

Output: ``results/loeo_feature_residual.csv``
Usage:  python3 loeo_feature_residual.py
"""

from __future__ import annotations

import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)

import time, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import batman_atomic as ba
import experiments as ex

RES = _os.path.join(ba.ROOT, "results")
N_ITER = 12000
VARIANTS = [("hybrid_frozen", 0.25), ("hybrid_feature", 0.25),
            ("hybrid_feature", 0.50)]


def compute():
    phi = ba.build_atomic_features("base8").to_numpy()
    D = ba.load_blosum100_distance()
    df = ba.load_batcave()
    rows = []

    for L, sub, arrays in ex.length_groups(df, phi):
        eps = sorted(sub.index_peptide.unique())
        if len(eps) < 2:
            continue
        pos = sub.mutation_position.to_numpy(dtype=int)
        idx_pep = sub.index_peptide.to_numpy()

        for held in eps:
            test_m = (idx_pep == held) & (pos > 0)
            train_m = (idx_pep != held) & (pos > 0)
            if test_m.sum() < 20 or train_m.sum() < 200:
                continue
            tr, te = np.where(train_m)[0], np.where(test_m)[0]
            train, test = ba.subset(arrays, tr), ba.subset(arrays, te)
            n_tcr = sub.loc[test_m, "tcr"].nunique()
            fs = ba.feature_scale(train)          # from TRAIN only
            t0 = time.time()

            post1 = ba.fit(ba.build_model("atomic", train, D, pan_tcr=True),
                           n_iter=N_ITER, seed=0)
            theta = post1.posterior["theta"].mean(("chain", "draw")).values
            w = post1.posterior["w"].mean(("chain", "draw")).values
            a_auc = ba.per_tcr_auc(
                test, ba.posterior_distance("atomic", post1, test, D,
                                            pan_tcr=True))
            for tcr, auc in a_auc.items():
                rows.append(dict(L=L, held_out_epitope=held, n_tcr=n_tcr,
                                 variant="atomic", sigma=np.nan,
                                 tcr=tcr, auc=auc))

            w_tiled = np.tile(w, (train["n_tcr"], 1))
            means = {}
            for kind, sg in VARIANTS:
                kw = dict(hybrid_shrinkage=sg, frozen_theta=theta,
                          frozen_w=w_tiled)
                if kind == "hybrid_feature":
                    kw["feat_scale"] = fs
                post2 = ba.fit(ba.build_model(kind, train, D, **kw),
                               n_iter=N_ITER, seed=0)
                dk = dict(frozen_theta=theta, frozen_w=w, pan_tcr=True)
                if kind == "hybrid_feature":
                    dk["feat_scale"] = fs
                d2 = ba.posterior_distance(kind, post2, test, D, **dk)
                h = ba.per_tcr_auc(test, d2)
                tag = f"{kind}@{sg:g}"
                for tcr, auc in h.items():
                    rows.append(dict(L=L, held_out_epitope=held, n_tcr=n_tcr,
                                     variant=tag, sigma=sg, tcr=tcr, auc=auc))
                means[tag] = np.mean(list(h.values()))

            print(f"  L={L} {held:22s} atomic={np.mean(list(a_auc.values())):.3f}  "
                  + "  ".join(f"{k.replace('hybrid_','')}={v:.3f}"
                              for k, v in means.items())
                  + f"  [{time.time()-t0:.0f}s]", flush=True)
    return pd.DataFrame(rows)


def main():
    t0 = time.time()
    r = ex.cached("loeo_feature_residual.csv", compute)
    print(f"\n@@@ loeo_feature_residual FINISHED {len(r)} rows in "
          f"{(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
