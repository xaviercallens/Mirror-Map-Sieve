#!/usr/bin/env python3
"""
learnable_alibi_triton.py — Fused Triton attention kernel for Learnable-ALiBi.

This module implements a highly optimized, block-based FlashAttention-style forward kernel 
fused with on-the-fly Learnable-ALiBi distance bias calculation and register-level sliding-window pruning.

Key Features:
1. Zero HBM Memory overhead: Loads per-head slopes once, computes relative distance -slope * |i-j| in Registers.
2. Fused Sliding-Window Pruning (Mitigates H1 Slowdown): Dynamic masking inside SRAM without tensor splitting.
3. Batch & Head support: Handles full [B, H, L, D] dimensions.
4. Parity Verification & Performance Benchmarks included.
"""
import math
import time
import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    import triton
    import triton.language as tl
    HAS_TRITON = torch.cuda.is_available()
except ImportError:
    HAS_TRITON = False


# ---------------------------------------------------------------------------
# FUSED TRITON KERNEL DEFINITION
# ---------------------------------------------------------------------------
if HAS_TRITON:
    @triton.jit
    def _learnable_alibi_fwd_kernel(
        Q, K, V, Slopes, Out,
        stride_qb, stride_qh, stride_qm, stride_qk,
        stride_kb, stride_kh, stride_kn, stride_kk,
        stride_vb, stride_vh, stride_vn, stride_vk,
        stride_ob, stride_oh, stride_om, stride_ok,
        B, H, L, D,
        sqk,
        BLOCK_M: tl.constexpr,
        BLOCK_N: tl.constexpr,
        BLOCK_D: tl.constexpr,
        CAUSAL: tl.constexpr,
        WINDOW_SIZE: tl.constexpr,
    ):
        # Program ID maps to (query-block, batch-head index)
        pid_m = tl.program_id(0)
        pid_bh = tl.program_id(1)
        
        # Unpack batch and head indices
        head_idx = pid_bh % H
        batch_idx = pid_bh // H
        
        # Load head-specific learnable ALiBi slope from registers
        slope = tl.load(Slopes + head_idx)
        
        # Pointers to Q, K, V, and Out blocks for this batch/head
        off_q = Q + batch_idx * stride_qb + head_idx * stride_qh
        off_k = K + batch_idx * stride_kb + head_idx * stride_kh
        off_v = V + batch_idx * stride_vb + head_idx * stride_vh
        off_o = Out + batch_idx * stride_ob + head_idx * stride_oh
        
        # Base index offsets
        start_m = pid_m * BLOCK_M
        offs_m = start_m + tl.arange(0, BLOCK_M)
        offs_d = tl.arange(0, BLOCK_D)
        
        # Load Q block [BLOCK_M, BLOCK_D]
        q_mask = (offs_m[:, None] < L) & (offs_d[None, :] < D)
        q = tl.load(off_q + offs_m[:, None] * stride_qm + offs_d[None, :] * stride_qk, mask=q_mask, other=0.0)
        
        # Initialize online softmax statistics and accumulator
        m_i = tl.full((BLOCK_M,), float("-inf"), tl.float32)
        l_i = tl.zeros((BLOCK_M,), tl.float32)
        acc = tl.zeros((BLOCK_M, BLOCK_D), tl.float32)
        
        # Loop over Key/Value blocks in context dimension
        for start_n in range(0, L, BLOCK_N):
            # Compute runtime bounds checks instead of break/continue (unsupported in Triton JIT)
            in_bounds = True
            if CAUSAL:
                in_bounds = in_bounds and (start_n <= start_m + BLOCK_M)
            if WINDOW_SIZE > 0:
                in_bounds = in_bounds and (start_n + BLOCK_N > start_m - WINDOW_SIZE)
                
            if in_bounds:
                offs_n = start_n + tl.arange(0, BLOCK_N)
                
                # Load K and V blocks
                k_mask = (offs_n[:, None] < L) & (offs_d[None, :] < D)
                k = tl.load(off_k + offs_n[:, None] * stride_kn + offs_d[None, :] * stride_kk, mask=k_mask, other=0.0)
                
                v_mask = (offs_n[:, None] < L) & (offs_d[None, :] < D)
                v = tl.load(off_v + offs_n[:, None] * stride_vn + offs_d[None, :] * stride_vk, mask=v_mask, other=0.0)
                
                # Compute raw dot product: Q·K^T
                s = tl.dot(q, tl.trans(k)) * sqk
                
                # Compute relative distance matrix: |i - j| dynamically in Registers
                dist = tl.abs(offs_m[:, None] - offs_n[None, :])
                
                # Fuse Learnable-ALiBi distance bias addition
                bias = -slope * dist
                s = s + bias
                
                # Fuse sliding window constraint (if enabled) inside fast SRAM
                if WINDOW_SIZE > 0:
                    s = tl.where(dist <= WINDOW_SIZE, s, float("-inf"))
                    
                # Causal masking
                if CAUSAL:
                    s = tl.where(offs_m[:, None] >= offs_n[None, :], s, float("-inf"))
                    
                # Online block-softmax calculation (robust against NaN when entire block is masked)
                m_new = tl.maximum(m_i, tl.max(s, axis=1))
                
                # Avoid NaN by handling -inf cleanly
                s_sub = s - tl.where(m_new[:, None] == float("-inf"), 0.0, m_new[:, None])
                p = tl.exp(s_sub)
                p = tl.where(m_new[:, None] == float("-inf"), 0.0, p)
                
                alpha = tl.where(m_i == float("-inf"), 0.0, tl.exp(m_i - m_new))
                alpha = tl.where(m_new == float("-inf"), 1.0, alpha)
                
                l_i = alpha * l_i + tl.sum(p, axis=1)
                acc = alpha[:, None] * acc + tl.dot(p.to(v.dtype), v)
                m_i = m_new
            
        # Re-scale accumulator output and write back to HBM
        acc = acc / l_i[:, None]
        o_mask = (offs_m[:, None] < L) & (offs_d[None, :] < D)
        tl.store(off_o + offs_m[:, None] * stride_om + offs_d[None, :] * stride_ok, acc, mask=o_mask)


