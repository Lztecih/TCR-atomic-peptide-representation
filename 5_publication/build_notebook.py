"""
build_notebook.py
=================
Emits ``REPRODUCE.ipynb`` -- the notebook a reader (or reviewer) runs to go
from a clean checkout to every number and figure in the manuscript.

The notebook is generated rather than hand-edited so that it cannot drift out
of sync with the library, and so that re-running it is a one-line operation.

Usage:
    python3 build_notebook.py                 # write the .ipynb
    jupyter nbconvert --to notebook --execute --inplace REPRODUCE.ipynb
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "REPRODUCE.ipynb")

cells: list[dict] = []


def md(text: str):
    cells.append({"cell_type": "markdown", "metadata": {},
                  "source": text.strip("\n").splitlines(keepends=True)})


def code(text: str):
    cells.append({"cell_type": "code", "execution_count": None,
                  "metadata": {}, "outputs": [],
                  "source": text.strip("\n").splitlines(keepends=True)})


# ===========================================================================
md(r"""
# Atomic peptide representation for TCR cross-reactivity

**Replacing the 20×20 amino-acid similarity matrix with an atomic
representation in a Bayesian TCR cross-reactivity model — and what actually
survives scrutiny.**

This notebook reproduces every headline number and figure in
[`MANUSCRIPT.md`](MANUSCRIPT.md), starting from the raw data.

---

### The question

[BATMAN](https://doi.org/10.1016/j.cels.2025.101345) (Banerjee *et al.*,
*Cell Systems*, 2025) predicts how strongly a TCR responds to a mutated
peptide from the peptide's weighted distance to the index peptide:

$$d(\text{peptide},\text{index}) \;=\; \sum_{j=1}^{L} w_j \, M\big[a_{\text{idx},j},\, a_{\text{pep},j}\big]$$

fed into a 3-level ordered-logistic likelihood (non / weak / strong).

Everything hinges on $M$ — a **20×20 substitution distance matrix** learned
from data. It has four structural weaknesses:

| # | Weakness | Consequence |
|---|---|---|
| 1 | ~380 free parameters | data-hungry, overfit-prone |
| 2 | cannot extrapolate | an unseen substitution falls back to its prior |
| 3 | canonical 20 residues only | phospho-Ser, citrulline, … cannot be scored **at all** |
| 4 | 400 opaque numbers | tells you *which*, never *why* |

**We ask:** if $M$ is a function of the *atomic properties* of the two
residues, is accuracy preserved and are those weaknesses removed?

$$\boxed{\;M[a,b] \;=\; \sum_{k=1}^{K}\theta_k\,\big|\phi_k(a)-\phi_k(b)\big|,\qquad \theta_k \ge 0\;}$$

With $\theta \ge 0$ this gives $M[a,a]=0$, $M \ge 0$, symmetry and the
triangle inequality **for free** — a matrix has to be forced into all four.

### What you should expect to find

This notebook does **not** end with "our method wins". The honest summary is
in the last section: one solid positive result, one refuted hypothesis, and
three negative results.
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 0 · Setup

Dependencies:

```bash
pip install pymc arviz rdkit scikit-learn biopython pandas numpy matplotlib openpyxl scipy jupyter
```

Tested on macOS (Apple Silicon), Python 3.14, pymc 6.3.1, rdkit 2026.03.5.
""")

code(r"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")

# the shared library lives one directory up
ROOT = os.path.dirname(os.getcwd()) if os.path.basename(os.getcwd()) == "5_publication" else os.getcwd()
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
from IPython.display import Image, display

import batman_atomic as ba
import experiments as ex

RES = os.path.join(ba.ROOT, "results")
FIG = os.path.join(ba.ROOT, "figures")
print("project root:", ba.ROOT)
print("python", sys.version.split()[0], "| numpy", np.__version__, "| pandas", pd.__version__)
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 1 · Verify the setup before trusting anything

`verify_setup.py` checks four independent things — environment, data
integrity (SHA-256 against the upstream release), correctness of the
reimplementation, and whether the cached results still recompute.

Run it first. If it fails, nothing below is meaningful.
""")

