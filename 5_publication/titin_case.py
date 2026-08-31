"""
titin_case.py
=============
A clinical retrospective on one peptide.

In 2013 an affinity-enhanced TCR against the melanoma antigen MAGE-A3
(`EVDPIGHLY`, HLA-A*01:01) was infused into patients. The first two died of
cardiogenic shock within days. The cause was cross-reactivity with an
unrelated peptide from **titin** (`ESDPIVAQY`), expressed in beating
cardiomyocytes -- four substitutions away from the intended target, and
missed by every preclinical assay run at the time.
(Linette et al., *Blood* 122:863, 2013; Cameron et al., *Sci Transl Med* 2013.)

That TCR is in BATCAVE as `a3a`, and the titin peptide is in the multi-mutant
set with a measured activation of 2 (strong).

So we can ask the question a clinician would actually ask:

    Given only the single-amino-acid scan -- the kind of characterisation you
    could run BEFORE first-in-human dosing -- would the model have ranked the
    titin peptide as dangerous?

The models are fitted on single-substitution data only and then asked to rank
111 held-out multi-substitution peptides. Nothing about titin is in training.

Output: ``results/titin_case.csv`` + printed summary.

Usage:  python3 titin_case.py
"""

from __future__ import annotations

# --- bootstrap: shared library lives one level up ---
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
# --- end bootstrap ---

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import batman_atomic as ba

RES = _os.path.join(ba.ROOT, "results")

TCR = "a3a"
INDEX = "EVDPIGHLY"      # MAGE-A3 168-176
TITIN = "ESDPIVAQY"      # titin 394-403 -- the off-target that proved fatal
SHRINK = 0.25
N_ITER = 12000


def main():
    phi = ba.build_atomic_features("base8").to_numpy()
    D = ba.load_blosum100_distance()
    df = ba.load_batcave()
    mh = ba.load_multi_hamming()

    # ---- training: single-substitution rows of the 9-mer group ------------
    L9 = df[(df.index_peptide.str.len() == 9) & (df.peptide.str.len() == 9)]
    ok = (L9.peptide.apply(lambda s: all(c in ba.AA_IDX for c in s))
          & L9.index_peptide.apply(lambda s: all(c in ba.AA_IDX for c in s)))
    L9 = L9[ok & (L9.mutation_position > 0)].reset_index(drop=True)
    assert TCR in set(L9.tcr), f"{TCR} missing from the 9-mer group"

    # ---- test: the held-out multi-substitution peptides for this TCR ------
    test = mh[(mh.tcr == TCR) & (mh.index_peptide == INDEX)].reset_index(drop=True)
    assert TITIN in set(test.peptide), "titin peptide not found in the test set"
    print(f"train: {len(L9):,} single-substitution rows "
          f"({L9.tcr.nunique()} TCRs, 9-mers)")
    print(f"test : {len(test)} multi-substitution peptides for {TCR}, "
          f"none seen in training")
    n_strong = int((test.activation == 2).sum())
    print(f"       of which {n_strong} are strong activators (activation = 2)\n")

    # shared TCR indexing so train/test line up
    tcr_index = {t: i for i, t in enumerate(sorted(L9.tcr.unique()))}
    tr_arr = ba.prepare(L9, phi, tcr_index=tcr_index)
    te = test.copy()
    te["tcr"] = TCR
    te_arr = ba.prepare(te, phi, tcr_index=tcr_index)

    rows = []

    def record(model, dist):
        order = np.argsort(dist)                 # small distance = ranked first
        ranks = np.empty(len(dist), dtype=int)
        ranks[order] = np.arange(1, len(dist) + 1)
        i = int(np.where(te.peptide.values == TITIN)[0][0])
        strong = te.activation.values == 2
        rows.append(dict(
            model=model,
            titin_rank=int(ranks[i]),
            n_tested=len(dist),
            titin_percentile=round(100 * (1 - (ranks[i] - 1) / len(dist)), 1),
            median_rank_strong=float(np.median(ranks[strong])),
            n_strong=int(strong.sum())))
        print(f"  {model:16s} titin ranked {ranks[i]:3d} / {len(dist)}   "
              f"(top {100*ranks[i]/len(dist):4.1f}%)   "
              f"median rank of all strong activators = "
              f"{np.median(ranks[strong]):.0f}")

    # ---- learning-free null ---------------------------------------------
    ham = np.array([sum(a != b for a, b in zip(INDEX, p)) for p in te.peptide])
    record("hamming", ham.astype(float))

    # ---- fitted models ---------------------------------------------------
    for kind in ("fixed", "learned", "atomic"):
        post = ba.fit(ba.build_model(kind, tr_arr, D), n_iter=N_ITER, seed=0)
        record(kind, ba.posterior_distance(kind, post, te_arr, D))
        if kind == "atomic":
            theta = post.posterior["theta"].mean(("chain", "draw")).values
            w = post.posterior["w"].mean(("chain", "draw")).values

    post2 = ba.fit(
        ba.build_model("hybrid_frozen", tr_arr, D, hybrid_shrinkage=SHRINK,
                       frozen_theta=theta, frozen_w=w),
        n_iter=N_ITER, seed=0)
    record("hybrid_frozen",
           ba.posterior_distance("hybrid_frozen", post2, te_arr, D,
                                 frozen_theta=theta, frozen_w=w))

    out = pd.DataFrame(rows)
    out.to_csv(_os.path.join(RES, "titin_case.csv"), index=False)

    print(f"\n{INDEX}  MAGE-A3 168-176   (the intended target)")
    print(f"{TITIN}  titin 394-403     (the off-target that killed two patients)")
    diff = [i + 1 for i, (a, b) in enumerate(zip(INDEX, TITIN)) if a != b]
    print(f"differ at positions {diff} -- {len(diff)} of 9\n")
    print(out.to_string(index=False))
    print("\n@@@ titin_case FINISHED")


if __name__ == "__main__":
    main()
