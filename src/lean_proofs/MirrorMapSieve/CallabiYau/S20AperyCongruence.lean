/-
  S₂₀ Apéry-style congruence (mod p) — Formal Lean 4 Verification
  ===============================================================

  The weight-5 Apéry-like sequence S₂₀(n) = Σ_{k=0}^{n} C(n,k)⁴ · C(n+k,k).

  This module formalizes the Apéry-style boundary congruence

      S₂₀(p-1) ≡ 1  (mod p)      for every prime p.

  ───────────────────────────────────────────────────────────────────────
  HONEST SCOPE STATEMENT (read me)
  ───────────────────────────────────────────────────────────────────────
  Numerically, the *stronger* statement S₂₀(p-1) ≡ 1 (mod p³) holds for all
  tested primes p ≥ 5 (see the reproducibility report). That mod-p³ refinement
  is a genuine open problem in this project and is NOT proved here.

  What IS proved here, with zero `sorry`/`admit`/custom-axiom, is the mod-p
  statement, whose mechanism is clean and complete:

  (1) For 1 ≤ k ≤ p-1 the companion binomial C(p-1+k, k) is divisible by p.
      Reason: writing C(p-1+k,k)·(k!·(p-1)!) = (p-1+k)!, the prime p divides
      the right-hand factorial (since p ≤ p-1+k) but divides neither k! nor
      (p-1)! (both arguments are < p). Hence p ∣ C(p-1+k, k).

  (2) Therefore every interior term C(p-1,k)⁴·C(p-1+k,k) vanishes mod p, and
      the sum collapses to its single boundary term at k = 0, which equals 1.

  This is the honest, fully-formal fragment of the Apéry-style congruence.

  Reference: "The Mirror Map Sieve", X. Callens, SocrateAI Lab, June 2026.
-/

import Mathlib

namespace MirrorMapSieve.CallabiYau.AperyCongruence

open Finset

/-- The summand of S₂₀: `T n k = C(n,k)⁴ · C(n+k,k)` (over ℕ). -/
def T (n k : ℕ) : ℕ := (Nat.choose n k) ^ 4 * (Nat.choose (n + k) k)

/-- The weight-5 Apéry-like sequence over ℕ. -/
def S20 (n : ℕ) : ℕ := ∑ k ∈ range (n + 1), T n k

/-- Sanity: agrees with the published first values. -/
example : S20 0 = 1 := by decide
example : S20 4 = 29751 := by decide

/-! ### Step (1): the companion binomial is divisible by p on the interior -/

/-- **Companion divisibility.** For a prime `p` and `1 ≤ k ≤ p-1`,
        `p ∣ C(p-1+k, k)`.
    Proof via the factorial identity `C(p-1+k,k)·k!·(p-1)! = (p-1+k)!`:
    `p` divides the right side (as `p ≤ p-1+k`) but neither `k!` nor `(p-1)!`
    (their arguments are `< p`), so `p` must divide the binomial. -/
theorem p_dvd_companion {p k : ℕ} (hp : p.Prime) (hk0 : k ≠ 0) (hkp : k < p) :
    p ∣ Nat.choose (p - 1 + k) k := by
  have hkle : k ≤ p - 1 + k := Nat.le_add_left k (p - 1)
  -- factorial identity (note (p-1+k) - k = p-1)
  have hid : Nat.choose (p - 1 + k) k * Nat.factorial k * Nat.factorial (p - 1 + k - k)
      = Nat.factorial (p - 1 + k) := Nat.choose_mul_factorial_mul_factorial hkle
  have hsub : p - 1 + k - k = p - 1 := by omega
  rw [hsub] at hid
  -- p divides (p-1+k)! since p ≤ p-1+k
  have hdvd_fact : p ∣ Nat.factorial (p - 1 + k) := (Nat.Prime.dvd_factorial hp).2 (by omega)
  -- rewrite the factorial as the product and push divisibility onto the binomial
  rw [← hid] at hdvd_fact
  -- p ∤ k!  (since k < p) and p ∤ (p-1)!  (since p-1 < p)
  have hnk : ¬ p ∣ Nat.factorial k := by
    rw [Nat.Prime.dvd_factorial hp]; omega
  have hnp1 : ¬ p ∣ Nat.factorial (p - 1) := by
    rw [Nat.Prime.dvd_factorial hp]; omega
  -- p divides (choose * k!) * (p-1)! ; strip (p-1)!, then strip k!
  have h1 : p ∣ Nat.choose (p - 1 + k) k * Nat.factorial k :=
    (hp.dvd_mul.mp hdvd_fact).resolve_right hnp1
  exact (hp.dvd_mul.mp h1).resolve_right hnk

