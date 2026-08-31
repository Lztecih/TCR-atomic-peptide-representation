"""
review_checks.py
================
Adversarial checks a referee would demand before believing the headline claim.

    prior_art   Atchley (2005) five-factor encoding on the *same* splits.
                pTEAM already uses these, so if five published numbers match
                the atomic representation, the novelty claim collapses.
    seeds       Re-run leave-chemistry-out under several ADVI seeds. ADVI is
                stochastic; a +0.005 AUC effect is only real if it survives
                seed noise.
    fallback    Verify the "learned" matrix really does fall back to its prior
                on substitutions absent from training (paper Eq. 9-10), i.e.
                that the baseline was given a fair chance.

Usage:  python3 review_checks.py <prior_art|seeds|fallback>
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


def _cv_for_phi(df, phi, D, tag, n_iter=12000, seed=0):
    """exp1-style 5-fold CV for one feature matrix (atomic model only)."""
    rows = []
    for L, sub, arrays in ex.length_groups(df, phi):
        fold = sub.training_fold.to_numpy()
        is_index = sub.mutation_position.to_numpy() == 0
        for f in range(5):
            test_m = fold == f
            if test_m.sum() < 10:
                continue
            tr = np.where(~test_m | is_index)[0]
            te = np.where(test_m)[0]
            per, _, _ = ex._fit_predict("atomic", arrays, tr, te, D,
                                        n_iter=n_iter, seed=seed + f)
            for tcr, auc in per.items():
                rows.append(dict(encoding=tag, L=L, fold=f, tcr=tcr, auc=auc))
        print(f"  [{tag}] L={L} done", flush=True)
    return pd.DataFrame(rows)


def _chem_for_phi(df, phi, D, tag, n_iter=12000, seed=0):
    """exp2-style leave-chemistry-out for one feature matrix."""
    rows = []
    for L, sub, arrays in ex.length_groups(df, phi):
        mut_aa = ex._mutant_residue(sub)
        pos = sub.mutation_position.to_numpy(dtype=int)
        for gname, held in ex.CHEM_GROUPS.items():
            test_m = np.array([m in held for m in mut_aa])
            train_m = (~test_m) & (pos > 0)
            if test_m.sum() < 20 or train_m.sum() < 50:
                continue
            tr, te = np.where(train_m)[0], np.where(test_m)[0]
            per, _, _ = ex._fit_predict("atomic", arrays, tr, te, D,
                                        n_iter=n_iter, seed=seed)
            for tcr, auc in per.items():
                rows.append(dict(encoding=tag, seed=seed, L=L,
                                 group=gname, tcr=tcr, auc=auc))
        print(f"  [{tag} seed={seed}] L={L} done", flush=True)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------

def prior_art(df, D):
    """Atchley 5-factor encoding vs the atomic representation."""
    def compute():
        atch = ba.load_atchley_factors().to_numpy()
        frames = [_cv_for_phi(df, atch, D, "atchley5")]
        return pd.concat(frames, ignore_index=True)

    cv = ex.cached("review_atchley_cv.csv", compute)

    def compute2():
        atch = ba.load_atchley_factors().to_numpy()
        return _chem_for_phi(df, atch, D, "atchley5")

    chem = ex.cached("review_atchley_chem.csv", compute2)
    return cv, chem


def seeds(df, D, seed_list=(0, 1, 2, 3, 4)):
    """Does the leave-chemistry-out effect survive ADVI seed noise?"""
    def compute():
        phi = ba.build_atomic_features("base8").to_numpy()
        out = []
        for s in seed_list:
            out.append(_chem_for_phi(df, phi, D, "atomic_base8", seed=s))
        return pd.concat(out, ignore_index=True)

    return ex.cached("review_seed_stability.csv", compute)


def fallback(df, D):
    """Check the learned matrix's unseen entries revert to the prior mean."""
    phi = ba.build_atomic_features("base8").to_numpy()
    sub = df[(df.index_peptide.str.len() == 9) & (df.peptide.str.len() == 9)]
    ok = (sub.peptide.apply(lambda s: all(c in ba.AA_IDX for c in s))
          & sub.index_peptide.apply(lambda s: all(c in ba.AA_IDX for c in s)))
    sub = sub[ok].reset_index(drop=True)
    arrays = ba.prepare(sub, phi)

    mut_aa = ex._mutant_residue(sub)
    pos = sub.mutation_position.to_numpy(dtype=int)
    held = set("WFY")
    test_m = np.array([m in held for m in mut_aa])
    tr = np.where((~test_m) & (pos > 0))[0]

    model = ba.build_model("learned", ba.subset(arrays, tr), D)
    post = ba.fit(model, n_iter=12000, seed=0)
    delta = post.posterior["delta"].mean(("chain", "draw")).values
    mu = float(post.posterior["mu"].mean())

    # Which (index_aa -> mutant_aa) cells actually appear in the training rows?
    seen = np.zeros((20, 20), dtype=bool)
    idxI, idxP = arrays["idxI"][tr], arrays["idxP"][tr]
    for a, b in zip(idxI.ravel(), idxP.ravel()):
        if a != b:
            seen[a, b] = True

    print(f"training covers {seen.sum()} of 380 off-diagonal cells")
    print(f"posterior mu (prior mean of delta) = {mu:+.4f}")
    print(f"delta on SEEN cells   : mean {delta[seen].mean():+.4f} "
          f"sd {delta[seen].std():.4f}")
    unseen = (~seen) & ~np.eye(20, dtype=bool)
    print(f"delta on UNSEEN cells : mean {delta[unseen].mean():+.4f} "
          f"sd {delta[unseen].std():.4f}")
    print()
    # Judge reversion on the scale of the parameter, not in absolute units:
    # delta absorbs a large global rescale (mu is far from 0), so an absolute
    # threshold would be meaningless here.
    gap = abs(delta[unseen].mean() - mu)
    rel = gap / delta[seen].std()
    spread_ratio = delta[unseen].std() / delta[seen].std()
    print(f"|mean(delta_unseen) - mu| = {gap:.4f}  "
          f"({rel:.3f} of the seen-cell sd)")
    print(f"spread ratio unseen/seen  = {spread_ratio:.3f}")
    print("PASS: unseen cells revert to the prior, matching paper Eq. 9-10"
          if rel < 0.1 and spread_ratio < 0.5 else
          "WARNING: unseen cells deviate from the prior -- check implementation")
    print(f"NOTE: mu = {mu:+.3f}, i.e. M ~ {1+mu:.1f}x D -- most of the learned "
          f"matrix's freedom goes into a global rescale, not per-substitution "
          f"reshaping.")
    return delta, seen, mu


