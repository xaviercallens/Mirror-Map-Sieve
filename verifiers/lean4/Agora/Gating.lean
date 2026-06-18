/-
  SocrateAI Scientific Agora — Lean 4 Formal Verification Library
  Copyright © 2025-2026 Socrate AI Lab, Paris, France
  Author: Xavier Callens <callensxavier@gmail.com>
  License: Apache-2.0 (framework) + CC-BY-NC-ND 4.0 (proprietary)
  Patent:  US-PAT-PEND-2026-0525

  Agora.Gating — Dynamic gating function properties.

  The dynamic gating mechanism maps a complexity score C ∈ [0, 1] to a
  gate activation g ∈ [0, 1] that controls the mixture weight between
  fast (retrieval) and slow (reasoning) pathways.

  Properties proved:
    1. Monotonicity: higher complexity → higher gate activation
    2. Boundedness: gate output stays in [0, 1]
    3. Sigmoid correctness: the default sigmoid implementation
       satisfies both properties
-/

import Agora.Basic
import Mathlib.Analysis.SpecialFunctions.Exp
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Order.Monotone.Basic
import Mathlib.Tactic.Positivity

set_option autoImplicit false

namespace Agora.Gating

/-! ## Abstract Gating Function -/

/-- An abstract gating function mapping complexity scores to gate
    activations, with monotonicity and boundedness guarantees. -/
structure GatingFunction where
  /-- The gate map: [0,1] → [0,1]. We model it on all of ℝ and
      require the image to lie in [0,1]. -/
  f : ℝ → ℝ
  /-- Monotonicity: higher input → higher output. -/
  monotone : Monotone f
  /-- Lower bound: output ≥ 0. -/
  nonneg : ∀ x, 0 ≤ f x
  /-- Upper bound: output ≤ 1. -/
  le_one : ∀ x, f x ≤ 1

/-! ## Monotonicity Theorem -/

/-- Gating is monotone: if complexity C₁ ≤ C₂, then f(C₁) ≤ f(C₂). -/
theorem gating_monotone (g : GatingFunction)
    (c1 c2 : ComplexityScore)
    (h : c1 ≤ c2) :
    g.f c1.val ≤ g.f c2.val :=
  g.monotone h

/-! ## Boundedness Theorem -/

/-- The gate output lies in [0, 1] for any input. -/
theorem gating_bounded (g : GatingFunction) (c : ComplexityScore) :
    0 ≤ g.f c.val ∧ g.f c.val ≤ 1 :=
  ⟨g.nonneg c.val, g.le_one c.val⟩

/-- The gate output is itself a valid complexity score. -/
def gating_as_score (g : GatingFunction) (c : ComplexityScore) :
    ComplexityScore where
  val  := g.f c.val
  ge_0 := g.nonneg c.val
  le_1 := g.le_one c.val

/-! ## Sigmoid Implementation

The standard sigmoid σ(x) = 1 / (1 + exp(-x)) is the default gating
function in SymBrain. We define a shifted/scaled version:

    σ_gate(C) = 1 / (1 + exp(-k(C - c₀)))

where k > 0 is the steepness and c₀ ∈ (0,1) is the midpoint.
-/

/-- Standard sigmoid function. -/
noncomputable def sigmoid (x : ℝ) : ℝ :=
  1 / (1 + Real.exp (-x))

/-- Shifted sigmoid for gating with steepness k and midpoint c₀. -/
noncomputable def sigmoidGate (k c₀ : ℝ) (x : ℝ) : ℝ :=
  sigmoid (k * (x - c₀))

/-! ### Sigmoid Basic Properties -/

/-- exp(-x) > 0 for all x ∈ ℝ. -/
theorem exp_neg_pos (x : ℝ) : 0 < Real.exp (-x) :=
  Real.exp_pos (-x)

/-- The denominator 1 + exp(-x) > 0. -/
theorem sigmoid_denom_pos (x : ℝ) : 0 < 1 + Real.exp (-x) := by
  linarith [exp_neg_pos x]

/-- σ(x) > 0 for all x. -/
theorem sigmoid_pos (x : ℝ) : 0 < sigmoid x := by
  unfold sigmoid
  apply div_pos one_pos (sigmoid_denom_pos x)

