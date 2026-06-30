/-
  S₂₀ Recurrence Proof — Inductive Step Template
  ==================================================================
  This file provides a structured Lean 4 template for the inductive step of the 
  order-4 linear recurrence proof for S₂₀(n) via creative telescoping.

  Mathematical Context:
    Summand:     T(n, k) = (n! / (k! (n-k)!))^4 * ((n+k)! / (k! n!))
    Sequence:    S₂₀(n) = ∑_{k=0}^{n} T(n, k)
    Recurrence:  ∑_{j=0}^{4} P_j(n) * S₂₀(n+j) = 0
    Certificate: R(n, k) is a rational function in n and k such that:
                 ∑_{j=0}^{4} P_j(n) * T(n+j, k) = Δ_k [ R(n, k) * T(n, k) ]
                 where Δ_k g(k) = g(k+1) - g(k) is the forward difference.

  This template formalizes the sum manipulation, boundary term vanishing, 
  and interchanging of summations that bridges the local term identity 
  with the global sequence recurrence.
-/

import Mathlib

open BigOperators

namespace S20RecurrenceTemplate

-- 1. Represent the S₂₀ polynomial coefficients of the order-4 recurrence
variable (P₀ P₁ P₂ P₃ P₄ : ℕ → ℤ)

-- 2. Represent the summand T(n, k) embedded as a real function for analysis
variable (T : ℕ → ℕ → ℝ)

-- Summand support condition: T(n, k) = 0 for k > n
def SummandSupport : Prop :=
  ∀ n k, k > n → T n k = 0

-- 3. Definition of the S₂₀ sequence as a finite sum
noncomputable def S20 (n : ℕ) : ℝ :=
  ∑ k ∈ Finset.range (n + 1), T n k

-- 4. The rational certificate R(n, k)
variable (R : ℕ → ℕ → ℝ)