code(r"""
import subprocess
_v = subprocess.run([sys.executable, "verify_setup.py"],
                    cwd=os.path.join(ba.ROOT, "5_publication"),
                    capture_output=True, text=True)
print(_v.stdout[-3000:])
print("exit code:", _v.returncode, "(0 = every check passed)")
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 2 · The data

**BATCAVE** — the mutational-scan database assembled by the BATMAN authors.
Every row is one measured peptide: an index peptide, a single-amino-acid
mutant of it, and the observed activation level.

It downloads automatically on first use and caches into `data/`.
""")

code(r"""
df = ba.load_batcave()
print(f"{len(df):,} rows | {df.tcr.nunique()} TCRs | "
      f"{df.index_peptide.nunique()} index peptides | "
      f"{df.pmid.nunique()} publications | {df.mhc.nunique()} MHC alleles")

print("\nactivation levels (0=non, 1=weak, 2=strong):")
print(df.activation.value_counts().sort_index().to_string())

print("\nTCRs per index-peptide length (a separate model is fitted per length,")
print("because the positional weights w are length-specific):")
print(df.groupby(df.index_peptide.str.len()).tcr.nunique().to_string())

df[["tcr", "index_peptide", "peptide", "mutation_position", "activation", "mhc"]].head()
""")

md(r"""
A second, harder dataset holds peptides carrying **2–9 simultaneous**
substitutions. It is never trained on — it tests whether the additive-across-
positions assumption survives.
""")

code(r"""
mh = ba.load_multi_hamming()
print(f"{len(mh):,} multi-substitution peptides | {mh.tcr.nunique()} TCRs")
print(mh.hamming.value_counts().sort_index().to_string())
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 3 · Building the atomic representation

Each residue goes SMILES → RDKit → descriptors. The glycine (pure backbone)
value is subtracted from the additive descriptors, so what remains describes
the **side chain** — the part a point mutation actually changes.

| descriptor | meaning | extreme |
|---|---|---|
| `heavy` | heavy-atom count → steric bulk | G=0, W=10 |
| `polar` | N+O atoms → polarity | L=0, R=3 |
| `S` | sulfur atoms | only C, M |
| `aromatic` | aromatic atoms → π-stacking | W=9, F=6 |
| `HBD`/`HBA` | H-bond donors / acceptors | R: HBD=3 |
| `rotB` | rotatable bonds → flexibility | G=0, R=4 |
| `charge` | net side-chain charge at pH 7 | D,E=−1; K,R=+1 |
""")

code(r"""
phi = ba.build_atomic_features("base8")
print("descriptor matrix (z-scored):", phi.shape)
phi.round(2)
""")

md(r"""
Now reconstruct $M$ from the learned weights $\theta$ and check the four
properties that come free from the functional form — plus the more
interesting question: **is this just BLOSUM in disguise?**
""")

