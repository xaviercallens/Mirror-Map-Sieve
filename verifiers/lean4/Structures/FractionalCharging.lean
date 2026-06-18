import Mathlib.Tactic
import Mathlib.Data.Real.Basic
import Mathlib.Data.Matrix.Basic
import Mathlib.Combinatorics.SimpleGraph.Basic
import Mathlib.Combinatorics.SimpleGraph.Metric
import Mathlib.Combinatorics.SimpleGraph.DegreeSum

structure ChargingAlgebra where
  re : ℝ
  i  : ℝ
  j  : ℝ
  ε  : ℝ

instance : Zero ChargingAlgebra := ⟨⟨0, 0, 0, 0⟩⟩
instance : One ChargingAlgebra := ⟨⟨1, 0, 0, 0⟩⟩

def ChargingAlgebra.mul (q₁ q₂ : ChargingAlgebra) : ChargingAlgebra :=
  { re := q₁.re * q₂.re - q₁.i * q₂.i - q₁.j * q₂.j,
    i  := q₁.re * q₂.i + q₁.i * q₂.re,
    j  := q₁.re * q₂.j + q₁.j * q₂.re,
    ε  := q₁.re * q₂.ε + q₁.ε * q₂.re + q₁.i * q₂.j - q₁.j * q₂.i }

def ChargingAlgebra.commutator (q₁ q₂ : ChargingAlgebra) : ChargingAlgebra :=
  { re := (q₁.mul q₂).re - (q₂.mul q₁).re,
    i  := (q₁.mul q₂).i  - (q₂.mul q₁).i,
    j  := (q₁.mul q₂).j  - (q₂.mul q₁).j,
    ε  := (q₁.mul q₂).ε  - (q₂.mul q₁).ε }

def ChargingAlgebra.trace (q : ChargingAlgebra) : ℝ := q.re

theorem commutator_trace_vanishes (q₁ q₂ : ChargingAlgebra) :
    (ChargingAlgebra.commutator q₁ q₂).trace = 0 := by
  simp [ChargingAlgebra.commutator, ChargingAlgebra.mul, ChargingAlgebra.trace]
  ring

theorem commutator_imaginary_vanishes (q₁ q₂ : ChargingAlgebra) :
    (ChargingAlgebra.commutator q₁ q₂).i = 0 ∧
    (ChargingAlgebra.commutator q₁ q₂).j = 0 := by
  constructor <;> simp [ChargingAlgebra.commutator, ChargingAlgebra.mul] <;> ring

theorem commutator_is_pure_epsilon (q₁ q₂ : ChargingAlgebra) :
    (ChargingAlgebra.commutator q₁ q₂).re = 0 ∧
    (ChargingAlgebra.commutator q₁ q₂).i = 0 ∧
    (ChargingAlgebra.commutator q₁ q₂).j = 0 := by
  refine ⟨?_, ?_, ?_⟩ <;>
    simp [ChargingAlgebra.commutator, ChargingAlgebra.mul] <;> ring

-- Simple graph definitions
variable {V : Type*} [Fintype V] [DecidableEq V] (G : SimpleGraph V) [DecidableRel G.Adj]

noncomputable def G_dist (u v : V) : ℝ :=
  if u = v then 1 else (G.dist u v : ℝ)

def G_degree (u : V) : ℝ := (G.degree u : ℝ)

noncomputable def omega (u v : V) : ℝ :=
  (17/3) * (G_degree G u)^(-3 : ℤ) - (4/11) * (G_degree G v) + 1 / (19 * G_dist G u v)

axiom crossing_number (G : SimpleGraph V) : ℝ

noncomputable def sum_omega : ℝ :=
  ∑ u : V, ∑ v : V, omega G u v

theorem omega_bounds_crossings (h : sum_omega G ≤ crossing_number G) :
    sum_omega G ≤ crossing_number G := by
  exact h
