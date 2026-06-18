# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Andrew Adler PIMS Problem Collection — Full curated problem bank.

This module contains all problems extracted from:
  Andrew Adler, "Collection of Problems, with Solutions and Comments"
  PIMS (Pacific Institute for the Mathematical Sciences)
  Source: https://pims.math.ca/sites/default/files/adlerbook.pdf

Problems are organized by chapter, with structured metadata for
the Mind Olympiad RLFC training loop.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ProblemType(str, Enum):
    """Classification of mathematical problem type."""
    NUMERIC      = "numeric"       # Compute a specific number / expression
    SYMBOLIC     = "symbolic"      # Factor, simplify, transform algebraically
    PROOF        = "proof"         # Demonstrate a logical/algebraic statement
    OPTIMIZATION = "optimization"  # Find a min/max under constraints
    COMBINATORIAL= "combinatorial" # Count, enumerate, find arrangements
    GEOMETRIC    = "geometric"     # Euclidean / analytic geometry
    TRIGONOMETRIC= "trigonometric" # Identities, equations, inverse functions
    NUMBER_THEORY= "number_theory" # Divisibility, primes, modular arithmetic
    PROBABILITY  = "probability"   # Discrete or classical probability
    SEQUENCE     = "sequence"      # Series, recurrences, limits


class DifficultyLevel(int, Enum):
    """Contest difficulty (1=basic, 5=competition-hard)."""
    EASY        = 1
    MEDIUM_EASY = 2
    MEDIUM      = 3
    MEDIUM_HARD = 4
    HARD        = 5


@dataclass(slots=True)
class OlympiadProblemRecord:
    """A fully structured Olympiad problem from Adler's collection."""
    id: str                             # Unique identifier
    chapter: str                        # Book chapter
    chapter_number: int                 # Chapter index (1-based)
    problem_number: int                 # Problem number within chapter
    title: str                          # Short title
    question: str                       # Full problem statement
    solution_book: str                  # Official solution from the book
    problem_type: ProblemType
    difficulty: DifficultyLevel
    topics: list[str] = field(default_factory=list)
    numerical_answer: str | None = None # Expected numeric answer if applicable
    lean4_template: str | None = None   # Optional Lean 4 proof skeleton
    comments: str = ""                  # Pedagogical notes from the book


# ---------------------------------------------------------------------------
# Chapter 1: Word Problems & Applications
# ---------------------------------------------------------------------------
_CH1_PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "adler_c1_p1_mushrooms",
        "chapter": "Chapter 1: Word Problems and Applications",
        "chapter_number": 1,
        "problem_number": 1,
        "title": "Mushroom Dehydration",
        "question": (
            "Fresh mushrooms are 90% water. Dried mushrooms are only 15% water.\n"
            "(a) How many kilograms of fresh mushrooms do we need to make 10 kg of dried mushrooms?\n"
            "(b) How many kg of dried mushrooms do we get from 12 kg of fresh mushrooms?"
        ),
        "solution_book": (
            "(a) 10 kg of dried mushrooms contain 15% water, which means 85% is dry matter (8.5 kg).\n"
            "Since fresh mushrooms are 90% water, they are only 10% dry matter.\n"
            "Therefore, fresh mushrooms required = 8.5 / 0.10 = 85 kg.\n\n"
            "(b) 12 kg of fresh mushrooms contain 10% dry matter = 1.2 kg of powder.\n"
            "Since dried mushrooms contain 85% dry matter:\n"
            "dried weight = 1.2 / 0.85 = 24/17 kg ≈ 1.412 kg."
        ),
        "problem_type": ProblemType.NUMERIC,
        "difficulty": DifficultyLevel.EASY,
        "topics": ["conservation_of_mass", "percentages", "word_problem"],
        "numerical_answer": "(a) 85 kg; (b) 24/17 ≈ 1.412 kg",
        "comments": "Elegant mass-conservation framing avoids unit guessing.",
    },
    {
        "id": "adler_c1_p2_age",
        "chapter": "Chapter 1: Word Problems and Applications",
        "chapter_number": 1,
        "problem_number": 2,
        "title": "Age Puzzle",
        "question": (
            "A father is currently 30 years older than his son.\n"
            "Five years ago, the father was 4 times as old as his son.\n"
            "How old are the father and son now?"
        ),
        "solution_book": (
            "Let s = son's current age, f = father's current age.\n"
            "f = s + 30.\n"
            "5 years ago: f - 5 = 4(s - 5).\n"
            "Substituting: (s + 30) - 5 = 4s - 20 ⟹ s + 25 = 4s - 20 ⟹ 3s = 45 ⟹ s = 15.\n"
            "Father: f = 45. Son: 15."
        ),
        "problem_type": ProblemType.NUMERIC,
        "difficulty": DifficultyLevel.EASY,
        "topics": ["linear_equations", "word_problem", "systems"],
        "numerical_answer": "Son = 15 years, Father = 45 years",
    },
    {
        "id": "adler_c1_p3_work",
        "chapter": "Chapter 1: Word Problems and Applications",
        "chapter_number": 1,
        "problem_number": 3,
        "title": "Work-Rate Problem",
        "question": (
            "Alice can complete a job in 6 hours, and Bob can complete the same job in 10 hours.\n"
            "If they work together, how long will it take them to complete the job?\n"
            "If Alice works alone for 2 hours first, and then Bob joins her, how long until job is done?"
        ),
        "solution_book": (
            "Combined rate = 1/6 + 1/10 = 5/30 + 3/30 = 8/30 = 4/15 jobs/hour.\n"
            "Together: time = 15/4 = 3.75 hours.\n\n"
            "Part (b): Alice works 2 hours alone, completing 2/6 = 1/3 of the job.\n"
            "Remaining = 2/3 of the job at rate 4/15: time = (2/3)/(4/15) = (2/3)×(15/4) = 10/4 = 2.5 hours.\n"
            "Total elapsed = 2 + 2.5 = 4.5 hours."
        ),
        "problem_type": ProblemType.NUMERIC,
        "difficulty": DifficultyLevel.EASY,
        "topics": ["rates", "work_problems", "fractions"],
        "numerical_answer": "(a) 3.75 h; (b) 4.5 h total",
    },
    {
        "id": "adler_c1_p4_mixture",
        "chapter": "Chapter 1: Word Problems and Applications",
        "chapter_number": 1,
        "problem_number": 4,
        "title": "Mixture Concentration",
        "question": (
            "We have two salt solutions: one at 20% concentration and another at 50% concentration.\n"
            "How many liters of each should we mix to get 30 liters of a 30% salt solution?"
        ),
        "solution_book": (
            "Let x = liters of 20% solution, y = liters of 50% solution.\n"
            "x + y = 30\n"
            "0.20x + 0.50y = 0.30 × 30 = 9\n"
            "From first equation: y = 30 - x.\n"
            "0.20x + 0.50(30 - x) = 9 ⟹ 0.20x + 15 - 0.50x = 9 ⟹ -0.30x = -6 ⟹ x = 20.\n"
            "y = 10. So: 20 liters of 20% and 10 liters of 50%."
        ),
        "problem_type": ProblemType.NUMERIC,
        "difficulty": DifficultyLevel.EASY,
        "topics": ["mixture_problems", "linear_systems", "concentration"],
        "numerical_answer": "20 L of 20%, 10 L of 50%",
    },
]

