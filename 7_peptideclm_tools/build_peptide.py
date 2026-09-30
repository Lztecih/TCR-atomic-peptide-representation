"""
Build a linear peptide SMILES from residue fragments, including residues that
have no one-letter code.

This is what an atomic representation buys: a peptide containing citrulline,
phosphoserine or norleucine has a SMILES string and therefore an embedding,
while a 20x20 substitution matrix has no entry for it at all.

Fragments are written N-terminus first as `N[C@@H](<side chain>)C(=O)`; the
chain is closed with a terminal `O`. Ring-closure labels are renumbered per
residue so fragments can be concatenated safely.
"""
import re

from rdkit import Chem
from rdkit import RDLogger

RDLogger.DisableLog("rdApp.*")

_ATOM_RE = re.compile(r"\[[^\]]+\]|Cl|Br|[BCNOSPFIbcnosp*]")


def _ring_spans(frag):
    """Character spans of ring-closure labels: digits and %nn outside
    bracketed atoms. Inside brackets a digit is an isotope or a charge."""
    spans, i, n = [], 0, len(frag)
    while i < n:
        c = frag[i]
        if c == "[":
            j = frag.index("]", i)
            i = j + 1
            continue
        if c == "%" and i + 2 < n and frag[i + 1:i + 3].isdigit():
            spans.append((i, i + 3))
            i += 3
            continue
        if c.isdigit():
            spans.append((i, i + 1))
            i += 1
            continue
        i += 1
    return spans

# side chain only; the backbone is supplied by the template
SIDE = {
    "A": "C", "C": "CS", "D": "CC(=O)O", "E": "CCC(=O)O", "F": "Cc1ccccc1",
    "H": "Cc1c[nH]cn1", "I": "[C@@H](C)CC", "K": "CCCCN", "L": "CC(C)C",
    "M": "CCSC", "N": "CC(N)=O", "Q": "CCC(N)=O", "R": "CCCNC(N)=N",
    "S": "CO", "T": "[C@@H](C)O", "V": "C(C)C",
    "W": "Cc1c[nH]c2ccccc12", "Y": "Cc1ccc(O)cc1",
}

# residues with no one-letter code, by their usual abbreviation
NONCANONICAL = {
    "Nle": "CCCC",                       # norleucine, Met without the sulfur
    "Nva": "CCC",                        # norvaline
    "Abu": "CC",                         # 2-aminobutyric acid
    "Orn": "CCCN",                       # ornithine, Lys one carbon shorter
    "Cit": "CCCNC(N)=O",                 # citrulline, deiminated arginine
    "Sep": "COP(=O)(O)O",                # phosphoserine
    "Cha": "CC1CCCCC1",                  # cyclohexylalanine, saturated Phe
    "Hph": "CCc1ccccc1",                 # homophenylalanine
    "Phe4F": "Cc1ccc(F)cc1",             # 4-fluorophenylalanine
    "Tyr3NO2": "Cc1ccc(O)c([N+](=O)[O-])c1",   # 3-nitrotyrosine
    "Nal": "Cc1ccc2ccccc2c1",            # 3-(2-naphthyl)alanine
}

SPECIAL = {
    "G": ("NCC(=O)", [False, False, False, False]),
    "P": ("N1CCC[C@H]1C(=O)", [False, True, True, True, False, False, False]),
    "Aib": ("NC(C)(C)C(=O)", [False, False, True, True, False, False]),
}


def _fragment(res):
    """(smiles fragment, is_sidechain per atom in fragment order)."""
    if res in SPECIAL:
        return SPECIAL[res]
    side = SIDE.get(res) or NONCANONICAL.get(res)
    if side is None:
        raise KeyError(f"unknown residue {res!r}")
    frag = f"N[C@@H]({side})C(=O)"
    n_side = len(_ATOM_RE.findall(side))
    flags = [False, False] + [True] * n_side + [False, False]
    return frag, flags


def _renumber_rings(frag, next_label):
    """Give this fragment's ring-closure labels globally unique numbers."""
    spans = _ring_spans(frag)
    if not spans:
        return frag, next_label
    mapping = {}
    for s, e in spans:
        t = frag[s:e]
        if t not in mapping:
            mapping[t] = next_label
            next_label += 1
    out, pos = [], 0
    for s, e in spans:
        n = mapping[frag[s:e]]
        out.append(frag[pos:s])
        out.append(str(n) if n < 10 else f"%{n:02d}")
        pos = e
    out.append(frag[pos:])
    return "".join(out), next_label


def build(residues):
    """SMILES plus (span_start, span_end, residue_index, is_sidechain, '') per
    atom, in the same tuple layout `chem.token_residue_weights` expects."""
    parts, atoms, label = [], [], 1
    offset = 0
    for i, res in enumerate(residues):
        frag, flags = _fragment(res)
        frag, label = _renumber_rings(frag, label)
        spans = [(m.start(), m.end()) for m in _ATOM_RE.finditer(frag)]
        if len(spans) != len(flags):
            raise RuntimeError(f"atom count mismatch in fragment for {res}")
        for (s, e), is_side in zip(spans, flags):
            atoms.append((offset + s, offset + e, i, is_side,
                          "CA" if not is_side else ""))
        parts.append(frag)
        offset += len(frag)
    smi = "".join(parts) + "O"
    if Chem.MolFromSmiles(smi) is None:
        raise ValueError(f"invalid SMILES built for {residues}: {smi}")
    return smi, atoms


def parse(seq):
    """'EVDPIGHLY' or 'EVDPIGHL/Nle/' style: slashes delimit multi-letter
    residue names."""
    out, i = [], 0
    while i < len(seq):
        if seq[i] == "/":
            j = seq.index("/", i + 1)
            out.append(seq[i + 1:j])
            i = j + 1
        else:
            out.append(seq[i])
            i += 1
    return out


if __name__ == "__main__":
    for s in ["EVDPIGHLY", "EVDPIGHL/Nle/", "GPGPG", "/Aib/W/Cit/P/Sep/",
              "EVDPIG/Cit/LY", "EVDPIGHL/Tyr3NO2/"]:
        smi, atoms = build(parse(s))
        n_res = len({a[2] for a in atoms})
        print(f"{s:24s} {n_res} residues, {len(atoms)} atoms\n  {smi}")
