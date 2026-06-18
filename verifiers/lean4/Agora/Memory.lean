/-
  SocrateAI Scientific Agora — Lean 4 Formal Verification Library
  Copyright © 2025-2026 Socrate AI Lab, Paris, France
  Author: Xavier Callens <callensxavier@gmail.com>
  License: Apache-2.0 (framework) + CC-BY-NC-ND 4.0 (proprietary)
  Patent:  US-PAT-PEND-2026-0525

  Agora.Memory — Arena memory safety proofs for the RunuX kernel.

  The RunuX kernel uses a three-zone arena allocator:
    1. Weight zone  — model parameters (read-heavy, long-lived)
    2. KVCache zone — attention key-value cache (per-request)
    3. Scratch zone — temporary computation buffers (ephemeral)

  Each zone has a base address, capacity, and current allocation level.
  This module proves:
    1. Total allocation never exceeds arena capacity
    2. Allocation preserves the arena invariant
    3. Zones do not overlap in address space
-/

import Agora.Basic
import Mathlib.Data.List.Basic
import Mathlib.Tactic.Linarith

set_option autoImplicit false

namespace Agora.Memory

/-! ## Arena Structure (refined from Basic) -/

/-- A memory arena with verified capacity bounds.
    Re-exports from `Agora.Basic.ArenaConfig` with additional
    allocation-level invariants. -/
structure VerifiedArena where
  zones          : List ZoneDescriptor
  total_capacity : ℕ
  /-- The sum of individual zone capacities fits within total capacity. -/
  zones_fit      : (zones.map ZoneDescriptor.capacity).sum ≤ total_capacity
  /-- Every zone's allocation is within its own capacity. -/
  zones_valid    : ∀ zd ∈ zones, zd.allocated ≤ zd.capacity

/-! ## Boundary Safety Theorem

**Theorem**: The total bytes allocated across all zones never exceeds
the arena's total capacity.

**Proof sketch**:
  Σ zd.allocated ≤ Σ zd.capacity    (each zone: allocated ≤ capacity)
                  ≤ total_capacity   (zones_fit)  □
-/

/-- Total allocated bytes across all zones. -/
def totalAllocated (arena : VerifiedArena) : ℕ :=
  (arena.zones.map ZoneDescriptor.allocated).sum

theorem arena_boundary_safety (arena : VerifiedArena) :
    totalAllocated arena ≤ arena.total_capacity := by
  unfold totalAllocated
  calc (arena.zones.map ZoneDescriptor.allocated).sum
      ≤ (arena.zones.map ZoneDescriptor.capacity).sum := by
        apply List.sum_le_sum
        intro zd hzd_mem
        exact arena.zones_valid zd hzd_mem
    _ ≤ arena.total_capacity := arena.zones_fit

/-! ## Allocation Preserves Invariant

When we allocate `n` additional bytes to a specific zone, the arena
invariant is preserved provided the zone has sufficient remaining
capacity.
-/

/-- Allocate `n` bytes to the zone at index `idx`, returning a new
    zone descriptor with an increased allocation level. -/
def allocateInZone (zd : ZoneDescriptor) (n : ℕ)
    (h : zd.allocated + n ≤ zd.capacity) : ZoneDescriptor where
  zone      := zd.zone
  base      := zd.base
  capacity  := zd.capacity
  allocated := zd.allocated + n
  inv       := h

/-- Allocation within a single zone preserves its local invariant. -/
theorem allocate_zone_valid (zd : ZoneDescriptor) (n : ℕ)
    (h : zd.allocated + n ≤ zd.capacity) :
    (allocateInZone zd n h).allocated ≤ (allocateInZone zd n h).capacity := by
  simp [allocateInZone]
  exact h

theorem map_set_capacity_eq (l : List ZoneDescriptor) (i : ℕ) (v : ZoneDescriptor)
    (h_i : i < l.length)
    (h_cap : v.capacity = (l.get ⟨i, h_i⟩).capacity) :
    (l.set i v).map ZoneDescriptor.capacity = l.map ZoneDescriptor.capacity := by
  induction l generalizing i with
  | nil =>
    simp
  | cons x xs ih =>
    cases i with
    | zero =>
      simp [h_cap]
    | succ i =>
      have h_i_succ : i < xs.length := by
        simp at h_i
        omega
      have ih_i := ih i h_i_succ (by
        simp [h_cap]
      )
      simp [ih_i]

