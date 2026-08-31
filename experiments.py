"""
experiments.py
==============
Full-scale benchmark experiments for the atomic-representation TCR model.

Every experiment writes a tidy CSV to ``results/`` and reuses it on the next
call, so re-running the notebook is instant and a long run can be resumed
after an interruption. Delete a file in ``results/`` to force recomputation.

Experiment map
--------------
exp1_cross_validation      5-fold CV, all TCRs                 (in-distribution)
exp2_leave_chemistry_out   hold out a whole chemical class     (OOD substitutions)
exp3_feature_ablation      does adding hydrophobicity help?
exp4_novel_tcr             TCR-grouped folds, pan-TCR weights  (OOD receptors)
exp5_multi_mutant          train single-aa -> test multi-aa    (OOD peptides)
exp6_nuts_vs_advi          does the variational approximation hold up?
exp7_pmhc_term             does NetMHCpan binding level help?
"""

from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd

import batman_atomic as ba

RESULTS_DIR = os.path.join(ba.ROOT, "results")



#: Chemical classes held out wholesale in the leave-chemistry-out benchmark.
CHEM_GROUPS = {
    "aromatic (W/F/Y)": set("WFY"),
    "charged (D/E/K/R)": set("DEKR"),
    "aliphatic (I/L/V/M)": set("ILVM"),
    "small (A/G/S/T)": set("AGST"),
}

MODEL_LABEL = {
    "fixed": "Fixed BLOSUM100",
    "learned": "Learned 20x20 (BATMAN)",
    "atomic": "Atomic (proposed)",
}


# --------------------------------------------------------------------------
# Infrastructure
# --------------------------------------------------------------------------

def _cache(name: str) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    return os.path.join(RESULTS_DIR, name)


def cached(name: str, compute, force: bool = False, verbose: bool = True):
    """Return a cached DataFrame, computing and saving it when absent."""
    path = _cache(name)
    if os.path.exists(path) and not force:
        if verbose:
            print(f"[cache] loaded {name}")
        return pd.read_csv(path)
    if verbose:
        print(f"[run  ] computing {name} ...")
    t0 = time.time()
    df = compute()
    df.to_csv(path, index=False)
    if verbose:
        print(f"[done ] {name} in {time.time() - t0:.0f}s -> {path}")
    return df


def length_groups(df: pd.DataFrame, phi: np.ndarray, min_tcr: int = 1):
    """Yield (L, subframe, arrays) for each index-peptide length.

    Positional weights are length-specific, so each length is a separate model.
    Pooling still happens *within* a length across all its TCRs.
    """
    valid = (df.peptide.str.len() == df.index_peptide.str.len())
    df = df[valid]
    for L in sorted(df.index_peptide.str.len().unique()):
        sub = df[df.index_peptide.str.len() == L]
        ok = (sub.peptide.apply(lambda s: all(c in ba.AA_IDX for c in s))
              & sub.index_peptide.apply(lambda s: all(c in ba.AA_IDX for c in s)))
        sub = sub[ok].reset_index(drop=True)
        if sub.tcr.nunique() < min_tcr or len(sub) < 30:
            continue
        yield int(L), sub, ba.prepare(sub, phi)


def _mutant_residue(sub: pd.DataFrame) -> np.ndarray:
    """Residue that each single-aa mutant carries at its mutated position."""
    pos = sub.mutation_position.to_numpy(dtype=int)
    pep = sub.peptide.to_numpy()
    return np.array(["-" if p == 0 else pep[i][p - 1] for i, p in enumerate(pos)])


def _fit_predict(kind, arrays, train_rows, test_rows, D, *,
                 use_mhc=False, pan_tcr=False, n_iter=12000, seed=0,
                 method="advi"):
    """Fit on train_rows, return per-TCR AUCs and overall AUC on test_rows."""
    model = ba.build_model(kind, ba.subset(arrays, train_rows), D,
                           use_mhc=use_mhc, pan_tcr=pan_tcr)
    post = ba.fit(model, method=method, n_iter=n_iter, seed=seed)
    test = ba.subset(arrays, test_rows)
    dist = ba.posterior_distance(kind, post, test, D,
                                 use_mhc=use_mhc, pan_tcr=pan_tcr)
    return ba.per_tcr_auc(test, dist), ba.mean_pairwise_auc(test["y"], dist), post