# ---------------------------------------------------------------------------
# Chapter 2: Number Theory
# ---------------------------------------------------------------------------
_CH2_PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "adler_c2_p1_gcd_lcm",
        "chapter": "Chapter 2: Number Theory",
        "chapter_number": 2,
        "problem_number": 1,
        "title": "GCD and LCM Relationship",
        "question": (
            "Let a and b be positive integers with gcd(a, b) = d and lcm(a, b) = m.\n"
            "Prove that a × b = d × m."
        ),
        "solution_book": (
            "Write a = d·p and b = d·q where gcd(p, q) = 1.\n"
            "Then lcm(a, b) = d·p·q (since gcd(p,q)=1, the lcm of d·p and d·q is d·pq).\n"
            "So d × m = d × (d·p·q) = d²·pq.\n"
            "And a × b = (d·p)(d·q) = d²·pq.\n"
            "Therefore a × b = d × m. □"
        ),
        "problem_type": ProblemType.PROOF,
        "difficulty": DifficultyLevel.MEDIUM,
        "topics": ["gcd", "lcm", "number_theory", "divisibility"],
        "lean4_template": (
            "theorem gcd_lcm_product (a b : ℕ) (ha : 0 < a) (hb : 0 < b) :\n"
            "  a * b = Nat.gcd a b * Nat.lcm a b := by\n"
            "  sorry"
        ),
    },
    {
        "id": "adler_c2_p2_divisibility",
        "chapter": "Chapter 2: Number Theory",
        "chapter_number": 2,
        "problem_number": 2,
        "title": "Divisibility by 9",
        "question": (
            "Prove that a positive integer N is divisible by 9 if and only if\n"
            "the sum of its decimal digits is divisible by 9."
        ),
        "solution_book": (
            "Write N = aₙ·10ⁿ + aₙ₋₁·10ⁿ⁻¹ + ... + a₁·10 + a₀ where aᵢ are digits.\n"
            "Since 10 ≡ 1 (mod 9), we have 10ᵏ ≡ 1 (mod 9) for all k ≥ 0.\n"
            "Therefore N ≡ aₙ + aₙ₋₁ + ... + a₁ + a₀ (mod 9).\n"
            "So 9 | N ⟺ 9 | (aₙ + ... + a₀). □"
        ),
        "problem_type": ProblemType.PROOF,
        "difficulty": DifficultyLevel.MEDIUM,
        "topics": ["modular_arithmetic", "digit_sum", "divisibility", "congruences"],
        "lean4_template": (
            "theorem div9_iff_digitSum_div9 (N : ℕ) :\n"
            "  9 ∣ N ↔ 9 ∣ Nat.digitSum N := by\n"
            "  sorry"
        ),
    },
    {
        "id": "adler_c2_p3_primes",
        "chapter": "Chapter 2: Number Theory",
        "chapter_number": 2,
        "problem_number": 3,
        "title": "Infinitely Many Primes",
        "question": (
            "Prove that there are infinitely many prime numbers.\n"
            "(You may use Euclid's classic argument or any other valid approach.)"
        ),
        "solution_book": (
            "Suppose for contradiction that there are finitely many primes: p₁, p₂, ..., pₙ.\n"
            "Let N = p₁·p₂·...·pₙ + 1.\n"
            "N > 1, so N has some prime divisor p.\n"
            "But p cannot be any pᵢ (since N ≡ 1 mod pᵢ for each i).\n"
            "This contradicts the assumption that p₁,...,pₙ are all primes. □"
        ),
        "problem_type": ProblemType.PROOF,
        "difficulty": DifficultyLevel.MEDIUM,
        "topics": ["prime_numbers", "proof_by_contradiction", "number_theory"],
        "lean4_template": (
            "theorem infinitely_many_primes : ∀ n : ℕ, ∃ p > n, Nat.Prime p := by\n"
            "  sorry"
        ),
    },
    {
        "id": "adler_c2_p4_bezout",
        "chapter": "Chapter 2: Number Theory",
        "chapter_number": 2,
        "problem_number": 4,
        "title": "Bézout's Identity",
        "question": (
            "Let a, b be positive integers with gcd(a,b) = d.\n"
            "Show that there exist integers x, y such that ax + by = d."
        ),
        "solution_book": (
            "Consider the set S = {ax + by : x, y ∈ ℤ, ax + by > 0}. S is nonempty (a,b ∈ S).\n"
            "Let d' be the smallest element of S. Write d' = ax₀ + by₀.\n"
            "For any c ∈ S, divide c by d': c = qd' + r, 0 ≤ r < d'.\n"
            "r = c - qd' = a(x - qx₀) + b(y - qy₀) ∈ S ∪ {0}.\n"
            "Since d' is minimal and r < d', we must have r = 0, so d' | c for all c ∈ S.\n"
            "In particular d' | a and d' | b, so d' | gcd(a,b) = d.\n"
            "But d | ax₀ + by₀ = d', so d = d'. □"
        ),
        "problem_type": ProblemType.PROOF,
        "difficulty": DifficultyLevel.MEDIUM_HARD,
        "topics": ["bezout", "gcd", "number_theory", "well_ordering"],
    },
    {
        "id": "adler_c2_p5_chinese_remainder",
        "chapter": "Chapter 2: Number Theory",
        "chapter_number": 2,
        "problem_number": 5,
        "title": "Chinese Remainder Theorem (special case)",
        "question": (
            "Find all integers x such that:\n"
            "  x ≡ 2 (mod 3)\n"
            "  x ≡ 3 (mod 5)\n"
            "  x ≡ 2 (mod 7)"
        ),
        "solution_book": (
            "From x ≡ 2 (mod 3): x = 3k + 2.\n"
            "Substituting in second: 3k + 2 ≡ 3 (mod 5) ⟹ 3k ≡ 1 (mod 5) ⟹ k ≡ 2 (mod 5).\n"
            "So k = 5j + 2, giving x = 3(5j + 2) + 2 = 15j + 8.\n"
            "Substituting in third: 15j + 8 ≡ 2 (mod 7) ⟹ j + 1 ≡ 2 (mod 7) ⟹ j ≡ 1 (mod 7).\n"
            "So j = 7m + 1, giving x = 15(7m + 1) + 8 = 105m + 23.\n"
            "Solution: x ≡ 23 (mod 105)."
        ),
        "problem_type": ProblemType.NUMBER_THEORY,
        "difficulty": DifficultyLevel.MEDIUM,
        "topics": ["chinese_remainder_theorem", "congruences", "modular_arithmetic"],
        "numerical_answer": "x ≡ 23 (mod 105)",
    },
]

