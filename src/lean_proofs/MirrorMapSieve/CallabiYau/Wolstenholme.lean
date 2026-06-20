/-
  Towards Wolstenholme's Theorem — Formal Lean 4 development
  ===========================================================

  Goal: the classical congruence
        C(2p, p) ≡ 2  (mod p³)   for primes p ≥ 5,
  which is the one external input used by the S₂₀ cubic supercongruence
  (`S20Supercongruence.lean`). This theorem is NOT present in the Mathlib
  revision pinned by this project, so we develop it here.

  ───────────────────────────────────────────────────────────────────────
  HONEST STATUS (read me)
  ───────────────────────────────────────────────────────────────────────
  Fully proven here, with NO `sorry` / `admit` / custom axiom:

    • `centralBinom_eq_sum_sq` :  C(2p,p) = Σ_{k=0}^{p} C(p,k)²
        (Vandermonde / Chu–Vandermonde specialisation).

    • `babbage` :  C(2p,p) ≡ 2  (mod p²)   for every prime p.
        — UNCONDITIONAL.  This already upgrades the S₂₀ supercongruence to
          an unconditional statement modulo p² (see `S20Supercongruence`).

    • `choose_pred_eq_neg_one_pow` :  C(p-1, j) ≡ (-1)^j  (mod p)  for j < p.
        — the Pascal-induction lemma; a building block for the mod-p³ lift.

    • `sum_units_sq_eq_zero` :  Σ_{x ∈ (ZMod p)ˣ} x² = 0  for primes p ≥ 5.
        — the "harmonic core" (Σ 1/k² ≡ 0 mod p), obtained from
          `FiniteField.sum_pow_units`.

  These are exactly the three non-trivial ingredients of the standard proof
  of the full mod-p³ statement.

  ───────────────────────────────────────────────────────────────────────
  UPDATE (assembly complete).  The lifting step is now FORMALIZED:

    • `reduced_zmod` :  for `1 ≤ k < p`, writing `d = C(p,k)/p`,
          (d : ZMod p) = (k : ZMod p)⁻¹ · (-1)^(k-1).
        — the absorption identity `k·C(p,k) = p·C(p-1,k-1)` reduced mod p,
          using `choose_pred_eq_neg_one_pow`.

    • `sum_inv_sq_eq_zero` :  for `p ≥ 5`,
          Σ_{k=1}^{p-1} ((k : ZMod p)⁻¹)² = 0
        — the harmonic core, reindexed onto the full field and evaluated by
          `FiniteField.sum_pow_lt_card_sub_one`.

    • `wolstenholme` :  C(2p, p) ≡ 2 (mod p³)  for every prime `p ≥ 5`.
        — UNCONDITIONAL.  No `sorry`, no `admit`, no custom axiom.

  This closes the one external input of the S₂₀ cubic supercongruence, which
  is therefore now unconditional for `p ≥ 5` (see `S20Supercongruence`).

  Reference: "The Mirror Map Sieve", X. Callens, SocrateAI Lab, June 2026.
-/

import Mathlib

namespace MirrorMapSieve.CallabiYau.Wolstenholme

open Finset

/-! ### Vandermonde: the central binomial as a sum of squares -/

/-- `C(2p, p) = Σ_{k=0}^{p} C(p,k)²`. A specialisation of Vandermonde's
    identity `(m+n choose k) = Σ C(m,i)·C(n,k-i)` together with the symmetry
    `C(p, p-k) = C(p,k)`. -/
theorem centralBinom_eq_sum_sq (p : ℕ) :
    (2 * p).choose p = ∑ k ∈ range (p + 1), (p.choose k) ^ 2 := by
  have h := Nat.add_choose_eq p p p
  rw [two_mul, h, Finset.Nat.sum_antidiagonal_eq_sum_range_succ_mk]
  apply Finset.sum_congr rfl
  intro k hk
  rw [mem_range, Nat.lt_succ_iff] at hk
  rw [Nat.choose_symm hk, sq]