# --------------------------------------------------------------------------
# Experiment 1 -- in-distribution 5-fold cross-validation, all TCRs
# --------------------------------------------------------------------------

def exp1_cross_validation(df, phi, D, kinds=("fixed", "learned", "atomic"),
                          n_iter=12000, force=False):
    def compute():
        rows = []
        for L, sub, arrays in length_groups(df, phi):
            fold = sub.training_fold.to_numpy()
            is_index = sub.mutation_position.to_numpy() == 0
            for f in range(5):
                test_m = fold == f
                if test_m.sum() < 10:
                    continue
                train_rows = np.where(~test_m | is_index)[0]
                test_rows = np.where(test_m)[0]
                for kind in kinds:
                    per_tcr, overall, _ = _fit_predict(
                        kind, arrays, train_rows, test_rows, D,
                        n_iter=n_iter, seed=f)
                    for tcr, auc in per_tcr.items():
                        rows.append(dict(model=kind, L=L, fold=f,
                                         tcr=tcr, auc=auc))
                print(f"  L={L} fold={f} done")
        return pd.DataFrame(rows)

    return cached("exp1_cross_validation.csv", compute, force)


# --------------------------------------------------------------------------
# Experiment 2 -- leave-chemistry-out
# --------------------------------------------------------------------------

def exp2_leave_chemistry_out(df, phi, D, kinds=("fixed", "learned", "atomic"),
                             n_iter=12000, force=False,
                             cache_name="exp2_leave_chemistry_out.csv",
                             phi_label="base8"):
    def compute():
        rows = []
        for L, sub, arrays in length_groups(df, phi):
            mut_aa = _mutant_residue(sub)
            pos = sub.mutation_position.to_numpy(dtype=int)
            for gname, held in CHEM_GROUPS.items():
                test_m = np.array([m in held for m in mut_aa])
                train_m = (~test_m) & (pos > 0)
                if test_m.sum() < 20 or train_m.sum() < 50:
                    continue
                tr, te = np.where(train_m)[0], np.where(test_m)[0]
                for kind in kinds:
                    per_tcr, overall, _ = _fit_predict(
                        kind, arrays, tr, te, D, n_iter=n_iter, seed=0)
                    for tcr, auc in per_tcr.items():
                        rows.append(dict(model=kind, features=phi_label,
                                         L=L, group=gname, tcr=tcr, auc=auc))
                print(f"  L={L} {gname} done")
        return pd.DataFrame(rows)

    return cached(cache_name, compute, force)


# --------------------------------------------------------------------------
# Experiment 3 -- feature ablation (atomic only, richer feature sets)
# --------------------------------------------------------------------------

def exp3_feature_ablation(df, D, feature_sets=("plus_logp", "full11"),
                          n_iter=12000, force=False):
    def compute():
        frames = []
        for fs in feature_sets:
            phi_fs = ba.build_atomic_features(fs).to_numpy()
            part = exp2_leave_chemistry_out(
                df, phi_fs, D, kinds=("atomic",), n_iter=n_iter,
                cache_name=f"_exp3_{fs}.csv", phi_label=fs)
            frames.append(part)
        return pd.concat(frames, ignore_index=True)

    return cached("exp3_feature_ablation.csv", compute, force)


# --------------------------------------------------------------------------
# Experiment 4 -- generalization to unseen TCRs (grouped folds, pan-TCR)
# --------------------------------------------------------------------------

