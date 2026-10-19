"""The evaluation metric and the paired tests around it.

Three-class ordinal activation (0 none / 1 weak / 2 strong), so plain accuracy
is the wrong summary. We use the mean of the three one-vs-one ROC AUCs: drop one
class, score the remaining two with the larger as positive. The predictor is
MINUS the predicted distance, because a large distance means low activation.
nanmean over the pairs, so a receptor missing a class contributes only its
defined pairs. Aggregation order: pairs -> folds -> receptors (unweighted over
receptors, since the question is "given one receptor, can we rank its peptides").
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def auc(score, positive) -> float:
    s = np.asarray(score, float)
    p = np.asarray(positive, bool)
    ok = np.isfinite(s)
    s, p = s[ok], p[ok]
    n1, n0 = int(p.sum()), int((~p).sum())
    if n1 < 1 or n0 < 1:
        return float("nan")
    r = stats.rankdata(s)
    return float((r[p].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def three_pairwise(y, distance):
    """(mean of the 3 one-vs-one AUCs, [WS, NS, NW]); predictor is -distance."""
    y = np.asarray(y)
    s = -np.asarray(distance, float)
    out = []
    for drop in (0, 1, 2):
        m = y != drop
        out.append(auc(s[m], y[m] == max({0, 1, 2} - {drop})))
    mean = float(np.nanmean(out)) if not all(np.isnan(v) for v in out) else float("nan")
    return mean, out


def per_receptor(rows: pd.DataFrame) -> pd.Series:
    """rows: one per (tcr, split) with an `auc` column -> mean per receptor."""
    return rows.groupby("tcr").auc.mean()


def paired(new: pd.Series, base: pd.Series, n_boot: int = 20000, seed: int = 0) -> dict:
    """Paired comparison over the receptors both arms scored."""
    common = sorted(set(new.index) & set(base.index))
    d = (new[common] - base[common]).to_numpy()
    if len(d) < 2:
        return dict(n=len(d), delta=float("nan"))
    rng = np.random.default_rng(seed)
    boot = rng.choice(d, size=(n_boot, len(d)), replace=True).mean(axis=1)
    return dict(n=len(d), new=float(new[common].mean()), base=float(base[common].mean()),
                delta=float(d.mean()),
                ci_low=float(np.percentile(boot, 2.5)),
                ci_high=float(np.percentile(boot, 97.5)),
                p=float(stats.wilcoxon(d).pvalue) if np.any(d != 0) else 1.0,
                wins=int((d > 0).sum()))
