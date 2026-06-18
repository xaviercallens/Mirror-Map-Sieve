import torch
import torch.nn.functional as F
from s15_kernel.sequence import compute_decay_table, compute_s20, compute_s15
import functools

# Global cache for decay masks to avoid recomputing per layer/step
_MASK_CACHE = {}

def get_decay_mask(L, device, window_size=32, sequence_fn="s20", causal=True):
    """Get or build the banded decay mask."""
    key = (L, device, window_size, sequence_fn, causal)
    if key in _MASK_CACHE:
        return _MASK_CACHE[key]
        
    fn = compute_s20 if sequence_fn == "s20" else compute_s15
    decay_table = compute_decay_table(fn, max_d=window_size, dtype=torch.float32)
    decay_table = decay_table.to(device)
    
    # Build (L, L) mask
    mask = torch.zeros((L, L), device=device, dtype=torch.float32)
    
    # Fill bands
    for d in range(min(window_size + 1, L)):
        val = decay_table[d]
        mask += torch.diag(torch.full((L - d,), val, device=device), diagonal=d)
        if d > 0:
            mask += torch.diag(torch.full((L - d,), val, device=device), diagonal=-d)
            
    # Apply causal mask if required
    if causal:
        causal_mask = torch.tril(torch.ones(L, L, device=device, dtype=torch.bool))
        mask = mask.masked_fill(~causal_mask, 0.0)
        
    _MASK_CACHE[key] = mask
    return mask

def s20_scaled_dot_product_attention(
    query, key, value, attn_mask=None, dropout_p=0.0, is_causal=False, scale=None,
    window_size=32, sequence_fn="s20"
):
    """
    Drop-in replacement for F.scaled_dot_product_attention using S20/S15 banded decay.
    query, key, value shapes: (B, H, L, Dh) or (B, L, H, Dh) depending on model,
    but SDPA expects (B, H, L, Dh).
    """
    L_q = query.shape[-2]
    L_k = key.shape[-2]
    
    # We only cache masks for the specific length. If doing cross-attention or decoding, L_q != L_k
    # For causal generation, we often have L_q=1 and L_k=sequence_length.
    # The decay depends on distance. 
    # For autoregressive decoding (L_q=1), the distance from the current token (L_k - 1) to previous token i is (L_k - 1 - i).
    
    # 1. L2 Normalize Q and K
    q_norm = F.normalize(query, p=2, dim=-1)
    k_norm = F.normalize(key, p=2, dim=-1)
    
    # 2. Dot-product scores
    scores = torch.matmul(q_norm, k_norm.transpose(-2, -1))  # (B, H, L_q, L_k)
    
    # 3. Apply banded decay mask
    # Need to handle decoding step where L_q = 1, L_k > 1
    if L_q == L_k:
        # Prefill phase or full self-attention
        decay_mask = get_decay_mask(L_q, query.device, window_size, sequence_fn, causal=is_causal)
        scores = scores * decay_mask.to(scores.dtype).unsqueeze(0).unsqueeze(0)
    else:
        # Decoding phase: L_q = 1, L_k is the full context length
        # The query is the LAST token (index L_k - 1).
        # We need the last row of the full decay mask.
        full_mask = get_decay_mask(L_k, query.device, window_size, sequence_fn, causal=True)
        last_row = full_mask[-1:, :]  # shape (1, L_k)
        scores = scores * last_row.to(scores.dtype).unsqueeze(0).unsqueeze(0)
        
    # 4. ReLU + L1 normalisation
    scores = F.relu(scores)
    row_sums = scores.sum(dim=-1, keepdim=True).clamp(min=1e-8)
    attn_weights = scores / row_sums
    attn_weights = attn_weights.to(value.dtype)
    
    # 5. Output
    out = torch.matmul(attn_weights, value)
    return out

class S20PatchContext:
    """Context manager to globally patch F.scaled_dot_product_attention."""
    def __init__(self, window_size=32, sequence_fn="s20"):
        self.original_sdpa = F.scaled_dot_product_attention
        self.patched_sdpa = functools.partial(
            s20_scaled_dot_product_attention,
            window_size=window_size,
            sequence_fn=sequence_fn
        )
        
    def __enter__(self):
        F.scaled_dot_product_attention = self.patched_sdpa
        # Also need to patch in torch.nn.functional if it was imported differently
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        F.scaled_dot_product_attention = self.original_sdpa

_ORIGINAL_SDPA = F.scaled_dot_product_attention

def patch_model_with_s20(model, window_size=32, sequence_fn="s20"):
    """
    Permanently patch a model by replacing its SDPA calls.
    For HF models using attn_implementation="sdpa", they call F.scaled_dot_product_attention.
    """
    F.scaled_dot_product_attention = functools.partial(
        s20_scaled_dot_product_attention,
        window_size=window_size,
        sequence_fn=sequence_fn
    )
    print(f"✅ Globally patched F.scaled_dot_product_attention with {sequence_fn} (W={window_size})")
    
def unpatch_model():
    """Restore original SDPA."""
    F.scaled_dot_product_attention = _ORIGINAL_SDPA
    print("✅ Restored original F.scaled_dot_product_attention")
