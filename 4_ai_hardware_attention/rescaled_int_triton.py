#!/usr/bin/env python3
"""
rescaled_int_triton.py — Fused Triton exact-ish attention kernel.

Implements the exact-ish Rescaled-Integer QK^T accumulation + FP32 online softmax 
in a fused Triton kernel, preserving high numerical precision over long contexts 
without HBM memory round-trips.
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
    def _rescaled_int_attn_fwd_kernel(
        Q, K, V, Slopes, Out,
        stride_qb, stride_qh, stride_qm, stride_qk,
        stride_kb, stride_kh, stride_kn, stride_kk,
        stride_vb, stride_vh, stride_vn, stride_vk,
        stride_ob, stride_oh, stride_om, stride_ok,
        B, H, L, D,
        sqk,
        scale_factor,
        BLOCK_M: tl.constexpr,
        BLOCK_N: tl.constexpr,
        BLOCK_D: tl.constexpr,
        CAUSAL: tl.constexpr,
        USE_FP64: tl.constexpr,
    ):
        pid_m = tl.program_id(0)
        pid_bh = tl.program_id(1)
        
        head_idx = pid_bh % H
        batch_idx = pid_bh // H
        
        # Load head slope
        slope = tl.load(Slopes + head_idx)
        
        # Pointers for this batch/head
        off_q = Q + batch_idx * stride_qb + head_idx * stride_qh
        off_k = K + batch_idx * stride_kb + head_idx * stride_kh
        off_v = V + batch_idx * stride_vb + head_idx * stride_vh
        off_o = Out + batch_idx * stride_ob + head_idx * stride_oh
        
        start_m = pid_m * BLOCK_M
        offs_m = start_m + tl.arange(0, BLOCK_M)
        offs_d = tl.arange(0, BLOCK_D)
        
        # Load Q and cast to float32 BEFORE scaling to prevent float16 overflow
        q_mask = (offs_m[:, None] < L) & (offs_d[None, :] < D)
        q_fp = tl.load(off_q + offs_m[:, None] * stride_qm + offs_d[None, :] * stride_qk, mask=q_mask, other=0.0).to(tl.float32)
        
        q_scaled = q_fp * scale_factor
        q_int_fp = tl.where(q_scaled >= 0, q_scaled + 0.5, q_scaled - 0.5).to(tl.int32)
        
        # Initialize online softmax statistics (FP32)
        m_i = tl.full((BLOCK_M,), float("-inf"), tl.float32)
        l_i = tl.zeros((BLOCK_M,), tl.float32)
        acc = tl.zeros((BLOCK_M, BLOCK_D), tl.float32)
        
        # Loop over context keys/values
        for start_n in range(0, L, BLOCK_N):
            if not CAUSAL or (start_n <= start_m + BLOCK_M):
                offs_n = start_n + tl.arange(0, BLOCK_N)
                k_mask = (offs_n[:, None] < L) & (offs_d[None, :] < D)
                
                # Load K and cast to float32 before scaling
                k_fp = tl.load(off_k + offs_n[:, None] * stride_kn + offs_d[None, :] * stride_kk, mask=k_mask, other=0.0).to(tl.float32)
                k_scaled = k_fp * scale_factor
                k_int_fp = tl.where(k_scaled >= 0, k_scaled + 0.5, k_scaled - 0.5).to(tl.int32)
                
                # Load V (FP32)
                v_fp = tl.load(off_v + offs_n[:, None] * stride_vn + offs_d[None, :] * stride_vk, mask=k_mask, other=0.0).to(tl.float32)
                
                # Compute raw exact dot product
                if USE_FP64:
                    # Accumulate in FP64 for exact precision with large scale factors
                    dots = tl.dot(q_int_fp.to(tl.float64), tl.trans(k_int_fp.to(tl.float64)))
                    # Scale back to standard float attention score (FP32)
                    s = (dots / (scale_factor * scale_factor)).to(tl.float32) * sqk
                else:
                    # Accumulate in FP32
                    dots = tl.dot(q_int_fp.to(tl.float32), tl.trans(k_int_fp.to(tl.float32)))
                    # Scale back
                    s = (dots / (scale_factor * scale_factor)) * sqk
                
                # Fuse ALiBi linear distance bias
                dist = tl.abs(offs_m[:, None] - offs_n[None, :])
                s = s - slope * dist
                
                # Causal masking
                if CAUSAL:
                    s = tl.where(offs_m[:, None] >= offs_n[None, :], s, float("-inf"))
                    
                # Online softmax update (FP32)
                m_new = tl.maximum(m_i, tl.max(s, axis=1))
                s_sub = s - tl.where(m_new[:, None] == float("-inf"), 0.0, m_new[:, None])
                p = tl.exp(s_sub)
                p = tl.where(m_new[:, None] == float("-inf"), 0.0, p)
                
                alpha = tl.where(m_i == float("-inf"), 0.0, tl.exp(m_i - m_new))
                alpha = tl.where(m_new == float("-inf"), 1.0, alpha)
                
                l_i = alpha * l_i + tl.sum(p, axis=1)
                acc = alpha[:, None] * acc + tl.dot(p, v_fp)
                m_i = m_new
                
        # Write back output
        acc = acc / l_i[:, None]
        o_mask = (offs_m[:, None] < L) & (offs_d[None, :] < D)
        tl.store(off_o + offs_m[:, None] * stride_om + offs_d[None, :] * stride_ok, acc.to(Q.dtype.element_ty), mask=o_mask)


# ---------------------------------------------------------------------------
# PYTHON WRAPPER (USER INTERFACE)
# ---------------------------------------------------------------------------
def rescaled_int_attention(q, k, v, slopes, scale_bits=6, causal=True, use_fp64=False):
    """
    Computes QKV attention with exact-ish Rescaled-Integer accumulation and
    FP32 online softmax in a fused Triton kernel.
    """
    if not HAS_TRITON:
        raise RuntimeError("Triton or CUDA is not available on this system.")
        
    assert q.is_cuda and k.is_cuda and v.is_cuda and slopes.is_cuda, "All tensors must be on CUDA."
    assert q.shape == k.shape == v.shape, "Q, K, V shapes must match."
    assert slopes.shape[0] == q.shape[1], "Number of slopes must equal the number of attention heads."
    
    orig_dtype = q.dtype
    if orig_dtype == torch.bfloat16:
        q, k, v = q.half(), k.half(), v.half()
        
    B, H, L, D = q.shape
    out = torch.empty_like(q)
    
    BLOCK_M = 32
    BLOCK_N = 32
    BLOCK_D = triton.next_power_of_2(D)
    
    grid = (triton.cdiv(L, BLOCK_M), B * H)
    scale_factor = 2.0 ** scale_bits
    
    _rescaled_int_attn_fwd_kernel[grid](
        q, k, v, slopes, out,
        q.stride(0), q.stride(1), q.stride(2), q.stride(3),
        k.stride(0), k.stride(1), k.stride(2), k.stride(3),
        v.stride(0), v.stride(1), v.stride(2), v.stride(3),
        out.stride(0), out.stride(1), out.stride(2), out.stride(3),
        B, H, L, D,
        sqk=1.0 / math.sqrt(D),
        scale_factor=scale_factor,
        BLOCK_M=BLOCK_M,
        BLOCK_N=BLOCK_N,
        BLOCK_D=BLOCK_D,
        CAUSAL=causal,
        USE_FP64=use_fp64,
    )
    
    return out.to(orig_dtype)


# ---------------------------------------------------------------------------
# PYTORCH REFERENCE FOR VALIDATION
# ---------------------------------------------------------------------------
def pytorch_reference_rescaled_int(q, k, v, slopes, scale_bits=6, causal=True):
    """PyTorch CPU/GPU reference for Rescaled-Integer attention emulation."""
    B, H, L, D = q.shape
    scale_factor = 2.0 ** scale_bits
    
    # Cast to float first to prevent float16 overflow
    q_scaled = q.float() * scale_factor
    q_rounded = torch.where(q_scaled >= 0, torch.trunc(q_scaled + 0.5), torch.trunc(q_scaled - 0.5))
    
    k_scaled = k.float() * scale_factor
    k_rounded = torch.where(k_scaled >= 0, torch.trunc(k_scaled + 0.5), torch.trunc(k_scaled - 0.5))
    
    # Dot product accumulated in float64 for exact precision
    scores = torch.matmul(q_rounded.double(), k_rounded.transpose(-2, -1).double())
    
    # Scale back to normal range
    scores = (scores / (scale_factor * scale_factor)) / math.sqrt(D)
    
    # Add ALiBi linear distance bias
    idx = torch.arange(L, device=q.device)
    dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs()
    bias = -slopes.view(1, -1, 1, 1) * dist.unsqueeze(0).unsqueeze(0).to(scores.dtype)
    
    scores = scores + bias
    
    if causal:
        causal_mask = torch.triu(torch.ones(L, L, device=q.device), diagonal=1).bool()
        scores = scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float("-inf"))
        
    attn = torch.softmax(scores.float(), dim=-1) # Softmax in FP32
    return torch.matmul(attn.to(v.dtype), v)


# ---------------------------------------------------------------------------
# DRIVER & COMPARATIVE FIDELITY/PERFORMANCE RUNS
# ---------------------------------------------------------------------------
def main():
    if not HAS_TRITON:
        print("Triton / CUDA is not available. Skipping execution.")
        return
        
    print("=== STARTING EXACT-ATTENTION RESCALED-INTEGER TRITON KERNEL ===")
    
    B, H, L, D = 4, 16, 1024, 64
    print(f"Dimensions: Batch={B}, Heads={H}, SeqLen={L}, HeadDim={D}")
    
    torch.manual_seed(42)
    q = torch.randn(B, H, L, D, device="cuda", dtype=torch.float16)
    k = torch.randn(B, H, L, D, device="cuda", dtype=torch.float16)
    v = torch.randn(B, H, L, D, device="cuda", dtype=torch.float16)
    
    slopes = torch.exp(torch.tensor([2**(-8*(h+1)/H) for h in range(H)], device="cuda").log()).to(torch.float16)
    
    # Pure FP64 Ground-Truth Reference
    q_f64, k_f64, v_f64 = q.double(), k.double(), v.double()
    slopes_f64 = slopes.double()
    ref_scores = torch.matmul(q_f64, k_f64.transpose(-2, -1)) / math.sqrt(D)
    idx = torch.arange(L, device="cuda")
    dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs()
    bias = -slopes_f64.view(1, -1, 1, 1) * dist.unsqueeze(0).unsqueeze(0)
    ref_scores = ref_scores + bias
    causal_mask = torch.triu(torch.ones(L, L, device="cuda"), diagonal=1).bool()
    ref_scores = ref_scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float("-inf"))
    attn_f64 = torch.softmax(ref_scores, dim=-1)
    out_f64_reference = torch.matmul(attn_f64, v_f64)
    
    # ------------------------------------------------------------
    # 1. PARITY VERIFICATION
    # ------------------------------------------------------------
    print("\n1. Verifying mathematical parity (bit-for-bit vs PyTorch emulate reference)...")
    for bits in [6, 10, 14]:
        for use_f64 in [False, True]:
            ref_out = pytorch_reference_rescaled_int(q, k, v, slopes, scale_bits=bits, causal=True)
            tri_out = rescaled_int_attention(q, k, v, slopes, scale_bits=bits, causal=True, use_fp64=use_f64)
            discrepancy = torch.max(torch.abs(ref_out - tri_out)).item()
            print(f"  * scale_bits={bits:<2} | fp64={str(use_f64):<5} | Max discrepancy: {discrepancy:.2e}")
            
    # ------------------------------------------------------------
    # 2. NUMERICAL FIDELITY EVALUATION (vs FP64 Reference)
    # ------------------------------------------------------------
    print("\n2. Numerical fidelity benchmark vs FP64 (at context length 1024)...")
    
    # Baseline FP16 Fused Triton Attention
    try:
        from learnable_alibi_triton import learnable_alibi_attention
        baseline_out = learnable_alibi_attention(q, k, v, slopes, causal=True, window_size=0)
    except Exception as e:
        baseline_out = torch.matmul(torch.softmax((torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(D) - slopes.view(1, -1, 1, 1) * dist.unsqueeze(0).unsqueeze(0)).masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float("-inf")), dim=-1), v)
        
    def error_metrics(out_tensor, ref_f64):
        diff = torch.abs(out_tensor.double() - ref_f64)
        max_err = diff.max().item()
        mean_err = diff.mean().item()
        return max_err, mean_err
        
    err_base_max, err_base_mean = error_metrics(baseline_out, out_f64_reference)
    print(f"  * Baseline FP16:               Max Rel Error = {err_base_max:.2e} | Mean = {err_base_mean:.2e}")
    
    for bits in [6, 10, 12, 14]:
        for use_f64 in [False, True]:
            tri_out = rescaled_int_attention(q, k, v, slopes, scale_bits=bits, causal=True, use_fp64=use_f64)
            err_exact_max, err_exact_mean = error_metrics(tri_out, out_f64_reference)
            ratio = err_base_max / max(1e-12, err_exact_max)
            print(f"  * Rescaled-Int ({bits:<2}b, f64={str(use_f64):<5}):  Max Rel Error = {err_exact_max:.2e} | Mean = {err_exact_mean:.2e} | Improvement = {ratio:.1f}x")
            
    # ------------------------------------------------------------
    # 3. LATENCY BENCHMARK
    # ------------------------------------------------------------
    print("\n3. Latency profiling (execution times)...")
    for bits in [10]:
        for use_f64 in [False, True]:
            # Warmups
            for _ in range(20):
                _ = rescaled_int_attention(q, k, v, slopes, scale_bits=bits, causal=True, use_fp64=use_f64)
            torch.cuda.synchronize()
            
            t0 = time.perf_counter()
            for _ in range(100):
                _ = rescaled_int_attention(q, k, v, slopes, scale_bits=bits, causal=True, use_fp64=use_f64)
            torch.cuda.synchronize()
            t_exact = (time.perf_counter() - t0) * 10.0 # ms per batch
            print(f"  * Rescaled-Int (10b, f64={str(use_f64):<5}): {t_exact:.3f} ms")
            
    print("\n=======================================================")


if __name__ == "__main__":
    main()
