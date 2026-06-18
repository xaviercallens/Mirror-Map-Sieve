# Mirror Map Sieve — TODO (Revised After Honest Audit)

## URGENT: Fix Credibility Issues Before arXiv Submission

### [ ] 1. Fix Self-Eponymy Remnants in README
- [ ] Replace "Callens-ALIX Sequence" → "Weight-5 Apéry-like binomial sum S(n)" in glossary (line 20)
- [ ] Replace "Callens-ALIX Sequence" → "Weight-5 Apéry-like binomial sum S(n)" in breakthroughs (line 28)
- [ ] Replace "Callens-ALIX Attention Kernel" → "S₂₀-based Attention Kernel" or remove section
- [ ] Update `data/s20_terms.json` to replace `"sequence": "Callens-ALIX"` → `"sequence": "S20"`
- [ ] Rename files: callens_alix_kernel.py → s20_decay_kernel.py (if keeping)

### [ ] 2. Fix Overstatements in README
- [ ] Change Lean 4 badge from "Verified 0 Axioms" → "Base Cases Kernel-Verified"
- [ ] Add explicit scope note: "Lean verifies base cases at n=0,1 and 8 exact values. General recurrence established by WZ certificate."
- [ ] Remove or rephrase "formally verified in the Lean 4 kernel" (line 48) — say "base cases verified"
- [ ] Fix benchmark table: note "CPU benchmark" not GPU

### [ ] 3. Fix Broken References
- [ ] Remove `proof_artifacts/sage_zeilberger_gcp.log` reference from extracted_polynomials.json (file doesn't exist)
- [ ] Fix lean_version in extracted_polynomials.json: v4.14.0 → v4.31.0

### [ ] 4. Fix Comment Bug in diagonal_search.py
- [ ] Line 23: wrong first values "1, 6, 126, 5040, 297990" → "1, 3, 55, 1155, 29751"

---

## HIGH: Create Real Test Suite

### [ ] 5. Create tests/ Directory
- [ ] Create `tests/test_sequence.py` — verify S(n) at 10+ points
- [ ] Create `tests/test_recurrence.py` — verify recurrence at n=0..69
- [ ] Create `tests/test_mirror_map.py` — verify q_d integrality
- [ ] Create `tests/test_polynomials.py` — verify JSON data integrity
- [ ] Create `tests/conftest.py` — shared fixtures
- [ ] Update CI to run pytest

### [ ] 6. Make Solver Script Write Output
- [ ] Modify `guess_s20_recurrence_int.py` to write `extracted_polynomials.json` directly
- [ ] Add a verification step that reads back and checks against computed values

---

## HIGH: Mathematical Next Steps

### [ ] 7. Submit to OEIS
- [ ] Submit S(n) = sum C(n,k)^4 * C(n+k,k) with first 30 terms
- [ ] Include the recurrence, generating function info, and repository link
- [ ] Get an A-number assigned

### [ ] 8. Prove Supercongruences (Next Session)
- [ ] Lucas: S(mp+r) ≡ S(m)S(r) (mod p)
- [ ] Apéry: S(p-1) ≡ 1 (mod p³) for primes p ≥ 5
- [ ] Cubic: S(p) ≡ 3 (mod p³) for primes p ≥ 5

---

## MEDIUM: Repository Quality

### [ ] 9. Decide on AI Hardware Section
**Recommendation: Remove or drastically reduce.** It dilutes the mathematical message and the "topological decay" claim is not supported. If keeping, be honest: "We use S₂₀ values as a demonstration of integer-arithmetic attention decay. The choice of S₂₀ is illustrative, not theoretically motivated."

### [ ] 10. arXiv Submission
- [ ] Package .tex + .bbl into .tar.gz
- [ ] Set primary category math.AG, cross-list math.NT, cs.SC
- [ ] Include DOI in metadata

### [ ] 11. Improve Dockerfile
- [ ] Test that Docker build actually works
- [ ] Add a `make test` target