/-- Replace the zone descriptor at position `idx` in the arena. -/
def replaceZone (arena : VerifiedArena) (idx : Fin arena.zones.length)
    (new_zd : ZoneDescriptor)
    (h_cap : new_zd.capacity = (arena.zones.get idx).capacity)
    (h_valid : new_zd.allocated ≤ new_zd.capacity) : VerifiedArena where
  zones := arena.zones.set idx.val new_zd
  total_capacity := arena.total_capacity
  zones_fit := by
    rw [map_set_capacity_eq arena.zones idx.val new_zd idx.isLt h_cap]
    exact arena.zones_fit
  zones_valid := by
    intro zd hzd
    rcases List.mem_or_eq_of_mem_set hzd with h_mem | h_eq
    · exact arena.zones_valid zd h_mem
    · subst h_eq
      exact h_valid

/-- Full allocation operation: allocate n bytes to zone at index idx. -/
theorem allocation_preserves_invariant
    (arena : VerifiedArena)
    (idx : Fin arena.zones.length)
    (n : ℕ)
    (h_fits : (arena.zones.get idx).allocated + n ≤ (arena.zones.get idx).capacity) :
    let new_zd := allocateInZone (arena.zones.get idx) n h_fits
    let new_arena := replaceZone arena idx new_zd rfl (allocate_zone_valid _ n h_fits)
    totalAllocated new_arena ≤ new_arena.total_capacity := by
  intro new_zd new_arena
  exact arena_boundary_safety new_arena

/-! ## Zone Non-Overlap

Zones must occupy disjoint address ranges to prevent corruption.
A zone occupies the byte range [base, base + capacity).
-/

/-- Two zone descriptors have non-overlapping address ranges. -/
def zonesDisjoint (a b : ZoneDescriptor) : Prop :=
  a.base + a.capacity ≤ b.base ∨ b.base + b.capacity ≤ a.base

/-- A list of zones is pairwise non-overlapping. -/
def allZonesDisjoint (zones : List ZoneDescriptor) : Prop :=
  ∀ i j : Fin zones.length, i ≠ j →
    zonesDisjoint (zones.get i) (zones.get j)

/-- If zones are laid out contiguously (each zone starts where the
    previous one ends), they are automatically disjoint. -/
theorem contiguous_implies_disjoint
    (zones : List ZoneDescriptor)
    (h_contiguous : ∀ i : Fin zones.length, ∀ j : Fin zones.length,
      i.val < j.val →
      (zones.get i).base + (zones.get i).capacity ≤ (zones.get j).base) :
    allZonesDisjoint zones := by
  intro i j hij
  unfold zonesDisjoint
  rcases Nat.lt_or_gt_of_ne (Fin.val_ne_of_ne hij) with h | h
  · exact Or.inl (h_contiguous i j h)
  · exact Or.inr (h_contiguous j i h)

/-! ## Deallocation Safety -/

/-- Deallocating n bytes from a zone is safe if n ≤ allocated. -/
def deallocateInZone (zd : ZoneDescriptor) (n : ℕ)
    (h : n ≤ zd.allocated) : ZoneDescriptor where
  zone      := zd.zone
  base      := zd.base
  capacity  := zd.capacity
  allocated := zd.allocated - n
  inv       := by
    have h_inv := zd.inv
    omega

/-- Deallocation preserves the zone invariant (trivially, since
    allocated can only decrease). -/
theorem deallocate_zone_valid (zd : ZoneDescriptor) (n : ℕ)
    (h : n ≤ zd.allocated) :
    (deallocateInZone zd n h).allocated ≤ (deallocateInZone zd n h).capacity := by
  simp [deallocateInZone]
  have h_inv := zd.inv
  omega

end Agora.Memory
