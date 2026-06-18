# SocrateAI Scientific Agora — Platform Specification
**Version**: v4.4.0
**Author**: Xavier Callens / Socrate AI Lab
**Patent**: US-PAT-PEND-2026-0525

## 1. System Architecture
- **Multi-agent framework**: 28 agents, 15 pipelines
- **Three-language ecosystem**: Python (≥3.11), Rust (2024 edition), Lean 4
- **GCP deployment**: Cloud Run, Secret Manager, Pub/Sub
- **Core principle**: Neuro-symbolic frugal AI

## 2. Agent Specification
- **AbstractAgent contract**: `think()` → `act()` → `run()`
- **AgentConfig**: name, model, role, budget_limit, project_budget
- **AgentResult**: answer, confidence, cost_usd, proofs, telemetry
- **AgentRole enum**: DIALECTICIAN, EXPERIMENTER, VERIFIER, FORMALIZER, INTUITION_SCOUT, ALGO_TRANSLATOR, MEMORY_KEEPER, etc.
- **Budget guard**: $30/pipeline, $100/project defaults
- **Quality tiers**: Production (>200 lines), Thin (90-200 lines), Stub (37 lines)

## 3. Pipeline Specification
- **PipelineResult contract**: symposium_id, stages_completed, total_duration_s, total_cost_usd, pdf_path, tex_path, vault_artifact_ids, audit_trail_path, etc.
- **Pipeline types**: Symposium (10 stages), Discovery (6 stages), Patent (8 stages), Prototyping (6 stages), Literature Review (4 stages)
- **agent_generate()**: identity, prompt, model, strict mode support
- **Error handling**: `strict_mode=True` propagates errors. Fallback returns `[MOCK_FALLBACK: error_msg]`.

## 4. Multi-LLM Integration
- **Primary**: Gemini 2.5 Pro/Flash via Antigravity SDK
- **Peer review**: Mistral via direct HTTP API
- **Secret management**: GCP Secret Manager → env var fallback

## 5. Lean 4 Verification Standard
- **Ground truth**: 0 sorry, 0 axiom
- **Verification pipeline**: agent_generate → lake build → parse output
- **Production files**: ExactRationalWitness, CombinatorialIdentity (clean)
- **Achievement files**: auto-generated, may contain sorry (expected)

## 6. Quality Requirements (v4.4.0)
- All agents must have either real implementation (>90 lines) or explicit deprecation notice
- All pipelines must populate stages_completed correctly as `list[str]`
- No MOCK_FALLBACK in strict_mode
- Test coverage: minimum 5 critical agents tested
- No API keys in repository — Secret Manager only

## 7. Deployment Specification
- **GCP Project**: gen-lang-client-0625573011
- **Region**: us-central1
- **Secret names**: gemini-api-key, mistral-api-key
- **Docker**: Python 3.12-slim + uv, non-root user
- **Cloud Run**: 2Gi memory, 2 CPU, 3600s timeout, gen2 execution