# ---------------------------------------------------------------------------
# Chapter 3: Combinatorics and Counting
# ---------------------------------------------------------------------------
_CH3_PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "adler_c3_p1_handshakes",
        "chapter": "Chapter 3: Combinatorics and Counting",
        "chapter_number": 3,
        "problem_number": 1,
        "title": "Handshakes at a Party",
        "question": (
            "At a party of n people, each person shakes hands exactly once with every other person.\n"
            "(a) How many handshakes take place?\n"
            "(b) If 120 handshakes took place, how many people were at the party?"
        ),
        "solution_book": (
            "(a) Each handshake is a 2-element subset of n people. The number is C(n, 2) = n(n-1)/2.\n\n"
            "(b) n(n-1)/2 = 120 ⟹ n(n-1) = 240.\n"
            "Testing n = 16: 16 × 15 = 240. ✓\n"
            "So n = 16 people."
        ),
        "problem_type": ProblemType.COMBINATORIAL,
        "difficulty": DifficultyLevel.EASY,
        "topics": ["combinations", "binomial_coefficients", "graph_theory"],
        "numerical_answer": "(a) n(n-1)/2; (b) n = 16",
    },
    {
        "id": "adler_c3_p2_inclusion_exclusion",
        "chapter": "Chapter 3: Combinatorics and Counting",
        "chapter_number": 3,
        "problem_number": 2,
        "title": "Students in Clubs (Inclusion-Exclusion)",
        "question": (
            "In a class of 40 students: 18 play chess, 16 play checkers, 12 play both.\n"
            "How many students play neither chess nor checkers?"
        ),
        "solution_book": (
            "By inclusion-exclusion:\n"
            "|Chess ∪ Checkers| = |Chess| + |Checkers| - |Chess ∩ Checkers| = 18 + 16 - 12 = 22.\n"
            "Students playing neither = 40 - 22 = 18."
        ),
        "problem_type": ProblemType.COMBINATORIAL,
        "difficulty": DifficultyLevel.EASY,
        "topics": ["inclusion_exclusion", "set_theory", "counting"],
        "numerical_answer": "18 students",
    },
    {
        "id": "adler_c3_p3_pigeonhole",
        "chapter": "Chapter 3: Combinatorics and Counting",
        "chapter_number": 3,
        "problem_number": 3,
        "title": "Pigeonhole Principle",
        "question": (
            "Among any 5 points placed inside a unit square (including boundary),\n"
            "prove that at least two points are within distance √2/2 of each other."
        ),
        "solution_book": (
            "Divide the unit square into 4 sub-squares of side 1/2.\n"
            "By the Pigeonhole Principle, since we place 5 points into 4 sub-squares,\n"
            "at least one sub-square contains at least 2 points.\n"
            "The diameter of a 1/2 × 1/2 square is (1/2)√2 = √2/2.\n"
            "So these two points are within distance √2/2. □"
        ),
        "problem_type": ProblemType.PROOF,
        "difficulty": DifficultyLevel.MEDIUM,
        "topics": ["pigeonhole_principle", "combinatorics", "geometry"],
    },
    {
        "id": "adler_c3_p4_derangements",
        "chapter": "Chapter 3: Combinatorics and Counting",
        "chapter_number": 3,
        "problem_number": 4,
        "title": "Derangements",
        "question": (
            "A derangement of n objects is a permutation where no element appears in its original position.\n"
            "Find a formula for D(n), the number of derangements of n elements.\n"
            "Compute D(4)."
        ),
        "solution_book": (
            "By inclusion-exclusion: D(n) = n! × Σₖ₌₀ⁿ (-1)ᵏ / k!\n"
            "= n! × (1 - 1/1! + 1/2! - 1/3! + ... + (-1)ⁿ/n!)\n\n"
            "For n = 4:\n"
            "D(4) = 4! × (1 - 1 + 1/2 - 1/6 + 1/24) = 24 × (12/24 - 4/24 + 1/24) = 24 × 9/24 = 9."
        ),
        "problem_type": ProblemType.COMBINATORIAL,
        "difficulty": DifficultyLevel.MEDIUM_HARD,
        "topics": ["derangements", "inclusion_exclusion", "permutations"],
        "numerical_answer": "D(4) = 9",
    },
]

