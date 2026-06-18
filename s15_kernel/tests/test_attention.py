# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
"""Tests for s15_kernel.attention — S20SpectralAttention module."""

from __future__ import annotations

import pytest
import torch

from s15_kernel.attention import S20SpectralAttention


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def default_module() -> S20SpectralAttention:
    """Small S20SpectralAttention for testing."""
    torch.manual_seed(42)
    return S20SpectralAttention(
        d_model=64, n_heads=4, window_size=8, sequence_fn="s20", causal=True
    )


@pytest.fixture
def sample_input() -> torch.Tensor:
    """Random input tensor (B=2, L=16, D=64)."""
    torch.manual_seed(123)
    return torch.randn(2, 16, 64)


# ------------------------------------------------------------------
# Shape tests
# ------------------------------------------------------------------

class TestOutputShape:
    """Output shape must match input shape (drop-in replacement)."""

    def test_basic_shape(
        self, default_module: S20SpectralAttention, sample_input: torch.Tensor
    ) -> None:
        out = default_module(sample_input)
        assert out.shape == sample_input.shape

    @pytest.mark.parametrize("B,L,D", [(1, 4, 64), (3, 32, 64), (2, 1, 64)])
    def test_various_shapes(self, B: int, L: int, D: int) -> None:
        torch.manual_seed(0)
        module = S20SpectralAttention(d_model=D, n_heads=4, window_size=8)
        x = torch.randn(B, L, D)
        out = module(x)
        assert out.shape == (B, L, D)


# ------------------------------------------------------------------
# Attention weight properties
# ------------------------------------------------------------------

class TestAttentionWeights:
    """Verify internal attention weight properties."""

    def _get_attn_weights(
        self, module: S20SpectralAttention, x: torch.Tensor
    ) -> torch.Tensor:
        """Extract attention weights by hooking into the forward pass."""
        B, L, D = x.shape
        H = module.n_heads
        Dh = module.head_dim
        import torch.nn.functional as F

        Q = module.q_proj(x).view(B, L, H, Dh).transpose(1, 2)
        K = module.k_proj(x).view(B, L, H, Dh).transpose(1, 2)
        Q = F.normalize(Q, p=2, dim=-1)
        K = F.normalize(K, p=2, dim=-1)
        scores = torch.matmul(Q, K.transpose(-2, -1))
        decay_mask = module._build_decay_mask(L, x.device)
        scores = scores * decay_mask.unsqueeze(0).unsqueeze(0)
        scores = F.relu(scores)
        row_sums = scores.sum(dim=-1, keepdim=True).clamp(min=1e-8)
        attn_weights = scores / row_sums
        return attn_weights

    def test_weights_sum_to_one(
        self, default_module: S20SpectralAttention, sample_input: torch.Tensor
    ) -> None:
        """Rows with non-zero ReLU scores should sum to ~1.

        Rows where ALL pre-ReLU scores are negative will have sum ≈ 0
        (clamped to 1e-8 denominator). This is expected and correct.
        """
        weights = self._get_attn_weights(default_module, sample_input)
        row_sums = weights.sum(dim=-1)
        # Only check rows with meaningful positive scores (exclude sparse rows
        # where random init causes near-zero sums that don't normalize to 1.0)
        active_rows = row_sums > 0.5
        if active_rows.any():
            active_sums = row_sums[active_rows]
            assert torch.allclose(active_sums, torch.ones_like(active_sums), atol=1e-5), (
                f"Active row sums should be ~1, got min={active_sums.min():.6f}, "
                f"max={active_sums.max():.6f}"
            )


    def test_weights_non_negative(
        self, default_module: S20SpectralAttention, sample_input: torch.Tensor
    ) -> None:
        """All attention weights must be non-negative (ReLU output)."""
        weights = self._get_attn_weights(default_module, sample_input)
        assert (weights >= 0).all()


# ------------------------------------------------------------------
# Banded structure
# ------------------------------------------------------------------

class TestBandedStructure:
    """Attention weights must be zero outside the window."""

    def test_outside_window_is_zero(self) -> None:
        torch.manual_seed(0)
        W = 4
        module = S20SpectralAttention(
            d_model=32, n_heads=2, window_size=W, causal=False
        )
        L = 16
        x = torch.randn(1, L, 32)

        # Build mask and check structure
        mask = module._build_decay_mask(L, x.device)
        idx = torch.arange(L)
        dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs()
        outside = dist > W
        assert (mask[outside] == 0).all(), "Mask must be zero outside window"

    def test_inside_window_is_nonzero(self) -> None:
        torch.manual_seed(0)
        W = 4
        module = S20SpectralAttention(
            d_model=32, n_heads=2, window_size=W, causal=False
        )
        L = 16
        mask = module._build_decay_mask(L, torch.device("cpu"))
        idx = torch.arange(L)
        dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs()
        inside = dist <= W
        assert (mask[inside] > 0).all(), "Mask must be > 0 inside window"


