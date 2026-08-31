"""
schematic.py
============
The two explanatory figures a reader needs before any result makes sense:

  fig1_overview.png      the biology and the data -- what a TCR recognises,
                         what a mutational scan measures, what BATCAVE holds
  fig2_architecture.png  the model -- how a peptide becomes a probability,
                         and exactly which piece this work replaces

Panel 1b plots a REAL scan (the a3a / MAGE-A3 TCR), not a cartoon, so the
reader sees the actual signal the model is fitted to.

Usage:  python3 schematic.py
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
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import (FancyBboxPatch, FancyArrowPatch, Circle,
                                Rectangle, Polygon)
from matplotlib.colors import ListedColormap, BoundaryNorm

import batman_atomic as ba

os = _os
FIG = os.path.join(ba.ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

mpl.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "axes.titleweight": "bold", "axes.spines.top": False,
    "axes.spines.right": False, "axes.linewidth": .8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "legend.frameon": False,
})

C = {"atom": "#0072B2", "signal": "#D55E00", "accent": "#009E73",
     "prior": "#E69F00", "null": "#CC79A7", "grey": "#8A9997",
     "ink": "#1B2426", "faint": "#E3EAE8", "mid": "#B9C6C3"}
ACT = ["#DCE4E2", "#E9B26B", "#C0392B"]        # none / weak / strong


def panel(ax, letter, dx=-.04, dy=1.02):
    ax.text(dx, dy, letter, transform=ax.transAxes, fontsize=11,
            fontweight="bold", va="bottom", ha="left")


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(FIG, f"{name}.{ext}"))
    plt.close(fig)
    print(f"  wrote figures/{name}.png / .pdf")


# ==========================================================================
#  drawing helpers -- schematic cell biology
# ==========================================================================
def membrane(ax, y, x0, x1, color, label, flip=False):
    """A lipid bilayer drawn as a band of head groups."""
    h = .28
    ax.add_patch(Rectangle((x0, y - h / 2), x1 - x0, h, facecolor=color,
                           edgecolor="none", alpha=.30, zorder=1))
    n = int((x1 - x0) / .34)
    for i in range(n + 1):
        x = x0 + i * (x1 - x0) / max(n, 1)
        ax.add_patch(Circle((x, y + (h / 2 if not flip else -h / 2)), .075,
                            facecolor=color, edgecolor="none", zorder=2))
        ax.add_patch(Circle((x, y - (h / 2 if not flip else -h / 2)), .075,
                            facecolor=color, edgecolor="none", zorder=2))
    if label:
        ax.text(x0 + .1, y + (-.62 if flip else .62), label, ha="left",
                va="center", fontsize=7.5, color=color, fontweight="bold")


def mhc(ax, cx, cy):
    """MHC class I: two alpha helices forming a groove, on a stalk."""
    ax.add_patch(FancyBboxPatch((cx - .95, cy - 1.5), 1.9, 1.05,
                                boxstyle="round,pad=.06,rounding_size=.18",
                                facecolor=C["faint"], edgecolor=C["mid"],
                                lw=.9, zorder=3))
    ax.text(cx, cy - 1.0, "MHC", ha="center", va="center", fontsize=7.5,
            color=C["ink"], fontweight="bold")
    for sx in (-1, 1):                                   # the two helices
        ax.add_patch(FancyBboxPatch((cx + sx * .62 - .34, cy - .30), .68, .52,
                                    boxstyle="round,pad=.05,rounding_size=.24",
                                    facecolor=C["mid"], edgecolor="none",
                                    zorder=4))
    ax.text(cx - 1.30, cy + .02, "α1", ha="center", va="center", fontsize=6.5,
            color=C["grey"])
    ax.text(cx + 1.30, cy + .02, "α2", ha="center", va="center", fontsize=6.5,
            color=C["grey"])


def peptide(ax, cx, cy, seq, mutated=None, r=.175, gap=.40):
    """The presented peptide, one circle per residue."""
    n = len(seq)
    x0 = cx - (n - 1) * gap / 2
    for i, aa in enumerate(seq):
        hot = mutated is not None and i == mutated
        ax.add_patch(Circle((x0 + i * gap, cy), r,
                            facecolor=C["signal"] if hot else "#FFFFFF",
                            edgecolor=C["signal"] if hot else C["ink"],
                            lw=1.5 if hot else .9, zorder=6))
        ax.text(x0 + i * gap, cy, aa, ha="center", va="center",
                fontsize=6.2, color="#FFFFFF" if hot else C["ink"],
                fontweight="bold", zorder=7)
    return x0


def tcr(ax, cx, cy, color):
    """TCR alpha/beta heterodimer reaching down onto the peptide."""
    for sx, lab in ((-1, "α"), (1, "β")):
        ax.add_patch(Polygon([[cx + sx * .12, cy - .55],
                              [cx + sx * .58, cy + .95],
                              [cx + sx * 1.02, cy + .95],
                              [cx + sx * .52, cy - .55]],
                             closed=True, facecolor=color, alpha=.22,
                             edgecolor=color, lw=1.0, zorder=3))
        ax.text(cx + sx * .74, cy + .42, lab, ha="center", va="center",
                fontsize=7, color=color, fontweight="bold")
    for sx in (-1, 1):                                   # CDR loops
        ax.add_patch(Circle((cx + sx * .30, cy - .60), .13,
                            facecolor=color, edgecolor="none", zorder=5))
    ax.text(cx, cy - .95, "CDR loops", ha="center", va="center", fontsize=6.3,
            color=color)


# ==========================================================================
#  FIGURE 1 -- the biology and the data
# ==========================================================================
def fig1():
    fig = plt.figure(figsize=(7.2, 6.0))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.05, 1],
                          width_ratios=[1.25, 1], hspace=.34, wspace=.26)

    # ---------------- (a) recognition ------------------------------------
    ax = fig.add_subplot(gs[0, :])
    ax.set_xlim(0, 20); ax.set_ylim(-3.7, 4.5); ax.axis("off")
    ax.text(.0, 1.0, "a", transform=ax.transAxes, fontsize=11,
            fontweight="bold", va="bottom")
    ax.text(.035, 1.0, "How a T cell reads a peptide", transform=ax.transAxes,
            fontsize=9, fontweight="bold", va="bottom")

    for cx, x0, x1, mut, cap in (
            (4.5, .4, 8.6, None,
             "peptide sits in the MHC groove;\nthe TCR reads its exposed face"),
            (15.3, 11.2, 19.4, 5,
             "change ONE residue and recognition\ncan vanish — or survive intact")):
        membrane(ax, 3.5, x0, x1, C["atom"], "", flip=True)
        tcr(ax, cx, 2.05, C["atom"])
        mhc(ax, cx, .55)
        peptide(ax, cx, .55, "EVDPIGHLY", mutated=mut)
        membrane(ax, -1.95, x0, x1, C["grey"], "")
        ax.text(cx, -3.05, cap, ha="center", va="center", fontsize=7.2,
                color=C["ink"])
    ax.text(.6, 3.9, "T cell", fontsize=7.5, color=C["atom"], fontweight="bold")
    ax.text(.6, -2.5, "antigen-presenting cell", fontsize=7.5, color=C["grey"],
            fontweight="bold")

    ax.add_patch(FancyArrowPatch((9.3, .55), (10.5, .55),
                                 arrowstyle="-|>", mutation_scale=13,
                                 lw=1.3, color=C["signal"], zorder=8))
    ax.text(9.9, 1.15, "1 substitution", ha="center", fontsize=7,
            color=C["signal"], fontweight="bold")

    # ---------------- (b) a real mutational scan --------------------------
    ax = fig.add_subplot(gs[1, 0])
    df = ba.load_batcave()
    sub = df[df.tcr == "a3a"]
    idx = sub.index_peptide.iloc[0]
    M = np.full((20, len(idx)), np.nan)
    for _, r in sub.iterrows():
        p = int(r.mutation_position)
        if p == 0:
            continue
        M[ba.AA_IDX[r.peptide[p - 1]], p - 1] = r.activation

    cmap = ListedColormap(ACT)
    ax.imshow(M, cmap=cmap, norm=BoundaryNorm([-.5, .5, 1.5, 2.5], 3),
              aspect="auto", interpolation="nearest")
    for j, aa in enumerate(idx):                       # mark the index residue
        ax.add_patch(Rectangle((j - .5, ba.AA_IDX[aa] - .5), 1, 1,
                               facecolor="none", edgecolor=C["ink"], lw=1.4))
    ax.set_xticks(range(len(idx)))
    ax.set_xticklabels(list(idx), fontsize=7.5, fontweight="bold")
    ax.set_yticks(range(20)); ax.set_yticklabels(ba.AA20, fontsize=5.6)
    ax.set_xlabel("position in the index peptide", labelpad=2)
    ax.set_ylabel("substituted to")
    ax.set_title("What one experiment measures", loc="left", pad=13)
    ax.text(0, 1.015, "TCR a3a · MAGE-A3 · all 19 substitutions at every position",
            transform=ax.transAxes, fontsize=6.5, color=C["grey"])
    handles = [Rectangle((0, 0), 1, 1, facecolor=c, edgecolor="none")
               for c in ACT]
    handles.append(Rectangle((0, 0), 1, 1, facecolor="none",
                             edgecolor=C["ink"], lw=1.4))
    ax.legend(handles, ["no activation", "weak", "strong", "index residue"],
              fontsize=6.2, ncol=2, loc="upper center",
              bbox_to_anchor=(.5, -.20), handlelength=1.1)
    panel(ax, "b", dx=-.22)

    # ---------------- (c) what the database holds -------------------------
    ax = fig.add_subplot(gs[1, 1]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_title("Scaled up: the BATCAVE database", loc="left")

    rows = [("151", "TCRs"), ("22,827", "measured peptides"),
            ("25", "index peptides"), ("22", "publications"),
            ("15", "MHC alleles")]
    for i, (v, k) in enumerate(rows):
        y = .88 - i * .155
        ax.text(.02, y, v, fontsize=15, fontweight="bold", va="center",
                color=C["ink"], family="sans-serif")
        ax.text(.42, y, k, fontsize=8, va="center", color=C["grey"])

    ax.plot([.02, .98], [.09, .09], color=C["faint"], lw=1)
    counts = [9161, 5838, 7828]
    tot = sum(counts); x = .02
    for c, col, lab in zip(counts, ACT, ["none", "weak", "strong"]):
        w = .96 * c / tot
        ax.add_patch(Rectangle((x, .015), w, .055, facecolor=col,
                               edgecolor="none"))
        ax.text(x + w / 2, -.045, f"{lab}\n{c:,}", ha="center", va="top",
                fontsize=6, color=C["grey"])
        x += w
    ax.text(.02, .155, "activation labels across the database",
            fontsize=6.8, color=C["grey"])
    panel(ax, "c", dx=-.06)

    save(fig, "fig1_overview")


# ==========================================================================
#  FIGURE 2 -- the model architecture
# ==========================================================================
def box(ax, x, y, w, h, label, sub=None, fc="#FFFFFF", ec=None, lw=1.0,
        fs=8, tc=None):
    ec = ec or C["mid"]
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=.02,rounding_size=.10",
                                facecolor=fc, edgecolor=ec, lw=lw, zorder=3))
    cx = x + w / 2
    if sub:
        ax.text(cx, y + h - .42, label, ha="center", va="center", fontsize=fs,
                color=tc or C["ink"], fontweight="bold", zorder=4)
        ax.text(cx, y + h - .78, sub, ha="center", va="top", fontsize=6.4,
                color=C["grey"], zorder=4, linespacing=1.45)
    else:
        ax.text(cx, y + h / 2, label, ha="center", va="center", fontsize=fs,
                color=tc or C["ink"], fontweight="bold", zorder=4)


def arrow(ax, x0, y0, x1, y1, color=None, lw=1.2, style="-|>"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style,
                                 mutation_scale=11, lw=lw,
                                 color=color or C["grey"], zorder=2))


def fig2():
    fig = plt.figure(figsize=(7.2, 5.8))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.30, 1], hspace=.26)

    # ---------------- (a) the computational graph -------------------------
    ax = fig.add_subplot(gs[0])
    ax.set_xlim(0, 20); ax.set_ylim(1.05, 6.80); ax.axis("off")
    ax.text(.0, 1.0, "a", transform=ax.transAxes, fontsize=11,
            fontweight="bold", va="bottom")
    ax.text(.035, 1.0, "From two peptides to a probability",
            transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom")

    ax.text(2.6, 6.35, "index peptide", fontsize=7, color=C["grey"], ha="center")
    peptide(ax, 2.6, 5.75, "EVDPIGHLY", r=.17, gap=.42)
    ax.text(2.6, 4.75, "mutant peptide", fontsize=7, color=C["grey"], ha="center")
    peptide(ax, 2.6, 4.15, "EVDPIVHLY", mutated=5, r=.17, gap=.42)

    Y, H = 4.05, 1.75                       # box band
    arrow(ax, 4.55, Y + H / 2, 5.35, Y + H / 2)
    box(ax, 5.45, Y, 3.15, H, "M[a, b]",
        "chemical cost of\nswapping a $\\rightarrow$ b",
        fc="#FDF1E8", ec=C["signal"], lw=1.6, fs=10)
    ax.text(7.02, Y - .34, "THIS WORK REPLACES THIS BOX", ha="center",
            fontsize=6.4, color=C["signal"], fontweight="bold")

    arrow(ax, 8.75, Y + H / 2, 9.45, Y + H / 2)
    box(ax, 9.55, Y, 2.75, H, "$\\times\\ w_j$",
        "how much position\nj matters (per TCR)", ec=C["atom"], lw=1.3, fs=10)

    arrow(ax, 12.45, Y + H / 2, 13.15, Y + H / 2)
    box(ax, 13.25, Y, 2.3, H, "$d=\\sum_j$",
        "total distance\nfrom the index", fs=10)

    arrow(ax, 15.7, Y + H / 2, 16.4, Y + H / 2)
    box(ax, 16.5, Y, 3.3, H, "ordered\nlogistic", None,
        ec=C["accent"], lw=1.3, fs=8.5)

    ax.add_patch(FancyArrowPatch((18.15, Y - .05), (18.15, Y - .55),
                                 arrowstyle="-|>", mutation_scale=10, lw=1.1,
                                 color=C["accent"]))
    for i, (lab, col) in enumerate(zip(["strong", "weak", "none"], ACT[::-1])):
        yy = Y - 1.30 - i * .48
        ax.add_patch(Rectangle((16.6, yy), .85, .34, facecolor=col,
                               edgecolor="none"))
        ax.text(17.62, yy + .17, lab, va="center", fontsize=6.8, color=C["ink"])

    ax.text(.4, 1.35, "all boxes estimated jointly by Bayesian inference "
                      "(ADVI, validated against NUTS)",
            ha="left", va="center", fontsize=6.8, color=C["grey"])

    # ---------------- (b) the four ways to define M -----------------------
    ax = fig.add_subplot(gs[1])
    ax.set_xlim(0, 20); ax.set_ylim(0, 4.2); ax.axis("off")
    ax.text(.0, 1.0, "b", transform=ax.transAxes, fontsize=11,
            fontweight="bold", va="bottom")
    ax.text(.035, 1.0, "Four ways to fill that one box — the only thing that changes",
            transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom")

    models = [
        ("fixed", "BLOSUM100\nlookup table", "0 free\nparameters",
         C["grey"], "off-the-shelf"),
        ("learned", "20×20 table\nfitted to data", "~380 free\nparameters",
         C["signal"], "BATMAN"),
        ("atomic", "8 chemical\nrulers", "8 free\nparameters",
         C["atom"], "this work"),
        ("hybrid", "atomic frozen\n+ small residual", "8 frozen\n+ 400 shrunk",
         C["accent"], "this work"),
    ]
    w = 4.35
    for i, (name, what, params, col, tag) in enumerate(models):
        x = .35 + i * (w + .55)
        ax.add_patch(FancyBboxPatch((x, .55), w, 3.0,
                                    boxstyle="round,pad=.03,rounding_size=.12",
                                    facecolor="#FFFFFF", edgecolor=col,
                                    lw=1.4, zorder=3))
        ax.add_patch(Rectangle((x, 3.28), w, .27, facecolor=col,
                               edgecolor="none", zorder=4))
        ax.text(x + w / 2, 3.41, name, ha="center", va="center", fontsize=8,
                color="#FFFFFF", fontweight="bold", zorder=5)
        ax.text(x + w / 2, 2.55, what, ha="center", va="center", fontsize=8,
                color=C["ink"], zorder=5)
        ax.text(x + w / 2, 1.55, params, ha="center", va="center", fontsize=7.4,
                color=col, fontweight="bold", zorder=5)
        ax.text(x + w / 2, .85, tag, ha="center", va="center", fontsize=6.4,
                color=C["grey"], zorder=5)
    ax.text(10.0, .08, "identical priors, identical likelihood, identical "
                       "positional weights — so any difference in accuracy is "
                       "the representation, and nothing else",
            ha="center", fontsize=6.9, color=C["grey"])

    save(fig, "fig2_architecture")


if __name__ == "__main__":
    print("[schematic]")
    fig1()
    fig2()
    print("done ->", FIG)
