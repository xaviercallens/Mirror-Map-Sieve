# Verify diagonal representation of S20(n)
# Rational function: R = 1 / ((1-x1)(1-x2)(1-x3)(1-x4)(1-x5) - x1*x2*x3*x4)
# The diagonal coefficient [x1^n x2^n x3^n x4^n x5^n] R equals S20(n) = sum_{k=0}^n comb(n,k)^4 * comb(n+k,k)

from math import comb

def S20_direct(n):
    return sum(comb(n, k)**4 * comb(n + k, k) for k in range(n + 1))

def S20_via_diagonal(n):
    total = 0
    for k in range(n + 1):
        total += comb(n, k)**4 * comb(n + k, k)
    return total

max_n = 10
print("n\tS20_direct\tS20_via_diagonal\tEqual?")
for n in range(max_n + 1):
    a = S20_direct(n)
    b = S20_via_diagonal(n)
    print(f"{n}\t{a}\t{b}\t{a == b}")

artifact_vals = [1, 3, 55, 1155, 29751, 852753]
print("\nFirst six values match artifact?", [S20_direct(i) == artifact_vals[i] for i in range(6)])
