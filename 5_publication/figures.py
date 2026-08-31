"""
figures.py
==========
Generates every publication figure from the cached results in ``results/``.

Nothing here re-fits a model: figures are a *view* of the cached CSV/NPY files,
so a figure can never silently disagree with the numbers in the manuscript.

Output: ``figures/fig{3..8}_*.png``  (fig1/fig2 come from schematic.py) (300 dpi) and matching ``.pdf`` vectors.

Usage:  python3 figures.py [fig3 fig4 ...]     (default: all)
"""

from __future__ import annotations

# --- bootstrap: shared library lives one level up ---
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
# --- end bootstrap ---

import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from scipy import stats

import batman_atomic as ba

ROOT = ba.ROOT
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

# ---------------------------------------------------------------- style ----
mpl.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "axes.titleweight": "bold", "axes.spines.top": False,
    "axes.spines.right": False, "axes.linewidth": 0.8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "legend.frameon": False, "lines.linewidth": 1.2,
})

# Okabe-Ito colourblind-safe palette
C = {
    "fixed": "#999999", "atchley5": "#E69F00", "atomic": "#0072B2",
    "learned": "#D55E00", "hybrid_frozen": "#009E73", "hamming": "#CC79A7",
}
LABEL = {
    "fixed": "Fixed BLOSUM100", "atchley5": "Atchley-5 (2005)",
    "atomic": "Atomic (8 param.)", "learned": "Learned 20×20 (BATMAN)",
    "hybrid_frozen": "Frozen hybrid", "hamming": "Hamming",
}


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(FIG, f"{name}.{ext}"))
    plt.close(fig)
    print(f"  wrote figures/{name}.png / .pdf")


def panel(ax, letter, dx=-0.16, dy=1.06):
    ax.text(dx, dy, letter, transform=ax.transAxes,
            fontsize=11, fontweight="bold", va="top", ha="left")


def boot_ci(v, n=10000, seed=0):
    rng = np.random.default_rng(seed)
    v = np.asarray(v, float)
    m = rng.choice(v, size=(n, len(v)), replace=True).mean(1)
    return np.percentile(m, [2.5, 97.5])


def per_tcr(df, model, keys):
    """Mean AUC per (TCR[, group]) for one model -- the paired unit."""
    return df[df.model == model].groupby(keys).auc.mean()


def paired(df, m1, m2, keys):
    a, b = per_tcr(df, m1, keys), per_tcr(df, m2, keys)
    j = pd.concat([a, b], axis=1, join="inner", keys=["a", "b"]).dropna()
    d = j.a - j.b
    return dict(n=len(j), delta=d, mean=d.mean(), win=(d > 0).mean(),
                d_cohen=d.mean() / d.std(ddof=1),
                p=stats.wilcoxon(j.a, j.b).pvalue)


def _load(name):
    return pd.read_csv(os.path.join(RES, name))


def _harmonized():
    """Preferred source for the headline benchmark (review item R6)."""
    p = os.path.join(RES, "exp8_harmonized_protocol.csv")
    return pd.read_csv(p) if os.path.exists(p) else None