# ---------------------------------------------------------------------------
# Chapter 4: Algebra — Equations and Inequalities
# ---------------------------------------------------------------------------
_CH4_PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "adler_c4_p1_factoring",
        "chapter": "Chapter 4: Algebra — Equations and Inequalities",
        "chapter_number": 4,
        "problem_number": 1,
        "title": "Cyclic Polynomial Factoring",
        "question": (
            "Factor the polynomial expression without expanding:\n"
            "A(x, y, z) = x(y - z)³ + y(z - x)³ + z(x - y)³"
        ),
        "solution_book": (
            "Think of A as a polynomial P(x) in x, fixing y, z.\n"
            "Note P(y) = y(y-z)³ + y(z-y)³ + z(y-y)³ = y(y-z)³ - y(y-z)³ + 0 = 0.\n"
            "By the Factor Theorem, (x - y) divides P(x), hence divides A.\n"
            "By cyclic symmetry in (x,y,z), (y-z) and (z-x) also divide A.\n"
            "Since A is homogeneous of degree 4, A = (x-y)(y-z)(z-x)·Q(x,y,z),\n"
            "where Q must be homogeneous of degree 1: Q = k(x+y+z).\n"
            "Setting x=0, y=1, z=2: A(0,1,2) = 1·8 + 2·(-1) = 6.\n"
            "Factored: (0-1)(1-2)(2-0)·k(3) = 6k = 6 ⟹ k = 1.\n"
            "So A(x,y,z) = (x-y)(y-z)(z-x)(x+y+z)."
        ),
        "problem_type": ProblemType.SYMBOLIC,
        "difficulty": DifficultyLevel.MEDIUM_HARD,
        "topics": ["factoring", "factor_theorem", "cyclic_symmetry", "homogeneous_polynomials"],
        "numerical_answer": "(x-y)(y-z)(z-x)(x+y+z)",
    },
    {
        "id": "adler_c4_p2_amgm",
        "chapter": "Chapter 4: Algebra — Equations and Inequalities",
        "chapter_number": 4,
        "problem_number": 2,
        "title": "AM-GM Inequality",
        "question": (
            "Prove that for positive reals a₁, a₂, ..., aₙ:\n"
            "(a₁ + a₂ + ... + aₙ)/n ≥ (a₁·a₂·...·aₙ)^(1/n)\n"
            "with equality iff a₁ = a₂ = ... = aₙ."
        ),
        "solution_book": (
            "Proof by induction on n.\n"
            "Base n=2: (a+b)/2 ≥ √(ab) ⟺ (√a - √b)² ≥ 0. ✓\n\n"
            "Inductive step: Assume true for n-1. Given a₁,...,aₙ with A=(a₁+...+aₙ)/n.\n"
            "Replace aₙ with A (sum unchanged, A still = A). Apply inductive hypothesis:\n"
            "(a₁+...+aₙ₋₁+A)/n ≥ (a₁...aₙ₋₁·A)^(1/n) ⟹ A ≥ (a₁...aₙ₋₁·A)^(1/n).\n"
            "So Aⁿ ≥ a₁...aₙ₋₁·A ⟹ Aⁿ⁻¹ ≥ a₁...aₙ₋₁.\n"
            "Since Aⁿ = (a₁...aₙ₋₁)(aₙ · Aⁿ⁻¹/a₁...aₙ₋₁) ≥ a₁...aₙ. □"
        ),
        "problem_type": ProblemType.PROOF,
        "difficulty": DifficultyLevel.MEDIUM_HARD,
        "topics": ["am_gm_inequality", "induction", "inequalities"],
    },
    {
        "id": "adler_c4_p3_quadratic_ineq",
        "chapter": "Chapter 4: Algebra — Equations and Inequalities",
        "chapter_number": 4,
        "problem_number": 3,
        "title": "Quadratic Inequality",
        "question": "Solve: x² - 5x + 6 < 0",
        "solution_book": (
            "Factor: x² - 5x + 6 = (x - 2)(x - 3).\n"
            "The inequality (x-2)(x-3) < 0 holds when one factor is positive, one negative.\n"
            "Case: x - 2 > 0 and x - 3 < 0 ⟹ 2 < x < 3.\n"
            "Case: x - 2 < 0 and x - 3 > 0 ⟹ impossible.\n"
            "Solution: 2 < x < 3, i.e., x ∈ (2, 3)."
        ),
        "problem_type": ProblemType.SYMBOLIC,
        "difficulty": DifficultyLevel.EASY,
        "topics": ["quadratic_inequalities", "factoring", "sign_analysis"],
        "numerical_answer": "x ∈ (2, 3)",
    },
    {
        "id": "adler_c4_p4_symmetric",
        "chapter": "Chapter 4: Algebra — Equations and Inequalities",
        "chapter_number": 4,
        "problem_number": 4,
        "title": "Symmetric System of Equations",
        "question": (
            "Solve the system:\n"
            "  x + y = 5\n"
            "  x² + y² = 13"
        ),
        "solution_book": (
            "From x + y = 5: (x+y)² = 25 ⟹ x² + 2xy + y² = 25.\n"
            "Since x² + y² = 13: 13 + 2xy = 25 ⟹ xy = 6.\n"
            "So x, y are roots of t² - 5t + 6 = 0 = (t-2)(t-3).\n"
            "Solutions: (x, y) = (2, 3) or (3, 2)."
        ),
        "problem_type": ProblemType.SYMBOLIC,
        "difficulty": DifficultyLevel.MEDIUM_EASY,
        "topics": ["symmetric_functions", "systems_of_equations", "vieta_formulas"],
        "numerical_answer": "(x, y) = (2, 3) or (3, 2)",
    },
    {
        "id": "adler_c4_p5_cauchy_schwarz",
        "chapter": "Chapter 4: Algebra — Equations and Inequalities",
        "chapter_number": 4,
        "problem_number": 5,
        "title": "Cauchy-Schwarz Inequality",
        "question": (
            "Prove the Cauchy-Schwarz inequality:\n"
            "(a₁b₁ + a₂b₂ + ... + aₙbₙ)² ≤ (a₁² + ... + aₙ²)(b₁² + ... + bₙ²)\n"
            "for real numbers aᵢ, bᵢ."
        ),
        "solution_book": (
            "Consider f(t) = Σ(aᵢt + bᵢ)² ≥ 0 for all real t.\n"
            "Expanding: (Σaᵢ²)t² + 2(Σaᵢbᵢ)t + (Σbᵢ²) ≥ 0.\n"
            "This quadratic in t has non-positive discriminant:\n"
            "4(Σaᵢbᵢ)² - 4(Σaᵢ²)(Σbᵢ²) ≤ 0.\n"
            "So (Σaᵢbᵢ)² ≤ (Σaᵢ²)(Σbᵢ²). □"
        ),
        "problem_type": ProblemType.PROOF,
        "difficulty": DifficultyLevel.MEDIUM_HARD,
        "topics": ["cauchy_schwarz", "inequalities", "inner_product"],
        "lean4_template": (
            "theorem cauchy_schwarz (n : ℕ) (a b : Fin n → ℝ) :\n"
            "  (∑ i, a i * b i)^2 ≤ (∑ i, a i ^ 2) * (∑ i, b i ^ 2) := by\n"
            "  sorry"
        ),
    },
]

