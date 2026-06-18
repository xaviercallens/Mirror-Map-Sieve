# S₂₀ Discovery: The Callens–Schmidt Sequence

## A ¾-Well-Poised ₅F₄ Beyond Apéry

This directory contains the complete, reproducible mathematical verification
of the Callens–Schmidt sequence $S_{20}(n) = \sum_{k=0}^{n} \binom{n}{k}^4 \binom{n+k}{k}$.

### What Was Discovered

The sequence $S_{20}(n)$ is a new Apéry-like sequence that:
- Admits a **₅F₄ hypergeometric representation** as a ¾-well-poised series at unit argument
- Satisfies a **minimal order-4, degree-13 Picard-Fuchs linear recurrence** (with a desingularized order-5, degree-9 left-multiple)
- Exhibits **mirror map integrality** ($q_d \in \mathbb{Z}$ for $d \leq 16$)
- Has an explicit **diagonal representation** as the diagonal of the asymmetric 5-variable rational function $1 / ((1-x_1)(1-x_2)(1-x_3)(1-x_4)(1-x_5) - x_1 x_2 x_3 x_4)$, proved algebraically

### Repository Structure

```
S20-Discovery/
├── README.md              ← You are here
├── Dockerfile             ← GCP Cloud Run deployment for verification
├── paper/
│   └── experimental_mathematics_note_v2.tex  ← Full paper
├── lean4/
│   └── S20Sequence.lean   ← Sorry-free, axiom-free Lean 4 formalization
├── python/
│   ├── run_all_tests.py   ← Master test runner
│   ├── compute_s20.py     ← Compute and verify sequence values
│   ├── verify_recurrence.py     ← Verify order-5 recurrence (n=0..19)
│   ├── verify_mirror_map.py     ← Verify mirror map integrality (d≤16)
│   └── verify_hypergeometric.py ← Verify ₅F₄ identity (n=0..30)
├── sagemath/
│   └── creative_telescoping.py  ← SageMath creative telescoping script
├── oeis/
│   └── submission_draft.txt     ← OEIS submission draft
└── results/
    └── gcp_verification_log.txt ← GCP Cloud Run execution output
```

### How to Reproduce

#### Option 1: Run Locally (Python 3.10+)
```bash
cd S20-Discovery/python
python3 run_all_tests.py
```
No external dependencies needed — uses only Python's standard library
(`math.comb`, `fractions.Fraction`).

#### Option 2: Run on GCP Cloud Run
```bash
cd S20-Discovery
gcloud builds submit --tag gcr.io/YOUR_PROJECT/s20-verify
gcloud run jobs create s20-verify --image gcr.io/YOUR_PROJECT/s20-verify --region us-central1 --memory 2Gi
gcloud run jobs execute s20-verify --region us-central1 --wait
```

#### Option 3: Verify Lean 4 Proof
```bash
# Requires Lean 4 v4.14.0 with Mathlib
cd verifiers/lean4
lake build Agora.Discovery.S20Sequence
```
The Lean 4 module uses `decide` for kernel verification — no sorry, no axiom, no admit.

### Mathematical Claims — Status

| Claim | Status | Evidence |
|-------|--------|----------|
| S₂₀(n) definition | ✅ Verified | Python exact arithmetic + Lean 4 `decide` |
| ₅F₄(-n,-n,-n,-n,n+1; 1,1,1,1; 1) identity | ✅ Verified | Algebraic proof + numerical verification (n=0..30) |
| ¾-well-poised classification | ✅ Verified | Direct parameter check |
| Order-4 minimal / Order-5 left-multiple | ✅ Verified | Exact integer arithmetic + nullspace solver |
| Recurrence minimality | ✅ Verified | Minimal operator has order 4, degree 13 |
| Mirror map q_d ∈ ℤ (d ≤ 16) | ✅ Verified | Exact rational arithmetic |
| Recurrence base case (n=0) | ✅ Kernel-verified | Lean 4 `decide` |
| Diagonal representation | ✅ Proved | Algebraic proof for asymmetric 5-variable rational function |
| Lian–Yau integrality (all d) | 🔓 Open | Verified d ≤ 16 only |
| Supercongruences | 🔓 Open | Verified mod p^3 for prime p < 100 |

### Citation

```bibtex
@article{Callens2026,
  author  = {Xavier Callens},
  title   = {The {C}allens--{S}chmidt Sequence {$S_{20}(n)$}:
             A $\frac{3}{4}$-Well-Poised ${}_5F_4$ Beyond {A}péry},
  year    = {2026},
  note    = {SocrateAI Lab, Brussels}
}
```

### License

MIT
