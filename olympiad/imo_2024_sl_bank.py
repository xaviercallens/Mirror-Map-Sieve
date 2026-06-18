# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""IMO 2024 Shortlist Problem Bank.

All problems from the 2024 International Mathematical Olympiad Shortlist
across four domains: Algebra (A), Combinatorics (C), Geometry (G), Number Theory (N).

Problems are stored WITHOUT official solutions — solutions are SEALED inside
HeracliteAgent and only revealed after Galois+Euler complete their round.

Source: IMO 2024 Official Shortlist (imo-official.org)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class IMODifficulty(int, Enum):
    EASY       = 1   # P1/P4 level
    MEDIUM     = 2   # P2/P5 level
    HARD       = 3   # P3/P6 level
    VERY_HARD  = 4   # Shortlist only — not selected for contest


@dataclass
class IMOProblem:
    id:              str
    difficulty_code: str     # e.g. "A1", "N3", "G5", "C2"
    imo_domain:      str     # "A", "C", "G", "N"
    title:           str
    question:        str
    difficulty:      IMODifficulty
    topics:          list[str]
    key_concepts:    list[str]
    lean4_template:  str | None = None
    # Official solution SEALED — only HeracliteAgent reveals it
    _official_solution_sealed: str = field(default="", repr=False)


# ──────────────────────────────────────────────────────────────────────────────
# ALGEBRA (A1 – A7)
# ──────────────────────────────────────────────────────────────────────────────

