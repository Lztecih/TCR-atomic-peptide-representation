"""Figure 12 -- sigma controls how badly the residual fails to transfer."""
from __future__ import annotations
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, matplotlib as mpl, matplotlib.pyplot as plt
from scipy import stats
import batman_atomic as ba

RES=_os.path.join(ba.ROOT,"results"); FIG=_os.path.join(ba.ROOT,"figures")
mpl.rcParams.update({"figure.dpi":120,"savefig.dpi":300,"savefig.bbox":"tight",
 "font.family":"sans-serif","font.sans-serif":["Helvetica Neue","Helvetica","Arial","DejaVu Sans"],
 "font.size":8,"axes.titlesize":9,"axes.labelsize":8,"axes.titleweight":"bold",
 "axes.spines.top":False,"axes.spines.right":False,"axes.linewidth":.8,
 "xtick.labelsize":7,"ytick.labelsize":7,"legend.frameon":False})
AT="#0072B2"; AC="#009E73"; SG="#8A9997"

d=pd.read_csv(_os.path.join(RES,"loeo_shrinkage.csv"))
at=d[d.model=="atomic"].groupby("held_out_epitope").auc.mean()
sig=sorted(d.sigma.dropna().unique())
mean,lo,hi,ps=[],[],[],[]
for sg in sig:
    h=d[(d.model=="hybrid_frozen")&(d.sigma==sg)].groupby("held_out_epitope").auc.mean()
    j=pd.concat([at,h],axis=1,join="inner",keys=["a","h"]).dropna()
    diff=(j.h-j.a).to_numpy()
    b=np.random.default_rng(0).choice(diff,(10000,len(diff))).mean(1)
    mean.append(diff.mean()); l,u=np.percentile(b,[2.5,97.5]); lo.append(l); hi.append(u)
    ps.append(stats.wilcoxon(j.h,j.a).pvalue)

fig,ax=plt.subplots(figsize=(5.4,3.2),gridspec_kw=dict(top=.82))
ax.axhline(0,color=AT,lw=1.4,ls="--")
ax.text(.021,.0015,"atomic model (backbone alone)",fontsize=6.8,color=AT,va="bottom")
ax.fill_between(sig,lo,hi,color=AC,alpha=.18,lw=0)
ax.plot(sig,mean,"o-",color=AC,lw=1.6,ms=6,zorder=3)
for x,y,p in zip(sig,mean,ps):
    ax.annotate(f"p={p:.2f}" if p>=.01 else f"p={p:.3f}", (x,y),
                textcoords="offset points", xytext=(0,-14), ha="center",
                fontsize=6.2, color="#33403D")
# in-distribution reference (frozen hybrid, sigma = 0.25)
ax.scatter([.25],[.0282],marker="*",s=170,color=AC,edgecolors="white",
           linewidths=1.1,zorder=5)
ax.annotate("same model, same σ,\nbut scored on the epitopes\nit was trained on: +0.028",
            (.25,.0282), textcoords="offset points", xytext=(-14,6),
            ha="right", fontsize=6.4, color="#33403D")
ax.set_xscale("log"); ax.set_xticks(sig)
ax.set_xticklabels([f"{s:g}" for s in sig]); ax.minorticks_off()
ax.set_xlabel("residual shrinkage σ  (how much freedom δ is given)")
ax.set_ylabel("Δ mean per-TCR AUC  vs the atomic model")
rho=stats.spearmanr(sig,mean).statistic
ax.set_title("On an unseen epitope the residual only ever costs accuracy\n"
             f"and the cost is monotone in σ (Spearman ρ = {rho:+.2f})",loc="left")
ax.set_ylim(-.042,.040)
for ext in ("png","pdf"): fig.savefig(_os.path.join(FIG,f"fig12_residual_transfer.{ext}"))
print("wrote figures/fig12_residual_transfer.png / .pdf")