# ==========================================================================
# Figure 1 -- the representation itself
# ==========================================================================
def fig3():
    phi_df = ba.build_atomic_features("base8")
    phi = phi_df.to_numpy()
    theta = np.load(os.path.join(RES, "theta_9mer.npy"))
    D = ba.load_blosum100_distance()

    M = np.einsum("k,abk->ab", theta, np.abs(phi[:, None, :] - phi[None, :, :]))

    fig = plt.figure(figsize=(7.2, 4.6))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.25, 1], hspace=.55, wspace=.42)

    # (a) atomic feature matrix
    ax = fig.add_subplot(gs[0, :2])
    im = ax.imshow(phi.T, cmap="RdBu_r", vmin=-3, vmax=3, aspect="auto")
    ax.set_xticks(range(20)); ax.set_xticklabels(phi_df.index, fontsize=6.5)
    ax.set_yticks(range(phi.shape[1])); ax.set_yticklabels(phi_df.columns, fontsize=7)
    ax.set_title("Atomic side-chain descriptors  φ (z-scored)", loc="left")
    ax.set_xlabel("amino acid")
    fig.colorbar(im, ax=ax, pad=.012, shrink=.85).set_label("z-score", size=7)
    panel(ax, "a", dx=-0.10)

    # (b) learned theta
    ax = fig.add_subplot(gs[0, 2])
    order = np.argsort(theta)
    ax.barh(np.arange(len(theta)), theta[order], color=C["atomic"], height=.7)
    ax.set_yticks(np.arange(len(theta)))
    ax.set_yticklabels([phi_df.columns[i] for i in order], fontsize=7)
    ax.set_xlabel(r"posterior mean $\theta_k$")
    ax.set_title("Learned feature\nweights (9-mers)", loc="left")
    panel(ax, "b", dx=-0.42)

    # (c) reconstructed M vs BLOSUM100
    ax = fig.add_subplot(gs[1, 0])
    iu = np.triu_indices(20, 1)
    x, y = D[iu], M[iu]
    r = np.corrcoef(x, y)[0, 1]
    ax.scatter(x, y, s=5, alpha=.45, color=C["atomic"], edgecolors="none")
    ax.set_xlabel("BLOSUM100 distance $D[a,b]$")
    ax.set_ylabel("atomic $M[a,b]$")
    ax.set_title(f"Not a BLOSUM copy\nPearson r = {r:.2f}", loc="left")
    panel(ax, "c", dx=-0.30)

    # (d) parameter count -- the hybrid is 8 *unshrunk* backbone weights plus a
    # 400-cell residual held near zero by the shrinkage prior, so it is drawn
    # as a stacked bar rather than credited with 8 parameters.
    ax = fig.add_subplot(gs[1, 1])
    ks = ["fixed", "atomic", "hybrid_frozen", "learned"]
    free = [0.0, 8.0, 8.0, 380.0]          # freely estimated
    shrunk = [0.0, 0.0, 400.0, 0.0]        # estimated but shrunk toward 0
    xs = np.arange(4)
    ax.bar(xs, [max(v, .6) for v in free], color=[C[k] for k in ks], width=.68)
    ax.bar(xs, shrunk, bottom=[max(v, .6) for v in free], width=.68,
           facecolor="none", edgecolor=C["hybrid_frozen"], hatch="///", lw=.8)
    ax.set_yscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels(["fixed", "atomic", "hybrid", "learned"], fontsize=7)
    ax.set_ylabel("parameters in $M$")
    ax.set_title("Model capacity", loc="left")
    for x, f, s in zip(xs, free, shrunk):
        lab = f"{f:.0f}" + (f"+{s:.0f}*" if s else "")
        ax.text(x, (max(f, .6) + s) * 1.18, lab, ha="center", fontsize=6.3)
    ax.set_ylim(.5, 3000)
    ax.text(.02, .93, "* shrunk residual", transform=ax.transAxes, fontsize=5.6,
            color="#444")
    panel(ax, "d", dx=-0.30)

    # (e) the four M definitions
    ax = fig.add_subplot(gs[1, 2]); ax.axis("off")
    ax.text(.10, 1.02, "Substitution distance $M[a,b]$", fontsize=7.6,
            fontweight="bold", va="top")
    rows = [
        ("fixed", r"$D[a,b]$"),
        ("learned", r"$D[a,b]\,(1+\delta_{ab})$"),
        ("atomic", r"$\sum_k \theta_k |\phi_k(a)-\phi_k(b)|$"),
        ("hybrid_frozen", r"atomic$^{\mathrm{frozen}}\! + \delta_{ab}$"),
    ]
    for i, (k, expr) in enumerate(rows):
        y = .78 - i * .20
        ax.add_patch(mpl.patches.Rectangle((0, y - .045), .07, .07, color=C[k],
                                           transform=ax.transAxes, clip_on=False))
        ax.text(.12, y, expr, fontsize=7.5, va="center")
    panel(ax, "e", dx=-0.04, dy=1.12)

    save(fig, "fig3_representation")


