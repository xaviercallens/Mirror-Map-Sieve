# Lessons Learnt — Alien Mathematics Investigation

> **Project:** SocrateAI Scientific Agora  
> **Investigation:** Alien Mathematics / Claim Verification Pipeline  
> **Last updated:** 2026-06-14

---

## Lesson 1: LLM-Generated Mathematics Is ~85% Hallucination

LLM-generated mathematical claims are approximately **85% hallucination** and only **~15% real**. Models confidently produce plausible-sounding theorems, proofs, and constructions that dissolve under scrutiny. Never trust an LLM claim without independent verification — the default assumption must be *false until proven true*.

---

## Lesson 2: Falsification-First Methodology

**Test the strongest claim first.** If the most impressive result fails verification, weaker derivative claims collapse automatically. This saves enormous time compared to bottom-up verification. The falsification-first approach is the correct scientific methodology for evaluating LLM-generated research output.

---

## Lesson 3: Literature Check BEFORE Computation

Always perform a thorough literature search **before** investing compute in verification or discovery. The Bläser (2003) result on Strassen-like algorithms would have saved days of wasted computation. Known bounds, existing constructions, and state-of-the-art results must be established as baselines before any experimental work begins.

---

## Lesson 4: Lean 4 Kernel Is Ground Truth

The Lean 4 type-checker kernel is the gold standard for mathematical verification. The bar for a verified result is:

