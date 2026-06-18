// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # SymBrain Cognitive Engine
//!
//! Biomimetic cognitive engine implementing the SymBrain v1–v5 architecture.
//! Provides a complete neuro-symbolic reasoning pipeline:
//!
//! 1. **PFC Router** — Prefrontal Cortex–inspired 3-stage classifier that
//!    produces a routing tensor σ = (σ_ded, σ_gen, σ_mcts).
//! 2. **RLCF Optimizer** — Ricci-Lévy Curvature Flow for weight optimization
//!    with PCG Hessian solver and Lévy α-stable stochastic perturbation.
//! 3. **LoRA Engine** — On-device Low-Rank Adaptation with cache-line–aligned
//!    matrices and norm-bounded updates.
//! 4. **MCTS Search** — Safe parallel Monte Carlo Tree Search with UCB1
//!    selection and Rayon-based expansion.
//! 5. **Dynamic Gating** — Gating Girdles ensuring σ_ded = f(C) is strictly
//!    monotonic with a deductive floor of 0.30.
//! 6. **Early Stopping** — Speculative early stopping with 500ms time slices
//!    and robust child selection by visit count.
//! 7. **Co-Processor Pipeline** — 8-bit quantized proof pipeline with batch
//!    tensor verification.

pub mod pfc_router;
pub mod rlcf_optimizer;
pub mod lora_engine;
pub mod mcts_search;
pub mod dynamic_gating;
pub mod early_stopping;
pub mod coproc_pipeline;

pub use pfc_router::{PFCRouter, RoutingTensor, ComplexityScore, STEMCategory};
pub use rlcf_optimizer::{RLCFOptimizer, RLCFConfig, UpdateStep};
pub use lora_engine::{LoRAConfig, LoRAUpdate};
pub use mcts_search::{MCTSTree, MCTSNode, MCTSConfig, SearchResult};
pub use dynamic_gating::{GatingGirdle, GatingConfig};
pub use early_stopping::{EarlyStopPolicy, TimeSlice};
pub use coproc_pipeline::{QuantizedConstraint, ProofBatch, VerificationResult};
