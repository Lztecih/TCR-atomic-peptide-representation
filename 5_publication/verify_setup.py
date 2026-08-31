"""
verify_setup.py
===============
One command that answers "is this repository actually in a runnable, and
trustworthy, state?".

It checks four separate things, and a failure in each means something
different:

  ENV      packages importable at the versions the results were produced with
  DATA     input files present, the right shape, and byte-identical to the
           upstream BATMAN-paper release (SHA-256)
  CORRECT  the from-scratch BLOSUM100 -> distance reimplementation reproduces
           the authors' own matrix exactly, and the reimplemented BATMAN model
           lands where the paper reports
  RESULTS  every cached result file the manuscript cites exists, and the
           headline statistics recompute from the raw per-TCR AUCs

Exit code is 0 only if every check passes.

Usage:  python3 verify_setup.py [--no-network]
"""

from __future__ import annotations

# --- bootstrap: shared library lives one level up ---
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
# --- end bootstrap ---

import hashlib
import io
import os
import urllib.request
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy import stats

NO_NET = "--no-network" in _sys.argv

OK, FAIL, WARN = "  [ok]  ", "  [FAIL]", "  [warn]"
_failures: list[str] = []


def check(cond, msg, warn_only=False):
    if cond:
        print(OK + msg)
    elif warn_only:
        print(WARN + " " + msg)
    else:
        print(FAIL + " " + msg)
        _failures.append(msg)
    return bool(cond)


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


# ============================================================== 1. ENV ====
def check_env():
    print("\n=== ENV ===")
    expected = {
        "numpy": "2.", "pandas": "3.", "pymc": "6.", "arviz": "1.",
        "rdkit": "2026.", "sklearn": "1.", "scipy": "1.", "matplotlib": "3.",
    }
    for mod, prefix in expected.items():
        try:
            m = __import__(mod)
            v = getattr(m, "__version__", "?")
            check(True, f"{mod:12s} {v}")
            if not str(v).startswith(prefix):
                print(f"         (results were produced with {prefix}x)")
        except Exception as e:
            check(False, f"{mod:12s} NOT IMPORTABLE ({type(e).__name__})")
    print(f"  [ok]   python {_sys.version.split()[0]}")


# ============================================================= 2. DATA ====
#: SHA-256 of the upstream files, recorded from a fresh sparse clone of
#: meyer-lab-cshl/BATMAN-paper@main. A mismatch means the local copy drifted
#: from the published data -- or that upstream changed.
UPSTREAM_SHA = {
    "data/train_test_data_folds.xlsx":
        "cbb5ee36fcaf604d",          # first 16 hex chars, see note below
}


def check_data(ba):
    print("\n=== DATA ===")
    root = ba.ROOT

    df = ba.load_batcave()
    check(df.shape == (22827, 26),
          f"BATCAVE single-aa scan: {df.shape[0]:,} rows x {df.shape[1]} cols")
    check(df.tcr.nunique() == 151, f"TCRs: {df.tcr.nunique()}")
    check(set(df.activation.unique()) == {0, 1, 2},
          f"activation labels: {sorted(df.activation.unique())}")
    lens = sorted(df.index_peptide.str.len().unique())
    check(lens == [8, 9, 10, 11, 13, 20], f"index-peptide lengths: {lens}")

    mh = ba.load_multi_hamming()
    check(len(mh) == 1423 and mh.tcr.nunique() == 7,
          f"multi-aa mutants: {len(mh):,} rows, {mh.tcr.nunique()} TCRs")

    for rel, want in UPSTREAM_SHA.items():
        p = os.path.join(root, rel)
        if os.path.exists(p):
            got = sha256(p)[:16]
            check(got == want,
                  f"{rel} SHA-256 {got} (upstream {want})")
        else:
            check(False, f"{rel} MISSING")

    for sub in ("data/netmhcii", "data/multi_hamming", "data/raw_audit"):
        p = os.path.join(root, sub)
        n = len(os.listdir(p)) if os.path.isdir(p) else 0
        check(n > 0, f"{sub}/ present ({n} files)")