code(r"""
theta = np.load(os.path.join(RES, "theta_9mer.npy"))
P = phi.to_numpy()
M = np.einsum("k,abk->ab", theta, np.abs(P[:, None, :] - P[None, :, :]))
D = ba.load_blosum100_distance()

print("M[a,a] == 0        :", np.allclose(np.diag(M), 0))
print("M >= 0             :", bool((M >= -1e-12).all()))
print("M symmetric        :", np.allclose(M, M.T))
tri = np.triu_indices(20, 1)
tri_ok = all(M[i, j] <= M[i, k] + M[k, j] + 1e-9
             for i in range(20) for j in range(20) for k in range(20))
print("triangle inequality:", tri_ok)

r = np.corrcoef(M[tri], D[tri])[0, 1]
print(f"\nPearson r(M_atomic, BLOSUM100) = {r:.2f}")
print("-> only moderate: the model is NOT re-deriving BLOSUM,")
print("   it orders substitutions along its own physicochemical axes.")

print("\nlearned feature weights, largest first:")
for k in np.argsort(theta)[::-1]:
    print(f"  {phi.columns[k]:9s} {theta[k]:.3f}")
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 4 · The four models

All four share an **identical** backbone — same priors, same likelihood, same
positional weights. Only the definition of $M$ changes, so any difference is
attributable to the representation and nothing else.

| model | $M[a,b]$ | free params in $M$ |
|---|---|---|
| `fixed` | $D[a,b]$ (BLOSUM100) | **0** |
| `learned` (BATMAN) | $D[a,b](1+\delta_{ab})$ | **~380** |
| `atomic` (this work) | $\sum_k \theta_k\lvert\phi_k(a)-\phi_k(b)\rvert$ | **8** |
| `hybrid_frozen` (this work) | atomic backbone **frozen** $+\;\delta_{ab}$ | 8 frozen + 400 shrunk |

Priors: $\alpha,\beta\sim\text{Gamma}(2,2)$, $w\sim\text{Beta}(\alpha,\beta)$,
$\theta_k\sim\text{HalfNormal}(1)$, $d_0\sim\mathcal N(0,2)$,
$c_1<c_2\sim\mathcal N(0,2)$, and
$a_i\sim\text{OrderedLogistic}(d_0-d_i,\mathbf c)$.
""")

md(r"""
### 4.1 A live fit

Everything below this point uses cached full-scale results (they take hours).
This cell fits a real model now, on the 8-mer group, so the pipeline is
demonstrably working rather than merely replayed.

> ⚠️ **This is a speed-reduced demo fit** (4,000 ADVI iterations on one fold of
> one length group). Its AUC will land *below* the numbers reported in the
> paper, which use 12,000 iterations across all six length groups and all five
> folds. Treat it as a smoke test that the pipeline runs, not as a result.
""")

code(r"""
L8, sub8, arr8 = next(ex.length_groups(df, phi.to_numpy()))
pos = sub8.mutation_position.to_numpy(dtype=int)
fold = sub8.training_fold.to_numpy()
tr = np.where((fold != 0) & (pos > 0))[0]
te = np.where((fold == 0) & (pos > 0))[0]
print(f"L={L8}: {arr8['n_tcr']} TCRs | train {len(tr):,} rows | test {len(te):,} rows")

post = ba.fit(ba.build_model("atomic", ba.subset(arr8, tr), D), n_iter=4000, seed=0)
th = post.posterior["theta"].mean(("chain", "draw")).values
test = ba.subset(arr8, te)
auc = ba.per_tcr_auc(test, ba.posterior_distance("atomic", post, test, D))

print("\nfitted theta:", dict(zip(phi.columns, th.round(2))))
print(f"mean per-TCR AUC on held-out fold: {np.mean(list(auc.values())):.4f}")
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 5 · How results are measured (and one trap)

The unit of analysis is **one TCR**, scored by mean pairwise one-vs-one AUC
across the three activation levels. That gives one number per TCR, which makes
**paired** statistics valid.

**The trap:** a *pooled* AUC across TCRs is actively misleading here. Pooling
EWW-TCR (89% non-activating) with TCR-1E6 (87% activating) without a
TCR-specific intercept inverts the ranking and yields pooled AUCs of
0.31–0.39 — *worse than chance* — as a pure artefact. Only per-TCR AUCs are
reported anywhere in this work.

Statistics: paired Wilcoxon signed-rank, percentile bootstrap 95% CIs
(10,000 resamples), effect sizes (Cohen's *d*, win rate) alongside every
*p*-value, and **multiplicity corrected once over the whole family of tests**.
""")

code(r"""
def per_unit(d, model, keys):
    return d[d.model == model].groupby(keys).auc.mean()

def paired(d, m1, m2, keys):
    a, b = per_unit(d, m1, keys), per_unit(d, m2, keys)
    j = pd.concat([a, b], axis=1, join="inner", keys=["a", "b"]).dropna()
    diff = j.a - j.b
    return dict(n=len(j), delta=float(diff.mean()), win=float((diff > 0).mean()),
                d=float(diff.mean() / diff.std(ddof=1)),
                p=float(stats.wilcoxon(j.a, j.b).pvalue))

def boot_ci(v, n=10000, seed=0):
    rng = np.random.default_rng(seed)
    v = np.asarray(v, float)
    return np.percentile(rng.choice(v, size=(n, len(v)), replace=True).mean(1), [2.5, 97.5])
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 6 · How much does the substitution model actually matter?

Before comparing representations: how much of the accuracy comes from $M$ at
all? Learning-free scoring rules inside the same framework give the answer.
""")

