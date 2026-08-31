"""
prose_numbers.py
================
Prints every number that appears in the *prose* of ``MANUSCRIPT.md`` (as
opposed to the auto-generated tables), so the narrative can be checked against
the data in one pass instead of by eye.

Usage:  python3 prose_numbers.py
"""

from __future__ import annotations

# --- bootstrap ---
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
# --- end bootstrap ---

import warnings
warnings.filterwarnings("ignore")

import manuscript_tables as mt


def main():
    label, ind, ood = mt.source_tables()
    print(f"SOURCE: {label}\n")

    print("--- section 3.1 / Table 1: mean per-TCR AUC ---")
    means_i, means_o = {}, {}
    for m in mt.ORDER:
        if m in set(ind.model):
            means_i[m] = mt.per_unit(ind, m, ["tcr"]).mean()
        if m in set(ood.model):
            means_o[m] = mt.per_unit(ood, m, ["tcr", "group"]).mean()
        print(f"  {m:15s} in-dist {means_i.get(m, float('nan')):.4f}   "
              f"OOD {means_o.get(m, float('nan')):.4f}")
    fitted = [v for k, v in means_i.items()]
    print(f"\n  -> prose range for fitted models (in-dist): "
          f"{min(fitted):.3f}-{max(fitted):.3f}")

    print("\n--- section 3.2: atomic vs fixed / Atchley ---")
    for a, b, df, keys, tag in [
            ("atomic", "fixed", ind, ["tcr"], "in-dist"),
            ("atomic", "atchley5", ind, ["tcr"], "in-dist"),
            ("atomic", "atchley5", ood, ["tcr", "group"], "OOD")]:
        if a in set(df.model) and b in set(df.model):
            r = mt.paired(df, a, b, keys)
            print(f"  {a} vs {b} [{tag}]: D={r['mean']:+.4f} d={r['d']:+.2f} "
                  f"win={r['win']*100:.1f}% p={r['p']:.2e}")

    print("\n--- section 3.3: learned vs atomic ---")
    for a, b, df, keys, tag in [
            ("learned", "atomic", ind, ["tcr"], "in-dist"),
            ("atomic", "learned", ood, ["tcr", "group"], "OOD")]:
        if a in set(df.model) and b in set(df.model):
            r = mt.paired(df, a, b, keys)
            print(f"  {a} vs {b} [{tag}]: D={r['mean']:+.4f} d={r['d']:+.2f} "
                  f"win={r['win']*100:.1f}% p={r['p']:.2e}")

    print("\n--- section 3.4: frozen hybrid ---")
    for a, b, df, keys, tag in [
            ("hybrid_frozen", "atomic", ind, ["tcr"], "in-dist"),
            ("hybrid_frozen", "atomic", ood, ["tcr", "group"], "OOD"),
            ("hybrid_frozen", "learned", ind, ["tcr"], "in-dist"),
            ("hybrid_frozen", "learned", ood, ["tcr", "group"], "OOD")]:
        if a in set(df.model) and b in set(df.model):
            r = mt.paired(df, a, b, keys)
            print(f"  {a} vs {b} [{tag}]: n={r['n']} D={r['mean']:+.4f} "
                  f"d={r['d']:+.2f} win={r['win']*100:.1f}% p={r['p']:.2e}")

    print("\n--- cross-check: ORIGINAL-protocol run (hybrid_frozen_s025.csv) ---")
    hy = mt.L("hybrid_frozen_s025.csv")
    oi = hy[hy.setting == "in_distribution"]
    oo = hy[hy.setting == "leave_chemistry_out"]
    r1 = mt.paired(oi, "hybrid_frozen", "atomic", ["tcr"])
    r2 = mt.paired(oo, "hybrid_frozen", "atomic", ["tcr", "group"])
    print(f"  hybrid vs atomic [in-dist]: n={r1['n']} D={r1['mean']:+.4f} "
          f"d={r1['d']:+.2f} win={r1['win']*100:.1f}% p={r1['p']:.2e}")
    print(f"  hybrid vs atomic [OOD]    : n={r2['n']} D={r2['mean']:+.4f} "
          f"d={r2['d']:+.2f} win={r2['win']*100:.1f}% p={r2['p']:.2f}")
    print(f"  atomic  in-dist {oi[oi.model=='atomic'].groupby('tcr').auc.mean().mean():.4f}"
          f"  hybrid in-dist {oi[oi.model=='hybrid_frozen'].groupby('tcr').auc.mean().mean():.4f}")


if __name__ == "__main__":
    main()