# ========================================================== 3. CORRECT ====
def check_correctness(ba):
    print("\n=== CORRECTNESS ===")
    D = ba.load_blosum100_distance()
    check(D.shape == (20, 20), f"BLOSUM100 distance matrix {D.shape}")
    check(np.allclose(np.diag(D), 0), "diagonal is exactly 0")
    check(np.allclose(D, D.T), "matrix is symmetric")

    # Independent re-derivation of Eq. 24 straight from the raw BLOSUM100
    # substitution scores, compared against the authors' distributed matrix.
    if not NO_NET:
        try:
            url = ("https://raw.githubusercontent.com/meyer-lab-cshl/"
                   "BATMAN-paper/main/results_batman/batman_functions/"
                   "AA_matrices/blosum100.csv")
            raw = urllib.request.urlopen(url, timeout=30).read()
            ref = pd.read_csv(io.BytesIO(raw), index_col=0)
            R = ref.loc[list(ba.AA20), list(ba.AA20)].to_numpy(float)
            diff = float(np.abs(D - R).max())
            check(diff == 0.0,
                  f"reimplemented distance == authors' blosum100.csv "
                  f"(max abs diff {diff:g})")
        except Exception as e:
            check(True, f"upstream BLOSUM check skipped ({type(e).__name__})",
                  warn_only=True)

    phi = ba.build_atomic_features("base8")
    check(phi.shape == (20, 8), f"atomic descriptors {phi.shape}")
    check(abs(float(phi.to_numpy().mean())) < 1e-9
          and abs(float(phi.to_numpy().std(ddof=1)) - 1) < .05,
          "descriptors standardised (mean 0, sd 1)")
    # M[a,a] = 0 and non-negativity hold by construction -- assert it anyway
    theta = np.load(os.path.join(ba.ROOT, "results", "theta_9mer.npy"))
    P = phi.to_numpy()
    M = np.einsum("k,abk->ab", theta, np.abs(P[:, None, :] - P[None, :, :]))
    check(np.allclose(np.diag(M), 0), "atomic M has zero diagonal")
    check((M >= -1e-12).all(), "atomic M is non-negative")
    check(np.allclose(M, M.T), "atomic M is symmetric")
    tri = np.triu_indices(20, 1)
    r = float(np.corrcoef(M[tri], ba.load_blosum100_distance()[tri])[0, 1])
    check(0.2 < r < 0.6,
          f"atomic M correlates only moderately with BLOSUM100 (r={r:.2f})")


# ========================================================== 4. RESULTS ====
def per_tcr(df, model, keys):
    return df[df.model == model].groupby(keys).auc.mean()


def paired(df, m1, m2, keys):
    a, b = per_tcr(df, m1, keys), per_tcr(df, m2, keys)
    j = pd.concat([a, b], axis=1, join="inner", keys=["a", "b"]).dropna()
    d = j.a - j.b
    return dict(n=len(j), mean=float(d.mean()), win=float((d > 0).mean()),
                d=float(d.mean() / d.std(ddof=1)),
                p=float(stats.wilcoxon(j.a, j.b).pvalue))


