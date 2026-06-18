# Draft OEIS Submission for the Callens-ALIX Sequence

To submit the sequence to the On-Line Encyclopedia of Integer Sequences (OEIS), use the following details. 

**Title:**
Number of paths or geometric period related to the mirror Calabi-Yau 4-fold: $S_{20}(n) = \sum_{k=0}^{n} \binom{n}{k}^4 \binom{n+k}{k}$.

**Data (First 80 terms):**
(You can find these in `data/s20_terms.json`, copy the values from there into a comma-separated list).
Example:
`1, 3, 55, 1155, 29751, 852753, 26097499, 840454275, 28064517175, 964417304253, 33903837716805, 1214258225057265, ...`

**Comments:**
This sequence represents the holomorphic period of a mirror Calabi-Yau 4-fold. It exhibits Lian-Yau integrality, where the corresponding mirror map coefficients (instanton numbers) $q_d$ are strictly integers.
The sequence is 3/4-well-poised hypergeometric.

**Formula:**
`a(n) = sum_{k=0..n} binomial(n,k)^4 * binomial(n+k,k)`

The sequence satisfies an order-5, degree-9 linear recurrence with polynomial coefficients. 
The minimal recurrence was extracted via an exact Q-nullspace solver and formally verified in Lean 4.
See the linked repository for the exact 45-digit polynomials `P_0(n) ... P_5(n)`.

**Links:**
- Xavier Callens / SocrateAI Laboratory, [Mirror Map Sieve GitHub Repository](https://github.com/xaviercallens/Mirror-Map-Sieve)
- (Add arXiv link here when available)

**Programs (Python):**
```python
from math import comb
def a(n):
    return sum(comb(n, k)**4 * comb(n + k, k) for k in range(n + 1))
```

**Cross-References:**
Related to A005259 (Apéry numbers) and A002895.

**Author:**
Xavier Callens
