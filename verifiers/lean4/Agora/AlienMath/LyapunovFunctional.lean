import Mathlib.Tactic

/-!
# Corrected Lyapunov Functional (v3) — Pointwise Non-Negativity

This module verifies pointwise non-negativity of the three integrand terms
of the dimensionally-corrected Alien Lyapunov functional:

  V(u) = ∫ (71/3 · u_xx⁴ + 4/19 · u_x² · u_xxx² + 211/73 · u_xxxx²) dx

All three terms carry 8 total spatial-derivative factors (dimensionally
homogeneous under KS dilation symmetry x → λx, u → λ⁻³u).

**What is verified**: Each integrand is ≥ 0 for all real inputs.
**What is NOT verified**: H⁴-coercivity, monotone decay along KS trajectories.
These require Sobolev interpolation not yet in Mathlib.
-/

-- VERIFIED (no sorry, no axiom): pointwise non-negativity of each integrand term.

/-- The u_xx⁴ term: (71/3) · x⁴ ≥ 0 for all x ∈ ℝ. -/
lemma term1_nonneg (uxx : ℝ) : (71 / 3 : ℝ) * uxx ^ 4 ≥ 0 := by positivity

/-- The u_x² · u_xxx² term: (4/19) · x² · y² ≥ 0 for all x, y ∈ ℝ. -/
lemma term2_nonneg (ux uxxx : ℝ) : (4 / 19 : ℝ) * ux ^ 2 * uxxx ^ 2 ≥ 0 := by positivity

/-- The (u_xxxx)² term: (211/73) · x² ≥ 0 for all x ∈ ℝ.
This replaced the dimensionally inconsistent u_x⁴ term from v2. -/
lemma term3_nonneg (uxxxx : ℝ) : (211 / 73 : ℝ) * uxxxx ^ 2 ≥ 0 := by positivity
