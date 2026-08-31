"""
derive_M_and_w.py
=================
Shows the *entire* derivation of the two objects the model turns a peptide
into a probability with:

    M[a,b]  -- how far apart two amino acids are
    w[t,j]  -- how much TCR t cares about position j

Nothing here is new science. It exists because "where do M and w come from"
is the question everyone asks first, and the answer is spread across
``build_atomic_features`` (phi), ``build_model`` (priors) and ``fit`` (ADVI).
This walks it end to end, prints every intermediate stage, and writes the
final tables to ``results/derivation/`` so they can be inspected directly.

Protocol matches the manuscript: 9-mer group, mutant rows only
(``mutation_position > 0``), atomic model, ADVI 12,000 iterations, seed 0.

Usage:  python3 5_publication/derive_M_and_w.py
"""

from __future__ import annotations

# --- bootstrap ---
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
# --- end bootstrap ---

import time
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

import batman_atomic as ba
import experiments as ex

OUT = _os.path.join(ba.ROOT, "results", "derivation")
_os.makedirs(OUT, exist_ok=True)
N_ITER = 12000
LENGTH = 9
np.set_printoptions(suppress=True, linewidth=200)


def rule(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


# =====================================================================
# STAGE 1 -- phi : chemistry only, no TCR data involved
# =====================================================================
def stage1_phi():
    rule("STAGE 1  phi : descriptors from SMILES  (no TCR data used at all)")

    raw = []
    for aa in ba.AA20:
        mol = Chem.MolFromSmiles(ba.AA_SMILES[aa])
        raw.append({
            "aa": aa,
            "SMILES": ba.AA_SMILES[aa],
            "heavy": mol.GetNumHeavyAtoms(),
            "polar": sum(1 for a in mol.GetAtoms() if a.GetSymbol() in ("N", "O")),
            "S": sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "S"),
            "aromatic": sum(1 for a in mol.GetAtoms() if a.GetIsAromatic()),
            "HBD": rdMolDescriptors.CalcNumHBD(mol),
            "HBA": rdMolDescriptors.CalcNumHBA(mol),
            "rotB": rdMolDescriptors.CalcNumRotatableBonds(mol),
            "charge": ba.AA_CHARGE.get(aa, 0.0),
        })
    raw = pd.DataFrame(raw).set_index("aa")
    cols = ba.FEATURE_SETS["base8"]

    print("\n1a. RDKit counts on the FULL residue (still includes the backbone):")
    print(raw[cols].to_string())

    additive = ["heavy", "polar", "S", "HBD", "HBA", "rotB"]
    gly = raw.loc["G"]
    sub = raw[cols].copy()
    for c in additive:
        sub[c] = sub[c] - gly[c]
    print(f"\n1b. Subtract glycine (pure backbone: heavy={gly.heavy}, polar={gly.polar}, "
          f"HBD={gly.HBD}, HBA={gly.HBA}, rotB={gly.rotB})")
    print("    -> what is left describes the SIDE CHAIN, the part a mutation changes:")
    print(sub.to_string())

    z = (sub - sub.mean()) / sub.std()
    print("\n1c. z-score each column (else 'heavy' spans ~10 and 'charge' spans 2,")
    print("    and theta would be forced to undo the unit mismatch):")
    print(z.round(3).to_string())

    ref = ba.build_atomic_features("base8")
    assert np.allclose(z.loc[ba.AA20].to_numpy(), ref.to_numpy(), atol=1e-9), \
        "hand derivation does not match build_atomic_features()"
    print("\n  [check] identical to build_atomic_features('base8')  OK")

    raw[cols].to_csv(f"{OUT}/phi_1_raw.csv")
    sub.to_csv(f"{OUT}/phi_2_glycine_subtracted.csv")
    z.to_csv(f"{OUT}/phi_3_zscored.csv")
    return ref


