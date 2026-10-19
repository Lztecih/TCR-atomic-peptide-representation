"""Feature construction for ROUTE B (whole-peptide distance) and ROUTE C.

ROUTE C replaces the single matrix lookup M[a,b] by a vector describing the
substitution in the context of the peptide it happens in:

    u_idx        (q) whitened projection of the index residue embedding
    u_mut        (q) whitened projection of the mutant residue embedding
    |u_mut-u_idx|(q) componentwise change
    ||dz||, dzcos (2) size and cosine distance of the embedding change
    desc        (24) signed and absolute change in 12 interpretable RDKit
                     descriptors of the free amino acid

With q = 16 that is 3*16 + 2 = 50 language-model coefficients plus 24 chemical
ones, 74 in total. Rows with no substitution are all-zero, so the index peptide
keeps distance zero from itself.

The projection and the standardisation are fitted on TRAINING ROWS ONLY and
applied unchanged to test rows; neither sees an activation label. The descriptor
z-scoring constants are not fitted on training rows at all -- they come from the
20 free amino acids, so they are identical in every fold.
"""
from __future__ import annotations

import numpy as np

from data import AA, AAI
from embeddings import Embeddings

# twelve interpretable descriptors, entered signed and absolute -> 24 features
DESC_KEEP = ["MolWt", "MolLogP", "TPSA", "NumHDonors", "NumHAcceptors",
             "FractionCSP3", "NumAromaticRings", "NumRotatableBonds",
             "LabuteASA", "MaxPartialCharge", "MinPartialCharge", "HallKierAlpha"]

FREE_AA = {
    "A": "CC(N)C(=O)O", "C": "NC(CS)C(=O)O", "D": "NC(CC(=O)O)C(=O)O",
    "E": "NC(CCC(=O)O)C(=O)O", "F": "NC(Cc1ccccc1)C(=O)O", "G": "NCC(=O)O",
    "H": "NC(Cc1c[nH]cn1)C(=O)O", "I": "CCC(C)C(N)C(=O)O", "K": "NCCCCC(N)C(=O)O",
    "L": "CC(C)CC(N)C(=O)O", "M": "CSCCC(N)C(=O)O", "N": "NC(CC(N)=O)C(=O)O",
    "P": "OC(=O)C1CCCN1", "Q": "NC(CCC(N)=O)C(=O)O", "R": "NC(CCCNC(N)=N)C(=O)O",
    "S": "NC(CO)C(=O)O", "T": "CC(O)C(N)C(=O)O", "V": "CC(C)C(N)C(=O)O",
    "W": "NC(Cc1c[nH]c2ccccc12)C(=O)O", "Y": "NC(Cc1ccc(O)cc1)C(=O)O",
}

_DESC = None


def aa_descriptors() -> np.ndarray:
    """(20, 12) z-scored descriptors of the free amino acids. Fold-independent."""
    global _DESC
    if _DESC is None:
        from rdkit import Chem
        from rdkit.Chem import Descriptors
        fn = dict(Descriptors.descList)
        X = np.array([[fn[n](Chem.MolFromSmiles(FREE_AA[a])) for n in DESC_KEEP]
                      for a in AA], float)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        _DESC = (X - X.mean(0)) / np.where(X.std(0) > 0, X.std(0), 1.0)
    return _DESC


def substitution_lookups(d, mats):
    """(n, len(mats)) columns of M[wt, mt], zero on unsubstituted rows.

    Used by the A x C combination: the substitution-matrix value becomes one
    more coordinate of x_p, alongside the context features. In this soft form
    the model is free to shrink it to zero, so a gain here means the matrix
    carries something the context features do not.
    """
    out = np.zeros((len(d), len(mats)))
    for i, r in enumerate(d.itertuples()):
        if r.pos >= 0:
            for j, M in enumerate(mats):
                out[i, j] = M[AAI[r.wt], AAI[r.mt]]
    return out


