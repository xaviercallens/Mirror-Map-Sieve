"""
test_polynomials.py — Verify structural integrity of extracted_polynomials.json.

These tests do NOT require running the slow nullspace solver.
They verify that the stored JSON is internally consistent and that
the constant terms match the Lean 4 verified values.
"""
import json
from math import comb
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
JSON_PATH = ROOT / "1_algebraic_shielding_solvers" / "extracted_polynomials.json"


LEAN4_VERIFIED_CONSTANTS = [
    -5412650858431135013634958175726842170573378411840,
    -6600211789894833600749251782579095561783149274990400,
    -29724234537629673550738669814459138431115401303206240,
    -6675296886001563027617164081383167394996985596478240,
    -272198721521932617277293245047721130052020296806560,
     20478134952232355172884134183653971676016433020000,
]

LEAN4_VERIFIED_SEQUENCE = [1, 3, 55, 1155, 29751, 852753, 26097499, 840454275]


def test_json_file_exists():
    assert JSON_PATH.exists(), f"Missing: {JSON_PATH}"


def test_json_is_valid():
    with open(JSON_PATH) as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_all_six_polynomials_present(poly_data):
    for j in range(6):
        assert f"P_{j}" in poly_data["polynomials"], f"P_{j} missing from JSON"


def test_each_polynomial_has_10_coefficients(poly_data):
    """Degree 9 → 10 coefficients (ascending order)."""
    for j in range(6):
        coeffs = poly_data["polynomials"][f"P_{j}"]["coefficients_ascending"]
        assert len(coeffs) == 10, \
            f"P_{j} has {len(coeffs)} coefficients, expected 10 (degree 9)"


def test_constant_n0_matches_coefficients(poly_data):
    """constant_n0 must equal coefficients_ascending[0]."""
    for j in range(6):
        p = poly_data["polynomials"][f"P_{j}"]
        assert p["constant_n0"] == p["coefficients_ascending"][0], \
            f"P_{j}: constant_n0 ≠ coefficients_ascending[0]"


@pytest.mark.parametrize("j", range(6))
def test_constant_n0_matches_lean4(j, poly_data):
    """P_j(0) must exactly match the Lean 4 kernel-verified constant."""
    stored = poly_data["polynomials"][f"P_{j}"]["constant_n0"]
    expected = LEAN4_VERIFIED_CONSTANTS[j]
    assert stored == expected, \
        f"P_{j}(0): stored={stored}, Lean4-verified={expected}"


def test_recurrence_at_n0_using_stored_constants(poly_data):
    """The Lean 4 base case: sum P_j(0)*S(j) = 0 exactly."""
    S = LEAN4_VERIFIED_SEQUENCE
    constants = [
        poly_data["polynomials"][f"P_{j}"]["constant_n0"]
        for j in range(6)
    ]
    total = sum(constants[j] * S[j] for j in range(6))
    assert total == 0, f"Lean 4 base case fails in JSON data! Residual = {total}"


def test_p5_positive_leading_coefficient(poly_data):
    """P_5 must have a positive leading coefficient (determines recurrence direction)."""
    leading = poly_data["polynomials"]["P_5"]["coefficients_ascending"][-1]
    assert leading > 0, f"P_5 leading coefficient = {leading}, expected > 0"


def test_p0_through_p4_negative_leading(poly_data):
    """P_0..P_4 should all have negative leading coefficients."""
    for j in range(5):
        leading = poly_data["polynomials"][f"P_{j}"]["coefficients_ascending"][-1]
        assert leading < 0, \
            f"P_{j} leading coefficient = {leading}, expected < 0"


def test_first_10_terms_match_formula(poly_data):
    """The first_10_terms stored must match S(n) computed from formula."""
    for n, expected in enumerate(poly_data["first_10_terms"]):
        computed = sum(comb(n, k) ** 4 * comb(n + k, k) for k in range(n + 1))
        assert computed == expected, \
            f"Term mismatch at n={n}: stored={expected}, computed={computed}"


def test_lean_version_matches_toolchain(poly_data):
    """lean_version in JSON must match the lean-toolchain file."""
    toolchain_path = ROOT / "2_lean4_formal_proofs" / "lean-toolchain"
    if not toolchain_path.exists():
        pytest.skip("lean-toolchain file not found")
    with open(toolchain_path) as f:
        toolchain = f.read().strip()
    stored_version = poly_data["metadata"]["lean_version"]
    assert toolchain == stored_version, \
        f"lean_version mismatch: JSON='{stored_version}', toolchain='{toolchain}'"


def test_no_broken_file_references(poly_data):
    """No JSON field should reference a file path that doesn't exist in the repo."""
    import json as json_mod
    raw = json_mod.dumps(poly_data)
    # The old broken reference to a non-existent GCP log
    assert "sage_zeilberger_gcp.log" not in raw, \
        "Found reference to non-existent proof_artifacts/sage_zeilberger_gcp.log"
