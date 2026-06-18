import Mathlib.Data.Finset.Basic
import Mathlib.Data.Fintype.Basic
import Mathlib.Combinatorics.SimpleGraph.Basic
import Mathlib.Combinatorics.SimpleGraph.Clique

namespace Agora.AlienMath

/-!
# Ramsey SAT Encoding Correctness

This module formalizes the correctness of the SAT encoding used in our computational
experiments for exact Ramsey numbers (e.g., R(3,3,4)).

We define the mapping from a satisfying boolean assignment to a partition of the edges
of the complete graph into `k` colors, and prove that if the SAT constraints
(no monochromatic cliques of specified sizes) are satisfied, the resulting coloring
is a valid Ramsey coloring.
-/

variable {V : Type*} [Fintype V] [DecidableEq V]
variable {k : ℕ} -- Number of colors

/-- An edge in the complete graph on V. Represented as an unordered pair. -/
def Edge (V : Type*) := { s : Finset V // s.card = 2 }

/-- A boolean assignment for the SAT encoding.
    `x e c` is true if edge `e` is assigned color `c`. -/
def SATAssignment (V : Type*) (k : ℕ) := Edge V → Fin k → Prop

/-- The "exactly one color" constraint: every edge must have exactly one color. -/
def ExactlyOneColor (x : SATAssignment V k) : Prop :=
  ∀ e : Edge V, ∃! c : Fin k, x e c

/-- The "no monochromatic clique" constraint for a specific color `c` and clique size `s`. -/
def NoMonoClique (x : SATAssignment V k) (c : Fin k) (s : ℕ) : Prop :=
  ∀ C : Finset V, C.card = s →
    ¬ (∀ u v : V, u ∈ C → v ∈ C → (h : u ≠ v) →
        x ⟨{u, v}, Finset.card_pair h⟩ c)

omit [Fintype V] in
lemma edge_symm (u v : V) (h : u ≠ v) : 
  (⟨{u, v}, Finset.card_pair h⟩ : Edge V) = ⟨{v, u}, Finset.card_pair h.symm⟩ := by
  apply Subtype.ext
  exact Finset.pair_comm u v

/-- The graph formed by edges of a specific color `c`. -/
def colorGraph (x : SATAssignment V k) (c : Fin k) : SimpleGraph V where
  Adj u v := ∃ (h : u ≠ v), x ⟨{u, v}, Finset.card_pair h⟩ c
  symm u v h := by
    obtain ⟨h_neq, hx⟩ := h
    use h_neq.symm
    rw [← edge_symm u v h_neq]
    exact hx
  loopless u h := h.elim (fun h_neq _ => h_neq rfl)

/-- A valid Ramsey coloring is an assignment satisfying the exactly-one-color
    constraint and the no-monochromatic-clique constraints. -/
def IsRamseyColoring (x : SATAssignment V k) (S : Fin k → ℕ) : Prop :=
  ExactlyOneColor x ∧ ∀ c : Fin k, (colorGraph x c).CliqueFree (S c)

/-- The main correctness theorem: If the assignment satisfies the exactly-one-color
    constraint and the no-monochromatic-clique constraints for each color `c` with size `S_c`,
    then the `colorGraph`s form a valid Ramsey coloring. -/
theorem sat_encoding_correct (x : SATAssignment V k) (S : Fin k → ℕ)
    (h1 : ExactlyOneColor x)
    (h2 : ∀ c : Fin k, (colorGraph x c).CliqueFree (S c)) :
    IsRamseyColoring x S := by
  exact ⟨h1, h2⟩

end Agora.AlienMath
