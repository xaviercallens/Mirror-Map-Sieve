import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith

namespace Agora.AlienMath.Applications

-- Define a non-commutative ring (e.g., quaternions)
structure Quaternion where
  (a b c d : ℝ)

-- Define non-commutative multiplication
def quat_mul (q1 q2 : Quaternion) : Quaternion :=
  { a := q1.a * q2.a - q1.b * q2.b - q1.c * q2.c - q1.d * q2.d,
    b := q1.a * q2.b + q1.b * q2.a + q1.c * q2.d - q1.d * q2.c,
    c := q1.a * q2.c - q1.b * q2.d + q1.c * q2.a + q1.d * q2.b,
    d := q1.a * q2.d + q1.b * q2.c - q1.c * q2.b + q1.d * q2.a }

-- Theorem: Non-commutativity of quaternion multiplication
theorem quat_mul_non_commutative :
  ∃ q1 q2 : Quaternion, quat_mul q1 q2 ≠ quat_mul q2 q1 := by
  use ⟨0, 1, 0, 0⟩, ⟨0, 0, 1, 0⟩
  intro h
  have h_d : (quat_mul ⟨0, 1, 0, 0⟩ ⟨0, 0, 1, 0⟩).d = 1 := by norm_num [quat_mul]
  have h_d' : (quat_mul ⟨0, 0, 1, 0⟩ ⟨0, 1, 0, 0⟩).d = -1 := by norm_num [quat_mul]
  have h_eq : (quat_mul ⟨0, 1, 0, 0⟩ ⟨0, 0, 1, 0⟩).d = (quat_mul ⟨0, 0, 1, 0⟩ ⟨0, 1, 0, 0⟩).d := by rw [h]
  rw [h_d, h_d'] at h_eq
  linarith

end Agora.AlienMath.Applications
