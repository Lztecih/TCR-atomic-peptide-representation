"""
run_validation.py
=================
External validation of every model on **Malone et al. 2025** -- data that
shares nothing with the training set: unseen TCRs, an unseen epitope, and a
different readout.

Protocol
--------
train : BATCAVE 9-mers, single-substitution rows only, ``pan_tcr=True``
        (the Malone TCRs are unseen, so no per-TCR weights exist -- one shared
        positional-weight profile is learned, exactly as in Experiment 4)
test  : the 168 clean single substitutions of YLQPRTFLL, scored once per model

Because every model uses one shared weight profile, each model produces ONE
ranking of the 168 peptides. Each TCR then contributes one observation: how
well that single ranking agrees with that TCR's measured binding profile.

Metrics
-------
primary   Spearman rho between -distance and measured binding, per TCR.
          Rank-based and threshold-free, so nothing hinges on where a cutoff
          between "binder" and "non-binder" is drawn.
secondary per-TCR mean pairwise AUC after splitting each TCR's binding into
          three tertiles, to be comparable with the rest of the paper. The
          tertile split is arbitrary, which is exactly why it is secondary.

Output: ``results/malone_validation.csv`` (+ per-TCR detail) and a printed
summary.

Usage:  python3 run_validation.py
"""

from __future__ import annotations

# --- bootstrap: shared library lives one level up ---
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
if _os.path.dirname(_os.path.abspath(__file__)) not in _sys.path:
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
# --- end bootstrap ---

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy import stats

import batman_atomic as ba
import malone2025 as ml

RES = _os.path.join(ba.ROOT, "results")
N_ITER = 12000
SHRINK = 0.25
MODELS = ["blosum_uniform", "fixed", "learned", "atomic", "hybrid_frozen"]


def train_arrays(phi):
    """BATCAVE 9-mers, mutant rows only -- the training pool."""
    df = ba.load_batcave()
    sub = df[(df.index_peptide.str.len() == 9) & (df.peptide.str.len() == 9)]
    ok = (sub.peptide.apply(lambda s: all(c in ba.AA_IDX for c in s))
          & sub.index_peptide.apply(lambda s: all(c in ba.AA_IDX for c in s)))
    sub = sub[ok & (sub.mutation_position > 0)].reset_index(drop=True)
    return sub, ba.prepare(sub, phi)


def test_arrays(peptides, phi):
    """The 168 Malone peptides, as one scoring batch."""
    te = pd.DataFrame({
        "index_peptide": [ml.INDEX_PEPTIDE] * len(peptides),
        "peptide": list(peptides),
        "activation": 0,                 # unused; prepare() just needs the column
        "tcr": "malone",
    })
    return ba.prepare(te, phi, tcr_index={"malone": 0})


def tertile_auc(binding, dist):
    """Mean pairwise AUC after cutting binding into three tertiles."""
    q = np.quantile(binding, [1 / 3, 2 / 3])
    y = np.digitize(binding, q)          # 0 = weakest third, 2 = strongest
    return ba.mean_pairwise_auc(y, dist)


