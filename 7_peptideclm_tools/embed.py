"""
Atom-token embeddings from PeptideCLM-2, pooled onto residue positions.

For every peptide we store
  res::<pep>  : (L, d) mean over all atom tokens of each residue, in the context
                of the whole peptide SMILES
  side::<pep> : (L, d) same but only side-chain atoms (CA stands in for Gly)
  pool::<pep> : (d,)   whole-molecule mean pool
"""
import argparse
import os
import sys

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chem import peptide_smiles, token_residue_weights  # noqa: E402


def get_device(name=None):
    if name:
        return torch.device(name)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def load_model(model_name, device):
    tk = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        model_name, trust_remote_code=True, use_safetensors=True
    )
    model.eval().to(device)
    return tk, model


@torch.no_grad()
def embed_peptides(peptides, tk, model, device, canonical=True, batch_size=32,
                   progress=True):
    """dict peptide -> (res (L,d), side (L,d), pool (d,)), all float32."""
    prepared = []
    for p in peptides:
        smi, atoms = peptide_smiles(p, canonical=canonical)
        enc = tk(smi, return_offsets_mapping=True)
        ids = enc["input_ids"]
        off = enc["offset_mapping"]
        w_all = token_residue_weights(atoms, off, len(p), len(ids))
        w_side = token_residue_weights(atoms, off, len(p), len(ids),
                                       sidechain_only=True)
        prepared.append((p, ids, w_all, w_side))
    prepared.sort(key=lambda x: len(x[1]))

    out = {}
    pad_id = tk.pad_token_id
    for start in range(0, len(prepared), batch_size):
        chunk = prepared[start:start + batch_size]
        tmax = max(len(c[1]) for c in chunk)
        ids = torch.full((len(chunk), tmax), pad_id, dtype=torch.long)
        mask = torch.zeros((len(chunk), tmax), dtype=torch.long)
        for i, (_, tok_ids, _, _) in enumerate(chunk):
            ids[i, :len(tok_ids)] = torch.tensor(tok_ids)
            mask[i, :len(tok_ids)] = 1
        res = model(input_ids=ids.to(device), attention_mask=mask.to(device))
        h = res.last_hidden_state.float().cpu().numpy()
        pool = res.mean_pool.float().cpu().numpy()
        for i, (pep, tok_ids, w_all, w_side) in enumerate(chunk):
            hi = h[i, :len(tok_ids)]
            za = (w_all / np.maximum(w_all.sum(0, keepdims=True), 1e-9)).T @ hi
            zs = (w_side / np.maximum(w_side.sum(0, keepdims=True), 1e-9)).T @ hi
            out[pep] = (za, zs, pool[i])
        if progress and (start // batch_size) % 20 == 0:
            print(f"  {start + len(chunk)}/{len(prepared)}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="aaronfeller/peptideclm-2-hybrid-base")
    ap.add_argument("--out", required=True)
    ap.add_argument("--peptides", required=True)
    ap.add_argument("--canonical", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    peptides = [l.strip() for l in open(args.peptides) if l.strip()]
    device = get_device(args.device)
    print(f"{len(peptides)} peptides | {args.model} | {device}", flush=True)
    tk, model = load_model(args.model, device)
    emb = embed_peptides(peptides, tk, model, device,
                         canonical=bool(args.canonical),
                         batch_size=args.batch_size)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    store = {}
    for p, (za, zs, pl) in emb.items():
        store[f"res::{p}"] = za.astype(np.float16)
        store[f"side::{p}"] = zs.astype(np.float16)
        store[f"pool::{p}"] = pl.astype(np.float16)
    np.savez_compressed(args.out, **store)
    print("wrote", args.out, round(os.path.getsize(args.out) / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
