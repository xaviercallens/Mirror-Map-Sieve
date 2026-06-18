// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Performance Counters
//!
//! Real-time performance metrics for the SymBrain cognitive engine.
//! Tracks solver evaluations, MCTS node expansions, latency percentiles,
//! and memory utilization.

use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, Instant};

/// A snapshot of performance metrics at a point in time.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricSnapshot {
    /// Total solver function evaluations.
    pub solver_evals: u64,
    /// Total MCTS nodes expanded.
    pub mcts_nodes: u64,
    /// Total PFC routing decisions.
    pub pfc_routes: u64,
    /// Total LoRA adaptation steps.
    pub lora_steps: u64,
    /// Mean latency in microseconds (rolling window).
    pub mean_latency_us: f64,
    /// P95 latency in microseconds.
    pub p95_latency_us: f64,
    /// P99 latency in microseconds.
    pub p99_latency_us: f64,
    /// Timestamp of this snapshot (seconds since start).
    pub elapsed_secs: f64,
}

/// Atomic performance counters for lock-free telemetry.
///
/// All counters use `AtomicU64` for safe concurrent updates from
/// multiple inference threads without locking.
pub struct PerformanceCounters {
    solver_evals: AtomicU64,
    mcts_nodes: AtomicU64,
    pfc_routes: AtomicU64,
    lora_steps: AtomicU64,
    /// Rolling window of latency samples (microseconds).
    latency_samples: std::sync::Mutex<Vec<u64>>,
    /// Maximum latency samples to keep.
    max_samples: usize,
    /// Start time for elapsed calculation.
    start_time: Instant,
}

impl PerformanceCounters {
    /// Creates new performance counters.
    ///
    /// # Arguments
    ///
    /// * `max_latency_samples` — Maximum rolling window size for latency tracking
    pub fn new(max_latency_samples: usize) -> Self {
        Self {
            solver_evals: AtomicU64::new(0),
            mcts_nodes: AtomicU64::new(0),
            pfc_routes: AtomicU64::new(0),
            lora_steps: AtomicU64::new(0),
            latency_samples: std::sync::Mutex::new(Vec::with_capacity(max_latency_samples)),
            max_samples: max_latency_samples,
            start_time: Instant::now(),
        }
    }

    /// Increments the solver evaluation counter.
    pub fn record_solver_eval(&self) {
        self.solver_evals.fetch_add(1, Ordering::Relaxed);
    }

    /// Increments the solver evaluation counter by n.
    pub fn record_solver_evals(&self, n: u64) {
        self.solver_evals.fetch_add(n, Ordering::Relaxed);
    }

    /// Increments the MCTS node counter.
    pub fn record_mcts_node(&self) {
        self.mcts_nodes.fetch_add(1, Ordering::Relaxed);
    }

    /// Increments the MCTS node counter by n.
    pub fn record_mcts_nodes(&self, n: u64) {
        self.mcts_nodes.fetch_add(n, Ordering::Relaxed);
    }

    /// Increments the PFC routing counter.
    pub fn record_pfc_route(&self) {
        self.pfc_routes.fetch_add(1, Ordering::Relaxed);
    }

    /// Increments the LoRA step counter.
    pub fn record_lora_step(&self) {
        self.lora_steps.fetch_add(1, Ordering::Relaxed);
    }

    /// Records a latency sample.
    pub fn record_latency(&self, duration: Duration) {
        let us = duration.as_micros() as u64;
        if let Ok(mut samples) = self.latency_samples.lock() {
            if samples.len() >= self.max_samples {
                samples.remove(0);
            }
            samples.push(us);
        }
    }

    /// Takes a snapshot of current metrics.
    pub fn snapshot(&self) -> MetricSnapshot {
        let (mean, p95, p99) = self.compute_latency_percentiles();

        MetricSnapshot {
            solver_evals: self.solver_evals.load(Ordering::Relaxed),
            mcts_nodes: self.mcts_nodes.load(Ordering::Relaxed),
            pfc_routes: self.pfc_routes.load(Ordering::Relaxed),
            lora_steps: self.lora_steps.load(Ordering::Relaxed),
            mean_latency_us: mean,
            p95_latency_us: p95,
            p99_latency_us: p99,
            elapsed_secs: self.start_time.elapsed().as_secs_f64(),
        }
    }

    /// Resets all counters.
    pub fn reset(&self) {
        self.solver_evals.store(0, Ordering::Relaxed);
        self.mcts_nodes.store(0, Ordering::Relaxed);
        self.pfc_routes.store(0, Ordering::Relaxed);
        self.lora_steps.store(0, Ordering::Relaxed);
        if let Ok(mut samples) = self.latency_samples.lock() {
            samples.clear();
        }
    }

    /// Computes latency percentiles from the rolling window.
    fn compute_latency_percentiles(&self) -> (f64, f64, f64) {
        let samples = match self.latency_samples.lock() {
            Ok(s) => s.clone(),
            Err(_) => return (0.0, 0.0, 0.0),
        };

        if samples.is_empty() {
            return (0.0, 0.0, 0.0);
        }

        let mut sorted = samples;
        sorted.sort_unstable();
        let n = sorted.len();

        let mean = sorted.iter().sum::<u64>() as f64 / n as f64;
        let p95_idx = (n as f64 * 0.95) as usize;
        let p99_idx = (n as f64 * 0.99) as usize;

        let p95 = sorted[p95_idx.min(n - 1)] as f64;
        let p99 = sorted[p99_idx.min(n - 1)] as f64;

        (mean, p95, p99)
    }
}

impl std::fmt::Debug for PerformanceCounters {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let snap = self.snapshot();
        f.debug_struct("PerformanceCounters")
            .field("solver_evals", &snap.solver_evals)
            .field("mcts_nodes", &snap.mcts_nodes)
            .field("pfc_routes", &snap.pfc_routes)
            .field("mean_latency_us", &snap.mean_latency_us)
            .finish()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_counter_increment() {
        let counters = PerformanceCounters::new(100);
        counters.record_solver_eval();
        counters.record_solver_eval();
        counters.record_mcts_nodes(10);

        let snap = counters.snapshot();
        assert_eq!(snap.solver_evals, 2);
        assert_eq!(snap.mcts_nodes, 10);
    }

    #[test]
    fn test_latency_recording() {
        let counters = PerformanceCounters::new(100);
        counters.record_latency(Duration::from_micros(100));
        counters.record_latency(Duration::from_micros(200));
        counters.record_latency(Duration::from_micros(300));

        let snap = counters.snapshot();
        assert!((snap.mean_latency_us - 200.0).abs() < 1.0);
    }

    #[test]
    fn test_reset() {
        let counters = PerformanceCounters::new(100);
        counters.record_solver_evals(50);
        counters.reset();
        assert_eq!(counters.snapshot().solver_evals, 0);
    }
}