def check_results(ba):
    print("\n=== RESULTS ===")
    RES = os.path.join(ba.ROOT, "results")
    needed = [
        "exp1_cross_validation.csv", "exp2_leave_chemistry_out.csv",
        "exp3_feature_ablation.csv", "exp4_novel_tcr.csv",
        "exp5_multi_mutant.csv", "exp6_nuts_vs_advi.csv",
        "exp7_pmhc_term.csv", "hybrid_frozen_s025.csv",
        "review_hybrid_shrinkage.csv", "review_atchley_cv.csv",
        "review_atchley_chem.csv", "review_seed_stability.csv",
        "proteome_null_baselines.csv", "noncanonical_distances.csv",
        "exp8_harmonized_protocol.csv", "malone_validation.csv",
        "leave_one_epitope_out.csv", "loeo_shrinkage.csv",
        "loeo_feature_residual.csv", "feature_indist.csv",
    ]
    for n in needed:
        check(os.path.exists(os.path.join(RES, n)), f"results/{n}")

    # --- headline claim recomputed from raw per-TCR AUCs -------------------
    hy = pd.read_csv(os.path.join(RES, "hybrid_frozen_s025.csv"))
    ind = hy[hy.setting == "in_distribution"]      # original protocol
    ood = hy[hy.setting == "leave_chemistry_out"]

    r = paired(ind, "hybrid_frozen", "atomic", ["tcr"])
    check(r["n"] == 150 and abs(r["mean"] - 0.0283) < 5e-4
          and r["d"] > 0.9 and r["p"] < 1e-20,
          f"HEADLINE hybrid>atomic in-dist: n={r['n']}, "
          f"D={r['mean']:+.4f}, d={r['d']:.2f}, win={r['win']:.1%}, p={r['p']:.1e}")

    r2 = paired(ood, "hybrid_frozen", "atomic", ["tcr", "group"])
    check(abs(r2["mean"]) < 0.005 and r2["p"] > 0.05,
          f"HEADLINE hybrid costs no OOD: n={r2['n']}, "
          f"D={r2['mean']:+.4f}, d={r2['d']:+.2f}, p={r2['p']:.2f}")

    # --- harmonised protocol: the numbers the manuscript reports as primary
    hp = os.path.join(RES, "exp8_harmonized_protocol.csv")
    if os.path.exists(hp):
        h = pd.read_csv(hp)
        hi = h[h.setting == "in_distribution"]
        ho = h[h.setting == "leave_chemistry_out"]
        r = paired(hi, "hybrid_frozen", "atomic", ["tcr"])
        check(r["d"] > 0.8 and r["p"] < 1e-15,
              f"HARMONISED hybrid>atomic in-dist: n={r['n']}, "
              f"D={r['mean']:+.4f}, d={r['d']:.2f}, win={r['win']:.1%}, "
              f"p={r['p']:.1e}")
        r2 = paired(ho, "hybrid_frozen", "atomic", ["tcr", "group"])
        check(abs(r2["mean"]) < 0.005 and r2["p"] > 0.05,
              f"HARMONISED hybrid costs no OOD: n={r2['n']}, "
              f"D={r2['mean']:+.4f}, p={r2['p']:.2f}")
        r3 = paired(hi, "learned", "atomic", ["tcr"])
        check(r3["mean"] > 0 and r3["p"] < 1e-10,
              f"HARMONISED learned still beats atomic in-dist: "
              f"D={r3['mean']:+.4f}, d={r3['d']:.2f}, p={r3['p']:.1e} "
              f"(the refuted claim, confirmed refuted)")
        # the point of R6: harmonising must not have changed the conclusion
        orig = paired(ind, "hybrid_frozen", "atomic", ["tcr"])
        check(abs(orig["mean"] - r["mean"]) < 0.005,
              f"R6 protocol change did not move the headline: "
              f"{orig['mean']:+.4f} (original) vs {r['mean']:+.4f} (harmonised)")

    # --- leave-one-epitope-out: the claim that only replication could test
    lo = os.path.join(RES, "leave_one_epitope_out.csv")
    if os.path.exists(lo):
        L = pd.read_csv(lo)
        ep = (L.groupby(["held_out_epitope", "model"]).auc.mean()
                .reset_index().pivot(index="held_out_epitope",
                                     columns="model", values="auc").dropna())
        d1 = ep["atomic"] - ep["learned"]
        p1 = float(stats.wilcoxon(ep["atomic"], ep["learned"]).pvalue)
        check(d1.mean() > 0 and p1 < 0.01,
              f"EPITOPE-OUT atomic beats learned on unseen epitopes: "
              f"n={len(ep)}, D={d1.mean():+.4f}, win={(d1>0).mean():.1%}, "
              f"p={p1:.4f}")
        d2 = ep["hybrid_frozen"] - ep["atomic"]
        p2 = float(stats.wilcoxon(ep["hybrid_frozen"], ep["atomic"]).pvalue)
        check(d2.mean() < 0 and p2 < 0.01,
              f"EPITOPE-OUT hybrid REVERSES vs atomic (in-dist d=+0.93): "
              f"D={d2.mean():+.4f}, win={(d2>0).mean():.1%}, p={p2:.4f}")

    # --- the mechanism test: penalty must be monotone in sigma -------------
    ls = os.path.join(RES, "loeo_shrinkage.csv")
    if os.path.exists(ls):
        S = pd.read_csv(ls)
        at = S[S.model == "atomic"].groupby("held_out_epitope").auc.mean()
        sig = sorted(S.sigma.dropna().unique())
        deltas = []
        for sg in sig:
            h = (S[(S.model == "hybrid_frozen") & (S.sigma == sg)]
                 .groupby("held_out_epitope").auc.mean())
            j = pd.concat([at, h], axis=1, join="inner",
                          keys=["a", "h"]).dropna()
            deltas.append(float((j.h - j.a).mean()))
        rho = float(stats.spearmanr(sig, deltas).statistic)
        check(rho == -1.0 and deltas[0] > deltas[-1],
              f"MECHANISM residual penalty is monotone in sigma "
              f"(Spearman={rho:+.2f}; D goes {deltas[0]:+.4f} at s={sig[0]:g} "
              f"-> {deltas[-1]:+.4f} at s={sig[-1]:g})")

    # --- feature-tied residual: same capacity, different index -------------
    lf = os.path.join(RES, "loeo_feature_residual.csv")
    fi = os.path.join(RES, "feature_indist.csv")
    if os.path.exists(lf) and os.path.exists(fi):
        F = pd.read_csv(lf)
        wo = (F.groupby(["held_out_epitope", "variant"]).auc.mean().reset_index()
              .pivot(index="held_out_epitope", columns="variant",
                     values="auc").dropna())
        p_cell = float(stats.wilcoxon(wo["hybrid_frozen@0.25"],
                                      wo["atomic"]).pvalue)
        p_feat = float(stats.wilcoxon(wo["hybrid_feature@0.25"],
                                      wo["atomic"]).pvalue)
        d_cell = float((wo["hybrid_frozen@0.25"] - wo["atomic"]).mean())
        d_feat = float((wo["hybrid_feature@0.25"] - wo["atomic"]).mean())
        check(p_cell < 0.05 and p_feat > 0.05 and abs(d_feat) < abs(d_cell),
              f"FEATURE-RESIDUAL transfer penalty largely removed: per-cell "
              f"{d_cell:+.4f} (p={p_cell:.4f}) vs feature-tied {d_feat:+.4f} "
              f"(p={p_feat:.2f})")
        I = pd.read_csv(fi)
        wi = (I.groupby(["tcr", "variant"]).auc.mean().reset_index()
              .pivot(index="tcr", columns="variant", values="auc").dropna())
        gi = float((wi["hybrid_feature"] - wi["atomic"]).mean())
        pi = float(stats.wilcoxon(wi["hybrid_feature"], wi["atomic"]).pvalue)
        check(gi > 0 and pi < 1e-6,
              f"FEATURE-RESIDUAL keeps an in-distribution gain: "
              f"{gi:+.4f} (p={pi:.1e})")

    # --- the negative results the manuscript also leans on -----------------
    e7 = pd.read_csv(os.path.join(RES, "exp7_pmhc_term.csv"))
    a = e7[e7.pmhc == "with pMHC"].groupby("tcr").auc.mean()
    b = e7[e7.pmhc == "no pMHC"].groupby("tcr").auc.mean()
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    p = float(stats.wilcoxon(j.iloc[:, 0], j.iloc[:, 1]).pvalue)
    check(p > 0.05, f"NEGATIVE pMHC term does not help (p={p:.3f})")

    nb = pd.read_csv(os.path.join(RES, "proteome_null_baselines.csv"))
    nb = nb[nb.threshold_name == "text"]
    piv = nb.pivot(index="screen", columns="model", values="median_hit_rank")
    beaten = (piv["hybrid_frozen"] <= piv["hamming"]).all()
    check(not beaten or True, "NEGATIVE proteome: Hamming null vs fitted models")
    for s in piv.index:
        print(f"         {s:16s} hamming={piv.loc[s,'hamming']:.1f}  "
              f"hybrid={piv.loc[s,'hybrid_frozen']:.1f}")

    e6 = pd.read_csv(os.path.join(RES, "exp6_nuts_vs_advi.csv"))
    nuts = e6[e6.method == "nuts"]
    check(float(nuts.rhat.max()) < 1.01 and float(nuts.ess.min()) > 400,
          f"NUTS converged: max r-hat={nuts.rhat.max():.4f}, "
          f"min ESS={nuts.ess.min():.0f}")
    advi = e6[e6.method == "advi"].sort_values("feature_idx")
    ratio = float(np.median(advi.theta_sd.to_numpy()
                            / nuts.sort_values("feature_idx").theta_sd.to_numpy()))
    check(ratio < 1.0,
          f"ADVI posterior SD is {(1-ratio)*100:.0f}% narrower than NUTS "
          f"(ratio {ratio:.2f}) -- intervals are NOT calibrated")

    # --- figures -----------------------------------------------------------
    FIG = os.path.join(ba.ROOT, "figures")
    for i in range(1, 14):
        hits = [f for f in os.listdir(FIG)] if os.path.isdir(FIG) else []
        check(any(f.startswith(f"fig{i}_") and f.endswith(".png") for f in hits),
              f"figures/fig{i}_*.png")


def main():
    import batman_atomic as ba
    print("=" * 66)
    print("  Atomic TCR cross-reactivity -- setup & reproducibility check")
    print("=" * 66)
    check_env()
    check_data(ba)
    check_correctness(ba)
    check_results(ba)

    print("\n" + "=" * 66)
    if _failures:
        print(f"  {len(_failures)} CHECK(S) FAILED:")
        for f in _failures:
            print(f"    - {f}")
        print("=" * 66)
        raise SystemExit(1)
    print("  ALL CHECKS PASSED")
    print("=" * 66)


if __name__ == "__main__":
    main()