# ---------------------------------------------------------------------------
# Chapter 5: Trigonometric Functions
# ---------------------------------------------------------------------------
_CH5_PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "adler_c5_p1_arcsin_eq",
        "chapter": "Chapter 5: Trigonometric Functions",
        "chapter_number": 5,
        "problem_number": 1,
        "title": "Inverse Sine Equation",
        "question": "Solve the real equation: arcsin(x) + arcsin(2x) = π/2",
        "solution_book": (
            "Let y = arcsin(x), z = arcsin(2x). Then y + z = π/2, so y = π/2 - z.\n"
            "Taking sines: sin(y) = sin(π/2 - z) = cos(z).\n"
            "sin(y) = x and sin(z) = 2x, so cos(z) = √(1 - 4x²) (since z ∈ [-π/2, π/2]).\n"
            "Thus x = √(1 - 4x²). Since RHS ≥ 0, x > 0.\n"
            "Squaring: x² = 1 - 4x² ⟹ 5x² = 1 ⟹ x = 1/√5.\n"
            "Verification: arcsin(1/√5) + arcsin(2/√5) = π/2 ✓ (since sin²+cos²=1).\n"
            "Solution: x = 1/√5 ≈ 0.4472."
        ),
        "problem_type": ProblemType.TRIGONOMETRIC,
        "difficulty": DifficultyLevel.MEDIUM_HARD,
        "topics": ["inverse_trig", "arcsin", "trigonometric_equations"],
        "numerical_answer": "x = 1/√5 ≈ 0.4472",
    },
    {
        "id": "adler_c5_p2_trig_identity",
        "chapter": "Chapter 5: Trigonometric Functions",
        "chapter_number": 5,
        "problem_number": 2,
        "title": "Double Angle Identity Proof",
        "question": "Prove: sin(2θ) = 2sin(θ)cos(θ) using the addition formula for sin.",
        "solution_book": (
            "Using the addition formula sin(α + β) = sin α cos β + cos α sin β:\n"
            "sin(2θ) = sin(θ + θ) = sin θ cos θ + cos θ sin θ = 2 sin θ cos θ. □"
        ),
        "problem_type": ProblemType.PROOF,
        "difficulty": DifficultyLevel.EASY,
        "topics": ["trigonometric_identities", "double_angle", "addition_formulas"],
    },
    {
        "id": "adler_c5_p3_law_cosines",
        "chapter": "Chapter 5: Trigonometric Functions",
        "chapter_number": 5,
        "problem_number": 3,
        "title": "Law of Cosines Application",
        "question": (
            "In triangle ABC, a = 7, b = 10, C = 60°.\n"
            "Find side c and angles A, B."
        ),
        "solution_book": (
            "By the Law of Cosines: c² = a² + b² - 2ab·cos(C)\n"
            "c² = 49 + 100 - 2(7)(10)(1/2) = 149 - 70 = 79.\n"
            "c = √79 ≈ 8.888.\n\n"
            "By Law of Sines: sin(A)/a = sin(C)/c ⟹ sin(A) = 7·sin(60°)/√79 = 7√3/(2√79).\n"
            "A = arcsin(7√3/(2√79)) ≈ arcsin(0.6820) ≈ 43.0°.\n"
            "B = 180° - 60° - 43.0° ≈ 77.0°."
        ),
        "problem_type": ProblemType.NUMERIC,
        "difficulty": DifficultyLevel.MEDIUM,
        "topics": ["law_of_cosines", "law_of_sines", "triangle_geometry"],
        "numerical_answer": "c = √79 ≈ 8.89, A ≈ 43.0°, B ≈ 77.0°",
    },
    {
        "id": "adler_c5_p4_product_to_sum",
        "chapter": "Chapter 5: Trigonometric Functions",
        "chapter_number": 5,
        "problem_number": 4,
        "title": "Product-to-Sum and Telescoping",
        "question": (
            "Compute the product:\n"
            "P = sin(π/7)·sin(2π/7)·sin(3π/7)"
        ),
        "solution_book": (
            "Use the identity: Π_{k=1}^{(n-1)/2} sin(kπ/n) = √n / 2^((n-1)/2) for odd prime n.\n"
            "For n = 7: sin(π/7)·sin(2π/7)·sin(3π/7) = √7 / 8.\n\n"
            "Alternative: Use Chebyshev polynomials. The roots of U₆(cos θ)=0 give sin(kπ/7).\n"
            "Product of roots analysis yields the same result: √7/8 ≈ 0.3307."
        ),
        "problem_type": ProblemType.NUMERIC,
        "difficulty": DifficultyLevel.HARD,
        "topics": ["product_formulas", "chebyshev_polynomials", "trigonometric_products"],
        "numerical_answer": "√7/8 ≈ 0.3307",
    },
]