# ==========================================================================
# Figure 2 -- headline benchmark
# ==========================================================================
def fig4():
    h = _harmonized()
    if h is not None:
        ind = h[h.setting == "in_distribution"]
        ood = h[h.setting == "leave_chemistry_out"]
        src = "harmonized protocol (mutant rows only)"
    else:                                   # fall back to the original runs
        ind = _load("exp1_cross_validation.csv")
        ood = _load("exp2_leave_chemistry_out.csv")
        hy = _load("hybrid_frozen_s025.csv")
        ind = pd.concat([ind, hy[hy.setting == "in_distribution"]
                         [hy.model == "hybrid_frozen"]], ignore_index=True)
        ood = pd.concat([ood, hy[hy.setting == "leave_chemistry_out"]
                         [hy.model == "hybrid_frozen"]], ignore_index=True)
        src = "original protocol"

    at_cv = _load("review_atchley_cv.csv").rename(columns={"encoding": "model"})
    at_ch = _load("review_atchley_chem.csv").rename(columns={"encoding": "model"})
    ind = pd.concat([ind, at_cv], ignore_index=True)
    ood = pd.concat([ood, at_ch], ignore_index=True)

    models = ["fixed", "atchley5", "atomic", "hybrid_frozen", "learned"]

    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.1),
                             gridspec_kw=dict(width_ratios=[1, 1, 1.05],
                                              wspace=.62, top=.74))

    for ax, df, keys, title, letter in [
        (axes[0], ind, ["tcr"], "In-distribution\n(5-fold CV)", "a"),
        (axes[1], ood, ["tcr", "group"], "Out-of-distribution\n(leave-chemistry-out)", "b"),
    ]:
        present = [m for m in models if m in set(df.model)]
        means, los, his = [], [], []
        for m in present:
            v = per_tcr(df, m, keys).to_numpy()
            means.append(v.mean())
            lo, hi = boot_ci(v)
            los.append(v.mean() - lo); his.append(hi - v.mean())
        ax.bar(range(len(present)), means, yerr=[los, his], capsize=2.5,
               color=[C[m] for m in present], width=.68,
               error_kw=dict(lw=.9, ecolor="#333"))
        ax.set_xticks(range(len(present)))
        ax.set_xticklabels([LABEL[m].split(" (")[0].replace("Fixed ", "")
                            .replace("Learned ", "learned\n")
                            for m in present], rotation=35, ha="right", fontsize=6.5)
        ax.set_ylim(.70, .90)
        ax.set_ylabel("mean per-TCR AUC")
        ax.set_title(title, loc="left")
        ax.axhline(.5, color="k", lw=.5, ls=":")
        for i, m in enumerate(means):
            ax.text(i, m + his[i] + .004, f"{m:.3f}", ha="center", fontsize=6.2)
        panel(ax, letter, dx=-0.30, dy=1.26)

    # (c) paired effect sizes
    ax = axes[2]
    comps = [("atomic", "fixed", ind, ["tcr"], "in-dist"),
             ("atomic", "atchley5", ind, ["tcr"], "in-dist"),
             ("learned", "atomic", ind, ["tcr"], "in-dist"),
             ("hybrid_frozen", "atomic", ind, ["tcr"], "in-dist"),
             ("hybrid_frozen", "atomic", ood, ["tcr", "group"], "OOD"),
             ("hybrid_frozen", "learned", ind, ["tcr"], "in-dist")]
    labels, ds, ps, cols = [], [], [], []
    for m1, m2, df, keys, tag in comps:
        if m1 not in set(df.model) or m2 not in set(df.model):
            continue
        r = paired(df, m1, m2, keys)
        SHORT = {"fixed": "fixed", "atchley5": "Atchley-5", "atomic": "atomic",
                 "learned": "learned", "hybrid_frozen": "hybrid"}
        labels.append(f"{SHORT[m1]} vs {SHORT[m2]}\n[{tag}]")
        ds.append(r["d_cohen"]); ps.append(r["p"]); cols.append(C[m1])
    ypos = np.arange(len(ds))
    ax.barh(ypos, ds, color=cols, height=.62)
    ax.axvline(0, color="k", lw=.7)
    ax.set_yticks(ypos); ax.set_yticklabels(labels, fontsize=5.9)
    ax.invert_yaxis()
    ax.set_xlabel("Cohen's $d$ (paired, per TCR)")
    ax.set_title("Effect size, not just $p$", loc="left")
    for i, (d_, p_) in enumerate(zip(ds, ps)):
        star = "***" if p_ < 1e-3 else "**" if p_ < 1e-2 else "*" if p_ < .05 else "n.s."
        ax.text(d_ + (.03 if d_ >= 0 else -.03), i, star,
                va="center", ha="left" if d_ >= 0 else "right", fontsize=6.5)
    ax.set_xlim(min(ds) - .35, max(ds) + .35)
    panel(ax, "c", dx=-0.46, dy=1.26)

    fig.suptitle(f"Benchmark on BATCAVE — 151 TCRs, {src}",
                 fontsize=9, fontweight="bold", y=1.02, x=.02, ha="left")
    save(fig, "fig4_benchmark")