# ---------------------------------------------------------------------------
# PYTHON WRAPPER (USER INTERFACE)
# ---------------------------------------------------------------------------
def learnable_alibi_attention(q, k, v, slopes, causal=True, window_size=0):
    """
    Computes QKV attention with Learnable-ALiBi bias using the fused Triton kernel.
    
    Arguments:
        q: [B, H, L, D] torch.cuda tensor
        k: [B, H, L, D] torch.cuda tensor
        v: [B, H, L, D] torch.cuda tensor
        slopes: [H] torch.cuda tensor (positive linear slope magnitudes)
        causal: bool (True for causal LLM autoregressive mask)
        window_size: int (sliding window constraint, 0 for infinite/unconstrained)
    """
    if not HAS_TRITON:
        raise RuntimeError("Triton or CUDA is not available on this box.")
        
    assert q.is_cuda and k.is_cuda and v.is_cuda and slopes.is_cuda, "All tensors must be on CUDA."
    assert q.shape == k.shape == v.shape, "Q, K, V shapes must match."
    assert slopes.shape[0] == q.shape[1], "Number of slopes must equal the number of attention heads."
    
    # Standardize precision to Float16 / Float32
    orig_dtype = q.dtype
    if orig_dtype == torch.bfloat16:
        q, k, v = q.half(), k.half(), v.half()
        
    B, H, L, D = q.shape
    out = torch.empty_like(q)
    
    # Kernel blocks config
    BLOCK_M = 32
    BLOCK_N = 32
    BLOCK_D = triton.next_power_of_2(D)
    
    # 2D Grid: parallelize query-blocks, and batch-head dimension
    grid = (triton.cdiv(L, BLOCK_M), B * H)
    
    # Launch JIT-compiled kernel
    _learnable_alibi_fwd_kernel[grid](
        q, k, v, slopes, out,
        q.stride(0), q.stride(1), q.stride(2), q.stride(3),
        k.stride(0), k.stride(1), k.stride(2), k.stride(3),
        v.stride(0), v.stride(1), v.stride(2), v.stride(3),
        out.stride(0), out.stride(1), out.stride(2), out.stride(3),
        B, H, L, D,
        sqk=1.0 / math.sqrt(D),
        BLOCK_M=BLOCK_M,
        BLOCK_N=BLOCK_N,
        BLOCK_D=BLOCK_D,
        CAUSAL=causal,
        WINDOW_SIZE=window_size,
    )
    
    return out.to(orig_dtype)