/-! ### Babbage's congruence: `C(2p,p) ≡ 2 (mod p²)` (unconditional) -/

/-- **Babbage's congruence.** For every prime `p`,
        `C(2p, p) ≡ 2  (mod p²)`.
    The interior terms `C(p,k)²` (for `1 ≤ k ≤ p-1`) are each divisible by
    `p²`, since `p ∣ C(p,k)`; only the two boundary terms `k = 0` and `k = p`
    survive, contributing `1 + 1 = 2`. This is unconditional (no `p ≥ 5`). -/
theorem babbage {p : ℕ} (hp : p.Prime) :
    ((2 * p).choose p : ℤ) ≡ 2 [ZMOD (p : ℤ) ^ 2] := by
  have hp1 : 1 ≤ p := hp.one_lt.le
  -- ℕ split:  C(2p,p) = 1 + (interior) + 1
  have hsplit : (2 * p).choose p
      = 1 + (∑ k ∈ Ioo 0 p, (p.choose k) ^ 2) + 1 := by
    rw [centralBinom_eq_sum_sq, Finset.sum_range_succ, Nat.choose_self, one_pow]
    have hrange : range p = insert 0 (Ioo 0 p) := by
      ext x; simp only [mem_range, mem_insert, mem_Ioo]; omega
    rw [hrange, Finset.sum_insert (by simp), Nat.choose_zero_right]
    ring
  rw [Int.modEq_iff_dvd]
  -- p² divides every interior square
  have hdvd : (p : ℤ) ^ 2 ∣ (∑ k ∈ Ioo 0 p, (p.choose k : ℤ) ^ 2) := by
    apply dvd_sum
    intro k hk
    rw [mem_Ioo] at hk
    have hd : p ∣ p.choose k := hp.dvd_choose_self (by omega) hk.2
    have hz : (p : ℤ) ∣ (p.choose k : ℤ) := by exact_mod_cast hd
    exact pow_dvd_pow_of_dvd hz 2
  have hcast : ((2 * p).choose p : ℤ)
      = 1 + (∑ k ∈ Ioo 0 p, (p.choose k : ℤ) ^ 2) + 1 := by
    rw [hsplit]; push_cast; ring
  have heq : (2 : ℤ) - ((2 * p).choose p : ℤ)
      = - (∑ k ∈ Ioo 0 p, (p.choose k : ℤ) ^ 2) := by
    rw [hcast]; ring
  rw [heq, dvd_neg]
  exact hdvd

/-! ### Building blocks for the mod-p³ lift -/

/-- **Pascal-induction lemma.** For a prime `p` and `j < p`,
        `C(p-1, j) ≡ (-1)^j  (mod p)`  (stated in `ZMod p`).
    Proof: induction on `j` using Pascal's rule
    `C(p, j+1) = C(p-1, j) + C(p-1, j+1)` together with `p ∣ C(p, j+1)`. -/
theorem choose_pred_eq_neg_one_pow {p : ℕ} (hp : p.Prime) :
    ∀ j, j < p → (((p - 1).choose j : ZMod p)) = (-1) ^ j := by
  have hp1 : 1 ≤ p := hp.one_lt.le
  have : NeZero p := ⟨by omega⟩
  intro j
  induction j with
  | zero => intro _; simp
  | succ n ih =>
    intro hn
    have hpascal : p.choose (n + 1) = (p - 1).choose n + (p - 1).choose (n + 1) := by
      have heq : (p - 1).succ = p := by omega
      have h := Nat.choose_succ_succ (p - 1) n
      rw [heq] at h; exact h
    have hdvd : p ∣ p.choose (n + 1) := hp.dvd_choose_self (by omega) hn
    have hzero : ((p.choose (n + 1)) : ZMod p) = 0 :=
      (ZMod.natCast_eq_zero_iff _ p).mpr hdvd
    rw [hpascal] at hzero; push_cast at hzero
    have ihn := ih (by omega)
    have hb : (((p - 1).choose (n + 1) : ZMod p)) = -(((p - 1).choose n : ZMod p)) :=
      eq_neg_of_add_eq_zero_right hzero
    rw [hb, ihn]; ring

