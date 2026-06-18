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
