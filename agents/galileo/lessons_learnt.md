# Galileo Lessons Learnt
*   **Lesson 1**: High-precision numerical arithmetic must be protected against division-by-zero singularities. When generating meshes near poles (e.g. rational hypersurface slices), apply mask thresholds to prevent infinite spikes.
*   **Lesson 2**: Use `BigInt` or exact rational representations (like Python `Fraction`) for combinatorial summations to avoid floating-point roundoff errors when checking modular congruences.
*   **Lesson 3**: Generate plots using a consistent dark-theme style (`dark_background`) to align with modern web application dashboard ergonomics.