# ==========================================================================
# Figure 3 -- the frozen-backbone hybrid
# ==========================================================================
def fig5():
    # The hybrid-vs-atomic pairing MUST come from a single run: the hybrid's
    # stage 2 sits on top of that run's stage-1 atomic fit, so pairing it with
    # an atomic fit from a different experiment breaks the pairing and shifts
    # the reported effect. `pair` is that single source; `ind`/`ood` are used
    # only for the model means shown in panel (a).
    h = _harmonized()
    if h is not None:
        ind = h[h.setting == "in_distribution"]
        ood = h[h.setting == "leave_chemistry_out"]
        pair_i, pair_o = ind, ood
    else:
        hy = _load("hybrid_frozen_s025.csv")
        pair_i = hy[hy.setting == "in_distribution"]
        pair_o = hy[hy.setting == "leave_chemistry_out"]
        ind = pd.concat([_load("exp1_cross_validation.csv"),
                         pair_i[pair_i.model == "hybrid_frozen"]], ignore_index=True)
        ood = pd.concat([_load("exp2_leave_chemistry_out.csv"),
                         pair_o[pair_o.model == "hybrid_frozen"]], ignore_index=True)

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.8),
                             gridspec_kw=dict(wspace=.48, top=.76))

    # (a) Pareto plane
    ax = axes[0]
    for m in ["fixed", "atomic", "learned", "hybrid_frozen"]:
        if m not in set(ind.model) or m not in set(ood.model):
            continue
        x = per_tcr(ind, m, ["tcr"]).mean()
        y = per_tcr(ood, m, ["tcr", "group"]).mean()
        ax.scatter(x, y, s=70, color=C[m], zorder=3,
                   edgecolors="white", linewidths=1.1)
        ax.annotate(LABEL[m].split(" (")[0], (x, y), textcoords="offset points",
                    xytext=(0, -13), ha="center", fontsize=6.3)
    # arrow atomic -> hybrid
    if "hybrid_frozen" in set(ind.model):
        ax.annotate("", xy=(per_tcr(ind, "hybrid_frozen", ["tcr"]).mean(),
                            per_tcr(ood, "hybrid_frozen", ["tcr", "group"]).mean()),
                    xytext=(per_tcr(ind, "atomic", ["tcr"]).mean(),
                            per_tcr(ood, "atomic", ["tcr", "group"]).mean()),
                    arrowprops=dict(arrowstyle="->", color="#009E73", lw=1.3))
    ax.set_xlabel("in-distribution AUC")
    ax.set_ylabel("out-of-distribution AUC")
    ax.set_title("Pareto plane", loc="left")
    ax.grid(alpha=.18, lw=.5)
    ax.margins(x=.44, y=.30)
    panel(ax, "a", dx=-0.34, dy=1.24)

    # (b) paired gain in-distribution
    ax = axes[1]
    r = paired(pair_i, "hybrid_frozen", "atomic", ["tcr"])
    ax.hist(r["delta"], bins=28, color=C["hybrid_frozen"], alpha=.85)
    ax.axvline(0, color="k", lw=.8, ls="--")
    ax.set_xlabel(r"$\Delta$AUC  (hybrid $-$ atomic)")
    ax.set_ylabel("TCRs")
    ax.set_title(f"In-distribution gain\n$d$={r['d_cohen']:.2f}, "
                 f"{r['win']*100:.1f}% of TCRs, $p$={r['p']:.0e}", loc="left")
    panel(ax, "b", dx=-0.32, dy=1.24)

    # (c) OOD is not paid for
    ax = axes[2]
    r2 = paired(pair_o, "hybrid_frozen", "atomic", ["tcr", "group"])
    ax.hist(r2["delta"], bins=28, color=C["atomic"], alpha=.85)
    ax.axvline(0, color="k", lw=.8, ls="--")
    ax.set_xlabel(r"$\Delta$AUC  (hybrid $-$ atomic)")
    ax.set_ylabel("TCR × chemistry group")
    ax.set_title(f"OOD cost ≈ 0\n$d$={r2['d_cohen']:.2f}, $p$={r2['p']:.2f}", loc="left")
    panel(ax, "c", dx=-0.32, dy=1.24)

    save(fig, "fig5_hybrid_pareto")


