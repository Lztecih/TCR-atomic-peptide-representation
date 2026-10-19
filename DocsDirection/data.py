"""BATCAVE loading, receptor panels, folds and labels.

Everything here is derived from data/ alone. No dependency on any previous
implementation.

Facts re-derived and asserted at load time:
  - peptide_activity in train_test_data_folds.xlsx is ALREADY normalised per
    receptor (max == 1.0 for each of the 151). The documented 0.1 / 0.5 cuts
    then reproduce the activation column exactly.
  - 153 rows have training_fold NaN: the 151 wild-type rows (peptide ==
    index_peptide) plus 2 singleton-cell mutants. They go into the TRAINING
    set of every fold and are never tested.
  - mutation_position is 1-indexed.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

AA = "ACDEFGHIKLMNPQRSTVWY"
AAI = {a: i for i, a in enumerate(AA)}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RESULTS = os.path.join(ROOT, "results")

_CACHE: dict[str, pd.DataFrame] = {}


def load_batcave() -> pd.DataFrame:
    """The 22,827-row table with the substitution annotated."""
    if "b" in _CACHE:
        return _CACHE["b"].copy()
    df = pd.read_excel(os.path.join(DATA, "raw", "train_test_data_folds.xlsx"))
    df["peptide"] = df.peptide.astype(str)
    df["index_peptide"] = df.index_peptide.astype(str)
    assert len(df) == 22827, len(df)

    lvl = np.ones(len(df), int)
    a = df.peptide_activity.to_numpy()
    lvl[a < 0.1] = 0
    lvl[a >= 0.5] = 2
    assert (lvl == df.activation.to_numpy()).all(), "0.1/0.5 cuts do not reproduce activation"

    pos, wt, mt = [], [], []
    for p, q in zip(df.index_peptide, df.peptide):
        if p == q:
            pos.append(-1); wt.append(""); mt.append("")
            continue
        d = [i for i, (x, y) in enumerate(zip(p, q)) if x != y]
        assert len(d) == 1 and len(p) == len(q), f"{p} -> {q}"
        pos.append(d[0]); wt.append(p[d[0]]); mt.append(q[d[0]])
    df["pos"], df["wt"], df["mt"] = pos, wt, mt
    df["is_wt"] = df.peptide == df.index_peptide
    df["L"] = df.index_peptide.str.len()
    assert int(df.is_wt.sum()) == 151
    assert ((df.mutation_position == df.pos + 1) | df.is_wt).all()
    _CACHE["b"] = df
    return df.copy()


def eligible_panel(df: pd.DataFrame | None = None, min_per_class: int = 5) -> list[str]:
    """Every receptor this benchmark can actually score.

    Our own rule, stated rather than inherited: a receptor is in if it has at
    least `min_per_class` mutant peptides in each of the three activation
    classes (otherwise a pairwise AUC is undefined or trivial) and all five
    cross-validation folds are present.
    """
    if df is None:
        df = load_batcave()
    d = df[~df.is_wt]
    keep = []
    for tcr, g in d.groupby("tcr"):
        counts = [int((g.activation == k).sum()) for k in (0, 1, 2)]
        if min(counts) >= min_per_class and g.training_fold.nunique() == 5:
            keep.append(tcr)
    return sorted(keep)


def one_per_index(df: pd.DataFrame | None = None, panel: list[str] | None = None) -> list[str]:
    """One receptor per index peptide, the most label-balanced of each group.

    With a fixed substitution matrix the predicted distance depends only on
    (index peptide, mutant peptide) -- the receptor does not enter it. Receptors
    sharing an index peptide are then scored by an identical vector and are not
    independent replicates, so a paired test over all of them is
    pseudo-replicated. This subset is the honest unit of analysis.
    Selection: highest entropy of the activation-class distribution, ties by name.
    """
    if df is None:
        df = load_batcave()
    if panel is None:
        panel = eligible_panel(df)
    d = df[(~df.is_wt) & df.tcr.isin(panel)]
    out = []
    for _, g in d.groupby("index_peptide"):
        ent = {}
        for tcr, gg in g.groupby("tcr"):
            f = gg.activation.value_counts(normalize=True).to_numpy()
            ent[tcr] = float(-(f * np.log(f)).sum())
        out.append(sorted(ent, key=lambda t: (-ent[t], t))[0])
    return sorted(out)


def length_groups(df: pd.DataFrame, panel: list[str]) -> dict[int, list[str]]:
    """Receptors grouped by index-peptide length.

    One fit handles one length: the positional weight is a dense (receptors x L)
    rectangle, so mixed lengths cannot be expressed in a single model.
    """
    sub = df[df.tcr.isin(panel)]
    g = sub.groupby("tcr").L.first()
    return {int(L): sorted(g[g == L].index) for L in sorted(g.unique())}


def folds(df: pd.DataFrame, tcrs: list[str], length: int):
    """(fold, train, test) using the shipped training_fold column.

    The NaN-fold rows (wild type + 2 singletons) join every training set and are
    never tested: they anchor each receptor's own index peptide at distance 0.
    """
    d = df[df.tcr.isin(tcrs) & (df.L == length)]
    anchor = d[d.training_fold.isna()]
    for f in sorted(d.training_fold.dropna().unique()):
        tr = pd.concat([d[(d.training_fold != f) & d.training_fold.notna()], anchor])
        te = d[d.training_fold == f]
        yield int(f), tr.reset_index(drop=True), te.reset_index(drop=True)


def leave_one_receptor_out(df: pd.DataFrame, tcrs: list[str], length: int,
                           relabel: bool = True):
    """Train on every receptor of this length but one; test on the held-out one.

    All training receptors are relabelled to a single name, so one pan-receptor
    positional-weight profile is inferred and the held-out receptor is genuinely
    unseen. This is the protocol that matters for the project's claim: it asks
    whether the representation transfers to a receptor with no training data.

    relabel=False when the weights are conditioned on a receptor covariate: with
    every training receptor renamed to "pan" there is only ONE training identity
    left, so the covariate matrix collapses to two rows and the "pan" row is one
    arbitrary training receptor's CDR3 standing in for all the others. Same
    reason as in leave_one_group_out.
    """
    d = df[df.tcr.isin(tcrs) & (df.L == length)]
    for held in sorted(d.tcr.unique()):
        tr = d[d.tcr != held].copy()
        if relabel:
            tr["tcr"] = "pan"
        te = d[(d.tcr == held) & ~d.is_wt]
        if len(tr) and len(te):
            yield held, tr.reset_index(drop=True), te.reset_index(drop=True)


def leave_one_group_out(df: pd.DataFrame, tcrs: list[str], length: int,
                        relabel: bool = True):
    """Hold out EVERY receptor that shares an index peptide; train on the rest.

    This is the correct generalisation test once the panel contains more than one
    receptor per index peptide. Holding out a single receptor would leave its
    siblings -- receptors raised against the SAME index peptide, and therefore
    scored on the very same mutant peptides -- in the training set, so the model
    would already have seen that index peptide and its whole mutational scan.
    That is leakage, and it is why the one-receptor-per-index panel was used
    until now.

    Grouping by index peptide instead lets us train on every other receptor
    (about 55 of the 60 nine-mer receptors) while keeping the test genuinely
    unseen. The number of independent test units does not change -- it is the
    number of index peptides, 15 for the 9-mers -- but the training set is four
    times larger.

    Yields (index_peptide, train, test). Training receptors are relabelled to a
    single name so one pan-receptor weight profile is inferred.
    """
    d = df[df.tcr.isin(tcrs) & (df.L == length)]
    for idx in sorted(d.index_peptide.unique()):
        tr = d[d.index_peptide != idx].copy()
        if relabel:
            tr["tcr"] = "pan"      # one pan-receptor profile
        # relabel=False keeps each training receptor distinct, which is required
        # when the weights are conditioned on that receptor's CDR3 sequence.
        te = d[(d.index_peptide == idx) & ~d.is_wt]
        if len(tr) and len(te) and te.tcr.nunique() >= 1:
            yield idx, tr.reset_index(drop=True), te.reset_index(drop=True)
