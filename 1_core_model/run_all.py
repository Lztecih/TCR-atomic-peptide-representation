
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r=_os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r,"batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0,_r)
# --- end bootstrap: shared library lives one level up ---
"""Driver: compute every experiment and cache to results/. Safe to re-run."""


import warnings, time
warnings.filterwarnings("ignore")
import batman_atomic as ba, experiments as ex

t0 = time.time()
phi = ba.build_atomic_features("base8").to_numpy()
D   = ba.load_blosum100_distance()
df  = ba.load_batcave()
mh  = ba.load_multi_hamming()
print(f"BATCAVE {len(df)} rows / {df.tcr.nunique()} TCRs | multi-aa {len(mh)} rows", flush=True)

steps = [
    ("exp1 5-fold CV",        lambda: ex.exp1_cross_validation(df, phi, D)),
    ("exp5 multi-aa mutants", lambda: ex.exp5_multi_mutant(df, mh, phi, D)),
    ("exp2 leave-chemistry",  lambda: ex.exp2_leave_chemistry_out(df, phi, D)),
    ("exp3 feature ablation", lambda: ex.exp3_feature_ablation(df, D)),
    ("exp4 novel TCR",        lambda: ex.exp4_novel_tcr(df, phi, D)),
    ("exp7 pMHC term",        lambda: ex.exp7_pmhc_term(df, phi, D)),
    ("exp6 NUTS vs ADVI",     lambda: ex.exp6_nuts_vs_advi(df, phi, D)),
]
for name, fn in steps:
    s = time.time()
    r = fn()
    print(f"### {name}: {len(r)} rows in {time.time()-s:.0f}s "
          f"(total {(time.time()-t0)/60:.1f} min)", flush=True)
print(f"ALL DONE in {(time.time()-t0)/60:.1f} min", flush=True)
