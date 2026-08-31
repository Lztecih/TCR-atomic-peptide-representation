
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r=_os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r,"batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0,_r)
# --- end bootstrap: shared library lives one level up ---
"""Shrinkage sweep: can a tighter residual keep the atomic OOD advantage?"""


import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, batman_atomic as ba, experiments as ex

phi = ba.build_atomic_features("base8").to_numpy()
D   = ba.load_blosum100_distance()
df  = ba.load_batcave()
SHRINK = [0.02, 0.05, 0.1, 0.25]

def fit_pred(kind, arrays, tr, te, shrink, seed=0):
    m = ba.build_model(kind, ba.subset(arrays, tr), D, hybrid_shrinkage=shrink)
    post = ba.fit(m, n_iter=12000, seed=seed)
    test = ba.subset(arrays, te)
    dist = ba.posterior_distance(kind, post, test, D)
    return ba.per_tcr_auc(test, dist)

def compute():
    rows=[]
    for L, sub, arrays in ex.length_groups(df, phi):
        # --- in-distribution: fold 0 only, to keep the sweep affordable ---
        fold=sub.training_fold.to_numpy(); isx=sub.mutation_position.to_numpy()==0
        tr=np.where((fold!=0)|isx)[0]; te=np.where(fold==0)[0]
        for sh in SHRINK:
            for tcr,a in fit_pred("hybrid",arrays,tr,te,sh).items():
                rows.append(dict(setting="in_distribution",shrinkage=sh,L=L,tcr=tcr,auc=a))
        # --- OOD: leave-chemistry-out ---
        mut=ex._mutant_residue(sub); pos=sub.mutation_position.to_numpy(int)
        for g,held in ex.CHEM_GROUPS.items():
            tm=np.array([m in held for m in mut]); trm=(~tm)&(pos>0)
            if tm.sum()<20 or trm.sum()<50: continue
            tr2,te2=np.where(trm)[0],np.where(tm)[0]
            for sh in SHRINK:
                for tcr,a in fit_pred("hybrid",arrays,tr2,te2,sh).items():
                    rows.append(dict(setting="leave_chemistry_out",shrinkage=sh,
                                     L=L,group=g,tcr=tcr,auc=a))
        print(f"  L={L} done", flush=True)
    return pd.DataFrame(rows)

r = ex.cached("review_hybrid_shrinkage.csv", compute)
print(f"@@@ sweep FINISHED {len(r)} rows", flush=True)
