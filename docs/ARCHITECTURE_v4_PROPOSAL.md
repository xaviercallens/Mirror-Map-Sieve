# Agora Swarm v4.0 — Full AI-Human Hybrid Research Lab Evolution

> **Scope:** Promote 15 agents → 17 agents (+ Hilbert, Einstein), upgrade to Gemini 3.1 Pro / Deep Think, enforce GCP-native cost optimization, A2A agent cards + registry, Pub/Sub resilience, GCS-backed Alexandrie, and draft 6 future agents for genius discovery lifecycle.

---

## 1. Current State Assessment

> [!IMPORTANT]
> The GCP infrastructure is **already mature**. Terraform IaC has 8 modules, Cloud Run v2 enforces `min_replicas=0` at the Terraform level, OIDC security is active, and A2A Protocol v1.1 is implemented with agent cards, Firestore state, and GCS artifact passing. This plan builds on this strong foundation.

### What Exists Today

| Component | Status | Detail |
|---|---|---|
| Terraform IaC (8 modules) | ✅ Production | GCS backend, 8 modules, `gen-lang-client-0625573011` |
| Cloud Run v2 (`min_replicas=0`) | ✅ Enforced at Terraform + Code level | `AgentConfig.__post_init__()` raises ValueError if `min_replicas != 0` |
| A2A Protocol v1.1 (JSON-RPC + Agent Cards) | ✅ 8 agents | `agents/common/a2a.py` (449 lines), async Claim Check, 11 tests |
| Firestore-backed task state | ✅ `a2a_tasks` collection | `agents/common/a2a_state.py` with in-memory fallback |
| GCS artifact passing | ✅ `upload_artifact_to_gcs()` | In `agents/common/a2a.py` |
| OIDC authentication | ✅ Token injection | GCP metadata server, `OIDC_ENABLED=1` |
| Budget Guard / FinOps circuit breaker | ✅ Multi-layered | Code + Terraform + GCP budget alerts + kill switch |
| Docker images in Artifact Registry | ✅ 9 Dockerfiles | `us-central1-docker.pkg.dev/.../agora` |
| AGY SDK integration | ⚠️ Partial (6 of 17 agents) | Lindelof, Riemann, DeGennes use AGY; others use custom `AbstractAgent` |
| Agent framework split | ⚠️ Two frameworks | `AbstractAgent` (custom) vs `google.antigravity.Agent` (AGY SDK) |
| Centralized Agent Registry | ❌ Missing | Agents hardcode URLs or use env vars |
| GCP Secret Manager for API keys | ❌ Keys in `.env` file | `GEMINI_API_KEY`, `GALOIS_MISTRAL_KEY` in plaintext |
| Pub/Sub resilience layer | ❌ HTTP only | Budget alerts use Pub/Sub, but inter-agent comms are HTTP-only |
| GCS-backed Alexandrie (production) | ❌ Local filesystem only | `AlexandrieHub` writes to `/Users/...` paths |
| Hilbert / Einstein agents | ❌ Not implemented | — |

---

## 2. Proposed Changes

---

### Phase 1: New Agents — Hilbert & Einstein

#### [NEW] `agents/hilbert/hilbert.py`

**Purpose:** The **Hilbert Agent** formalizes research programs into axiomatic frameworks, inspired by Hilbert's 23 Problems and his foundational program. It takes a collection of empirical results and conjectures from the swarm and distills them into a coherent axiomatic system with explicit dependencies.

| Property | Value |
|---|---|
| Model | `gemini-2.5-pro` (GCP Cloud) → `gemini-2.5-pro` when available |
| Deep Think | Yes — uses `models/deep-research-max-preview-04-2026` for axiomatization |
| Location | Cloud Run (INTERNAL_ONLY) |
| Compute | 4 CPU / 8Gi |
| A2A Skills | `axiomatize_field`, `identify_open_problems`, `propose_research_program` |
| Deliverables | Formal axiomatic systems in Lean 4, ranked open problem lists, research program blueprints |

#### [NEW] `agents/einstein/einstein.py`

**Purpose:** The **Einstein Agent** synthesizes breakthrough theories by connecting seemingly unrelated domains — performing the "thought experiment" role. It ingests outputs from DeGennes (hypotheses), Galileo (empirical data), and Hilbert (axioms) to propose unified theoretical frameworks, analogous to how Einstein connected electromagnetism and gravity.