def main():
    phi_df = ba.build_atomic_features("base8")
    phi = phi_df.to_numpy()
    D = ba.load_blosum100_distance()

    tidy, wide = ml.load()
    index_tcrs = tidy.attrs["index_tcrs"]
    peptides = list(wide.index)

    sub, tr = train_arrays(phi)
    te = test_arrays(peptides, phi)
    print(f"\ntrain: {len(sub):,} single-substitution rows, "
          f"{sub.tcr.nunique()} BATCAVE 9-mer TCRs (pan-TCR weights)")
    print(f"test : {len(peptides)} peptides x {len(index_tcrs)} unseen TCRs\n")

    # ---------------- score every model once ------------------------------
    dist = {}
    # NOTE: plain Hamming distance is useless on a single-substitution scan --
    # every peptide is exactly 1 substitution from the index, so the score is
    # constant and its correlation is undefined. The learning-free null here is
    # BLOSUM100 with uniform positional weights, which at least varies.
    idxI = np.array([ba.AA_IDX[c] for c in ml.INDEX_PEPTIDE])
    dist["blosum_uniform"] = np.array([
        sum(D[idxI[j], ba.AA_IDX[p[j]]] for j in range(len(p)))
        for p in peptides], dtype=float)

    for kind in ("fixed", "learned", "atomic"):
        post = ba.fit(ba.build_model(kind, tr, D, pan_tcr=True),
                      n_iter=N_ITER, seed=0)
        dist[kind] = ba.posterior_distance(kind, post, te, D, pan_tcr=True)
        if kind == "atomic":
            theta = post.posterior["theta"].mean(("chain", "draw")).values
            w = post.posterior["w"].mean(("chain", "draw")).values
        print(f"  fitted {kind}", flush=True)

    # build_model("hybrid_frozen") always indexes frozen_w by the training
    # row's TCR, so a single pan-TCR profile has to be broadcast to every
    # training TCR first. posterior_distance handles pan_tcr itself, so it
    # takes the un-tiled profile.
    w_tiled = np.tile(w, (tr["n_tcr"], 1))
    post2 = ba.fit(
        ba.build_model("hybrid_frozen", tr, D, hybrid_shrinkage=SHRINK,
                       frozen_theta=theta, frozen_w=w_tiled),
        n_iter=N_ITER, seed=0)
    dist["hybrid_frozen"] = ba.posterior_distance(
        "hybrid_frozen", post2, te, D, pan_tcr=True,
        frozen_theta=theta, frozen_w=w)
    print("  fitted hybrid_frozen", flush=True)

    # ---------------- evaluate against each TCR ---------------------------
    rows = []
    for c in index_tcrs:
        binding = wide[c].to_numpy(dtype=float)
        for m in MODELS:
            rho = stats.spearmanr(-dist[m], binding).statistic
            rows.append(dict(tcr=c, model=m, spearman=float(rho),
                             auc_tertile=float(tertile_auc(binding, dist[m]))))
    out = pd.DataFrame(rows)
    out.to_csv(_os.path.join(RES, "malone_validation.csv"), index=False)

    # ---------------- summary --------------------------------------------
    print("\n=== external validation: Malone 2025 "
          f"({len(index_tcrs)} unseen TCRs, unseen epitope, binding readout) ===\n")
    print(f"{'model':16s} {'Spearman rho':>14s} {'95% CI':>18s} "
          f"{'tertile AUC':>12s}")
    summ = []
    for m in MODELS:
        v = out[out.model == m].spearman.to_numpy()
        a = out[out.model == m].auc_tertile.to_numpy()
        lo, hi = np.percentile(
            np.random.default_rng(0).choice(v, (10000, len(v))).mean(1),
            [2.5, 97.5])
        summ.append(dict(model=m, spearman=v.mean(), lo=lo, hi=hi, auc=a.mean()))
        print(f"{m:16s} {v.mean():>14.3f} {f'[{lo:.3f}, {hi:.3f}]':>18s} "
              f"{a.mean():>12.3f}")

    # ---------------- how independent are these 20 TCRs, really? ----------
    W = wide[index_tcrs].to_numpy(dtype=float)
    C = np.corrcoef(stats.rankdata(W, axis=0).T)
    iu = np.triu_indices(len(index_tcrs), 1)
    r_bar = float(C[iu].mean())
    n_eff = len(index_tcrs) / (1 + (len(index_tcrs) - 1) * r_bar)
    print(f"\nWARNING -- the 20 TCRs are NOT independent replicates.")
    print(f"  they all recognise the same epitope, and their binding profiles")
    print(f"  correlate at mean Spearman {r_bar:.2f} -> effective n ~ {n_eff:.1f}.")
    print(f"  A paired test across TCRs would therefore be pseudo-replicated,")
    print(f"  so it is NOT used for inference here.")

    # ---------------- valid inference: resample PEPTIDES -------------------
    # The defensible question is whether a difference survives re-drawing which
    # peptides were assayed. Peptides are the resampling unit; TCRs are not.
    print(f"\nbootstrap over the {len(peptides)} peptides "
          f"(10,000 resamples, mean over TCRs):")
    rng = np.random.default_rng(0)
    boot_idx = rng.integers(0, len(peptides), size=(10000, len(peptides)))

    def boot_rho(m):
        out_b = np.empty(len(boot_idx))
        dm = -dist[m]
        for i, ii in enumerate(boot_idx):
            out_b[i] = np.mean([stats.spearmanr(dm[ii], W[ii, k]).statistic
                                for k in range(W.shape[1])])
        return out_b

    cache = {}
    for a, b in [("atomic", "fixed"), ("atomic", "learned"),
                 ("hybrid_frozen", "atomic"), ("hybrid_frozen", "learned")]:
        for m in (a, b):
            if m not in cache:
                cache[m] = boot_rho(m)
        d = cache[a] - cache[b]
        lo, hi = np.percentile(d, [2.5, 97.5])
        crosses = "ไม่ต่าง (CI คร่อม 0)" if lo <= 0 <= hi else "ต่างจริง"
        print(f"  {a:14s} - {b:14s} = {d.mean():+.4f}  "
              f"95% CI [{lo:+.4f}, {hi:+.4f}]  {crosses}")

    print("\n@@@ malone validation FINISHED")


if __name__ == "__main__":
    main()
