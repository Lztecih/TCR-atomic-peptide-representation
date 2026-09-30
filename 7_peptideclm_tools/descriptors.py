"""
The 99 RDKit descriptors PeptideCLM-2 was trained to regress (its MTR head),
so that the hand-built chemical features and the language-model features
describe the same chemistry.
"""
import numpy as np
from rdkit.Chem import Descriptors, Fragments, rdMolDescriptors

DESC99 = [
    "Chi0", "Chi0n", "Chi0v", "Chi1", "Chi1n", "FpDensityMorgan2",
    "FpDensityMorgan3", "Kappa1", "Kappa2", "Kappa3", "ExactMolWt",
    "MaxAbsPartialCharge", "MaxPartialCharge", "MinAbsPartialCharge",
    "MinPartialCharge", "MolLogP", "MolMR", "MolWt", "RingCount",
    "HeavyAtomCount", "HeavyAtomMolWt", "FractionCSP3", "HallKierAlpha",
    "LabuteASA", "TPSA", "NHOHCount", "NOCount", "NumAliphaticCarbocycles",
    "NumAliphaticHeterocycles", "NumAliphaticRings", "NumAromaticCarbocycles",
    "NumAromaticHeterocycles", "NumAromaticRings", "NumHAcceptors",
    "NumHDonors", "NumHeteroatoms", "NumRadicalElectrons", "NumRotatableBonds",
    "NumSaturatedCarbocycles", "NumSaturatedHeterocycles", "NumSaturatedRings",
    "NumValenceElectrons",
] + [f"PEOE_VSA{i}" for i in range(1, 15)] \
  + [f"SMR_VSA{i}" for i in range(1, 11)] \
  + [f"SlogP_VSA{i}" for i in range(1, 13)] \
  + ["fr_amide", "fr_NH0", "fr_NH1", "fr_NH2", "fr_COO", "fr_priamide",
     "fr_guanido", "fr_imidazole", "fr_phenol", "fr_Al_OH", "fr_C_O",
     "fr_ether", "fr_alkyl_halide", "fr_unbrch_alkane", "fr_aryl_methyl",
     "fr_benzene", "fr_ester", "fr_ketone", "fr_methoxy", "fr_sulfide",
     "fr_sulfonamd"]


def _resolve(name):
    if name.startswith("fr_"):
        fn = getattr(Fragments, "fr_" + name[3:], None)
        if fn is None:
            fn = getattr(Fragments, name, None)
        if fn is None:
            fn = getattr(Descriptors, name, None)
        return fn
    fn = getattr(Descriptors, name, None)
    if fn is None:
        fn = getattr(rdMolDescriptors, "Calc" + name, None)
    return fn


_FNS = None


def descriptor_functions():
    global _FNS
    if _FNS is None:
        _FNS = []
        missing = []
        for n in DESC99:
            fn = _resolve(n)
            if fn is None:
                missing.append(n)
            else:
                _FNS.append((n, fn))
        if missing:
            raise RuntimeError(f"RDKit is missing descriptors: {missing}")
    return _FNS


def describe(mol):
    """99-vector for one molecule; non-finite values become 0."""
    out = np.zeros(len(DESC99), dtype=np.float64)
    for i, (_, fn) in enumerate(descriptor_functions()):
        try:
            v = float(fn(mol))
        except Exception:
            v = 0.0
        out[i] = v if np.isfinite(v) else 0.0
    return out