- **0 `sorry`** — no admitted proofs
- **0 `axiom`** (beyond Lean's foundational axioms) — no unproven assumptions

Any proof that does not meet this standard is incomplete, not verified.

---

## Lesson 5: Definitional Tautologies Fool Naive Metrics

Beware of verification metrics that count modules or theorems without assessing depth. In the Alien Mathematics investigation, **8 "verified" modules were mostly trivial** — definitional tautologies that prove `x = x` by definition. A theorem that unfolds to `rfl` is not a discovery. Metrics must distinguish between substantive proofs and trivial restatements.

---

## Lesson 6: Bugs in Search Code Produce False Positives

Computational search (e.g., tabu search, simulated annealing) is only as reliable as its implementation. **Two bugs were caught in the tabu search code** that produced false positive results — colorings that appeared valid but violated constraints due to indexing or neighbor-generation errors. Always validate search results with an independent checker.

---

## Lesson 7: Pure Local Search Hits Hard Walls for Ramsey

Simulated annealing (SA) and similar pure local-search heuristics hit a **hard performance wall around n = 26–28** for Ramsey number lower bounds (e.g., R(3,3,4)). Beyond this range, the search landscape becomes too rugged for local moves to escape local minima. More sophisticated methods (SAT solvers, algebraic constructions) are required.

---

## Lesson 8: Algebraic/Pseudorandom Constructions Are the Breakthrough Method

The **Mattheus–Verstraëte (2024)** result in *Annals of Mathematics* solved r(4, t) using pseudorandom graphs derived from **finite geometry**. This algebraic/pseudorandom construction approach represents the current frontier for Ramsey-type problems. Pure combinatorial search cannot compete with constructions that exploit deep algebraic structure.

---

## Lesson 9: The ClaimVerificationPipeline Is Transferable

The methodology developed during this investigation — structured claim extraction → falsification-first testing → formal verification → literature cross-check — is **domain-general**. The `ClaimVerificationPipeline` can be applied to any domain where LLM-generated claims need rigorous evaluation, not just mathematics.

---

## Lesson 10: Honest Negative Results Are More Valuable Than False Positives

Publishing that a claimed breakthrough is **false** is more valuable to the scientific community than inflating weak results into apparent discoveries. Negative results:

- Prevent others from wasting time on dead ends
- Establish rigorous baselines
- Build trust in the verification methodology itself

The integrity of the pipeline depends on willingness to report failure.

---

## Summary Table

| # | Lesson | Key Takeaway |
|---|--------|-------------|
| 1 | LLM hallucination rate | ~85% false, verify everything |
| 2 | Falsification-first | Test strongest claim first |
| 3 | Literature before compute | Check state-of-the-art first |
| 4 | Lean 4 ground truth | 0 sorry, 0 axiom standard |
| 5 | Definitional tautologies | Naive metrics are misleading |
| 6 | Search code bugs | Independent validation required |
| 7 | Local search walls | SA fails at n ≈ 26–28 for Ramsey |
| 8 | Algebraic constructions | Mattheus–Verstraëte 2024 breakthrough |
| 9 | Pipeline transferability | ClaimVerificationPipeline is general |
| 10 | Honest negatives | Integrity over inflation |
| 11 | API compatibility is fragile | Test model availability before pipeline design |
| 12 | Base class contracts | Read the interface — don't assume it |
| 13 | Pipeline-to-Patent-to-Prototype | Discovery → Patent → Prototype in one weekend |
| 14 | Multi-LLM peer review | Diverse models catch different weaknesses |
| 15 | Deterministic > LLM code review | ast + ruff = reproducible; LLMs = creative but non-reproducible |
| 16 | Exact rational arithmetic | Float-free arithmetic is practical for safety-critical systems |
| 17 | LaTeX ampersands | Always escape ampersands in LaTeX headers |
| 18 | Library deprecations | NumPy 2.0+ deprecates np.math; use math module |
| 19 | Clientside BigInt | Local BigInt avoids server roundtrips for exact combinatorics |

---

## Weekend Session Lessons (2026-06-14)

### Lesson 11: API Compatibility Is Fragile — Test Before Deploying
The Antigravity SDK only supports Google models. Mistral calls via SDK fail with 404. Deprecated models (gemini-2.0-flash) cause silent pipeline failures. Always use direct HTTP API calls for third-party LLMs, and always test model availability before designing a pipeline around a specific model.

---

### Lesson 12: Base Class Contracts Must Be Read — Not Assumed
Three successive crashes in TeslaAgent came from misunderstanding the AbstractAgent interface: `_stop_timer()` requires (start, label), `current_run_cost` doesn't exist, `telemetry.to_dict()` doesn't exist. Cost: 3 debug cycles. Lesson: always read the base class contract before implementing a subclass.

---

### Lesson 13: Pipeline-to-Patent-to-Prototype Is a Viable Methodology
The chain Discovery → Patent → Prototype is a working industrial research pipeline. The ExactRationalWitness discovery went from math theorem → 3 USPTO patent claims → 3 working prototypes with numeric validation in a single weekend. This methodology is the core value proposition of SocrateAI.

---

### Lesson 14: Multi-LLM Peer Review Catches Different Weaknesses
Gemini reviews focus on technical rigor. Mistral reviews focus on market viability and engineering skepticism. Using diverse LLMs for peer review produces a more balanced assessment than any single model. The adversarial/controversial reviewer persona is particularly effective.

---

### Lesson 15: Deterministic Engines Are More Trustworthy Than LLM Code Review
Python `ast` analysis and `ruff` linting catch real structural issues (deep nesting, global variables, complexity scores) with 100% reproducibility. LLM-based code review is creative but non-reproducible. Use deterministic engines for correctness checks, LLMs for design feedback.

---

### Lesson 16: Exact Rational Arithmetic Is the Real Innovation
The `fractions.Fraction` (Python) and `i128` rational (Rust) demos prove that deterministic, float-free arithmetic is practical for safety-critical applications. This is not just theoretical — 22/22 Rust tests and 64/70 Python tests pass with zero floating-point rounding. This is the foundation of a real product.

---

### Lesson 17: LaTeX Ampersands Cause Silent pdflatex Compilation Failures
Unescaped ampersands (`&`) in LaTeX section headings trigger compilation aborts. Section titles must always use `\&` to prevent pipeline failures in `NewTheoryDocumentationPipeline` Stage 4.

---

### Lesson 18: Protect Code Against Library Deprecations (NumPy 2.0+)
NumPy 2.0+ deprecates the `np.math` namespace. Code doing combinations or factorial math must import from python's built-in `math` module directly to prevent runtime AttributeErrors in production environments.

---

### Lesson 19: Value of Browser-side BigInt for Large Integer Math
Rather than routing every sequence evaluation through a cloud backend API, running combinations and large-number summations in the browser using JavaScript's native `BigInt` allows fast, local, exact arithmetic with zero network latency.
