import Mathlib.Tactic
import Mathlib.Combinatorics.Enumerative.Partition
import Mathlib.Data.Multiset.Fold

-- Replace the `IntegerPartition` axiom with Mathlib's native `Nat.Partition`
-- axiom IntegerPartition (n : ℕ) : Type
-- axiom largest_part {n : ℕ} (lam : IntegerPartition n) : ℕ

/-- The largest part of a partition. -/
def largest_part {n : ℕ} (lam : Nat.Partition n) : ℕ :=
  lam.parts.fold max 0

axiom SchurPolynomial (R : Type) : Type
axiom s_poly {n : ℕ} (lam : Nat.Partition n) : SchurPolynomial ℕ

-- Define how a single row Schur polynomial maps for an index i
axiom single_row_schur (i : ℕ) : SchurPolynomial ℕ

-- Define an additive group structure on SchurPolynomial ℕ so we can use +
axiom add_schur : SchurPolynomial ℕ → SchurPolynomial ℕ → SchurPolynomial ℕ
axiom zero_schur : SchurPolynomial ℕ

noncomputable instance : Add (SchurPolynomial ℕ) where
  add := add_schur

noncomputable instance : Zero (SchurPolynomial ℕ) where
  zero := zero_schur

axiom plethysm (f g : SchurPolynomial ℕ) : SchurPolynomial ℕ
axiom SchurPositive (f : SchurPolynomial ℕ) : Prop

/-- The sum of single-row Schur polynomials `s_(1) + s_(2) + ... + s_(k)`. -/
noncomputable def sum_single_schur : ℕ → SchurPolynomial ℕ
  | 0     => zero_schur
  | (n+1) => sum_single_schur n + single_row_schur n

/-- For any partition `lam` of `n`, there exists an integer `k ≥ 1` such that
    the plethysm `s_lam ∘ (s_(1) + s_(2) + ... + s_(k))` is Schur-positive.
    Moreover, `k` is bounded above by `n + lam₁`, where `lam₁` is the largest part of `lam`. -/
axiom schur_positivity_threshold_conjecture {n : ℕ} (lam : Nat.Partition n) :
  ∃ (k : ℕ), 1 ≤ k ∧ k ≤ n + largest_part lam ∧ SchurPositive (plethysm (s_poly lam) (sum_single_schur k))