/-! ### Step (2): the interior collapses mod p, leaving the boundary term 1 -/

/-- Each interior term `T (p-1) k`, for `1 ≤ k ≤ p-1`, is divisible by `p`. -/
theorem term_dvd_p {p k : ℕ} (hp : p.Prime) (hk0 : k ≠ 0) (hkp : k < p) :
    p ∣ T (p - 1) k := by
  have hp1 : 1 ≤ p := hp.one_lt.le
  -- T (p-1) k = C(p-1,k)⁴ · C((p-1)+k, k); the companion factor is divisible by p
  have hco : p ∣ Nat.choose (p - 1 + k) k := p_dvd_companion hp hk0 hkp
  exact Dvd.dvd.mul_left hco _

/-- The boundary term at `k = 0` equals `1`. -/
theorem T_zero (n : ℕ) : T n 0 = 1 := by
  simp [T, Nat.choose_zero_right]

/-- **Apéry-style congruence (mod p).** For every prime `p`,
        `S₂₀(p-1) ≡ 1  (mod p)`.
    The sum `S₂₀(p-1) = Σ_{k=0}^{p-1} T (p-1) k` splits as the `k=0` boundary
    term (`= 1`) plus an interior `Σ_{k=1}^{p-1}` block; by `term_dvd_p` the
    whole interior block is divisible by `p`. -/
theorem apery_congruence {p : ℕ} (hp : p.Prime) :
    (S20 (p - 1) : ℤ) ≡ 1 [ZMOD (p : ℤ)] := by
  have hp1 : 1 ≤ p := hp.one_lt.le
  -- range ((p-1)+1) = range p = insert 0 (Ioo 0 p) ... but here indices run 0..p-1.
  -- S20 (p-1) = Σ_{k ∈ range ((p-1)+1)} T (p-1) k, and (p-1)+1 = p.
  have hrng : (p - 1) + 1 = p := by omega
  -- split off k = 0
  have hsplit : S20 (p - 1) = 1 + ∑ k ∈ Ioo 0 p, T (p - 1) k := by
    unfold S20
    rw [hrng]
    have hins : range p = insert 0 (Ioo 0 p) := by
      ext x; simp only [mem_range, mem_insert, mem_Ioo]; omega
    rw [hins, Finset.sum_insert (by simp), T_zero]
  -- the interior block is divisible by p
  have hdvd : p ∣ ∑ k ∈ Ioo 0 p, T (p - 1) k := by
    apply dvd_sum
    intro k hk
    rw [mem_Ioo] at hk
    exact term_dvd_p hp (by omega) hk.2
  -- push to ℤ
  rw [Int.modEq_iff_dvd]
  have hZ : (1 : ℤ) - (S20 (p - 1) : ℤ) = - (∑ k ∈ Ioo 0 p, T (p - 1) k : ℤ) := by
    have : (S20 (p - 1) : ℤ) = 1 + (∑ k ∈ Ioo 0 p, T (p - 1) k : ℤ) := by
      rw [hsplit]; push_cast; ring
    rw [this]; ring
  rw [hZ, dvd_neg]
  exact_mod_cast hdvd

end MirrorMapSieve.CallabiYau.AperyCongruence