code(r"""
base = pd.DataFrame([
    ("Hamming distance, uniform weights",   "no",  0.5095),
    ("BLOSUM100, uniform weights",          "no",  0.5591),
    ("Mutated position only",               "no",  0.5765),
    ("Any fitted model (see below)",        "yes", np.nan),
], columns=["scoring rule", "learns?", "mean per-TCR AUC"])
print(base.to_string(index=False))
print("\n-> positional weights + the ordered-logistic likelihood do most of the work.")
print("   Both are inherited from BATMAN. Everything here operates in the margin above ~0.58.")
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 7 · The headline result — the frozen-backbone hybrid

The atomic model is constrained and extrapolates; the learned matrix has
capacity. Can we get both?

**Three attempts failed first**, and each failure identified the next
constraint:

| attempt | outcome | diagnosis |
|---|---|---|
| multiplicative `base × (1+δ)` | ADVI diverged at every learning rate | θ and δ multiplicatively non-identifiable |
| additive, θ and δ fitted **jointly** | OOD fell *below* atomic-only | the residual cannibalises θ's signal |
| additive, θ frozen but `w` re-learned | OOD still fell | weights no longer match the frozen backbone |
| **additive, θ *and* `w` frozen** | ✅ **works** | on an unseen substitution δ→0, distance reduces *exactly* to atomic, and AUC (rank-based) cannot drop below it |

That last row is the mechanism — the guarantee is structural, not empirical.
""")

code(r"""
hy = pd.read_csv(os.path.join(RES, "hybrid_frozen_s025.csv"))
ind = hy[hy.setting == "in_distribution"]
ood = hy[hy.setting == "leave_chemistry_out"]

r_in  = paired(ind, "hybrid_frozen", "atomic", ["tcr"])
r_ood = paired(ood, "hybrid_frozen", "atomic", ["tcr", "group"])

print("frozen hybrid vs atomic")
print(f"  in-distribution : n={r_in['n']:3d}  DAUC={r_in['delta']:+.4f}  "
      f"win={r_in['win']*100:.1f}%  d={r_in['d']:+.2f}  p={r_in['p']:.1e}")
print(f"  out-of-dist     : n={r_ood['n']:3d}  DAUC={r_ood['delta']:+.4f}  "
      f"win={r_ood['win']*100:.1f}%  d={r_ood['d']:+.2f}  p={r_ood['p']:.2f}")
print("\n-> large in-distribution gain, no measurable OOD cost: a Pareto improvement.")
""")

md(r"""
### 7.1 Freezing is *necessary*, not a lucky hyperparameter

The obvious objection: maybe a well-chosen shrinkage $\sigma$ would do the
same without freezing. Sweeping $\sigma$ for the **jointly** fitted hybrid
settles it.
""")

