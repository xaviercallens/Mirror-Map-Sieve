-- ============================================================================
-- SocrateAI Scientific Agora — Lean 4 Formal Verification Library
-- Copyright © 2025-2026 Socrate AI Lab, Paris, France
-- Author: Xavier Callens <callensxavier@gmail.com>
-- License: Apache-2.0 (framework) + CC-BY-NC-ND 4.0 (proprietary)
-- Patent:  US-PAT-PEND-2026-0525
-- ============================================================================
-- lakefile.lean — Lake build configuration for the Agora proof library.
-- ============================================================================

import Lake
open Lake DSL

package Agora where
  leanOptions := #[
    ⟨`autoImplicit, false⟩,
    ⟨`relaxedAutoImplicit, false⟩,
    ⟨`weak.doc.verso, true⟩
  ]

  moreLinkArgs := #["-L./.lake/packages/mathlib/.lake/build/lib"]

@[default_target]
lean_lib Agora where
  -- add any library configuration options here
  roots := #[
    -- Tier 1: Core infrastructure (fully verified)
    `Agora.Basic,
    -- Tier 2: Shattered axiom proofs
    `Agora.saw_simple_cubic,
    -- AlienMath core (sorry-free, fully verified)
    `Agora.AlienMath.KalTensorDecomposition,
    `Agora.AlienMath.StrassenVerified,
    `Agora.AlienMath.NonCommutativeCryptography,
    `Agora.AlienMath.LyapunovFunctional,
    `Agora.AlienMath.KalChargingMatrix,
    `Agora.AlienMath.ExactRationalWitness,
    `Agora.AlienMath.RamseySATCorrectness,
    `Agora.AlienMath.Ramsey44,
    `Agora.AlienMath.KalSliceConcatenation,
    `Agora.AlienMath.KalEntropy,
    `Agora.AlienMath.KalHolographicBorderRank,
    `Agora.AlienMath.TensorDeformations,
    `Agora.AlienMath.BlaserLowerBound,
    -- Applications
    `Agora.AlienMath.Applications.Cryptography,
    `Agora.AlienMath.Applications.Quantum,
    -- Tier 3: Axiomatic Local Contexts (external compute pending)
    `Agora.diff_basis_optimal_10000,
    `Agora.crossing_number_kn,
    -- Tier 4: Heavy blueprints (many sorry — formalization frontier)
    `Agora.E37BSD_v6_blueprint,
    `Agora.cmi_millennium_blueprints,
    -- Tier 5: Infrastructure
    `Agora.FormalizationDebt,
    -- Tier 6: Callens Conjectures
    `Agora.Conjectures.LatticePacking,
    `Agora.Conjectures.SchurPositivity,
    `Agora.Conjectures.TownesSoliton,
    `Agora.Conjectures.MirrorSymmetry,
    `Agora.Conjectures.FeynmanSunrise,
    -- Tier 7: Discovery pipeline — combinatorial identities
    `Agora.Discovery.CombinatorialIdentity,
    `Agora.Discovery.RamseySearch,
    `Agora.Discovery.DiscoveredIdentities
  ]

@[default_target]
lean_lib AlienMathematics where
  roots := #[
    `AlienMathematics,
    `Structures.AsymmetricTensors,
    `Structures.AsymptoticTensors,
    `Structures.ExactRationalWitness,
    `Structures.PathologicalLyapunov,
    `Structures.FractionalCharging,
    `Structures.SliceConcatenation,
    `Structures.SelfAvoidingWalks,
    `Structures.CrossingNumbers,
    `Structures.Krawtchouk,
    `Tests.TestAlienMath
  ]

require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @ "v4.14.0"

require verso from git
  "https://github.com/leanprover/verso.git" @ "v4.14.0"

require REPL from git
  "https://github.com/leanprover-community/repl" @ "v4.14.0"

