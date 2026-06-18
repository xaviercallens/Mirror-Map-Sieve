<!-- Copyright (c) 2026 Xavier Callens / Socrate AI Lab, Paris, France -->
<!-- SPDX-License-Identifier: Apache-2.0 AND CC-BY-NC-ND-4.0 -->
<!-- Patent: US-PAT-PEND-2026-0525 -->

# Specifications — SocrateAI Scientific Agora

> *"Measure what is measurable, and make measurable what is not so."*
> — Galileo Galilei

| Field | Value |
|---|---|
| **Version** | 2.1.0 |
| **Author** | Xavier Callens \<callensxavier@gmail.com\> |
| **Organisation** | Socrate AI Lab, Paris, France |
| **Date** | 2026-06-11 |
| **Status** | Living Document |

---

## Table of Contents

1. [SymBrain Specifications (v1–v7)](#1-symbrain-specifications-v1v7)
2. [RunuX Kernel Modules](#2-runux-kernel-modules)
3. [rusty-SUNDIALS Crates](#3-rusty-sundials-crates)
4. [Agent Specifications](#4-agent-specifications)
5. [Lean 4 Theorem Index](#5-lean-4-theorem-index)
6. [DeepProbLog Program Index](#6-deepproblog-program-index)
7. [NVIDIA NIM Service Contracts](#7-nvidia-nim-service-contracts)
8. [Benchmark Methodology](#8-benchmark-methodology)
9. [Wire Protocols](#9-wire-protocols)
10. [Configuration Schema](#10-configuration-schema)

---

## 1. SymBrain Specifications (v1–v7)

### 1.1 Version History

| Version | Codename | Date | Key Innovation | Spec Status |
|---|---|---|---|---|
| v1 | *Tabula Rasa* | 2025-Q3 | Base transformer + LoRA | ✅ Final |
| v2 | *Reflex Arc* | 2025-Q4 | PFC Router | ✅ Final |
| v3 | *Hippocampal* | 2026-Q1 | MCTS planner + episodic memory | ✅ Final |
| v4 | *Cortical* | 2026-Q2 | RLCF optimiser | ✅ Final |
| v5 | *Sapiens* | 2026-Q3 | Dynamic Gating, Speculative ES, INT8 | ✅ Final |
| v6 | *Heraclitean* | 2026-Q3 | Monograph generation + Peer review pipeline | ✅ Final |
| v7 | *Adler* | 2026-Q3 | Multi-model peer review + Kindle delivery | ✅ Final |
| v8 | *Mind Olympiad* | 2026-Q4 | SIAG routing, Kolmogorov ratio, domain tactics | ✅ Final |
| v8a | *Adler-IMO* | 2026-Q4 | Adler RLFC priors, BSD cohomology reasoning | ✅ Final |
| v9 | *Archimedes* | 2026-Q4 | Hardware-adaptive MCTS, intermediate invariants | ✅ Final |
| v11 | *Dieudonné* | 2026-Q4 | Dopaminergic RPE, Hippocampal Replay | ✅ Final |
| v12 | *PSLQ-Discovery* | 2027-Q1 | PSLQ at leaf nodes, Adaptive Basis Routing | 📋 Planned |

### 1.2 SymBrain v5 Component Specifications

#### PFC Router

| Parameter | Value | Unit |
|---|---|---|
| Complexity classifier | 2-layer MLP, 128 hidden | — |
| Domain classifier | 4-class softmax (STEM, MATH, PROOF, GENERAL) | — |
| Routing latency overhead | < 2 | ms |
| Complexity threshold (Edge) | C < 0.3 | — |
| Complexity threshold (Cloud-32B) | 0.3 ≤ C < 0.7 | — |
| Complexity threshold (Cloud-70B) | 0.7 ≤ C < 0.9 | — |
| Complexity threshold (Cloud-122B) | C ≥ 0.9 | — |

#### RLCF Optimiser

| Parameter | Value | Unit |
|---|---|---|
| Learning rate (η) | 3e-4 | — |
| Lévy stability index (α) | 1.7 | — |
| Noise coefficient (λ) | 0.01 | — |
| Ricci curvature approximation | 2nd-order finite differences | — |
| Curvature estimation batch size | 64 | samples |
| Max gradient norm | 1.0 | — |
| Weight decay | 0.01 | — |

#### LoRA Adapter

| Parameter | Value | Unit |
|---|---|---|
| Rank (r) | 16 | — |
| Alpha (α_lora) | 32 | — |
| Dropout | 0.05 | — |
| Target modules | q_proj, k_proj, v_proj, o_proj | — |
| Trainable parameters | ~0.5% of base model | — |

#### MCTS Planner

| Parameter | Value | Unit |
|---|---|---|
| Max tree depth | 8 | — |
| Max rollouts per step | 64 | — |
| UCB exploration constant (c) | √2 | — |
| Speculative early stop timeout | 500 | ms |
| Value network | Shared with PFC complexity estimator | — |

#### Dynamic Gating

| Parameter | Value | Unit |
|---|---|---|
| Gate function | σ(W_g · [C; h_PFC] + b_g) | — |
| Gate dimension | 256 | — |
| System 1 threshold | σ_ded < 0.3 | — |
| System 2 threshold | σ_ded ≥ 0.7 | — |
| Hybrid zone | 0.3 ≤ σ_ded < 0.7 | — |

#### Co-Processor INT8 Pipeline

| Parameter | Value | Unit |
|---|---|---|
| Quantisation scheme | Per-channel symmetric INT8 | — |
| DMA transfer mode | Zero-copy, double-buffered | — |
| Peak throughput | 12.4 | TOPS |
| Target co-processor | ARM Cortex-M85 Helium MVE | — |
| Dequantisation latency | < 0.1 | ms |

### 1.3 Arena Memory Specification

| Zone | Size | Alignment | Contents |
|---|---|---|---|
| Weight Zone | 4 GB | 4 KB pages | INT4 AWQ base + BF16 LoRA Δ |
| KV-Cache Zone | 2 GB | 64 B cache lines | Per-layer KV pairs |
| Scratch Zone | 2 GB | 64 B cache lines | MCTS nodes, solver workspace, temps |
| **Total Arena** | **8 GB** | — | — |

**Invariant**: Zero heap allocations during inference. All memory is
bump-allocated from the arena and reset per request.

---

## 2. RunuX Kernel Modules

### 2.1 Module Summary (305 crates)

| Module | Crate Prefix | Crate Count | Description |
|---|---|---|---|
| Scheduler | `runux-sched-*` | 12 | Real-time priority scheduler with inheritance |
| Memory Manager | `runux-mm-*` | 8 | Arena allocator, page tables, DMA |
| HAL | `runux-hal-*` | 45 | ARM Cortex-M/A, RISC-V, x86-64 |
| AI Runtime | `runux-ai-*` | 18 | GEMM kernels, quantisation, activations |
| Networking | `runux-net-*` | 15 | TLS 1.3, gRPC-lite, mDNS discovery |
| Filesystem | `runux-fs-*` | 7 | Append-only log FS, checkpoint/restore |
| Crypto | `runux-crypto-*` | 9 | AES-256-GCM, ChaCha20-Poly1305, Ed25519 |
| Drivers | `runux-drv-*` | 62 | SPI, I2C, UART, USB, PCIe, NVMe |
| Power | `runux-pwr-*` | 6 | DVFS, sleep states, energy metering |
| Testing | `runux-test-*` | 4 | Property-based, fuzzing harness |
| Build System | `runux-build-*` | 3 | Cross-compilation, link scripts |
| Tracing | `runux-trace-*` | 5 | Lock-free ring buffer, OpenTelemetry export |
| IPC | `runux-ipc-*` | 8 | Lock-free channels, shared memory, signals |
| Boot | `runux-boot-*` | 4 | Bootloader, device tree parser |
| Watchdog | `runux-wdt-*` | 2 | Hardware & software watchdog timers |
| Math | `runux-math-*` | 11 | Fixed-point, CORDIC, fast transcendentals |
| DSP | `runux-dsp-*` | 14 | FFT, FIR/IIR filters, spectral analysis |
| Sensor Fusion | `runux-fusion-*` | 8 | Kalman, complementary, Madgwick filters |
| Protocol | `runux-proto-*` | 22 | Modbus, CANbus, MQTT, CoAP, LwM2M |
| Safety | `runux-safe-*` | 6 | ASIL-B runtime checks, stack guards |
| Misc | `runux-misc-*` | 36 | Utilities, data structures, allocators |
| **Total** | — | **305** | — |

### 2.2 Key Specifications

| Specification | Value |
|---|---|
| Minimum target | ARM Cortex-M4F (256 KB SRAM) |
| Maximum target | ARM Cortex-A78AE (server-class) |
| RTOS tick rate | 1 kHz |
| Context switch latency | < 5 μs (Cortex-M85) |
| Interrupt latency | < 1 μs (Cortex-M85) |
| Boot time to inference-ready | < 200 ms |
| Safety standard | ASIL-B compatible |
| Rust edition | 2024 |
| MSRV | 1.85.0 |

---

## 3. rusty-SUNDIALS Crates

### 3.1 Crate Inventory

| Crate | Upstream Solver | Problem Class | Tests | Lean 4 Specs |
|---|---|---|---|---|
| `rsun-cvode` | CVODE 7.1 | Stiff & non-stiff IVP ODEs | 32 | 5 |
| `rsun-ida` | IDA 7.1 | DAE systems (index ≤ 1) | 28 | 4 |
| `rsun-kinsol` | KINSOL 7.1 | Nonlinear algebraic systems | 22 | 3 |
| `rsun-arkode` | ARKODE 6.1 | Adaptive Runge-Kutta | 24 | 4 |
| `rsun-nvector` | N_Vector | Parallel vector ops | 16 | 2 |
| `rsun-sunlinsol` | SUNLinSol | Sparse direct & iterative | 12 | 2 |
| **Total** | — | — | **134** | **20** |

### 3.2 API Surface

```rust
// Core solver trait — all 4 solvers implement this
pub trait Solver {
    type State;
    type Error;

    fn init(config: SolverConfig) -> Result<Self, Self::Error>;
    fn step(&mut self, t: f64, dt: f64) -> Result<Self::State, Self::Error>;
    fn solve(&mut self, t_span: (f64, f64), y0: &[f64]) -> Result<Solution, Self::Error>;
    fn set_tolerance(&mut self, rtol: f64, atol: f64);
    fn set_max_steps(&mut self, max_steps: usize);
    fn stats(&self) -> SolverStats;
}
```

### 3.3 Convergence Specifications

| Solver | Order | Convergence Rate | Stability Region |
|---|---|---|---|
| CVODE (BDF) | 1–5 (adaptive) | O(h^p), p = order | A-stable (orders 1-2), A(α)-stable (3-5) |
| CVODE (Adams) | 1–12 (adaptive) | O(h^p) | Conditionally stable |
| IDA (BDF) | 1–5 (adaptive) | O(h^p) | A-stable (orders 1-2) |
| ARKODE (ERK) | 1–8 | O(h^p) | Method-dependent |
| ARKODE (DIRK) | 2–5 | O(h^p) | L-stable |
| KINSOL | — | Superlinear (Newton) | N/A |

### 3.4 Safety Guarantees

All crates enforce the following Rust safety properties:

- **No `unsafe` in public API**: All unsafe FFI calls are encapsulated
- **No panics in solver core**: All error paths return `Result<T, SolverError>`
- **No data races**: All shared state behind `Arc<Mutex<_>>` or `AtomicU64`
- **Bounded memory**: Pre-allocated workspace, no heap growth during solve

---

## 4. Agent Specifications

### 4.1 Agent Role Matrix

| Agent | Role | SDK | Primary Tools | Budget Share |
|---|---|---|---|---|
| **Socrates** | Orchestrator | AGY SDK | Dialectical protocol, budget guard | 10% (orchestration only) |
| **Galileo** | Experimenter | AGY SDK | rusty-SUNDIALS, NVIDIA NIM, datasets | 40% (compute-heavy) |
| **Euler** | Verifier | AGY SDK | Lean 4, DeepProbLog, statistical tests | 20% (proof search) |
| **Galois** | Creative Mathematician | AGY SDK | MCTS conjecture, creative hemisphere | 15% (conjecture generation) |
| **Turing** | Computational Optimizer | AGY SDK | Cost optimization, quota billing, austerity | 5% (infrastructure) |
| **Hypatie** | Astronomical Librarian | AGY SDK | Alexandrie vault, astrolabe conics, artifact catalog | 5% (knowledge curation) |
| **Heraclite** | Dialectical Philosopher | AGY SDK | Monograph generation, LaTeX/MathJax, peer review | 5% (synthesis & publication) |

### 4.2 Galileo — Scientific Experimenter

| Specification | Value |
|---|---|
| Max hypotheses per cycle | 8 |
| MCTS rollouts per hypothesis | 64 |
| Solver calls per experiment | ≤ 100 |
| NIM API calls per experiment | ≤ 10 |
| Max wall time per experiment | 300 s |
| Confidence threshold for promotion | ≥ 0.85 |

### 4.3 Euler — Mathematical Verifier

| Specification | Value |
|---|---|
| Lean 4 proof search depth | ≤ 50 tactics |
| Lean 4 timeout per theorem | 60 s |
| DeepProbLog inference timeout | 30 s |
| Minimum proof confidence | ≥ 0.95 |
| Statistical test significance | α = 0.05 (two-tailed) |

### 4.4 Socrates — Dialectical Orchestrator

| Specification | Value |
|---|---|
| Max Elenchus cycles per query | 5 |
| Max agents per cycle | 7 (all agents) |
| Budget enforcement | Hard limit, non-bypassable |
| Aporia declaration threshold | 3 failed cycles |
| Message timeout | 120 s |

### 4.5 Galois — Creative Mathematician

| Specification | Value |
|---|---|
| SymBrain cortex version | v4 (Cortical) |
| Creative hemisphere activation (σ_gen) | 0.75 |
| MCTS rollouts per conjecture | 128 |
| Max conjectures per cycle | 12 |
| Conjecture novelty threshold | ≥ 0.60 |
| Peer review integration | Heraclite cross-validation |

### 4.6 Turing — Computational Optimizer

| Specification | Value |
|---|---|
| Cost model | Per-token billing + solver compute |
| Quota enforcement | Hard limits per agent per cycle |
| Austerity mode trigger | Budget remaining < 20% |
| Memory bound monitoring | Arena scratch capacity > 85% alert |
| Network latency bound | Remote API < 30 s timeout |

### 4.7 Hypatie — Astronomical Librarian

| Specification | Value |
|---|---|
| Alexandrie vault access | Full read/write |
| Astrolabe conics module | Conic section classification |
| Artifact catalog | Scientific paper ingestion & indexing |
| Knowledge retrieval latency | < 500 ms |
| Ingestion failure fallback | Automatic retry with exponential backoff |

### 4.8 Heraclite — Dialectical Philosopher

| Specification | Value |
|---|---|
| Monograph generation | LaTeX + MathJax rendering pipeline |
| Output formats | PDF, HTML, EPUB, Kindle-compatible |
| Peer review coordination | Multi-agent dialectic review cycles |
| Max peer reviewers per monograph | 10 agents |
| Review convergence criterion | 3 consecutive approvals |

### 4.9 Hilbert — Axiomatic Program Builder (v2.1)

| Specification | Value |
|---|---|
| Model | `gemini-2.5-pro-deep-think` |
| Role | `AgentRole.MATHEMATICIAN` |
| Budget | $100/experiment, $500 project |
| Temperature | 0.1 (precision-focused) |
| Timeout | 120,000 ms |
| Max Iterations | 15 |
| Cloud Run | INTERNAL_ONLY, 4 CPU / 8Gi |

**A2A Skills:**

| Skill | Description |
|---|---|
| `axiomatize_field` | Distill empirical evidence into a Lean 4 axiom system |
| `identify_open_problems` | Rank and blueprint open problems in a mathematical field |
| `propose_research_program` | Design a Hilbert-style research programme with milestones |
| `scan_sorrys` | Scan Lean 4 codebase for sorry/axiom targets with difficulty classification |
| `complete_sorrys` | 10-hypothesis autoresearch engine with LeanBERT + DeepSeek + Gemini |

**Sorry Completion Pipeline:**

| Stage | Backend | Hypotheses | Cost |
|---|---|---|---|
| LeanBERT GAN | CPU-only Cloud Run | 3 per sorry | ~$0.001 |
| DeepSeek-Prover-V2-7B | T4 GPU (4-bit AWQ) | 4 per sorry | ~$0.005 |
| Gemini Deep-Think | API | 3 per sorry | ~$0.015 |
| DeepSeek-Prover-V2-671B | API (extreme only) | escalation | ~$0.05 |

**Verification:** `lake env lean` single-file kernel compilation (120s timeout)  
**Ranking:** LeanBERT GAN critic score + proof compactness + source reliability  
**Ratchet:** Up to 3 iterations with error feedback reflection

### 4.10 Einstein — Relativistic Reasoner

| Specification | Value |
|---|---|
| Model | `gemini-2.5-pro-deep-think` |
| Role | `AgentRole.PHYSICIST` |
| Budget | $100/experiment |
| Timeout | 120,000 ms |
| Cloud Run | INTERNAL_ONLY, 4 CPU / 8Gi |

---

## 5. Lean 4 Theorem Index

All formal specifications reside in `verifiers/lean4/Agora/`. For a
comprehensive catalog, see [SPEC_LEAN4.md](SPEC_LEAN4.md).

### 5.1 Basic Definitions (`Basic.lean`)

| ID | Theorem | Status |
|---|---|---|
| BAS-001 | `budgetPerExperiment_pos` — Per-experiment budget is positive | ✅ Proven |
| BAS-002 | `budgetTotal_ge_per` — Total budget ≥ per-experiment budget | ✅ Proven |
| BAS-003 | `deductiveFloor_pos` — Deductive floor is positive | ✅ Proven |
| BAS-004 | `deductiveFloor_le_one` — Deductive floor ≤ 1 | ✅ Proven |
| BAS-005 | `frobeniusSq_nonneg` — Frobenius norm² is non-negative | ✅ Proven |

### 5.2 Arena Memory Safety (`Memory.lean`)

| ID | Theorem | Status |
|---|---|---|
| MEM-001 | `arena_boundary_safety` — Total allocation ≤ arena capacity | ✅ Proven |
| MEM-002 | `allocate_zone_valid` — Single-zone allocation preserves invariant | ✅ Proven |
| MEM-003 | `contiguous_implies_disjoint` — Contiguous layout ⟹ disjoint zones | ✅ Proven |
| MEM-004 | `deallocate_zone_valid` — Deallocation preserves invariant | ✅ Proven |
| MEM-005 | `allocation_preserves_invariant` — Full allocation preserves arena | ❌ Sorry |
| MEM-006 | `replaceZone.zones_fit` — Zone replacement preserves capacity sum | ❌ Sorry |
| MEM-007 | `replaceZone.zones_valid` — Zone replacement preserves validity | ❌ Sorry |

### 5.3 Physical Conservation Laws (`Conservation.lean`)

| ID | Theorem | Status |
|---|---|---|
| CON-001 | `energy_conservation` — dE/dt = −(boundary flux) | ✅ Proven |
| CON-002 | `robin_degenerate_not_wellformed` — Robin BC with α=β=0 is degenerate | ✅ Proven |
| CON-003 | `dirichlet_bounded_wellformed` — Bounded Dirichlet BC is well-formed | ✅ Proven |
| CON-004 | `mass_conservation` — M(t₁) = M(t₂) for closed systems | ❌ Sorry |
| CON-005 | `energy_conservation_isolated` — E constant in isolated system | ❌ Sorry |
| CON-006 | `charge_conservation` — dQ/dt = 0 for source-free closed system | ❌ Sorry |

### 5.4 PFC Router (`PFC.lean`)

| ID | Theorem | Status |
|---|---|---|
| PFC-001 | `deductive_floor_elimination` — σ_ded ≥ floor ⟹ deductive selected | ✅ Proven |
| PFC-002 | `gate_norm_nonneg` — Gate output norm ≥ 0 | ✅ Proven |
| PFC-003 | `gate_at_stationary` — Gate bounded by C_stab at stationary points | ✅ Proven |

### 5.5 Dynamic Gating (`Gating.lean`)

| ID | Theorem | Status |
|---|---|---|
| GAT-001 | `sigmoid_pos` — σ(x) > 0 for all x | ✅ Proven |
| GAT-002 | `sigmoid_nonneg` — σ(x) ≥ 0 for all x | ✅ Proven |
| GAT-003 | `sigmoid_le_one` — σ(x) ≤ 1 for all x | ✅ Proven |
| GAT-004 | `sigmoid_in_unit` — σ(x) ∈ (0, 1] | ✅ Proven |
| GAT-005 | `gating_monotone` — Gating is monotone w.r.t. complexity | ✅ Proven |
| GAT-006 | `gating_bounded` — Gate output ∈ [0, 1] | ✅ Proven |
| GAT-007 | `sigmoid_monotone` — Sigmoid is monotone | ❌ Sorry |
| GAT-008 | `sigmoidGate_monotone` — Shifted sigmoid is monotone (k > 0) | ❌ Sorry |
| GAT-009 | `sigmoid_logit_inverse` — σ(logit(p)) = p for p ∈ (0, 1) | ❌ Sorry |

### 5.6 LoRA Norm Bounds (`LoRA.lean`)

| ID | Theorem | Status |
|---|---|---|
| LOR-001 | `lora_scale_well_defined` — α/r is well-defined (r ≠ 0) | ✅ Proven |
| LOR-002 | `lora_scale_pos` — α/r > 0 when α > 0 | ✅ Proven |
| LOR-003 | `lora_norm_bound` — ‖ΔW‖ ≤ \|α/r\| · ‖B‖ · ‖A‖ | ❌ Sorry |
| LOR-004 | `lora_gradient_bound_A` — ‖∂L/∂A‖ bound | ❌ Sorry |
| LOR-005 | `lora_gradient_bound_B` — ‖∂L/∂B‖ bound | ❌ Sorry |
| LOR-006 | `lora_param_efficiency` — r(m+n) < mn (low-rank efficiency) | ❌ Sorry |

### 5.7 RLCF Convergence (`RLCF.lean`)

| ID | Theorem | Status |
|---|---|---|
| RCF-001 | `levy_alpha_range` — α_min < α_max | ✅ Proven |
| RCF-002 | `levy_alpha_min_gt_one` — α_min > 1 | ✅ Proven |
| RCF-003 | `levy_alpha_max_lt_two` — α_max < 2 | ✅ Proven |
| RCF-004 | `valid_levy_in_range` — Valid α ∈ (1, 2) | ✅ Proven |
| RCF-005 | `lyapunovV_nonneg` — Lyapunov V ≥ 0 | ✅ Proven |
| RCF-006 | `rlcf_monotone_descent` — f(W_{t+1}) ≤ f(W_t) − (η/2)‖∇f‖² | ❌ Sorry |
| RCF-007 | `rlcf_lyapunov_decrease` — Lyapunov decreases under small noise | ❌ Sorry |

### 5.8 Millennium Prize Blueprints (`cmi_millennium_blueprints.lean`)

| ID | Theorem | Status |
|---|---|---|
| CMI-001 | `riemann_hypothesis` — All non-trivial ζ zeros on Re(s)=½ | ❌ Sorry |
| CMI-002 | `p_neq_np` — P ≠ NP | ❌ Sorry |
| CMI-003 | `navier_stokes_globally_smooth` — Global smooth solutions exist | ❌ Sorry |
| CMI-004 | `bsd_rank_equality` — Algebraic rank = analytic rank | ❌ Sorry |
| CMI-005 | `hodge_conjecture_cycles` — Hodge (p,p) cycles are algebraic | ❌ Sorry |
| CMI-006 | `yang_mills_mass_gap_positive` — Mass gap Δ > 0 | ❌ Sorry |
| CMI-007 | `poincare_conjecture_homeomorphism` — Simply connected 3-manifold ≅ S³ | ❌ Sorry |

> **Note**: The Millennium Prize blueprints are *research-level open problems*.
> They represent the aspirational scope of the Agora framework, not solved
> results. See [ROADMAP.md](../ROADMAP.md) for an honest assessment.

### 5.9 Verification Statistics

| Metric | Value |
|---|---|
| Total theorems | 50 |
| Proven (✅) | 28 |
| In progress | 0 |
| Sorry / pending (❌) | 22 |
| Total LoC (Lean 4) | ~1,300 |
| Proof coverage | 56% |
| Lean 4 files | 9 (incl. `E37BSD_v6_blueprint.lean`) |

---

## 6. DeepProbLog Program Index

All programs reside in `verifiers/deepproblog/programs/`.

| Program | Purpose | Neural Predicates | Rules |
|---|---|---|---|
| `hypothesis_ranking.pl` | Rank hypotheses by evidence support | 2 (embed, score) | 12 |
| `causal_inference.pl` | Identify causal relations in data | 3 (cause, effect, confound) | 18 |
| `consistency_check.pl` | Verify logical consistency of claims | 1 (entailment) | 8 |
| `uncertainty_calibration.pl` | Calibrate prediction uncertainties | 2 (predict, calibrate) | 10 |
| `domain_transfer.pl` | Transfer domain knowledge across tasks | 2 (source, target) | 15 |

---

## 7. NVIDIA NIM Service Contracts

| Service | Container | GPU | Max Latency | Cost/Call | Endpoint |
|---|---|---|---|---|---|
| BioNeMo | `nvcr.io/nim/bionemo:1.2` | L4 24GB | 10 s | $0.05 | `/v1/biology/structure` |
| Earth-2 | `nvcr.io/nim/earth2:0.9` | L4 24GB | 15 s | $0.08 | `/v1/climate/forecast` |
| Modulus | `nvcr.io/nim/modulus:0.7` | T4 16GB | 8 s | $0.03 | `/v1/physics/simulate` |

All services deployed with `min_replicas=0` on GCP Cloud Run.

---

## 8. Benchmark Methodology

See [BENCHMARKS.md](BENCHMARKS.md) for full results. Summary of methodology:

| Aspect | Specification |
|---|---|
| Evaluation framework | lm-evaluation-harness v0.4+ |
| Statistical tests | Wilson 95% CI, McNemar's χ² test |
| Data decontamination | 13-gram overlap filter on training corpus |
| Reproducibility | Fixed seeds (42, 123, 456), 3 runs per config |
| Energy measurement | NVIDIA DCGM + Keysight N6705C power analyser |
| Reporting | All raw data published in `benchmarks/results/` |

---

## 9. Wire Protocols

### 9.1 Agent-to-Agent (gRPC)

```protobuf
syntax = "proto3";
package agora.v1;

service AgoraAgent {
  rpc SendMessage(AgoraMessage) returns (AgoraAck);
  rpc StreamDialogue(stream AgoraMessage) returns (stream AgoraMessage);
}

message AgoraMessage {
  string msg_id = 1;           // UUID v7
  AgentRole sender = 2;
  AgentRole receiver = 3;
  MessageType msg_type = 4;
  bytes payload = 5;           // JSON-encoded type-specific payload
  string budget_remaining = 6; // Decimal string, e.g. "98.50"
  int64 timestamp_ns = 7;      // Unix nanoseconds
  string parent_id = 8;
  string cycle_id = 9;
}

enum AgentRole {
  SOCRATES = 0;
  GALILEO = 1;
  EULER = 2;
  GALOIS = 3;
  TURING = 4;
  HYPATIE = 5;
  HERACLITE = 6;
}

enum MessageType {
  ELENCHUS = 0;
  MAIEUTIC = 1;
  SYNTHESIS = 2;
  APORIA = 3;
  BUDGET_ALERT = 4;
  CONJECTURE = 5;
  PEER_REVIEW = 6;
}
```

### 9.2 Agent-to-Solver (Native FFI)

rusty-SUNDIALS exposes a C-ABI-compatible interface wrapped in safe Rust:

```rust
#[repr(C)]
pub struct SolverConfig {
    pub rtol: f64,
    pub atol: f64,
    pub max_steps: u64,
    pub method: SolverMethod,
    pub arena_ptr: *mut u8,
    pub arena_len: usize,
}
```

---

## 10. Configuration Schema

All agent and system configuration uses TOML format:

```toml
# agora.toml — Master configuration
[agora]
version = "2.0.0"
budget_usd = 100.0
max_cycles = 5

[symbrain]
version = "v5"
pfc_model = "mistral-7b-complexity-clf"
rlcf_lr = 3e-4
rlcf_alpha = 1.7
rlcf_lambda = 0.01
mcts_max_depth = 8
mcts_rollouts = 64
early_stop_ms = 500

[arena]
total_bytes = 8_589_934_592  # 8 GB
weight_zone_bytes = 4_294_967_296
kv_cache_bytes = 2_147_483_648
scratch_bytes = 2_147_483_648

[models.edge-7b]
name = "mistral-7b-v0.4"
quantisation = "INT4-AWQ"
vram_gb = 8
tier = 1

[models.cloud-32b]
name = "mixtral-8x4b"
quantisation = "INT8-GPTQ"
vram_gb = 40
tier = 2

[models.cloud-70b]
name = "llama-3.1-70b"
quantisation = "BF16"
vram_gb = 160
tier = 3

[models.cloud-122b]
name = "mistral-large-2"
quantisation = "FP8-E4M3"
vram_gb = 320
tier = 4

[galileo]
max_hypotheses = 8
max_solver_calls = 100
max_nim_calls = 10
max_wall_time_s = 300

[euler]
lean4_timeout_s = 60
deepproblog_timeout_s = 30
min_proof_confidence = 0.95

[socrates]
max_elenchus_cycles = 5
aporia_threshold = 3
message_timeout_s = 120

[galois]
symbrain_cortex = "v4"
sigma_gen = 0.75
mcts_rollouts = 128
max_conjectures = 12

[turing]
austerity_threshold = 0.20
scratch_alert_threshold = 0.85

[hypatie]
vault_access = "full"
retrieval_timeout_ms = 500

[heraclite]
output_formats = ["pdf", "html", "epub", "kindle"]
max_reviewers = 10
review_convergence = 3
```

---

## Cross-References

- [ARCHITECTURE.md](ARCHITECTURE.md) — System topology and component diagrams
- [VISION.md](VISION.md) — Scientific vision and intellectual foundations
- [EXECUTION_PLAN.md](EXECUTION_PLAN.md) — 4-phase development roadmap
- [BUDGET_POLICY.md](BUDGET_POLICY.md) — GCP cost governance
- [BENCHMARKS.md](BENCHMARKS.md) — Benchmark results and analysis
- [SPEC_LEAN4.md](SPEC_LEAN4.md) — Comprehensive Lean 4 verification catalog
- [api/agents.md](api/agents.md) — Agent API reference
- [api/solvers.md](api/solvers.md) — Solver API reference
- [api/verifiers.md](api/verifiers.md) — Verifier API reference
- [../TESTS.md](../TESTS.md) — Test suite guide
- [../ROADMAP.md](../ROADMAP.md) — Project roadmap and honest assessment
- [../TODO.md](../TODO.md) — Actionable task list

---

## 11. Agora Pipelines

### 11.1 Pipeline Framework
The `agents/pipelines/` package provides a reusable, templated pipeline framework for orchestrating multi-agent scientific workflows.

**Core classes:**
- `AgentPipeline(ABC)` — Abstract pipeline with `run()` and `get_stages()`
- `SymposiumConfig` — Frozen dataclass configuring all pipeline parameters
- `SymposiumAuditTrail` — Append-only JSONL audit log with SHA-256 integrity
- `PipelineStage` — 10-stage enum (SOCRATE_RULES through PUBLICATION)

### 11.2 Agora Symposium — 10 Stages
| Stage | Agent(s) | Input | Output |
|-------|----------|-------|--------|
| 1. Scientific Rules | Socrate | Config | 5-10 formal constraints |
| 2. Hypothesis Generation | DeGennes Swarm (5×5) | Rules | 25 hypotheses (JSON) |
| 3. Adversarial Review | Gemini Deep Think | Hypotheses | Top-K scored hypotheses |
| 4. Lean 4 Formalization | Euler | Top-K | Lean 4 theorems |
| 5. Kernel Compilation | Pythagore + lake | Theorems | Kernel verdicts |
| 6. Numerical Simulation | Galileo | Top-K | Figures + stats |
| 7. Impact Assessment | DeGennes (business) | Top-K | ROI/impact reports |
| 8. Monograph Generation | Hypatia (D&C) | All above | LaTeX (50-150 pages) |
| 9. Peer Review Loop | Multi-LLM × 5 | LaTeX + Lean/Galileo | Revised LaTeX |
| 10. Publication | pdflatex + Alexandrie | Final LaTeX | PDF + vault entries |

### 11.3 Budget Governance
$30 USD per pipeline run. Enforced by cumulative cost tracking across all agent_generate() calls.

### 11.4 Audit Trail Schema
```json
{"stage": "LEAN4_FORMALIZATION", "timestamp": "2026-06-12T08:00:00Z", "agent": "Euler", "input_sha256": "abc...", "output_sha256": "def...", "socrate_verdict": "PASS", "lean_sorry_count": 1, "lean_axiom_count": 0, "duration_s": 45.2, "cost_usd": 0.15}
```

### 11.5 Pre-built Templates
- `quantum_computing` — Quantum tensor network optimization
- `airline_revenue_mgmt` — Dynamic pricing with non-commutative demand algebra
- `airport_operations` — ICAO-compliant operations via holographic entropy
- `cycloreactor_environment` — Symbiotic planetary cycles (CycloReactor)
- `plasma_fusion_iter` — Tokamak plasma confinement (ITER)

---

*Copyright © 2026 Xavier Callens / Socrate AI Lab, Paris, France.*
*Licensed under Apache 2.0 (framework) and CC-BY-NC-ND 4.0 (proprietary content).*
*Patent Pending: US-PAT-PEND-2026-0525*
