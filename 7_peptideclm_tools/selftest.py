"""Self-test for the PeptideCLM-2 tooling. Run it before trusting anything here.

    python 7_peptideclm_tools/selftest.py            # mapping + builder only, no model
    python 7_peptideclm_tools/selftest.py --model    # also downloads and runs PeptideCLM-2
"""
import os
import sys

import numpy as np
from rdkit import Chem

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chem import peptide_smiles, token_residue_weights          # noqa: E402
import build_peptide as B                                       # noqa: E402
from descriptors import DESC99, describe, descriptor_functions  # noqa: E402

PEPTIDES = ["EVDPIGHLY", "ESDPIVAQY", "SIINFEKL", "FEAQKAKANKAVD", "ASQKRPSQRSK"]


def test_builder():
    for s in ["EVDPIGHLY", "EVDPIG/Cit/LY", "/Aib/W/Cit/P/Sep/", "EVDPIGHL/Tyr3NO2/"]:
        smi, _ = B.build(B.parse(s))
        assert Chem.MolFromSmiles(smi) is not None, s
    # canonical peptides must reproduce RDKit exactly, stereocentres included
    for seq in ["MNPQRSTVWY", "ACDEFGHIKL", "ILTILT"]:
        mine = Chem.CanonSmiles(B.build(B.parse(seq))[0])
        ref = Chem.CanonSmiles(Chem.MolToSmiles(Chem.MolFromSequence(seq)))
        assert mine == ref, seq
    print("builder            OK   non-canonical residues build; canonical match RDKit")


def test_descriptors():
    descriptor_functions()
    v = describe(Chem.MolFromSequence("W"))
    assert len(DESC99) == 99 and np.isfinite(v).all()
    print("descriptors        OK   99 names resolved, all finite")


def test_mapping(tokenizer=None):
    if tokenizer is None:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            "aaronfeller/peptideclm-2-hybrid-base", trust_remote_code=True)
    for p in PEPTIDES:
        smi, atoms = peptide_smiles(p)
        enc = tokenizer(smi, return_offsets_mapping=True)
        w = token_residue_weights(atoms, enc["offset_mapping"], len(p),
                                  len(enc["input_ids"]))
        assert (w.sum(0) > 0).all(), f"a residue of {p} received no token weight"
    print(f"atom->residue map  OK   {len(PEPTIDES)} peptides, every residue covered")
    return tokenizer


def test_embedding():
    from embed import embed_peptides, get_device, load_model
    dev = get_device()
    tk, model = load_model("aaronfeller/peptideclm-2-hybrid-base", dev)
    emb = embed_peptides(["EVDPIGHLY", "AVDPIGHLY", "ESDPIVAQY"], tk, model, dev,
                         progress=False)
    R = {k: v[0] for k, v in emb.items()}
    d1 = np.linalg.norm(R["AVDPIGHLY"] - R["EVDPIGHLY"], axis=1)
    d2 = np.linalg.norm(R["ESDPIVAQY"] - R["EVDPIGHLY"], axis=1)
    assert int(d1.argmax()) == 0, "a P1 mutant should move the P1 embedding most"
    assert sorted(np.argsort(d2)[-4:] + 1) == [2, 6, 7, 8], \
        "titin differs at P2,6,7,8 and those should be the four largest changes"
    print(f"embedding          OK   on {dev}; mutations localise to the right residues")


if __name__ == "__main__":
    tk = test_mapping()
    test_builder()
    test_descriptors()
    if "--model" in sys.argv:
        test_embedding()
    else:
        print("embedding          skipped (pass --model to download and run PeptideCLM-2)")
