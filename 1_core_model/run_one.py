
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r=_os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r,"batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0,_r)
# --- end bootstrap: shared library lives one level up ---
"""Run a single experiment by name (for parallel execution)."""


import sys, warnings, time
warnings.filterwarnings("ignore")
import batman_atomic as ba, experiments as ex

which = sys.argv[1]
phi = ba.build_atomic_features("base8").to_numpy()
D   = ba.load_blosum100_distance()
df  = ba.load_batcave()
t0 = time.time()

if   which == "exp1": r = ex.exp1_cross_validation(df, phi, D)
elif which == "exp2": r = ex.exp2_leave_chemistry_out(df, phi, D)
elif which == "exp3": r = ex.exp3_feature_ablation(df, D)
elif which == "exp4": r = ex.exp4_novel_tcr(df, phi, D)
elif which == "exp5": r = ex.exp5_multi_mutant(df, ba.load_multi_hamming(), phi, D)
elif which == "exp6": r = ex.exp6_nuts_vs_advi(df, phi, D)
elif which == "exp7": r = ex.exp7_pmhc_term(df, phi, D)
else: raise SystemExit(f"unknown {which}")
print(f"@@@ {which} FINISHED {len(r)} rows in {(time.time()-t0)/60:.1f} min", flush=True)