def exp4_novel_tcr(df, phi, D, kinds=("fixed", "learned", "atomic"),
                   n_folds=5, n_iter=12000, force=False):
    """Hold out whole TCRs, not rows.

    Test TCRs are unseen, so a shared (pan-TCR) positional weight profile is
    used -- this is the leave-one-TCR-out regime of the paper, run as grouped
    folds so the cost stays proportional to n_folds rather than to n_TCRs.
    """
    def compute():
        rng = np.random.default_rng(0)
        rows = []
        for L, sub, arrays in length_groups(df, phi, min_tcr=5):
            tcrs = np.array(sorted(sub.tcr.unique()))
            assign = rng.permutation(len(tcrs)) % n_folds
            tcr_fold = dict(zip(tcrs, assign))
            fold_of_row = sub.tcr.map(tcr_fold).to_numpy()
            pos = sub.mutation_position.to_numpy(dtype=int)
            for f in range(n_folds):
                test_m = fold_of_row == f
                train_m = (~test_m) & (pos > 0)
                if test_m.sum() < 20 or train_m.sum() < 50:
                    continue
                tr, te = np.where(train_m)[0], np.where(test_m)[0]
                for kind in kinds:
                    per_tcr, overall, _ = _fit_predict(
                        kind, arrays, tr, te, D, pan_tcr=True,
                        n_iter=n_iter, seed=f)
                    for tcr, auc in per_tcr.items():
                        rows.append(dict(model=kind, L=L, fold=f,
                                         tcr=tcr, auc=auc))
                print(f"  L={L} tcr-fold={f} done")
        return pd.DataFrame(rows)

    return cached("exp4_novel_tcr.csv", compute, force)


# --------------------------------------------------------------------------
# Experiment 5 -- multi-amino-acid mutants (a genuinely separate dataset)
# --------------------------------------------------------------------------

def exp5_multi_mutant(df, mh, phi, D, kinds=("fixed", "learned", "atomic"),
                      n_iter=12000, force=False):
    """Train on single-aa scans, test on peptides carrying 2+ substitutions."""
    def compute():
        rows = []
        for L in sorted(mh.index_peptide.str.len().unique()):
            mh_L = mh[mh.index_peptide.str.len() == L]
            sub = df[(df.index_peptide.str.len() == L)
                     & (df.peptide.str.len() == L)]
            ok = (sub.peptide.apply(lambda s: all(c in ba.AA_IDX for c in s))
                  & sub.index_peptide.apply(lambda s: all(c in ba.AA_IDX for c in s)))
            sub = sub[ok].reset_index(drop=True)
            shared = sorted(set(mh_L.tcr) & set(sub.tcr))
            if not shared or len(sub) < 50:
                continue
            mh_L = mh_L[mh_L.tcr.isin(shared)].reset_index(drop=True)

            # One shared TCR indexing so train and test rows line up.
            tcr_index = {t: i for i, t in enumerate(sorted(sub.tcr.unique()))}
            train_arr = ba.prepare(sub, phi, tcr_index=tcr_index)
            test_arr = ba.prepare(mh_L, phi, tcr_index=tcr_index)

            for kind in kinds:
                model = ba.build_model(kind, train_arr, D)
                post = ba.fit(model, n_iter=n_iter, seed=0)
                dist = ba.posterior_distance(kind, post, test_arr, D)
                for tcr, auc in ba.per_tcr_auc(test_arr, dist).items():
                    rows.append(dict(model=kind, L=L, tcr=tcr, auc=auc))
                rows.append(dict(model=kind, L=L, tcr="__overall__",
                                 auc=ba.mean_pairwise_auc(test_arr["y"], dist)))
            print(f"  L={L} multi-mutant done ({len(mh_L)} test rows)")
        return pd.DataFrame(rows)

    return cached("exp5_multi_mutant.csv", compute, force)


# --------------------------------------------------------------------------
# Experiment 6 -- NUTS vs ADVI
# --------------------------------------------------------------------------