code(r"""
sw = pd.read_csv(os.path.join(RES, "review_hybrid_shrinkage.csv"))
si = sw[sw.setting == "in_distribution"].groupby("shrinkage").auc.mean()
so = sw[sw.setting == "leave_chemistry_out"].groupby("shrinkage").auc.mean()
at_ood = ood[ood.model == "atomic"].groupby(["tcr", "group"]).auc.mean().mean()
fz_ood = ood[ood.model == "hybrid_frozen"].groupby(["tcr", "group"]).auc.mean().mean()

t = pd.DataFrame({"in-distribution": si.round(4), "OOD": so.round(4),
                  "OOD vs atomic-only": (so - at_ood).round(4)})
print("JOINT hybrid (theta and residual fitted together):")
print(t.to_string())
print(f"\nFROZEN hybrid (sigma=0.25):  OOD vs atomic-only = {fz_ood - at_ood:+.4f}")
print(f"\nSpearman rho(sigma, in-dist) = {stats.spearmanr(si.index, si.values).statistic:+.2f}")
print(f"Spearman rho(sigma, OOD)     = {stats.spearmanr(so.index, so.values).statistic:+.2f}")
print("\n-> the joint variant loses OOD accuracy at EVERY sigma. Freezing loses ~nothing.")
print("   The mechanism buys the free lunch, not the hyperparameter.")
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 8 · The full benchmark

Two settings:

- **in-distribution** — 5-fold CV over all TCRs
- **out-of-distribution** — *leave-chemistry-out*: every substitution **to** a
  chemical class (aliphatic / aromatic / charged / small) is removed from
  training and used as the test set. This is exactly where a matrix must fall
  back on its prior while a feature-based distance can still interpolate.

`Atchley-5` is included as **prior art**, not as a straw man: pTEAM already
uses that encoding, so any novelty claim has to beat it on identical splits.
""")

code(r"""
import subprocess
out = subprocess.run([sys.executable, "manuscript_tables.py"],
                     cwd=os.path.join(ba.ROOT, "5_publication"),
                     capture_output=True, text=True)
tables = out.stdout
# show Tables 1 and 2
start = tables.index("## Table 1")
end = tables.index("## Table 3")
from IPython.display import Markdown
display(Markdown(tables[start:end]))
""")

md(r"""
Read that table carefully, because it does **not** say what we hoped.

* ✅ `atomic` beats `fixed` BLOSUM100, with 8 parameters instead of 0-but-frozen.
* ✅ `atomic` beats `Atchley-5` — structure-derived descriptors add something
  over published factors — but the effect is small (*d* ≈ 0.16–0.19).
* ❌ `atomic` does **not** replace `learned`. The matrix stays ahead
  in-distribution with a large effect (*d* = 0.84, winning 86% of TCRs).
* ✅ `hybrid_frozen` closes most of that gap without an OOD cost.
* ❌ but `hybrid_frozen` still does not beat `learned` in-distribution.
""")

md(r"""
### 8.1 Can more analysis rescue the refuted claim? No.

The atomic model's OOD advantage over the learned matrix is *real and
reproducible* — five ADVI seeds, mean Δ between +0.0079 and +0.0102, never
reversing sign — but small. A power analysis on the observed effect size shows
whether it could ever be confirmed with the data that exists.
""")

code(r"""
d_obs = 0.18                     # observed Cohen's d, atomic vs learned (OOD)
from scipy.stats import norm
def n_needed(d, alpha, power=0.8):
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return int(np.ceil((z / d) ** 2))

print(f"observed effect size d = {d_obs}")
print(f"  TCRs needed at alpha=0.05          : {n_needed(d_obs, 0.05)}")
print(f"  TCRs needed after multiplicity     : {n_needed(d_obs, 0.05/12)}")
print(f"  TCRs that exist in the entire field: {df.tcr.nunique()}")
print("\n-> no reanalysis closes this gap. New mutational scans are required.")
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 9 · Is the variational approximation trustworthy?

ADVI is fast but can be well-centred and still too narrow. Validated against
NUTS (4 chains × 1,500 draws).
""")

code(r"""
e6 = pd.read_csv(os.path.join(RES, "exp6_nuts_vs_advi.csv"))
a = e6[e6.method == "advi"].sort_values("feature_idx")
n = e6[e6.method == "nuts"].sort_values("feature_idx")

print(f"NUTS converged : max r-hat {n.rhat.max():.4f} (<1.01)  "
      f"min ESS {n.ess.min():.0f} (>400)")
print(f"posterior means: r = {np.corrcoef(a.theta_mean, n.theta_mean)[0,1]:.3f}")
print(f"test AUC       : ADVI {a.auc.iloc[0]:.4f} vs NUTS {n.auc.iloc[0]:.4f}")
ratio = a.theta_sd.to_numpy() / n.theta_sd.to_numpy()
print(f"posterior SD   : ADVI / NUTS median ratio = {np.median(ratio):.2f}")
print(f"\n-> point estimates are reliable; ADVI intervals are ~{(1-np.median(ratio))*100:.0f}% too narrow.")
print("   Credible intervals from ADVI are therefore NOT reported as calibrated.")
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 10 · Negative results

Three findings that constrain what the next study should attempt. Each would
have been easy to leave out.
""")

