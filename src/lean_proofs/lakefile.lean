import Lake
open Lake DSL

package «mirror-map-sieve» {
  -- Mirror Map Sieve: S_20 Sequence Formal Verification
  leanOptions := #[
    ⟨`autoImplicit, false⟩,
    ⟨`pp.unicode.fun, true⟩
  ]
}

@[default_target]
lean_lib MirrorMapSieve {
  roots := #[`MirrorMapSieve]
}

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git"

require «SLT» from "../../external/lean-stat-learning-theory"
