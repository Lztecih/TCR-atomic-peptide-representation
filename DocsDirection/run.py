"""Run one arm over a panel and protocol, and write per-receptor AUCs.

Arms:
  matrix:<name>   fixed substitution matrix (blosum100 | hamming | peptideclm)
  batman:<name>   BATMAN proper: M = D*(1+delta), delta learned per substitution
  peptide         ROUTE B: learned low-rank metric on whole-peptide embeddings
  feature:full    ROUTE C: 50 language-model + 24 descriptor coefficients
  feature:plm     ROUTE C ablation, language model only (50)
  feature:desc    ROUTE C ablation, descriptors only (24)

Examples:
  python src/run.py --arm matrix:blosum100 --lengths 9
  python src/run.py --arm feature:full --lengths 9 --protocol loo
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data as D        # noqa: E402
import features as FT   # noqa: E402
import matrices as MX   # noqa: E402
import metric as MT     # noqa: E402
import model as MD      # noqa: E402


def run(arm, panel_name="one_per_index", protocol="within", lengths=None,
        steps=40000, draws=3000, seed=111, use_mhc=False, emb="mtr_large",
        kind="res", quiet=True, cdr3=False, partial_path=None,
        cdr3_shuffle=False, pos_pool=False, mhc_shuffle=False):
    df = D.load_batcave()
    panel = D.one_per_index(df) if panel_name == "one_per_index" else D.eligible_panel(df)
    groups = D.length_groups(df, panel)
    if lengths:
        groups = {L: g for L, g in groups.items() if L in lengths}
    kindname, _, arg = arm.partition(":")

    rows = []
    for L, group in groups.items():
        if len(group) < 2 and protocol == "loo":
            continue
        if protocol == "within":
            splits = list(D.folds(df, group, L))
        elif protocol == "gloo":
            # Hold out EVERY receptor sharing the held-out index peptide. Without
            # this, a held-out receptor's siblings stay in training and the model
            # has already seen that index peptide's whole mutational scan.
            # relabel=False when the weights are conditioned on CDR3: each
            # training receptor must keep its identity for its CDR3 row to mean
            # anything.
            splits = list(D.leave_one_group_out(df, group, L, relabel=not cdr3))
        else:
            splits = list(D.leave_one_receptor_out(df, group, L,
                                                   relabel=not cdr3))
        for tag, tr, te in splits:
            t0 = time.time()
            if mhc_shuffle:
                # NEGATIVE CONTROL for the pMHC term, built like the CDR3 one.
                # Permute BindLevel WITHIN each receptor: every receptor keeps
                # its own mix of NB/WB/SB, so the model keeps the identical
                # structure and the identical three extra parameters, and only
                # the peptide-to-level pairing is destroyed. Whatever the real
                # arm still gains over this is pMHC information; whatever both
                # gain is the extra parameters.
                rs = np.random.default_rng(2000 + seed)

                def _perm(d):
                    d = d.reset_index(drop=True).copy()
                    bl = d.BindLevel.to_numpy().copy()
                    for pos in d.groupby("tcr").indices.values():
                        bl[pos] = bl[pos][rs.permutation(len(pos))]
                    d["BindLevel"] = bl
                    return d

                tr, te = _perm(tr), _perm(te)
            # Rebuild any PeptideCLM matrix without the held-out index peptide,
            # so a held-out run never sees it. Hoisted out of the arm branches:
            # it used to sit inside the `matrix:` branch only, which left the
            # featmat and *+mat arms building their matrix from the full frame.
            excl = (set(te.index_peptide.unique())
                    if protocol in ("loo", "gloo") else None)
            kw = dict(use_mhc=use_mhc, pooled=(protocol == "within"),
                      steps=steps, draws=draws, seed=seed)
            if pos_pool:
                # per-position pooling: an unseen receptor inherits a per-position
                # pan-receptor profile instead of one flat constant. No receptor
                # covariate of any kind is used.
                kw["pooled"] = True
                kw["pos_pool"] = True
            if cdr3:
                names = sorted(set(tr.tcr) | set(te.tcr))
                # Standardise the descriptors on the TRAINING receptors only.
                # Fitting mu/sd over training and held-out rows together lets
                # the held-out receptor set the scale the training rows are
                # expressed on.
                Cm, _ = FT.cdr3_features(
                    pd.concat([tr, te]).assign(
                        cdr3a=pd.concat([tr, te]).cdr3a,
                        cdr3b=pd.concat([tr, te]).cdr3b), names,
                    fit=sorted(set(tr.tcr)))
                if cdr3_shuffle:
                    # NEGATIVE CONTROL. Give every receptor somebody else's CDR3.
                    # The model keeps the identical structure -- same 8 columns,
                    # same 72 coefficients, same prior -- so anything this arm
                    # still gains is the reparameterisation of w(p), not the
                    # immunology. The real arm's lift is only a CDR3 result to
                    # the extent that it beats this one.
                    rs = np.random.default_rng(1000 + seed)
                    Cm = Cm[rs.permutation(len(Cm))]
                kw["C"] = Cm
            if kindname == "feature":
                # combination arms:  full+mat = A x C soft,  full+pep = B x C
                mats = None
                if arg.endswith("+mat"):
                    mats = [MX.peptideclm(df, tag=emb, kind=kind,
                                          exclude_index=excl)[0],
                            MX.reference("blosum100")]
                base = arg.replace("+mat", "").replace("+pep", "")
                # variants that attack the LOO overfitting:
                #   nodidx  drop u_idx (the receptor fingerprint)
                #   delta   keep only features of the CHANGE, not of either endpoint
                #   q4/q8   same blocks, fewer PCA components
                BLK = {"nodidx": ("u_mut", "diff", "scalar"),
                       "delta": ("diff", "scalar")}
                blocks = BLK.get(base, FT.PLM_BLOCKS)
                qq = 4 if base == "q4" else (8 if base == "q8" else 16)
                Xtr, Xte = FT.route_c(tr, te, tag=emb, kind=kind, q=qq,
                                      use_plm=base != "desc",
                                      use_desc=base != "plm",
                                      mats=mats, blocks=blocks)
                if arg.endswith("+pep"):
                    Etr, Ete = FT.route_b(tr, te, tag=emb, center=False)
                    dist = MD.fit_predict(tr, te, mode="feature_peptide",
                                          X_train=Xtr, X_test=Xte,
                                          E_train=Etr, E_test=Ete, **kw)
                else:
                    dist = MD.fit_predict(tr, te, mode="feature",
                                          X_train=Xtr, X_test=Xte, **kw)
            elif kindname == "featmat":
                # A x C STRUCTURAL: matrix multiplies the per-position term
                Mc = MX.peptideclm(df, tag=emb, kind=kind, exclude_index=excl)[0]
                Xtr, Xte = FT.route_c(tr, te, tag=emb, kind=kind)
                dist = MD.fit_predict(tr, te, mode="feature_matrix", D=Mc,
                                      X_train=Xtr, X_test=Xte, **kw)
            elif kindname == "peptide":
                Etr, Ete = FT.route_b(tr, te, tag=emb)
                dist = MD.fit_predict(tr, te, mode="peptide", E_train=Etr, E_test=Ete, **kw)
            else:
                if arg.startswith("peptideclm"):
                    M = MX.peptideclm(df, tag=emb, kind=kind, exclude_index=excl)[0]
                else:
                    M = MX.reference(arg)
                dist = MD.fit_predict(tr, te, mode=("batman" if kindname == "batman"
                                                    else "matrix"), D=M, **kw)
            te = te.assign(_d=dist)
            for tcr, g in te.groupby("tcr"):
                g = g[~g.is_wt]
                if len(g) < 3:
                    continue
                m, pr = MT.three_pairwise(g.activation.to_numpy(), g._d.to_numpy())
                if np.isfinite(m):
                    rows.append(dict(arm=arm, protocol=protocol, L=L, split=str(tag),
                                     tcr=tcr, n=len(g), auc=m,
                                     WS=pr[0], NS=pr[1], NW=pr[2]))
            if not quiet:
                print(f"  [{arm}] L={L} split={tag} {time.time()-t0:.0f}s", flush=True)
            # Write after every fold, not only when the whole arm finishes. A
            # group-aware LOO arm is 15 fits of ~9,300 rows and can run for well
            # over an hour; losing all of it because the machine had to be
            # closed is avoidable for the cost of one small file write.
            if partial_path and rows:
                pd.DataFrame(rows).to_csv(partial_path, index=False)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--panel", default="one_per_index",
                    choices=["one_per_index", "eligible"])
    ap.add_argument("--protocol", default="within", choices=["within", "loo", "gloo"])
    ap.add_argument("--lengths", type=int, nargs="*", default=None)
    ap.add_argument("--steps", type=int, default=40000)
    ap.add_argument("--draws", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=111)
    ap.add_argument("--emb", default="mtr_large")
    ap.add_argument("--kind", default="res")
    ap.add_argument("--mhc", action="store_true")
    ap.add_argument("--cdr3", action="store_true",
                    help="condition the positional weights on each receptor's CDR3")
    ap.add_argument("--cdr3-shuffle", action="store_true",
                    help="NEGATIVE CONTROL: permute the CDR3 rows across receptors")
    ap.add_argument("--pos-pool", action="store_true",
                    help="per-position pooling prior on w(p); no receptor covariate")
    ap.add_argument("--mhc-shuffle", action="store_true",
                    help="NEGATIVE CONTROL: permute BindLevel within each receptor")
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()

    # --cdr3 replaces the Beta pooling prior on w(p) with a deterministic
    # sigmoid of the CDR3 covariates (model.py), so alpha_w/beta_w -- and
    # therefore --pos-pool -- are never constructed. Accepting both silently
    # would file the result under a flag that did nothing.
    if a.pos_pool and a.cdr3:
        ap.error("--pos-pool has no effect with --cdr3: conditioning w(p) on "
                 "CDR3 replaces the pooling prior entirely. Pick one.")
    if a.mhc_shuffle and not a.mhc:
        ap.error("--mhc-shuffle is the control for --mhc and does nothing "
                 "without it.")

    # The default name has to carry every flag that changes the numbers, or two
    # different runs collide on one file and the later one silently wins.
    flags = "".join(["_mhc" if a.mhc else "", "_mhcshuf" if a.mhc_shuffle else "",
                     "_cdr3" if a.cdr3 else "", "_cdr3shuf" if a.cdr3_shuffle else "",
                     "_pospool" if a.pos_pool else "",
                     f"_s{a.seed}" if a.seed != 111 else ""])
    tag0 = a.tag or (f"{a.arm.replace(':','-')}_{a.panel}_{a.protocol}"
                     + (f"_L{''.join(map(str,a.lengths))}" if a.lengths else "")
                     + flags)
    os.makedirs(D.RESULTS, exist_ok=True)
    r = run(a.arm, a.panel, a.protocol, a.lengths, a.steps, a.draws, a.seed,
            a.mhc, a.emb, a.kind, quiet=False, cdr3=a.cdr3,
            cdr3_shuffle=a.cdr3_shuffle, pos_pool=a.pos_pool,
            mhc_shuffle=a.mhc_shuffle,
            # NOT "{tag0}.csv": a run killed half way used to leave a file at
            # the final path with no sign that folds were missing, and a mean
            # over 2 of 15 folds reads exactly like a result.
            partial_path=os.path.join(D.RESULTS, f"{tag0}.partial.csv"))
    per = MT.per_receptor(r)
    print(f"\n=== {a.arm} | {a.panel} | {a.protocol} | L={a.lengths} | steps={a.steps} ===")
    print(f"receptors {len(per)}   mean AUC {per.mean():.4f}   sd {per.std():.4f}")
    os.makedirs(D.RESULTS, exist_ok=True)
    tag = tag0          # one definition only; it used to be recomputed here
                        # WITHOUT the flag suffix, so the checkpoint and the
                        # final file could land under two different names.
    r.to_csv(os.path.join(D.RESULTS, f"{tag}.csv"), index=False)
    part = os.path.join(D.RESULTS, f"{tag0}.partial.csv")
    if os.path.exists(part):
        os.remove(part)
    print(f"[written] results/{tag}.csv")


if __name__ == "__main__":
    main()