def _residue_pairs(d, E, kind):
    """(n, dim) index-residue and mutant-residue vectors at the mutated position."""
    dim = E.dim
    a = np.zeros((len(d), dim), np.float32)
    b = np.zeros((len(d), dim), np.float32)
    ok = np.zeros(len(d), bool)
    for i, r in enumerate(d.itertuples()):
        if r.pos < 0 or not (E.has(r.index_peptide) and E.has(r.peptide)):
            continue
        va, vb = E.get(kind, r.index_peptide), E.get(kind, r.peptide)
        if va.shape != vb.shape:
            continue
        a[i], b[i], ok[i] = va[r.pos], vb[r.pos], True
    return a, b, ok


def fit_projection(vectors, q=16):
    """Whitening PCA fitted on training residue vectors; returns a callable.

    Factored out so the multi-residue scoring path applies the IDENTICAL
    transform as the single-residue training path. If the two ever diverge the
    comparison is meaningless, so there must be exactly one implementation.
    Eigenvector signs are pinned (largest-magnitude loading forced positive) so
    a component means the same thing across folds.
    """
    Z = np.asarray(vectors, np.float64)
    mu = Z.mean(0)
    U, S, Vt = np.linalg.svd(Z - mu, full_matrices=False)
    k = min(q, int((S > 1e-8).sum()))
    V = Vt[:k].copy()
    for j in range(k):
        if V[j][np.argmax(np.abs(V[j]))] < 0:
            V[j] = -V[j]
    scale = np.where(S[:k] > 1e-8, S[:k] / np.sqrt(max(len(Z) - 1, 1)), 1.0)
    return lambda x: ((np.asarray(x, np.float64) - mu) @ V.T) / scale


# Which language-model blocks to include. `u_idx` is the projection of the INDEX
# peptide's residue, which is fixed for a receptor, so it is a pure lookup of
# (receptor, position) -- measured R^2 = 1.0000 -- and carries no information
# about what the residue became. Within a receptor that is harmless, but across
# receptors it is a 16-dimensional receptor fingerprint and the coefficients
# learned on it are meaningless for a receptor never seen. PLM_BLOCKS lets an
# arm drop it.
PLM_BLOCKS = ("u_idx", "u_mut", "diff", "scalar")


def route_c(train, test, tag="mtr_large", kind="res", q=16,
            use_plm=True, use_desc=True, mats=None, blocks=PLM_BLOCKS):
    """ROUTE C feature matrices (n, K), gated to zero on unsubstituted rows.

    `mats`: optional list of 20x20 matrices whose [wt, mt] lookup is appended as
    extra columns -- the soft form of the A x C combination.
    """
    with Embeddings(tag) as E:
        atr, btr, oktr = _residue_pairs(train, E, kind)
        ate, bte, okte = _residue_pairs(test, E, kind)

    blocks_tr, blocks_te = [], []
    if use_plm:
        # whitening PCA fitted on TRAINING residue vectors only, no labels
        proj = fit_projection(np.vstack([atr[oktr], btr[oktr]]), q=q)

        for (a, b, ok) in ((atr, btr, oktr), (ate, bte, okte)):
            ua, ub = proj(a), proj(b)
            dz = b.astype(np.float64) - a.astype(np.float64)
            nrm = np.linalg.norm(dz, axis=1, keepdims=True)
            na = np.linalg.norm(a, axis=1); nb = np.linalg.norm(b, axis=1)
            cos = 1.0 - (a * b).sum(1) / np.where(na * nb > 0, na * nb, 1.0)
            parts = []
            if "u_idx" in blocks: parts.append(ua)
            if "u_mut" in blocks: parts.append(ub)
            if "diff" in blocks: parts.append(np.abs(ub - ua))
            if "scalar" in blocks: parts.extend([nrm, cos[:, None]])
            blk = np.hstack(parts) if parts else np.zeros((len(a), 0))
            blk[~ok] = 0.0
            (blocks_tr if a is atr else blocks_te).append(blk)

    if use_desc:
        Dsc = aa_descriptors()
        for d, ok in ((train, oktr), (test, okte)):
            n = len(d)
            s = np.zeros((n, len(DESC_KEEP)))
            for i, r in enumerate(d.itertuples()):
                if r.pos >= 0:
                    s[i] = Dsc[AAI[r.mt]] - Dsc[AAI[r.wt]]
            blk = np.hstack([s, np.abs(s)])
            blk[d.pos.to_numpy() < 0] = 0.0
            (blocks_tr if d is train else blocks_te).append(blk)

    if mats:
        blocks_tr.append(substitution_lookups(train, mats))
        blocks_te.append(substitution_lookups(test, mats))

    Xtr = np.hstack(blocks_tr) if blocks_tr else np.zeros((len(train), 0))
    Xte = np.hstack(blocks_te) if blocks_te else np.zeros((len(test), 0))
    # standardise on training rows that actually carry a substitution
    m = train.pos.to_numpy() >= 0
    mu_f = Xtr[m].mean(0) if m.any() else np.zeros(Xtr.shape[1])
    sd_f = Xtr[m].std(0) if m.any() else np.ones(Xtr.shape[1])
    sd_f = np.where(sd_f > 1e-9, sd_f, 1.0)
    Xtr = (Xtr - mu_f) / sd_f
    Xte = (Xte - mu_f) / sd_f
    Xtr[train.pos.to_numpy() < 0] = 0.0
    Xte[test.pos.to_numpy() < 0] = 0.0
    return Xtr, Xte


