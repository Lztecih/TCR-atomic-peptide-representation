"""
proteome_screen.py
==================
Path B: proteome-scale TCR target discovery.

The mutational-scan benchmark asks "how accurately does the model rank
single-amino-acid mutants?". This module asks the question a clinician
actually has: **given a TCR, can we find its real targets in a whole
proteome?**

Data: the TScan-II genome-wide / virome-wide screens shipped as supplementary
files with Kula et al. and never used by BATCAVE (259,344 and 96,099 peptides
respectively). Each screen gives a fold-enrichment per ~90-mer library
construct; a handful of them are genuine TCR targets.

For the CTAG1B (NY-ESO-1) screen the ground truth is unusually informative:

    fold  90-mer contains                       identity
    69.4  LPVPGVLLKEFTVSGNILTI  (exact index)   NY-ESO-1  -- the source antigen
   125.2  LPRPGAVLKDFTVSGNLLFM  (Hamming 7)     LAGE-1    -- a cross-reactive paralog
    36.0  ...VRKEFTVTSLDENQ...  (distant)       unrelated protein sharing KEFTV

so the screen contains both the trivial positive and genuinely distant
cross-reactive targets -- exactly the "targets with high sequence
dissimilarity" the source paper highlights.

Scoring: every L-mer window of every construct is scored with the model's
peptide-to-index distance; a construct's score is its best (smallest) window.
Ranking 259k constructs means scoring ~17.9M windows, done in chunks.
"""



from __future__ import annotations

import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r=_os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r,"batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0,_r)
# --- end bootstrap: shared library lives one level up ---

import os
import urllib.request

import numpy as np
import pandas as pd

import batman_atomic as ba

RAW_DIR = os.path.join(ba.ROOT, "data", "raw_audit")

#: Screens available, with the BATCAVE TCR / index peptide they correspond to.
SCREENS = {
    "ctag1b_genome": dict(
        file="tscanII_mmc2.xlsx", sheet="Table S2A",
        tcr="TCR-3598-2", index="LPVPGVLLKEFTVSGNILTI",
        mhc="HLA-DRB1*04:01", label="CTAG1B (NY-ESO-1) human genome-wide"),
    "hiv_virome": dict(
        file="tscanII_mmc1.xlsx", sheet="Tavle S1C",
        tcr="TCR-F5", index="FRDYVDRFYKTLRAEQASQE",
        mhc="HLA-DRB1*11:01", label="HIV virome-wide"),
    "hiv_genome": dict(
        file="tscanII_mmc1.xlsx", sheet="Table S1A",
        tcr="TCR-F5", index="FRDYVDRFYKTLRAEQASQE",
        mhc="HLA-DRB1*11:01", label="HIV genome-wide"),
}

_MMC_URL = (
    "https://raw.githubusercontent.com/meyer-lab-cshl/BATMAN-paper/main/"
    "results_batman/tcr_epitope_datasets/mutational_scan_datasets/"
    "TCR_data_input_by_publication/MHCII/TScanII-TCRs/"
)


def load_screen(name: str) -> tuple[pd.DataFrame, dict]:
    """Load one screen as (DataFrame[pep, fe], metadata)."""
    meta = SCREENS[name]
    os.makedirs(RAW_DIR, exist_ok=True)
    path = os.path.join(RAW_DIR, meta["file"])
    if not os.path.exists(path):
        urllib.request.urlretrieve(_MMC_URL + meta["file"], path)

    d = pd.read_excel(path, sheet_name=meta["sheet"], header=1)
    d = d.iloc[:, :3]
    d.columns = ["pid", "pep", "fe"]
    d["fe"] = pd.to_numeric(d.fe, errors="coerce")
    d["pep"] = d.pep.astype(str).str.strip().str.upper()
    d = d.dropna(subset=["fe"])
    d = d[d.pep.str.fullmatch(r"[ACDEFGHIKLMNPQRSTVWY]+")]
    return d.reset_index(drop=True), meta


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

