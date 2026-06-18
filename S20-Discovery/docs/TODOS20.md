# S₂₀ / S₁₅ Benchmarks To-Do List (TODOS20)

## Phase 1: Bug Fixes & Patching
- [ ] Fix `run_full_benchmark.py` API mismatch.
- [ ] Implement `s15_kernel/patching.py` using **Option A (Forward Hook)**.
- [ ] Update `benchmark_mmlu.py` and `benchmark_tpot.py` to use the new patching utility.
- [ ] Add known $S_{15}$ sequence values to `test_sequence.py`.

## Phase 2: Correctness & Unit Tests
- [ ] Create `s15_kernel/tests/test_patching.py` and verify outputs differ from baseline.
- [ ] Create `s15_kernel/tests/test_numerical.py` for gradient and property verification.
- [ ] Run all `pytest` locally on CPU.

## Phase 3: GPU Microbenchmarks (Latency)
- [ ] Deploy Dockerfile and Cloud Build YAML for GPU jobs.
- [ ] Run latency sweep on GCP (T4/L4).
- [ ] Validate O(LW) vs O(L²) memory scaling.

## Phase 4: End-to-End Evaluation
- [ ] Run MMLU on `Phi-3-mini` via L4/T4.
- [ ] Run TPOT + Energy tracking on `Phi-3-mini` via L4/T4.
- [ ] Log results honestly.

## Phase 5: Scale Up (Future)
- [ ] Implement Option B (Layer Replacement) for maximal performance.
- [ ] Run on Llama-3-8B.
- [ ] Run full industrialization suite on A100/H100.
