"""
batman_atomic.py
================
Atomic-representation Bayesian model for TCR-peptide cross-reactivity.

Replaces the 20x20 amino-acid substitution matrix M of BATMAN
(Banerjee et al., Cell Systems 16, 101345, 2025) with a learned weighted
distance in an *atomic* feature space:

    M[a,b] = sum_k theta_k * |phi_k(a) - phi_k(b)|,   theta_k >= 0

Three model variants share an identical ordered-logistic backbone and differ
only in how M is defined:

    "fixed"   : M = BLOSUM100-derived distance (0 free parameters)
    "learned" : M = D * (1 + delta),  delta ~ Normal(mu, sigma)   (~380 params)
    "atomic"  : M = sum_k theta_k |dphi_k|                        (K params)

All heavy lifting lives here so the notebook stays readable.
"""

from __future__ import annotations

import os
import urllib.request

# Anchor every default path to the project root (the directory holding this
# file), so scripts import and run identically from any sub-folder.
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")

import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt
from rdkit import Chem
from rdkit.Chem import Crippen, rdMolDescriptors, rdPartialCharges
from sklearn.metrics import roc_auc_score

__all__ = [
    "AA20", "AA_IDX", "AA_SMILES", "FEATURE_SETS",
    "build_atomic_features", "load_blosum100_distance",
    "prepare", "build_model", "fit", "posterior_distance",
    "mean_pairwise_auc", "per_tcr_auc", "bootstrap_ci", "paired_wilcoxon",
    "load_batcave", "load_multi_hamming", "load_atchley_factors",
]

# --------------------------------------------------------------------------
# Amino-acid definitions
# --------------------------------------------------------------------------

AA20 = list("ACDEFGHIKLMNPQRSTVWY")
AA_IDX = {a: i for i, a in enumerate(AA20)}

#: Neutral canonical SMILES for the 20 standard amino acids (full residue).
AA_SMILES = {
    "A": "CC(N)C(=O)O",
    "R": "NC(CCCNC(=N)N)C(=O)O",
    "N": "NC(CC(=O)N)C(=O)O",
    "D": "NC(CC(=O)O)C(=O)O",
    "C": "NC(CS)C(=O)O",
    "Q": "NC(CCC(=O)N)C(=O)O",
    "E": "NC(CCC(=O)O)C(=O)O",
    "G": "NCC(=O)O",
    "H": "NC(Cc1cnc[nH]1)C(=O)O",
    "I": "CCC(C)C(N)C(=O)O",
    "L": "CC(C)CC(N)C(=O)O",
    "K": "NCCCCC(N)C(=O)O",
    "M": "CSCCC(N)C(=O)O",
    "F": "NC(Cc1ccccc1)C(=O)O",
    "P": "OC(=O)C1CCCN1",
    "S": "NC(CO)C(=O)O",
    "T": "CC(O)C(N)C(=O)O",
    "W": "NC(Cc1c[nH]c2ccccc12)C(=O)O",
    "Y": "NC(Cc1ccc(O)cc1)C(=O)O",
    "V": "CC(C)C(N)C(=O)O",
}

#: Net side-chain charge at pH 7 (His partially protonated).
AA_CHARGE = {"D": -1.0, "E": -1.0, "K": 1.0, "R": 1.0, "H": 0.1}

#: Named feature sets used across the experiments.
#:
#: ``full11`` deliberately avoids TPSA and LabuteASA: those are near-duplicates
#: of ``polar`` (r = 0.97) and ``heavy`` (r = 0.99), and including them pushes
#: the design matrix condition number from ~14 to ~172, which leaves theta
#: unidentifiable and makes ADVI diverge to NaN on long peptides. The Gasteiger
#: partial-charge extremes used instead carry genuinely new electrostatic
#: information (worst |r| vs the base set is 0.41) at condition number ~15.
FEATURE_SETS = {
    "base8": ["heavy", "polar", "S", "aromatic", "HBD", "HBA", "rotB", "charge"],
    "plus_logp": ["heavy", "polar", "S", "aromatic", "HBD", "HBA", "rotB",
                  "charge", "logP"],
    "full11": ["heavy", "polar", "S", "aromatic", "HBD", "HBA", "rotB",
               "charge", "logP", "qmin", "qmax"],
}


