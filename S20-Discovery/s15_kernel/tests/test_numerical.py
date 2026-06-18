# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
"""Numerical stability and gradient tests for S20 attention."""

import pytest
import torch
import torch.nn.functional as F
from s15_kernel.patching import s20_scaled_dot_product_attention

def test_s20_gradients_flow():
    """Verify gradients flow through S20 attention without NaNs."""
    B, H, L, D = 2, 4, 32, 16
    q = torch.randn(B, H, L, D, requires_grad=True)
    k = torch.randn(B, H, L, D, requires_grad=True)
    v = torch.randn(B, H, L, D, requires_grad=True)

    out = s20_scaled_dot_product_attention(q, k, v, window_size=8, sequence_fn="s20")
    loss = out.sum()
    loss.backward()

    assert q.grad is not None
    assert k.grad is not None
    assert v.grad is not None
    assert not torch.isnan(q.grad).any()
    assert not torch.isnan(k.grad).any()
    assert not torch.isnan(v.grad).any()

@pytest.mark.parametrize("dtype", [torch.float32, torch.float16, torch.bfloat16])
def test_s20_dtypes(dtype):
    """Verify S20 attention runs stably in mixed precision."""
    if not torch.cuda.is_available() and dtype == torch.float16:
        pytest.skip("FP16 requires CUDA")
        
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    B, H, L, D = 1, 2, 64, 32
    q = torch.randn(B, H, L, D, device=device, dtype=dtype)
    k = torch.randn(B, H, L, D, device=device, dtype=dtype)
    v = torch.randn(B, H, L, D, device=device, dtype=dtype)

    out = s20_scaled_dot_product_attention(q, k, v, window_size=16, sequence_fn="s15")
    assert out.dtype == dtype
    assert not torch.isnan(out).any()

def test_s20_attention_weights_properties():
    """
    Since we can't easily extract attn_weights from SDPA without modifying the function,
    we can test that the L1 normalization implies the output magnitude is bounded by V's magnitude.
    """
    B, H, L, D = 1, 1, 16, 16
    q = torch.randn(B, H, L, D)
    k = torch.randn(B, H, L, D)
    v = torch.ones(B, H, L, D) * 5.0  # V is all 5s

    # Since attention weights sum to 1 per row, the output should also be exactly 5.0 everywhere
    out = s20_scaled_dot_product_attention(q, k, v, window_size=4, sequence_fn="s20")
    
    assert torch.allclose(out, torch.full_like(out, 5.0), atol=1e-4)
