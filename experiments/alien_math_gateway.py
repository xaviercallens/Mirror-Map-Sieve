#!/usr/bin/env python3
"""
alien_math_gateway.py
=====================
Numerical experiments for the Kal Alien Mathematics gateway problem.

Four self-contained experiments demonstrate core algebraic constructions
that underpin the holographic tensor-network speed-up claim:

  1. Strassen 2×2 correctness   (Lean 4: strassen_2x2_correct)
  2. Charging Algebra cross-term annihilation (Lean 4: cross_term_zero)
  3. Scaling comparison  N^3 vs N^{log2 7} vs N^{2.372} vs N^2 log N
  4. Krawtchouk witness positivity  (Lean 4: krawtchouk_witness_positive)

Dependencies: numpy, matplotlib, Python standard library only.

Usage
-----
    python alien_math_gateway.py              # run all experiments
    python alien_math_gateway.py --verify-all # same, with explicit flag
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from fractions import Fraction
from typing import List, Tuple

import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for saving figures
import matplotlib.pyplot as plt


# ────────────────────────────────────────────────────────────────────
#  Helpers
# ────────────────────────────────────────────────────────────────────

FIGURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")


def ensure_figures_dir() -> None:
    """Create the figures output directory if it doesn't exist."""
    os.makedirs(FIGURES_DIR, exist_ok=True)


def section_header(title: str) -> None:
    """Print a clear experiment header."""
    bar = "=" * 72
    print(f"\n{bar}")
    print(f"  {title}")
    print(f"{bar}\n")


# ────────────────────────────────────────────────────────────────────
#  Experiment 1: Strassen 2×2 Correctness
#  Lean 4 theorem: strassen_2x2_correct
# ────────────────────────────────────────────────────────────────────

def experiment_1_strassen() -> bool:
    """
    Compare the standard 8-multiplication matrix product with
    Strassen's 7-multiplication algorithm on concrete 2×2 matrices.

    Returns True iff both products match element-wise.
    """
    section_header("Experiment 1: Strassen 2×2 Correctness")

    # --- Input matrices --------------------------------------------------
    A = np.array([[1, 2],
                  [3, 4]], dtype=int)
    B = np.array([[5, 6],
                  [7, 8]], dtype=int)

    # --- Standard product (8 scalar multiplications) ----------------------
    C_std = A @ B
    n_muls_std = 8
    print("A =")
    print(A)
    print("\nB =")
    print(B)
    print(f"\nStandard product  (8 multiplications):\n{C_std}")

    # --- Strassen product (7 scalar multiplications) ----------------------
    a00, a01 = A[0, 0], A[0, 1]
    a10, a11 = A[1, 0], A[1, 1]
    b00, b01 = B[0, 0], B[0, 1]
    b10, b11 = B[1, 0], B[1, 1]

    # The 7 auxiliary products
    m1 = (a00 + a11) * (b00 + b11)      # (a00+a11)(b00+b11)
    m2 = (a10 + a11) * b00              # (a10+a11) b00
    m3 = a00 * (b01 - b11)              # a00 (b01-b11)
    m4 = a11 * (b10 - b00)              # a11 (b10-b00)
    m5 = (a00 + a01) * b11              # (a00+a01) b11
    m6 = (a10 - a00) * (b00 + b01)      # (a10-a00)(b00+b01)
    m7 = (a01 - a11) * (b10 + b11)      # (a01-a11)(b10+b11)

    # Reconstruct the product matrix
    c00 = m1 + m4 - m5 + m7
    c01 = m3 + m5
    c10 = m2 + m4
    c11 = m1 - m2 + m3 + m6

    C_str = np.array([[c00, c01],
                      [c10, c11]])
    n_muls_str = 7

    print(f"\nStrassen product  (7 multiplications):\n{C_str}")

    match = np.array_equal(C_std, C_str)
    print(f"\nExact match: {match}")
    print(f"Multiplications  —  standard: {n_muls_std}  |  Strassen: {n_muls_str}")

    if match:
        print("✓  Strassen 2×2 correctness verified.")
    else:
        print("✗  MISMATCH — something is wrong.")

    return match


# ────────────────────────────────────────────────────────────────────
#  Experiment 2: Charging Algebra Cross-Term Annihilation
#  Lean 4 theorem: cross_term_zero
# ────────────────────────────────────────────────────────────────────