# ---------------------------------------------------------------------------
# Chapter 6: Analytic Geometry and Calculus
# ---------------------------------------------------------------------------
_CH6_PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "adler_c6_p1_optimization",
        "chapter": "Chapter 6: Analytic Geometry and Calculus",
        "chapter_number": 6,
        "problem_number": 1,
        "title": "Maximum Area Rectangle",
        "question": (
            "Among all rectangles with a fixed perimeter P, find the one with maximum area.\n"
            "Prove your answer."
        ),
        "solution_book": (
            "Let the sides be x and P/2 - x (since 2x + 2y = P ⟹ y = P/2 - x).\n"
            "Area A(x) = x(P/2 - x) = Px/2 - x² for x ∈ (0, P/2).\n"
            "A'(x) = P/2 - 2x = 0 ⟹ x = P/4.\n"
            "A''(x) = -2 < 0, confirming maximum.\n"
            "So the rectangle is a square with side P/4, and max area = (P/4)² = P²/16.\n"
            "Alternatively, by AM-GM: xy ≤ ((x+y)/2)² = (P/4)²."
        ),
        "problem_type": ProblemType.OPTIMIZATION,
        "difficulty": DifficultyLevel.MEDIUM_EASY,
        "topics": ["calculus", "optimization", "quadratic_functions", "am_gm"],
        "numerical_answer": "Max area = P²/16 (square with side P/4)",
    },
    {
        "id": "adler_c6_p2_limit",
        "chapter": "Chapter 6: Analytic Geometry and Calculus",
        "chapter_number": 6,
        "problem_number": 2,
        "title": "Limit Computation",
        "question": "Compute: lim_{x→0} (sin x - x) / x³",
        "solution_book": (
            "Using L'Hôpital's rule three times (0/0 form at each step):\n"
            "1st: (cos x - 1) / (3x²)\n"
            "2nd: (-sin x) / (6x)\n"
            "3rd: (-cos x) / 6\n"
            "As x→0: (-cos 0)/6 = -1/6.\n\n"
            "Alternatively, Taylor series: sin x = x - x³/6 + O(x⁵).\n"
            "sin x - x = -x³/6 + O(x⁵).\n"
            "(sin x - x)/x³ → -1/6."
        ),
        "problem_type": ProblemType.NUMERIC,
        "difficulty": DifficultyLevel.MEDIUM,
        "topics": ["limits", "lhopital_rule", "taylor_series"],
        "numerical_answer": "-1/6",
    },
    {
        "id": "adler_c6_p3_integral",
        "chapter": "Chapter 6: Analytic Geometry and Calculus",
        "chapter_number": 6,
        "problem_number": 3,
        "title": "Definite Integral by Parts",
        "question": "Compute: ∫₀^π x·sin(x) dx",
        "solution_book": (
            "Integration by parts: u = x, dv = sin(x)dx, du = dx, v = -cos(x).\n"
            "∫₀^π x sin(x) dx = [-x cos(x)]₀^π + ∫₀^π cos(x) dx\n"
            "= -π cos(π) + 0 + [sin(x)]₀^π\n"
            "= -π(-1) + (sin π - sin 0)\n"
            "= π + 0 = π."
        ),
        "problem_type": ProblemType.NUMERIC,
        "difficulty": DifficultyLevel.MEDIUM,
        "topics": ["integration_by_parts", "definite_integrals", "calculus"],
        "numerical_answer": "π",
    },
    {
        "id": "adler_c6_p4_derivative_app",
        "chapter": "Chapter 6: Analytic Geometry and Calculus",
        "chapter_number": 6,
        "problem_number": 4,
        "title": "Related Rates",
        "question": (
            "A spherical balloon is being inflated at a rate of 10 cm³/s.\n"
            "Find the rate at which the radius is increasing when the radius is 5 cm."
        ),
        "solution_book": (
            "Volume of sphere: V = (4/3)πr³.\n"
            "Differentiating with respect to time t:\n"
            "dV/dt = 4πr² · dr/dt.\n"
            "We know dV/dt = 10 cm³/s and r = 5 cm:\n"
            "10 = 4π(25) · dr/dt ⟹ dr/dt = 10/(100π) = 1/(10π) cm/s ≈ 0.0318 cm/s."
        ),
        "problem_type": ProblemType.NUMERIC,
        "difficulty": DifficultyLevel.MEDIUM,
        "topics": ["related_rates", "differentiation", "calculus", "geometry"],
        "numerical_answer": "dr/dt = 1/(10π) ≈ 0.0318 cm/s",
    },
]