/-- **Harmonic core.** For a prime `p ≥ 5`, the sum of squares over the
    multiplicative group vanishes:  `Σ_{x ∈ (ZMod p)ˣ} x² = 0`.
    This is `Σ 1/k² ≡ 0 (mod p)` in disguise (the squaring map is invariant
    under `x ↦ x⁻¹`, which permutes the units). It follows from
    `FiniteField.sum_pow_units` because `p - 1 ∤ 2` once `p ≥ 5`. -/
theorem sum_units_sq_eq_zero {p : ℕ} [Fact p.Prime] (h5 : 5 ≤ p) :
    ∑ x : (ZMod p)ˣ, ((x : ZMod p)) ^ 2 = 0 := by
  have hcard : Fintype.card (ZMod p) = p := ZMod.card p
  have hsum := FiniteField.sum_pow_units (ZMod p) 2
  rw [hcard] at hsum
  rw [hsum]
  have hnd : ¬ (p - 1 ∣ 2) := by
    intro hdvd
    have : p - 1 ≤ 2 := Nat.le_of_dvd (by norm_num) hdvd
    omega
  simp [hnd]

/-! ### The mod-p³ lift: assembling Wolstenholme's theorem -/

/-- **Reduced interior coefficient.** For a prime `p` and `1 ≤ k < p`, the
    binomial `C(p,k)` is divisible by `p`; write `d := C(p,k)/p` for the
    reduced coefficient. Then, in `ZMod p`,
        `d = k⁻¹ · (-1)^(k-1)`.
    Proof: the absorption identity `k · C(p,k) = p · C(p-1,k-1)` gives, after
    dividing by `p`, the integer relation `k · d = C(p-1,k-1)`; reducing mod p
    and using `choose_pred_eq_neg_one_pow` (`C(p-1,k-1) ≡ (-1)^(k-1)`) plus the
    invertibility of `k` in `ZMod p` yields the claim. -/
theorem reduced_zmod {p k : ℕ} (hp : p.Prime) (hk0 : k ≠ 0) (hkp : k < p) :
    ((p.choose k / p : ℕ) : ZMod p)
      = (k : ZMod p)⁻¹ * (-1) ^ (k - 1) := by
  have : Fact p.Prime := ⟨hp⟩
  -- p divides C(p,k)
  have hdvd : p ∣ p.choose k := hp.dvd_choose_self hk0 hkp
  -- the ℕ-level absorption identity, divided by p:  k * (C(p,k)/p) = C(p-1,k-1)
  -- start from  (n+1) * C(n,j) = C(n+1,j+1) * (j+1)  with n=p-1, j=k-1
  have hkpos : 1 ≤ k := Nat.one_le_iff_ne_zero.mpr hk0
  have hpsucc : (p - 1) + 1 = p := by omega
  have hksucc : (k - 1) + 1 = k := by omega
  have habs : p * (p - 1).choose (k - 1) = p.choose k * k := by
    have h := Nat.add_one_mul_choose_eq (p - 1) (k - 1)
    rw [hpsucc, hksucc] at h
    -- h : p * (p-1).choose (k-1) = p.choose k * k
    exact h
  -- divide both sides by p: with C(p,k) = p * d, get  d * k = C(p-1,k-1)
  obtain ⟨d, hd⟩ := hdvd
  have hdkey : (p - 1).choose (k - 1) = d * k := by
    have hp0 : p ≠ 0 := hp.pos.ne'
    have : p * (p - 1).choose (k - 1) = p * (d * k) := by
      rw [habs, hd]; ring
    exact Nat.eq_of_mul_eq_mul_left hp.pos this
  -- so C(p,k)/p = d
  have hdiv : p.choose k / p = d := by
    rw [hd, Nat.mul_div_cancel_left d hp.pos]
  rw [hdiv]
  -- reduce  d * k = C(p-1,k-1)  to ZMod p
  have hzmod : (d : ZMod p) * (k : ZMod p) = (-1) ^ (k - 1) := by
    have hcast : ((p - 1).choose (k - 1) : ZMod p) = (d : ZMod p) * (k : ZMod p) := by
      rw [hdkey]; push_cast; ring
    have hneg : (((p - 1).choose (k - 1) : ℕ) : ZMod p) = (-1) ^ (k - 1) :=
      choose_pred_eq_neg_one_pow hp (k - 1) (by omega)
    rw [← hcast]; exact hneg
  -- k is a unit in ZMod p, so solve for d
  have hkne : (k : ZMod p) ≠ 0 := by
    rw [Ne, ZMod.natCast_eq_zero_iff]
    intro hdvdk
    exact absurd (Nat.le_of_dvd (Nat.pos_of_ne_zero hk0) hdvdk) (not_le.mpr hkp)
  field_simp
  -- goal (up to commutativity):  (d : ZMod p) * k = (-1)^(k-1)
  linear_combination hzmod

