import Mathlib.Tactic
import Mathlib.Data.Real.Basic

/-!
# Non-Commutative Algebra — Quaternion Non-Commutativity

This module defines a quaternion-like non-commutative algebra over the Reals,
and formally verifies that multiplication is non-commutative using an explicit
counterexample (the quaternion basis vectors i and j).

## Peer Review Transparency (v3.0.1)

> **AI Peer Review Finding (Gemini 2.5 Pro, 2026-06-11):**
> - The proof of `quat_mul_non_commutative` is GENUINE and mathematically
>   meaningful: it constructs a concrete counterexample (i, j) and derives
>   a contradiction (1 = -1) from the assumption of commutativity.
> - The module title "Non-Commutative Cryptography" is an OVERSTATEMENT.
>   Proving `i*j ≠ j*i` is a basic algebraic fact, not a cryptographic
>   primitive. No hardness assumptions, key exchange protocols, or
>   security properties are defined or proven.

## What IS Formally Verified

- Hamilton's quaternion multiplication is correctly defined.
- Quaternion multiplication is non-commutative (∃ q₁ q₂, q₁*q₂ ≠ q₂*q₁).
- The proof uses a constructive counterexample with `norm_num`.

## What Is NOT Formally Verified

- Any cryptographic security property.
- Hardness of the conjugacy search problem.
- Key exchange correctness or security.
-/

/-- A Non-Commutative Ring element (e.g., Quaternion) over the Reals -/
structure AlienQuaternion where
  a : ℝ
  b : ℝ
  c : ℝ
  d : ℝ

/-- Hamilton's non-commutative multiplication rule -/
def quat_mul (q1 q2 : AlienQuaternion) : AlienQuaternion :=
  { a := q1.a * q2.a - q1.b * q2.b - q1.c * q2.c - q1.d * q2.d,
    b := q1.a * q2.b + q1.b * q2.a + q1.c * q2.d - q1.d * q2.c,
    c := q1.a * q2.c - q1.b * q2.d + q1.c * q2.a + q1.d * q2.b,
    d := q1.a * q2.d + q1.b * q2.c - q1.c * q2.b + q1.d * q2.a }

/-- Theorem: The alien multiplication is strictly non-commutative. -/
theorem quat_mul_non_commutative :
  ∃ (q1 q2 : AlienQuaternion), quat_mul q1 q2 ≠ quat_mul q2 q1 := by
  -- We instantiate the classic i and j basis vectors as our counterexample
  let i : AlienQuaternion := ⟨0, 1, 0, 0⟩
  let j : AlienQuaternion := ⟨0, 0, 1, 0⟩
  use i, j
  -- Assume they commute, and derive a contradiction
  intro h
  -- Extract the 'd' component (k basis) which should flip signs
  have h_eq : (quat_mul i j).d = (quat_mul j i).d := by rw [h]
  -- Compute the fields directly
  have h_ij : (quat_mul i j).d = 1 := by 
    dsimp [quat_mul, i, j]
    norm_num
  have h_ji : (quat_mul j i).d = -1 := by 
    dsimp [quat_mul, i, j]
    norm_num
  -- Substitute back into the assumed equality
  rw [h_ij, h_ji] at h_eq
  -- Derive 1 = -1 contradiction
  norm_num at h_eq
