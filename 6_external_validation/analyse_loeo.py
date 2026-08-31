"""
analyse_loeo.py
===============
Summarise the leave-one-epitope-out run and make Figure 11.

The unit of analysis is the **held-out epitope**, not the TCR: each epitope
contributes one number per model (the mean per-TCR AUC on that epitope), and
the paired tests run across epitopes. This is the point of the experiment --
it supplies the replication that the single-epitope Malone validation could
not.

Usage:  python3 analyse_loeo.py
"""

from __future__ import annotations

# --- bootstrap ---
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
import matplotlib as mpl
import matplotlib.pyplot as plt
from scipy import stats

import batman_atomic as ba

RES = _os.path.join(ba.ROOT, "results")
FIG = _os.path.join(ba.ROOT, "figures")
ORDER = ["fixed", "learned", "atomic", "hybrid_frozen"]
C = {"fixed": "#999999", "learned": "#D55E00",
     "atomic": "#0072B2", "hybrid_frozen": "#009E73"}
LAB = {"fixed": "fixed\nBLOSUM100", "learned": "learned\n20×20",
       "atomic": "atomic", "hybrid_frozen": "frozen\nhybrid"}

mpl.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "axes.titleweight": "bold", "axes.spines.top": False,
    "axes.spines.right": False, "axes.linewidth": .8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.frameon": False})


def main():
    d = pd.read_csv(_os.path.join(RES, "leave_one_epitope_out.csv"))

    # one value per (held-out epitope, model)
    per_ep = (d.groupby(["held_out_epitope", "L", "n_tcr", "model"])
                .auc.mean().reset_index())
    wide = per_ep.pivot_table(index=["held_out_epitope", "L", "n_tcr"],
                              columns="model", values="auc").dropna()

    print(f"held-out epitopes: {len(wide)}  "
          f"(TCRs covered: {int(wide.reset_index().n_tcr.sum())})\n")
    print(wide.round(3).to_string())

    print("\n=== mean over held-out epitopes ===")
    for m in ORDER:
        v = wide[m].to_numpy()
        lo, hi = np.percentile(
            np.random.default_rng(0).choice(v, (10000, len(v))).mean(1),
            [2.5, 97.5])
        print(f"  {m:16s} {v.mean():.4f}  95% CI [{lo:.4f}, {hi:.4f}]")

    print(f"\n=== paired across epitopes (n = {len(wide)}) ===")
    rows = []
    for a, b in [("atomic", "fixed"), ("atomic", "learned"),
                 ("hybrid_frozen", "atomic"), ("hybrid_frozen", "learned"),
                 ("learned", "fixed")]:
        diff = wide[a] - wide[b]
        p = stats.wilcoxon(wide[a], wide[b]).pvalue if len(wide) >= 6 else np.nan
        dz = diff.mean() / diff.std(ddof=1)
        rows.append(dict(comparison=f"{a} - {b}", delta=diff.mean(),
                         win=(diff > 0).mean(), d=dz, p=p))
        print(f"  {a:14s} vs {b:14s} D={diff.mean():+.4f}  "
              f"win={100*(diff>0).mean():5.1f}%  d={dz:+.2f}  p={p:.4f}")
    pd.DataFrame(rows).to_csv(
        _os.path.join(RES, "leave_one_epitope_out_summary.csv"), index=False)

    # ---- sensitivity: epitopes with only 1 TCR give a noisy single-TCR AUC,
    # so check the headline contrasts survive dropping them -------------------
    print("\n=== sensitivity to how many TCRs a held-out epitope has ===")
    nt = wide.reset_index().n_tcr.to_numpy()
    for min_tcr in (1, 2, 3):
        sel = wide[nt >= min_tcr]
        if len(sel) < 3:
            continue
        bits = []
        for a, b in [("atomic", "learned"), ("atomic", "fixed"),
                     ("hybrid_frozen", "learned")]:
            diff = sel[a] - sel[b]
            bits.append(f"{a.replace('_frozen','')}−{b} {diff.mean():+.4f} "
                        f"({100*(diff>0).mean():.0f}%)")
        print(f"  >={min_tcr} TCR  (n={len(sel):2d} epitopes)  " + "  ".join(bits))

    # ------------------------------------------------------------------ figure
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0),
                             gridspec_kw=dict(wspace=.34, top=.80,
                                              width_ratios=[1.15, 1]))

    ax = axes[0]
    for i, m in enumerate(ORDER):
        v = wide[m].to_numpy()
        ax.scatter(np.full(len(v), i) + np.random.default_rng(1)
                   .uniform(-.16, .16, len(v)), v, s=18, color=C[m],
                   alpha=.8, edgecolors="none", zorder=3)
        ax.plot([i - .3, i + .3], [v.mean()] * 2, color="k", lw=1.8,
                zorder=4, solid_capstyle="butt")
    # connect each epitope so the paired structure is visible
    for _, r in wide.iterrows():
        ax.plot(range(len(ORDER)), [r[m] for m in ORDER],
                color="#B9C6C3", lw=.5, alpha=.6, zorder=1)
    ax.set_xticks(range(len(ORDER)))
    ax.set_xticklabels([LAB[m] for m in ORDER], fontsize=6.8)
    ax.set_ylabel("mean per-TCR AUC on the held-out epitope")
    ax.axhline(.5, color="k", lw=.6, ls=":")
    ax.set_title(f"Leave-one-epitope-out\n({len(wide)} held-out epitopes)",
                 loc="left")
    ax.text(-.20, 1.22, "a", transform=ax.transAxes, fontsize=11,
            fontweight="bold", va="top")

    ax = axes[1]
    comps = [("atomic", "fixed"), ("atomic", "learned"),
             ("hybrid_frozen", "atomic"), ("hybrid_frozen", "learned")]
    for i, (a, b) in enumerate(comps):
        y = len(comps) - 1 - i
        diff = (wide[a] - wide[b]).to_numpy()
        boot = np.random.default_rng(0).choice(diff, (10000, len(diff))).mean(1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        sig = lo > 0 or hi < 0
        ax.plot([lo, hi], [y, y], color=C[a], lw=2.4,
                solid_capstyle="round", alpha=1.0 if sig else .45)
        ax.scatter([diff.mean()], [y], color=C[a], s=26, zorder=3,
                   alpha=1.0 if sig else .45)
        ax.text(hi + .004, y, "sig." if sig else "n.s.", va="center",
                fontsize=6.6, color=C[a] if sig else "#8A9997")
    ax.axvline(0, color="k", lw=.8, ls="--")
    ax.set_yticks(range(len(comps)))
    ax.set_yticklabels([f"{a.replace('_frozen','')} − {b}"
                        for a, b in comps][::-1], fontsize=6.6)
    ax.set_xlabel("Δ mean per-TCR AUC\n(bootstrap over held-out epitopes)")
    ax.set_title("Paired across epitopes", loc="left")
    ax.text(-.42, 1.22, "b", transform=ax.transAxes, fontsize=11,
            fontweight="bold", va="top")

    for ext in ("png", "pdf"):
        fig.savefig(_os.path.join(FIG, f"fig11_leave_one_epitope_out.{ext}"))
    plt.close(fig)
    print("\nwrote figures/fig11_leave_one_epitope_out.png / .pdf")


if __name__ == "__main__":
    main()
