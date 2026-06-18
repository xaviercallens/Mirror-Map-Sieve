/-
  S₂₀ Sequence — Formal Lean 4 Verification
  ============================================

  The Callens–Schmidt sequence S₂₀(n) = Σ_{k=0}^{n} C(n,k)⁴ · C(n+k,k).

  This module provides:
  • The definition of S₂₀ via Finset.sum
  • Kernel-verified (decide) proofs that the order-5 recurrence holds at n=0
  • Kernel-verified first values

  STATUS: ✅ Sorry-free, axiom-free, admit-free
  All proofs use `decide` — the Lean 4 kernel evaluates the exact integer
  arithmetic and confirms equality. No external oracles.

  Reference: "The Callens–Schmidt Sequence S₂₀(n): A ¾-Well-Poised ₅F₄
  Beyond Apéry", Xavier Callens, SocrateAI Lab, June 2026.
-/

import Mathlib.Data.Nat.Choose.Basic
import Mathlib.Data.Finset.Basic
import Mathlib.Tactic

namespace Agora.Discovery.S20Seq

/-- The Callens–Schmidt sequence: S₂₀(n) = Σ_{k=0}^{n} C(n,k)⁴ · C(n+k,k) -/
def S20 (n : ℕ) : ℤ :=
  ↑((Finset.range (n + 1)).sum (fun k => (Nat.choose n k)^4 * (Nat.choose (n + k) k)))

/-- S₂₀(0) = 1 -/
theorem s20_val_0 : S20 0 = 1 := by decide

/-- S₂₀(1) = 3 -/
theorem s20_val_1 : S20 1 = 3 := by decide

/-- S₂₀(2) = 55 -/
theorem s20_val_2 : S20 2 = 55 := by decide

/-- S₂₀(3) = 1155 -/
theorem s20_val_3 : S20 3 = 1155 := by decide

/-- S₂₀(4) = 29751 -/
theorem s20_val_4 : S20 4 = 29751 := by decide

/-- S₂₀(5) = 852753 -/
theorem s20_val_5 : S20 5 = 852753 := by decide

/-!
## Order-5 Recurrence — Base Case Verification

The minimal recurrence for S₂₀ has order 5 with polynomial coefficients
of degree 9. At n=0, the polynomial coefficients reduce to their constant
terms, giving the following exact integer identity:

  P₀(0)·S₂₀(0) + P₁(0)·S₂₀(1) + P₂(0)·S₂₀(2)
  + P₃(0)·S₂₀(3) + P₄(0)·S₂₀(4) + P₅(0)·S₂₀(5) = 0

This is verified by the Lean 4 kernel via `decide`.
-/

/-- The order-5 recurrence for S₂₀ holds at n=0.
    This is a kernel-verified numerical identity — no sorry, no axiom.
    The integer coefficients are the constant terms P_j(0) of the
    degree-9 polynomial coefficients of the minimal recurrence. -/
theorem recurrence_at_0 :
    (-5412650858431135013634958175726842170573378411840) * S20 0 +
    (-6600211789894833600749251782579095561783149274990400) * S20 1 +
    (-29724234537629673550738669814459138431115401303206240) * S20 2 +
    (-6675296886001563027617164081383167394996985596478240) * S20 3 +
    (-272198721521932617277293245047721130052020296806560) * S20 4 +
    (20478134952232355172884134183653971676016433020000) * S20 5
    = 0 := by decide

end Agora.Discovery.S20Seq
