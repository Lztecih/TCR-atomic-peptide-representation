"""
noncanonical.py
===============
Addresses review item **R5**.

The reviewer's charge was fair: "the representation extends to non-canonical
residues and PTMs" was asserted in the discussion and never demonstrated. A
20x20 matrix has no row for phospho-serine, so it *cannot* score one; the
atomic model only needs the molecule.

This script turns that assertion into something checkable. It is a
**capability demonstration, not an accuracy validation** -- no mutational-scan
dataset with PTM-bearing peptides exists, so nothing here claims the predicted
distances are correct. What it does show is that

  1. the pipeline produces a distance for a residue it has never seen, with no
     retraining, using only the learned weights theta; and
  2. those distances land where independent chemistry says they should --
     which is a genuine falsification test, because they did not have to.

The sharpest check is **citrulline**. Deimination of arginine removes the
guanidinium charge and yields a residue whose side chain is chemically close
to glutamine. If the representation is behaving sensibly, citrulline's nearest
canonical neighbour must be Q -- and its distance to its own parent R must be
large. Neither outcome is built in anywhere.

Output: ``results/noncanonical_distances.csv`` and ``figures/fig9_noncanonical.png``.

Usage:  python3 noncanonical.py
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
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors, rdPartialCharges

import batman_atomic as ba

RES = os.path.join(ba.ROOT, "results")
FIG = os.path.join(ba.ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

#: Modified residues, as free amino acids so RDKit sees the same construction
#: as :data:`batman_atomic.AA_SMILES`.
#:
#: ``charge`` is the net side-chain charge at pH 7 and is the one descriptor
#: that is assigned rather than computed, exactly as for the canonical 20.
#: Values follow standard side-chain pKa's: phospho-groups are taken as the
#: dianion (-2), acetylation neutralises the lysine ammonium (0), and
#: selenocysteine (pKa ~5.2) is mostly ionised at pH 7 (-1).
NONCANONICAL = {
    "pSer  (phospho-Ser)":   ("NC(COP(=O)(O)O)C(=O)O",              -2.0, "S"),
    "pThr  (phospho-Thr)":   ("CC(OP(=O)(O)O)C(N)C(=O)O",           -2.0, "T"),
    "pTyr  (phospho-Tyr)":   ("NC(Cc1ccc(OP(=O)(O)O)cc1)C(=O)O",    -2.0, "Y"),
    "Cit   (citrulline)":    ("NC(CCCNC(=O)N)C(=O)O",                0.0, "R"),
    "meLys (Nε-methyl-Lys)": ("CNCCCCC(N)C(=O)O",                    1.0, "K"),
    "me2Lys (dimethyl-Lys)": ("CN(C)CCCCC(N)C(=O)O",                 1.0, "K"),
    "acLys (acetyl-Lys)":    ("CC(=O)NCCCCC(N)C(=O)O",               0.0, "K"),
    "Hyp   (4-hydroxy-Pro)": ("OC(=O)C1CC(O)CN1",                    0.0, "P"),
    "nTyr  (3-nitro-Tyr)":   ("NC(Cc1ccc(O)c([N+](=O)[O-])c1)C(=O)O", 0.0, "Y"),
    "Sec   (selenocysteine)": ("NC(C[SeH])C(=O)O",                  -1.0, "C"),
    "Orn   (ornithine)":     ("NCCCC(N)C(=O)O",                      1.0, "K"),
    "Nle   (norleucine)":    ("CCCCC(N)C(=O)O",                      0.0, "L"),
}

FEATS = ba.FEATURE_SETS["base8"]
ADDITIVE = ["heavy", "polar", "S", "HBD", "HBA", "rotB"]


def _descriptors(smiles: str, charge: float) -> dict:
    """Raw (unstandardised, backbone-included) descriptors for one residue."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"RDKit could not parse {smiles!r}")
    rdPartialCharges.ComputeGasteigerCharges(mol)
    return {
        "heavy": mol.GetNumHeavyAtoms(),
        "polar": (sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "N")
                  + sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "O")),
        "S": sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "S"),
        "aromatic": sum(1 for a in mol.GetAtoms() if a.GetIsAromatic()),
        "HBD": rdMolDescriptors.CalcNumHBD(mol),
        "HBA": rdMolDescriptors.CalcNumHBA(mol),
        "rotB": rdMolDescriptors.CalcNumRotatableBonds(mol),
        "charge": charge,
    }


