import torch
import math

def test():
    B, H, L, D = 4, 16, 128, 64
    q = torch.randn(B, H, L, D, device="cuda", dtype=torch.float16)
    k = torch.randn(B, H, L, D, device="cuda", dtype=torch.float16)
    slopes = torch.exp(torch.tensor([2**(-8*(h+1)/H) for h in range(H)], device="cuda").log()).to(torch.float16)
    
    for bits in [6, 10, 12, 14]:
        scale_factor = 2.0 ** bits
        q_scaled = q.float() * scale_factor
        q_rounded = torch.where(q_scaled >= 0, torch.trunc(q_scaled + 0.5), torch.trunc(q_scaled - 0.5))
        
        k_scaled = k.float() * scale_factor
        k_rounded = torch.where(k_scaled >= 0, torch.trunc(k_scaled + 0.5), torch.trunc(k_scaled - 0.5))
        
        scores = torch.matmul(q_rounded.double(), k_rounded.transpose(-2, -1).double())
        scores = (scores / (scale_factor * scale_factor)) / math.sqrt(D)
        
        idx = torch.arange(L, device="cuda")
        dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs()
        bias = -slopes.view(1, -1, 1, 1) * dist.unsqueeze(0).unsqueeze(0).to(scores.dtype)
        scores = scores + bias
        
        causal_mask = torch.triu(torch.ones(L, L, device="cuda"), diagonal=1).bool()
        scores = scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float("-inf"))
        
        print(f"bits={bits} | scores finite (ignoring -inf): {torch.isfinite(scores).any().item()} | max score: {scores[scores > -float('inf')].max().item()} | min score: {scores[scores > -float('inf')].min().item()}")

if __name__ == "__main__":
    test()