# =====================================================================
# STAGE 2 -- theta and w : the only things actually inferred
# =====================================================================
def stage2_fit(phi_df):
    rule("STAGE 2  theta, w, d0, cutpoints : inferred by ADVI")

    phi = phi_df.to_numpy()
    df = ba.load_batcave()
    for L, sub, arrays in ex.length_groups(df, phi):
        if L != LENGTH:
            continue
        keep = np.where(sub.mutation_position.to_numpy(dtype=int) > 0)[0]
        sub = sub.iloc[keep].reset_index(drop=True)
        arrays = ba.subset(arrays, keep)
        break

    print(f"\ndata: L={LENGTH}  rows={len(sub)}  TCRs={arrays['n_tcr']}  "
          f"epitopes={sub.index_peptide.nunique()}")
    print(f"free parameters: theta 8  +  w {arrays['n_tcr']}x{LENGTH}"
          f"={arrays['n_tcr']*LENGTH}  +  d0 1  +  cut 2"
          f"  =  {8 + arrays['n_tcr']*LENGTH + 3}")
    print(f"\nrunning ADVI, {N_ITER} iterations ...", flush=True)

    t0 = time.time()
    post = ba.fit(ba.build_model("atomic", arrays, ba.load_blosum100_distance()),
                  n_iter=N_ITER, seed=0)
    print(f"  done in {time.time()-t0:.0f}s")

    pm_ = post.posterior.mean(("chain", "draw"))
    theta = pm_["theta"].values
    w = pm_["w"].values
    d0 = float(pm_["d0"].values)
    cut = pm_["cut"].values
    sd = post.posterior.std(("chain", "draw"))

    print("\ntheta  (posterior mean +- sd) -- which chemical axis matters:")
    for c, m, s in sorted(zip(phi_df.columns, theta, sd["theta"].values),
                          key=lambda x: -x[1]):
        print(f"    {c:9s} {m:6.3f}  +- {s:.3f}")
    print(f"\nd0 = {d0:.4f}    cutpoints = [{cut[0]:.4f}, {cut[1]:.4f}]")

    pd.DataFrame({"feature": list(phi_df.columns), "theta_mean": theta,
                  "theta_sd": sd["theta"].values}).to_csv(
        f"{OUT}/theta.csv", index=False)
    wdf = pd.DataFrame(w, index=arrays["tcr_names"],
                       columns=[f"pos{j+1}" for j in range(LENGTH)])
    wdf.to_csv(f"{OUT}/w_per_tcr.csv")
    pd.DataFrame({"param": ["d0", "cut1", "cut2"],
                  "value": [d0, cut[0], cut[1]]}).to_csv(
        f"{OUT}/scalars.csv", index=False)

    print(f"\nw : {w.shape[0]} TCRs x {w.shape[1]} positions.  First 8 rows:")
    print(wdf.head(8).round(3).to_string())
    print(f"\n  mean w per position (across all {w.shape[0]} TCRs):")
    print("   ", " ".join(f"p{j+1}={w[:, j].mean():.3f}" for j in range(LENGTH)))
    print(f"  spread across TCRs at the most-used position: "
          f"sd={w[:, int(np.argmax(w.mean(0)))].std():.3f}"
          "   <- each TCR really does get its own profile")
    return theta, w, d0, cut, arrays, sub, wdf


# =====================================================================
# STAGE 3 -- assemble M
# =====================================================================
def stage3_M(phi_df, theta):
    rule("STAGE 3  M : assembled from phi and theta, never stored")

    phi = phi_df.to_numpy()
    M = np.einsum("k,abk->ab", theta, np.abs(phi[:, None, :] - phi[None, :, :]))
    Mdf = pd.DataFrame(M, index=ba.AA20, columns=ba.AA20)
    Mdf.to_csv(f"{OUT}/M_atomic.csv")

    print("\nM[a,b] = sum_k theta_k * |phi_k(a) - phi_k(b)|      (20 x 20, symmetric)\n")
    print(Mdf.round(1).to_string())

    D = ba.load_blosum100_distance()
    iu = np.triu_indices(20, 1)
    print(f"\nproperties that come free from theta >= 0 and the |.| form:")
    print(f"    M >= 0                : {bool((M >= -1e-12).all())}")
    print(f"    M[a,a] == 0           : {bool(np.allclose(np.diag(M), 0))}")
    print(f"    symmetric             : {bool(np.allclose(M, M.T))}")
    tri = all(M[i, j] <= M[i, k] + M[k, j] + 1e-9
              for i in range(20) for j in range(20) for k in range(20))
    print(f"    triangle inequality   : {tri}")
    print(f"\n    correlation with BLOSUM100 distance r = "
          f"{np.corrcoef(M[iu], D[iu])[0,1]:.3f}   "
          "(it is NOT re-deriving BLOSUM)")

    flat = sorted(((M[i, j], ba.AA20[i], ba.AA20[j]) for i, j in zip(*iu)))
    print("\n    closest pairs :", ", ".join(f"{a}-{b} {v:.2f}" for v, a, b in flat[:5]))
    print("    farthest pairs:", ", ".join(f"{a}-{b} {v:.1f}" for v, a, b in flat[-5:]))
    zero = [(a, b) for v, a, b in flat if v < 1e-9]
    if zero:
        print(f"\n    *** DEGENERATE (M = 0 for a != b): {zero}")
        print("        the descriptor set cannot separate these at all")
    return M


