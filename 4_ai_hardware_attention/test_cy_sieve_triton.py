#!/usr/bin/env python3
"""
test_cy_sieve_triton.py — tests.md §4 T4.1: Triton kernel ↔ CPU reference parity.

These tests AUTO-SKIP on a CPU-only machine (no CUDA/Triton), so the suite stays
green everywhere; they run for real on the GPU box. The CPU reference
`cy_sieve_attention.flash_sdpa_with_bias` is the parity oracle (it already
matches the dense softmax to ~3e-16 on CPU).
"""
from __future__ import annotations
import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_reference as cy
import cy_sieve_attention as att
import cy_sieve_triton as tri

pytestmark = pytest.mark.skipif(
    not tri.HAS_TRITON,
    reason="Triton/CUDA unavailable (CPU-only); GPU-phase parity test.")


@pytest.mark.parametrize("L,D,tau", [(128, 64, 20.0), (256, 64, 128.0),
                                     (256, 128, 480.0)])
def test_t4_1_triton_matches_reference(L, D, tau):
    """Triton kernel output matches the NumPy CPU reference within FP16/BF16
    tolerance (relative ~2^-8 as specified in tests.md §4)."""
    import torch
    g = torch.Generator(device="cuda").manual_seed(L + D)
    Q = torch.randn(L, D, device="cuda", generator=g)
    K = torch.randn(L, D, device="cuda", generator=g)
    V = torch.randn(L, D, device="cuda", generator=g)
    bias = torch.tensor(cy.build_bias_vector(L, "S20", tau)[:L],
                        device="cuda", dtype=torch.float32)
    out_tri = tri.cy_sieve_attention_triton(Q, K, V, bias, causal=True).cpu().numpy()

    out_ref = att.flash_sdpa_with_bias(Q.cpu().numpy().astype(np.float64),
                                       K.cpu().numpy().astype(np.float64),
                                       V.cpu().numpy().astype(np.float64),
                                       seq="S20", tau=tau, causal=True)
    rel = np.max(np.abs(out_tri - out_ref)) / (np.max(np.abs(out_ref)) + 1e-9)
    assert rel < 2 ** -8, f"Triton vs reference rel.err {rel:.2e} exceeds 2^-8"


def test_t4_1_smoke():
    """Kernel runs and returns finite, correctly-shaped output."""
    import torch
    L, D = 96, 64
    g = torch.Generator(device="cuda").manual_seed(1)
    Q, K, V = (torch.randn(L, D, device="cuda", generator=g) for _ in range(3))
    bias = torch.tensor(cy.build_bias_vector(L, "S20", 128.0)[:L],
                        device="cuda", dtype=torch.float32)
    out = tri.cy_sieve_attention_triton(Q, K, V, bias)
    assert out.shape == (L, D) and torch.isfinite(out).all()


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["pytest", "-v", __file__]))
