# Mirror Map Sieve — Test Plan

## Current State: No Tests Exist ❌
There is no `tests/` directory. The CI runs Python scripts as integration tests,
but has no assertion framework, no unit tests, and cannot detect silent failures.

---

## Proposed Test Architecture

### Level 1: Unit Tests (pytest)

```
tests/
├── test_sequence.py        # Verify S(n) computation
├── test_recurrence.py      # Verify recurrence at multiple n values
├── test_mirror_map.py      # Verify q_d integrality and values
├── test_polynomials.py     # Verify polynomial data integrity
└── conftest.py             # Shared fixtures
```

### test_sequence.py
```python
"""Test exact computation of S(n) = sum C(n,k)^4 * C(n+k,k)."""
import pytest
from math import comb

def compute_s20(n):
    return sum(comb(n, k)**4 * comb(n + k, k) for k in range(n + 1))

KNOWN_VALUES = {0: 1, 1: 3, 2: 55, 3: 1155, 4: 29751, 5: 852753,
                6: 26097499, 7: 840454275, 8: 28064517175, 9: 964417304253}

@pytest.mark.parametrize("n, expected", KNOWN_VALUES.items())
def test_s20_exact_value(n, expected):
    assert compute_s20(n) == expected

def test_s20_symmetry():
    """S(n) should always be odd for n >= 0."""
    for n in range(20):
        assert compute_s20(n) % 2 == 1
```

### test_recurrence.py
```python
"""Test the order-5 degree-9 recurrence at multiple values of n."""
import pytest
import json
from math import comb
from pathlib import Path

def compute_s20(n):
    return sum(comb(n, k)**4 * comb(n + k, k) for k in range(n + 1))

@pytest.fixture
def polynomials():
    path = Path(__file__).parent.parent / "1_algebraic_shielding_solvers" / "extracted_polynomials.json"
    with open(path) as f:
        data = json.load(f)
    polys = []
    for j in range(6):
        coeffs = data["polynomials"][f"P_{j}"]["coefficients_ascending"]
        polys.append(coeffs)
    return polys

@pytest.fixture
def sequence_values():
    return [compute_s20(n) for n in range(80)]

@pytest.mark.parametrize("n", range(70))
def test_recurrence_at_n(polynomials, sequence_values, n):
    """Recurrence sum_{j=0}^5 P_j(n) * S(n+j) = 0 must hold."""
    S = sequence_values
    total = 0
    for j in range(6):
        P_j_at_n = sum(c * (n ** i) for i, c in enumerate(polynomials[j]))
        total += P_j_at_n * S[n + j]
    assert total == 0, f"Recurrence fails at n={n}: residual = {total}"
```

### test_mirror_map.py
```python
"""Test Lian-Yau mirror map integrality."""
import pytest
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "3_mirror_map_geometry"))
from verify_mirror_map import compute_mirror_map

def test_mirror_map_all_integer():
    q = compute_mirror_map(16)
    for d in range(2, 17):
        assert q[d].denominator == 1, f"q_{d} = {q[d]} is not an integer"

def test_mirror_map_known_values():
    EXPECTED = {2: 9, 3: 165, 4: 4110, 5: 111075}
    q = compute_mirror_map(5)
    for d, expected in EXPECTED.items():
        assert int(q[d]) == expected
```

### test_polynomials.py
```python
"""Verify extracted_polynomials.json data integrity."""
import json, pytest
from pathlib import Path

def test_json_structure():
    path = Path(__file__).parent.parent / "1_algebraic_shielding_solvers" / "extracted_polynomials.json"
    with open(path) as f:
        data = json.load(f)
    for j in range(6):
        key = f"P_{j}"
        assert key in data["polynomials"]
        coeffs = data["polynomials"][key]["coefficients_ascending"]
        assert len(coeffs) == 10, f"{key} should have 10 coefficients (degree 9)"
        assert coeffs[0] == data["polynomials"][key]["constant_n0"]

def test_leading_polynomial_sign():
    """P_5 should have positive leading coefficient (determines growth)."""
    path = Path(__file__).parent.parent / "1_algebraic_shielding_solvers" / "extracted_polynomials.json"
    with open(path) as f:
        data = json.load(f)
    assert data["polynomials"]["P_5"]["coefficients_ascending"][-1] > 0

def test_first_10_terms():
    path = Path(__file__).parent.parent / "1_algebraic_shielding_solvers" / "extracted_polynomials.json"
    with open(path) as f:
        data = json.load(f)
    from math import comb
    for n, expected in enumerate(data["first_10_terms"]):
        computed = sum(comb(n,k)**4 * comb(n+k,k) for k in range(n+1))
        assert computed == expected
```

