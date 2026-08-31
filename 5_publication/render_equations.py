"""
render_equations.py
===================
Renders the model's equations as transparent PNGs via matplotlib's mathtext,
so the deck can show real typeset mathematics instead of ASCII approximations
like "Sigma_j w_j".

pptxgenjs cannot emit OMML (PowerPoint's native equation format), and plain
text loses subscripts, the summation sign and proper spacing -- which is
exactly the part of the model people need to read.

One PNG per line, so the deck can position each one exactly. Each file's
aspect ratio is printed and also written to ``figures/eq_ratios.json`` for
``build_deck.js`` to size the images without guessing.

Output: ``figures/eq_*.png``  (transparent, 400 dpi)

Usage:  python3 5_publication/render_equations.py
"""

from __future__ import annotations

# --- bootstrap ---
import sys as _sys, os as _os
for _p in (_os.getcwd(), _os.path.dirname(_os.path.abspath(__file__))):
    _r = _os.path.dirname(_p)
    if _os.path.exists(_os.path.join(_r, "batman_atomic.py")) and _r not in _sys.path:
        _sys.path.insert(0, _r)
# --- end bootstrap ---

import json
import warnings
warnings.filterwarnings("ignore")

import matplotlib as mpl
import matplotlib.pyplot as plt
from PIL import Image

import batman_atomic as ba

FIG = _os.path.join(ba.ROOT, "figures")
_os.makedirs(FIG, exist_ok=True)

NAVY = "#1F4E79"
BODY = "#2D2D2D"
ATOMIC = "#0072B2"
GREEN = "#009E73"

mpl.rcParams.update({
    "mathtext.fontset": "cm",        # Computer Modern -- the LaTeX look
})

RATIOS: dict[str, float] = {}


def render(name, latex, fontsize=26, color=NAVY):
    """Render a single math line to a tight, transparent PNG."""
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, latex, fontsize=fontsize, color=color, ha="left", va="bottom")
    out = _os.path.join(FIG, f"{name}.png")
    fig.savefig(out, dpi=400, transparent=True,
                bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    w, h = Image.open(out).size
    RATIOS[name] = round(w / h, 4)
    print(f"  {name:22s} {w:5d}x{h:4d}  ratio={w/h:7.3f}")


EQUATIONS = [
    # --- the core model, one line each --------------------------------
    ("eq_core_1",
     r"$d_i \;=\; \sum_{j=1}^{L}\, w_{j,\,\mathrm{tcr}(i)} \cdot M\left[\,a_{ij},\, b_{ij}\,\right]$",
     30, NAVY),
    ("eq_core_2",
     r"$P(\mathrm{level}_i) \;=\; \mathrm{OrderedLogistic}\left(\eta_i = d_0 - d_i,\;\; c_1 < c_2\right)$",
     24, NAVY),

    # --- how M is built in the atomic model ---------------------------
    ("eq_atomic",
     r"$M[a,b] \;=\; \sum_{k=1}^{K} \theta_k \left|\, \phi_k(a) - \phi_k(b) \,\right|,"
     r"\qquad \theta_k \geq 0$",
     26, NAVY),

    # --- the five ways M is assembled ---------------------------------
    ("eq_m_fixed",   r"$M = D[a,b]$", 21, BODY),
    ("eq_m_learned", r"$M = D[a,b]\,\left(1 + \delta_{ab}\right)$", 21, BODY),
    # inline Sigma (limits beside, not below) so every table row is the same
    # height -- a display-style \sum here would render at half the font size
    ("eq_m_atomic",  r"$M = \Sigma_k\, \theta_k \left|\Delta\phi_k\right|$", 21, ATOMIC),
    ("eq_m_frozen",
     r"$M = \Sigma_k\, \bar{\theta}_k \left|\Delta\phi_k\right| + \delta_{ab}$", 21, GREEN),
    ("eq_m_feature",
     r"$M = \Sigma_k\, \bar{\theta}_k \left|\Delta\phi_k\right| + \Sigma_{k \leq l}\, \Lambda_{kl}\, u_k u_l$",
     21, GREEN),

    # --- the worked example, one line per step ------------------------
    ("eq_step1",
     r"$M[P,R] \;=\; \Sigma_k\, \theta_k \left|\Delta\phi_k\right| \;=\; 28.221$", 22, NAVY),
    ("eq_step2",
     r"$d \;=\; M \cdot w_{\mathrm{16A11},\,2} \;=\; 28.221 \times 0.8066 \;=\; 22.7635$",
     22, NAVY),
    ("eq_step3",
     r"$\eta \;=\; d_0 - d \;=\; 0.8334 - 22.7635 \;=\; -21.930$", 22, NAVY),
    ("eq_step4",
     r"$P \;=\; \mathrm{OrderedLogistic}\left(\eta,\; [\,-1.4946,\; 0.4629\,]\right)$",
     22, NAVY),

    # --- priors, for the protocol slide -------------------------------
    ("eq_priors",
     r"$\alpha,\beta \sim \Gamma(2,2) \quad w \sim \mathrm{Beta}(\alpha,\beta)"
     r"\quad \theta_k \sim \mathrm{HalfNormal}(1)$", 20, NAVY),
]


def main():
    print("rendering equations ...")
    for name, latex, fs, col in EQUATIONS:
        render(name, latex, fs, col)
    with open(_os.path.join(FIG, "eq_ratios.json"), "w") as fh:
        json.dump(RATIOS, fh, indent=2, sort_keys=True)
    print(f"\nwrote figures/eq_ratios.json ({len(RATIOS)} equations)")


if __name__ == "__main__":
    main()