/-- σ(x) ≥ 0 for all x. -/
theorem sigmoid_nonneg (x : ℝ) : 0 ≤ sigmoid x :=
  le_of_lt (sigmoid_pos x)

/-- σ(x) ≤ 1 for all x.

    **Proof sketch**: 1 / (1 + exp(-x)) ≤ 1 ⟺ 1 ≤ 1 + exp(-x),
    which holds since exp(-x) > 0. -/
theorem sigmoid_le_one (x : ℝ) : sigmoid x ≤ 1 := by
  unfold sigmoid
  rw [div_le_one (sigmoid_denom_pos x)]
  linarith [exp_neg_pos x]

/-- σ(x) ∈ (0, 1) for all x. -/
theorem sigmoid_in_unit (x : ℝ) : 0 < sigmoid x ∧ sigmoid x ≤ 1 :=
  ⟨sigmoid_pos x, sigmoid_le_one x⟩

/-! ### Sigmoid Monotonicity -/

/-- The sigmoid function is monotone (non-decreasing).

    **Proof sketch**: σ'(x) = σ(x)(1 − σ(x)) > 0 since σ ∈ (0,1).
    A monotone function on ℝ is one where x ≤ y → f(x) ≤ f(y).
    Equivalently, 1/(1 + exp(-x)) is increasing because exp(-x) is
    decreasing, so 1 + exp(-x) is decreasing, so its reciprocal
    is increasing. -/
theorem sigmoid_monotone : Monotone sigmoid := by
  intro a b hab
  unfold sigmoid
  have h_denom_a := sigmoid_denom_pos a
  have h_denom_b := sigmoid_denom_pos b
  have h_exp : Real.exp (-b) ≤ Real.exp (-a) := Real.exp_monotone (neg_le_neg hab)
  have h_le : 1 + Real.exp (-b) ≤ 1 + Real.exp (-a) := by linarith
  exact div_le_div_of_nonneg_left zero_le_one h_denom_b h_le

/-- The shifted sigmoid σ_gate(k, c₀, ·) is monotone when k > 0.

    **Proof sketch**: Composition of the monotone σ with the
    monotone affine map x ↦ k(x − c₀) (monotone since k > 0). -/
theorem sigmoidGate_monotone (k c₀ : ℝ) (hk : 0 < k) :
    Monotone (sigmoidGate k c₀) := by
  intro a b hab
  unfold sigmoidGate
  apply sigmoid_monotone
  have h1 : a - c₀ ≤ b - c₀ := by linarith
  exact mul_le_mul_of_nonneg_left h1 (le_of_lt hk)

/-! ### Sigmoid as a GatingFunction -/

/-- Construct a `GatingFunction` from the sigmoid gate with given
    steepness and midpoint. -/
noncomputable def sigmoidGatingFunction (k c₀ : ℝ) (hk : 0 < k) :
    GatingFunction where
  f        := sigmoidGate k c₀
  monotone := sigmoidGate_monotone k c₀ hk
  nonneg   := fun x => sigmoid_nonneg (k * (x - c₀))
  le_one   := fun x => sigmoid_le_one (k * (x - c₀))

/-! ### Sigmoid Self-Inverse (Logit) -/

/-- The logit function (inverse of sigmoid):
    logit(p) = ln(p / (1 − p)). -/
noncomputable def logit (p : ℝ) : ℝ :=
  Real.log (p / (1 - p))

/-- σ(logit(p)) = p for p ∈ (0, 1).

    **Proof sketch**: Let q = p/(1−p). Then σ(ln q) = 1/(1 + 1/q) = q/(q+1).
    Since q = p/(1−p), we get q/(q+1) = p. □ -/
theorem sigmoid_logit_inverse (p : ℝ) (hp0 : 0 < p) (hp1 : p < 1) :
    sigmoid (logit p) = p := by
  unfold sigmoid logit
  have hp_sub_pos : 0 < 1 - p := by linarith
  have hdiv_pos : 0 < p / (1 - p) := div_pos hp0 hp_sub_pos
  rw [Real.exp_neg]
  rw [Real.exp_log hdiv_pos]
  have hp_ne : p ≠ 0 := ne_of_gt hp0
  have hp_sub_ne : 1 - p ≠ 0 := ne_of_gt hp_sub_pos
  field_simp

end Agora.Gating