# ==========================================================================
# Figure 4 -- why the backbone must be frozen
# ==========================================================================
def fig6():
    sw = _load("review_hybrid_shrinkage.csv")
    ind = sw[sw.setting == "in_distribution"].groupby("shrinkage").auc.mean()
    ood = sw[sw.setting == "leave_chemistry_out"].groupby("shrinkage").auc.mean()

    hy = _load("hybrid_frozen_s025.csv")
    fz_i = hy[(hy.setting == "in_distribution") &
              (hy.model == "hybrid_frozen")].groupby("tcr").auc.mean().mean()
    fz_o = hy[(hy.setting == "leave_chemistry_out") &
              (hy.model == "hybrid_frozen")].groupby(["tcr", "group"]).auc.mean().mean()
    at_i = hy[(hy.setting == "in_distribution") &
              (hy.model == "atomic")].groupby("tcr").auc.mean().mean()
    at_o = hy[(hy.setting == "leave_chemistry_out") &
              (hy.model == "atomic")].groupby(["tcr", "group"]).auc.mean().mean()

    fig, axes = plt.subplots(1, 2, figsize=(6.2, 2.7), gridspec_kw=dict(wspace=.38))

    ax = axes[0]
    ax.plot(ind.index, ind.values, "o-", color="#B03A2E", label="joint hybrid — in-dist")
    ax.plot(ood.index, ood.values, "s--", color="#B03A2E", alpha=.55,
            label="joint hybrid — OOD")
    ax.axhline(at_o, color=C["atomic"], lw=1, ls=":", label="atomic — OOD")
    ax.scatter([.25], [fz_o], marker="*", s=150, color=C["hybrid_frozen"],
               zorder=4, label="frozen hybrid — OOD")
    ax.set_xscale("log")
    ax.set_xticks(list(ind.index))
    ax.set_xticklabels([f"{v:g}" for v in ind.index], fontsize=7)
    ax.minorticks_off()
    ax.set_xlabel(r"residual shrinkage $\sigma$")
    ax.set_ylabel("mean per-TCR AUC")
    ax.set_title("Joint fitting trades OOD away\nat every $\\sigma$", loc="left")
    ax.legend(fontsize=5.8, loc="center right")
    panel(ax, "a", dx=-0.24)

    ax = axes[1]
    labels = ["atomic", "joint hybrid\n(σ=0.25)", "frozen hybrid\n(σ=0.25)"]
    ind_v = [at_i, ind.loc[0.25], fz_i]
    ood_v = [at_o, ood.loc[0.25], fz_o]
    x = np.arange(3); w = .36
    ax.bar(x - w/2, ind_v, w, color=C["hybrid_frozen"], label="in-distribution")
    ax.bar(x + w/2, ood_v, w, color=C["atomic"], label="OOD")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=6.5)
    ax.set_ylim(.74, .88); ax.set_ylabel("mean per-TCR AUC")
    ax.set_title("Freezing keeps both", loc="left")
    ax.legend(fontsize=6.5)
    for xi, (a, b) in enumerate(zip(ind_v, ood_v)):
        ax.text(xi - w/2, a + .003, f"{a:.3f}", ha="center", fontsize=6)
        ax.text(xi + w/2, b + .003, f"{b:.3f}", ha="center", fontsize=6)
    panel(ax, "b", dx=-0.24)

    save(fig, "fig6_shrinkage")


