"""
malone2025.py
=============
Loader for the **Malone et al. 2025** TCR fingerprinting dataset -- an external
validation set that is independent of BATCAVE in every way that matters.

    Malone M.J., Huang C., Zhang Y., Qi Y., Williams L., Su L.F., Lou J.,
    Jiang N. *Resistance potential of the HLA-A2-restricted immunodominant
    SARS-CoV-2-specific CD8+ T cell receptor repertoire to antigenic drift.*
    Nat Commun (2025). doi:10.1038/s41467-025-67336-w

What it contains: every single-amino-acid variant of the HLA-A*02:01 epitope
`YLQPRTFLL` (SARS-CoV-2 spike 269-277) assayed against 23 TCR clones by
DNA-barcoded pMHC tetramer staining.

Why it is a genuinely hard external test -- three things differ at once:

    1. the TCRs are unseen        -> no per-TCR positional weights exist
    2. the epitope is unseen      -> YLQPRTFLL is not among BATCAVE's 25
    3. the readout is different   -> tetramer BINDING (continuous log2 fold
                                     change), not functional activation in
                                     three ordered levels

Point 3 is the important caveat: a TCR can bind without being activated, so
agreement here is not the same quantity the models were fitted on.

Three data-quality decisions, all made from the file itself:

  * Of the 172 rows, 3 carry the wild-type sequence (the labelled one plus two
    unlabelled duplicates) and 1 is a transcription slip (`YLQSPTFLL`, two
    positions from wild type). Dropping those leaves 168 clean single
    substitutions -- 98% of the 171 that a complete scan would contain.
  * The wild-type row is dropped from scoring: its distance is 0 under every
    model, so keeping it would hand every model the same free correct call.
  * Only TCRs for which the wild type really is the index peptide are used.
    The criterion is stated before looking at any model output: wild type must
    rank in the top 10% of that TCR's own binding profile. 20 of 23 TCRs pass
    with wild-type rank 1-8; the 3 that fail sit at rank 36, 80 and 81. This
    matches the paper, which reports 20 clones isolated with wild-type antigen
    and one isolated from a pool of R5 mutants.

Usage:
    import malone2025 as ml
    tidy, wide = ml.load()
"""

from __future__ import annotations

# --- bootstrap: shared library lives one level up ---
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
# --- end bootstrap ---

import os
import urllib.request

import numpy as np
import pandas as pd

import batman_atomic as ba

INDEX_PEPTIDE = "YLQPRTFLL"          # SARS-CoV-2 spike 269-277, HLA-A*02:01
MHC = "HLA-A*02:01"
SHEET = "Fig3b-c_Fig4a_Fig5a_Fingerprint"

DATA_DIR = os.path.join(ba.ROOT, "data", "malone2025")
FILENAME = "41467_2025_67336_MOESM4_ESM.xlsx"
URL = ("https://static-content.springer.com/esm/"
       "art%3A10.1038%2Fs41467-025-67336-w/MediaObjects/" + FILENAME)

#: wild type must rank inside this top fraction of a TCR's own profile for
#: YLQPRTFLL to count as that TCR's index peptide
WT_RANK_FRACTION = 0.10


def download(cache_dir: str = DATA_DIR) -> str:
    """Fetch the supplementary workbook (open access) if it is not cached."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, FILENAME)
    if not os.path.exists(path):
        print(f"downloading Malone 2025 supplementary data -> {path}")
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r, open(path, "wb") as fh:
            fh.write(r.read())
    return path


def load(cache_dir: str = DATA_DIR, verbose: bool = True):
    """Return (tidy, wide).

    tidy : one row per (TCR, peptide) with columns
           index_peptide, peptide, tcr, binding, mutation_position
    wide : peptides x TCRs matrix of binding values (index-peptide row removed)

    Only clean single substitutions and only index-peptide TCRs are kept.
    """
    raw = pd.read_excel(download(cache_dir), sheet_name=SHEET)
    tcols = [c for c in raw.columns if c.startswith("SVAR")]
    # row 0 is labelled "YLQPRTFLL wild type" -- take the sequence token only
    peps = (raw["Antigen peptide"].astype(str).str.strip()
            .str.split().str[0].str.upper())

    # ---- keep clean single substitutions -------------------------------
    def hamming(p):
        if len(p) != len(INDEX_PEPTIDE):
            return -1
        return sum(a != b for a, b in zip(INDEX_PEPTIDE, p))

    ham = peps.apply(hamming)
    keep = (ham == 1)                  # excludes the wild type AND the 3 bad rows
    n_wt = int((ham == 0).sum())       # the wild type and its 2 duplicate rows
    n_bad = int(((ham != 1) & (ham != 0)).sum())   # transcription slip
    clean = raw[keep].copy()
    clean_peps = peps[keep]

    # ---- decide which TCRs treat YLQPRTFLL as their index peptide ------
    n_all = len(raw)
    cutoff = max(1, int(round(WT_RANK_FRACTION * n_all)))
    index_tcrs, other_tcrs, wt_rank = [], [], {}
    for c in tcols:
        v = raw[c].to_numpy(dtype=float)
        rank = int((v > v[0]).sum()) + 1        # row 0 is the wild type
        wt_rank[c] = rank
        (index_tcrs if rank <= cutoff else other_tcrs).append(c)

    wide = clean[tcols].copy()
    wide.index = clean_peps.to_numpy()

    rows = []
    for c in tcols:
        for pep, val in zip(clean_peps, clean[c]):
            pos = next(i + 1 for i, (a, b) in enumerate(zip(INDEX_PEPTIDE, pep))
                       if a != b)
            rows.append(dict(index_peptide=INDEX_PEPTIDE, peptide=pep, tcr=c,
                             binding=float(val), mutation_position=pos,
                             mhc=MHC,
                             is_index_tcr=c in index_tcrs))
    tidy = pd.DataFrame(rows)

    if verbose:
        print(f"Malone 2025: {len(clean)} clean single substitutions of "
              f"{INDEX_PEPTIDE} (of 171 possible) | dropped {n_wt} wild-type "
              f"rows + {n_bad} malformed")
        print(f"  TCRs total {len(tcols)} | index-peptide TCRs "
              f"{len(index_tcrs)} (wild-type rank <= {cutoff}) | excluded "
              f"{len(other_tcrs)}: "
              + ", ".join(f"{c}(rank {wt_rank[c]})" for c in other_tcrs))
        cov = tidy[tidy.tcr == tcols[0]].mutation_position.value_counts().sort_index()
        print(f"  substitutions per position: {cov.to_dict()}")

    tidy.attrs["index_tcrs"] = index_tcrs
    tidy.attrs["other_tcrs"] = other_tcrs
    tidy.attrs["wt_rank"] = wt_rank
    return tidy, wide


if __name__ == "__main__":
    tidy, wide = load()
    print("\ntidy:", tidy.shape, "| wide:", wide.shape)
    print(tidy.head(4).to_string(index=False))
