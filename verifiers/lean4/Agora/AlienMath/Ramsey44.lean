import Mathlib.Data.Finset.Basic
import Mathlib.Data.Fintype.Basic
import Mathlib.Tactic

namespace Agora.AlienMath

/-- The non-zero quadratic residues modulo 17. -/
def Q17 : List (Fin 17) := [1, 2, 4, 8, 9, 13, 15, 16]

/-- The Paley graph of order 17 coloring.
    Returns true if the edge (u, v) is in the Paley graph. -/
def paleyColor (u v : Fin 17) : Bool :=
  if u = v then false
  else (u - v) ∈ Q17

/-- The complement of the Paley graph of order 17. -/
def paleyColorComp (u v : Fin 17) : Bool :=
  if u = v then false
  else !paleyColor u v

/-- A naive decider for the existence of a K_4 in a given graph coloring.
    It checks all strictly increasing 4-tuples of vertices.
    Since 17 choose 4 is 2380, this is extremely fast to evaluate by `decide`. -/
def hasClique4 (color : Fin 17 → Fin 17 → Bool) : Bool :=
  let V := List.finRange 17
  V.any fun v1 =>
    V.any fun v2 =>
      if v1 ≥ v2 then false else
      V.any fun v3 =>
        if v2 ≥ v3 then false else
        V.any fun v4 =>
          if v3 ≥ v4 then false else
          color v1 v2 && color v1 v3 && color v1 v4 &&
          color v2 v3 && color v2 v4 && color v3 v4

/-- Proof that the Paley graph of order 17 has no K_4. -/
theorem paley_no_clique4 : hasClique4 paleyColor = false := by decide

/-- Proof that the complement of the Paley graph of order 17 has no K_4. -/
theorem paley_comp_no_clique4 : hasClique4 paleyColorComp = false := by decide

end Agora.AlienMath
