"""
mhc_filter.py
=============
Test whether MHC-II presentation is the missing signal in proteome-scale TCR
target retrieval.

Background (see PATH_B_FINDINGS.md): every substitution model -- fixed BLOSUM,
learned 20x20, atomic, hybrid -- ranks the true genome-wide targets identically,
and a plain Hamming distance does just as well. The top decoys are peptides that
are sequence-similar to the index yet non-activating. The natural hypothesis is
that those decoys are simply not presented by the relevant HLA-DR allele, so an
MHC-binding filter should separate them from the real targets.

Testing that needs an MHC-II binding score for arbitrary genome-wide windows.
A neural predictor (NetMHCIIpan) will not install under this Python 3.14 offline
environment, so we build a transparent surrogate from data we *do* have: the
BATMAN repo ships real NetMHCIIpan predictions for the two relevant alleles
(DRB1*04:01, DRB1*11:01) on the single-aa mutational scan of each index 20-mer.

Those 381 mutants are exactly an MHC-binding mutational scan of the index. From
them we build an additive per-position core PSSM (an eluted-ligand-score model
local to the index register). It is validated only in the neighbourhood of the
index and is explicitly a surrogate, not a replacement for a full NetMHCIIpan
run -- the module is written so a real NetMHCIIpan table can be dropped in.

    build_core_pssm(allele)      -> (PSSM[20 index-positions, 20 aa], core_slice)
    mhc_el_score(window, pssm)   -> mean eluted-ligand score over the core
"""

from __future__ import annotations

import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r=_os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r,"batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0,_r)


import os

import numpy as np
import pandas as pd

import batman_atomic as ba

#: NetMHCIIpan predictions shipped with the repo, per screen allele.
NETMHCII = {
    "DRB1_0401": dict(file="DRB1_0401_20_formated.csv",
                      index="LPVPGVLLKEFTVSGNILTI"),
    "DRB1_1101": dict(file="DRB1_1101_20_formated.csv",
                      index="FRDYVDRFYKTLRAEQASQE"),
}
#: which allele each screen uses
SCREEN_ALLELE = {"ctag1b_genome": "DRB1_0401",
                 "hiv_genome": "DRB1_1101",
                 "hiv_virome": "DRB1_1101"}


def _mut_pos_aa(pep: str, index: str):
    diff = [i for i in range(len(index)) if i < len(pep) and pep[i] != index[i]]
    return (diff[0], pep[diff[0]]) if len(diff) == 1 else (-1, None)


def build_core_pssm(allele: str, score_col: str = "Score_EL"):
    """Additive per-position PSSM of NetMHCIIpan eluted-ligand score.

    Returns (pssm, core_slice) where pssm[p, a] is the whole-peptide score when
    residue a sits at index position p (index elsewhere), and core_slice is the
    range of index positions NetMHCIIpan placed the 9-mer binding core in.
    """
    meta = NETMHCII[allele]
    d = pd.read_csv(os.path.join(ba.DATA_DIR, "netmhcii", meta["file"]))
    index = meta["index"]
    base = (d[d.Peptide == index][score_col].iloc[0]
            if (d.Peptide == index).any() else d[score_col].median())

    idx_aa = [ba.AA_IDX[c] for c in index]
    pssm = np.full((len(index), 20), np.nan)
    for _, r in d.iterrows():
        p, a = _mut_pos_aa(r.Peptide, index)
        if p >= 0:
            pssm[p, ba.AA_IDX[a]] = r[score_col]
    for p in range(len(index)):
        if np.isnan(pssm[p, idx_aa[p]]):
            pssm[p, idx_aa[p]] = base
    colmean = np.nanmean(pssm, axis=1)
    for p in range(len(index)):
        m = np.isnan(pssm[p])
        pssm[p, m] = colmean[p] if not np.isnan(colmean[p]) else base

    core = d[d.Peptide == index].Core.iloc[0] if (d.Peptide == index).any() \
        else d.Core.mode().iloc[0]
    cstart = index.find(core)
    core_slice = range(cstart, cstart + 9) if cstart >= 0 else range(0, 9)
    return pssm, core_slice


def mhc_el_score(window: str, pssm: np.ndarray, core_slice) -> float:
    """Mean eluted-ligand score over the core, for a window aligned to the index."""
    vals = [pssm[p, ba.AA_IDX[window[p]]]
            for p in core_slice if p < len(window) and window[p] in ba.AA_IDX]
    return float(np.mean(vals)) if vals else np.nan


def best_window(pep: str, index: str) -> str:
    """The window of pep with the smallest Hamming distance to the index."""
    L = len(index)
    if len(pep) < L:
        return ""
    hams = [sum(a != b for a, b in zip(index, pep[s:s + L]))
            for s in range(len(pep) - L + 1)]
    j = int(np.argmin(hams))
    return pep[j:j + L]
