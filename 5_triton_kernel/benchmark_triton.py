import torch
import triton
import pandas as pd
from s20_attention import holonomic_s20_attention

def benchmark_memory_throughput():
    Z = 2
    H = 8
    HEAD_DIM = 128
    
    configs = []
    
    for seq_len in [128, 256, 512, 1024, 2048, 4096]:
        q = torch.randn((Z, H, seq_len, HEAD_DIM), device='cuda', dtype=torch.float16)
        k = torch.randn((Z, H, seq_len, HEAD_DIM), device='cuda', dtype=torch.float16)
        v = torch.randn((Z, H, seq_len, HEAD_DIM), device='cuda', dtype=torch.float16)
        
        # We benchmark PyTorch SDPA (which calls FlashAttention backend if possible)
        def run_sdpa():
            return torch.nn.functional.scaled_dot_product_attention(q, k, v, is_causal=True)
            
        def run_s20():
            return holonomic_s20_attention(q.to(torch.float32), k.to(torch.float32), v.to(torch.float32))
            
        # Warmup
        for _ in range(10):
            run_sdpa()
            run_s20()
            
        ms_sdpa, min_ms_sdpa, max_ms_sdpa = triton.testing.do_bench(run_sdpa, quantiles=[0.5, 0.2, 0.8])
        ms_s20, min_ms_s20, max_ms_s20 = triton.testing.do_bench(run_s20, quantiles=[0.5, 0.2, 0.8])
        
        # Calculate theoretically required memory bandwidth in GB/s
        # 3 tensors read (Q, K, V), 1 tensor write (Out)
        bytes_transferred = 4 * q.numel() * q.element_size()
        
        gbps_sdpa = (bytes_transferred / (ms_sdpa * 1e-3)) / 1e9
        gbps_s20 = (bytes_transferred / (ms_s20 * 1e-3)) / 1e9
        
        configs.append({
            'seq_len': seq_len,
            'sdpa_ms': ms_sdpa,
            's20_ms': ms_s20,
            'speedup': ms_sdpa / ms_s20,
            'sdpa_gbps': gbps_sdpa,
            's20_gbps': gbps_s20
        })
        
        print(f"SeqLen: {seq_len:4d} | SDPA: {ms_sdpa:.3f}ms ({gbps_sdpa:.1f} GB/s) | S20: {ms_s20:.3f}ms ({gbps_s20:.1f} GB/s) | Speedup: {ms_sdpa/ms_s20:.2f}x")
        
    df = pd.DataFrame(configs)
    df.to_csv("triton_benchmark_results.csv", index=False)
    
if __name__ == '__main__':
    benchmark_memory_throughput()
