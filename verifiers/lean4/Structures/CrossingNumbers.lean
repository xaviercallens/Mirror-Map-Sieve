import Mathlib.Data.Nat.Choose.Basic
import Mathlib.Order.Monotone.Basic
import Mathlib.Tactic

open Real Set Filter MeasureTheory Topology

-- We postulate the existence of the crossing number function for the complete graph K_n.
opaque cr_K (n : ℕ) : ℕ

-- Postulate a basic, known property that cr_K is non-decreasing.
axiom cr_K_mono : Monotone cr_K

-- Axiom 1 (Crossing Sub-drawings & Double Counting):
-- In any drawing of K_{n+1}, each crossing involves exactly 4 vertices.
-- Thus, a crossing appears in exactly choose((n+1)-4, n-4) = n-3 sub-drawings of size n.
axiom crossing_double_counting_bound (n : ℕ) (hn : n ≥ 4) :
  (n + 1) * cr_K n ≤ (n - 3) * cr_K (n + 1)

/-- The conjectured incremental lower bound for `cr(K_{n+1}) - cr(K_n)`.
This value is equivalent to `Z(n+1) - Z(n)`, where `Z` is the conjectured
formula for `cr(K_n)`. -/
def incremental_crossing_lower_bound (n : ℕ) : ℕ :=
  (Nat.choose (n / 2) 2) * ((n - 1) / 2)

/--
This conjecture states that the crossing number of the complete graph satisfies
a sharp inductive inequality. If true, it implies the conjectured formula for `cr(K_n)`.
-/
axiom crossing_number_kn_conjecture (n : ℕ) (hn : n ≥ 3) :
  cr_K (n + 1) ≥ cr_K n + incremental_crossing_lower_bound n