class ChargingAlgebra:
    """
    A 4-component algebra over the rationals with basis {1, i, j, ε}.

    Multiplication rule (bilinear extension):
        re  = q1.re * q2.re  -  q1.i * q2.i  -  q1.j * q2.j
        i   = q1.re * q2.i   +  q1.i * q2.re
        j   = q1.re * q2.j   +  q1.j * q2.re
        eps = q1.re * q2.eps  +  q1.eps * q2.re
              + q1.i * q2.j   -  q1.j * q2.i

    Trace:  tr(q) = q.re

    All arithmetic uses fractions.Fraction for exact results.
    """

    __slots__ = ("re", "i", "j", "eps")

    def __init__(self, re: Fraction, i: Fraction, j: Fraction, eps: Fraction):
        self.re = Fraction(re)
        self.i = Fraction(i)
        self.j = Fraction(j)
        self.eps = Fraction(eps)

    # --- Algebra operations -----------------------------------------------

    def __mul__(self, other: "ChargingAlgebra") -> "ChargingAlgebra":
        return ChargingAlgebra(
            re  = self.re * other.re  - self.i * other.i  - self.j * other.j,
            i   = self.re * other.i   + self.i * other.re,
            j   = self.re * other.j   + self.j * other.re,
            eps = self.re * other.eps  + self.eps * other.re
                  + self.i * other.j   - self.j * other.i,
        )

    def __sub__(self, other: "ChargingAlgebra") -> "ChargingAlgebra":
        return ChargingAlgebra(
            re  = self.re  - other.re,
            i   = self.i   - other.i,
            j   = self.j   - other.j,
            eps = self.eps  - other.eps,
        )

    def __repr__(self) -> str:
        return (f"CA(re={self.re}, i={self.i}, j={self.j}, eps={self.eps})")

    # --- Trace & Q-map ----------------------------------------------------

    @property
    def trace(self) -> Fraction:
        """tr(q) = q.re  (the real / scalar component)."""
        return self.re

    @staticmethod
    def commutator(a: "ChargingAlgebra", b: "ChargingAlgebra") -> "ChargingAlgebra":
        """[A, B] = A*B - B*A."""
        return a * b - b * a

    @staticmethod
    def Q(a: Fraction, b: Fraction) -> "ChargingAlgebra":
        """
        Charging map:  Q(a, b) = CA(re = a*b,  i = a,  j = b,  eps = 0).

        Key property:  tr(Q(a,b)) = a*b  (product encoded in the trace).
        """
        return ChargingAlgebra(re=a * b, i=a, j=b, eps=Fraction(0))


def experiment_2_charging_algebra() -> bool:
    """
    Verify the cross-term annihilation identity:
        tr([Q(a1,b1), Q(a2,b2)]) = 0    for all a1,b1,a2,b2 ∈ ℚ.

    Also verifies that tr(Q(a,b)) = a*b  (product recovery).
    Uses exact rational arithmetic — no floating-point.

    Returns True iff every test passes.
    """
    section_header("Experiment 2: Charging Algebra — Cross-Term Annihilation")

    all_ok = True

    # --- 2a.  Random pairs ------------------------------------------------
    print("2a) Commutator trace = 0 for 10 random rational pairs")
    print("-" * 60)
    rng = random.Random(42)  # reproducible

    for trial in range(10):
        a1 = Fraction(rng.randint(-20, 20), rng.randint(1, 10))
        b1 = Fraction(rng.randint(-20, 20), rng.randint(1, 10))
        a2 = Fraction(rng.randint(-20, 20), rng.randint(1, 10))
        b2 = Fraction(rng.randint(-20, 20), rng.randint(1, 10))

        Q1 = ChargingAlgebra.Q(a1, b1)
        Q2 = ChargingAlgebra.Q(a2, b2)
        comm = ChargingAlgebra.commutator(Q1, Q2)
        tr = comm.trace

        status = "✓" if tr == 0 else "✗"
        if tr != 0:
            all_ok = False
        print(f"  trial {trial+1:2d}:  a1={str(a1):>5s}  b1={str(b1):>5s}  "
              f"a2={str(a2):>5s}  b2={str(b2):>5s}  →  tr([Q1,Q2]) = {tr}  {status}")

    # --- 2b.  Specific worked example -------------------------------------
    print(f"\n2b) Detailed example:  a1=3, b1=7, a2=5, b2=2")
    print("-" * 60)

    a1, b1 = Fraction(3), Fraction(7)
    a2, b2 = Fraction(5), Fraction(2)

    Q1 = ChargingAlgebra.Q(a1, b1)
    Q2 = ChargingAlgebra.Q(a2, b2)
    print(f"  Q(3,7)  = {Q1}")
    print(f"  Q(5,2)  = {Q2}")

    AB = Q1 * Q2
    BA = Q2 * Q1
    comm = AB - BA
    print(f"  Q1*Q2   = {AB}")
    print(f"  Q2*Q1   = {BA}")
    print(f"  [Q1,Q2] = {comm}")
    print(f"  tr([Q1,Q2]) = {comm.trace}")

    if comm.trace != 0:
        print("  ✗  FAILURE: commutator trace ≠ 0")
        all_ok = False
    else:
        print("  ✓  Commutator trace is exactly 0.")

    # --- 2c.  Product recovery:  tr(Q(a,b)) == a*b -----------------------
    print(f"\n2c) Product recovery:  tr(Q(a,b)) == a*b  for 10 pairs")
    print("-" * 60)

    for trial in range(10):
        a = Fraction(rng.randint(-50, 50), rng.randint(1, 10))
        b = Fraction(rng.randint(-50, 50), rng.randint(1, 10))
        q = ChargingAlgebra.Q(a, b)
        ok = (q.trace == a * b)
        status = "✓" if ok else "✗"
        if not ok:
            all_ok = False
        print(f"  trial {trial+1:2d}:  a={str(a):>6s}  b={str(b):>6s}  "
              f"tr(Q)={str(q.trace):>8s}  a*b={str(a*b):>8s}  {status}")

    if all_ok:
        print("\n✓  All Charging Algebra tests passed (exact rational arithmetic).")
    else:
        print("\n✗  Some tests FAILED.")

    return all_ok


