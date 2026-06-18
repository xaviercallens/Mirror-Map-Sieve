# SymBrain v12: PSLQ-Guided MCTS for Solvability Class 2 Constants

> **Auto-Research Report & Implementation Plan**
> **Version**: v3.3.0 (planned)
> **Date**: 2026-06-03
> **Researcher**: Socrate AI Lab / Antigravity Auto-Research Pipeline

---

## 1. Research Context & Motivation

The HorizonMath Top 5 evaluation (v3.2.0) demonstrated that the Agora pipeline produces **structurally interesting** heuristic candidates for Solvability Class 3 problems (constants with no known closed form), achieving relative errors between 9.3% and 114%. However, the candidates were fundamentally limited because:

1. **PSLQ runs as a post-hoc filter** — the existing [pslq_reduction.py](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/agents/galois/pslq_reduction.py) module is invoked *after* MCTS completes, not *during* tree search.
2. **The MCTS leaf evaluation uses LLM-based PRM scoring** — the [mcts_reasoner.py](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/agents/galois/tools/mcts_reasoner.py) `process_reward_model_eval()` calls Gemini to score logical steps, but never tests whether the candidate *numerically snaps* to an exact algebraic relation.
3. **Solvability Class 2 problems are the sweet spot** — these are constants *believed* to have closed forms (like Catalan's $G$, Apéry's $\zeta(3)$ relatives, Bessel moments $c_{5,1}$), where PSLQ has the best chance of discovering genuine identities rather than numerological coincidences.

### The Core Idea (from Lead Mathematician)

> *"Give the Galois agent direct execution access to `mpmath.pslq` during its MCTS tree search. If Galois can dynamically test integer relations at the leaf nodes, it could automatically snap near-miss heuristic guesses into highly precise algebraic conjectures before passing them to Euler."*

This represents an architectural shift from:
```
MCTS → LLM evaluation → post-hoc PSLQ filter → Euler
```
to:
```
MCTS → PSLQ-at-leaf evaluation → automatic snapping → Euler
```

### Literature Survey

| Reference | Key Finding | Relevance |
|:---|:---|:---|
| **Ramanujan Machine (ICLR 2025)** | PSLQ discovers 75 new formulas for $\pi$, $e$, $\ln(2)$ via hypergraph library | Validates PSLQ as a discovery engine, not just a verifier |
| **Ferguson-Bailey-Arwade (1999)** | PSLQ complexity: polynomial in $n$ (basis size); requires $\geq nd$ digits where $d$ = coefficient magnitude | Sets precision floor for our integration |
| **Duminil-Copin & Smirnov (2012)** | $\mu_{\text{hex}} = \sqrt{2+\sqrt{2}}$ proved via parafermionic observables | Only known exact connective constant — validates Class 2 difficulty |
| **Conservative Matrix Fields (2025)** | CMFs unify relations between $\pi$, $e$, $\zeta(3)$, Catalan's $G$ | Provides structural basis vectors for our PSLQ hunts |

### Cost Analysis

At $11.06/hr per H100 GPU (GCP on-demand), a $100 budget allows:
- **~9 GPU-hours** of H100 compute
- PSLQ at 500 DPS takes ~50ms per call on CPU (no GPU needed for PSLQ itself)
- The LLM calls (Gemini 2.5 Pro) dominate cost: ~$0.01/call × 5 problems × 50 MCTS iterations × 3 expansions = ~$7.50
- **Net available for experimentation**: ~$85 after LLM costs

> [!TIP]
> PSLQ itself is CPU-bound (`mpmath` arbitrary precision arithmetic) — the GPU budget is for LLM-based MCTS expansion and PRM scoring, not for PSLQ. This makes the $100 budget highly feasible.

---

## 2. Five Research Hypotheses

### H1: PSLQ-at-Leaf Reward Augmentation 🏆 **(SELECTED)**

**Statement**: Augmenting the MCTS leaf-node reward function with a real-time `mpmath.pslq` call against a standard basis $\mathbf{V} = [T, C, \pi, \pi^2, \sqrt{2}, \zeta(3), G, \ln(2), 1]$ will produce candidates with relative errors $<1\%$ for at least 2 out of 5 Solvability Class 2 HorizonMath constants within a single MCTS search session.

**Mechanism**: After the LLM generates a candidate expression $C$ at a leaf node, evaluate $C$ to 500 DPS using `mpmath`, then run:
```python
relation = mpmath.pslq([T, C, pi, pi**2, sqrt(2), zeta(3), catalan, log(2), 1], tol=1e-200)
```
If a relation is found with residual $< 10^{-50}$ (the "confidence drop" threshold from `PSLQReductionWorker`), assign reward = 1.0 (maximum). Otherwise, use the standard PRM score.

