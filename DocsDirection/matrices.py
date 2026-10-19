"""Candidate 20x20 amino-acid substitution-distance matrices.

Every matrix is symmetrised, given a zero diagonal, and rescaled to the same
mean off-diagonal value. The rescaling is not cosmetic: the positional weight
w(p) is bounded to (0,1) by its Beta prior and so cannot shrink an over-large
matrix, which means an unscaled candidate would be handicapped or flattered by
its magnitude rather than judged on its shape.

Reference matrices (blosum100, blosum62, hamming) live in data/aa_matrices/ in
the distance form D[a,b] = (1 - S[a,b]/S[a,a])(1 - S[b,a]/S[b,b]).

ROUTE A of the proposal is `peptideclm`: the amino-acid difference matrix read
out of PeptideCLM-2 residue representations.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from data import AA, AAI, DATA
from embeddings import Embeddings

MD = os.path.join(DATA, "aa_matrices")
OFF = ~np.eye(20, dtype=bool)


def _finish(M: np.ndarray, ref_mean: float) -> np.ndarray:
    M = np.asarray(M, float).copy()
    M = (M + M.T) / 2.0
    np.fill_diagonal(M, 0.0)
    if not np.isfinite(M[OFF]).all():
        M[OFF & ~np.isfinite(M)] = np.nanmean(M[OFF])
    M *= ref_mean / M[OFF].mean()
    np.fill_diagonal(M, 0.0)
    return M


def _raw(name: str) -> np.ndarray:
    d = pd.read_csv(os.path.join(MD, f"{name}.csv"), index_col=0)
    d.index = [str(i) for i in d.index]
    d.columns = [str(c) for c in d.columns]
    return d.loc[list(AA), list(AA)].to_numpy(float)


REF_MEAN = _raw("blosum100")[OFF].mean()


def reference(name: str) -> np.ndarray:
    return _finish(_raw(name), REF_MEAN)


def peptideclm(df, tag: str = "mtr_large", kind: str = "res",
               exclude_index: set[str] | None = None) -> np.ndarray:
    """ROUTE A: amino-acid distances read out of PeptideCLM-2 (matched context).

    For every distinct (index peptide, single-mutant peptide) pair, take the L2
    distance between the two residue vectors AT THE MUTATED POSITION. Both come
    from the same position of two otherwise-identical peptides, so sequence
    context is held fixed and cancels; this is far better behaved than embedding
    each residue on a poly-glycine scaffold, which throws context away entirely.

    Averaged over the contexts in which each substitution is observed. Pairs are
    DE-DUPLICATED first: the displacement is a property of the peptide pair, not
    of the receptor it was assayed against, so counting it once per receptor
    would let the three most-assayed index peptides write most of the matrix.

    exclude_index: index peptides to leave out, so the matrix can be rebuilt
    without the held-out receptor's data in a leave-one-receptor-out run.
    """
    d = df[~df.is_wt]
    if exclude_index:
        d = d[~d.index_peptide.isin(exclude_index)]
    pairs = d[["index_peptide", "peptide", "pos", "wt", "mt"]].drop_duplicates(
        subset=["index_peptide", "peptide"])
    acc = np.zeros((20, 20))
    cnt = np.zeros((20, 20))
    with Embeddings(tag) as E:
        for r in pairs.itertuples():
            if not (E.has(r.index_peptide) and E.has(r.peptide)):
                continue
            a, b = E.get(kind, r.index_peptide), E.get(kind, r.peptide)
            if a.shape != b.shape:
                continue
            acc[AAI[r.wt], AAI[r.mt]] += float(np.linalg.norm(b[r.pos] - a[r.pos]))
            cnt[AAI[r.wt], AAI[r.mt]] += 1
    M = np.divide(acc, cnt, out=np.full((20, 20), np.nan), where=cnt > 0)
    return _finish(M, REF_MEAN), cnt


def get(name: str, df=None, **kw) -> np.ndarray:
    if name.startswith("peptideclm"):
        _, _, spec = name.partition(":")
        tag, _, kind = (spec or "mtr_large/res").partition("/")
        return peptideclm(df, tag=tag, kind=kind or "res", **kw)[0]
    return reference(name)
