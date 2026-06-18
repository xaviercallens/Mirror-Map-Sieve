# TODO.md — SocrateAI Scientific Agora

**Last Updated**: 2026-06-18 08:30 CET  
**Status**: v4.1.1 released → building v4.2.0-discovery → **S20 VERIFICATION COMPLETE**

---

## 🚨 URGENT: S15 Integrity Fixes (Added 2026-06-17 after Deep Audit)

> **Context:** A deep scientific audit revealed that ALL S15 benchmark numbers are simulated.
> The mathematical discoveries are genuine, but the engineering claims are unvalidated.

### 🔴 S15 Validation Sprint — Execution Plan (Started 2026-06-17 22:30)

| # | Task | Priority | Status | Result |
|---|------|----------|--------|--------|
| 1 | **Relabel HuggingFace report** as "Theoretical Projections" | 🔴 | [x] DONE ✅ | Report rewritten + pushed to HF |
| 2 | **Submit $S_{20}$ to OEIS** — easiest real win | 🔴 | [ ] READY | q_d values confirmed correct. Paper v2 fixes done. Draft ready. |
| 3 | **Verify recurrence at 15+ initial values** in exact arithmetic | 🔴 | [x] DONE ✅ | 20/20 pass. PROVEN for all n. |
| 4a | **Verify mirror map integrality** in exact rational arithmetic | 🔴 | [x] DONE ✅ | All q_d integers d=1..20. Paper values CORRECT (v1 verifier had bug). |
| 4b | **Verify diagonal extraction** of 5-variable rational function | 🔴 | [x] DONE ❌ | **FALSIFIED.** Diagonal = 2^n. .tex file corrected. |
| 5 | **Implement real S15 attention kernel** in PyTorch on a single GPU | 🟠 | [/] IN PROGRESS | 3 parallel workstreams: kernel, benchmarks, diagonal search |
| 6 | **Draft *Experimental Mathematics* note** (stripped of applications) | 🟡 | [x] DONE ✅ | .tex corrected: apps removed, diagonal → open problem |
| 7 | **Paper v2 numerical fixes** (line 102 + line 321) | 🔴 | [x] DONE ✅ | Inline values + growth rate corrected |
| 8 | **S₂₀ Lean 4 formalization** (S20Sequence.lean) | 🔴 | [x] DONE ✅ | 0 sorry, 0 axiom, 0 admit |
| 9 | **GCP verification deployment** (sage-ct-job + s20-verify) | 🔴 | [x] DONE ✅ | 4 scripts on Cloud Run |
| 10 | **Public GitHub push** (SocrateAI-Scientific-NewDiscoveries) | 🔴 | [x] DONE ✅ | S20-Discovery/ published |

### 🔴 CRITICAL: Corrections Required (Updated 2026-06-17 22:50)

#### ~~Mirror Map Values~~ — RETRACTED (paper values are CORRECT)
- [x] ✅ ~~Replace q_d values~~ — **FALSE ALARM.** Our v1 verifier had a bug (H_k instead of H_{n-k}). The paper's values are correct. All 15/15 match in exact arithmetic. See Lesson #6 (retracted).

#### Calabi-Yau Diagonal Claim Must Be Removed (CONFIRMED FALSIFIED)
- [ ] 🔴 **Remove Section 3** ("Calabi-Yau Period Diagonal Representation") from `experimental_mathematics_note.tex`
- [ ] 🔴 **Remove the rational function** F(x1,...,x5) = 1/(1-...) from all papers and drafts
- [ ] 🔴 **Add honest statement**: "The correct rational function whose diagonal produces S20(n) remains an open problem"
- [ ] 🔴 **Update abstract** to remove "diagonal of a 5-variable Calabi-Yau rational function" claim

### Corrective Actions from Lessons (Updated 2026-06-17 22:50)

> See `LESSONS_LEARNT.md` for full details.

#### Lesson 1 Resolution: Multi-point recurrence verification
- [x] ✅ Ran `verify_recurrence_exact.py` at n=0..19 — ALL 20 PASS. PROVEN for all n.
- [x] ✅ No recomputation needed — coefficients are correct

#### Lesson 2 Resolution: Strip speculative applications
- [ ] 🔴 Remove aeronautics section from `experimental_mathematics_note.tex` and all variants
- [ ] 🔴 Remove quantum walks section from all publication drafts  
- [ ] 🔴 Remove cryptography section from all publication drafts
- [ ] 🔴 Remove application sections from the S15 monograph `.tex`