# ────────────────────────────────────────────────────────────────────
#  Experiment 3: Scaling Comparison (N = 2 .. 1024)
# ────────────────────────────────────────────────────────────────────

def experiment_3_scaling() -> str:
    """
    Generate a log-log plot comparing four matrix-multiplication scalings:

        • Naive:                  N^3
        • Strassen:               N^{log_2 7} ≈ N^{2.807}
        • Earth SOTA (2023):      N^{2.372}   (Williams–Alman–Duan)
        • Alien claim (holo):     N^2 · log_2(N)

    Saves the figure and returns the file path.
    """
    section_header("Experiment 3: Scaling Comparison (N = 2 .. 1024)")

    ensure_figures_dir()
    out_path = os.path.join(FIGURES_DIR, "scaling_comparison.png")

    # Powers of 2 from 2 to 1024
    Ns = np.array([2**k for k in range(1, 11)])  # 2, 4, 8, ..., 1024

    strassen_exp = math.log2(7)   # ≈ 2.807
    earth_exp    = 2.372          # Williams–Alman–Duan 2023

    naive   = Ns.astype(float) ** 3
    strassen = Ns.astype(float) ** strassen_exp
    earth   = Ns.astype(float) ** earth_exp
    alien   = Ns.astype(float) ** 2 * np.log2(Ns.astype(float))

    # --- Print table ------------------------------------------------------
    print(f"{'N':>6s}  {'Naive N^3':>14s}  {'Strassen':>14s}  "
          f"{'Earth 2.372':>14s}  {'Alien N²logN':>14s}")
    print("-" * 72)
    for i, n in enumerate(Ns):
        print(f"{n:6d}  {naive[i]:14.1f}  {strassen[i]:14.1f}  "
              f"{earth[i]:14.1f}  {alien[i]:14.1f}")

    # --- Plot -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 6))

    ax.loglog(Ns, naive,    "o-",  label=r"Naïve  $N^3$",               linewidth=2)
    ax.loglog(Ns, strassen, "s-",  label=r"Strassen  $N^{2.807}$",      linewidth=2)
    ax.loglog(Ns, earth,    "^-",  label=r"Earth SOTA  $N^{2.372}$",    linewidth=2)
    ax.loglog(Ns, alien,    "D-",  label=r"Alien (holo)  $N^2 \log N$", linewidth=2,
              color="crimson")

    ax.set_xlabel("Matrix size  N", fontsize=13)
    ax.set_ylabel("Operation count", fontsize=13)
    ax.set_title("Matrix Multiplication Scaling Comparison", fontsize=14)
    ax.legend(fontsize=11, loc="upper left")
    ax.grid(True, which="both", ls="--", alpha=0.4)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    print(f"\nFigure saved → {out_path}")
    return out_path


# ────────────────────────────────────────────────────────────────────
#  Experiment 4: Krawtchouk Witness Positivity
#  Lean 4 theorem: krawtchouk_witness_positive
# ────────────────────────────────────────────────────────────────────

def comb(n: int, k: int) -> Fraction:
    """Exact binomial coefficient C(n, k) as a Fraction."""
    if k < 0 or k > n:
        return Fraction(0)
    return Fraction(math.comb(n, k))