/-- **Harmonic core, reduced form.** For a prime `p ≥ 5`,
        `Σ_{k=1}^{p-1} ((k : ZMod p)⁻¹)² = 0`.
    Reindex by `k ↦ (k : ZMod p)`: as `k` runs over `{1,…,p-1}` the residues
    `(k : ZMod p)` run over the nonzero elements of `ZMod p`, and `x ↦ x⁻¹`
    permutes those, so the sum equals `Σ_{x ≠ 0} x² = Σ_{x : ZMod p} x²`, which
    is `0` by `sum_pow_lt_card_sub_one` (since `2 < p - 1`). -/
theorem sum_inv_sq_eq_zero {p : ℕ} (hp : p.Prime) (h5 : 5 ≤ p) :
    ∑ k ∈ Ioo 0 p, ((k : ZMod p)⁻¹) ^ 2 = 0 := by
  have : Fact p.Prime := ⟨hp⟩
  classical
  -- Step 1: drop the inverse — squaring sum over nonzero residues is invariant
  -- under x ↦ x⁻¹.  First rewrite the indexed sum as a sum over ZMod p \ {0}.
  -- ∑_{k ∈ Ioo 0 p} f (k : ZMod p) = ∑_{x ∈ univ \ {0}} f x
  have hreindex : ∀ f : ZMod p → ZMod p,
      ∑ k ∈ Ioo 0 p, f (k : ZMod p) = ∑ x ∈ (univ \ {0} : Finset (ZMod p)), f x := by
    intro f
    refine Finset.sum_nbij' (i := fun k : ℕ => (k : ZMod p)) (j := fun x : ZMod p => x.val)
      ?_ ?_ ?_ ?_ ?_
    · -- maps Ioo 0 p into univ \ {0}
      intro k hk
      rw [mem_Ioo] at hk
      simp only [mem_sdiff, mem_univ, true_and, mem_singleton,
        ZMod.natCast_eq_zero_iff]
      intro hdvd
      exact absurd (Nat.le_of_dvd hk.1 hdvd) (not_le.mpr hk.2)
    · -- maps univ \ {0} into Ioo 0 p
      intro x hx
      simp only [mem_sdiff, mem_univ, true_and, mem_singleton] at hx
      rw [mem_Ioo]
      exact ⟨ZMod.val_pos.mpr hx, ZMod.val_lt x⟩
    · -- left inverse:  (k : ZMod p).val = k  for k < p
      intro k hk
      rw [mem_Ioo] at hk
      exact ZMod.val_natCast_of_lt hk.2
    · -- right inverse:  ((x.val : ℕ) : ZMod p) = x
      intro x _
      exact ZMod.natCast_zmod_val x
    · -- function values agree
      intro k _; rfl
  rw [hreindex (fun x => x⁻¹ ^ 2)]
  -- Step 2: x ↦ x⁻¹ is a bijection of univ \ {0}; reindex to drop the inverse
  have hbij : ∑ x ∈ (univ \ {0} : Finset (ZMod p)), (x⁻¹) ^ 2
            = ∑ x ∈ (univ \ {0} : Finset (ZMod p)), x ^ 2 := by
    refine Finset.sum_nbij' (i := fun x : ZMod p => x⁻¹) (j := fun x : ZMod p => x⁻¹)
      ?_ ?_ ?_ ?_ ?_
    · intro x hx
      simp only [mem_sdiff, mem_univ, true_and, mem_singleton] at hx ⊢
      exact inv_ne_zero hx
    · intro x hx
      simp only [mem_sdiff, mem_univ, true_and, mem_singleton] at hx ⊢
      exact inv_ne_zero hx
    · intro x _; exact inv_inv x
    · intro x _; exact inv_inv x
    · -- values:  (x⁻¹)^2 = (x⁻¹)^2   (g (i x) = (x⁻¹)^2)
      intro x _; rfl
  rw [hbij]
  -- Step 3: ∑_{x ≠ 0} x² = ∑_{x} x² (the x=0 term is 0), and that is 0.
  have hfull : ∑ x ∈ (univ \ {0} : Finset (ZMod p)), x ^ 2
             = ∑ x : ZMod p, x ^ 2 := by
    rw [eq_comm]
    rw [← Finset.sum_sdiff (Finset.subset_univ ({0} : Finset (ZMod p)))]
    simp
  rw [hfull]
  -- ∑_{x : ZMod p} x² = 0  since  2 < p - 1  (i.e. p ≥ 5)
  have hcard : Fintype.card (ZMod p) = p := ZMod.card p
  have := FiniteField.sum_pow_lt_card_sub_one (K := ZMod p) 2 (by rw [hcard]; omega)
  exact this