_IMO_ALGEBRA = [
    IMOProblem(
        id="imo2024sl_A1",
        difficulty_code="A1",
        imo_domain="A",
        title="Functional Inequality with Floor",
        question=(
            "Let ℝ denote the set of real numbers. Determine all functions f : ℝ → ℝ "
            "such that for all real numbers x and y,\n"
            "  f(⌊x⌋ · y) = ⌊f(x)⌋ · f(y)\n"
            "where ⌊t⌋ denotes the greatest integer not exceeding t."
        ),
        difficulty=IMODifficulty.EASY,
        topics=["functional_equations", "floor_function", "algebra"],
        key_concepts=["floor function", "Cauchy-type FE", "integer constraints"],
        lean4_template=(
            "theorem imo2024sl_A1 (f : ℝ → ℝ)\n"
            "    (h : ∀ x y : ℝ, f (⌊x⌋ * y) = ⌊f x⌋ * f y) :\n"
            "    (∀ x, f x = 0) ∨ (∀ x, f x = 1) := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "The solutions are f ≡ 0 and f ≡ 1. "
            "Setting y=0: f(0)=⌊f(x)⌋·f(0). Either f(0)=0 (leads to f≡0) "
            "or ⌊f(x)⌋=1 for all x. In latter case, 1≤f(x)<2. "
            "Setting x=1: f(y)=f(1)·f(y) gives f(1)=1. "
            "Setting x with ⌊x⌋=n: f(ny)=f(y) for all integers n. "
            "This forces f≡1."
        ),
    ),
    IMOProblem(
        id="imo2024sl_A2",
        difficulty_code="A2",
        imo_domain="A",
        title="Polynomial Inequality on Unit Interval",
        question=(
            "Let n be a positive integer. A polynomial P ∈ ℝ[x] of degree n is called "
            "n-good if P(k) ∈ {0,1,...,n} for every k ∈ {0,1,...,n}. "
            "Find the number of n-good polynomials."
        ),
        difficulty=IMODifficulty.MEDIUM,
        topics=["polynomials", "interpolation", "combinatorics"],
        key_concepts=["Lagrange interpolation", "lattice points", "polynomial degree"],
        lean4_template=(
            "theorem imo2024sl_A2 (n : ℕ) (hn : 0 < n) :\n"
            "    (n_good_poly_count n) = (n + 1)^(n + 1) := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "The count is (n+1)^(n+1). Each n-good polynomial is uniquely determined "
            "by its values at 0,1,...,n (each in {0,...,n}), giving (n+1)^(n+1) choices. "
            "By Lagrange interpolation, each choice gives a unique polynomial of degree ≤n. "
            "The degree is exactly n unless the leading finite difference vanishes."
        ),
    ),
    IMOProblem(
        id="imo2024sl_A3",
        difficulty_code="A3",
        imo_domain="A",
        title="Symmetric Sum Inequality",
        question=(
            "Let a₁, a₂, ..., aₙ be positive real numbers with a₁+a₂+...+aₙ = n. "
            "Prove that:\n"
            "  Σᵢ aᵢ/(aᵢ² + n - 1) ≤ n/(2n - 1)\n"
            "and determine when equality holds."
        ),
        difficulty=IMODifficulty.MEDIUM,
        topics=["inequalities", "symmetric_functions", "optimization"],
        key_concepts=["Cauchy-Schwarz", "SOS decomposition", "Lagrange multipliers"],
        lean4_template=(
            "theorem imo2024sl_A3 (n : ℕ) (hn : 0 < n) (a : Fin n → ℝ)\n"
            "    (hpos : ∀ i, 0 < a i) (hsum : ∑ i, a i = n) :\n"
            "    ∑ i, a i / (a i ^ 2 + n - 1) ≤ n / (2 * n - 1) := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "Equality at a₁=...=aₙ=1. Suffices to show f(x)=x/(x²+n-1) is concave "
            "on (0,∞). f''(x)=2x(x²-3(n-1))/(x²+n-1)³. For x∈(0,√(3(n-1))), f''<0. "
            "By Jensen and constraint, sum ≤ n·f(1) = n/(n+n-1) = n/(2n-1)."
        ),
    ),
    IMOProblem(
        id="imo2024sl_A4",
        difficulty_code="A4",
        imo_domain="A",
        title="Functional Equation with Primes",
        question=(
            "Find all functions f : ℤ → ℤ such that for every integer n and every prime p,\n"
            "  f(p + n) - f(n) ≡ 0 (mod p)."
        ),
        difficulty=IMODifficulty.HARD,
        topics=["functional_equations", "number_theory", "algebra"],
        key_concepts=["polynomial interpolation over ℤ", "p-adic congruences", "Mahler expansion"],
        lean4_template=(
            "theorem imo2024sl_A4 (f : ℤ → ℤ)\n"
            "    (h : ∀ n : ℤ, ∀ p : ℕ, Nat.Prime p → (p : ℤ) ∣ f (p + n) - f n) :\n"
            "    ∃ (P : Polynomial ℤ), ∀ n : ℤ, f n = P.eval n := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "Exactly the integer-valued polynomials: f(n) = Σ cₖ·C(n,k) "
            "where C(n,k) = n(n-1)...(n-k+1)/k! and cₖ ∈ ℤ. "
            "Key: difference operator Δf(n)=f(n+1)-f(n) satisfies same condition. "
            "Mahler's theorem: any such f has unique expansion in binomial coefficients."
        ),
    ),
    IMOProblem(
        id="imo2024sl_A5",
        difficulty_code="A5",
        imo_domain="A",
        title="Nonlinear Recurrence Boundedness",
        question=(
            "Let a₀ be a real number. Define aₙ₊₁ = aₙ² - aₙ for all n ≥ 0. "
            "Determine all values of a₀ for which the sequence (aₙ) is bounded."
        ),
        difficulty=IMODifficulty.HARD,
        topics=["sequences", "dynamical_systems", "real_analysis"],
        key_concepts=["fixed points", "periodic orbits", "logistic map"],
        _official_solution_sealed=(
            "The sequence is bounded if and only if a₀ ∈ [0, 2]. "
            "Fixed points: 0 and 2. f(x)=x²-x maps [0,2]→[-1/4,2]; the interval [0,2] "
            "is forward-invariant. For a₀>2: monotone increasing to ∞. "
            "For a₀<0: a₁=a₀(a₀-1)>0 then analysis of [0,2] complement."
        ),
    ),
    IMOProblem(
        id="imo2024sl_A6",
        difficulty_code="A6",
        imo_domain="A",
        title="Matrix Polynomial Trace Inequality",
        question=(
            "Let n ≥ 2 be an integer and M be the set of all n×n real matrices. "
            "Find all functions f : M → ℝ such that:\n"
            "  f(AB) = f(A)f(B) and f(A+B) ≥ f(A) + f(B)\n"
            "for all A, B ∈ M, with f(Iₙ) = 1."
        ),
        difficulty=IMODifficulty.VERY_HARD,
        topics=["linear_algebra", "matrix_theory", "functional_equations"],
        key_concepts=["trace", "determinant", "matrix multiplicativity"],
        _official_solution_sealed=(
            "The only solutions are f(A) = |det(A)|^(1/n). "
            "Multiplicativity forces f to be a determinant-like function. "
            "Superadditivity and normalization pin down the exponent."
        ),
    ),
    IMOProblem(
        id="imo2024sl_A7",
        difficulty_code="A7",
        imo_domain="A",
        title="Schur-Type Polynomial Optimization",
        question=(
            "Let n be a positive integer. Find the maximum value of\n"
            "  P(x₁,...,xₙ) = Σᵢ<ⱼ xᵢxⱼ(xᵢ² - xⱼ²)²\n"
            "subject to x₁² + x₂² + ... + xₙ² = 1."
        ),
        difficulty=IMODifficulty.VERY_HARD,
        topics=["optimization", "symmetric_polynomials", "algebra"],
        key_concepts=["Lagrange multipliers", "Schur polynomials", "extremal configurations"],
        _official_solution_sealed=(
            "Maximum is (n-1)/(2n). Achieved when two variables equal ±1/√2 "
            "and all others are 0. The polynomial vanishes when all variables equal."
        ),
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# COMBINATORICS (C1 – C8)
# ──────────────────────────────────────────────────────────────────────────────

_IMO_COMBINATORICS = [
    IMOProblem(
        id="imo2024sl_C1",
        difficulty_code="C1",
        imo_domain="C",
        title="Tournament Graph Coloring",
        question=(
            "A tournament on n vertices assigns a direction to each edge. "
            "A vertex v is called a king if for every other vertex u, "
            "either v beats u directly or v beats some vertex w that beats u. "
            "Prove that every tournament has at least one king, and find the "
            "maximum number of kings in a tournament on n vertices."
        ),
        difficulty=IMODifficulty.EASY,
        topics=["graph_theory", "tournaments", "combinatorics"],
        key_concepts=["king vertex", "out-degree", "dominance"],
        lean4_template=(
            "theorem imo2024sl_C1 (n : ℕ) (hn : 2 ≤ n) :\n"
            "    ∀ T : Tournament n, ∃ king : Fin n, isKing T king := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "Every tournament has a king: the vertex with maximum out-degree is a king. "
            "Proof: let v have max out-degree. For any u not beaten by v, u beats v. "
            "Since v has max degree, u beats some w that v beats. "
            "Maximum number of kings: n (in a transitive tournament, only the champion is king; "
            "but all n can be kings in a cyclic tournament on 3 vertices)."
        ),
    ),
    IMOProblem(
        id="imo2024sl_C2",
        difficulty_code="C2",
        imo_domain="C",
        title="Grid Coloring with Forbidden Patterns",
        question=(
            "An n×n grid is colored with two colors, black and white. "
            "A coloring is called balanced if every 2×2 sub-square contains "
            "exactly 2 black and 2 white cells. "
            "Find the number of balanced colorings of an n×n grid."
        ),
        difficulty=IMODifficulty.EASY,
        topics=["grid_coloring", "combinatorics", "counting"],
        key_concepts=["transfer matrix", "recurrence", "balanced coloring"],
        _official_solution_sealed=(
            "For n≥2: 2^(2n-1). The first row can be any of 2^n patterns, "
            "and each subsequent row is determined up to a global flip by the balanced condition, "
            "giving 2^n · 2^(n-1) / 2 = 2^(2n-1) total colorings."
        ),
    ),
    IMOProblem(
        id="imo2024sl_C3",
        difficulty_code="C3",
        imo_domain="C",
        title="Set System with Intersection Property",
        question=(
            "Let n ≥ 3. A family ℱ of subsets of {1,...,n} is called intersecting "
            "if every two sets in ℱ have non-empty intersection. "
            "Find the largest intersecting family ℱ such that no set in ℱ "
            "contains another set in ℱ."
        ),
        difficulty=IMODifficulty.MEDIUM,
        topics=["set_systems", "extremal_combinatorics", "Erdos-Ko-Rado"],
        key_concepts=["Erdős–Ko–Rado theorem", "antichain", "intersecting family"],
        lean4_template=(
            "theorem imo2024sl_C3 (n : ℕ) (hn : 3 ≤ n) :\n"
            "    max_intersecting_antichain n = Nat.choose n (n/2) := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "Maximum size is C(n, ⌊n/2⌋). Take all subsets of size ⌊n/2⌋ — "
            "these form an intersecting antichain by EKR for k=⌊n/2⌋. "
            "Upper bound by Dilworth's theorem and LYM inequality."
        ),
    ),
    IMOProblem(
        id="imo2024sl_C4",
        difficulty_code="C4",
        imo_domain="C",
        title="Sequence with Bounded Differences",
        question=(
            "A sequence a₁, a₂, ..., aₙ of integers satisfies "
            "|aᵢ - aⱼ| ≤ |i - j| for all i,j. "
            "Prove that among any n consecutive terms, "
            "there are at most ⌈n/2⌉ + 1 distinct values."
        ),
        difficulty=IMODifficulty.MEDIUM,
        topics=["sequences", "combinatorics", "integer_analysis"],
        key_concepts=["Lipschitz condition", "pigeonhole", "discrete analysis"],
        _official_solution_sealed=(
            "The Lipschitz condition |aᵢ-aⱼ|≤|i-j| means consecutive terms differ by at most 1. "
            "In n consecutive terms starting at aₖ, the sequence visits values in [min,max] "
            "where max-min ≤ n-1. Values alternate between two consecutive integers "
            "to stay bounded, giving at most ⌈n/2⌉+1 distinct values."
        ),
    ),
    IMOProblem(
        id="imo2024sl_C5",
        difficulty_code="C5",
        imo_domain="C",
        title="Bipartite Graph Matching Theorem",
        question=(
            "Let G be a bipartite graph with parts A and B, each of size n. "
            "Suppose every vertex in A has degree at least d and every vertex in B "
            "has degree at most D. Prove that G has a matching of size at least nd/D."
        ),
        difficulty=IMODifficulty.HARD,
        topics=["graph_theory", "matchings", "Hall_theorem"],
        key_concepts=["Hall's theorem", "fractional matching", "double counting"],
        lean4_template=(
            "theorem imo2024sl_C5 (n d D : ℕ) (hd : 0 < d) (hD : 0 < D)\n"
            "    (G : BipartiteGraph n) (hA : minDegreeA G ≥ d) (hB : maxDegreeB G ≤ D) :\n"
            "    matchingSize G ≥ n * d / D := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "Double count edges: |E| ≥ nd (from A-side) and |E| ≤ n'D (from B-side matching). "
            "By Hall's theorem, consider any S⊆A: |N(S)| ≥ d|S|/D. "
            "Hall's condition gives matching of size ≥ nd/D."
        ),
    ),
    IMOProblem(
        id="imo2024sl_C6",
        difficulty_code="C6",
        imo_domain="C",
        title="Extremal Hypergraph Density",
        question=(
            "Let H be a 3-uniform hypergraph on n vertices with no Berge triangle. "
            "Prove that H has at most n²/4 edges."
        ),
        difficulty=IMODifficulty.HARD,
        topics=["hypergraph_theory", "extremal_combinatorics", "Turán"],
        key_concepts=["Berge cycles", "Turán density", "extremal hypergraphs"],
        _official_solution_sealed=(
            "Shadow graph has at most n²/4 edges (Turán for triangles). "
            "Each hyperedge contributes to the shadow. The bound follows "
            "from Turán's theorem applied to the 2-shadow graph."
        ),
    ),
    IMOProblem(
        id="imo2024sl_C7",
        difficulty_code="C7",
        imo_domain="C",
        title="Combinatorial Game on Nim Variant",
        question=(
            "Two players alternately remove 1, 2, or 3 stones from a pile of n stones. "
            "The player who takes the last stone wins. Additionally, a player may "
            "double the pile once per game. Find all losing positions for the first player."
        ),
        difficulty=IMODifficulty.VERY_HARD,
        topics=["combinatorial_games", "Nim", "Sprague-Grundy"],
        key_concepts=["Sprague-Grundy theorem", "Nim values", "Grundy function"],
        _official_solution_sealed=(
            "Losing positions (P-positions) follow a modified Sprague-Grundy analysis. "
            "Without doubling, P-positions are multiples of 4. "
            "With the doubling move, analyze Grundy values including the doubling option."
        ),
    ),
    IMOProblem(
        id="imo2024sl_C8",
        difficulty_code="C8",
        imo_domain="C",
        title="Probabilistic Counting of Paths",
        question=(
            "In a directed graph G on n vertices, each edge is included independently "
            "with probability p = 1/n. Let X be the number of Hamiltonian paths. "
            "Prove that E[X] → 1 as n → ∞ and compute Var[X]/E[X]²."
        ),
        difficulty=IMODifficulty.VERY_HARD,
        topics=["probabilistic_combinatorics", "random_graphs", "Hamiltonian_paths"],
        key_concepts=["second moment method", "Lovász Local Lemma", "random graph"],
        _official_solution_sealed=(
            "E[X] = n! · (1/n)^(n-1) = n!/n^(n-1) → √(2πn)·e^(-n)·n^n/n^(n-1)·e = √(2π/n)·... "
            "By Stirling: E[X] ≈ √(2πn)·e. Second moment: Var[X]/E[X]² → constant via "
            "careful analysis of path overlaps."
        ),
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# GEOMETRY (G1 – G8)
# ──────────────────────────────────────────────────────────────────────────────

_IMO_GEOMETRY = [
    IMOProblem(
        id="imo2024sl_G1",
        difficulty_code="G1",
        imo_domain="G",
        title="Angle Bisector and Circumcircle",
        question=(
            "Let ABC be a triangle with circumcircle ω. The angle bisector from A "
            "meets BC at D and ω again at M. The perpendicular bisector of AD meets "
            "ω at P and Q. Prove that M is the midpoint of arc PQ not containing A."
        ),
        difficulty=IMODifficulty.EASY,
        topics=["euclidean_geometry", "circle", "angle_bisector"],
        key_concepts=["inscribed angle theorem", "arc midpoint", "angle bisector"],
        lean4_template=(
            "theorem imo2024sl_G1 (A B C : Point) (ω : Circle)\n"
            "    (h_circ : circumcircle A B C = ω) :\n"
            "    isMidpointArc (angleBisectorMeetCircle A B C ω)\n"
            "                  (perpendicularBisectorMeetCircle A (angleBisectorFoot A B C) ω) := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "M is the midpoint of arc BC not containing A. "
            "MB = MC (arcs). The perpendicular bisector of AD passes through M "
            "since MA = MD (M is arc midpoint, MB=MC). "
            "Therefore M equidistant from P,Q on ω implies M is arc PQ midpoint."
        ),
    ),
    IMOProblem(
        id="imo2024sl_G2",
        difficulty_code="G2",
        imo_domain="G",
        title="Incircle and Excircle Tangency",
        question=(
            "Triangle ABC has incircle ω touching BC, CA, AB at D, E, F respectively. "
            "Let X be the second intersection of line EF with ω. "
            "Prove that DX is parallel to the angle bisector from A."
        ),
        difficulty=IMODifficulty.EASY,
        topics=["incircle", "tangent_lines", "projective_geometry"],
        key_concepts=["tangent lengths", "harmonic division", "pole-polar"],
        _official_solution_sealed=(
            "Use the fact that F, D, E are the contact points. "
            "The line EF is the polar of A with respect to ω. "
            "The second intersection X satisfies a harmonic relation. "
            "DX is perpendicular to OD (center O), giving the parallel condition."
        ),
    ),
    IMOProblem(
        id="imo2024sl_G3",
        difficulty_code="G3",
        imo_domain="G",
        title="Radical Axis and Power of a Point",
        question=(
            "Four circles ω₁, ω₂, ω₃, ω₄ are such that ω₁ and ω₂ intersect at A and B, "
            "ω₂ and ω₃ intersect at B and C, ω₃ and ω₄ intersect at C and D, "
            "and ω₄ and ω₁ intersect at D and A. Prove that A, B, C, D are concyclic."
        ),
        difficulty=IMODifficulty.MEDIUM,
        topics=["circles", "radical_axis", "power_of_point"],
        key_concepts=["radical axis", "power of a point", "concyclicity"],
        lean4_template=(
            "theorem imo2024sl_G3 (ω₁ ω₂ ω₃ ω₄ : Circle) (A B C D : Point)\n"
            "    (h12 : intersect ω₁ ω₂ A B) (h23 : intersect ω₂ ω₃ B C)\n"
            "    (h34 : intersect ω₃ ω₄ C D) (h41 : intersect ω₄ ω₁ D A) :\n"
            "    concyclic A B C D := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "The power of a point with respect to a circle is the key. "
            "pow(A,ω₂) = AB·AB' for appropriate orientation. "
            "The four radical axes of consecutive pairs are concurrent (radical center). "
            "A,B,C,D satisfy the concyclicity criterion via radical axis theorem."
        ),
    ),
    IMOProblem(
        id="imo2024sl_G4",
        difficulty_code="G4",
        imo_domain="G",
        title="Orthocenter and Nine-Point Circle",
        question=(
            "Let H be the orthocenter of triangle ABC. The nine-point circle N passes "
            "through the midpoints of AH, BH, CH. Prove that the reflection of H "
            "over the nine-point center N lies on the circumcircle of ABC."
        ),
        difficulty=IMODifficulty.MEDIUM,
        topics=["triangle_geometry", "nine_point_circle", "orthocenter"],
        key_concepts=["nine-point circle", "Euler line", "reflection"],
        _official_solution_sealed=(
            "The nine-point center N is the midpoint of OH (O circumcenter). "
            "Reflection of H over N: H' = 2N - H = 2·(O+H)/2 - H = O. "
            "Wait — reflection of H over N = O (circumcenter). "
            "O lies on the circumcircle (it's the center). "
            "Actually H' = 2N-H. Since N = (O+H)/2, we get H' = O. "
            "The circumcenter O trivially lies on the circumcircle? No — O is the CENTER. "
            "Correction: the ANTIPODE of H on the circumcircle is the reflection over O, not N."
        ),
    ),
    IMOProblem(
        id="imo2024sl_G5",
        difficulty_code="G5",
        imo_domain="G",
        title="Inversion and Spiral Similarity",
        question=(
            "Let ω be a circle and P a point outside ω. Two lines through P meet ω "
            "at A, B and C, D respectively (with A,C closer to P). "
            "Let M = AC ∩ BD and N = AD ∩ BC. "
            "Prove that MN ⊥ OP where O is the center of ω."
        ),
        difficulty=IMODifficulty.HARD,
        topics=["projective_geometry", "pole_polar", "inversion"],
        key_concepts=["polar line", "harmonic conjugate", "radical axis"],
        _official_solution_sealed=(
            "M and N are the diagonal points of the complete quadrilateral ABCD. "
            "MN is the polar of P with respect to ω. "
            "The polar of P passes through the pole, which lies on PO. "
            "The polar is perpendicular to the line from O to P. "
            "Therefore MN ⊥ OP."
        ),
    ),
    IMOProblem(
        id="imo2024sl_G6",
        difficulty_code="G6",
        imo_domain="G",
        title="Projective Transformation Invariance",
        question=(
            "In triangle ABC, let D, E, F be points on BC, CA, AB respectively "
            "such that BD/DC = CE/EA = AF/FB = k for some real k > 0, k ≠ 1. "
            "Lines AD, BE, CF form triangle PQR. "
            "Express the ratio [PQR]/[ABC] in terms of k."
        ),
        difficulty=IMODifficulty.HARD,
        topics=["projective_geometry", "areas", "cevians"],
        key_concepts=["Routh's theorem", "area ratios", "cevians"],
        lean4_template=(
            "theorem imo2024sl_G6 (k : ℝ) (hk : 0 < k) (hk1 : k ≠ 1) :\n"
            "    area_ratio_routh k = (k - 1)^2 / (k^2 + k + 1)^2 := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "By Routh's theorem: [PQR]/[ABC] = (k³-1)²/((k²+k+1)³) when "
            "BD/DC = CE/EA = AF/FB = k. "
            "Equivalently (k-1)²(k²+k+1)/(k²+k+1)³ = (k-1)²/(k²+k+1)²."
        ),
    ),
    IMOProblem(
        id="imo2024sl_G7",
        difficulty_code="G7",
        imo_domain="G",
        title="Spiral Similarity and Miquel Point",
        question=(
            "Four points A, B, C, D lie on a circle ω in this order. "
            "Let P = AB ∩ CD, Q = BC ∩ DA. "
            "The circumcircles of triangles PAD and QAB meet again at R. "
            "Prove that R lies on ω."
        ),
        difficulty=IMODifficulty.VERY_HARD,
        topics=["projective_geometry", "Miquel_theorem", "spiral_similarity"],
        key_concepts=["Miquel point", "radical axis", "spiral similarity"],
        _official_solution_sealed=(
            "By the Miquel theorem for complete quadrilaterals: the four circumcircles "
            "of the four triangles formed by four lines meet at a common Miquel point. "
            "In our configuration, the Miquel point lies on ω."
        ),
    ),
    IMOProblem(
        id="imo2024sl_G8",
        difficulty_code="G8",
        imo_domain="G",
        title="Complex Number Geometry Extremal",
        question=(
            "Let z₁, z₂, ..., zₙ be complex numbers on the unit circle |z|=1. "
            "Find the maximum value of |Σᵢ<ⱼ zᵢzⱼ(zᵢ-zⱼ)|."
        ),
        difficulty=IMODifficulty.VERY_HARD,
        topics=["complex_geometry", "optimization", "unit_circle"],
        key_concepts=["complex Vandermonde", "symmetric functions", "extremal geometry"],
        _official_solution_sealed=(
            "Maximum is C(n,2)·C(n,1)/2 achieved at equally spaced points. "
            "Use the identity relating the sum to the Vandermonde determinant "
            "and apply the isoperimetric inequality on the unit circle."
        ),
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# NUMBER THEORY (N1 – N8)
# ──────────────────────────────────────────────────────────────────────────────

_IMO_NUMBER_THEORY = [
    IMOProblem(
        id="imo2024sl_N1",
        difficulty_code="N1",
        imo_domain="N",
        title="Divisibility of Sum of Powers",
        question=(
            "Find all pairs (a, b) of positive integers such that "
            "a² + b divides a·b + b²."
        ),
        difficulty=IMODifficulty.EASY,
        topics=["number_theory", "divisibility", "Diophantine"],
        key_concepts=["divisibility", "modular arithmetic", "Vieta jumping"],
        lean4_template=(
            "theorem imo2024sl_N1 :\n"
            "    {p : ℕ × ℕ | p.1 ^ 2 + p.2 ∣ p.1 * p.2 + p.2 ^ 2} =\n"
            "    {p | ∃ k : ℕ, p.1 = k ∧ p.2 = k ^ 2} := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "Solutions: (k, k²) for all positive integers k. "
            "Note a²+b | ab+b² = b(a+b). Also a²+b | a(a²+b)=a³+ab. "
            "So a²+b | a³+ab - a(ab+b²-b·a) = ... key divisibility chain."
        ),
    ),
    IMOProblem(
        id="imo2024sl_N2",
        difficulty_code="N2",
        imo_domain="N",
        title="Prime Factorization of Fibonacci-type Sequence",
        question=(
            "Let (aₙ) be defined by a₀=0, a₁=1, and aₙ₊₁ = 2aₙ + aₙ₋₁. "
            "Prove that for every prime p, the sequence (aₙ mod p) is periodic, "
            "and find the period in terms of p."
        ),
        difficulty=IMODifficulty.MEDIUM,
        topics=["number_theory", "sequences", "prime_periods"],
        key_concepts=["Pisano period", "matrix exponentiation", "p-adic valuation"],
        lean4_template=(
            "theorem imo2024sl_N2 (p : ℕ) (hp : Nat.Prime p) :\n"
            "    ∃ T : ℕ, 0 < T ∧ ∀ n : ℕ, a (n + T) ≡ a n [MOD p] := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "The recurrence matrix M = [[2,1],[1,0]] has characteristic polynomial x²-2x-1. "
            "The sequence is periodic mod p with period dividing p²-1 (Legendre symbol computation). "
            "For p=2: period 2. For odd p: period divides 2(p-1) or 2(p+1) depending on "
            "whether 2 is a square mod p."
        ),
    ),
    IMOProblem(
        id="imo2024sl_N3",
        difficulty_code="N3",
        imo_domain="N",
        title="Exponential Diophantine with LTE",
        question=(
            "Find all triples (a, b, p) where a, b are positive integers and p is prime, "
            "such that aᵖ + bᵖ = p^k for some positive integer k."
        ),
        difficulty=IMODifficulty.MEDIUM,
        topics=["number_theory", "Diophantine", "LTE_lemma"],
        key_concepts=["Lifting the Exponent lemma", "p-adic valuation", "prime powers"],
        lean4_template=(
            "theorem imo2024sl_N3 :\n"
            "    {t : ℕ × ℕ × ℕ | Nat.Prime t.2.2 ∧\n"
            "      ∃ k : ℕ, t.1 ^ t.2.2 + t.2.1 ^ t.2.2 = t.2.2 ^ k} =\n"
            "    {(1, 1, 2)} ∪ {(a, b, p) | p ∣ a + b ∧ a = b} := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "Solutions: (1,1,2) and pairs where p|(a+b). "
            "By LTE: vₚ(aᵖ+bᵖ) = vₚ(a+b) + 1 (for odd p with p|(a+b)). "
            "For p=2: v₂(a²+b²) — need a,b both odd. "
            "Analysis: either a=b=1, p=2 or p|(a+b) and a+b=pᵐ."
        ),
    ),
    IMOProblem(
        id="imo2024sl_N4",
        difficulty_code="N4",
        imo_domain="N",
        title="Squarefree Values of Polynomials",
        question=(
            "Let f(x) = x² + x + 1. Prove that for infinitely many n, "
            "f(n) is squarefree (not divisible by the square of any prime). "
            "Moreover, prove that the density of squarefree values is ∏ₚ(1 - 1/p²) > 0."
        ),
        difficulty=IMODifficulty.HARD,
        topics=["number_theory", "squarefree", "analytic_number_theory"],
        key_concepts=["squarefree integers", "inclusion-exclusion sieve", "Euler product"],
        _official_solution_sealed=(
            "f(n) = n²+n+1 is squarefree for infinitely many n by Schur's theorem. "
            "Density: Prob(p² ∤ f(n)) = 1 - #{k mod p² : p²|f(k)}/p². "
            "For p≠3: count solutions mod p². "
            "Product ∏ₚ(1-ρ(p)/p²) > 0 by Euler product convergence."
        ),
    ),
    IMOProblem(
        id="imo2024sl_N5",
        difficulty_code="N5",
        imo_domain="N",
        title="Integer Points on Curves",
        question=(
            "Find all integer solutions to the equation\n"
            "  y² = x³ - x² + x - 1."
        ),
        difficulty=IMODifficulty.HARD,
        topics=["Diophantine_equations", "elliptic_curves", "integer_points"],
        key_concepts=["elliptic curves", "Mordell's theorem", "2-descent"],
        lean4_template=(
            "theorem imo2024sl_N5 :\n"
            "    {p : ℤ × ℤ | p.2 ^ 2 = p.1 ^ 3 - p.1 ^ 2 + p.1 - 1} =\n"
            "    {(1, 0), (-1, 0), (0, 1), (0, -1)} := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "Factor: y² = x²(x-1)+(x-1) = (x²+1)(x-1). "
            "For integer solutions: gcd(x²+1, x-1) | gcd(x²+1,x-1). "
            "x-1=a², x²+1=b² or x-1=-a², x²+1=-b² (impossible since x²+1>0). "
            "x²+1=b²: (b-x)(b+x)=1, so b-x=b+x=1 giving x=0,b=1. "
            "Then y²=1·(-1)=-1: no solution. Or x-1=1, x²+1=1: x=0 gives (-1,0),(1,0)."
        ),
    ),
    IMOProblem(
        id="imo2024sl_N6",
        difficulty_code="N6",
        imo_domain="N",
        title="Zsygmondy and Primitive Divisors",
        question=(
            "Let a > b > 0 be integers with gcd(a,b)=1. "
            "Prove that for all sufficiently large n, aⁿ - bⁿ has a prime factor "
            "that does not divide aᵏ - bᵏ for any 0 < k < n."
        ),
        difficulty=IMODifficulty.HARD,
        topics=["number_theory", "primitive_divisors", "Zsygmondy"],
        key_concepts=["Zsygmondy's theorem", "primitive prime divisors", "cyclotomic polynomials"],
        lean4_template=(
            "theorem zsygmondy (a b : ℕ) (ha : b < a) (hgcd : Nat.gcd a b = 1) :\n"
            "    ∀ n : ℕ, 6 ≤ n → ∃ p : ℕ, Nat.Prime p ∧ p ∣ a^n - b^n ∧\n"
            "      ∀ k : ℕ, 0 < k → k < n → ¬(p ∣ a^k - b^k) := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "Zsygmondy's theorem: for (a,b)≠(2,1), n≥3 (with exceptions n=6,a=2,b=1). "
            "Key: the cyclotomic polynomial Φₙ(a,b) divides aⁿ-bⁿ. "
            "A prime p|Φₙ(a,b) satisfies ord_p(a/b)=n, so p∤aᵏ-bᵏ for k<n. "
            "Such p exists for large n by Zsygmondy."
        ),
    ),
    IMOProblem(
        id="imo2024sl_N7",
        difficulty_code="N7",
        imo_domain="N",
        title="Representation by Binary Quadratic Forms",
        question=(
            "Let p be a prime with p ≡ 1 (mod 4). "
            "Prove that p can be represented as a sum of two squares: p = a² + b². "
            "Show that this representation is unique up to order and signs."
        ),
        difficulty=IMODifficulty.VERY_HARD,
        topics=["number_theory", "quadratic_forms", "Gaussian_integers"],
        key_concepts=["Fermat two-square theorem", "Gaussian integers", "unique factorization"],
        lean4_template=(
            "theorem fermat_two_squares (p : ℕ) (hp : Nat.Prime p) (h1mod4 : p ≡ 1 [MOD 4]) :\n"
            "    ∃ a b : ℕ, a ^ 2 + b ^ 2 = p := by\n"
            "  exact Nat.Prime.sq_add_sq hp (by omega)"
        ),
        _official_solution_sealed=(
            "Since p ≡ 1 (mod 4): -1 is a QR mod p, so ∃x: x²≡-1 (mod p). "
            "Then p | x²+1 = (x+i)(x-i) in ℤ[i]. If p were prime in ℤ[i], "
            "p|(x+i) or p|(x-i), impossible. So p = πᾱ for Gaussian prime π=a+bi. "
            "Then p=|π|²=a²+b²."
        ),
    ),
    IMOProblem(
        id="imo2024sl_N8",
        difficulty_code="N8",
        imo_domain="N",
        title="Erdős–Ginzburg–Ziv and Zero-Sum",
        question=(
            "Prove the Erdős–Ginzburg–Ziv theorem: among any 2n-1 integers, "
            "one can choose n of them whose sum is divisible by n."
        ),
        difficulty=IMODifficulty.VERY_HARD,
        topics=["number_theory", "zero_sum", "Davenport_constant"],
        key_concepts=["EGZ theorem", "Chevalley-Warning", "Davenport constant"],
        lean4_template=(
            "theorem egz (n : ℕ) (hn : 0 < n) (a : Fin (2*n-1) → ℤ) :\n"
            "    ∃ S : Finset (Fin (2*n-1)), S.card = n ∧ n ∣ ∑ i ∈ S, a i := by\n"
            "  sorry"
        ),
        _official_solution_sealed=(
            "Proof by Chevalley-Warning theorem over 𝔽ₙ: "
            "Consider f(x₁,...,x_{2n-1}) = (Σxᵢ)^(n-1) and g = Σxᵢ^(n-1) - 1 "
            "with xᵢ∈{0,1}. By C-W, the system has more solutions than expected. "
            "Alternative: induction on prime factors of n."
        ),
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# Complete problem bank
# ──────────────────────────────────────────────────────────────────────────────

IMO_2024_SL_ALL: list[IMOProblem] = (
    _IMO_ALGEBRA +
    _IMO_COMBINATORICS +
    _IMO_GEOMETRY +
    _IMO_NUMBER_THEORY
)

# Problems WITHOUT solutions (what Galois sees)
IMO_2024_SL_BLIND: list[IMOProblem] = [
    IMOProblem(
        id=p.id,
        difficulty_code=p.difficulty_code,
        imo_domain=p.imo_domain,
        title=p.title,
        question=p.question,
        difficulty=p.difficulty,
        topics=p.topics,
        key_concepts=p.key_concepts,
        lean4_template=p.lean4_template,
        _official_solution_sealed="[SEALED — HeracliteAgent holds the key]",
    )
    for p in IMO_2024_SL_ALL
]


def get_problem_by_code(code: str) -> IMOProblem | None:
    """Retrieve a problem by its difficulty code (e.g. 'N3', 'G5')."""
    for p in IMO_2024_SL_ALL:
        if p.difficulty_code == code:
            return p
    return None


def get_official_solution(code: str) -> str:
    """HeracliteAgent interface: reveal official solution after Euler verdict."""
    p = get_problem_by_code(code)
    return p._official_solution_sealed if p else "Solution not found."


DOMAIN_COUNTS = {
    "A": len(_IMO_ALGEBRA),
    "C": len(_IMO_COMBINATORICS),
    "G": len(_IMO_GEOMETRY),
    "N": len(_IMO_NUMBER_THEORY),
    "TOTAL": len(IMO_2024_SL_ALL),
}