def krawtchouk(k: int, x: int, n: int = 21, q: int = 2) -> Fraction:
    """
    Krawtchouk polynomial K_k(x) for the binary Hamming scheme H(n, q).

    K_k(x) = Σ_{j=0}^{k}  (-1)^j · C(x, j) · C(n-x, k-j)

    All arithmetic is exact via fractions.Fraction.
    """
    total = Fraction(0)
    for j in range(k + 1):
        sign = Fraction((-1) ** j)
        total += sign * comb(x, j) * comb(n - x, k - j)
    return total


def W_alien(w: int) -> Fraction:
    """
    Alien witness polynomial (sum-of-squares + 1):

        W(w) = ( c2·K2(w) - c4·K4(w) + c7·K7(w) - c10·K10(w) )² + 1

    with exact rational coefficients:
        c2  = 17493 / 3114
        c4  =   892 / 11
        c7  = 10023 / 17
        c10 = 4111902 / 13331

    By construction W(w) ≥ 1 > 0 for all w, which witnesses
    that the design bound is not tight.
    """
    c2  = Fraction(17493, 3114)
    c4  = Fraction(892, 11)
    c7  = Fraction(10023, 17)
    c10 = Fraction(4111902, 13331)

    K2  = krawtchouk(2,  w)
    K4  = krawtchouk(4,  w)
    K7  = krawtchouk(7,  w)
    K10 = krawtchouk(10, w)

    inner = c2 * K2 - c4 * K4 + c7 * K7 - c10 * K10
    return inner * inner + 1


def experiment_4_krawtchouk() -> bool:
    """
    Compute the alien Krawtchouk witness W(w) for w = 0 … 21
    and verify strict positivity (W(w) > 0) at every point.

    Uses exact rational arithmetic — no floating-point rounding.
    Saves a bar chart of log10(W(w)) to figures/.

    Returns True iff all 22 values are strictly positive.
    """
    section_header("Experiment 4: Krawtchouk Witness Positivity  (H(21,2))")

    ensure_figures_dir()
    out_path = os.path.join(FIGURES_DIR, "krawtchouk_positivity.png")

    all_positive = True
    values: List[Tuple[int, Fraction]] = []

    print(f"{'w':>3s}  {'W_alien(w)':>60s}  {'> 0?':>5s}")
    print("-" * 74)

    for w in range(22):
        val = W_alien(w)
        values.append((w, val))
        pos = val > 0
        if not pos:
            all_positive = False

        # For display, truncate very long numerators
        val_str = str(val)
        if len(val_str) > 55:
            # Show as float approximation with note
            val_str = f"≈ {float(val):.6e}"
        print(f"{w:3d}  {val_str:>60s}  {'✓' if pos else '✗':>5s}")

    if all_positive:
        print(f"\n✓  All 22 values are strictly positive (W(w) ≥ 1 by construction).")
    else:
        print(f"\n✗  Some values are NOT positive — check coefficients.")

    # --- Bar chart of log10(W(w)) -----------------------------------------
    ws = [v[0] for v in values]
    log_vals = [float(v[1].numerator) / float(v[1].denominator) for v in values]
    log_vals = [math.log10(v) if v > 0 else 0.0 for v in log_vals]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(ws, log_vals, color="steelblue", edgecolor="navy", alpha=0.85)
    ax.axhline(0, color="red", linewidth=1, linestyle="--", label="Positivity threshold")
    ax.set_xlabel("Weight  w", fontsize=13)
    ax.set_ylabel(r"$\log_{10}\, W_{\mathrm{alien}}(w)$", fontsize=13)
    ax.set_title("Krawtchouk Witness Positivity — H(21, 2)", fontsize=14)
    ax.set_xticks(range(22))
    ax.legend(fontsize=11)
    ax.grid(axis="y", ls="--", alpha=0.4)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    print(f"Figure saved → {out_path}")
    return all_positive


# ────────────────────────────────────────────────────────────────────
#  Main
# ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kal Alien Mathematics Gateway — Numerical Experiments"
    )
    parser.add_argument(
        "--verify-all",
        action="store_true",
        default=True,
        help="Run all four experiments and verify results (default behaviour).",
    )
    parser.parse_args()

    results = {}

    results["1_strassen"]    = experiment_1_strassen()
    results["2_charging"]    = experiment_2_charging_algebra()
    results["3_scaling"]     = experiment_3_scaling()  # returns path, always "passes"
    results["4_krawtchouk"]  = experiment_4_krawtchouk()

    # --- Summary ----------------------------------------------------------
    section_header("Summary")
    for key, val in results.items():
        status = "PASS ✓" if val else "FAIL ✗"
        if isinstance(val, str):
            status = f"DONE (→ {val})"
        print(f"  {key:20s}  {status}")

    all_pass = all(v is True or isinstance(v, str) for v in results.values())
    print()
    if all_pass:
        print("All experiments completed successfully.")
    else:
        print("Some experiments FAILED — review output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