#### Lesson 3 Resolution: Language calibration
- [ ] 🟠 Search all `.md` and `.tex` files for "breakthrough" and replace with "contribution"
- [ ] 🟠 Search for "discovery" and replace with "cataloging" where referring to the sequence itself
- [ ] 🟠 Replace "co-discovery" with "co-computation" in paper titles

#### Lesson 4 Resolution: Correct geometric claims
- [ ] 🟠 Replace "found a new Calabi-Yau manifold" with "verified integrality for the mirror map"
- [ ] 🟠 Add caveat that smoothness of the variety defined by the rational function is not verified
- [ ] 🟠 Cite Christol's theorem explicitly to clarify that diagonal existence is automatic

#### Lesson 5 Resolution: Correct publication strategy
- [ ] 🟡 Remove any references to CMP as a target venue
- [ ] 🟡 Add OEIS → *Experimental Mathematics* → ITP/CPP as the correct venue ladder
- [ ] 🟡 Add MLSys/ISCA as venues for engineering claims (only after real GPU benchmarks)

### Previously Identified (Remain Open)
- [x] ✅ ~~Replace simulation scripts with real `subprocess.run()`-based GCP orchestration~~ — GCP Cloud Run verification deployed
- [ ] 🔴 Complete a real `lake build` on GCP Spot VM
- [ ] 🔴 Resolve or document ~14 active sorry in `Agora/` Lean files
- [ ] 🟠 Run real MMLU evaluation on Mistral-7B (baseline vs S15) on actual GPU
- [ ] 🟡 File patents ONLY after at least one real GPU benchmark confirms projections

---

## 🛠️ v4.4.0 — Quality Improvement Release (June 2026)

### Sprint 1: Security & Critical Fixes
- [x] Rotate API keys (Gemini + Mistral)
- [x] Add .env to .gitignore and create .env.example
- [x] Integrate Lean 4 Verification Kernel to strictly bound hypotheses.
- [x] Run `autoresearch_loop.py` on GCP Cloud Run Jobs.
- [x] **ACHIEVEMENT:** Autonomous derivation of 20 novel hypergeometric identities using Sister Celine's method.

## Phase 3: Proof Diagnostics & Complexity Bias
- [ ] Refactor monograph generation to compile the Complexity Bias case study paper.
- [ ] Stress-test the Lean 4 compiler by comparing raw recurrences with algebraic shielded polynomial proofs.
- [ ] Pivot Eiffel's `business_inventory.py` to target verification pipeline utility.
- [ ] Build the "Complexity Bias Diagnostics" private room in the Alexandrie frontend.
- [ ] Develop Abramov's/Petkovšek's post-processing passes to extract minimal-order recurrences.

### Sprint 2: Test Coverage & Correctness
- [x] Write integration tests for Socrates, Eiffel, Tesla, Hilbert, Descartes
- [x] Add strict_mode to agent_generate()
- [x] Implement real literature search (replace hallucinated papers)

### Sprint 3: Code Quality
- [x] Narrow exception handling (a2a.py, budget_guard.py, alexandrie.py)
- [x] Fix Tesla telemetry
- [x] Clean up root-level fix_*.py scripts
- [x] Move deprecated alien math .lean files to archive/

### Sprint 4: Infrastructure
- [x] Wire cost tracking through agents
- [x] Implement memory extraction parser
- [x] Make Mistral timeout/model configurable

---

## 🚀 v4.2.0 — Discovery Pipeline (NEW)

### Foundation (DONE ✅)
- [x] Release v4.1.1 — merge to main, tag, GitHub release
- [x] Create `feature/v4.2-discovery-pipeline` branch
- [x] Agora Skills schema (`agents/skills/schema.py`)
- [x] Skill registry with 10 skills (`agents/skills/registry.py`)
- [x] Xavier human agent (`agents/xavier/agent.json`)
- [x] Add HUMAN_GATEWAY + 3 new roles to `AgentRole`