def exp6_nuts_vs_advi(df, phi, D, L_target=13, max_tcr=12,
                      n_iter=12000, advi_draws=1000,
                      nuts_draws=1500, nuts_tune=1500, nuts_chains=4,
                      force=False):
    """Refit one group with full MCMC to check the variational approximation.

    NUTS is run with enough chains/draws to yield trustworthy r-hat and ESS;
    both diagnostics are stored so the comparison can be judged rather than
    assumed. A short NUTS run would make ADVI look good for the wrong reason.
    """
    def compute():
        import arviz as az

        sub = df[(df.index_peptide.str.len() == L_target)
                 & (df.peptide.str.len() == L_target)]
        ok = (sub.peptide.apply(lambda s: all(c in ba.AA_IDX for c in s))
              & sub.index_peptide.apply(lambda s: all(c in ba.AA_IDX for c in s)))
        sub = sub[ok]
        keep = sub.tcr.value_counts().index[:max_tcr]
        sub = sub[sub.tcr.isin(keep)].reset_index(drop=True)
        arrays = ba.prepare(sub, phi)
        fold = sub.training_fold.to_numpy()
        is_index = sub.mutation_position.to_numpy() == 0
        tr = np.where((fold != 0) | is_index)[0]
        te = np.where(fold == 0)[0]

        rows = []
        for method in ("advi", "nuts"):
            model = ba.build_model("atomic", ba.subset(arrays, tr), D)
            if method == "advi":
                post = ba.fit(model, method="advi", n_iter=n_iter,
                              draws=advi_draws, seed=0)
                rhat = ess = None
            else:
                post = ba.fit(model, method="nuts", draws=nuts_draws,
                              tune=nuts_tune, chains=nuts_chains, seed=0)
                rhat = az.rhat(post, var_names=["theta"])["theta"].values
                ess = az.ess(post, var_names=["theta"])["theta"].values

            test = ba.subset(arrays, te)
            dist = ba.posterior_distance("atomic", post, test, D)
            auc = ba.mean_pairwise_auc(test["y"], dist)
            theta = post.posterior["theta"]
            mean = theta.mean(("chain", "draw")).values
            sd = theta.std(("chain", "draw")).values
            for k in range(len(mean)):
                rows.append(dict(
                    method=method, feature_idx=k,
                    theta_mean=mean[k], theta_sd=sd[k], auc=auc,
                    rhat=(np.nan if rhat is None else rhat[k]),
                    ess=(np.nan if ess is None else ess[k])))
            print(f"  {method} done"
                  + ("" if rhat is None
                     else f" (max r-hat {rhat.max():.3f}, min ESS {ess.min():.0f})"))
        return pd.DataFrame(rows)

    return cached("exp6_nuts_vs_advi.csv", compute, force)


# --------------------------------------------------------------------------
# Experiment 7 -- does the pMHC binding term help?
# --------------------------------------------------------------------------

def exp7_pmhc_term(df, phi, D, n_iter=12000, force=False):
    def compute():
        rows = []
        for L, sub, arrays in length_groups(df, phi):
            if arrays.get("mhc") is None:
                continue
            fold = sub.training_fold.to_numpy()
            is_index = sub.mutation_position.to_numpy() == 0
            for f in range(5):
                test_m = fold == f
                if test_m.sum() < 10:
                    continue
                tr = np.where(~test_m | is_index)[0]
                te = np.where(test_m)[0]
                for use_mhc in (False, True):
                    per_tcr, overall, _ = _fit_predict(
                        "atomic", arrays, tr, te, D, use_mhc=use_mhc,
                        n_iter=n_iter, seed=f)
                    for tcr, auc in per_tcr.items():
                        rows.append(dict(model="atomic",
                                         pmhc="with pMHC" if use_mhc else "no pMHC",
                                         L=L, fold=f, tcr=tcr, auc=auc))
                print(f"  L={L} fold={f} pmhc done")
        return pd.DataFrame(rows)

    return cached("exp7_pmhc_term.csv", compute, force)


# --------------------------------------------------------------------------
# Aggregation helpers
# --------------------------------------------------------------------------

def summarize(long_df: pd.DataFrame, by: str = "model",
              within: list[str] | None = None) -> pd.DataFrame:
    """Average per-TCR AUCs (over folds) then bootstrap a CI of the mean."""
    keys = [by] + (within or [])
    per_tcr = long_df.groupby(keys + ["tcr"], as_index=False).auc.mean()
    out = []
    for vals, grp in per_tcr.groupby(keys):
        vals = vals if isinstance(vals, tuple) else (vals,)
        mean, lo, hi = ba.bootstrap_ci(grp.auc.values)
        out.append(dict(zip(keys, vals),
                        n_tcr=len(grp), mean_auc=mean, ci_low=lo, ci_high=hi))
    return pd.DataFrame(out)


def compare_models(long_df: pd.DataFrame, a: str, b: str,
                   within: list[str] | None = None) -> dict:
    """Paired Wilcoxon between two models over their shared TCRs."""
    keys = (within or []) + ["tcr"]
    per_tcr = long_df.groupby(["model"] + keys, as_index=False).auc.mean()

    def as_dict(model):
        sel = per_tcr[per_tcr.model == model]
        idx = sel[keys].astype(str).agg("|".join, axis=1)
        return dict(zip(idx, sel.auc))

    return ba.paired_wilcoxon(as_dict(a), as_dict(b))
