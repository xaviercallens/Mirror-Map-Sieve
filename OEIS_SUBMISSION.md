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

%C A?????? This is the (A,B) = (4,1) member of the Apery-like family
%C A?????? Sum_{k} C(n,k)^A * C(n+k,k)^B; the Apery numbers A005259 are the (2,2) case.
%C A?????? a(n) = _5F_4(-n,-n,-n,-n,n+1; 1,1,1,1; 1), a 3/4-well-poised hypergeometric
%C A?????? value. a(n) is odd and strictly increasing.
%C A?????? a(n) is the diagonal coefficient [x_1^n...x_5^n] of the rational function
%C A?????? 1/((1-x_1)(1-x_2)(1-x_3)(1-x_4)(1-x_5) - x_1*x_2*x_3*x_4); this follows by
%C A?????? expanding 1/(D-M) = Sum_{r>=0} M^r/D^{r+1} and extracting the diagonal.
%C A?????? Empirically a(n) satisfies a linear recurrence of order 4 (verified by an
%C A?????? exact rational nullspace computation over 85 terms); a general-n proof via a
%C A?????? certified creative-telescoping certificate is not yet available to the author.
%C A?????? Proved congruence: a(p) == 3 (mod p^3) for primes p >= 5. The proof is
%C A?????? elementary -- C(p,k)^4 is divisible by p^4 for 1 <= k <= p-1, so the sum
%C A?????? collapses mod p^3 to 1 + C(2p,p), and Wolstenholme's theorem gives the value
%C A?????? 3 -- and the same argument applies to Sum_k C(n,k)^a C(n+k,k) for any a >= 3.
%C A?????? Proved congruence: a(p-1) == 1 (mod p) for all primes p.
%C A?????? Conjectured (numerically checked for primes p <= 200, no proof known):
%C A?????? a(p-1) == 1 (mod p^3) for p >= 5, and the Lucas property
%C A?????? a(m*p + r) == a(m)*a(r) (mod p).
%C A?????? Conjectural interpretation: a(n) may be the holomorphic period of a
%C A?????? one-parameter family of Calabi-Yau manifolds. The minimal Picard-Fuchs
%C A?????? operator appears to have order 4, which would correspond to a Calabi-Yau
%C A?????? 3-fold (despite the weight-5 binomial structure). The mirror-map
%C A?????? coefficients q_d (q_1=1, q_2=9, q_3=165, q_4=4110, q_5=111075, q_6=3316785)
%C A?????? are integers for d <= 16 by exact rational arithmetic, consistent with
%C A?????? Lian-Yau integrality. This geometric reading is conjectural; expert review
%C A?????? by specialists in Calabi-Yau differential operators is invited.

%D A?????? X. Callens, A Weight-5 Apery-like Binomial Sum S_{20}(n): Formally Verified
%D A?????? Supercongruences and a Conjectural Calabi-Yau Period (preprint),
%D A?????? SocrateAI Laboratory, 2026. DOI: 10.5281/zenodo.20747943.
%D A?????? W. Zudilin, Apery-like difference equations, Journees Arithmetiques, 2003.

%H A?????? Xavier Callens, <a href="https://github.com/xaviercallens/Mirror-Map-Sieve">Mirror-Map-Sieve: code, Lean 4 proofs, and data repository</a>
%H A?????? Xavier Callens, <a href="https://doi.org/10.5281/zenodo.20747943">Preprint on Zenodo</a> (2026)
%H A?????? G. Almkvist, C. van Enckevort, D. van Straten, W. Zudilin, <a href="https://arxiv.org/abs/math/0507430">Tables of Calabi-Yau equations</a>, arXiv:math/0507430.
%H A?????? R. H. Lian and S.-T. Yau, <a href="https://arxiv.org/abs/hep-th/9507151">Arithmetic properties of mirror map and quantum coupling</a>, Comm. Math. Phys. 176 (1996), 163-191.

%F A?????? a(n) = Sum_{k=0..n} C(n,k)^4 * C(n+k,k).
%F A?????? a(n) = _5F_4(-n,-n,-n,-n,n+1; 1,1,1,1; 1).
%F A?????? Conjectured asymptotic: a(n) ~ C * n^alpha * G^n with
%F A?????? G = 43.044328670928... (the reciprocal of the smallest positive root of
%F A?????? the relevant algebraic equation; see the preprint).

