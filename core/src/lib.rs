// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Agora Core
//!
//! Core framework for the **SocrateAI Scientific Agora** — a neuro-symbolic,
//! frugal-AI cognitive engine integrating biomimetic reasoning with formal
//! verification.
//!
//! ## Modules
//!
//! - [`symbrain`] — SymBrain cognitive engine (PFC router, RLCF optimizer,
//!   LoRA adaptation, MCTS search, dynamic gating, early stopping,
//!   co-processor pipeline)
//! - [`memory`] — Three-zone arena allocator, NUMA pinning, bump allocator
//! - [`kernel`] — RunuX kernel interface (scheduler, SIMD ops, FFI bridge)
//! - [`telemetry`] — Performance counters, budget monitoring
//!
//! ## Budget Constraints
//!
//! This framework enforces frugal-AI budget limits:
//! - **$100** per experiment
//! - **$500** total across all experiments
//! - All deployments use `min_replicas = 0` for serverless cold-start

pub mod symbrain;
pub mod memory;
pub mod kernel;
pub mod telemetry;

/// Framework version string.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Patent identifier for the SymBrain cognitive architecture.
pub const PATENT_ID: &str = "US-PAT-PEND-2026-0525";
