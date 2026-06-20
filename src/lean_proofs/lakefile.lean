import Lake
open Lake DSL

package «mirror-map-sieve» {
  -- Mirror Map Sieve: S_20 Sequence Formal Verification
}

lean_lib MirrorMapSieve {
  roots := #[`MirrorMapSieve]
}

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git"