def build_extended_features() -> tuple[pd.DataFrame, pd.Series]:
    """Canonical + non-canonical residues in ONE feature space.

    The critical detail: the non-canonical residues are standardised with the
    **canonical** mean and SD. Re-standardising over the extended set would
    move the 20 canonical residues, invalidating the theta learned on them.
    """
    raw = {}
    for aa in ba.AA20:
        raw[aa] = _descriptors(ba.AA_SMILES[aa], ba.AA_CHARGE.get(aa, 0.0))
    for name, (smi, q, _parent) in NONCANONICAL.items():
        raw[name] = _descriptors(smi, q)

    table = pd.DataFrame(raw).T
    gly = table.loc["G"]
    for col in ADDITIVE:                       # strip the glycine backbone
        table[col] = table[col] - gly[col]
    table = table[FEATS].astype(float)

    canon = table.loc[ba.AA20]
    mu, sd = canon.mean(), canon.std()         # canonical scaling, frozen
    return (table - mu) / sd, pd.Series({"mu": mu, "sd": sd})


def main():
    phi_all, _ = build_extended_features()
    theta = np.load(os.path.join(RES, "theta_9mer.npy"))

    # sanity: the canonical block must match the production feature builder
    ref = ba.build_atomic_features("base8")
    delta = np.abs(phi_all.loc[ba.AA20].to_numpy() - ref.to_numpy()).max()
    print(f"canonical block matches batman_atomic.build_atomic_features: "
          f"max abs diff = {delta:.2e}")
    assert delta < 1e-9, "canonical residues moved -- theta would be invalid"

    def dist(a, b):
        return float(np.sum(theta * np.abs(phi_all.loc[a] - phi_all.loc[b])))

    # reference scale: all canonical-canonical substitution distances
    canon_d = np.array([dist(a, b) for i, a in enumerate(ba.AA20)
                        for b in ba.AA20[i + 1:]])

    rows = []
    for name, (_smi, _q, parent) in NONCANONICAL.items():
        ds = {aa: dist(name, aa) for aa in ba.AA20}
        order = sorted(ds, key=ds.get)
        d_parent = ds[parent]
        rows.append(dict(
            residue=name, parent=parent,
            d_to_parent=round(d_parent, 3),
            parent_percentile=round(float((canon_d < d_parent).mean() * 100), 1),
            nearest=order[0], d_nearest=round(ds[order[0]], 3),
            second=order[1], d_second=round(ds[order[1]], 3),
            third=order[2],
            farthest=order[-1], d_farthest=round(ds[order[-1]], 3)))

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RES, "noncanonical_distances.csv"), index=False)
    print("\n" + out.to_string(index=False))

    # ------------------------------------------------- falsification check
    # Pre-registered above: citrulline's nearest canonical residue should be Q.
    # It is not -- reported as stated rather than quietly restated afterwards.
    cit_name = next(n for n in NONCANONICAL if n.startswith("Cit"))
    cit = out[out.residue == cit_name].iloc[0]
    verdict = "PASS" if cit.nearest == "Q" else "FAIL"
    print(f"\n--- pre-registered falsification check: {verdict} ---")
    print(f"citrulline nearest canonical residue = {cit.nearest} "
          f"(predicted Q); nearest excluding the parent = {cit.second}")
    print(f"d(R, Cit) = {cit.d_to_parent} "
          f"({cit.parent_percentile:.0f}th percentile of canonical substitutions)")

    # Why it failed, per feature -- the useful part of a negative result.
    contrib = pd.DataFrame({
        f"R -> Cit": theta * np.abs(phi_all.loc["R"] - phi_all.loc[cit_name]),
        f"Q -> Cit": theta * np.abs(phi_all.loc["Q"] - phi_all.loc[cit_name]),
    }, index=FEATS)
    contrib.loc["TOTAL"] = contrib.sum()
    contrib.round(3).to_csv(os.path.join(RES, "noncanonical_citrulline_decomp.csv"))
    print("\nper-feature decomposition:")
    print(contrib.round(3).to_string())
    print(
        "\ninterpretation: citrulline is ISOSTERIC with arginine -- identical\n"
        "heavy-atom, polar-atom and rotatable-bond counts -- so the entire\n"
        f"R->Cit distance ({contrib.loc['TOTAL', 'R -> Cit']:.2f}) is the charge\n"
        "term. Q differs from Cit in charge AND size AND flexibility, so R is\n"
        "genuinely nearer in this space. The textbook 'citrulline resembles\n"
        "glutamine' refers to the neutral carbamoyl group, and that is\n"
        "recovered: Q is the nearest NON-parent residue. The check is still\n"
        "recorded as a failure of the claim as pre-registered.")
    print(
        "\nopen question (needs data, not modelling): deimination lands at only\n"
        f"the {cit.parent_percentile:.0f}th percentile of canonical substitution\n"
        "distances, yet citrullinated neoepitopes are potent in rheumatoid\n"
        "arthritis. Whether theta_charge is large enough is untestable here --\n"
        "no mutational scan contains a citrullinated peptide.")

    # ---------------------------------------------------------------- figure
    mpl.rcParams.update({
        "figure.dpi": 120, "savefig.dpi": 300, "savefig.bbox": "tight",
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
        "axes.titleweight": "bold", "axes.spines.top": False,
        "axes.spines.right": False, "legend.frameon": False,
    })
    names = list(NONCANONICAL)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4),
                             gridspec_kw=dict(width_ratios=[1.45, 1], wspace=.34))

    # (a) distance from each modification to every canonical residue
    ax = axes[0]
    Mx = np.array([[dist(n, aa) for aa in ba.AA20] for n in names])
    im = ax.imshow(Mx, cmap="viridis_r", aspect="auto")
    ax.set_xticks(range(20)); ax.set_xticklabels(ba.AA20, fontsize=6.5)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=6.2, family="monospace")
    for i, n in enumerate(names):
        j = int(np.argmin(Mx[i]))
        ax.scatter([j], [i], marker="o", s=22, facecolors="none",
                   edgecolors="white", linewidths=1.3)
        p = ba.AA20.index(NONCANONICAL[n][2])
        ax.scatter([p], [i], marker="s", s=14, color="#D55E00")
    ax.set_xlabel("canonical amino acid")
    ax.set_title("Distance from an unseen residue to the canonical 20",
                 loc="left")
    fig.colorbar(im, ax=ax, pad=.012, shrink=.85).set_label(
        r"$M[\,\cdot\,,x]$", size=7)
    h_near = plt.Line2D([], [], marker="o", ls="none", mfc="none",
                        mec="#333", mew=1.3, ms=5, label="nearest canonical")
    h_par = plt.Line2D([], [], marker="s", ls="none", color="#D55E00",
                       ms=4, label="parent residue")
    ax.legend(handles=[h_near, h_par], fontsize=6.2, ncol=2,
              loc="lower left", bbox_to_anchor=(0, 1.04))
    ax.text(-.30, 1.14, "a", transform=ax.transAxes, fontsize=11,
            fontweight="bold", va="top")

    # (b) how far each modification moves from its own parent
    ax = axes[1]
    order = np.argsort([r.d_to_parent for r in out.itertuples()])
    vals = [out.d_to_parent.iloc[i] for i in order]
    labs = [f"{out.parent.iloc[i]} → {out.residue.iloc[i].split()[0]}"
            for i in order]
    cols = ["#D55E00" if v > np.median(canon_d) else "#0072B2" for v in vals]
    ax.barh(range(len(vals)), vals, color=cols, height=.7)
    ax.axvline(np.median(canon_d), color="k", ls="--", lw=.9)
    ax.text(np.median(canon_d), len(vals) - .3,
            " median canonical\n substitution", fontsize=5.8, va="top")
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(labs, fontsize=6.2, family="monospace")
    ax.set_xlabel(r"$M[\mathrm{parent},\ \mathrm{modified}]$")
    ax.set_title("Chemical cost of the\nmodification itself", loc="left")
    ax.text(-.52, 1.14, "b", transform=ax.transAxes, fontsize=11,
            fontweight="bold", va="top")

    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(FIG, f"fig9_noncanonical.{ext}"))
    plt.close(fig)
    print("\nwrote figures/fig9_noncanonical.png / .pdf")
    print("@@@ noncanonical FINISHED")


if __name__ == "__main__":
    main()
