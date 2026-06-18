import Lake
open Lake DSL

package S20Verify where
  leanOptions := #[
    ⟨`autoImplicit, false⟩,
    ⟨`relaxedAutoImplicit, false⟩
  ]

@[default_target]
lean_lib S20Verify where
  roots := #[`Agora.Discovery.S20Sequence]

require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @ "v4.14.0"