---

## CI Integration

Update `.github/workflows/ci.yml` to run:
```yaml
    - name: Run Unit Tests
      run: |
        pip install pytest
        pytest tests/ -v --tb=short
```

---

## Priority

| Test | Priority | Why |
|------|----------|-----|
| test_recurrence_at_n (70 values) | **P0** | Core mathematical claim |
| test_s20_exact_value | **P0** | Foundation of everything |
| test_mirror_map_all_integer | **P0** | Paper's Theorem 3 |
| test_json_structure | **P1** | Data integrity |
| test_first_10_terms | **P1** | Cross-check |

---
---

# CY-Sieve Attention Kernel — Validation Suite

> **Implementation status (2026-06-21).** Sections **§1–§3 are implemented and
> passing** in `4_ai_hardware_attention/test_cy_sieve.py` (30 tests, ~2 s,
> CPU-only) against the reference `4_ai_hardware_attention/cy_sieve_reference.py`,
> and run **blocking** in CI (`ci.yml`). Writing the tests **caught a real bug**:
> the naive $2^{32}$ fixed-point shift made the Tier-1 decay table underflow to
> $0$ by $d\approx8$ — fixed with `FIXED_POINT_SHIFT=62` (reciprocal window 13 for
> $S_{20}$, 15 for $S_{15}$). Sections **§4–§7 remain TODO** (they require a
> GPU/Triton kernel and a model — not runnable on a laptop).

This suite validates the applied CY-Sieve kernel (`vision.md`, `roadmap.md`).
**Guiding rule: a fast kernel that degrades model quality is a FAILED kernel.**
Every speed/HBM claim is meaningless unless the quality gate (§5) passes. Each
section lists an explicit **PASS criterion**; a tier that fails is reported as a
negative result, not shipped.

Reference numbers below were verified in this session (see git history of
`src/picard_fuchs/`): they are the ground truth the kernel must reproduce.

## §1 — Tier 1: exact INT64 local table

- **T1.1 Overflow boundary.** Assert $S_{20}(13) \le 2^{63}-1 < S_{20}(14)$, and
  $S_{15}(16)\le 2^{63}-1 < S_{15}(17)$. (These define the legal Tier-1 windows:
  13 for $S_{20}$, 16 for $S_{15}$.)
- **T1.2 Table values.** The preloaded reciprocal-decay table equals
  $\lfloor 2^{32}\,S_{20}(0)/S_{20}(d)\rfloor$ for $d=0..13$, computed from the
  exact integers. Bit-exact assertion against `math.comb` reference.
- **T1.3 Monotonic decay.** Table is strictly decreasing in $d$ (a positional
  *decay*), and table[0] is the max.
- **PASS:** all three exact; zero floating-point drift in the INT64 path
  (the cast to FP16 happens only after the exact integer division).

## §2 — Tier 2: recurrence-mod-$p$ generator (RESEARCH — currently failing)

- **T2.1 Generator correctness.** The on-the-fly recurrence-mod-$p$ value equals
  `S20(d) % p` computed directly, for all $d\le 4096$, $p\in\{251, 67, 17\}$.
  (Pure correctness of the finite-field generator — this MUST pass.)
- **T2.2 Keep-rule density (DIAGNOSTIC, documents the failure).** For the
  proposed rule "keep iff $S_{20}(d)\equiv0\ (p{=}251)$": assert measured density
  $\approx0.78\%$ and **nearest kept distance $=226$**. This test exists to
  *document why the proposed rule is unusable* (a token must not be starved of
  all context between $d=14$ and $d=226$).
- **T2.3 Redesign acceptance (future).** Any replacement router must, on a real
  eval, **match or beat a sliding-window mask of equal density** on perplexity.
  Until such a rule exists, **Tier 2 is DISABLED in the shipped kernel.**
- **PASS:** T2.1 passes (generator correct); T2.2 is informational; T2.3 gates
  any future Tier-2 activation.