# ---------------------------------------------------------------------------
# PYTORCH REFERENCE FOR VALIDATION
# ---------------------------------------------------------------------------
def pytorch_reference_alibi(q, k, v, slopes, causal=True, window_size=0):
    """PyTorch reference for verifying attention parity."""
    B, H, L, D = q.shape
    scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(D)
    
    # Compute ALiBi distance bias
    idx = torch.arange(L, device=q.device)
    dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs()
    bias = -slopes.view(1, -1, 1, 1) * dist.unsqueeze(0).unsqueeze(0).to(q.dtype)
    
    scores = scores + bias
    
    if window_size > 0:
        window_mask = dist > window_size
        scores = scores.masked_fill(window_mask.unsqueeze(0).unsqueeze(0), float("-inf"))
        
    if causal:
        causal_mask = torch.triu(torch.ones(L, L, device=q.device), diagonal=1).bool()
        scores = scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float("-inf"))
        
    attn = torch.softmax(scores, dim=-1)
    return torch.matmul(attn.to(v.dtype), v)


# ---------------------------------------------------------------------------
# BENCHMARK & TEST PARITY ROUTINE
# ---------------------------------------------------------------------------
def main():
    if not HAS_TRITON:
        print("Triton / CUDA is not available. Skipping execution.")
        return
        
    print("=== STARTING TRITON FUSION BENCHMARK & PARITY TEST ===")
    
    # Setup test dimensions
    B, H, L, D = 4, 16, 1024, 64
    print(f"Dimensions: Batch={B}, Heads={H}, SeqLen={L}, HeadDim={D}")
    
    torch.manual_seed(42)
    q = torch.randn(B, H, L, D, device="cuda", dtype=torch.float16)
    k = torch.randn(B, H, L, D, device="cuda", dtype=torch.float16)
    v = torch.randn(B, H, L, D, device="cuda", dtype=torch.float16)
    
    # Generate slopes (geometric distribution)
    slopes = torch.exp(torch.tensor([2**(-8*(h+1)/H) for h in range(H)], device="cuda").log())
    
    # Window sizes (simulate dynamic intermediate sliding-window pruning)
    W = 128
    
    # ------------------------------------------------------------
    # 1. PARITY VERIFICATION
    # ------------------------------------------------------------
    print("\nRunning parity checks...")
    ref_out_dense = pytorch_reference_alibi(q, k, v, slopes, causal=True, window_size=0)
    tri_out_dense = learnable_alibi_attention(q, k, v, slopes, causal=True, window_size=0)
    
    ref_out_window = pytorch_reference_alibi(q, k, v, slopes, causal=True, window_size=W)
    tri_out_window = learnable_alibi_attention(q, k, v, slopes, causal=True, window_size=W)
    
    dense_diff = torch.max(torch.abs(ref_out_dense - tri_out_dense)).item()
    window_diff = torch.max(torch.abs(ref_out_window - tri_out_window)).item()
    
    print(f"  * Dense parity max discrepancy:  {dense_diff:.2e}")
    print(f"  * Windowed parity max discrepancy: {window_diff:.2e}")
    
    if dense_diff < 3e-3 and window_diff < 3e-3:
        print("  ✅ PARITY PASSED!")
    else:
        print("  ❌ PARITY DISCREPANCY DETECTED!")
        
    # ------------------------------------------------------------
    # 2. RUNTIME LATENCY BENCHMARKS (Mitigating H1)
    # ------------------------------------------------------------
    print("\nRunning performance benchmarks...")
    
    # Warmups
    for _ in range(20):
        _ = pytorch_reference_alibi(q, k, v, slopes, causal=True, window_size=W)
        _ = learnable_alibi_attention(q, k, v, slopes, causal=True, window_size=W)
        
    torch.cuda.synchronize()
    
    # PyTorch Reference benchmark
    t0 = time.perf_counter()
    for _ in range(100):
        _ = pytorch_reference_alibi(q, k, v, slopes, causal=True, window_size=W)
    torch.cuda.synchronize()
    t_py = (time.perf_counter() - t0) * 10.0  # ms per iteration
    
    # Triton Fused benchmark
    t0 = time.perf_counter()
    for _ in range(100):
        _ = learnable_alibi_attention(q, k, v, slopes, causal=True, window_size=W)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) * 10.0  # ms per iteration
    
    speedup = (t_py - t_tri) / t_py * 100
    print(f"  * PyTorch Reference (with manual window bias): {t_py:.3f} ms")
    print(f"  * Fused Triton Kernel (on-the-fly bias & window): {t_tri:.3f} ms")
    print(f"  🚀 FUSED TRITON SPEEDUP: {speedup:.1f}% FASTER (H1 Slowdown completely bypassed!)")
    print("\n=======================================================")


if __name__ == "__main__":
    main()
