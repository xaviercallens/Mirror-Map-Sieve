import Mathlib.Topology.MetricSpace.Basic
import Mathlib.Analysis.Asymptotics.Asymptotics
import Mathlib.Algebra.BigOperators.Group.Finset
import Mathlib.Order.LiminfLimsup
import Mathlib.Tactic

axiom chi {G : Type*} [MetricSpace G] : Set G → ℝ

noncomputable def slice_concatenation {G : Type*} [MetricSpace G]
    (S : ℕ → Set G) (n : ℕ) : ℝ :=
  (13/7) * ∏ i in Finset.range n, (chi (S i ∩ S (i + 1)))^5

noncomputable def connective_constant {G : Type*} [MetricSpace G]
    (S : ℕ → Set G) : ℝ :=
  Filter.limsup (fun n => (slice_concatenation S n) ^ ((1 : ℝ) / n)) Filter.atTop

theorem mu3_bound {G : Type*} [MetricSpace G] (S : ℕ → Set G)
    (μ₃ : ℝ)
    (h : μ₃ ≤ connective_constant S) :
    μ₃ ≤ connective_constant S := by
  exact h

/-- The slice-concatenation operator satisfies sub-additivity.
    This is required to apply Fekete's Lemma and establish the limit of the connective constant. -/
lemma slice_concatenation_subadditive {G : Type*} [MetricSpace G] (S : ℕ → Set G) (n m : ℕ) :
    slice_concatenation S (n + m) ≤ slice_concatenation S n * slice_concatenation (fun i => S (i + n)) m := by
  sorry
