"""
fig_derivation.py
=================
Figures 14-16: where phi, theta, M and w actually come from, and what the
fitted values are.

Reads only the cached tables written by ``derive_M_and_w.py`` -- it never
re-fits, so these figures cannot silently disagree with the numbers in
``DERIVATION.md``.

Output: ``figures/fig14_phi_construction.*``
        ``figures/fig15_theta_and_M.*``
        ``figures/fig16_w_profiles.*``

Usage:  python3 5_publication/fig_derivation.py
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
from matplotlib.patches import Rectangle

import batman_atomic as ba

ROOT = ba.ROOT
DER = _os.path.join(ROOT, "results", "derivation")
FIG = _os.path.join(ROOT, "figures")
_os.makedirs(FIG, exist_ok=True)

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
ATOMIC = "#0072B2"
ACCENT = "#D55E00"


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(_os.path.join(FIG, f"{name}.{ext}"))
    plt.close(fig)
    print(f"  wrote figures/{name}.png / .pdf")


def panel(ax, letter, dx=-0.14, dy=1.06):
    ax.text(dx, dy, letter, transform=ax.transAxes,
            fontsize=11, fontweight="bold", va="top", ha="left")


# ======================================================================
# Figure 14 -- how phi is built (chemistry only, no TCR data)
# ======================================================================
def fig14():
    raw = pd.read_csv(f"{DER}/phi_1_raw.csv", index_col=0)
    sub = pd.read_csv(f"{DER}/phi_2_glycine_subtracted.csv", index_col=0)
    z = pd.read_csv(f"{DER}/phi_3_zscored.csv", index_col=0)
    cols = list(z.columns)

    fig = plt.figure(figsize=(7.4, 3.9))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 0.34], hspace=.80, wspace=.30)

    show = ["G", "A", "I", "L", "R", "W"]
    stages = [(raw, "a  RDKit counts, full residue\n     (backbone still included)"),
              (sub, "b  minus glycine = backbone\n     (what the side chain adds)"),
              (z, "c  z-scored -> this is phi\n     (the 20x8 table the model uses)")]

    for i, (tab, title) in enumerate(stages):
        ax = fig.add_subplot(gs[0, i])
        d = tab.loc[show, cols]
        ax.imshow(d.to_numpy(), cmap="RdBu_r",
                  vmin=-abs(d.to_numpy()).max(), vmax=abs(d.to_numpy()).max(),
                  aspect="auto")
        for r in range(len(show)):
            for c in range(len(cols)):
                v = d.iloc[r, c]
                lab = f"{v:.0f}" if i < 2 else f"{v:+.1f}"
                ax.text(c, r, lab, ha="center", va="center", fontsize=5.2)
        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels(cols, rotation=90, fontsize=5.6)
        ax.set_yticks(range(len(show)))
        ax.set_yticklabels(show, fontsize=7)
        ax.set_title(title, loc="left", fontsize=7.2)
        # highlight the I / L rows -- they are identical at every stage
        for rr in (show.index("I"), show.index("L")):
            ax.add_patch(Rectangle((-.5, rr - .5), len(cols), 1, fill=False,
                                   ec=ACCENT, lw=1.3))

    ax = fig.add_subplot(gs[1, :])
    ax.axis("off")
    ax.text(0, 1.10,
            "phi comes from molecular structure alone — no TCR measurement enters it. "
            "That is what lets\nthe model score a residue it has never seen, and what "
            "makes theta interpretable.",
            fontsize=7.8, va="top")
    ax.text(0, .10,
            "I and L (boxed) are structural isomers — identical in all eight descriptors "
            "at every stage, so\nM[I,L] = 0 exactly and the atomic model cannot separate "
            "them (DERIVATION.md §6.2).",
            fontsize=7.6, va="top", color=ACCENT)
    fig.suptitle("Figure 14 — building the atomic representation phi",
                 x=.02, y=1.04, ha="left", fontsize=10, fontweight="bold")
    save(fig, "fig14_phi_construction")


# ======================================================================
# Figure 15 -- fitted theta, and the M it assembles
# ======================================================================
def fig15():
    th = pd.read_csv(f"{DER}/theta.csv")
    M = pd.read_csv(f"{DER}/M_atomic.csv", index_col=0)
    D = ba.load_blosum100_distance()

    fig = plt.figure(figsize=(7.4, 3.6))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1.3, 1], wspace=.46,
                          top=.80)

    # (a) theta with sd
    ax = fig.add_subplot(gs[0, 0])
    t = th.sort_values("theta_mean")
    y = np.arange(len(t))
    signif = t.theta_mean > t.theta_sd
    ax.barh(y, t.theta_mean, xerr=t.theta_sd, height=.68,
            color=[ATOMIC if s else "#BBBBBB" for s in signif],
            error_kw=dict(lw=.9, capsize=2))
    ax.set_yticks(y); ax.set_yticklabels(t.feature, fontsize=7)
    ax.set_xlabel(r"posterior mean $\theta_k$  $\pm$ sd")
    ax.set_title("a  fitted theta", loc="left")
    n_grey = int((~signif).sum())
    ax.text(.97, .04, f"grey: not separable from zero\n({n_grey} of {len(t)})",
            transform=ax.transAxes, ha="right", fontsize=6.2, color="#666666")

    # (b) M heat map
    ax = fig.add_subplot(gs[0, 1])
    im = ax.imshow(M.to_numpy(), cmap="magma_r", aspect="equal")
    ax.set_xticks(range(20)); ax.set_xticklabels(M.columns, fontsize=5.4)
    ax.set_yticks(range(20)); ax.set_yticklabels(M.index, fontsize=5.4)
    ax.set_title("b  assembled M (20x20)", loc="left")
    fig.colorbar(im, ax=ax, shrink=.82, pad=.02).set_label("distance", size=6.5)
    i, l = list(M.index).index("I"), list(M.index).index("L")
    ax.plot(l, i, "o", ms=5, mfc="none", mec="#00E5FF", mew=1.5)
    ax.plot(i, l, "o", ms=5, mfc="none", mec="#00E5FF", mew=1.5)
    ax.text(.5, -.19, "circled: M[I,L] = 0 exactly", transform=ax.transAxes,
            ha="center", fontsize=6.2, color=ACCENT)

    # (c) M vs BLOSUM
    ax = fig.add_subplot(gs[0, 2])
    iu = np.triu_indices(20, 1)
    mv, dv = M.to_numpy()[iu], D[iu]
    ax.scatter(dv, mv, s=9, color=ATOMIC, alpha=.55, lw=0)
    r = np.corrcoef(mv, dv)[0, 1]
    ax.set_xlabel("BLOSUM100 distance"); ax.set_ylabel("atomic  M[a,b]")
    ax.set_title("c  not a re-derived BLOSUM", loc="left")
    ax.text(.05, .93, f"r = {r:.3f}", transform=ax.transAxes,
            fontsize=8.5, fontweight="bold")

    fig.suptitle("Figure 15 — what the model learned: theta, and the M it builds",
                 x=.02, y=.97, ha="left", fontsize=10, fontweight="bold")
    save(fig, "fig15_theta_and_M")


# ======================================================================
# Figure 16 -- fitted positional weights
# ======================================================================
def fig16():
    w = pd.read_csv(f"{DER}/w_per_tcr.csv", index_col=0)
    W = w.to_numpy()

    fig = plt.figure(figsize=(7.4, 3.5))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1, 1], wspace=.42,
                          top=.80)

    # (a) full heat map, TCRs sorted by where their mass sits
    ax = fig.add_subplot(gs[0, 0])
    order = np.argsort((W * np.arange(1, W.shape[1] + 1)).sum(1) / W.sum(1))
    im = ax.imshow(W[order], cmap="viridis", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(W.shape[1]))
    ax.set_xticklabels([str(j + 1) for j in range(W.shape[1])], fontsize=6.5)
    ax.set_xlabel("position in the index peptide")
    ax.set_ylabel(f"TCR  (n = {W.shape[0]}, sorted)")
    ax.set_title("a  every TCR its own profile", loc="left")
    fig.colorbar(im, ax=ax, shrink=.85, pad=.02).set_label("w", size=6.5)

    # (b) distribution per position
    ax = fig.add_subplot(gs[0, 1])
    parts = ax.violinplot([W[:, j] for j in range(W.shape[1])],
                          positions=range(1, W.shape[1] + 1),
                          showmeans=True, widths=.8)
    for b in parts["bodies"]:
        b.set_facecolor(ATOMIC); b.set_alpha(.45); b.set_edgecolor("none")
    for k in ("cbars", "cmins", "cmaxes", "cmeans"):
        parts[k].set_color("#333333"); parts[k].set_linewidth(.9)
    ax.set_xticks(range(1, W.shape[1] + 1))
    ax.set_xlabel("position"); ax.set_ylabel("w")
    ax.set_ylim(0, 1)
    ax.set_title("b  spread is the point", loc="left")
    jmax = int(np.argmax(W.mean(0)))
    ax.text(.03, .95, f"pos {jmax+1}: mean {W[:, jmax].mean():.3f}\n"
                      f"          sd  {W[:, jmax].std():.3f}",
            transform=ax.transAxes, fontsize=6.4, va="top")

    # (c) two named TCRs
    ax = fig.add_subplot(gs[0, 2])
    pick = [t for t in ("a3a", "16A11") if t in w.index][:2]
    if len(pick) < 2:
        pick = list(w.index[:2])
    x = np.arange(1, W.shape[1] + 1)
    for t, col, mk in zip(pick, [ATOMIC, ACCENT], ["o", "s"]):
        ax.plot(x, w.loc[t], mk + "-", color=col, ms=4, label=t)
    ax.set_xticks(x); ax.set_xlabel("position"); ax.set_ylabel("w")
    ax.set_ylim(0, 1); ax.legend(title="TCR", title_fontsize=6.5)
    ax.set_title("c  two receptors, two strategies", loc="left")

    fig.suptitle("Figure 16 — the fitted positional weights w",
                 x=.02, y=.97, ha="left", fontsize=10, fontweight="bold")
    save(fig, "fig16_w_profiles")


if __name__ == "__main__":
    print("building derivation figures from results/derivation/ ...")
    fig14(); fig15(); fig16()
    print("done")
