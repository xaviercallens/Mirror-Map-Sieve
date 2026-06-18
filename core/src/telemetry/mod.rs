// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Telemetry
//!
//! Performance counters and budget monitoring for frugal-AI enforcement.
//! Tracks solver evaluations, MCTS node expansions, latency percentiles,
//! and real-time cost against the $100/experiment and $500/total thresholds.

pub mod metrics;
pub mod budget_monitor;

pub use metrics::{PerformanceCounters, MetricSnapshot};
pub use budget_monitor::{BudgetMonitor, BudgetConfig, BudgetAlert};