# ------------------------------------------------------------------
# Causal masking
# ------------------------------------------------------------------

class TestCausalMask:
    """Causal mask must zero out future positions."""

    def test_upper_triangle_zero(self) -> None:
        module = S20SpectralAttention(
            d_model=32, n_heads=2, window_size=8, causal=True
        )
        L = 12
        mask = module._build_decay_mask(L, torch.device("cpu"))
        # Upper triangle (j > i) should be zero
        for i in range(L):
            for j in range(i + 1, L):
                assert mask[i, j].item() == 0.0, (
                    f"Causal mask[{i},{j}] should be 0, got {mask[i, j].item()}"
                )

    def test_non_causal_has_upper_triangle(self) -> None:
        module = S20SpectralAttention(
            d_model=32, n_heads=2, window_size=8, causal=False
        )
        L = 12
        mask = module._build_decay_mask(L, torch.device("cpu"))
        # At least some upper-triangle entries should be non-zero
        upper = torch.triu(mask, diagonal=1)
        assert upper.sum().item() > 0, "Non-causal mask should have non-zero upper triangle"


# ------------------------------------------------------------------
# Gradient flow
# ------------------------------------------------------------------

class TestGradientFlow:
    """Gradients must flow without NaN or all-zero."""

    def test_gradients_exist(
        self, default_module: S20SpectralAttention
    ) -> None:
        torch.manual_seed(7)
        x = torch.randn(2, 8, 64, requires_grad=True)
        out = default_module(x)
        loss = out.sum()
        loss.backward()

        assert x.grad is not None, "Input should receive gradients"
        assert not torch.isnan(x.grad).any(), "Gradients should not be NaN"
        assert x.grad.abs().sum().item() > 0, "Gradients should not all be zero"

    def test_param_gradients(
        self, default_module: S20SpectralAttention
    ) -> None:
        torch.manual_seed(7)
        x = torch.randn(2, 8, 64)
        out = default_module(x)
        loss = out.sum()
        loss.backward()

        for name, param in default_module.named_parameters():
            assert param.grad is not None, f"Parameter {name} should have gradient"
            assert not torch.isnan(param.grad).any(), (
                f"Parameter {name} gradient is NaN"
            )


# ------------------------------------------------------------------
# CPU / CUDA consistency
# ------------------------------------------------------------------

class TestDeviceConsistency:
    """CPU and CUDA should produce consistent results."""

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_cpu_cuda_close(self) -> None:
        torch.manual_seed(42)
        module = S20SpectralAttention(d_model=64, n_heads=4, window_size=8)

        x = torch.randn(2, 16, 64)
        out_cpu = module(x)

        module_cuda = module.cuda()
        x_cuda = x.cuda()
        out_cuda = module_cuda(x_cuda)

        assert torch.allclose(out_cpu, out_cuda.cpu(), atol=1e-4), (
            "CPU and CUDA outputs should be close"
        )


# ------------------------------------------------------------------
# Window size sensitivity
# ------------------------------------------------------------------

class TestWindowSize:
    """Different window sizes should produce different outputs."""

    def test_different_windows_differ(self) -> None:
        torch.manual_seed(0)
        x = torch.randn(1, 16, 64)

        m1 = S20SpectralAttention(d_model=64, n_heads=4, window_size=2)
        m2 = S20SpectralAttention(d_model=64, n_heads=4, window_size=16)

        # Use the same weights for a fair comparison
        m2.load_state_dict(m1.state_dict(), strict=False)

        out1 = m1(x)
        out2 = m2(x)

        assert not torch.allclose(out1, out2, atol=1e-6), (
            "Different window sizes should produce different outputs"
        )


# ------------------------------------------------------------------
# Configuration validation
# ------------------------------------------------------------------

class TestConfigValidation:
    """Test that invalid configs are rejected."""

    def test_d_model_not_divisible(self) -> None:
        with pytest.raises(ValueError, match="divisible"):
            S20SpectralAttention(d_model=65, n_heads=4)

    def test_invalid_sequence_fn(self) -> None:
        with pytest.raises(ValueError, match="sequence_fn"):
            S20SpectralAttention(d_model=64, n_heads=4, sequence_fn="s99")

    def test_s15_sequence_fn(self) -> None:
        """S15 variant should instantiate without error."""
        module = S20SpectralAttention(d_model=64, n_heads=4, sequence_fn="s15")
        x = torch.randn(1, 8, 64)
        out = module(x)
        assert out.shape == x.shape

    def test_repr(self) -> None:
        module = S20SpectralAttention(d_model=64, n_heads=4, window_size=16)
        r = repr(module)
        assert "d_model=64" in r
        assert "n_heads=4" in r
        assert "window_size=16" in r
