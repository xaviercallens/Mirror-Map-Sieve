import torch
import pytest
from s20_attention import holonomic_s20_attention

def naive_s20_attention(q, k, v):
    """
    Reference PyTorch implementation.
    """
    assert q.dim() == 4
    Z, H, N_CTX, HEAD_DIM = q.shape
    
    # Compute QK^T
    scores = torch.matmul(q, k.transpose(-2, -1)) # [Z, H, N_CTX, N_CTX]
    
    # Create distance matrix
    idx = torch.arange(N_CTX, device=q.device)
    d = idx.unsqueeze(1) - idx.unsqueeze(0) # [N_CTX, N_CTX]
    d = d.unsqueeze(0).unsqueeze(0) # [1, 1, N_CTX, N_CTX]
    
    # Apply causal mask and sparsity cutoff
    valid_mask = (d >= 0) & (d < 3)
    
    # Compute S20 decay
    decay = torch.zeros_like(scores)
    decay[d == 0] = 1.0 / 1.0
    decay[d == 1] = 1.0 / 3.0
    decay[d == 2] = 1.0 / 55.0
    
    # Apply decay and mask
    scores = scores * decay * valid_mask.float()
    
    # Multiply by V (no softmax!)
    out = torch.matmul(scores, v)
    return out

@pytest.mark.parametrize("Z, H, N_CTX, HEAD_DIM", [
    (1, 2, 128, 64),
    (2, 4, 256, 128),
    (1, 1, 100, 64), # Non-power of 2
])
def test_s20_triton_vs_pytorch(Z, H, N_CTX, HEAD_DIM):
    torch.manual_seed(42)
    q = torch.randn((Z, H, N_CTX, HEAD_DIM), device='cuda', dtype=torch.float32)
    k = torch.randn((Z, H, N_CTX, HEAD_DIM), device='cuda', dtype=torch.float32)
    v = torch.randn((Z, H, N_CTX, HEAD_DIM), device='cuda', dtype=torch.float32)
    
    out_ref = naive_s20_attention(q, k, v)
    out_tri = holonomic_s20_attention(q, k, v)
    
    # Check numerical equivalence
    torch.testing.assert_close(out_tri, out_ref, atol=1e-5, rtol=1e-5)