def route_b(train, test, tag="mtr_large", q=32, center=True):
    """ROUTE B inputs: whole-peptide embedding difference, PCA-reduced.

    d is then a learned low-rank quadratic form on this vector (see model.py),
    not a raw norm -- a single scalar norm of a 1024-dim difference discards
    nearly all of it.
    """
    with Embeddings(tag) as E:
        def diff(d):
            X = np.zeros((len(d), E.dim), np.float32)
            for i, r in enumerate(d.itertuples()):
                if E.has(r.index_peptide) and E.has(r.peptide):
                    X[i] = E.get("pool", r.peptide) - E.get("pool", r.index_peptide)
            return X
        Dtr, Dte = diff(train), diff(test)
    # center=False is required by the B x C combination: the whole-peptide term
    # must vanish exactly when peptide == index, and subtracting a mean would
    # leave a non-zero offset on those rows and break d(index, index) = 0.
    mu = Dtr.mean(0) if center else np.zeros(Dtr.shape[1], Dtr.dtype)
    U, S, Vt = np.linalg.svd(Dtr - mu, full_matrices=False)
    k = min(q, (S > 1e-8).sum())
    V = Vt[:k]
    for j in range(k):
        if V[j][np.argmax(np.abs(V[j]))] < 0:
            V[j] = -V[j]
    sc = np.where(S[:k] > 1e-8, S[:k] / np.sqrt(max(len(Dtr) - 1, 1)), 1.0)
    return ((Dtr - mu) @ V.T) / sc, ((Dte - mu) @ V.T) / sc