# ==========================================================================
# Figure 5 -- inference check: ADVI vs NUTS
# ==========================================================================
def fig7():
    e6 = _load("exp6_nuts_vs_advi.csv")
    names = ba.FEATURE_SETS["base8"]
    a = e6[e6.method == "advi"].sort_values("feature_idx")
    n = e6[e6.method == "nuts"].sort_values("feature_idx")

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.5), gridspec_kw=dict(wspace=.42))

    ax = axes[0]
    x = np.arange(len(names)); w = .38
    ax.bar(x - w/2, a.theta_mean, w, yerr=a.theta_sd, capsize=2,
           color=C["atomic"], label="ADVI", error_kw=dict(lw=.8))
    ax.bar(x + w/2, n.theta_mean, w, yerr=n.theta_sd, capsize=2,
           color="#444444", label="NUTS", error_kw=dict(lw=.8))
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=40, ha="right", fontsize=6.5)
    ax.set_ylabel(r"$\theta_k$")
    ax.set_title("Posterior means agree", loc="left")
    ax.legend(fontsize=6.5)
    panel(ax, "a", dx=-0.26)

    ax = axes[1]
    r = np.corrcoef(a.theta_mean, n.theta_mean)[0, 1]
    lim = [0, max(a.theta_mean.max(), n.theta_mean.max()) * 1.12]
    ax.plot(lim, lim, "k:", lw=.8)
    ax.scatter(n.theta_mean, a.theta_mean, s=34, color=C["atomic"],
               edgecolors="white", linewidths=.8, zorder=3)
    ax.set_xlabel(r"NUTS  $\theta_k$"); ax.set_ylabel(r"ADVI  $\theta_k$")
    ax.set_title(f"r = {r:.3f}", loc="left")
    ax.set_xlim(lim); ax.set_ylim(lim)
    panel(ax, "b", dx=-0.30)

    ax = axes[2]
    ratio = (a.theta_sd.to_numpy() / n.theta_sd.to_numpy())
    ax.bar(x, ratio, color="#B03A2E", width=.66)
    ax.axhline(1, color="k", lw=.8, ls="--")
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=40, ha="right", fontsize=6.5)
    ax.set_ylabel("SD ratio  ADVI / NUTS")
    ax.set_title(f"ADVI understates uncertainty\nmedian ratio = {np.median(ratio):.2f}",
                 loc="left")
    panel(ax, "c", dx=-0.30)

    save(fig, "fig7_advi_nuts")


