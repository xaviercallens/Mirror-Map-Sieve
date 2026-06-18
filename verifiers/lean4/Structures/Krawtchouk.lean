/-
# Krawtchouk Polynomials

This module defines **Krawtchouk polynomials**, a family of orthogonal polynomials
arising in combinatorics and coding theory. They are defined via a **three-term recurrence relation**
and are orthogonal with respect to the **binomial distribution**.

## References
- [Wikipedia: Krawtchouk Polynomials](https://en.wikipedia.org/wiki/Krawtchouk_polynomials)
- [Koekoek, Lesky, and Swarttouw: Hypergeometric Orthogonal Polynomials](https://www.win.tue.nl/~aeb/gkp/hypergeometric.html)
-/

import Mathlib.Algebra.Polynomial.Basic
import Mathlib.Data.Fintype.Basic
import Mathlib.Topology.Instances.Real
import Mathlib.Analysis.SpecialFunctions.Trigonometric.Chebyshev
import Mathlib.Order.Filter.Basic

/-!
## Definition of Krawtchouk Polynomials
-/

open Polynomial Fintype Filter Topology

/-- Krawtchouk polynomial of degree `n` evaluated at `x`.
Parameters:
- `n`: Degree of the polynomial.
- `x`: Evaluation point (real number).
- `N`: Total number of points (default: arbitrary).
- `p`: Probability parameter (default: 1/2 for symmetric case). -/
noncomputable def krawtchouk : ℕ → ℝ → ℕ → ℝ → ℝ
  | 0, _, _, _ => 1
  | 1, x, N, p => (2 * (N : ℝ) * p - 1) * x - (N : ℝ) * (1 - p)
  | n + 2, x, N, p =>
    ((2 * (N : ℝ) - 2 * (n + 2 : ℝ) + 1) * p - 1) * x * krawtchouk (n + 1) x N p -
    (n + 2 : ℝ)⁻¹ * ((N : ℝ) - (n + 2 : ℝ) + 1) * (1 - p) * krawtchouk n x N p

/-!
## Basic Properties
-/

@[simp]
theorem krawtchouk_zero (x : ℝ) (N : ℕ) (p : ℝ) :
    krawtchouk 0 x N p = 1 := by
  rfl

@[simp]
theorem krawtchouk_one (x : ℝ) (N : ℕ) (p : ℝ) :
    krawtchouk 1 x N p = (2 * (N : ℝ) * p - 1) * x - (N : ℝ) * (1 - p) := by
  rfl

/-- Krawtchouk polynomials satisfy a three-term recurrence relation. -/
theorem krawtchouk_recurrence (n : ℕ) (x : ℝ) (N : ℕ) (p : ℝ) :
    krawtchouk (n + 2) x N p =
    ((2 * (N : ℝ) - 2 * (n + 2 : ℝ) + 1) * p - 1) * x * krawtchouk (n + 1) x N p -
    (n + 2 : ℝ)⁻¹ * ((N : ℝ) - (n + 2 : ℝ) + 1) * (1 - p) * krawtchouk n x N p := by
  rfl

/-!
## Orthogonality
-/

/-- The binomial distribution with parameters `N` and `p`. -/
noncomputable def binomial_distribution (N : ℕ) (p : ℝ) (k : ℕ) : ℝ :=
  if k ≤ N then (Nat.choose N k : ℝ) * p^k * (1 - p)^(N - k) else 0

/-- Orthogonality of Krawtchouk polynomials with respect to the binomial distribution. -/
theorem krawtchouk_orthogonality (n m : ℕ) (N : ℕ) (p : ℝ) (hnm : n ≠ m) :
    ∑ k in Finset.range (N + 1), krawtchouk n (k : ℝ) N p * krawtchouk m (k : ℝ) N p *
    binomial_distribution N p k = 0 := by
  sorry  -- Proof requires generating functions or Rodrigues' formula

/-- Norm squared of Krawtchouk polynomials. -/
theorem krawtchouk_norm_sq (n : ℕ) (N : ℕ) (p : ℝ) :
    ∑ k in Finset.range (N + 1), (krawtchouk n (k : ℝ) N p)^2 * binomial_distribution N p k =
    ((Nat.choose N n : ℝ))⁻¹ * ((p * (1 - p))^n)⁻¹ * ((N : ℝ) * p * (1 - p))^n := by
  sorry

/-!
## Special Cases
-/

/-- Krawtchouk polynomials reduce to Chebyshev polynomials when `N → ∞`. -/
theorem krawtchouk_to_chebyshev (n : ℕ) (x : ℝ) (p : ℝ) :
    Tendsto (fun N : ℕ => krawtchouk n (x * Real.sqrt ((N : ℝ) * p * (1 - p))) N p) atTop (𝓝 ((Polynomial.Chebyshev.T ℝ n).eval x)) := by
  sorry
