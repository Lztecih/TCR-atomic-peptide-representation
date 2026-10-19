"""Accessor for the precomputed PeptideCLM-2 embeddings in data/proc/.

Three checkpoints were run over the peptide set:
    emb_hybrid_base.npz   dim  768   peptideclm-2-hybrid-base   (114M)
    emb_hybrid_large.npz  dim 1024   peptideclm-2-hybrid-large  (337M)
    emb_mtr_large.npz     dim 1024   peptideclm-2-mtr-large     (337M)

Each stores three arrays per peptide:
    res::<pep>   (L, dim)  per-residue vector, pooling all atoms of the residue
    side::<pep>  (L, dim)  per-residue vector over the non-backbone atoms
    pool::<pep>  (dim,)    whole-peptide vector

Two traps this module exists to close:
  - numpy's NpzFile.files has ALREADY stripped the '.npy' suffix, while
    zipfile.namelist() has not. Slicing four characters off a key read from
    .files silently corrupts every peptide name and yields all-NaN features.
  - the arrays are stored float16. Always cast to float32 before any norm, dot
    product or covariance: float16 accumulation overflows and loses precision.
"""
from __future__ import annotations

import os
import numpy as np

from data import DATA

FILES = {
    "hybrid_base": "emb_hybrid_base.npz",
    "hybrid_large": "emb_hybrid_large.npz",
    "mtr_large": "emb_mtr_large.npz",
}


class Embeddings:
    def __init__(self, tag: str = "mtr_large"):
        if tag not in FILES:
            raise ValueError(f"unknown checkpoint {tag!r}; have {sorted(FILES)}")
        self.tag = tag
        self.z = np.load(os.path.join(DATA, "proc", FILES[tag]))
        self.have = {k.split("::", 1)[1] for k in self.z.files if k.startswith("pool::")}
        self._c: dict[tuple[str, str], np.ndarray] = {}

    @property
    def dim(self) -> int:
        return int(self.get("pool", next(iter(self.have))).shape[0])

    def get(self, kind: str, pep: str) -> np.ndarray:
        key = (kind, pep)
        if key not in self._c:
            self._c[key] = self.z[f"{kind}::{pep}"].astype(np.float32)
        return self._c[key]

    def has(self, pep: str) -> bool:
        return pep in self.have

    def close(self):
        self.z.close(); self._c.clear()

    def __enter__(self): return self
    def __exit__(self, *a): self.close()
