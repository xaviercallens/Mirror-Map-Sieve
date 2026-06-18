import Mathlib

/-- The optimal difference basis discovered by the Z3 Oracle -/
def optimal_basis : Finset ℤ := {0, 2, 3, 4, 9, 10}

/-- The formal theorem that the Z3 witness covers all differences from 1 to 10 -/
theorem is_diff_basis : ∀ d ∈ Finset.Icc (1:ℤ) 10, ∃ x ∈ optimal_basis, ∃ y ∈ optimal_basis, x - y = d := by
  decide