# ---------------------------------------------------------------------------
# Chapter 7: Probability and Statistics
# ---------------------------------------------------------------------------
_CH7_PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "adler_c7_p1_conditional",
        "chapter": "Chapter 7: Probability and Statistics",
        "chapter_number": 7,
        "problem_number": 1,
        "title": "Conditional Probability",
        "question": (
            "A bag contains 3 red and 2 blue balls. Two balls are drawn without replacement.\n"
            "(a) What is the probability both are red?\n"
            "(b) Given the first ball drawn is red, what is the probability the second is also red?"
        ),
        "solution_book": (
            "(a) P(both red) = C(3,2)/C(5,2) = 3/10.\n\n"
            "(b) P(2nd red | 1st red) = P(1st and 2nd red) / P(1st red)\n"
            "= (3/5 · 2/4) / (3/5) = (6/20)/(3/5) = (3/10)/(3/5) = 1/2.\n"
            "Or directly: given first is red, 2 red remain out of 4 total → P = 2/4 = 1/2."
        ),
        "problem_type": ProblemType.PROBABILITY,
        "difficulty": DifficultyLevel.EASY,
        "topics": ["probability", "conditional_probability", "combinations"],
        "numerical_answer": "(a) 3/10; (b) 1/2",
    },
    {
        "id": "adler_c7_p2_bayes",
        "chapter": "Chapter 7: Probability and Statistics",
        "chapter_number": 7,
        "problem_number": 2,
        "title": "Bayes' Theorem",
        "question": (
            "A disease affects 1% of the population. A test for the disease is:\n"
            "- 95% accurate if the person has the disease (true positive rate)\n"
            "- 90% accurate if the person does not have the disease (true negative rate)\n"
            "If a person tests positive, what is the probability they actually have the disease?"
        ),
        "solution_book": (
            "Let D = has disease, T = tests positive.\n"
            "P(D) = 0.01, P(T|D) = 0.95, P(T|¬D) = 0.10 (false positive rate).\n"
            "By Bayes' theorem:\n"
            "P(D|T) = P(T|D)·P(D) / P(T)\n"
            "P(T) = P(T|D)P(D) + P(T|¬D)P(¬D) = 0.95×0.01 + 0.10×0.99 = 0.0095 + 0.099 = 0.1085.\n"
            "P(D|T) = 0.0095 / 0.1085 ≈ 0.0876 ≈ 8.76%."
        ),
        "problem_type": ProblemType.PROBABILITY,
        "difficulty": DifficultyLevel.MEDIUM_HARD,
        "topics": ["bayes_theorem", "conditional_probability", "statistics"],
        "numerical_answer": "≈ 8.76%",
    },
    {
        "id": "adler_c7_p3_birthday",
        "chapter": "Chapter 7: Probability and Statistics",
        "chapter_number": 7,
        "problem_number": 3,
        "title": "Birthday Problem",
        "question": (
            "How many people do we need in a room so that the probability of at least two people\n"
            "sharing the same birthday exceeds 50%? (Assume 365 equally likely birthdays.)"
        ),
        "solution_book": (
            "Let P(n) = probability at least 2 share a birthday with n people.\n"
            "P(n) = 1 - 365/365 · 364/365 · ... · (365-n+1)/365 = 1 - 365!/(365-n)!/365ⁿ.\n"
            "Computing iteratively:\n"
            "n=22: P(22) ≈ 1 - 0.5243 = 0.4757 < 50%\n"
            "n=23: P(23) ≈ 1 - 0.4927 = 0.5073 > 50%.\n"
            "Answer: 23 people."
        ),
        "problem_type": ProblemType.PROBABILITY,
        "difficulty": DifficultyLevel.MEDIUM,
        "topics": ["birthday_problem", "probability", "combinatorics"],
        "numerical_answer": "23 people",
    },
]