def route_c_multi(train, multi, tag="mtr_large", kind="res", q=16,
                  use_plm=True, use_desc=True, blocks=PLM_BLOCKS):
    """Per-position features for MULTI-residue mutants.

    Returns (Xtr, Xm) where Xtr is the ordinary (n_train, K) single-substitution
    matrix used to FIT the model, and Xm is (n_multi, L, K): the same feature
    vector evaluated at EVERY substituted position of each multi-residue mutant,
    zero at positions that match the index peptide.

    The projection and the feature standardisation are fitted once on the
    training rows and applied to both, so the multi-residue distance is the same
    function of a substitution as the one the model was trained on. That is the
    whole point: the model sees only single substitutions during training and
    must extrapolate to several at once.
    """
    with Embeddings(tag) as E:
        atr, btr, oktr = _residue_pairs(train, E, kind)
        L = len(multi["index"].iloc[0])
        dim = E.dim
        ai = np.zeros((len(multi), L, dim), np.float32)
        bi = np.zeros((len(multi), L, dim), np.float32)
        mask = np.zeros((len(multi), L), bool)
        for i, r in enumerate(multi.itertuples()):
            idx, pep = getattr(r, "index"), r.peptide
            if not (E.has(idx) and E.has(pep)):
                continue
            va, vb = E.get(kind, idx), E.get(kind, pep)
            if va.shape != vb.shape or va.shape[0] != L:
                continue
            for p in range(L):
                if idx[p] != pep[p]:
                    ai[i, p], bi[i, p], mask[i, p] = va[p], vb[p], True

    btr_tr, bte_tr = [], []
    if use_plm:
        proj = fit_projection(np.vstack([atr[oktr], btr[oktr]]), q=q)
        ua, ub = proj(atr), proj(btr)
        dz = btr.astype(np.float64) - atr.astype(np.float64)
        nrm = np.linalg.norm(dz, axis=1, keepdims=True)
        na, nb = np.linalg.norm(atr, axis=1), np.linalg.norm(btr, axis=1)
        cos = 1.0 - (atr * btr).sum(1) / np.where(na * nb > 0, na * nb, 1.0)
        parts = []
        if "u_idx" in blocks: parts.append(ua)
        if "u_mut" in blocks: parts.append(ub)
        if "diff" in blocks: parts.append(np.abs(ub - ua))
        if "scalar" in blocks: parts.extend([nrm, cos[:, None]])
        blk = np.hstack(parts)
        blk[~oktr] = 0.0
        btr_tr.append(blk)

        flat_a, flat_b = ai.reshape(-1, dim), bi.reshape(-1, dim)
        ua2, ub2 = proj(flat_a), proj(flat_b)
        dz2 = flat_b.astype(np.float64) - flat_a.astype(np.float64)
        nrm2 = np.linalg.norm(dz2, axis=1, keepdims=True)
        na2, nb2 = np.linalg.norm(flat_a, axis=1), np.linalg.norm(flat_b, axis=1)
        cos2 = 1.0 - (flat_a * flat_b).sum(1) / np.where(na2 * nb2 > 0, na2 * nb2, 1.0)
        parts2 = []
        if "u_idx" in blocks: parts2.append(ua2)
        if "u_mut" in blocks: parts2.append(ub2)
        if "diff" in blocks: parts2.append(np.abs(ub2 - ua2))
        if "scalar" in blocks: parts2.extend([nrm2, cos2[:, None]])
        blk2 = np.hstack(parts2)
        blk2[~mask.reshape(-1)] = 0.0
        bte_tr.append(blk2)

    if use_desc:
        Dsc = aa_descriptors()
        s = np.zeros((len(train), len(DESC_KEEP)))
        for i, r in enumerate(train.itertuples()):
            if r.pos >= 0:
                s[i] = Dsc[AAI[r.mt]] - Dsc[AAI[r.wt]]
        b1 = np.hstack([s, np.abs(s)]); b1[train.pos.to_numpy() < 0] = 0.0
        btr_tr.append(b1)

        s2 = np.zeros((len(multi), L, len(DESC_KEEP)))
        for i, r in enumerate(multi.itertuples()):
            idx, pep = getattr(r, "index"), r.peptide
            if len(idx) != L or len(pep) != L:
                continue
            for p in range(L):
                if idx[p] != pep[p] and idx[p] in AAI and pep[p] in AAI:
                    s2[i, p] = Dsc[AAI[pep[p]]] - Dsc[AAI[idx[p]]]
        b2 = np.concatenate([s2, np.abs(s2)], axis=-1).reshape(len(multi) * L, -1)
        b2[~mask.reshape(-1)] = 0.0
        bte_tr.append(b2)

    Xtr = np.hstack(btr_tr)
    Xm = np.hstack(bte_tr)
    m = train.pos.to_numpy() >= 0
    mu_f = Xtr[m].mean(0)
    sd_f = np.where(Xtr[m].std(0) > 1e-9, Xtr[m].std(0), 1.0)
    Xtr = (Xtr - mu_f) / sd_f
    Xm = (Xm - mu_f) / sd_f
    Xtr[train.pos.to_numpy() < 0] = 0.0
    Xm[~mask.reshape(-1)] = 0.0
    return Xtr, Xm.reshape(len(multi), L, -1), mask


