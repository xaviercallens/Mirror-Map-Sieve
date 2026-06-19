/-
  S₂₀ Sequence — Formal Lean 4 Verification
  ============================================

  The Callens–Alix sequence S₂₀(n) = Σ_{k=0}^{n} C(n,k)⁴ · C(n+k,k).

  This module provides:
  • The definition of S₂₀ via Finset.sum
  • Kernel-verified (decide) proofs that the order-5 left-multiple recurrence holds at n=0
  • Kernel-verified first values

  STATUS: ✅ Sorry-free, axiom-free, admit-free
  All proofs use `decide` — the Lean 4 kernel evaluates the exact integer
  arithmetic and confirms equality. No external oracles.

  Reference: "The Callens–Alix Sequence S₂₀(n): A ¾-Well-Poised ₅F₄
  Beyond Apéry", Xavier Callens, SocrateAI Lab, June 2026.
-/

import Mathlib.Data.Nat.Choose.Basic
import Mathlib.Data.Finset.Basic
import Mathlib.Data.Nat.Choose.Dvd
import Mathlib.Tactic

namespace Agora.Discovery.S20Seq

/-- The Callens–Alix sequence: S₂₀(n) = Σ_{k=0}^{n} C(n,k)⁴ · C(n+k,k) -/
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
## Order-5 Left-Multiple Recurrence — Base Case Verification

The minimal recurrence for S₂₀ has order 4 with polynomial coefficients of
degree 13. A computationally compact left-multiple has order 5 and degree 9.
At n=0, the order-5 left-multiple recurrence coefficients reduce to their
constant terms, giving the following exact integer identity:

  P₀(0)·S₂₀(0) + P₁(0)·S₂₀(1) + P₂(0)·S₂₀(2)
  + P₃(0)·S₂₀(3) + P₄(0)·S₂₀(4) + P₅(0)·S₂₀(5) = 0

This is verified by the Lean 4 kernel via `decide`.
-/

/-- The order-5 left-multiple recurrence for S₂₀ holds at n=0.
    This is a kernel-verified numerical identity — no sorry, no axiom.
    The integer coefficients are the constant terms P_j(0) of the
    degree-9 polynomial coefficients of the order-5 left-multiple recurrence. -/
theorem recurrence_at_0 :
    (-5412650858431135013634958175726842170573378411840) * S20 0 +
    (-6600211789894833600749251782579095561783149274990400) * S20 1 +
    (-29724234537629673550738669814459138431115401303206240) * S20 2 +
    (-6675296886001563027617164081383167394996985596478240) * S20 3 +
    (-272198721521932617277293245047721130052020296806560) * S20 4 +
    (20478134952232355172884134183653971676016433020000) * S20 5
    = 0 := by decide

/-!
## Supercongruences (Cubic Congruence)

The sequence S₂₀(n) satisfies the remarkable cubic supercongruence:
  S₂₀(p) ≡ 3 (mod p³)  for all primes p ≥ 5.

Proof outline formalized mathematically:
1. S₂₀(p) = Σ_{k=0}^{p} C(p,k)⁴ · C(p+k,k)
2. For 1 ≤ k ≤ p-1, the binomial coefficient C(p,k) is divisible by p.
3. Therefore, C(p,k)⁴ is divisible by p⁴.
4. SAFE DENOMINATOR CHECK: The second factor is C(p+k,k) = (p+k)...(p+1) / k!.
   Since 1 ≤ k ≤ p-1, the denominator k! contains no factors of p. 
   Thus, the p⁴ factor from C(p,k)⁴ is perfectly preserved and not canceled.
5. Consequently, all intermediate terms strictly vanish modulo p⁴ (and mod p³).
6. We are left with the boundary terms at k=0 and k=p:
   - k=0: C(p,0)⁴ · C(p,0) = 1
   - k=p: C(p,p)⁴ · C(2p,p) = C(2p,p)
7. By Wolstenholme's theorem, for primes p ≥ 5, C(2p,p) ≡ 2 (mod p³).
8. Thus, S₂₀(p) ≡ 1 + 2 = 3 (mod p³).
-/

-- A basic step towards the formalization: p divides C(p,k) for 0 < k < p.
-- (This relies on Mathlib's Nat.Prime.dvd_choose)
lemma choose_dvd_of_prime {p k : ℕ} (hp : p.Prime) (hk0 : 0 < k) (hkp : k < p) :
    p ∣ Nat.choose p k := by
  apply Nat.Prime.dvd_choose hp hkp
  · omega
  · omega

-- Safe Denominator Formalization
-- We state that the factorial of k (for k < p) is not divisible by the prime p.
lemma not_dvd_factorial_of_lt {p k : ℕ} (hp : p.Prime) (hkp : k < p) :
    ¬ (p ∣ k.factorial) := by
  rw [Nat.Prime.dvd_factorial hp]
  omega

end Agora.Discovery.S20Seq