# ==========================================================================
# Figure 6 -- proteome-scale retrieval and its null baseline
# ==========================================================================
def fig8():
    screens = [("ctag1b_genome", "CTAG1B\ngenome"),
               ("hiv_genome", "HIV\ngenome"),
               ("hiv_virome", "HIV\nvirome")]
    ticks = [t for _, t in screens]
    nb = _load("proteome_null_baselines.csv")
    nb = nb[nb.threshold_name == "text"]
    nulls = json.load(open(os.path.join(RES, "proteome_null_summary.json")))

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 3.0),
                             gridspec_kw=dict(wspace=.46, top=.74))

    # (a) hit ranks for the hybrid model
    ax = axes[0]
    for i, (key, _) in enumerate(screens):
        s = nulls[key]["text"]["hybrid_frozen"]
        ranks = np.array(s["hit_ranks"], float)
        ax.scatter(np.full(len(ranks), i) + np.random.default_rng(0)
                   .uniform(-.14, .14, len(ranks)), ranks,
                   s=14, color=C["hybrid_frozen"], alpha=.7, edgecolors="none")
        ax.plot([i - .26, i + .26], [np.median(ranks)] * 2, color="k", lw=1.6,
                zorder=4, solid_capstyle="butt")
        ax.plot([i - .26, i + .26], [s["n_scored"] / 2] * 2, color="#B03A2E",
                lw=1.1, ls="--", zorder=4)
    ax.set_yscale("log")
    ax.set_xticks(range(3)); ax.set_xticklabels(ticks, fontsize=6.5)
    ax.set_xlim(-.5, 2.5)
    ax.set_ylabel("rank of a validated hit (log)")
    ax.set_title("Targets retrieved\nat the top", loc="left")
    # black bar = median hit rank, red dashed = chance; stated in the caption
    # rather than a legend, which would sit on top of the data here.
    ax.grid(axis="y", alpha=.18, lw=.5)
    panel(ax, "a", dx=-0.34, dy=1.20)

    # (b) model comparison incl. the learning-free nulls
    ax = axes[1]
    models = ["hamming", "fixed", "learned", "atomic", "hybrid_frozen"]
    width = .16
    for mi, m in enumerate(models):
        vals = [float(nb[(nb.screen == k) & (nb.model == m)].median_hit_rank
                      .iloc[0]) for k, _ in screens]
        ax.bar(np.arange(3) + (mi - 2) * width, vals, width,
               color=C[m], label=LABEL[m].split(" (")[0])
    ax.set_xticks(range(3)); ax.set_xticklabels(ticks, fontsize=6.5)
    ax.set_ylabel("median hit rank (lower = better)")
    ax.set_title("No fitted model beats\nthe Hamming null", loc="left")
    ax.legend(fontsize=5.6, ncol=2, loc="upper right",
              columnspacing=.8, handlelength=1.1, borderaxespad=.15)
    ax.set_ylim(0, 92)
    panel(ax, "b", dx=-0.30, dy=1.20)

    # (c) MHC filter test
    ax = axes[2]
    mf = json.load(open(os.path.join(RES, "mhc_filter_summary.json")))
    labs, tcr_auc, mhc_auc = [], [], []
    for k, lab in screens:
        if k not in mf:
            continue
        e = mf[k]
        labs.append(f"{lab}\n{e['allele'].replace('_', '*')}")
        tcr_auc.append(e["auc_tcr_alone"])
        mhc_auc.append(e["auc_mhc_alone"])
    x = np.arange(len(labs)); w = .36
    ax.bar(x - w/2, tcr_auc, w, color=C["hybrid_frozen"], label="TCR distance")
    ax.bar(x + w/2, mhc_auc, w, color="#8E44AD", label="MHC-II surrogate")
    ax.axhline(.5, color="k", lw=.6, ls=":")
    ax.set_xticks(x); ax.set_xticklabels(labs, fontsize=5.8)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("AUC  (hit vs decoy)")
    ax.set_title("MHC signal is real\nbut predictor-limited", loc="left")
    ax.legend(fontsize=6, loc="lower center", ncol=1)
    panel(ax, "c", dx=-0.30, dy=1.20)

    save(fig, "fig8_proteome")


ALL = dict(fig3=fig3, fig4=fig4, fig5=fig5, fig6=fig6, fig7=fig7, fig8=fig8)

if __name__ == "__main__":
    want = sys.argv[1:] or list(ALL)
    for k in want:
        print(f"[{k}]")
        ALL[k]()
    print("done ->", FIG)