def _count_atom(mol, symbol: str) -> int:
    return sum(1 for a in mol.GetAtoms() if a.GetSymbol() == symbol)


def load_atchley_factors(cache_dir: str = DATA_DIR) -> pd.DataFrame:
    """Atchley et al. (2005) five-factor amino-acid descriptors, z-scored.

    Included as a *prior-art baseline*: these five published numbers are the
    encoding pTEAM already uses, so any claim that the atomic representation
    contributes something new has to beat them on the same splits.
    """
    path = os.path.join(cache_dir, "atchley_clean.csv")
    d = pd.read_csv(path, index_col=0)
    d = (d - d.mean()) / d.std()
    return d.loc[AA20]


def build_atomic_features(feature_set: str | list[str] = "base8",
                          standardize: bool = True) -> pd.DataFrame:
    """Compute side-chain atomic descriptors for the 20 amino acids.

    Descriptors are computed on the full residue with RDKit, then glycine
    (pure backbone) is subtracted from the additive ones so that what remains
    describes the *side chain* only -- the part a point mutation changes.

    Returns a (20, K) DataFrame indexed by one-letter code, ordered as AA20.
    """
    feats = FEATURE_SETS[feature_set] if isinstance(feature_set, str) else list(feature_set)

    rows = []
    for aa in AA20:
        mol = Chem.MolFromSmiles(AA_SMILES[aa])
        rdPartialCharges.ComputeGasteigerCharges(mol)
        charges = [a.GetDoubleProp("_GasteigerCharge") for a in mol.GetAtoms()]
        rows.append({
            "aa": aa,
            "heavy": mol.GetNumHeavyAtoms(),
            "polar": _count_atom(mol, "N") + _count_atom(mol, "O"),
            "S": _count_atom(mol, "S"),
            "aromatic": sum(1 for a in mol.GetAtoms() if a.GetIsAromatic()),
            "HBD": rdMolDescriptors.CalcNumHBD(mol),
            "HBA": rdMolDescriptors.CalcNumHBA(mol),
            "rotB": rdMolDescriptors.CalcNumRotatableBonds(mol),
            "logP": Crippen.MolLogP(mol),
            "TPSA": rdMolDescriptors.CalcTPSA(mol),
            "LabuteASA": rdMolDescriptors.CalcLabuteASA(mol),
            # Atom-level electrostatics: the most positive / most negative
            # partial charge anywhere in the residue.
            "qmax": max(charges),
            "qmin": min(charges),
            "charge": AA_CHARGE.get(aa, 0.0),
        })
    table = pd.DataFrame(rows).set_index("aa")

    # Subtract the glycine backbone from additive (count-like) descriptors.
    additive = ["heavy", "polar", "S", "HBD", "HBA", "rotB",
                "logP", "TPSA", "LabuteASA"]
    gly = table.loc["G"]
    for col in additive:
        table[col] = table[col] - gly[col]

    out = table[feats].astype(float)
    if standardize:
        out = (out - out.mean()) / out.std()
    return out.loc[AA20]


# --------------------------------------------------------------------------
# Substitution matrices
# --------------------------------------------------------------------------

_BLOSUM100_URL = (
    "https://raw.githubusercontent.com/meyer-lab-cshl/BATMAN-paper/main/"
    "results_batman/batman_functions/AA_matrices/blosum100.csv"
)


