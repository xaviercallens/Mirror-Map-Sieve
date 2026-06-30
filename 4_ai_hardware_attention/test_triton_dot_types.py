import torch
import triton
import triton.language as tl

@triton.jit
def test_dot_kernel(A, B, C, BLOCK: tl.constexpr, dtype_in: tl.constexpr, dtype_out: tl.constexpr):
    off = tl.arange(0, BLOCK)
    a = tl.load(A + off[:, None] * BLOCK + off[None, :]).to(dtype_in)
    b = tl.load(B + off[:, None] * BLOCK + off[None, :]).to(dtype_in)
    c = tl.dot(a, b, out_dtype=dtype_out)
    tl.store(C + off[:, None] * BLOCK + off[None, :], c.to(tl.float32))

def try_compile(dtype_in, dtype_out):
    print(f"Testing dtype_in={dtype_in}, dtype_out={dtype_out}...")
    try:
        A = torch.randn(16, 16, device="cuda").double()
        B = torch.randn(16, 16, device="cuda").double()
        C = torch.empty(16, 16, device="cuda")
        test_dot_kernel[(1,)](A, B, C, BLOCK=16, dtype_in=dtype_in, dtype_out=dtype_out)
        torch.cuda.synchronize()
        print("  => SUCCESS!")
        return True
    except Exception as e:
        print(f"  => FAILED: {e}")
        return False

def main():
    print("Checking Triton float64 dot compilation:")
    try_compile(tl.float64, tl.float64)

if __name__ == "__main__":
    main()