def hybrid(df, D, n_iter=12000):
    """Full-scale evaluation of the hybrid model (atomic backbone + residual)."""
    phi = ba.build_atomic_features("base8").to_numpy()

    def cv_compute():
        rows = []
        for L, sub, arrays in ex.length_groups(df, phi):
            fold = sub.training_fold.to_numpy()
            is_index = sub.mutation_position.to_numpy() == 0
            for f in range(5):
                test_m = fold == f
                if test_m.sum() < 10:
                    continue
                tr = np.where(~test_m | is_index)[0]
                te = np.where(test_m)[0]
                per, _, _ = ex._fit_predict("hybrid", arrays, tr, te, D,
                                            n_iter=n_iter, seed=f)
                for tcr, auc in per.items():
                    rows.append(dict(model="hybrid", L=L, fold=f, tcr=tcr, auc=auc))
            print(f"  [hybrid cv] L={L} done", flush=True)
        return pd.DataFrame(rows)

    def chem_compute():
        rows = []
        for L, sub, arrays in ex.length_groups(df, phi):
            mut_aa = ex._mutant_residue(sub)
            pos = sub.mutation_position.to_numpy(dtype=int)
            for gname, held in ex.CHEM_GROUPS.items():
                test_m = np.array([m in held for m in mut_aa])
                train_m = (~test_m) & (pos > 0)
                if test_m.sum() < 20 or train_m.sum() < 50:
                    continue
                tr, te = np.where(train_m)[0], np.where(test_m)[0]
                per, _, _ = ex._fit_predict("hybrid", arrays, tr, te, D,
                                            n_iter=n_iter, seed=0)
                for tcr, auc in per.items():
                    rows.append(dict(model="hybrid", L=L, group=gname,
                                     tcr=tcr, auc=auc))
            print(f"  [hybrid chem] L={L} done", flush=True)
        return pd.DataFrame(rows)

    return (ex.cached("review_hybrid_cv.csv", cv_compute),
            ex.cached("review_hybrid_chem.csv", chem_compute))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "prior_art"
    D = ba.load_blosum100_distance()
    df = ba.load_batcave()
    t0 = time.time()
    if which == "prior_art":
        prior_art(df, D)
    elif which == "seeds":
        seeds(df, D)
    elif which == "fallback":
        fallback(df, D)
    elif which == "hybrid":
        hybrid(df, D)
    else:
        raise SystemExit(f"unknown check: {which}")
    print(f"@@@ {which} FINISHED in {(time.time()-t0)/60:.1f} min", flush=True)
