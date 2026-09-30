"""
Peptide sequence -> SMILES, with an exact map from SMILES characters to residues.

The map is what lets us pool atom-level token embeddings back onto residue
positions, so an atomic representation can be dropped into a position-weighted
model such as BATMAN.
"""
import re

import numpy as np
from rdkit import Chem
from rdkit import RDLogger

RDLogger.DisableLog("rdApp.*")

AA20 = list("ACDEFGHIKLMNPQRSTVWY")

# Atom tokens as RDKit writes them: bracket atoms, two-letter organic symbols
# before one-letter ones, then aromatic lower case.
_ATOM_RE = re.compile(r"\[[^\]]+\]|Cl|Br|[BCNOSPFIbcnosp*]")


BACKBONE_ATOMS = {"N", "CA", "C", "O", "OXT"}


def peptide_smiles(seq, canonical=True):
    """SMILES for a linear peptide plus (span_start, span_end, residue_index,
    is_sidechain) for every atom, in order of appearance in the string.

    residue_index is 0-based along the peptide.
    """
    mol = Chem.MolFromSequence(seq)
    if mol is None:
        raise ValueError(f"RDKit could not build a peptide from {seq!r}")
    smi = Chem.MolToSmiles(mol, canonical=canonical)
    order = mol.GetProp("_smilesAtomOutputOrder")
    order = [int(x) for x in order.strip("[]").rstrip(",").split(",")]

    res_of_atom = np.empty(mol.GetNumAtoms(), dtype=int)
    side_of_atom = np.zeros(mol.GetNumAtoms(), dtype=bool)
    name_of_atom = [""] * mol.GetNumAtoms()
    for atom in mol.GetAtoms():
        info = atom.GetPDBResidueInfo()
        if info is None:
            raise ValueError(f"no residue info on atom {atom.GetIdx()} of {seq!r}")
        res_of_atom[atom.GetIdx()] = info.GetResidueNumber() - 1
        side_of_atom[atom.GetIdx()] = info.GetName().strip() not in BACKBONE_ATOMS
        name_of_atom[atom.GetIdx()] = info.GetName().strip()

    spans = [(m.start(), m.end()) for m in _ATOM_RE.finditer(smi)]
    if len(spans) != mol.GetNumAtoms():
        raise ValueError(
            f"atom scan found {len(spans)} atoms, molecule has {mol.GetNumAtoms()} ({seq})"
        )
    atoms = [(s, e, int(res_of_atom[order[k]]), bool(side_of_atom[order[k]]),
              name_of_atom[order[k]])
             for k, (s, e) in enumerate(spans)]
    if {a[2] for a in atoms} != set(range(len(seq))):
        raise ValueError(f"residue coverage mismatch for {seq!r}")
    return smi, atoms


def token_residue_weights(atoms, offsets, n_res, n_tok, sidechain_only=False):
    """Weight matrix (n_tok, n_res): how many atoms of residue r a token covers.

    Tokens covering no atom (branch brackets, bond symbols, ring closures,
    special tokens) get zero weight and drop out of the residue pooling.
    With sidechain_only, backbone N/CA/C/O atoms are excluded; glycine then has
    no side-chain atom, so its CA is kept as a stand-in.
    """
    w = np.zeros((n_tok, n_res), dtype=np.float32)
    keep = atoms
    if sidechain_only:
        keep = [a for a in atoms if a[3]]
        covered = {a[2] for a in keep}
        keep = keep + [a for a in atoms if a[2] not in covered and a[4] == "CA"]
    for t, (ts, te) in enumerate(offsets):
        if te <= ts:
            continue
        for a_s, a_e, r, _, _ in keep:
            if a_s < te and ts < a_e:
                w[t, r] += 1.0
    return w


# ---------------------------------------------------------------------------
# Side-chain level chemistry, used for the context-free atomic matrices.
# ---------------------------------------------------------------------------

# Side chain written as a fragment attached to a dummy CA (methane carbon).
SIDECHAIN_SMILES = {
    "A": "C",
    "C": "CS",
    "D": "CC(=O)O",
    "E": "CCC(=O)O",
    "F": "Cc1ccccc1",
    "G": "[H]",
    "H": "Cc1c[nH]cn1",
    "I": "C(C)CC",
    "K": "CCCCN",
    "L": "CC(C)C",
    "M": "CCSC",
    "N": "CC(N)=O",
    "P": "CCC",
    "Q": "CCC(N)=O",
    "R": "CCCNC(N)=N",
    "S": "CO",
    "T": "C(C)O",
    "V": "C(C)C",
    "W": "Cc1c[nH]c2ccccc12",
    "Y": "Cc1ccc(O)cc1",
}


def residue_mol(aa):
    """The free amino acid, used for whole-residue descriptors."""
    return Chem.MolFromSequence(aa)


def sidechain_mol(aa):
    """Side chain as methyl-capped fragment (CH4 for Gly)."""
    smi = "C" + SIDECHAIN_SMILES[aa] if aa != "G" else "C"
    return Chem.MolFromSmiles(smi)
