"""Figure 13 -- what the residual is tied to decides whether it transfers."""
from __future__ import annotations
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r=_os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r,"batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0,_r)
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

i=pd.read_csv(_os.path.join(RES,"feature_indist.csv"))
wi=i.groupby(["tcr","variant"]).auc.mean().reset_index().pivot(
    index="tcr",columns="variant",values="auc").dropna()
o=pd.read_csv(_os.path.join(RES,"loeo_feature_residual.csv"))
wo=(o.groupby(["held_out_epitope","variant"]).auc.mean().reset_index()
     .pivot(index="held_out_epitope",columns="variant",values="auc").dropna())

def ci(v):
    b=np.random.default_rng(0).choice(v,(10000,len(v))).mean(1)
    return np.percentile(b,[2.5,97.5])

pts=[("atomic backbone\n(no residual)","atomic","atomic","#0072B2","o",0.0,0.0),
     ("per-cell residual\n400 parameters","hybrid_frozen","hybrid_frozen@0.25","#D55E00","s",None,None),
     ("feature-tied residual\n36 parameters","hybrid_feature","hybrid_feature@0.25","#009E73","D",None,None)]

fig,ax=plt.subplots(figsize=(5.8,4.4),gridspec_kw=dict(top=.80))
lim=.042
ax.axhline(0,color="#B9C6C3",lw=.8); ax.axvline(0,color="#B9C6C3",lw=.8)
ax.plot([-lim,lim],[lim,-lim],ls=":",color="#B9C6C3",lw=1)
ax.text(.030,-.031,"1 : 1\ngain = loss",fontsize=6.3,color="#8A9997",ha="center")
ax.fill_between([0,lim],[0,0],[lim,lim],color="#009E73",alpha=.06,lw=0)
ax.text(.021,.020,"free lunch\n(nothing lands here)",fontsize=6.3,
        color="#8A9997",ha="center")

for lab,ci_key,co_key,col,mk,fx,fy in pts:
    dx=(wi[ci_key]-wi["atomic"]).to_numpy() if fx is None else np.zeros(2)
    dy=(wo[co_key]-wo["atomic"]).to_numpy() if fy is None else np.zeros(2)
    x,y=(dx.mean(),dy.mean()) if fx is None else (0.0,0.0)
    if fx is None:
        lx,hx=ci(dx); ly,hy=ci(dy)
        ax.plot([lx,hx],[y,y],color=col,lw=1.1,alpha=.55)
        ax.plot([x,x],[ly,hy],color=col,lw=1.1,alpha=.55)
    ax.scatter([x],[y],marker=mk,s=110,color=col,zorder=5,
               edgecolors="white",linewidths=1.2)
    off=(10,10) if fx is not None else ((10,-4) if "per-cell" in lab else (10,8))
    ax.annotate(lab,(x,y),textcoords="offset points",xytext=off,
                fontsize=7,color=col,fontweight="bold",linespacing=1.35)

ax.set_xlim(-.012,lim); ax.set_ylim(-lim,.026)
ax.set_xlabel("Δ AUC on the epitopes it was trained on  (150 TCRs)")
ax.set_ylabel("Δ AUC on a held-out epitope  (23 epitopes)")
ax.set_title("What the residual is tied to decides whether it transfers\n"
             "per-cell trades 1:1 · feature-tied trades ~2:1",loc="left")
for ext in ("png","pdf"): fig.savefig(_os.path.join(FIG,f"fig13_residual_design.{ext}"))
print("wrote figures/fig13_residual_design.png / .pdf")