**Testable Prediction**: The PSLQ-augmented MCTS will produce at least one identity with residual $< 10^{-100}$ for a Solvability Class 2 constant.

**Budget**: ~$25 (5 problems × 10 MCTS iterations × 3 LLM calls + CPU PSLQ)

---

### H2: Multi-Pass PSLQ Basis Ladder

**Statement**: A hierarchical PSLQ strategy — first testing a small basis (6 elements), then expanding to a larger basis (12 elements) only when the small basis fails — will discover relations 3× faster than a single large-basis PSLQ call while using 40% less precision.

**Mechanism**: Three passes:
1. **Pass A (additive)**: $[T, C, \pi, \sqrt{2}, 1]$ at 200 DPS
2. **Pass B (multiplicative)**: $[\ln T, \ln C, \ln\pi, \ln 2, \ln 3, \ln 5]$ at 200 DPS
3. **Pass C (full)**: $[T, C, \pi, \pi^2, e, \sqrt{2}, \sqrt{3}, \zeta(3), G, \Gamma(1/4), \ln 2, 1]$ at 500 DPS

**Testable Prediction**: Pass A or B will succeed for at least 1 constant, avoiding the expensive Pass C.

**Budget**: ~$15 (CPU-only PSLQ, no LLM)

---

### H3: Adaptive Basis Expansion via Cortex Domain Routing 🏆 **(SELECTED)**

**Statement**: The SymBrain v12 Cortex should dynamically select the PSLQ basis vector based on the mathematical domain detected by the PFC router. A combinatorics problem should test against lattice-specific constants ($\mu_{\text{hex}}$, polygon areas), while a number-theory problem should test against $\zeta$-values, Bernoulli numbers, and Euler products. This domain-aware basis selection will reduce false-positive PSLQ matches by $>80\%$ compared to a universal basis.

**Mechanism**: Extend `GaloisCortexConfig` with a `pslq_basis_registry`:
```python
PSLQ_BASIS_REGISTRY = {
    "number_theory": [target, cand, pi, pi**2, zeta(3), zeta(5), euler_gamma, log(2), 1],
    "combinatorics": [target, cand, pi, sqrt(2), sqrt(3), mu_hex, catalan, 1],
    "analysis": [target, cand, pi, e, euler_gamma, log(2), log(3), sqrt(pi), 1],
    "algebra": [target, cand, pi, sqrt(2), sqrt(5), phi, log(2), zeta(3), 1],
}
```
The PFC router (already in `cortex_v4.py`) selects the appropriate basis before the PSLQ call.

**Testable Prediction**: Domain-specific bases will produce $\leq 1$ false positive per 50 MCTS evaluations, vs $\geq 5$ false positives with a universal basis.

**Budget**: ~$30 (5 problems × extended MCTS with domain routing + LLM calls)

---

### H4: PSLQ-Guided Backtracking (o1-Style Inner Monologue)

**Statement**: When PSLQ returns a relation with a high residual ($10^{-20} < r < 10^{-50}$), the Galois agent should use this as a "warm start" signal to regenerate the candidate expression with a tighter constraint prompt, effectively creating a PSLQ-in-the-loop refinement cycle.

**Mechanism**: If PSLQ finds a near-miss relation (coefficients with small norms but residual $> 10^{-50}$), inject the relation back into the LLM prompt:
```
"PSLQ found a near-relation: 3·T + 2·C - 7·π ≈ 0 with residual 1e-25.
 Refine the candidate expression to reduce this residual below 1e-100."
```

**Testable Prediction**: At least 1 near-miss relation will be refined to a full identity ($r < 10^{-100}$) within 3 refinement cycles.

**Budget**: ~$20 (LLM refinement calls)

---

### H5: Conservative Matrix Field (CMF) Exhaustive Enumeration

**Statement**: Instead of relying on MCTS to propose candidate expressions, systematically enumerate all Conservative Matrix Fields of dimension $\leq 3$ and evaluate their characteristic polynomials at integer points, then test the resulting values against Solvability Class 2 targets using PSLQ.

**Mechanism**: Following the Ramanujan Machine's CMF framework (ICLR 2025), generate continued fraction representations from matrix products and test convergence against HorizonMath targets.

**Testable Prediction**: CMF enumeration will discover at least 1 new continued-fraction formula for a Class 2 constant.

**Budget**: ~$10 (CPU-only, no LLM)