# =====================================================================
# STAGE 4 -- one row, end to end
# =====================================================================
def stage4_example(phi_df, theta, w, d0, cut, M, arrays, sub, wdf):
    rule("STAGE 4  one measured row, all the way to a probability")

    pos = sub.mutation_position.to_numpy(dtype=int)
    # pick a row at a position the TCR weights heavily, for a legible example
    best = None
    for r in range(len(sub)):
        t = arrays["tcr_i"][r]
        j = pos[r] - 1
        a, b = sub.index_peptide.iloc[r][j], sub.peptide.iloc[r][j]
        if a == b:
            continue
        score = w[t, j] * M[ba.AA_IDX[a], ba.AA_IDX[b]]
        if best is None or score > best[0]:
            best = (score, r, t, j, a, b)
    _, r, t, j, a, b = best
    row = sub.iloc[r]
    name = arrays["tcr_names"][t]

    print(f"\nTCR {name}   index {row.index_peptide}  ->  mutant {row.peptide}")
    print(f"position {j+1}:  {a} -> {b}\n")

    phi = phi_df.to_numpy()
    d = np.abs(phi[ba.AA_IDX[a]] - phi[ba.AA_IDX[b]])
    print("  step 1   M[a,b] = sum_k theta_k * |dphi_k|")
    tot = 0.0
    for k, c in enumerate(phi_df.columns):
        tot += theta[k] * d[k]
        print(f"             {c:9s} |dphi|={d[k]:6.3f} x theta={theta[k]:6.3f} "
              f"= {theta[k]*d[k]:7.3f}")
    print(f"             {'':9s} {'':21s}   M = {tot:7.3f}")

    print(f"\n  step 2   weight it by how much THIS TCR watches position {j+1}")
    print(f"             w[{name}, {j+1}] = {w[t, j]:.4f}"
          f"   (its own profile: {np.round(w[t], 3).tolist()})")
    dist = float((w[t] * np.array([
        M[ba.AA_IDX[x], ba.AA_IDX[y]]
        for x, y in zip(row.index_peptide, row.peptide)])).sum())
    print(f"             every other position is unchanged, so contributes 0")
    print(f"             d = {tot:.3f} x {w[t, j]:.4f} = {dist:.4f}")

    eta = d0 - dist
    print(f"\n  step 3   eta = d0 - d = {d0:.4f} - {dist:.4f} = {eta:.4f}")

    def sig(x):
        return 1.0 / (1.0 + np.exp(-x))
    p_le0 = sig(cut[0] - eta)
    p_le1 = sig(cut[1] - eta)
    p = [p_le0, p_le1 - p_le0, 1 - p_le1]
    print(f"\n  step 4   ordered logistic with cutpoints "
          f"[{cut[0]:.4f}, {cut[1]:.4f}]")
    for lab, v in zip(["no activation", "weak", "strong"], p):
        print(f"             P({lab:14s}) = {v*100:5.1f}%")
    print(f"\n  measured : activation = {int(row.activation)} "
          f"({['no activation','weak','strong'][int(row.activation)]})")
    print(f"  predicted: {['no activation','weak','strong'][int(np.argmax(p))]}"
          f"   -> {'MATCH' if int(np.argmax(p))==int(row.activation) else 'MISS'}")


def main():
    t0 = time.time()
    phi_df = stage1_phi()
    theta, w, d0, cut, arrays, sub, wdf = stage2_fit(phi_df)
    M = stage3_M(phi_df, theta)
    stage4_example(phi_df, theta, w, d0, cut, M, arrays, sub, wdf)
    rule("FILES WRITTEN")
    for f in sorted(_os.listdir(OUT)):
        print(f"  results/derivation/{f}")
    print(f"\ntotal {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