md(r"""
### 10.1 An explicit pMHC-binding term does not help
""")

code(r"""
e7 = pd.read_csv(os.path.join(RES, "exp7_pmhc_term.csv"))
a = e7[e7.pmhc == "with pMHC"].groupby("tcr").auc.mean()
b = e7[e7.pmhc == "no pMHC"].groupby("tcr").auc.mean()
j = pd.concat([a, b], axis=1, join="inner", keys=["with", "without"]).dropna()
print(f"with pMHC {j['with'].mean():.4f} | without {j['without'].mean():.4f} | "
      f"p = {stats.wilcoxon(j['with'], j['without']).pvalue:.3f}")
print("-> MHC binding information is already absorbed by the index-relative formulation.")
""")

md(r"""
### 10.2 At proteome scale, the substitution model is irrelevant

Applied to TScan-II genome/virome-wide screens (~365,000 peptides never used
by BATCAVE), the framework retrieves validated targets convincingly — 5 of the
top 5 out of 259,312 candidates, hypergeometric *p* = 6×10⁻²⁵.

Then we ran the simplest possible null: **plain Hamming distance, uniform
weights, no learning at all.**
""")

code(r"""
nb = pd.read_csv(os.path.join(RES, "proteome_null_baselines.csv"))
nb = nb[nb.threshold_name == "text"]
piv = nb.pivot(index="screen", columns="model", values="median_hit_rank")
cols = ["hamming", "blosum_uniform", "fixed", "learned", "atomic", "hybrid_frozen"]
print("median rank of a validated hit (lower = better):")
print(piv[cols].to_string())
print("\n-> Hamming ties or beats every fitted model. At this scale the task is")
print("   driven by raw sequence similarity and cannot discriminate between")
print("   substitution models. Without this null the same numbers would have")
print("   supported a far stronger, and entirely unjustified, claim.")
""")

md(r"""
The informative failure is elsewhere: decoys ranked 6–15 share long motifs
with the index peptide (`LL.EFT.SG`) yet cause no activation, and **no model
separates them**. Testing an MHC-II surrogate shows why — and shows it
conditionally.
""")

code(r"""
mf = json.load(open(os.path.join(RES, "mhc_filter_summary.json")))
for k, v in mf.items():
    print(f"{k:15s} {v['allele']:10s} TCR-dist AUC {v['auc_tcr_alone']:.3f} | "
          f"MHC-surrogate AUC {v['auc_mhc_alone']:.3f} | "
          f"precision@10 {v['precision@10_tcr']:.2f} -> {v['precision@10_fused']:.2f}")
print("\n-> On HIV/DRB1*11:01 the MHC score ALONE beats the TCR distance and fusion helps.")
print("   On CTAG1B/DRB1*04:01 the surrogate is near-random and fusion hurts --")
print("   NetMHCIIpan rates even the true NY-ESO-1 antigen a non-binder.")
print("   MHC-II presentation carries real signal, but exploiting it is limited")
print("   by MHC-II predictor quality, not by the substitution model.")
""")

md(r"""
### 10.3 A pre-registered chemical check of the extrapolation claim fails

A 20×20 matrix has no row for phospho-serine. The atomic model needs only the
molecule, so modified residues can be scored with **no retraining**.

These are **capability demonstrations, not accuracy validations** — no
mutational-scan dataset contains modified residues.

To avoid presenting an untestable claim as a result, we pre-registered a
falsification test: deimination of Arg gives citrulline, conventionally
described as glutamine-like, so citrulline's nearest canonical residue
*should* be **Q**.
""")