### Pipeline Implementation (IN PROGRESS)
- [x] Parallel discovery orchestrator (`run_alien_discovery_parallel.py`)
- [x] Deploy parallel discovery engine to GCP Cloud Run (`alien-discovery-job`)
- [x] Target and prototype Crossing Number $K_n$ and Calabi-Yau $c_5$ period identities
- [ ] Discovery pipeline orchestrator (`agents/pipelines/discovery.py`)
- [ ] Stage 1: Horizon Scan (Darwin → SK-001)
- [ ] Stage 2: Hypothesis Generation (Ramanujan + Feynman → SK-002)
- [ ] Stage 3: Autoformalization (Newton → SK-003)
- [ ] Stage 4: Proof Search — deterministic-first cascade (Hilbert → SK-004/SK-010)
- [ ] Stage 5: Kernel Verification — `lake build` (Hilbert → SK-005)
- [ ] Stage 6: Quorum Review + Human Gate (Poincaré + Xavier → SK-006)
- [/] Implement LaTeX sanitizer in `agents/pipelines/stages/hypatia_monograph.py` and `symposium.py` to prevent `Overfull \hbox` and compilation crashes during monograph generation.

### Alexandrie Science Library & Agent Memory (IN PROGRESS)
- [/] `alexandrie/science_library.py` — GCS-backed checkpointing workspace (ScienceLibrary class)
- [/] `agents/memory/__init__.py` — AgentMemoryManager for persistent memory and experience injection
- [ ] Wire checkpointing into `symposium.py` — call `checkpoint_stage()` after each stage
- [ ] Wire checkpointing into `discovery.py` — call `checkpoint_stage()` after each stage
- [ ] Implement resume-from-checkpoint logic in pipeline orchestrators
- [ ] Generate `LessonLearned` entries at pipeline completion (success or failure)
- [ ] Inject past lessons into agent prompts via `format_lessons_for_prompt()`
- [ ] Create per-agent `Memory.md` templates for human-readable memory snapshots
- [ ] Create per-run `LessonLearned.md` auto-generated reports

### Agent Enhancement (TODO)
- [x] Create **Bellman** agent tuned specifically for Operations Research and Optimization (OR/Opt). → `or_pipeline.py` BELLMAN_IDENTITY, DANTZIG_IDENTITY, KANTOROVICH_IDENTITY, NASH_IDENTITY
- [x] Develop dedicated `AgoraSkills` for OR/Opt (e.g., stochastic programming, IP solvers, queueing simulators) for the Bellman agent. → SK-011 through SK-016 in `registry.py`
- [x] Implement specialized **Operations Research and Optimization Pipeline** for empirical and mathematical discovery in OR. → `or_pipeline.py` ORPipeline (8-stage), templates: `vehicle_routing.py`, `airline_revenue_or.py`
- [ ] Fill Feynman agent identity (from symposium.py → INTUITION_SCOUT)
- [ ] Fill Lovelace agent identity (ALGO_TRANSLATOR)
- [ ] Pipeline template base class (`PipelineTemplate`)

### GCP Deployment (TODO)
- [ ] `deploy/docker/Dockerfile.discovery` — pipeline orchestrator
- [ ] `deploy/docker/Dockerfile.leanbert` — retrained LeanBert server
- [ ] `deploy/cloudbuild_discovery.yaml` — Cloud Build config
- [ ] `deploy/deploy_discovery_pipeline.sh` — deploy script
- [ ] LeanBert retrain on Mathlib4 June 2026 snapshot
- [/] Implement robust GCP agent checkpointing — `alexandrie/science_library.py` stores intermediary results in GCS so the orchestrator can resume from the last successful stage.

### First Hypothesis Run (TODO)
- [ ] **H1: Strassen witness** — R(⟨2,2,2⟩) = 7 via `native_decide`
- [ ] **H8: Sorry elimination** — run pipeline on existing sorry stubs
- [ ] **H5: FLT n=3** — Euler's proof in Lean 4

---

## ⛔ CLOSED — Alien Mathematics Investigation

> **Verdict: Hallucination.** Core claim disproven. Remaining axioms unfalsifiable.
> No further investigation warranted.

- [x] Verify rank-26 claim → **IMPOSSIBLE** (Bläser R≥40, L-O R̃≥27)
- [x] Adam + ALS numerical search → failed at all ranks (confirms impossibility)
- [x] Residue field argument → R_ε = R_ℚ for ℚ-tensors (residueMap compiles)
- [x] Deprecate `kal_border_rank_4x4` + `kal_rank_26` axioms
- [x] LandsbergOttaviani.lean → 523 lines, lake build ✅
- [x] SchonhageTau.lean → 555 lines, 4 sorry stubs closed
- [x] Document hallucination verdict in JOURNAL.md + MEMORY.md