-- 5. Creative Telescoping Local Identity (certified by Maxima's Zeilberger)
def CreativeTelescopingIdentity : Prop :=
  ∀ n k, 
    P₀ n * T n k + 
    P₁ n * T (n + 1) k + 
    P₂ n * T (n + 2) k + 
    P₃ n * T (n + 3) k + 
    P₄ n * T (n + 4) k = 
    R n (k + 1) * T n (k + 1) - R n k * T n k

-- Boundary conditions for the certificate: R(n, 0) * T(n, 0) = 0 and R(n, n+5) * T(n, n+5) = 0
def BoundaryConditions : Prop :=
  ∀ n, R n 0 * T n 0 = 0 ∧ R n (n + 5) * T n (n + 5) = 0

/--
  The Inductive Step Theorem Template:
  If the creative telescoping identity holds locally and the boundary terms vanish,
  then the global S₂₀ sequence satisfies the order-4 recurrence.
-/
theorem s20_recurrence_step
    (h_support : SummandSupport T)
    (h_ident : CreativeTelescopingIdentity P₀ P₁ P₂ P₃ P₄ T R)
    (h_boundary : BoundaryConditions T R)
    (n : ℕ) :
    P₀ n * S20 T n + 
    P₁ n * S20 T (n + 1) + 
    P₂ n * S20 T (n + 2) + 
    P₃ n * S20 T (n + 3) + 
    P₄ n * S20 T (n + 4) = 0 := by
  
  -- Unfold the sequence definitions to represent them as sums up to (n + 4)
  unfold S20
  
  -- Step 1: Extend all summations to Finset.range (n + 5) using the support condition
  have h_extend_0 : ∑ k ∈ Finset.range (n + 1), T n k = ∑ k ∈ Finset.range (n + 5), T n k := by
    apply Finset.sum_subset
    · intro x hx
      rw [Finset.mem_range] at hx ⊢
      omega
    · intro x hx hnx
      rw [Finset.mem_range] at hx hnx
      have : x > n := by omega
      exact h_support n x this

  have h_extend_1 : ∑ k ∈ Finset.range (n + 2), T (n + 1) k = ∑ k ∈ Finset.range (n + 5), T (n + 1) k := by
    apply Finset.sum_subset
    · intro x hx
      rw [Finset.mem_range] at hx ⊢
      omega
    · intro x hx hnx
      rw [Finset.mem_range] at hx hnx
      have : x > n + 1 := by omega
      exact h_support (n + 1) x this

  have h_extend_2 : ∑ k ∈ Finset.range (n + 3), T (n + 2) k = ∑ k ∈ Finset.range (n + 5), T (n + 2) k := by
    apply Finset.sum_subset
    · intro x hx
      rw [Finset.mem_range] at hx ⊢
      omega
    · intro x hx hnx
      rw [Finset.mem_range] at hx hnx
      have : x > n + 2 := by omega
      exact h_support (n + 2) x this

  have h_extend_3 : ∑ k ∈ Finset.range (n + 4), T (n + 3) k = ∑ k ∈ Finset.range (n + 5), T (n + 3) k := by
    apply Finset.sum_subset
    · intro x hx
      rw [Finset.mem_range] at hx ⊢
      omega
    · intro x hx hnx
      rw [Finset.mem_range] at hx hnx
      have : x > n + 3 := by omega
      exact h_support (n + 3) x this

  -- Rewrite the main recurrence using the extended summations
  rw [h_extend_0, h_extend_1, h_extend_2, h_extend_3]
  
  -- Step 2: Push the scalar coefficient P_j(n) inside each summation
  -- (Use linearity of sums to combine into a single summation over Finset.range (n + 5))
  have h_combine : 
    P₀ n * ∑ k ∈ Finset.range (n + 5), T n k +
    P₁ n * ∑ k ∈ Finset.range (n + 5), T (n + 1) k +
    P₂ n * ∑ k ∈ Finset.range (n + 5), T (n + 2) k +
    P₃ n * ∑ k ∈ Finset.range (n + 5), T (n + 3) k +
    P₄ n * ∑ k ∈ Finset.range (n + 5), T (n + 4) k =
    ∑ k ∈ Finset.range (n + 5), (
      P₀ n * T n k + 
      P₁ n * T (n + 1) k + 
      P₂ n * T (n + 2) k + 
      P₃ n * T (n + 3) k + 
      P₄ n * T (n + 4) k
    ) := by
    simp_rw [Finset.mul_sum]
    rw [← Finset.sum_add_distrib, ← Finset.sum_add_distrib, ← Finset.sum_add_distrib, ← Finset.sum_add_distrib]

  rw [h_combine]

  -- Step 3: Apply the Creative Telescoping local identity term-by-term
  have h_apply_id : 
    (∑ k ∈ Finset.range (n + 5), (
      P₀ n * T n k + 
      P₁ n * T (n + 1) k + 
      P₂ n * T (n + 2) k + 
      P₃ n * T (n + 3) k + 
      P₄ n * T (n + 4) k
    )) = 
    ∑ k ∈ Finset.range (n + 5), (R n (k + 1) * T n (k + 1) - R n k * T n k) := by
    apply Finset.sum_congr rfl
    intro k _
    exact h_ident n k

  rw [h_apply_id]

  -- Step 4: Telescope the RHS summation
  have h_telescope : 
    ∑ k ∈ Finset.range (n + 5), (R n (k + 1) * T n (k + 1) - R n k * T n k) = 
    R n (n + 5) * T n (n + 5) - R n 0 * T n 0 := by
    -- Proved using the standard telescoping sum lemma in Mathlib (sum_range_succ_sub)
    exact Finset.sum_range_sub (fun k => R n k * T n k) (n + 5)

  rw [h_telescope]

  -- Step 5: Apply boundary conditions to collapse the difference to 0
  have h_bound_vals := h_boundary n
  rcases h_bound_vals with ⟨h_left, h_right⟩
  rw [h_right, h_left, sub_self]

end S20RecurrenceTemplate
