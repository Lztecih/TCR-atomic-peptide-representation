"""
# PeptideCLM-2 tooling: atom-level embeddings pooled onto residue positions

Standalone, dependency-light code for using a SMILES-level molecular language
model on peptides **at residue resolution**. Nothing here depends on the rest of
this repository.

The piece that took the work is `chem.py`. A molecular language model tokenises
a SMILES string, not a sequence, and the tokeniser merges several atoms into one
token and sometimes spans a peptide bond. To pool its embeddings back onto
residue positions you need an exact map from SMILES characters to residues.

## What each file does

| file | what it gives you | needs |
| --- | --- | --- |
| `chem.py` | peptide → SMILES plus an exact atom-to-residue map, and a token→residue weight matrix for any tokeniser that reports character offsets | rdkit |
| `build_peptide.py` | peptides containing residues with no one-letter code — citrulline, phosphoserine, norleucine, nitrotyrosine, Aib and others — written as valid SMILES with the same atom map | rdkit |
| `descriptors.py` | the 99 RDKit descriptors PeptideCLM-2's regression head is trained to predict | rdkit |
| `embed.py` | batched embedding of many peptides, pooled onto residues two ways: all atoms, or side-chain atoms only | + transformers, torch |
| `selftest.py` | checks all of the above | |

## Check it works

```bash
pip install -r requirements.txt
python 7_peptideclm_tools/selftest.py            # mapping + builder, no model download
python 7_peptideclm_tools/selftest.py --model    # also runs PeptideCLM-2
```

Expected:

```
atom->residue map  OK   5 peptides, every residue covered
builder            OK   non-canonical residues build; canonical match RDKit
descriptors        OK   99 names resolved, all finite
embedding          OK   on mps; mutations localise to the right residues
```

## Use

```python
from chem import peptide_smiles, token_residue_weights
from transformers import AutoTokenizer

tk = AutoTokenizer.from_pretrained("aaronfeller/peptideclm-2-hybrid-base",
                                   trust_remote_code=True)
smi, atoms = peptide_smiles("EVDPIGHLY")
enc = tk(smi, return_offsets_mapping=True)
w = token_residue_weights(atoms, enc["offset_mapping"], 9, len(enc["input_ids"]))
# w is (n_tokens, 9): how many atoms of residue r each token covers.
# residue_embedding = (w / w.sum(0)).T @ last_hidden_state
```

Whole pipeline for many peptides:

```bash
python 7_peptideclm_tools/embed.py \\
    --model aaronfeller/peptideclm-2-hybrid-base \\
    --peptides peptides.txt --out emb.npz
```

Residues with no one-letter code, using `/Name/` notation:

```python
import build_peptide as B
smi, atoms = B.build(B.parse("EVDPIG/Cit/LY"))   # citrulline at position 7
```

Available: `Nle Nva Abu Orn Cit Sep Cha Hph Phe4F Tyr3NO2 Nal Aib`. Adding one
is a single line in `NONCANONICAL`.

## Validation

- The atom-to-residue map runs without a failure over all **6,453** distinct
  peptides used in this project, checked against `mol.GetNumAtoms()` each time.
- The builder reproduces RDKit's own molecules **exactly**, stereocentres
  included, for canonical peptides.
- The pooling localises mutations without being told where they are: for
  `EVDPIGHLY`, the single mutant `AVDPIGHLY` moves the position-1 residue
  embedding by 12.4 in L2 norm against a median of 0.9 elsewhere; for the titin
  peptide `ESDPIVAQY`, which differs at positions 2, 6, 7 and 8, those four are
  exactly the four largest changes.

## What we found when we used it, which you should know before you rely on it

This tooling was built to test whether PeptideCLM-2 embeddings improve
prediction of TCR cross-reactivity. **Measured against 24 plain RDKit
descriptors on the same task, they did not.**

| features | within-receptor AUC |
| --- | --- |
| 24 RDKit descriptors, no language model | 0.8509 |
| + 50 PeptideCLM-2 embedding features | 0.8555 |

The increment is **+0.0046 (p = 0.23)**, against a measured inference noise
floor of 0.0054 AUC — smaller than the noise of the fitting procedure. Tripling
the model (114M → 337M, same pre-training objective) changed nothing
(+0.0003, p = 0.57). Read context-free as a 20x20 substitution matrix, the model
scored *below* the 99 hand-computed descriptors.

So: the tooling is offered as tooling. It is correct, tested and reusable, and
it is the right way to get residue-resolution embeddings out of a SMILES model.
Whether those embeddings help your task is a separate question, and on ours the
honest answer was no.

The one thing the atomic route does that a 20x20 table cannot is score residues
outside the twenty-letter alphabet, and that capability lives in
`build_peptide.py` and `descriptors.py` — not in the language model.

## Attribution

PeptideCLM-2: Feller, Secor, Swanson, Wilke and Deibler.
<https://github.com/AaronFeller/PeptideCLM-2> · weights at
<https://huggingface.co/aaronfeller>. This directory contains no PeptideCLM-2
code or weights, only code that calls the published model.
"""