| Property | Value |
|---|---|
| Model | `gemini-2.5-pro` (GCP Cloud) |
| Deep Think | Yes — primary mode for theory unification |
| Location | Cloud Run (INTERNAL_ONLY) |
| Compute | 8 CPU / 16Gi |
| A2A Skills | `unify_theories`, `thought_experiment`, `propose_new_physics` |
| Deliverables | Unified theory proposals, cross-domain analogy mappings, falsifiable predictions |

---

### Phase 2: Model Promotion (All 17 Agents)

#### [MODIFY] All agent configurations

Promote every agent to the latest Gemini model tier:

| Agent | Current Model | Target Model | Deep Think | Budget |
|---|---|---|---|---|
| Socrates | `gemini-2.5-pro` | `gemini-2.5-pro` | No (fast routing) | $100 |
| Galois | `gemini-2.5-pro` | `gemini-2.5-pro` | Yes (MCTS creative) | $100 |
| Galileo | Z3 Oracle (no LLM) | Z3 + `gemini-2.5-pro` for design | No | $100 |
| Euler | `gemini-2.5-pro` + Lean 4 | `gemini-2.5-pro` + Lean 4 | No | $100 |
| Pythagore | `gemini-2.5-pro` + SymPy | `gemini-2.5-pro` + SymPy | No | $100 |
| Hypatie | `gemini-2.5-pro` + AGY SDK | `gemini-2.5-pro` | No | $100 |
| Riemann | `deep-research-max-preview` | `gemini-2.5-pro-deep-think` | Yes | — |
| Turing | `gemini-2.5-pro` | `gemini-2.5-pro` | No | $100 |
| Bourbaki | `gemini-2.5-pro` | `gemini-2.5-pro` | Yes (axiom) | $50 |
| Descartes | `gemini-2.5-pro` | `gemini-2.5-pro` | No | $25 |
| Heraclite | `gemini-2.5-pro` | `gemini-2.5-pro` + `mistral-large` | No | $100 |
| Archimedes | `gemini-2.5-pro` + MCTS | `gemini-2.5-pro` + MCTS | No | $3 |
| Aristotle | `gemini-2.5-flash` | `gemini-3.1-flash` | No | $10 |
| Lindelof | `gemini-2.5-pro` (AGY SDK) | `gemini-2.5-pro` ✅ already | No | — |
| Champollion | `gemini-2.5-flash` | `gemini-2.5-pro` | Yes (translation) | $5 |
| **Hilbert** | — (NEW) | `gemini-2.5-pro-deep-think` | Yes | $100 |
| **Einstein** | — (NEW) | `gemini-2.5-pro-deep-think` | Yes | $100 |

---

### Phase 3: GCP Cost Optimization

#### [MODIFY] `deploy/terraform/modules/cloud_run/main.tf`

- Enforce **spot instances** (preemptible) for all INTERNAL_ONLY agents
- Add **startup CPU boost** (warm-up) for cold-start latency reduction
- Configure **automatic scale-down** timeout to 60 seconds
- Set `max_instance_request_concurrency = 1` for deterministic agent behavior

```hcl
scaling {
  min_instance_count = 0   # Already enforced
  max_instance_count = var.max_replicas  # Default: 3
}
template {
  execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
  startup_cpu_boost     = true
  timeout               = "3600s"
  annotations = {
    "run.googleapis.com/execution-environment" = "gen2"
    "run.googleapis.com/cpu-throttling"        = "false"  # Keep CPU during request
  }
}
```

#### [MODIFY] `deploy/terraform/modules/agent_fleet/main.tf`

- Pre-build and cache all 17 agent images in Artifact Registry to speed up instantiation
- Add image digest pinning for reproducibility

---

### Phase 4: GCP Secret Manager

#### [NEW] `deploy/terraform/modules/secrets/main.tf`

Migrate all API keys from `.env` to GCP Secret Manager:

| Secret Name | Current Source | Agents Using |
|---|---|---|
| `GEMINI_API_KEY` | `.env` | All 17 agents |
| `GALOIS_MISTRAL_KEY` | `.env` | Heraclite, Riemann, peer review panels |
| `HF_TOKEN` | Not configured | Galois (SymBrain weights), Champollion |
| `ZENODO_API_KEY` | Not configured | Hypatie (paper archiving) |
| `NIM_API_KEY` | `.env` | Galileo (NVIDIA NIM) |

#### [MODIFY] All agent Dockerfiles

Replace `ENV` directives with Secret Manager volume mounts:

```dockerfile
# Before: ENV GEMINI_API_KEY=...
# After:  Injected via Cloud Run secret mount
```

#### [MODIFY] `deploy/terraform/modules/cloud_run/main.tf`

Add secret volume mounts per service:

```hcl
volumes {
  name = "gemini-key"
  secret {
    secret       = google_secret_manager_secret.gemini_key.secret_id
    items { key = "latest"; path = "GEMINI_API_KEY" }
  }
}
```

---

### Phase 5: Pub/Sub Resilience Layer

#### [NEW] `agents/common/pubsub.py`

Add Google Cloud Pub/Sub as a resilience layer alongside existing HTTP A2A:

| Topic | Publisher | Subscribers | Purpose |
|---|---|---|---|
| `agora-task-dispatch` | Socrates | All agents | Robust task fan-out |
| `agora-task-results` | All agents | Socrates, Hypatie | Result collection |
| `agora-dead-letter` | System | Turing | Failed message inspection |
| `agora-heartbeat` | All agents | Turing | Health monitoring |

- **Retry policy**: Exponential backoff (10s → 600s), max 5 attempts
- **Dead letter**: After 5 failures → `agora-dead-letter` topic
- **Ordering key**: `agent_name` to preserve per-agent message order
- **Acknowledgment deadline**: 600s (for long MCTS runs)

#### [MODIFY] `agents/common/a2a.py`

Add `PubSubTransport` as fallback when HTTP A2A fails:

```python
class A2AClient:
    async def delegate_task(self, ...):
        try:
            return await self._http_delegate(...)  # Primary: HTTP
        except (ConnectionError, TimeoutError):
            return await self._pubsub_delegate(...)  # Fallback: Pub/Sub
```

---

### Phase 6: GCS-Backed Alexandrie

#### [MODIFY] `alexandrie/hub.py`

Replace local filesystem storage with GCS backend:

```python
class AlexandrieHub:
    def __init__(self, gcs_bucket: str = "socrateai-alexandrie-vault"):
        self.client = storage.Client()
        self.bucket = self.client.bucket(gcs_bucket)
        # Local cache for hot artifacts
        self.local_cache = Path("/tmp/alexandrie_cache")
```

| Bucket | Purpose | Lifecycle |
|---|---|---|
| `socrateai-alexandrie-vault` | All artifacts (proofs, papers, datasets) | Nearline after 30 days |
| `socrateai-alexandrie-logs` | Agent execution logs | Delete after 90 days |
| `socrateai-alexandrie-scratch` | Temporary computation files | Delete after 7 days |

#### [MODIFY] `alexandrie/server.py`

Add GCS streaming upload/download endpoints.

---

### Phase 7: A2A Agent Cards & Registry

#### [NEW] `agents/common/registry.py`

Centralized agent registry backed by Firestore:

```python
class AgentRegistry:
    """Firestore-backed agent registry for runtime discovery."""
    COLLECTION = "agora_agent_registry"

    async def register(self, card: AgentCard) -> None: ...
    async def discover(self, skill: str) -> list[AgentCard]: ...
    async def heartbeat(self, agent_name: str) -> None: ...
    async def list_all(self) -> list[AgentCard]: ...
```

#### [MODIFY] All 17 agent servers

- Each agent registers itself on startup via `registry.register()`
- Each agent sends periodic heartbeats via `registry.heartbeat()`
- Socrates queries the registry to discover agents by skill

#### All 17 agents will expose A2A cards at `/.well-known/agent.json`:

| Agent | A2A Skills |
|---|---|
| Socrates | `classify_complexity`, `orchestrate_debate`, `certify_result` |
| Galois | `generate_conjecture`, `mcts_search`, `pslq_reduction` |
| Galileo | `simulate_montecarlo`, `integrate_ode`, `nim_query` |
| Euler | `verify_lean4`, `audit_proof`, `deepproblog_check` |
| Pythagore | `validate_geometry`, `check_dimensions` |
| Hypatie | `archive_artifact`, `compile_monograph`, `search_vault` |
| Riemann | `deep_research`, `generate_conjectures`, `check_novelty` |
| Turing | `profile_execution`, `enforce_budget`, `teardown_gcp` |
| Bourbaki | `axiomatize`, `formalize_structure` |
| Descartes | `map_coordinates`, `analytical_geometry` |
| Heraclite | `analyze_chaos`, `entropy_bound`, `peer_review` |
| Archimedes | `physics_model`, `fluid_dynamics` |
| Aristotle | `classify_logic`, `syllogism_check` |
| Lindelof | `topology_proof`, `compactness_check` |
| Champollion | `translate_notation`, `decode_historical_math` |
| **Hilbert** | `axiomatize_field`, `identify_open_problems`, `propose_research_program` |
| **Einstein** | `unify_theories`, `thought_experiment`, `propose_new_physics` |

---

### Phase 8: Future Agents (AI-Human Hybrid Research Lab Lifecycle)