/-- **Wolstenholme's theorem.** For every prime `p ≥ 5`,
        `C(2p, p) ≡ 2  (mod p³)`.

    Proof. By `centralBinom_eq_sum_sq`, `C(2p,p) = Σ_{k=0}^{p} C(p,k)²`. The
    boundary terms `k = 0, p` contribute `1 + 1 = 2`. For each interior
    `1 ≤ k ≤ p-1` write `C(p,k) = p · dₖ`; then `C(p,k)² = p² · dₖ²`, so
        `C(2p,p) - 2 = p² · Σ_{k=1}^{p-1} dₖ²`.
    It remains to show `p ∣ Σ dₖ²`. By `reduced_zmod`, `dₖ ≡ k⁻¹·(-1)^(k-1)`
    in `ZMod p`, hence `dₖ² ≡ (k⁻¹)²`, and `Σ (k⁻¹)² = 0` by
    `sum_inv_sq_eq_zero`. Therefore `p ∣ Σ dₖ²`, giving `p³ ∣ C(2p,p) - 2`.

    Fully kernel-checked: no `sorry`, no `admit`, no custom axiom. -/
theorem wolstenholme {p : ℕ} (hp : p.Prime) (h5 : 5 ≤ p) :
    ((2 * p).choose p : ℤ) ≡ 2 [ZMOD (p : ℤ) ^ 3] := by
  have : Fact p.Prime := ⟨hp⟩
  have hp1 : 1 ≤ p := hp.one_lt.le
  -- abbreviation for the reduced interior coefficient
  set d : ℕ → ℕ := fun k => p.choose k / p with hd_def
  -- For interior k, C(p,k) = p * d k
  have hCpk : ∀ k, k ≠ 0 → k < p → p.choose k = p * d k := by
    intro k hk0 hkp
    obtain ⟨c, hc⟩ := hp.dvd_choose_self hk0 hkp
    simp only [hd_def, hc, Nat.mul_div_cancel_left c hp.pos]
  -- ℕ split of the central binomial:  C(2p,p) = 1 + (interior) + 1
  have hsplit : (2 * p).choose p
      = 1 + (∑ k ∈ Ioo 0 p, (p.choose k) ^ 2) + 1 := by
    rw [centralBinom_eq_sum_sq, Finset.sum_range_succ, Nat.choose_self, one_pow]
    have hrange : range p = insert 0 (Ioo 0 p) := by
      ext x; simp only [mem_range, mem_insert, mem_Ioo]; omega
    rw [hrange, Finset.sum_insert (by simp), Nat.choose_zero_right]
    ring
  -- the interior sum equals p² * Σ (d k)²
  have hinterior : (∑ k ∈ Ioo 0 p, (p.choose k) ^ 2)
      = p ^ 2 * (∑ k ∈ Ioo 0 p, (d k) ^ 2) := by
    rw [Finset.mul_sum]
    apply Finset.sum_congr rfl
    intro k hk
    rw [mem_Ioo] at hk
    rw [hCpk k (by omega) hk.2]
    ring
  -- push the congruence to ℤ:  p³ ∣ C(2p,p) - 2  ⟺  p ∣ Σ (d k)²
  rw [Int.modEq_iff_dvd]
  -- (2 : ℤ) - C(2p,p) = - p² * Σ (d k)²
  have hZcast : ((2 * p).choose p : ℤ)
      = 1 + (p : ℤ) ^ 2 * (∑ k ∈ Ioo 0 p, (d k : ℤ) ^ 2) + 1 := by
    have : ((2 * p).choose p : ℤ)
        = 1 + ((∑ k ∈ Ioo 0 p, (p.choose k) ^ 2 : ℕ) : ℤ) + 1 := by
      rw [hsplit]; push_cast; ring
    rw [this, hinterior]; push_cast; ring
  have heq : (2 : ℤ) - ((2 * p).choose p : ℤ)
      = - ((p : ℤ) ^ 2 * (∑ k ∈ Ioo 0 p, (d k : ℤ) ^ 2)) := by
    rw [hZcast]; ring
  rw [heq, dvd_neg]
  -- p³ ∣ p² * S  ⟺  p ∣ S
  have hps : p ∣ (∑ k ∈ Ioo 0 p, (d k) ^ 2) := by
    -- reduce mod p: in ZMod p the sum is Σ (k⁻¹)² = 0
    rw [← ZMod.natCast_eq_zero_iff]
    push_cast
    have hcong : (∑ k ∈ Ioo 0 p, ((d k : ZMod p)) ^ 2)
               = ∑ k ∈ Ioo 0 p, ((k : ZMod p)⁻¹) ^ 2 := by
      apply Finset.sum_congr rfl
      intro k hk
      rw [mem_Ioo] at hk
      rw [reduced_zmod hp (by omega) hk.2]
      rw [mul_pow]
      have : ((-1 : ZMod p) ^ (k - 1)) ^ 2 = 1 := by
        rw [← pow_mul, mul_comm, pow_mul]
        simp
      rw [this, mul_one]
    rw [hcong]
    exact sum_inv_sq_eq_zero hp h5
  -- conclude p³ ∣ p² * S from p ∣ S
  obtain ⟨S, hS⟩ := hps
  -- rewrite the ℤ-sum via the ℕ-divisibility fact
  have hZsum : (∑ k ∈ Ioo 0 p, (d k : ℤ) ^ 2) = (p : ℤ) * S := by
    have : ((∑ k ∈ Ioo 0 p, (d k) ^ 2 : ℕ) : ℤ) = ((p * S : ℕ) : ℤ) := by rw [hS]
    push_cast at this ⊢
    linarith [this]
  rw [hZsum]
  -- goal:  p³ ∣ p² * (p * S)
  exact ⟨(S : ℤ), by ring⟩

end MirrorMapSieve.CallabiYau.Wolstenholme