def _encode(seqs: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Pack sequences into one flat int8 array plus start offsets."""
    flat = np.frombuffer("".join(seqs).encode(), dtype=np.uint8)
    lut = np.full(256, -1, dtype=np.int8)
    for aa, i in ba.AA_IDX.items():
        lut[ord(aa)] = i
    codes = lut[flat]
    starts = np.zeros(len(seqs) + 1, dtype=np.int64)
    starts[1:] = np.cumsum([len(s) for s in seqs])
    return codes, starts


def score_screen(seqs, index_peptide: str, M: np.ndarray, w: np.ndarray,
                 chunk: int = 20000, reduce: str = "min") -> np.ndarray:
    """Best peptide-to-index distance over all L-mer windows of each sequence.

    ``M`` is the 20x20 substitution distance and ``w`` the positional weight
    profile (length L). Sequences shorter than L score +inf.
    """
    L = len(index_peptide)
    idx_i = np.array([ba.AA_IDX[c] for c in index_peptide])
    # Precompute the per-position cost of seeing residue b at position j:
    #   cost[j, b] = w[j] * M[index[j], b]
    cost = (w[:, None] * M[idx_i, :])                       # (L, 20)

    codes, starts = _encode(list(seqs))
    n = len(starts) - 1
    out = np.full(n, np.inf)

    for lo in range(0, n, chunk):
        hi = min(lo + chunk, n)
        for i in range(lo, hi):
            a, b = starts[i], starts[i + 1]
            seg = codes[a:b]
            if seg.size < L or (seg < 0).any():
                continue
            # sliding windows without copying
            win = np.lib.stride_tricks.sliding_window_view(seg, L)  # (nw, L)
            d = cost[np.arange(L), win].sum(axis=1)
            out[i] = d.min() if reduce == "min" else d.max()
    return out


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------

def evaluate(scores: np.ndarray, fe: np.ndarray, threshold: float = 2.0,
             ks=(10, 100, 1000)) -> dict:
    """Rank-based metrics for an extremely imbalanced retrieval task.

    AUC is uninformative when positives are 0.005% of the data, so the headline
    numbers are the ranks of the true hits and precision/recall at small k.
    """
    valid = np.isfinite(scores)
    s, f = scores[valid], fe[valid]
    order = np.argsort(s, kind="stable")           # small distance = top rank
    ranks = np.empty(len(s), dtype=np.int64)
    ranks[order] = np.arange(1, len(s) + 1)

    hit = f > threshold
    n_hit = int(hit.sum())
    res = {
        "n_scored": int(valid.sum()),
        "n_hits": n_hit,
        "hit_ranks": np.sort(ranks[hit]).tolist(),
        "median_hit_rank": float(np.median(ranks[hit])) if n_hit else np.nan,
        "best_hit_rank": int(ranks[hit].min()) if n_hit else -1,
    }
    for k in ks:
        in_top = int((ranks[hit] <= k).sum())
        res[f"recall@{k}"] = in_top / n_hit if n_hit else np.nan
        res[f"precision@{k}"] = in_top / k
    # enrichment of hits in the top 1% vs base rate
    top1 = max(1, len(s) // 100)
    base = n_hit / len(s) if len(s) else np.nan
    res["enrichment@top1%"] = ((ranks[hit] <= top1).sum() / top1) / base if base else np.nan
    return res


def hit_table(d: pd.DataFrame, scores: np.ndarray, index_peptide: str,
              threshold: float = 2.0) -> pd.DataFrame:
    """Per-hit detail: rank, distance, and closest window to the index."""
    valid = np.isfinite(scores)
    order = np.argsort(np.where(valid, scores, np.inf), kind="stable")
    ranks = np.empty(len(scores), dtype=np.int64)
    ranks[order] = np.arange(1, len(scores) + 1)

    L = len(index_peptide)
    rows = []
    for i in np.where(d.fe.values > threshold)[0]:
        pep = d.pep.iloc[i]
        best_win, best_ham = "", -1
        if len(pep) >= L:
            hams = [sum(a != b for a, b in zip(index_peptide, pep[s:s + L]))
                    for s in range(len(pep) - L + 1)]
            j = int(np.argmin(hams))
            best_win, best_ham = pep[j:j + L], hams[j]
        rows.append(dict(pid=d.pid.iloc[i], fe=round(float(d.fe.iloc[i]), 2),
                         rank=int(ranks[i]), distance=round(float(scores[i]), 3),
                         hamming=best_ham, window=best_win))
    return pd.DataFrame(rows).sort_values("fe", ascending=False)
