# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
"""Tests for global SDPA monkey-patching."""

import pytest
import torch
import torch.nn.functional as F

from s15_kernel.patching import patch_model_with_s20, unpatch_model, S20PatchContext

def test_s20_patch_context():
    """Verify S20PatchContext temporarily replaces F.sdpa."""
    B, H, L, D = 1, 2, 64, 32
    q = torch.randn(B, H, L, D)
    k = torch.randn(B, H, L, D)
    v = torch.randn(B, H, L, D)

    out_base = F.scaled_dot_product_attention(q, k, v)
    
    with S20PatchContext(window_size=16, sequence_fn="s15"):
        out_patched = F.scaled_dot_product_attention(q, k, v)
        
    out_restored = F.scaled_dot_product_attention(q, k, v)

    # Patched should differ significantly from base
    assert not torch.allclose(out_base, out_patched, atol=1e-3)
    
    # Restored should match base exactly
    assert torch.allclose(out_base, out_restored)

def test_global_patch_unpatch():
    """Verify manual global patch and unpatch."""
    B, H, L, D = 1, 2, 64, 32
    q = torch.randn(B, H, L, D)
    k = torch.randn(B, H, L, D)
    v = torch.randn(B, H, L, D)

    out_base = F.scaled_dot_product_attention(q, k, v)
    
    patch_model_with_s20(None, window_size=16, sequence_fn="s20")
    try:
        out_patched = F.scaled_dot_product_attention(q, k, v)
        assert not torch.allclose(out_base, out_patched, atol=1e-3)
    finally:
        unpatch_model()
        
    out_restored = F.scaled_dot_product_attention(q, k, v)
    assert torch.allclose(out_base, out_restored)

def test_patched_autoregressive_decoding():
    """Verify the patch handles autoregressive decoding shapes (L_q=1, L_k>1)."""
    B, H, L_k, D = 1, 2, 64, 32
    L_q = 1
    q = torch.randn(B, H, L_q, D)
    k = torch.randn(B, H, L_k, D)
    v = torch.randn(B, H, L_k, D)

    with S20PatchContext(window_size=8, sequence_fn="s20"):
        out = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        
    assert out.shape == (B, H, L_q, D)
    assert not torch.isnan(out).any()