code(r"""
nc = pd.read_csv(os.path.join(RES, "noncanonical_distances.csv"))
display(nc[["residue", "parent", "d_to_parent", "parent_percentile",
            "nearest", "second"]])

cit = nc[nc.residue.str.startswith("Cit")].iloc[0]
print(f"\npre-registered check: nearest to citrulline = {cit.nearest} "
      f"(predicted Q)  ->  {'PASS' if cit.nearest == 'Q' else 'FAIL'}")

dec = pd.read_csv(os.path.join(RES, "noncanonical_citrulline_decomp.csv"), index_col=0)
print("\nwhy (per-feature contribution):")
print(dec.to_string())
print("\n-> citrulline is ISOSTERIC with arginine: identical heavy-atom, polar-atom")
print("   and rotatable-bond counts. The whole R->Cit distance is the charge term,")
print("   so R is genuinely nearest in this space; Q is nearest among NON-parents.")
print("   The check is recorded as FAILED as stated, not restated after the fact.")
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 11 · Figures
""")

code(r"""
for name in sorted(os.listdir(FIG)):
    if name.endswith(".png"):
        print("=" * 78); print(name); print("=" * 78)
        display(Image(filename=os.path.join(FIG, name)))
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 12 · Honest summary

### ✅ What the evidence supports

1. **The frozen-backbone hybrid improves on the atomic model substantially and
   safely** — *d* = 0.97, 89% of TCRs, *p* ≈ 8×10⁻²³, with **no** OOD cost
   (*p* = 0.95). Survives correction across the whole test family.
2. **Freezing is the necessary mechanism** — the joint variant loses OOD
   accuracy at *every* shrinkage level (Spearman ρ = −0.80).
3. **Atomic beats fixed BLOSUM100 and beats Atchley-5** (prior art), though
   incrementally.
4. **ADVI point estimates are sound** (r = 0.997 with NUTS); its intervals are
   not.

### ❌ What it does not support

1. **"Atomic replaces the learned matrix"** — refuted. The matrix wins
   in-distribution (*d* = 0.84) and on unseen TCRs.
2. **"Atomic generalises better"** — the effect is real and reproducible but
   too small (*d* ≈ 0.18) to survive multiplicity at *n* = 151; ~425 TCRs
   would be needed.
3. **"The hybrid beats BATMAN"** — it does not; it closes most of the gap.
4. **"It extends to PTMs"** — the capability is demonstrated, the accuracy is
   not, and the one pre-registered chemical check failed as stated.

### 🔬 Negative results worth carrying forward

* A pMHC-binding term adds nothing (*p* = 0.91).
* At proteome scale, Hamming distance matches every fitted model — the
  bottleneck for TCR target discovery is **MHC presentation**, not substitution
  modelling.
* Jointly fitted hybrids are strictly worse than frozen ones.

### Where effort should go next

Given a fixed budget, these results argue for **new mutational scans** (the
field needs ~425 TCRs and has 151) and for **better MHC-II presentation
prediction** — not for further refinement of substitution distances, which is
the part already shown to have saturated.

---

### References

1. Banerjee A. *et al.* *T cell receptor cross-reactivity prediction improved
   by a comprehensive mutational scan database.* **Cell Systems** 16, 101345 (2025).
2. Dorigatti E. *et al.* *Predicting T cell receptor functionality against
   mutant epitopes.* **Cell Genomics** 4, 100634 (2024).
3. Atchley W.R. *et al.* *Solving the protein sequence metric problem.*
   **PNAS** 102, 6395–6400 (2005).
4. Kucukelbir A. *et al.* *Automatic differentiation variational inference.*
   **JMLR** 18(14), 1–45 (2017).
""")


nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python",
                       "name": "python3"},
        "language_info": {"name": "python", "version": "3.14.2"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open(OUT, "w") as fh:
    json.dump(nb, fh, indent=1)
print(f"wrote {OUT}  ({len(cells)} cells: "
      f"{sum(1 for c in cells if c['cell_type']=='markdown')} md, "
      f"{sum(1 for c in cells if c['cell_type']=='code')} code)")
