# Mirror Map Sieve — Roadmap

## Phase 1: Discovery & Publication ✅ COMPLETE
- [x] Discover S(n) = sum C(n,k)^4 * C(n+k,k)
- [x] Extract order-5, degree-9 recurrence (Q-nullspace, 80 terms)
- [x] Verify mirror map integrality (d ≤ 16)
- [x] Lean 4 base-case verification (sorry-free)
- [x] Paper v3 camera-ready
- [x] Zenodo DOI 10.5281/zenodo.20747943
- [x] GitHub release v1.0.0

## Phase 2: Repository Hardening (Next 1-2 Weeks)
**Goal: Make the repository withstand expert scrutiny.**

### Week 1: Critical Fixes
- [ ] Strip all "Callens-ALIX" self-eponymy from README, data files, and scripts
- [ ] Rewrite Lean 4 claims to accurately reflect scope (base cases only)
- [ ] Create full pytest test suite (recurrence at 70 points, mirror map, data integrity)
- [ ] Fix broken references (proof_artifacts path, version mismatch)
- [ ] Make solver script write JSON output directly

### Week 2: OEIS + arXiv
- [ ] Submit sequence to OEIS (first 30+ terms, recurrence, links)
- [ ] Package paper for arXiv (tex + bbl, cross-listed math.AG/math.NT/cs.SC)
- [ ] Decide fate of AI hardware section (remove or rephrase as "illustrative demo")

## Phase 3: Supercongruences (Next 1-3 Months)
**Goal: Resolve the three open conjectures. This is the highest-impact work.**

### Lucas Congruence: S(mp+r) ≡ S(m)S(r) (mod p)
- **Approach**: Apply Lucas's theorem directly to each binomial factor in the summand
- **Difficulty**: Low-moderate (standard p-adic technique)
- **Tools**: SageMath symbolic computation + manual proof

### Apéry-style: S(p-1) ≡ 1 (mod p³)
- **Approach**: p-adic Gamma function techniques (Beukers/Ahlgren/Osburn framework)
- **Difficulty**: Moderate-high
- **Tools**: WZ-pairs evaluated p-adically

### Cubic: S(p) ≡ 3 (mod p³)
- **Approach**: Unknown — this is the genuinely novel finding
- **Difficulty**: High (may require formal group law of the CY 4-fold)
- **Tools**: Deep number theory; may need expert collaboration
- **Fallback**: Present as strong computational evidence up to p ≤ 100+

### Deliverables
- [ ] Paper v4 or standalone note with proofs/extended evidence
- [ ] Lean 4 formalization of proven congruences
- [ ] Updated Zenodo record

## Phase 4: Community Engagement (Months 3-6)
**Goal: Get the work recognized by the number theory community.**

- [ ] Post to MathOverflow (diagonal representation is a strong open question)
- [ ] Contact Wadim Zudilin (leading expert on Apéry-like sequences)
- [ ] Contact Robert Osburn (supercongruences specialist)
- [ ] Submit to Experimental Mathematics or Journal of Number Theory
- [ ] Present at a workshop (CIRM, Oberwolfach, or AIM)

## Phase 5: Diagonal Representation (Long-term)
**Goal: Find F(x₁,...,x₅) such that Diag(F) = S(n). This is an open research problem.**

- The `diagonal_search.py` script has already eliminated several natural candidates
- The integral representation CT[Λⁿ · R] is known but R is rational, not Laurent
- The key question: can R be absorbed into Λ?
- This may require techniques from Bostan-Lairez-Salvy or new ideas

---

## Key Milestones

| Milestone | Target Date | Impact |
|-----------|-------------|--------|
| OEIS A-number assigned | July 2026 | Permanence in mathematics |
| arXiv preprint live | July 2026 | Visibility |
| Lucas congruence proved | Aug 2026 | Paper v4 upgrade |
| Apéry supercongruence | Sep 2026 | Significant number theory result |
| Journal submission | Oct 2026 | Peer review |
| Cubic congruence resolved | Dec 2026 | Major contribution if proved |
