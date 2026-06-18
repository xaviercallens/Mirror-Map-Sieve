import Mathlib
-- import Mathlib.Tactic
-- import Mathlib.Analysis.SpecialFunctions.Integrals
-- import Mathlib.NumberTheory.ArithmeticFunction
-- import Mathlib.Topology.Algebra.Order.LiminfLimsup

open Real Set Filter MeasureTheory Topology

/-
  v16 Lemma Pre-Decomposition Plan (H1):
  [1] schur_6_sub1 (MEDIUM): Count the relevant combinatorial objects via bijection
       Tactics: Fintype.card_eq_of_equiv, Finset.card_image_of_injOn
  [2] schur_6_sub2 (MEDIUM): Verify the extremal bound via double-counting
       Tactics: Finset.sum_le_sum, Nat.choose_le_choose
  [3] schur_6_sub3 (EASY): Establish the recurrence / generating function identity
       Tactics: ring, norm_num, simp [Finset.sum_cons]
-/


/-!
## v14 Original Sketch (preserved for reference)
-- import Mathlib.Analysis.Asymptotics.Asymptotics
-- import Mathlib.Data.Finset.Card
-- import Mathlib.Data.Nat.Basic
-- import Mathlib.Tactic

open Finset Asymptotics Filter
open scoped BigOperators Nat

/-- A finite set of natural numbers `S` has a Schur-6 solution if there exist
    elements (not necessarily distinct) `x, y, z, a, b, c` in `S` such that `x+y+z = a+b+c`. -/
def HasSchur6Solution (S : Finset ℕ) : Prop := 
  ∃ x y z a b c, x ∈ S ∧ y ∈ S ∧ z ∈ S ∧ a ∈ S ∧ b ∈ S ∧ c ∈ S ∧ x + y + z = a + b +
-/

/-!
## v16 Enriched Sketch (offline tactic substitutions applied)
-/

-- import Mathlib.Analysis.Asymptotics.Asymptotics
-- import Mathlib.Data.Finset.Card
-- import Mathlib.Data.Nat.Basic
-- import Mathlib.Tactic

open Finset Asymptotics Filter
open scoped BigOperators Nat

/-- A finite set of natural numbers `S` has a Schur-6 solution if there exist
    elements (not necessarily distinct) `x, y, z, a, b, c` in `S` such that `x+y+z = a+b+c`. -/
def HasSchur6Solution (S : Finset ℕ) : Prop := 
  ∃ x y z a b c, x ∈ S ∧ y ∈ S ∧ z ∈ S ∧ a ∈ S ∧ b ∈ S ∧ c ∈ S ∧ x + y + z = a + b + c

/-- The Schur-6 number for `c` colors, `Schur6Number c`, is the smallest `n` such that any
    `c`-coloring of `{1, ..., n}` admits a monochromatic Schur-6 solution. -/
noncomputable def Schur6Number (c : ℕ) : ℕ :=
  if c = 0 then 0 else sInf { n : ℕ | n > 0 ∧ ∀ f : (Icc 1 n) → (Fin c),
    ∃ i : Fin c,
    ∃ x y z a b c : ℕ,
      x ∈ Icc 1 n ∧ y ∈ Icc 1 n ∧ z ∈ Icc 1 n ∧
      a ∈ Icc 1 n ∧ b ∈ Icc 1 n ∧ c ∈ Icc 1 n ∧
      f x = i ∧ f y = i ∧ f z = i ∧
      f a = i ∧ f b = i ∧ f c = i ∧
      x + y + z = a + b + c
  }