Draft 6 new agents to anticipate a full genius-discovery pipeline:

| Agent | Inspiration | Purpose | Model Tier |
|---|---|---|---|
| **Curie** (Marie Curie) | Experimental Persistence | Long-running experimental campaigns with real lab equipment integration (IoT sensors, spectrometers). Manages multi-week experiment scheduling and data collection. | `gemini-2.5-pro` |
| **Ramanujan** | Intuitive Pattern Recognition | Pure mathematical intuition agent — generates conjectures from raw numerical patterns without formal training, complementing Galois's structured approach. Uses PSLQ and lattice reduction at extreme precision. | `gemini-2.5-pro-deep-think` |
| **Noether** (Emmy Noether) | Symmetry & Conservation Laws | Discovers hidden symmetries in datasets and derives conservation laws. Critical for physics-aware ML and ensuring model predictions respect fundamental invariants. | `gemini-2.5-pro` |
| **Feynman** | Pedagogical Communication | Translates complex discoveries into accessible explanations, generates teaching materials, creates interactive visualizations, and produces conference presentations. | `gemini-2.5-pro` |
| **Pasteur** | Applied Science Bridge | Bridges fundamental research to applied outcomes — patents, clinical trials, regulatory filings, technology transfer. Manages the "valley of death" between discovery and commercialization. | `gemini-2.5-pro` |
| **Lovelace** (Ada Lovelace) | Computational Algorithm Design | Designs novel algorithms to implement theoretical discoveries as production software. Generates optimized code, benchmarks, and deployment packages. | `gemini-2.5-pro` |

---

## 3. Complete 17-Agent Roster (v4.0)

| # | Agent | Model | Location | Deploy Mode | A2A | Purpose |
|---|---|---|---|---|---|---|
| 1 | Socrates | `gemini-2.5-pro` | Cloud Run | Serverless, `min=0` | ✅ | Dialectical Orchestrator |
| 2 | Galois | `gemini-2.5-pro` + Deep Think | Cloud Run | Spot, `min=0`, 8 CPU | ✅ | Creative Mathematician (SymBrain) |
| 3 | Galileo | Local + `gemini-2.5-pro` | Cloud Run | Spot, `min=0`, GPU optional | ✅ | Empirical Experimenter |
| 4 | Euler | `gemini-2.5-pro` + Lean 4 | Cloud Run | Spot, `min=0` | ✅ | Skeptical Verifier |
| 5 | Pythagore | Local SymPy + `gemini-2.5-pro` | Cloud Run | Spot, `min=0` | ✅ | Geometric Validator |
| 6 | Hypatie | `gemini-2.5-pro` + AGY SDK | Cloud Run | Spot, `min=0` | ✅ | Librarian & Vault Custodian |
| 7 | Riemann | `gemini-2.5-pro-deep-think` | Cloud Run | Spot, `min=0` | ✅ | Deep-Research Conjecture Generator |
| 8 | Turing | `gemini-2.5-flash` | Cloud Run | Spot, `min=0` | ✅ | Computational Optimizer & FinOps |
| 9 | Bourbaki | `gemini-2.5-pro` | Cloud Run | Spot, `min=0` | ✅ | Formal Axiomatizer |
| 10 | Descartes | `gemini-2.5-pro` | Cloud Run | Spot, `min=0` | ✅ | Analytical Mapper |
| 11 | Heraclite | `gemini-2.5-pro` + `mistral-large` | Cloud Run | Spot, `min=0` | ✅ | Chaos Analyst & Peer Reviewer |
| 12 | Archimedes | `gemini-2.5-pro` + SciPy | Cloud Run | Spot, `min=0` | ✅ | Physical Engineering |
| 13 | Aristotle | `gemini-2.5-flash` | Cloud Run | Spot, `min=0` | ✅ | Logic Classifier |
| 14 | Lindelof | `gemini-2.5-pro` | Cloud Run | Spot, `min=0` | ✅ | Topology Expert |
| 15 | Champollion | `gemini-2.5-pro` | Cloud Run | Spot, `min=0` | ✅ | Translation Rosetta Stone |
| 16 | **Hilbert** | `gemini-2.5-pro-deep-think` | Cloud Run | Spot, `min=0`, 4 CPU | ✅ | Axiomatic Program Builder |
| 17 | **Einstein** | `gemini-2.5-pro-deep-think` | Cloud Run | Spot, `min=0`, 8 CPU | ✅ | Theory Unification & Thought Experiments |

