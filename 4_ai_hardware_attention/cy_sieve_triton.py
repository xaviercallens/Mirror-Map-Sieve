#!/usr/bin/env python3
"""
cy_sieve_triton.py — Triton kernel for CY-Sieve attention (Stage B, GPU half).

This is the GPU port of the CPU reference `cy_sieve_attention.flash_sdpa_with_bias`
(the online/blocked softmax). It is GPU-GUARDED: the module imports cleanly on a
CPU-only box (HAS_TRITON=False) so the rest of the suite is unaffected; the kernel
only runs where CUDA + Triton are present.

The bias is passed as a precomputed per-distance vector `bias_vec[d]` (built on
the host from cy_sieve_reference.cy_sieve_bias with the chosen per-head tau) and
added to the scores inside the kernel — exactly mirroring the CPU reference, so
`tests.md` §4 T4.1 (Triton vs NumPy parity) can compare them bit-for-bit within
FP16/BF16 tolerance.

When you have a GPU:
    pip install -r requirements-gpu.txt
    python  4_ai_hardware_attention/cy_sieve_triton.py        # smoke test
    pytest  4_ai_hardware_attention/test_cy_sieve_triton.py   # parity vs reference
"""
from __future__ import annotations

try:
    import torch
    HAS_TORCH = True
except Exception:
    HAS_TORCH = False

try:
    import triton
    import triton.language as tl
    HAS_TRITON = HAS_TORCH and torch.cuda.is_available()
except Exception:
    HAS_TRITON = False


# ---------------------------------------------------------------------------
# Triton kernel (defined only when Triton is importable; never at CPU import).
# ---------------------------------------------------------------------------
if HAS_TRITON:

    @triton.jit
    def _cy_sieve_fwd(
        Q, K, V, BIAS, Out,
        L, D,
        sqk: tl.constexpr, BLOCK_N: tl.constexpr, BLOCK_D: tl.constexpr,
        CAUSAL: tl.constexpr,
    ):
        """One query-block of FlashAttention with an additive distance bias.
        BIAS is a length-L vector bias[d] = CY-Sieve bias at distance d (per the
        head's tau). scores[i,j] = (q_i·k_j)*sqk + BIAS[i-j], causal j<=i.
        Mirrors cy_sieve_attention.flash_sdpa_with_bias exactly.
        """
        start_i = tl.program_id(0) * BLOCK_N
        offs_i = start_i + tl.arange(0, BLOCK_N)
        offs_d = tl.arange(0, BLOCK_D)

        q = tl.load(Q + offs_i[:, None] * D + offs_d[None, :],
                    mask=(offs_i[:, None] < L) & (offs_d[None, :] < D), other=0.0)

        m_i = tl.full((BLOCK_N,), float("-inf"), tl.float32)
        l_i = tl.zeros((BLOCK_N,), tl.float32)
        acc = tl.zeros((BLOCK_N, BLOCK_D), tl.float32)

        for start_j in range(0, L, BLOCK_N):
            offs_j = start_j + tl.arange(0, BLOCK_N)
            k = tl.load(K + offs_j[:, None] * D + offs_d[None, :],
                        mask=(offs_j[:, None] < L) & (offs_d[None, :] < D), other=0.0)
            v = tl.load(V + offs_j[:, None] * D + offs_d[None, :],
                        mask=(offs_j[:, None] < L) & (offs_d[None, :] < D), other=0.0)
            s = tl.dot(q, tl.trans(k)) * sqk                      # [BN, BN]
            dist = offs_i[:, None] - offs_j[None, :]              # i - j (>=0 causal)
            b = tl.load(BIAS + dist, mask=(dist >= 0) & (dist < L), other=float("-inf"))
            s = s + b
            if CAUSAL:
                s = tl.where(offs_j[None, :] <= offs_i[:, None], s, float("-inf"))
            m_new = tl.maximum(m_i, tl.max(s, axis=1))
            p = tl.exp(s - m_new[:, None])
            alpha = tl.exp(m_i - m_new)
            l_i = alpha * l_i + tl.sum(p, axis=1)
            acc = alpha[:, None] * acc + tl.dot(p.to(v.dtype), v)
            m_i = m_new

        acc = acc / l_i[:, None]
        tl.store(Out + offs_i[:, None] * D + offs_d[None, :], acc,
                 mask=(offs_i[:, None] < L) & (offs_d[None, :] < D))


def cy_sieve_attention_triton(Q, K, V, bias_vec, causal=True, block_n=64):
    """Run the Triton kernel. Q,K,V: [L,D] torch.cuda tensors; bias_vec: [L]
    distance-bias (host-built from cy_sieve_reference for the head's tau).
    Raises if Triton/CUDA unavailable (use the CPU reference instead)."""
    if not HAS_TRITON:
        raise RuntimeError("Triton/CUDA unavailable; use cy_sieve_attention "
                           "(CPU reference) on this machine.")
    import math
    L, D = Q.shape
    out = torch.empty_like(Q)
    BLOCK_D = triton.next_power_of_2(D)
    grid = (triton.cdiv(L, block_n),)
    _cy_sieve_fwd[grid](Q, K, V, bias_vec, out, L, D,
                        sqk=1.0 / math.sqrt(D), BLOCK_N=block_n, BLOCK_D=BLOCK_D,
                        CAUSAL=causal)
    return out


def main():
    if not HAS_TRITON:
        print("Triton/CUDA not available on this machine.")
        print("This is the GPU-phase kernel; run it on a CUDA box after:")
        print("  pip install -r 4_ai_hardware_attention/requirements-gpu.txt")
        print("The CPU reference (cy_sieve_attention.py) is the parity oracle.")
        return
    import torch, numpy as np, os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    import cy_sieve_reference as cy
    L, D = 128, 64
    g = torch.Generator(device="cuda").manual_seed(0)
    Q, K, V = (torch.randn(L, D, device="cuda", generator=g) for _ in range(3))
    bias = torch.tensor(cy.build_bias_vector(L, "S20", tau=128.0)[:L],
                        device="cuda", dtype=torch.float32)
    out = cy_sieve_attention_triton(Q, K, V, bias)
    print("Triton kernel ran; out shape", tuple(out.shape))


if __name__ == "__main__":
    main()
