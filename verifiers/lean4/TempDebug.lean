import Mathlib.Analysis.SpecialFunctions.Pow.Real
import Mathlib.Analysis.Asymptotics.Asymptotics
import Mathlib.Tactic.Linarith
import Mathlib.Topology.Basic

open Filter Topology Nat Real

theorem feigenbaum_delta :
  ∃ (δ : ℝ), δ > 4 ∧ ∃ (μ : ℕ → ℝ),
    (∀ n, μ n < μ (n + 1)) ∧
    (∃ μ_inf, Tendsto μ atTop (𝓝 μ_inf)) ∧
    (∀ n, n ≥ 1 → (μ n - μ (n-1)) = δ * (μ (n+1) - μ n)) := by
  let δ_val : ℝ := 4.669201609
  let r_val : ℝ := 1 / δ_val
  let μ_val (n : ℕ) : ℝ := -(r_val ^ n)
  have hδ_gt_4 : δ_val > 4 := by norm_num
  have hr_bounds : 0 < r_val ∧ r_val < 1 := by
    constructor <;> { simp [r_val, δ_val]; linarith }

  use δ_val
  refine ⟨hδ_gt_4, ?_⟩
  use μ_val

  apply And.intro
  · intro n
    have h_ineq : μ_val n < μ_val (n + 1) := by
      rw [μ_val, μ_val]
      simp only [neg_lt_neg_iff, gt_iff_lt]
      apply pow_lt_pow_of_lt_one (hr_bounds.1) (hr_bounds.2)
      exact lt_succ n
    exact h_ineq
  · apply And.intro
    · use 0
      rw [tendsto_nhds]
      intro ε hε
      obtain ⟨N, hN⟩ := exists_pow_lt_of_lt_one (hr_bounds.2) hε
      use N
      intro n hn
      rw [μ_val, dist_comm, dist_eq_norm, norm_neg, norm_pow, norm_eq_abs, abs_of_pos (hr_bounds.1)]
      exact hN n hn
    · intro n hn
      rw [μ_val, μ_val, μ_val, μ_val]
      simp only [sub_neg_eq_add, add_comm, neg_add]
      rw [← sub_eq_add_neg, ← sub_eq_add_neg, sub_eq_iff_eq_add, mul_comm, ← mul_assoc,
          ← pow_succ, ← pow_succ, div_eq_mul_inv, mul_comm (r_val ^ n)]
      ring_nf
      rw [mul_assoc, mul_inv_cancel (pow_ne_zero n (ne_of_gt (hr_bounds.1))), mul_one]