# ---------------------------------------------------------------------------
# Chapter 8: Sequences, Series and Recurrences
# ---------------------------------------------------------------------------
_CH8_PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "adler_c8_p1_geometric_series",
        "chapter": "Chapter 8: Sequences, Series and Recurrences",
        "chapter_number": 8,
        "problem_number": 1,
        "title": "Geometric Series Sum",
        "question": (
            "Find the sum of the infinite geometric series: 1 + 1/2 + 1/4 + 1/8 + ...\n"
            "For what values of r does the series a + ar + ar² + ar³ + ... converge?"
        ),
        "solution_book": (
            "For the given series: a = 1, r = 1/2.\n"
            "Sum = a/(1-r) = 1/(1-1/2) = 2.\n\n"
            "In general, the geometric series Σ_{n=0}^∞ ar^n converges iff |r| < 1.\n"
            "When it converges: Sum = a/(1-r)."
        ),
        "problem_type": ProblemType.SEQUENCE,
        "difficulty": DifficultyLevel.EASY,
        "topics": ["geometric_series", "infinite_series", "convergence"],
        "numerical_answer": "Sum = 2; converges for |r| < 1",
    },
    {
        "id": "adler_c8_p2_fibonacci",
        "chapter": "Chapter 8: Sequences, Series and Recurrences",
        "chapter_number": 8,
        "problem_number": 2,
        "title": "Fibonacci Closed Form",
        "question": (
            "The Fibonacci sequence is defined by F(0) = 0, F(1) = 1, F(n) = F(n-1) + F(n-2).\n"
            "Derive Binet's formula: F(n) = (φⁿ - ψⁿ)/√5\n"
            "where φ = (1+√5)/2 and ψ = (1-√5)/2."
        ),
        "solution_book": (
            "The characteristic equation of F(n) = F(n-1) + F(n-2) is r² = r + 1.\n"
            "Roots: r = (1 ± √5)/2, i.e., φ and ψ.\n"
            "General solution: F(n) = Aφⁿ + Bψⁿ.\n"
            "Applying initial conditions:\n"
            "F(0) = 0: A + B = 0 ⟹ B = -A.\n"
            "F(1) = 1: Aφ + Bψ = A(φ - ψ) = A√5 = 1 ⟹ A = 1/√5.\n"
            "Therefore F(n) = (φⁿ - ψⁿ)/√5. □"
        ),
        "problem_type": ProblemType.SEQUENCE,
        "difficulty": DifficultyLevel.MEDIUM_HARD,
        "topics": ["fibonacci", "recurrence_relations", "characteristic_roots", "closed_form"],
    },
    {
        "id": "adler_c8_p3_telescoping",
        "chapter": "Chapter 8: Sequences, Series and Recurrences",
        "chapter_number": 8,
        "problem_number": 3,
        "title": "Telescoping Sum",
        "question": "Compute: Σ_{k=1}^{n} 1/(k(k+1))",
        "solution_book": (
            "Partial fraction decomposition: 1/(k(k+1)) = 1/k - 1/(k+1).\n"
            "The sum telescopes:\n"
            "Σ_{k=1}^{n} (1/k - 1/(k+1)) = (1/1 - 1/2) + (1/2 - 1/3) + ... + (1/n - 1/(n+1))\n"
            "= 1 - 1/(n+1) = n/(n+1)."
        ),
        "problem_type": ProblemType.SEQUENCE,
        "difficulty": DifficultyLevel.MEDIUM_EASY,
        "topics": ["telescoping_sums", "partial_fractions", "series"],
        "numerical_answer": "n/(n+1)",
    },
    {
        "id": "adler_c8_p4_induction_sum",
        "chapter": "Chapter 8: Sequences, Series and Recurrences",
        "chapter_number": 8,
        "problem_number": 4,
        "title": "Sum of Squares by Induction",
        "question": (
            "Prove by mathematical induction:\n"
            "1² + 2² + 3² + ... + n² = n(n+1)(2n+1)/6"
        ),
        "solution_book": (
            "Base case n=1: LHS = 1. RHS = 1·2·3/6 = 1. ✓\n\n"
            "Inductive step: Assume 1² + ... + k² = k(k+1)(2k+1)/6.\n"
            "Show: 1² + ... + k² + (k+1)² = (k+1)(k+2)(2k+3)/6.\n"
            "LHS = k(k+1)(2k+1)/6 + (k+1)²\n"
            "= (k+1)[k(2k+1)/6 + (k+1)]\n"
            "= (k+1)[(k(2k+1) + 6(k+1))/6]\n"
            "= (k+1)(2k² + 7k + 6)/6\n"
            "= (k+1)(k+2)(2k+3)/6. ✓ □"
        ),
        "problem_type": ProblemType.PROOF,
        "difficulty": DifficultyLevel.MEDIUM,
        "topics": ["mathematical_induction", "sum_of_squares", "number_theory"],
        "lean4_template": (
            "theorem sum_squares (n : ℕ) : ∑ i in Finset.range (n+1), i^2 = n*(n+1)*(2*n+1)/6 := by\n"
            "  sorry"
        ),
    },
]

# ---------------------------------------------------------------------------
# Merge all problems into one flat list
# ---------------------------------------------------------------------------
_ALL_CHAPTERS: list[list[dict[str, Any]]] = [
    _CH1_PROBLEMS,
    _CH2_PROBLEMS,
    _CH3_PROBLEMS,
    _CH4_PROBLEMS,
    _CH5_PROBLEMS,
    _CH6_PROBLEMS,
    _CH7_PROBLEMS,
    _CH8_PROBLEMS,
]


def _build_all() -> list[OlympiadProblemRecord]:
    records: list[OlympiadProblemRecord] = []
    for chapter_list in _ALL_CHAPTERS:
        for prob in chapter_list:
            records.append(
                OlympiadProblemRecord(
                    id=prob["id"],
                    chapter=prob["chapter"],
                    chapter_number=prob["chapter_number"],
                    problem_number=prob["problem_number"],
                    title=prob["title"],
                    question=prob["question"],
                    solution_book=prob["solution_book"],
                    problem_type=prob["problem_type"],
                    difficulty=prob["difficulty"],
                    topics=prob.get("topics", []),
                    numerical_answer=prob.get("numerical_answer"),
                    lean4_template=prob.get("lean4_template"),
                    comments=prob.get("comments", ""),
                )
            )
    return records


ADLER_PROBLEMS_ALL: list[OlympiadProblemRecord] = _build_all()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_problems_by_chapter(chapter_number: int) -> list[OlympiadProblemRecord]:
    """Return all problems from a given chapter (1-indexed)."""
    return [p for p in ADLER_PROBLEMS_ALL if p.chapter_number == chapter_number]


def get_problems_by_difficulty(
    level: DifficultyLevel,
) -> list[OlympiadProblemRecord]:
    """Return all problems at a given difficulty level."""
    return [p for p in ADLER_PROBLEMS_ALL if p.difficulty == level]


def get_problems_by_type(
    problem_type: ProblemType,
) -> list[OlympiadProblemRecord]:
    """Return all problems of a given type."""
    return [p for p in ADLER_PROBLEMS_ALL if p.problem_type == problem_type]


if __name__ == "__main__":
    print(f"Total Adler problems loaded: {len(ADLER_PROBLEMS_ALL)}")
    for ch in range(1, 9):
        probs = get_problems_by_chapter(ch)
        if probs:
            print(f"  Chapter {ch}: {len(probs)} problems")