%e A?????? a(0) = C(0,0)^4 * C(0,0) = 1.
%e A?????? a(1) = C(1,0)^4*C(1,0) + C(1,1)^4*C(2,1) = 1 + 2 = 3.
%e A?????? a(2) = 1 + 16*3 + 1*6 = 55.

%p A?????? a:= n -> add(binomial(n,k)^4*binomial(n+k,k), k=0..n):
%p A?????? seq(a(n), n=0..20);

%t A?????? a[n_]:=Sum[Binomial[n,k]^4*Binomial[n+k,k],{k,0,n}]; Table[a[n],{n,0,20}]

%o A?????? (Python)
%o A?????? from math import comb
%o A?????? def a(n): return sum(comb(n,k)**4 * comb(n+k,k) for k in range(n+1))

%o A?????? (PARI) a(n) = sum(k=0,n, binomial(n,k)^4 * binomial(n+k,k))

%o A?????? (SageMath) def a(n): return sum(binomial(n,k)^4*binomial(n+k,k) for k in range(n+1))

%Y A?????? Cf. A005259 (Apery numbers: Sum C(n,k)^2*C(n+k,k)^2, the (2,2) case).
%Y A?????? Cf. A005258 (Apery numbers for zeta(2): Sum C(n,k)^2*C(n+k,k)).
%Y A?????? Cf. A006480 (Domb-type Sum C(n,k)^2*C(2k,k)).
%Y A?????? Cf. A093388 (Sum C(n,k)^4, no upper binomial factor).
%Y A?????? Cf. A005260 (Franel numbers of order 5: Sum C(n,k)^5).

%K A?????? nonn,easy

%O A?????? 0,2

%A A?????? Xavier Callens (xavier.callens(AT)socrateai.fr), Jun 2026

================================================================================
NOTES FOR THE EDITOR AND FOR PROSPECTIVE REVIEWERS
================================================================================

This draft is submitted in good faith and in a spirit of provisional, correctable
inquiry. A few honest points that bear on whether the sequence merits inclusion:

1. NOVELTY IS UNVERIFIED, NOT ASSERTED. The author searched the OEIS and the
   literature and did not find this exact sum, but "not found" is not the same as
   "new." If this sequence (or its recurrence/Picard-Fuchs operator) already
   appears -- for instance in the Almkvist-van Straten-Zudilin Calabi-Yau tables,
   possibly under a different normalization -- the author would be grateful to be
   told, and will withdraw or amend accordingly. This is the single most useful
   feedback an editor or reader could provide.

2. SIGNIFICANCE IS MODEST BY DESIGN. The sequence is one member of a
   well-studied family (above). The proven congruence a(p) == 3 (mod p^3) is
   elementary, not deep; it is included because it is cleanly true and has been
   machine-checked, not because it is surprising.

3. WHAT IS PROVED vs CONJECTURED is stated explicitly in the comments. The
   order-4 recurrence is computed but not certified for general n; the
   Calabi-Yau interpretation and the mod-p^3 Apery-style congruence are
   conjectural.

4. FORMAL VERIFICATION. The congruences a(p) == 3 (mod p^3) (p >= 5),
   Wolstenholme's C(2p,p) == 2 (mod p^3), and a(p-1) == 1 (mod p) have been
   formalized in Lean 4 (Mathlib); each compiles and, under #print axioms,
   depends only on Lean's standard foundational axioms (propext,
   Classical.choice, Quot.sound) -- no sorry, no extra axioms. See the
   repository and VERIFICATION_REPORT.md.

--------------------------------------------------------------------------------
SUBMISSION INSTRUCTIONS
--------------------------------------------------------------------------------
1. Go to https://oeis.org/Submit.html and log in.
2. Paste the block above (from %I to %A) into the form.
3. Sequence field (first terms):
   1, 3, 55, 1155, 29751, 852753, 26097499, 840454275, 28064517175, 964417304253
4. Offset 0; Name: a(n) = Sum_{k=0..n} C(n,k)^4 * C(n+k,k); Keywords: nonn, easy.
5. Add the Zenodo DOI and GitHub URL in Links.
6. The editor assigns the A-number. NOTE: A397213 is the author's *proposed*
   draft identifier; until an editor accepts the submission it is NOT an
   approved OEIS entry and must not be cited as one.
7. After acceptance, update README.md, memory.md, and the papers with the
   confirmed A-number.

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
