%I A??????
%S A?????? 1,3,55,1155,29751,852753,26097499,840454275,28064517175,
%T A?????? 964417304253,33903837716805,1214258225057265,44166395275424475,
%U A?????? 1627604857066000725,60654810749855283555,2282379931043443585155,
%V A?????? 86613897907152215198775,3311529972822006548243925,
%W A?????? 127452628730493465426429625,4934498269789812991102113405,
%X A?????? 192066838040688957553828738501,7511993870030888837983610402883,
%Y A?????? 295093862567263496653118628410985,11638606519868729613471645167289585,
%Z A?????? 460714918076272178379736038666092251

%N A?????? a(n) = Sum_{k=0..n} C(n,k)^4 * C(n+k,k).

%C A?????? A weight-5 Apéry-like binomial sum. This sequence is the holomorphic period
%C A?????? of a mirror Calabi-Yau 4-fold. It satisfies an order-5, degree-9 linear
%C A?????? holonomic recurrence with integer polynomial coefficients (see Formula section).
%C A?????? The mirror map q(z) = z * exp(g(z)/f(z)) where f(z) = Sum_{n>=0} a(n)*z^n
%C A?????? has integer coefficients q_d for d=1,2,...,16 (Lian-Yau integrality):
%C A?????? q_1=1, q_2=9, q_3=165, q_4=4110, q_5=111075, q_6=3316785, ...
%C A?????? Computational evidence supports the supercongruences:
%C A?????? a(p-1) == 1 (mod p^3) and a(p) == 3 (mod p^3) for primes p >= 5.

%D A?????? X. Callens, A Weight-5 Apéry-like Binomial Sum, its Calabi-Yau 4-fold Period,
%D A?????? and Supercongruences, SocrateAI Scientific Agora, 2026.
%D A?????? DOI: 10.5281/zenodo.20747943.

%H A?????? Xavier Callens, <a href="https://github.com/xaviercallens/Mirror-Map-Sieve">Mirror-Map-Sieve repository</a>
%H A?????? Xavier Callens, <a href="https://doi.org/10.5281/zenodo.20747943">Preprint on Zenodo</a> (2026)
%H A?????? R. H. Lian and S.-T. Yau, <a href="https://arxiv.org/abs/hep-th/9507151">Arithmetic properties of mirror map and quantum coupling</a>, Comm. Math. Phys. 176 (1996), 163-191.
%H A?????? G. Almkvist, C. van Enckevort, D. van Straten, W. Zudilin, <a href="https://arxiv.org/abs/math/0507430">Tables of Calabi-Yau equations</a>, arXiv:math/0507430.

%F A?????? a(n) = Sum_{k=0..n} C(n,k)^4 * C(n+k,k).
%F A?????? Satisfies the order-5 linear recurrence:
%F A?????? Sum_{j=0}^{5} P_j(n) * a(n+j) = 0, where P_0,...,P_5 are polynomials
%F A?????? of degree 9 with integer coefficients (see Callens 2026 for explicit coefficients).
%F A?????? Asymptotic: a(n) ~ C * 43.0443^n as n -> infinity.

%p A?????? a:= n -> add(binomial(n,k)^4*binomial(n+k,k), k=0..n):
%p A?????? seq(a(n), n=0..20);

%t A?????? Table[Sum[Binomial[n,k]^4 * Binomial[n+k,k], {k,0,n}], {n,0,20}]

%o A?????? (Python)
%o A?????? from math import comb
%o A?????? def a(n): return sum(comb(n,k)**4 * comb(n+k,k) for k in range(n+1))

%o A?????? (PARI)
%o A?????? a(n) = sum(k=0,n, binomial(n,k)^4 * binomial(n+k,k))

%o A?????? (SageMath)
%o A?????? def a(n): return sum(binomial(n,k)^4 * binomial(n+k,k) for k in range(n+1))

%Y A?????? Cf. A005258 (Apéry numbers: Sum C(n,k)^2*C(n+k,k)^2),
%Y A?????? Cf. A006480 (Sum C(n,k)^2*C(2k,k), another weight-3 Apéry-like sum),
%Y A?????? Cf. A093388 (Sum C(n,k)^4, related but no upper binomial factor).

%K A?????? nonn,easy

%O A?????? 0,2

%A A?????? Xavier Callens (xavier.callens(AT)socrateai.fr), Jun 2026

---
SUBMISSION INSTRUCTIONS
=======================

1. Go to: https://oeis.org/Submit.html
2. Log in (or create an account).
3. Copy the block above (from %I to %A) into the submission form.
4. In the "Sequence" field enter the first terms:
   1, 3, 55, 1155, 29751, 852753, 26097499, 840454275, 28064517175, 964417304253
5. Set "Offset" to 0.
6. In the "Name" field: a(n) = Sum_{k=0..n} C(n,k)^4 * C(n+k,k).
7. Add keywords: nonn, easy
8. Add the Zenodo DOI and GitHub URL in the Links section.
9. The editor will assign an A-number (e.g. A??????).
10. Update memory.md and README.md once the A-number is confirmed.

FIRST 30 TERMS (for verification):
1, 3, 55, 1155, 29751, 852753, 26097499, 840454275, 28064517175, 964417304253,
33903837716805, 1214258225057265, 44166395275424475, 1627604857066000725,
60654810749855283555, 2282379931043443585155, 86613897907152215198775,
3311529972822006548243925, 127452628730493465426429625,
4934498269789812991102113405, 192066838040688957553828738501,
7511993870030888837983610402883, 295093862567263496653118628410985,
11638606519868729613471645167289585, 460714918076272178379736038666092251,
18298951028515637150899096536661977753, 729070814054304816408947896263604043209,
29131470721832417458088089237709021686965,
1167117749666396068705869779920927328740515,
46875530539169650156894476939797848989068253
