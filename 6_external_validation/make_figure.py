"""Figure 10 -- external validation on Malone 2025, with its own caveat shown."""
from __future__ import annotations
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
if _os.path.dirname(_os.path.abspath(__file__)) not in _sys.path:
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, matplotlib as mpl, matplotlib.pyplot as plt
from scipy import stats
import batman_atomic as ba, malone2025 as ml

FIG = _os.path.join(ba.ROOT, "figures"); RES = _os.path.join(ba.ROOT, "results")
mpl.rcParams.update({"figure.dpi":120,"savefig.dpi":300,"savefig.bbox":"tight",
    "font.family":"sans-serif","font.sans-serif":["Helvetica Neue","Helvetica","Arial","DejaVu Sans"],
    "font.size":8,"axes.titlesize":9,"axes.labelsize":8,"axes.titleweight":"bold",
    "axes.spines.top":False,"axes.spines.right":False,"axes.linewidth":.8,
    "xtick.labelsize":7,"ytick.labelsize":7,"legend.frameon":False})
C = {"blosum_uniform":"#CC79A7","fixed":"#999999","learned":"#D55E00",
     "atomic":"#0072B2","hybrid_frozen":"#009E73"}
LAB = {"blosum_uniform":"BLOSUM\nuniform","fixed":"fixed","learned":"learned\n20×20",
       "atomic":"atomic","hybrid_frozen":"frozen\nhybrid"}
ORDER = ["blosum_uniform","fixed","learned","atomic","hybrid_frozen"]

d = pd.read_csv(_os.path.join(RES, "malone_validation.csv"))
tidy, wide = ml.load(verbose=False)
idx = tidy.attrs["index_tcrs"]

fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.9), gridspec_kw=dict(wspace=.55, top=.80))

# (a) per-TCR Spearman
ax = axes[0]
for i, m in enumerate(ORDER):
    v = d[d.model == m].spearman.to_numpy()
    ax.scatter(np.full(len(v), i) + np.random.default_rng(0).uniform(-.15,.15,len(v)),
               v, s=13, color=C[m], alpha=.75, edgecolors="none")
    ax.plot([i-.28, i+.28], [v.mean()]*2, color="k", lw=1.6, solid_capstyle="butt")
ax.set_xticks(range(5)); ax.set_xticklabels([LAB[m] for m in ORDER], fontsize=6.5)
ax.set_ylabel("Spearman ρ  (per TCR)"); ax.axhline(0, color="k", lw=.6, ls=":")
ax.set_title("Agreement with measured\nbinding", loc="left")
ax.text(-.30, 1.22, "a", transform=ax.transAxes, fontsize=11, fontweight="bold", va="top")

# (b) the caveat -- profiles are highly correlated
ax = axes[1]
W = wide[idx].to_numpy(dtype=float)
Cm = np.corrcoef(stats.rankdata(W, axis=0).T)
im = ax.imshow(Cm, cmap="Purples", vmin=0, vmax=1)
ax.set_xticks([]); ax.set_yticks([])
iu = np.triu_indices(len(idx), 1); rbar = Cm[iu].mean()
neff = len(idx)/(1+(len(idx)-1)*rbar)
ax.set_title("…but the 20 TCRs are\nnot independent", loc="left")
ax.set_xlabel(f"mean ρ = {rbar:.2f} between profiles\neffective n ≈ {neff:.1f}, not 20",
              fontsize=6.8)
fig.colorbar(im, ax=ax, shrink=.72, pad=.04)
ax.text(-.18, 1.22, "b", transform=ax.transAxes, fontsize=11, fontweight="bold", va="top")

# (c) peptide-level bootstrap differences
ax = axes[2]
comps = [("atomic","fixed","+0.132",0.0547,0.2186),
         ("atomic","learned","+0.073",-0.0018,0.1535),
         ("hybrid_frozen","atomic","+0.034",-0.0196,0.0843),
         ("hybrid_frozen","learned","+0.106",0.0456,0.1776)]
for i,(a,b,mid,lo,hi) in enumerate(comps):
    y = len(comps)-1-i
    sig = lo > 0
    ax.plot([lo,hi],[y,y], color=C[a], lw=2.4, solid_capstyle="round",
            alpha=1.0 if sig else .45)
    ax.scatter([float(mid)],[y], color=C[a], s=26, zorder=3, alpha=1.0 if sig else .45)
    ax.text(hi+.012, y, "sig." if sig else "n.s.", va="center", fontsize=6.6,
            color=C[a] if sig else "#8A9997")
ax.axvline(0, color="k", lw=.8, ls="--")
ax.set_yticks(range(len(comps)))
ax.set_yticklabels([f"{a.replace('_frozen','')} − {b}" for a,b,_,_,_ in comps][::-1], fontsize=6.4)
ax.set_xlabel("Δ Spearman ρ\n(bootstrap over 168 peptides)")
ax.set_title("What survives valid\ninference", loc="left")
ax.set_xlim(-.06, .30)
ax.text(-.42, 1.22, "c", transform=ax.transAxes, fontsize=11, fontweight="bold", va="top")

for ext in ("png","pdf"):
    fig.savefig(_os.path.join(FIG, f"fig10_external_validation.{ext}"))
print("wrote figures/fig10_external_validation.png / .pdf")