def route_b_multi(train, multi, tag="mtr_large", q=32):
    """Whole-peptide embedding difference for train and for multi-residue mutants.

    Uncentred, so the projection of an unmutated peptide is exactly zero.
    """
    with Embeddings(tag) as E:
        def diff(d, icol):
            X = np.zeros((len(d), E.dim), np.float32)
            for i, r in enumerate(d.itertuples()):
                idx = getattr(r, icol)
                if E.has(idx) and E.has(r.peptide):
                    X[i] = E.get("pool", r.peptide) - E.get("pool", idx)
            return X
        Dtr = diff(train, "index_peptide")
        Dm = diff(multi, "index")
    U, S, Vt = np.linalg.svd(Dtr, full_matrices=False)
    k = min(q, int((S > 1e-8).sum()))
    V = Vt[:k].copy()
    for j in range(k):
        if V[j][np.argmax(np.abs(V[j]))] < 0:
            V[j] = -V[j]
    sc = np.where(S[:k] > 1e-8, S[:k] / np.sqrt(max(len(Dtr) - 1, 1)), 1.0)
    return (Dtr @ V.T) / sc, (Dm @ V.T) / sc


# --- receptor-side features -------------------------------------------------
# The diagnosed bottleneck: w(p) is learned per receptor and does not transfer,
# so a receptor never seen before only gets the population-average profile --
# which is worth almost nothing (positional-weights-only scores 0.519 on
# leave-one-receptor-out, against a chance floor of 0.5). The receptor's own
# CDR3 loops are what contact the peptide, they are known for any new receptor,
# and BATCAVE carries them for 106 of 151 receptors. They are currently unused.

CDR3_COLS = ["cdr3b", "cdr3a"]
_CHARGE = {"D": -1.0, "E": -1.0, "K": +1.0, "R": +1.0, "H": +0.5}
_AROMATIC = set("FWY")


def _hydrophobicity():
    """Wimley-White interfacial scale from data/raw/interfacial_hydrophobicity.xlsx."""
    import os
    import pandas as pd
    from data import DATA
    d = pd.read_excel(os.path.join(DATA, "raw", "interfacial_hydrophobicity.xlsx"))
    return dict(zip(d.AA.astype(str), d.interfacial_hydrophobicity.astype(float)))


def cdr3_features(df, tcrs, fit=None):
    """(T, J) standardised CDR3 descriptors, one row per receptor in `tcrs`.

    Four scalars per loop (length, net charge, mean interfacial hydrophobicity,
    aromatic fraction) for CDR3-beta and CDR3-alpha. Receptors with no CDR3 on
    record get the all-zero (= mean) row, so they fall back to the population
    profile rather than being dropped.

    fit: the receptors whose rows the mean and sd are computed from. Pass the
    TRAINING receptors on a held-out protocol; standardising over training and
    held-out rows together lets the held-out receptor's own descriptors move the
    scale every training row is expressed on. The leak is small and it flatters
    the CDR3 arms, so a conclusion that the CDR3 arms do not help survives it --
    but it is still the held-out receptor touching the fit. Default (None) keeps
    the old behaviour of fitting on every row in `tcrs`.
    """
    hyd = _hydrophobicity()

    def describe(seq):
        if not isinstance(seq, str) or not seq:
            return None
        aa = [c for c in seq if c in AAI]
        if not aa:
            return None
        return [float(len(aa)),
                float(sum(_CHARGE.get(c, 0.0) for c in aa)),
                float(np.mean([hyd.get(c, 0.0) for c in aa])),
                float(sum(c in _AROMATIC for c in aa) / len(aa))]

    rows, have = [], []
    for t in tcrs:
        g = df[df.tcr == t]
        vec = []
        ok = False
        for col in CDR3_COLS:
            v = g[col].dropna()
            d = describe(v.iloc[0]) if len(v) else None
            if d is None:
                vec += [np.nan] * 4
            else:
                vec += d; ok = True
        rows.append(vec); have.append(ok)
    X = np.array(rows, float)
    if fit is None:
        F = X
    else:
        keep = [i for i, t in enumerate(tcrs) if t in set(fit)]
        F = X[keep] if keep else X
    with np.errstate(invalid="ignore"):
        mu = np.nanmean(F, axis=0)
        sd = np.nanstd(F, axis=0)
    mu = np.where(np.isfinite(mu), mu, 0.0)
    sd = np.where(np.isfinite(sd) & (sd > 1e-9), sd, 1.0)
    X = (X - mu) / sd
    return np.nan_to_num(X, nan=0.0), np.array(have)