def load_blosum100_distance(cache_dir: str = DATA_DIR) -> np.ndarray:
    """Return the (20, 20) BLOSUM100-derived distance matrix used by BATMAN.

    This is the matrix produced by Eq. 24 of the paper,

        D[a,b] = (1 - B[a,b]/B[a,a]) * (1 - B[b,a]/B[b,b])

    fetched directly from the authors' repository (already transformed), so it
    matches the published prior exactly. Rows/columns follow AA20 order.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, "blosum100_distance.csv")
    if not os.path.exists(path):
        urllib.request.urlretrieve(_BLOSUM100_URL, path)
    mat = pd.read_csv(path, index_col=0).loc[AA20, AA20]
    arr = mat.to_numpy(dtype=float)
    np.fill_diagonal(arr, 0.0)
    return arr


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

_BATCAVE_URL = (
    "https://raw.githubusercontent.com/meyer-lab-cshl/BATMAN-paper/main/"
    "results_batman/tcr_epitope_datasets/mutational_scan_datasets/"
    "train_test_data_folds.xlsx"
)

_MULTI_HAMMING_FILES = [
    "868Z11_papers/868Z11_multi_hamming_all.csv",
    "EWW-TCR_papers/EWW-TCR_multi_hamming_all.csv",
    "MAGE_papers/a3a_multi_hamming_all.csv",
    "MBP-TCR_papers/MBP-TCR_multi_hamming_all.csv",
    "TCR-1E6_papers/TCR-1E6_multi_hamming_all.csv",
    "TIL1383I_papers/TIL1383I_multi_hamming_all.csv",
    "c259_papers/c259_multi_hamming_all.csv",
]
_MH_BASE = (
    "https://raw.githubusercontent.com/meyer-lab-cshl/BATMAN-paper/main/"
    "results_batman/tcr_epitope_datasets/more_than_one_hamming_datasets/"
)


def load_batcave(cache_dir: str = DATA_DIR) -> pd.DataFrame:
    """Load the processed BATCAVE single-aa mutational scan table.

    Looks for a local clone first, then a cached download, then fetches.
    """
    candidates = [
        os.path.join(ROOT, "BATMAN-paper", "results_batman",
                     "tcr_epitope_datasets", "mutational_scan_datasets",
                     "train_test_data_folds.xlsx"),
        os.path.join(cache_dir, "train_test_data_folds.xlsx"),
        os.path.join(ROOT, "train_test_data_folds.xlsx"),
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if path is None:
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, "train_test_data_folds.xlsx")
        urllib.request.urlretrieve(_BATCAVE_URL, path)
    return pd.read_excel(path)


def load_multi_hamming(cache_dir: str = DATA_DIR) -> pd.DataFrame:
    """Load the multi-amino-acid ('more than one hamming') mutant datasets.

    These peptides carry 2+ simultaneous substitutions and are held out
    entirely from training -- a strictly harder generalization test than the
    single-aa scans.
    """
    out_dir = os.path.join(cache_dir, "multi_hamming")
    os.makedirs(out_dir, exist_ok=True)
    frames = []
    for rel in _MULTI_HAMMING_FILES:
        name = os.path.basename(rel)
        local = os.path.join(out_dir, name)
        if not os.path.exists(local):
            urllib.request.urlretrieve(_MH_BASE + rel, local)
        frames.append(pd.read_csv(local))
    mh = pd.concat(frames, ignore_index=True)

    # Keep only well-formed rows with 2+ substitutions and canonical residues.
    same_len = mh.peptide.str.len() == mh.index_peptide.str.len()
    mh = mh[same_len].copy()
    mh["hamming"] = [sum(x != y for x, y in zip(a, b))
                     for a, b in zip(mh.index_peptide, mh.peptide)]
    valid = (mh.peptide.apply(lambda s: all(c in AA_IDX for c in s))
             & mh.index_peptide.apply(lambda s: all(c in AA_IDX for c in s)))
    return mh[valid & (mh.hamming >= 2)].reset_index(drop=True)


# --------------------------------------------------------------------------
# Array preparation
# --------------------------------------------------------------------------

def prepare(df: pd.DataFrame, phi: np.ndarray,
            tcr_index: dict[str, int] | None = None) -> dict:
    """Turn a peptide table into the arrays the models consume.

    Returns a dict with:
        idxI, idxP : (n, L) residue indices of index / mutant peptide
        dphi       : (n, L, K) |phi(index) - phi(mutant)| per position
        y          : (n,) activation label in {0, 1, 2}
        tcr_i      : (n,) TCR index
        tcr_names  : list of TCR names in index order
        mhc        : (n,) pMHC binding level index (0=SB, 1=WB, 2=NB) or None
    """
    df = df.reset_index(drop=True)
    L = len(df.index_peptide.iloc[0])
    K = phi.shape[1]

    idxI = np.array([[AA_IDX[c] for c in s] for s in df.index_peptide])
    idxP = np.array([[AA_IDX[c] for c in s] for s in df.peptide])

    # |dphi| is zero wherever the residue is unchanged, so d(index, index) = 0.
    changed = idxI != idxP
    dphi = np.where(changed[:, :, None],
                    np.abs(phi[idxI] - phi[idxP]), 0.0)

    if tcr_index is None:
        tcr_index = {t: i for i, t in enumerate(sorted(df.tcr.unique()))}
    tcr_i = df.tcr.map(tcr_index).to_numpy()

    mhc = None
    if "BindLevel" in df.columns:
        level_map = {"SB": 0, "WB": 1, "NB": 2}
        mhc = df.BindLevel.map(level_map).fillna(2).astype(int).to_numpy()

    return {
        "idxI": idxI, "idxP": idxP, "dphi": dphi,
        "y": df.activation.to_numpy(dtype=int),
        "tcr_i": tcr_i,
        "tcr_names": [t for t, _ in sorted(tcr_index.items(), key=lambda kv: kv[1])],
        "n_tcr": len(tcr_index), "L": L, "K": K,
        "mhc": mhc,
    }


def feature_scale(arrays: dict) -> float:
    """Scale that puts the quadratic feature-interaction term on the same
    footing as the linear backbone term.

    The residual of ``hybrid_feature`` is a quadratic form in |dphi|. Raw, that
    term runs about five times larger than the linear backbone (mean 57 vs 12
    on the 8-mer group) and peaks high enough to overflow the ordered-logistic
    link, which makes ADVI diverge at every learning rate. Dividing |dphi| by
    this scale first brings the two terms into the same range.

    Must be computed on the TRAINING arrays and reused unchanged for test rows,
    or train and test end up on different scales.
    """
    dphi = arrays["dphi"]
    changed = dphi.sum(axis=2) > 0
    if not changed.any():
        return 1.0
    return float(np.sqrt(np.mean((dphi[changed] ** 2).sum(axis=1))))


def subset(arrays: dict, rows: np.ndarray) -> dict:
    """Row-subset the arrays produced by :func:`prepare`."""
    out = dict(arrays)
    for key in ("idxI", "idxP", "dphi", "y", "tcr_i"):
        out[key] = arrays[key][rows]
    if arrays.get("mhc") is not None:
        out["mhc"] = arrays["mhc"][rows]
    return out


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------

_ORDERED = pm.distributions.transforms.ordered


def build_model(kind: str, arrays: dict, D: np.ndarray,
                use_mhc: bool = False, pan_tcr: bool = False,
                hybrid_shrinkage: float = 0.5,
                frozen_theta: np.ndarray | None = None,
                frozen_w: np.ndarray | None = None,
                feat_scale: float | None = None) -> pm.Model:
    """Build the hierarchical ordered-logistic model.

    Parameters
    ----------
    kind : {"fixed", "learned", "atomic"}
        How the substitution distance M is defined.
    pan_tcr : bool
        If True, learn a single positional weight profile shared by every TCR
        (required when predicting for TCRs unseen during training).
    """
    idxI, idxP, dphi = arrays["idxI"], arrays["idxP"], arrays["dphi"]
    y, tcr_i = arrays["y"], arrays["tcr_i"]
    n_tcr, L = arrays["n_tcr"], arrays["L"]

    with pm.Model() as model:
        if kind != "hybrid_frozen":
            alpha = pm.Gamma("alpha", 2, 2)
            beta = pm.Gamma("beta", 2, 2)
            if pan_tcr:
                w = pm.Beta("w", alpha, beta, shape=L)
                w_rows = w[None, :]
            else:
                w = pm.Beta("w", alpha, beta, shape=(n_tcr, L))
                w_rows = w[tcr_i]

        if kind == "fixed":
            m_rp = pt.as_tensor(D[idxI, idxP])
        elif kind == "learned":
            mu = pm.Normal("mu", 0, 0.5)
            sigma = pm.Exponential("sigma", 1.0)
            delta = pm.Normal("delta", mu, sigma, shape=(20, 20))
            m_rp = (pt.as_tensor(D) * (1 + delta))[idxI, idxP]
        elif kind == "atomic":
            theta = pm.HalfNormal("theta", 1.0, shape=dphi.shape[2])
            m_rp = pt.tensordot(pt.as_tensor(dphi), theta, axes=[[2], [0]])
        elif kind == "hybrid_frozen":
            # Fully frozen backbone: BOTH theta and the positional weights come
            # from the atomic fit, and only the residual is learned. This is the
            # version whose OOD behaviour really is guaranteed: when every test
            # row mutates to a residue absent from training, delta shrinks to 0
            # there, the distance reduces to the atomic model's distance, and
            # AUC (being rank-based) is identical to atomic by construction.
            #
            # `hybrid_staged` froze theta only, and still lost OOD accuracy --
            # because stage 2 re-learned w, which then no longer matched the
            # atomic backbone.
            if frozen_theta is None or frozen_w is None:
                raise ValueError("hybrid_frozen needs frozen_theta and frozen_w")
            base = pt.as_tensor(
                np.tensordot(dphi, np.asarray(frozen_theta), axes=[[2], [0]]))
            sigma = pm.HalfNormal("sigma", hybrid_shrinkage)
            delta = pm.Normal("delta", 0.0, sigma, shape=(20, 20))
            m_rp = base + delta[idxI, idxP]
            w_rows = pt.as_tensor(np.asarray(frozen_w)[arrays["tcr_i"]])
        elif kind == "hybrid_feature":
            # Feature-tied residual.
            #
            # `hybrid_frozen` gives the residual one free cell per ordered pair
            # of amino acids (400 of them). Leave-one-epitope-out showed that
            # this residual memorises the training epitopes: its penalty on an
            # unseen epitope is monotone in how much freedom it is given.
            #
            # This variant keeps the extra capacity but ties it to the same
            # physicochemical axes the backbone already uses, so it can only
            # express things about *amino acid properties* -- the part that
            # transfers -- and cannot address individual residue pairs:
            #
            #     M[a,b] = sum_k theta_k |dphi_k|            (frozen backbone)
            #            + sum_{k<=l} Lambda_kl |dphi_k||dphi_l|
            #
            # Lambda is a symmetric K x K interaction matrix, so the residual
            # costs K(K+1)/2 parameters (36 for K = 8) instead of 400.
            if frozen_theta is None or frozen_w is None:
                raise ValueError("hybrid_feature needs frozen_theta and frozen_w")
            K = dphi.shape[2]
            base = pt.as_tensor(
                np.tensordot(dphi, np.asarray(frozen_theta), axes=[[2], [0]]))
            n_pair = K * (K + 1) // 2
            sigma = pm.HalfNormal("sigma", hybrid_shrinkage)
            lam = pm.Normal("lam", 0.0, sigma, shape=n_pair)
            iu = np.triu_indices(K)
            Lam = pt.zeros((K, K))
            Lam = pt.set_subtensor(Lam[iu], lam)
            Lam = Lam + Lam.T - pt.diag(pt.diag(Lam))     # symmetrise
            fs = feature_scale(arrays) if feat_scale is None else feat_scale
            dphi_t = pt.as_tensor(dphi / fs)
            # sum_kl Lambda_kl dphi'_k dphi'_l, per (row, position)
            quad = (pt.tensordot(dphi_t, Lam, axes=[[2], [0]]) * dphi_t).sum(axis=2)
            m_rp = base + quad
            w_rows = pt.as_tensor(np.asarray(frozen_w)[arrays["tcr_i"]])
        elif kind == "hybrid_staged":
            # Two-stage hybrid: theta is FIXED at the atomic-only solution
            # (passed in via `frozen_theta`), so the residual cannot cannibalise
            # the atomic signal. On substitutions absent from training the
            # residual shrinks to 0 and the model reduces exactly to the atomic
            # model -- so out-of-distribution performance cannot fall below it.
            if frozen_theta is None:
                raise ValueError("hybrid_staged needs frozen_theta")
            base = pt.as_tensor(
                np.tensordot(dphi, np.asarray(frozen_theta), axes=[[2], [0]]))
            sigma = pm.HalfNormal("sigma", hybrid_shrinkage)
            delta = pm.Normal("delta", 0.0, sigma, shape=(20, 20))
            m_rp = base + delta[idxI, idxP]
        elif kind == "hybrid":
            # Atomic distance supplies a structured prior for M; a per-cell
            # residual then recovers the flexibility of the full matrix where
            # the training data can support it.
            # The atomic term supplies a structured backbone for M; a shrunk,
            # zero-centred per-cell residual then recovers matrix flexibility
            # wherever the training data can support it.
            #
            # The residual is ADDITIVE on purpose. A multiplicative residual --
            # base * (1 + delta), mirroring BATMAN's own Eq. 9 -- leaves theta
            # and delta multiplicatively non-identifiable, and ADVI diverges at
            # every learning rate we tried. The atomic base also runs ~4x larger
            # than the BLOSUM distance it replaces (row-sum 17.6 vs 4.2), which
            # makes that blow-up worse.
            theta = pm.HalfNormal("theta", 1.0, shape=dphi.shape[2])
            base = pt.tensordot(pt.as_tensor(dphi), theta, axes=[[2], [0]])
            sigma = pm.HalfNormal("sigma", hybrid_shrinkage)
            delta = pm.Normal("delta", 0.0, sigma, shape=(20, 20))
            m_rp = base + delta[idxI, idxP]
        else:
            raise ValueError(f"unknown kind: {kind!r}")

        dist = pt.sum(w_rows * m_rp, axis=1)

        if use_mhc:
            if arrays.get("mhc") is None:
                raise ValueError("use_mhc=True but arrays carry no 'mhc' column")
            alpha_m = pm.Gamma("alpha_m", 2, 2)
            beta_m = pm.Gamma("beta_m", 2, 2)
            d_mhc = pm.Beta("d_mhc", alpha_m, beta_m, shape=3)
            dist = dist + d_mhc[arrays["mhc"]]

        d0 = pm.Normal("d0", 0, 2)
        cut = pm.Normal("cut", 0, 2, shape=2, transform=_ORDERED,
                        initval=np.array([-1.0, 1.0]))
        pm.OrderedLogistic("obs", eta=d0 - dist, cutpoints=cut, observed=y)

    return model


def fit(model: pm.Model, method: str = "advi", n_iter: int = 12000,
        lr: float = 0.05, draws: int = 300, seed: int = 0,
        tune: int = 500, chains: int = 2, lr_ladder=(0.05, 0.01, 0.002)):
    """Fit with ADVI (fast, approximate) or NUTS (slow, exact-ish).

    ADVI can diverge to NaN when the summed distance is large (long peptides)
    or when features are collinear. Rather than lose the whole run, retry down
    a ladder of smaller learning rates; raise only if every attempt fails.

    Returns an ArviZ InferenceData whose ``posterior`` group holds the samples.
    """
    if method == "nuts":
        with model:
            return pm.sample(draws=draws, tune=tune, chains=chains,
                             random_seed=seed, progressbar=False,
                             compute_convergence_checks=True)
    if method != "advi":
        raise ValueError(f"unknown method: {method!r}")

    rates = tuple(dict.fromkeys((lr, *lr_ladder)))
    last = None
    for i, rate in enumerate(rates):
        try:
            with model:
                approx = pm.fit(n_iter, method="advi", progressbar=False,
                                obj_optimizer=pm.adam(learning_rate=rate),
                                random_seed=seed + i)
                return approx.sample(draws)
        except FloatingPointError as exc:      # NaN in the ELBO optimisation
            last = exc
            print(f"    [warn] ADVI diverged at lr={rate}; retrying lower")
    raise RuntimeError(
        f"ADVI failed to converge at every learning rate in {rates}") from last


def posterior_distance(kind: str, post, arrays: dict, D: np.ndarray,
                       use_mhc: bool = False, pan_tcr: bool = False,
                       frozen_theta: np.ndarray | None = None,
                       frozen_w: np.ndarray | None = None,
                       feat_scale: float | None = None) -> np.ndarray:
    """Peptide-to-index distance under the posterior-mean parameters.

    Larger distance means lower predicted activation.
    """
    pmean = post.posterior.mean(("chain", "draw"))
    # hybrid_frozen never infers w -- the caller supplies the frozen weights.
    w = (np.asarray(frozen_w)
         if kind in ("hybrid_frozen", "hybrid_feature")
         else pmean["w"].values)
    idxI, idxP = arrays["idxI"], arrays["idxP"]

    if kind == "fixed":
        m_rp = D[idxI, idxP]
    elif kind == "learned":
        delta = pmean["delta"].values
        m_rp = (D * (1 + delta))[idxI, idxP]
    elif kind == "atomic":
        theta = pmean["theta"].values
        m_rp = np.tensordot(arrays["dphi"], theta, axes=[[2], [0]])
    elif kind == "hybrid_feature":
        K = arrays["dphi"].shape[2]
        lam = pmean["lam"].values
        Lam = np.zeros((K, K))
        Lam[np.triu_indices(K)] = lam
        Lam = Lam + Lam.T - np.diag(np.diag(Lam))
        base = np.tensordot(arrays["dphi"], np.asarray(frozen_theta),
                            axes=[[2], [0]])
        fs = feature_scale(arrays) if feat_scale is None else feat_scale
        u = arrays["dphi"] / fs
        quad = np.einsum("nlk,kj,nlj->nl", u, Lam, u)
        m_rp = base + quad
    elif kind in ("hybrid_staged", "hybrid_frozen"):
        base = np.tensordot(arrays["dphi"], np.asarray(frozen_theta), axes=[[2], [0]])
        m_rp = base + pmean["delta"].values[idxI, idxP]
    elif kind == "hybrid":
        theta = pmean["theta"].values
        base = np.tensordot(arrays["dphi"], theta, axes=[[2], [0]])
        delta = pmean["delta"].values
        m_rp = base + delta[idxI, idxP]
    else:
        raise ValueError(f"unknown kind: {kind!r}")

    w_rows = w[None, :] if pan_tcr else w[arrays["tcr_i"]]
    dist = (w_rows * m_rp).sum(axis=1)

    if use_mhc:
        dist = dist + pmean["d_mhc"].values[arrays["mhc"]]
    return dist


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def mean_pairwise_auc(y: np.ndarray, dist: np.ndarray) -> float:
    """Mean one-vs-one AUC over the three activation-class pairs.

    Uses ``-dist`` as the score, since a larger distance predicts weaker
    activation. Pairs absent from ``y`` are skipped; returns NaN if none exist.
    """
    score = -dist
    aucs = []
    for lo, hi in ((0, 1), (0, 2), (1, 2)):
        mask = np.isin(y, (lo, hi))
        if mask.sum() > 3 and len(np.unique(y[mask])) == 2:
            aucs.append(roc_auc_score((y[mask] == hi).astype(int), score[mask]))
    return float(np.mean(aucs)) if aucs else float("nan")


def per_tcr_auc(arrays: dict, dist: np.ndarray,
                min_rows: int = 8) -> dict[str, float]:
    """Mean pairwise AUC computed separately for each TCR.

    Per-TCR values are the unit of analysis for the paired significance tests,
    giving one observation per TCR rather than one per experiment.
    """
    out = {}
    y, tcr_i, names = arrays["y"], arrays["tcr_i"], arrays["tcr_names"]
    for t in np.unique(tcr_i):
        mask = tcr_i == t
        if mask.sum() < min_rows:
            continue
        auc = mean_pairwise_auc(y[mask], dist[mask])
        if not np.isnan(auc):
            out[names[t]] = auc
    return out


def bootstrap_ci(values, n_boot: int = 10000, ci: float = 95,
                 seed: int = 0) -> tuple[float, float, float]:
    """Percentile bootstrap CI for the mean. Returns (mean, low, high)."""
    arr = np.asarray([v for v in values if not np.isnan(v)], dtype=float)
    if arr.size == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    boots = rng.choice(arr, size=(n_boot, arr.size), replace=True).mean(axis=1)
    lo, hi = np.percentile(boots, [(100 - ci) / 2, 100 - (100 - ci) / 2])
    return float(arr.mean()), float(lo), float(hi)


def paired_wilcoxon(a: dict[str, float], b: dict[str, float]) -> dict:
    """Wilcoxon signed-rank test on per-TCR AUCs shared by both models.

    Returns n, median paired difference (a - b), and the two-sided p-value.
    """
    from scipy.stats import wilcoxon

    keys = sorted(set(a) & set(b))
    x = np.array([a[k] for k in keys])
    y = np.array([b[k] for k in keys])
    diff = x - y
    if len(keys) < 6 or np.allclose(diff, 0):
        return {"n": len(keys), "median_diff": float(np.median(diff)) if keys else float("nan"),
                "p": float("nan")}
    stat, p = wilcoxon(x, y)
    return {"n": len(keys), "median_diff": float(np.median(diff)),
            "statistic": float(stat), "p": float(p)}