## §3 — Tier 3: asymptotic log-space penalty

- **T3.1 Constants from theory, not fitting.** Use $\lambda=43.04432867\ldots$
  ($\log\lambda=3.7622\ldots$) and $\beta=2$ (the rank-4 MUM / CY-3-fold tail
  $n^{-2}$). Assert the kernel's constants match these to $10^{-6}$.
  **Reject** the proposal's $\log\lambda=2.456$, $\beta=1.5$ (wrong).
- **T3.2 Penalty tracks exact decay.** For $14\le d\le 200$, the asymptotic
  penalty $-d\log\lambda+\beta\log d - \log C$ approximates $-\log S_{20}(d)$
  with relative error decreasing in $d$; assert error $<5\%$ by $d=100$ and
  monotonically improving.
- **T3.3 Continuity at the handoff.** At the Tier-1↔Tier-3 boundary ($d=13\to14$)
  the bias is continuous within a fixed tolerance (no discontinuity that a model
  would see as a hard cliff).
- **PASS:** constants exact, error bound met, handoff continuous.

## §4 — Kernel ↔ reference parity

- **T4.1 Triton-vs-NumPy.** For random $Q,K,V$ (several shapes, seeded), the
  fused Triton kernel output matches the pure-NumPy CY-Sieve reference within
  FP16/BF16 tolerance ($\le 2^{-8}$ relative on attention rows).
- **T4.2 Row-stochastic.** Post-softmax attention rows sum to $1\pm10^{-5}$.
- **T4.3 Causality.** No attention weight to $j>i$ (causal mask intact).
- **PASS:** all three within tolerance on CPU (reference) and, when available,
  GPU (Triton).

## §5 — QUALITY GATE (the decisive test)

This is the test that decides whether the kernel has any value at all.

- **T5.1 Perplexity parity.** Patch CY-Sieve into a small open model
  (e.g. Phi-3-mini or GPT-2) and measure zero-shot perplexity on WikiText-2 and
  a long-context set, **against RoPE, ALiBi, and sliding-window** at matched
  compute and context length.
- **T5.2 Long-context retrieval.** Needle-in-a-haystack accuracy at 4K, 16K, 64K
  vs the same baselines.
- **PASS criterion:** CY-Sieve perplexity is **within +1%** of the best baseline
  (ideally lower) **and** retrieval accuracy is not worse beyond noise.
- **KILL criterion:** if perplexity regresses by **>5%** vs the best baseline, or
  retrieval collapses, the kernel (or the offending tier) is reported as a
  **negative result** and not presented as a contribution.

## §6 — Performance (only meaningful if §5 passes)

- **T6.1 HBM traffic.** Measure bytes read from HBM for the positional-bias path;
  CY-Sieve Tier-1/Tier-3 must be **0 bytes** of bias-table HBM (the core claim).
- **T6.2 Throughput / latency.** Prefill latency vs dense SDPA and vs RoPE at
  8K–128K, on a single named GPU, reported with hardware + driver + seed.
- **T6.3 No-overclaim guard.** Any speedup number is reported **alongside** the
  §5 quality result for the same configuration; speed is never reported alone.
- **PASS:** measurable HBM reduction with §5 quality preserved, fully reproducible.

## §7 — Honesty / reporting guards

- **T7.1** No result is described as "infinite extrapolation", "zero
  degradation", or "dominance" unless §5/§6 on real hardware support it; default
  language is "hypothesis / measured on <hardware>".
- **T7.2** $S_{20}$ vs any baseline: the README/paper must state that a similar
  reciprocal decay arises from **any** fast-growing sequence, so a positive
  result is evidence for *holonomic on-the-fly bias*, not uniquely for $S_{20}$.

## Priority

| Test | Priority | Why |
|------|----------|-----|
| §5 Quality gate (perplexity/retrieval) | **P0** | Decides if the kernel is worth anything |
| §1 Tier-1 exactness | **P0** | The solid, shippable piece |
| §3 Tier-3 constants ($\lambda,\beta$) | **P0** | Must use the theory-correct values |
| §4 Kernel↔reference parity | **P0** | Correctness before benchmarking |
| §2.1 mod-$p$ generator | **P1** | Needed if Tier-2 is ever revived |
| §6 Performance | **P1** | Only after §5 passes |
| §7 Honesty guards | **P0** | Project's core value |