**All agents:** AGY SDK integrated · A2A agent card exposed · Images cached in Artifact Registry · Secrets via GCP Secret Manager · Pub/Sub fallback transport · Logs/artifacts on GCS via Hypatie.

---

## 4. Verification Plan — 22 Test Cases

### Infrastructure Tests

| # | Test Case | Validates |
|---|---|---|
| T1 | `terraform plan` succeeds with 17 agents | Terraform IaC correctness |
| T2 | All 17 Cloud Run services deploy with `min_replicas=0` | Scale-to-zero enforcement |
| T3 | All 17 services respond to `GET /health` within 5s after cold start | Warm-up + startup CPU boost |
| T4 | All 17 services serve `GET /.well-known/agent.json` with valid AgentCard | A2A agent card compliance |
| T5 | Agent registry Firestore collection contains 17 entries | Centralized registry |
| T6 | Spot instance preemption triggers graceful shutdown + Pub/Sub retry | Spot instance resilience |
| T7 | All 5 secrets accessible via Secret Manager volume mounts | Secret Manager migration |
| T8 | GCS bucket `socrateai-alexandrie-vault` accepts artifact uploads | GCS-backed Alexandrie |

### Agent Functionality Tests

| # | Test Case | Validates |
|---|---|---|
| T9 | Hilbert agent axiomatizes a set of 5 Galois conjectures into Lean 4 | Hilbert agent core function |
| T10 | Einstein agent unifies 2 DeGennes hypotheses from different domains | Einstein agent core function |
| T11 | Socrates routes a COMPLEX task through Galois → Galileo → Euler → Hilbert → Einstein pipeline | Full 5-agent pipeline |
| T12 | Riemann generates 5 novel Callens Conjectures with GNN provability scores | Riemann deep-research |
| T13 | Galois MCTS search on `gemini-2.5-pro` returns valid candidate in <60s | Model promotion validation |
| T14 | Hypatie compiles a 50-page LaTeX monograph and archives to GCS | GCS-backed monograph pipeline |

### Resilience Tests

| # | Test Case | Validates |
|---|---|---|
| T15 | HTTP A2A call fails → Pub/Sub fallback delivers task within 30s | Pub/Sub failover |
| T16 | Dead letter topic receives message after 5 failed retries | Dead letter queue |
| T17 | Agent heartbeat missing for 5 minutes triggers Turing alert | Health monitoring |
| T18 | Budget Guard kills all Cloud Run services when daily spend exceeds $50 | FinOps circuit breaker |

### Security Tests

| # | Test Case | Validates |
|---|---|---|
| T19 | INTERNAL_ONLY agents reject unauthenticated external requests | Network security |
| T20 | OIDC token injection works for inter-agent A2A calls | Authentication |
| T21 | `.env` file removed from Docker images (no plaintext secrets) | Secret hygiene |
| T22 | Alexandrie private vault artifacts are not accessible without IAM role | Data access control |

---

## 5. Implementation Priority & Timeline

| Phase | Scope | Estimated Effort | Priority |
|---|---|---|---|
| **Phase 1** | Hilbert + Einstein agents | 2 days | 🔴 High |
| **Phase 2** | Model promotion (all 17) | 1 day | 🔴 High |
| **Phase 3** | GCP cost optimization (spot, warm-up, scale-down) | 1 day | 🟡 Medium |
| **Phase 4** | GCP Secret Manager migration | 1 day | 🔴 High |
| **Phase 5** | Pub/Sub resilience layer | 2 days | 🟡 Medium |
| **Phase 6** | GCS-backed Alexandrie | 2 days | 🟡 Medium |
| **Phase 7** | A2A registry + full agent card exposure | 1 day | 🟡 Medium |
| **Phase 8** | Future agents (Curie, Ramanujan, Noether, Feynman, Pasteur, Lovelace) — draft only | 1 day | 🟢 Low |
| **Validation** | Run all 22 test cases | 1 day | 🔴 High |

**Total estimated effort: 12 days**

---

## Open Questions

> [!IMPORTANT]
> 1. **GCP Project billing**: Should we keep the existing project `gen-lang-client-0625573011` or create a dedicated `socrateai-agora-prod` project for the 17-agent fleet?
> 2. **Gemini 3.1 Pro availability**: Is `gemini-2.5-pro` available in the current project quota, or do we need to request access?
> 3. **Spot instance tolerance**: Some agents (Euler Lean 4 compilation) may not tolerate preemption mid-proof. Should we exempt Euler and Galois from spot instances?
> 4. **Future agents scope**: Should Curie, Ramanujan, Noether, Feynman, Pasteur, Lovelace be fully implemented now or only scaffolded as agent stubs with A2A cards?
