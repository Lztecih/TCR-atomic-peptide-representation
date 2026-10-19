"""Train on single-residue mutants, test on MULTI-residue mutants.

This is the only place the B x C combination can show its value. On a
single-residue mutant exactly one position changes, so a whole-peptide term is
nearly a deterministic function of (position, substitution) and is collinear
with the per-position term. With two or more positions changing at once, a term
that sees the whole molecule can in principle represent their interaction,
which a sum over independent positions cannot.

Protocol (per receptor, unpooled): fit on that receptor's complete single-residue
scan with no fold held out, then score every multi-residue mutant of the same
receptor. Parameters are learned on single substitutions only and must
extrapolate; nothing about the multi-residue peptides enters the fit.

Run:  python src/run_multi.py
Writes: results/multi_mutant.csv
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data as D        # noqa: E402
import features as FT   # noqa: E402
import matrices as MX   # noqa: E402
import metric as MT     # noqa: E402
import model as MD      # noqa: E402

ARMS = ["hamming_floor", "matrix:blosum100", "batman:blosum100",
        "feature:full", "feature:delta", "feature:full+pep", "feature:full+pepn"]


def load_multi() -> pd.DataFrame:
    fr = [pd.read_csv(f) for f in
          sorted(glob.glob(os.path.join(D.DATA, "multi_hamming", "*_multi_hamming_all.csv")))]
    m = pd.concat(fr, ignore_index=True).rename(columns={"index_peptide": "index"})
    m["peptide"] = m.peptide.astype(str)
    m["index"] = m["index"].astype(str)
    keep = m.peptide.str.len() == m["index"].str.len()
    if (~keep).any():
        print(f"  dropping {int((~keep).sum())} length-mismatched peptides: "
              f"{sorted(m.loc[~keep,'peptide'].unique())}")
    m = m[keep].copy()
    m["hamming"] = [sum(a != b for a, b in zip(i, p))
                    for i, p in zip(m["index"], m.peptide)]
    return m[m.hamming >= 2].reset_index(drop=True)


def score(arm, train, multi, steps, seed):
    """Posterior-mean distance for every multi-residue mutant."""
    L = len(multi["index"].iloc[0])
    sub = np.array([[i != p for i, p in zip(idx, pep)]
                    for idx, pep in zip(multi["index"], multi.peptide)])

    if arm == "hamming_floor":
        return sub.sum(axis=1).astype(float)          # just the substitution count

    kind, _, matname = arm.partition(":")
    tiny = train.head(8)

    if kind in ("matrix", "batman"):
        M = MX.reference(matname)
        _, post = MD.fit_predict(train, tiny, mode=("batman" if kind == "batman" else "matrix"),
                                 D=M, pooled=False, steps=steps, seed=seed,
                                 return_posterior=True)
        w = np.atleast_2d(post["w"])[0]
        d = np.zeros(len(multi))
        if kind == "batman":
            ai = np.array([D.AAI[a] for a in train.wt if a])
            bi = np.array([D.AAI[a] for a in train.mt if a])
            uniq = sorted({int(20 * a + b) for a, b in zip(ai, bi)})
            kmap = {k: i for i, k in enumerate(uniq)}
            delta = np.atleast_1d(post["delta"]); mu = float(post["mu"])
        for i, (idx, pep) in enumerate(zip(multi["index"], multi.peptide)):
            tot = 0.0
            for p in range(L):
                if idx[p] == pep[p]:
                    continue
                a, b = D.AAI[idx[p]], D.AAI[pep[p]]
                mult = 1.0
                if kind == "batman":
                    q = kmap.get(int(20 * a + b))
                    mult = 1.0 + (delta[q] if q is not None else mu)
                tot += w[p] * M[a, b] * mult
            d[i] = tot
        return d

    # feature arms
    # "+pepn" normalises the whole-peptide vector by the number of substituted
    # positions. beta is fitted on single-residue mutants, where ||z|| has a
    # median around 5; on multi-residue mutants ||z|| is 2.4-2.9x larger, so an
    # un-normalised linear term is being extrapolated far outside its fitted
    # range. Dividing by the substitution count puts a multi-residue peptide
    # back on the per-substitution scale the coefficient was learned on, and
    # isolates whether the failure is extrapolation or absence of signal.
    normalise_pep = arm.endswith("+pepn")
    use_pep = arm.endswith("+pep") or normalise_pep
    base = arm.split(":", 1)[1].replace("+mat", "").replace("+pepn", "").replace("+pep", "")
    BLK = {"nodidx": ("u_mut", "diff", "scalar"), "delta": ("diff", "scalar")}
    Xtr, Xm, mask = FT.route_c_multi(train, multi, blocks=BLK.get(base, FT.PLM_BLOCKS))
    if use_pep:
        Etr, Em = FT.route_b_multi(train, multi)
        if normalise_pep:
            ktr = np.maximum((train.pos.to_numpy() >= 0).astype(float), 1.0)
            Etr = Etr / ktr[:, None]
            Em = Em / np.maximum(sub.sum(axis=1), 1)[:, None]
        _, post = MD.fit_predict(train, tiny, mode="feature_peptide",
                                 X_train=Xtr, X_test=Xtr[:8],
                                 E_train=Etr, E_test=Etr[:8],
                                 pooled=False, steps=steps, seed=seed,
                                 return_posterior=True)
    else:
        _, post = MD.fit_predict(train, tiny, mode="feature",
                                 X_train=Xtr, X_test=Xtr[:8],
                                 pooled=False, steps=steps, seed=seed,
                                 return_posterior=True)
    w = np.atleast_2d(post["w"])[0]
    g0 = float(post["g0"]); gam = np.atleast_1d(post["gamma"])
    per = g0 + Xm @ gam                      # (n, L)
    d = (w[None, :] * per * mask).sum(axis=1)
    if use_pep:
        d = d + Em @ np.atleast_1d(post["beta"])
    return d


def main():
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    df = D.load_batcave()
    multi = load_multi()
    rows = []
    for tcr, mm in multi.groupby("tcr"):
        train = df[df.tcr == tcr]
        if not len(train):
            print(f"  {tcr}: no single-residue training data, skipped"); continue
        mm = mm.reset_index(drop=True)
        y = mm.activation.to_numpy()
        if len({int(v) for v in y}) < 2:
            print(f"  {tcr}: only one activation class present, AUC undefined, skipped"); continue
        for arm in ARMS:
            try:
                d = score(arm, train, mm, steps, 111)
            except Exception as e:
                print(f"  {tcr} {arm}: FAILED {type(e).__name__}: {e}"); continue
            a, pr = MT.three_pairwise(y, d)
            rows.append(dict(tcr=tcr, arm=arm, n=len(mm), auc=a,
                             WS=pr[0], NS=pr[1], NW=pr[2]))
        print(f"  {tcr}: {len(mm)} multi-residue peptides scored", flush=True)

    r = pd.DataFrame(rows)
    os.makedirs(D.RESULTS, exist_ok=True)
    r.to_csv(os.path.join(D.RESULTS, "multi_mutant.csv"), index=False)
    pd.set_option("display.width", 200)
    print("\n=== per receptor (mean of the 3 pairwise AUCs) ===")
    print(r.pivot_table(index="tcr", columns="arm", values="auc").to_string(
        float_format=lambda x: f"{x:.3f}"))
    print("\n=== mean over receptors ===")
    for arm, s in r.groupby("arm").auc.mean().sort_values(ascending=False).items():
        print(f"  {s:.4f}   {arm}")
    print(f"\n[written] results/multi_mutant.csv")


if __name__ == "__main__":
    main()
