# Euler Lessons Learnt
*   **Lesson 1**: Raw concrete instances evaluated via `decide` tactic can bottleneck the Lean 4 compiler if the integers are too large. Shielding them with algebraic properties (rational rings with `ring` tactic) dramatically speeds up compilation.
*   **Lesson 2**: Lean 4 type-coercion from Nat to Int (`↑`) is vital when dealing with signed coefficient sum recurrences, avoiding negative choice errors.
*   **Lesson 3**: Clear the build cache (`.lake/build/`) and purge unused `node_modules` periodically to avoid out-of-disk space errors during complex proofs.
