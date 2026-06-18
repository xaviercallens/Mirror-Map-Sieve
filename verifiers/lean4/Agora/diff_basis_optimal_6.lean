import Mathlib.Data.Finset.Pointwise
import Mathlib.Data.Finset.Card
import Mathlib.Tactic

-- The set of positive differences of S
def positive_differences (S : Finset ℤ) : Finset ℤ := 
  Finset.image (fun p : ℤ × ℤ ↦ p.2 - p.1) (S.offDiag.filter (fun p ↦ p.1 < p.2))

-- The result returned by our Z3 oracle (scripts/solve_diff_basis_z3.py 6 4)
def optimal_basis_6 : Finset ℤ := {0, 2, 5, 6}

theorem diff_basis_optimal_6_conjecture :
  ∃ (B : Finset ℤ),
    (∀ b ∈ B, b ∈ Finset.Icc (0 : ℤ) 6) ∧
    B.card < 5 ∧
    (Finset.Icc (1 : ℤ) 6) ⊆ positive_differences B := by
  use optimal_basis_6
  decide
