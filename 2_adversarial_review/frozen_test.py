
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r=_os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r,"batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0,_r)
# --- end bootstrap: shared library lives one level up ---
import warnings; warnings.filterwarnings("ignore")
import numpy as np, batman_atomic as ba, experiments as ex
phi=ba.build_atomic_features("base8").to_numpy(); D=ba.load_blosum100_distance()
df=ba.load_batcave()
sub=df[(df.index_peptide.str.len()==9)&(df.peptide.str.len()==9)]
ok=sub.peptide.apply(lambda s:all(c in ba.AA_IDX for c in s))&sub.index_peptide.apply(lambda s:all(c in ba.AA_IDX for c in s))
sub=sub[ok].reset_index(drop=True); arr=ba.prepare(sub,phi)

def run(tr,te,label):
    train=ba.subset(arr,tr); a=ba.subset(arr,te); out={}
    p1=ba.fit(ba.build_model("atomic",train,D),n_iter=12000,seed=0)
    th=p1.posterior["theta"].mean(("chain","draw")).values
    w =p1.posterior["w"].mean(("chain","draw")).values
    out["atomic"]=ba.mean_pairwise_auc(a["y"],ba.posterior_distance("atomic",p1,a,D))
    for sh in [0.1,0.25,0.5]:
        p2=ba.fit(ba.build_model("hybrid_frozen",train,D,hybrid_shrinkage=sh,
                                 frozen_theta=th,frozen_w=w),n_iter=12000,seed=0)
        dist=ba.posterior_distance("hybrid_frozen",p2,a,D,
                                   frozen_theta=th,frozen_w=w)
        out[f"frozen(s={sh})"]=ba.mean_pairwise_auc(a["y"],dist)
    print(f"--- {label} ---",flush=True)
    for k,v in out.items(): print(f"  {k:16s} {v:.4f}",flush=True)

fold=sub.training_fold.to_numpy(); isx=sub.mutation_position.to_numpy()==0
run(np.where((fold!=0)|isx)[0],np.where(fold==0)[0],"IN-DISTRIBUTION (fold 0)")
mut=ex._mutant_residue(sub); pos=sub.mutation_position.to_numpy(int)
tm=np.array([m in set("WFY") for m in mut]); trm=(~tm)&(pos>0)
run(np.where(trm)[0],np.where(tm)[0],"OOD (held-out aromatics)")
print("@@@ frozen_test DONE",flush=True)
