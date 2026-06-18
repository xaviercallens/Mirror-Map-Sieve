import Mathlib
-- SymBrain v16 Offline Sorry Solver — HorizonMath
-- Problem:   diff_basis_optimal_10000
-- Domain:    combinatorics
-- Generated: 2026-06-04 09:35 UTC
-- v14 Status: REFUTED | Sorry before: 0 | After v16: 0
-- H1 Lemma slots: 3 | Resolved: 0/0
-- Stored in Alexandrie (ArtifactType.PROOF, RoomType.OPEN_ACCESS)
--
-- Mathematical Conjecture:
-- Let $S \\subset \\mathbb{Z}$ be a finite set. Define the set of positive differences as $D(S) := \\{ s_i - s_j \\mid s_i, s_j \\in S, s_i > s_j \\}$. Define the contiguous range covered by these differences as $n(S) := \\sup \\{ n \\in \\mathbb{N} \\cup \\{0\\} \\mid \\{1, 2, \\dots, n\\} \\subseteq

-- import Mathlib.Tactic
-- import Mathlib.Analysis.SpecialFunctions.Integrals
-- import Mathlib.NumberTheory.ArithmeticFunction
-- import Mathlib.Topology.Algebra.Order.LiminfLimsup

open Real Set Filter MeasureTheory Topology

/-
  v16 Lemma Pre-Decomposition Plan (H1):
  [1] diff_basis_optimal_1_sub1 (MEDIUM): Count the relevant combinatorial objects via bijection
       Tactics: Fintype.card_eq_of_equiv, Finset.card_image_of_injOn
  [2] diff_basis_optimal_1_sub2 (MEDIUM): Verify the extremal bound via double-counting
       Tactics: Finset.sum_le_sum, Nat.choose_le_choose
  [3] diff_basis_optimal_1_sub3 (EASY): Establish the recurrence / generating function identity
       Tactics: ring, norm_num, simp [Finset.sum_cons]
-/


/-!
## v14 Original Sketch (preserved for reference)
-- import Mathlib.Data.Finset.Pointwise
-- import Mathlib.Data.Finset.Card
-- import Mathlib.Tactic

-- Let S be a finite set of integers
variable (S : Finset ℤ)

-- The set of positive differences of S
def positive_differences (S : Finset ℤ) : Finset ℤ := 
  Finset.image (fun p : ℤ × ℤ ↦ p.2 - p.1) (S.offDiag.filter (fun p ↦ p.1 < p.2))

-- The length of the initial segment of integers covered by the differences of S
-- We search up to a loose bound Nat.choose S.card 2, the max possible number of positi
-/

/-!
## v16 Enriched Sketch (offline tactic substitutions applied)
-/

-- import Mathlib.Data.Finset.Pointwise
-- import Mathlib.Data.Finset.Card
-- import Mathlib.Tactic

-- Let S be a finite set of integers
variable (S : Finset ℤ)

-- The set of positive differences of S
def positive_differences (S : Finset ℤ) : Finset ℤ := 
  Finset.image (fun p : ℤ × ℤ ↦ p.2 - p.1) (S.offDiag.filter (fun p ↦ p.1 < p.2))

-- The length of the initial segment of integers covered by the differences of S
-- We search up to a loose bound Nat.choose S.card 2, the max possible number of positive diffs
def n (S : Finset ℤ) : ℕ :=
  if h : S.card < 2 then 0
  else Nat.findGreatest 
    (fun m ↦ Finset.Icc 1 m ⊆ Finset.map ⟨Int.natAbs, Int.natAbs_injective⟩ (positive_differences S)) 
    (Nat.choose S.card 2)

-- A set S is an optimal difference basis
def IsOptimalDifferenceBasis (S : Finset ℤ) : Prop :=
  ∀ (S' : Finset ℤ), S'.card = S.card → n S' ≤ n S

-- This is the main conjecture to be proven.
-- It states the existence of a restricted difference basis for n=10000
-- with a cardinality smaller than the current best known of 174.
theorem diff_basis_optimal_10000_conjecture :
  ∃ (B : Finset ℤ),
    -- The elements of the basis must be within the specified range {0, ..., 9999}
    (∀ b ∈ B, b ∈ Finset.Icc (0 : ℤ) 9999) ∧
    -- The size of the basis must be less than 174
    B.card < 174 ∧
    -- Every integer from 1 to 9999 must be a difference of two elements in the basis
    (Finset.Icc (1 : ℤ) 9999) ⊆ positive_differences B := by
  sorry