---

## 3. Hypothesis Selection & Justification

### Selected: H1 (PSLQ-at-Leaf) + H3 (Adaptive Basis Expansion)

| Criterion | H1 | H2 | H3 | H4 | H5 |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Architectural impact** | ★★★★★ | ★★☆☆☆ | ★★★★★ | ★★★☆☆ | ★★☆☆☆ |
| **Scientific novelty** | ★★★★☆ | ★★☆☆☆ | ★★★★★ | ★★★☆☆ | ★★★☆☆ |
| **Feasibility in $100** | ★★★★★ | ★★★★★ | ★★★★☆ | ★★★☆☆ | ★★★★★ |
| **Integration with existing code** | ★★★★★ | ★★★★☆ | ★★★★★ | ★★★☆☆ | ★☆☆☆☆ |
| **Testability** | ★★★★★ | ★★★★☆ | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| **Total** | **24** | **17** | **24** | **15** | **15** |

> [!IMPORTANT]
> **H1** and **H3** are complementary: H1 defines *where* PSLQ is called (leaf nodes), while H3 defines *what* PSLQ tests (domain-specific basis vectors). Together they form the complete SymBrain v12 PSLQ-MCTS integration.

### Combined Budget: $55 (well within $100)

| Component | Est. Cost |
|:---|:---|
| LLM calls (Gemini 2.5 Pro, ~250 calls) | $25.00 |
| CPU PSLQ at 500 DPS (~500 calls) | $0.00 (CPU) |
| H100 GPU warmup + MCTS (1 GPU-hour) | $11.06 |
| Lean 4 verification (5 theorems) | $0.00 (CPU) |
| Monograph generation (WeasyPrint + Pandoc) | $0.00 (CPU) |
| Turing billing overhead | $5.00 |
| **Buffer** | **$13.94** |
| **Total** | **$55.00** |

---

## 4. Proposed Changes — SymBrain v12 Implementation Plan

### Component 1: PSLQ Leaf-Node Evaluator

#### [NEW] [agents/galois/tools/pslq_leaf_evaluator.py](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/agents/galois/tools/pslq_leaf_evaluator.py)

A new module that wraps `mpmath.pslq` for real-time MCTS leaf-node evaluation:

- `PSLQLeafEvaluator` class with configurable basis registry, precision (DPS), and confidence thresholds
- `evaluate_candidate(target: mpf, candidate_expr: str) -> PSLQResult` method
- Multi-pass strategy: additive → multiplicative → full basis
- Returns `PSLQResult(found: bool, relation: list[int], residual: float, confidence: str, basis_labels: list[str])`

---

### Component 2: MCTS Reasoner Integration

#### [MODIFY] [mcts_reasoner.py](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/agents/galois/tools/mcts_reasoner.py)

- Add `pslq_evaluator: Optional[PSLQLeafEvaluator]` parameter to `MCTSReasoner.__init__`
- In the backpropagation step (line ~209), after PRM evaluation:
  ```python
  if self.pslq_evaluator and node.candidate_value is not None:
      pslq_result = self.pslq_evaluator.evaluate_candidate(target, node.candidate_value)
      if pslq_result.found and pslq_result.confidence == "EXACT":
          reward = 1.0  # Override PRM with PSLQ certainty
          node.pslq_relation = pslq_result.relation
  ```
- Add `candidate_value: Optional[float]` and `pslq_relation: Optional[list[int]]` to `ThoughtNode`

---

### Component 3: Domain-Aware Basis Registry

#### [MODIFY] [cortex_v11.py → cortex_v12.py](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/agents/galois/symbrain/cortex_v11.py)

#### [NEW] [agents/galois/symbrain/cortex_v12.py](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/agents/galois/symbrain/cortex_v12.py)

- Extends `SymBrainV11Cortex` with:
  - `PSLQ_BASIS_REGISTRY: dict[str, list[Callable]]` — domain→basis mapping
  - `select_pslq_basis(domain: str) -> list[mpf]` — returns evaluated basis at current DPS
  - `pslq_discovery_log: list[PSLQResult]` — tracks all discovered relations across MCTS sessions

---

### Component 4: Solvability Class 2 Problem Set

#### [NEW] [examples/run_horizonmath_class2_pslq.py](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/examples/run_horizonmath_class2_pslq.py)

The orchestration script targeting Class 2 constants:

| Constant | Target Value | Domain | PSLQ Basis |
|:---|:---|:---|:---|
| Catalan's $G = \beta(2)$ | $0.9159655...$ | number_theory | $[\zeta(3), \pi^2, \ln 2, G, 1]$ |
| $\zeta(5)$ | $1.0369277...$ | number_theory | $[\pi^5, \zeta(3), \zeta(3)^2, \ln 2, 1]$ |
| Bessel moment $c_{5,1}$ | $2.4965992...$ | analysis | $[\Gamma(1/4)^4, \pi, \sqrt{2}, \zeta(3), 1]$ |
| Mertens constant $M$ | $0.2614972...$ | number_theory | $[\gamma, \ln\ln 2, \ln 2, \pi, 1]$ |
| Landau-Ramanujan $K$ | $0.7642...$ | number_theory | $[\pi, \sqrt{2}, \ln 2, \gamma, 1]$ |

---

### Component 5: Extended PSLQReductionWorker

#### [MODIFY] [pslq_reduction.py](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/agents/galois/pslq_reduction.py)

- Add `hunt_full(target, candidate, basis_labels, basis_values, tol)` method for arbitrary basis vectors
- Add `hunt_continued_fraction(target, max_depth=10)` method for detecting continued-fraction representations
- Add `validate_relation(relation, basis_values) -> bool` method that re-evaluates at 1000 DPS to confirm

---

### Component 6: Lean 4 Identity Verification

#### [NEW] [verifiers/lean4/Agora/PSLQIdentity.lean](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/verifiers/lean4/Agora/PSLQIdentity.lean)

Template theorems for PSLQ-discovered identities:
```lean
-- Template for a PSLQ-discovered linear identity
theorem pslq_identity_{constant_name}
    (h : {lhs_expression} = {rhs_expression}) :
    |{lhs_expression} - {rhs_expression}| < ε := by
  norm_num [h]
```

---

### Component 7: Version & Documentation Updates

#### [MODIFY] [pyproject.toml](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/pyproject.toml)
- Bump version to `3.3.0`
- Add `mpmath>=1.3.0` to dependencies (ensure `pslq` availability)

#### [MODIFY] [ROADMAP.md](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/ROADMAP.md)
- Add **Phase 8: SymBrain v12 — PSLQ-Guided Discovery** section
- Update Phase 7 PSLQ milestone from "📋 Planned" to "✅ Done"

#### [MODIFY] [TODO.md](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/TODO.md)
- Mark PSLQ-related items as in-progress
- Add SymBrain v12 items

#### [MODIFY] [README.md](file:///Users/xcallens/xdev/SocrateAI-Scientific-Agora/README.md)
- Add v3.3.0 accomplishment entry
- Update SymBrain version references from v11 to v12

---

## 5. Verification Plan

### Automated Tests

1. **Unit tests**: `tests/test_pslq_leaf_evaluator.py`
   - Test that PSLQ correctly identifies known identities (e.g., $\pi = 4\arctan(1)$)
   - Test false-positive rate with random noise inputs
   - Test domain basis selection routing

2. **Integration test**: `tests/test_mcts_pslq_integration.py`
   - Run a 3-iteration MCTS with PSLQ-at-leaf on Catalan's constant
   - Verify that the PSLQ reward override triggers correctly

3. **End-to-end**: `python examples/run_horizonmath_class2_pslq.py`
   - Execute the full pipeline on 5 Class 2 constants
   - Verify monograph generation with PSLQ results
   - Verify GCP teardown and cost under $100

### Success Criteria

- [ ] At least 1 PSLQ identity discovered with residual $< 10^{-100}$
- [ ] Domain-specific basis reduces false positives by $>50\%$ vs universal basis
- [ ] Total experiment cost $< $100
- [ ] All new code passes `test_no_stubs.py` anti-mock linter
- [ ] Monograph PDF/TEX/EPUB generated successfully

---

## 6. Open Questions

> [!IMPORTANT]
> **Q1**: Should the PSLQ-at-leaf evaluation be **blocking** (synchronous, adds ~50ms per leaf) or **async** (fire-and-forget, update reward retroactively during backpropagation)? Blocking is simpler but may slow MCTS iterations.

> [!IMPORTANT]
> **Q2**: Should we include **Ramanujan Machine CMF enumeration** (H5) as an optional secondary mode in v12, or defer it to v13? CMF is architecturally independent from MCTS and could run as a parallel background process.

> [!WARNING]
> **Q3**: The PSLQ algorithm can produce **spurious relations** with large coefficients when precision is insufficient. Our confidence threshold ($r < 10^{-50}$) and coefficient norm bound ($\|a\|_\infty < 1000$) should prevent this, but we need explicit regression tests.