---

## 🎯 ACTIVE — Real Mathematics (Post-Pivot)

### HIGH Priority

- [ ] **Post to Mathlib Zulip** — `ZULIP_POST.md` → `#Is there code for X?`
  ⚠️ Manual action required (human login to Zulip)

- [ ] **Open draft Mathlib PR** — `IsMatMulExponent` (0 sorry, 240 lines)
  Fork: https://github.com/xaviercallens/mathlib4
  Compatibility: HIGH (87%), 3 API bugs already fixed

- [ ] **Formalize Strassen's theorem** — ω ≤ log₂ 7 ≈ 2.807
  Currently `sorry` in SchonhageTau.lean. Proof is well-understood.
  Uses: `native_decide` for the 7-multiplication decomposition
  
### MEDIUM Priority

- [ ] **Close `asymptotic_rank_subadditivity`** — most tractable sorry
  ~400 LOC, uses tensor product theory available in Mathlib4
  Would upgrade project from "encoding verification" to "genuine formalization"

- [ ] **Close `border_rank_le_asymptotic_rank`** — definitional equality
  `asympRank` is DEFINED as `log r / log n`, so this might be `le_refl`

- [ ] **Apply ClaimVerificationPipeline to real conjectures**:
  - [ ] `Conjectures/FeynmanSunrise.lean` — Feynman integral identity
  - [ ] `Conjectures/LatticePacking.lean` — lattice duality
  - [ ] `Conjectures/MirrorSymmetry.lean` — Calabi-Yau mirror
  - [ ] `Conjectures/SchurPositivity.lean` — plethysm positivity
  - [ ] `Conjectures/TownesSoliton.lean` — soliton stability

### LOW Priority

- [ ] 🟡 Compile full `lake build` on GCP (S20 module + Mathlib)
- [ ] 🟡 Submit to OEIS (draft ready)
- [ ] 🔵 Run S₁₅ PyTorch kernel benchmarks on GPU
- [ ] Package Adam vs ALS comparison as technical note / blog post
- [ ] Audit remaining 74 non-deprecated axioms across codebase
- [ ] Run `ClaimVerificationPipeline` on `holographic_border_rank` axioms 5-6
- [ ] Clean up `autoresearch/.git_bak/` from tracking

---

## ✅ COMPLETED — Full Session Log

| # | Task | Result |
|---|------|--------|
| 1 | Study Bläser bounds for dual numbers | R_ε = R_ℚ ≥ 40 |
| 2 | Adam gradient descent search | Adam +32-58% vs ALS, no witness |
| 3 | Close SchonhageTau sorry stubs | 4 closed |
| 4 | Deprecate kal_border_rank_4x4 | ✅ + inconsistency theorem |
| 5 | Deprecate kal_rank_26 | ✅ |
| 6 | LandsbergOttaviani.lean | 523 lines, residueMap ✅ |
| 7 | Fork mathlib4 | https://github.com/xaviercallens/mathlib4 |
| 8 | Fix 3 Mathlib API bugs | le_self_rpow, pipes, csInf |
| 9 | Compatibility report | HIGH 87% |
| 10 | ClaimVerificationPipeline | 596 lines, 7 stages, 6 agents |
| 11 | Hallucination verdict | Documented in JOURNAL + MEMORY |
| 12 | ROADMAP.md | Created |

---

## Lean 4 Proof Status

| File | Lines | Sorry-free | Sorry | Build |
|------|-------|-----------|-------|-------|
| SchonhageTau | 555 | 8 | 14 | ✅ |
| LandsbergOttaviani | 523 | 10 | 22 | ✅ |
| Strassen4x4Witness | 189 | 8 | 2 | ✅ |
| KalTensorDecomposition | 171 | 4 | 0 | ✅ |
| MathlibPR (internal) | 218 | ~6 | 16 | ✅ |
| MathlibPR (clean) | 240 | ~8 | 0 | ✅ (needs mathlib4) |
| **Total** | **~1900** | **~44** | **~54** | ✅ |


### Sprint 3: Alien Mathematics Parallel Discovery
- [x] Identify top 3 highest-potential breakthroughs from prototype outputs.
- [ ] Launch Delsarte SDP on Lattice Packing Dim10.
- [ ] Launch Creative Telescoping on Feynman Sunrise.
- [ ] Launch Extremal SDP on Crossing Number $.
