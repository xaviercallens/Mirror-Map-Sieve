// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Speculative Early Stopping
//!
//! Time-bounded search controller that enforces 500ms time slices per
//! MCTS search step. When a time slice expires, the search backtracks
//! to the parent node and returns the most robust child (highest visit
//! count).
//!
//! ## Design Rationale
//!
//! In frugal-AI deployment, unbounded search is unacceptable. Early stopping
//! guarantees worst-case latency while preserving statistical robustness
//! by favoring well-explored subtrees over high-value but undersampled ones.

use serde::{Deserialize, Serialize};
use std::time::{Duration, Instant};
use thiserror::Error;

/// Errors from the early stopping system.
#[derive(Debug, Error)]
pub enum EarlyStopError {
    /// No search step has been started.
    #[error("no active search step — call start() first")]
    NotStarted,

    /// The time slice was already consumed.
    #[error("time slice expired ({0:?} elapsed)")]
    Expired(Duration),
}

/// A single time slice allocation for one MCTS search step.
///
/// Tracks elapsed time via `Instant::now()` and provides
/// remaining-budget queries.
#[derive(Debug, Clone)]
pub struct TimeSlice {
    /// Maximum allowed duration for this time slice.
    pub budget: Duration,
    /// Start time of the slice (set on start).
    start: Option<Instant>,
    /// Elapsed duration at the time of stopping.
    elapsed_at_stop: Option<Duration>,
}

impl TimeSlice {
    /// Default time slice: 500ms.
    pub const DEFAULT_BUDGET_MS: u64 = 500;

    /// Creates a new time slice with the given budget.
    pub fn new(budget: Duration) -> Self {
        Self {
            budget,
            start: None,
            elapsed_at_stop: None,
        }
    }

    /// Creates a time slice with the default 500ms budget.
    pub fn default_500ms() -> Self {
        Self::new(Duration::from_millis(Self::DEFAULT_BUDGET_MS))
    }

    /// Starts the time slice clock.
    pub fn start(&mut self) {
        self.start = Some(Instant::now());
        self.elapsed_at_stop = None;
    }

    /// Returns the elapsed time since start.
    ///
    /// # Errors
    ///
    /// Returns [`EarlyStopError::NotStarted`] if the slice hasn't started.
    pub fn elapsed(&self) -> Result<Duration, EarlyStopError> {
        match self.start {
            Some(start) => Ok(start.elapsed()),
            None => Err(EarlyStopError::NotStarted),
        }
    }

    /// Returns the remaining time in this slice.
    ///
    /// Returns `Duration::ZERO` if the budget is exhausted.
    pub fn remaining(&self) -> Result<Duration, EarlyStopError> {
        let elapsed = self.elapsed()?;
        Ok(self.budget.saturating_sub(elapsed))
    }

    /// Returns true if the time slice has expired.
    pub fn is_expired(&self) -> bool {
        self.start
            .map(|s| s.elapsed() >= self.budget)
            .unwrap_or(false)
    }

    /// Stops the time slice and records the elapsed time.
    pub fn stop(&mut self) {
        if let Some(start) = self.start {
            self.elapsed_at_stop = Some(start.elapsed());
        }
    }

    /// Returns the elapsed time at the point of stopping, if available.
    pub fn elapsed_at_stop(&self) -> Option<Duration> {
        self.elapsed_at_stop
    }
}

/// Child selection result after early stopping.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RobustChild {
    /// Index of the selected child.
    pub child_index: usize,
    /// Action ID of the selected child.
    pub action: u32,
    /// Visit count (robustness metric).
    pub visit_count: u64,
    /// Average value.
    pub average_value: f64,
    /// Whether selection was due to early stopping (vs. normal completion).
    pub was_early_stopped: bool,
}

/// Speculative Early Stopping Policy.
///
/// Wraps MCTS search steps with time budgets and provides
/// robust child selection when time expires.
#[derive(Debug)]
pub struct EarlyStopPolicy {
    /// Per-step time budget.
    step_budget: Duration,
    /// Total number of steps executed.
    steps_executed: u64,
    /// Total number of early stops triggered.
    early_stops: u64,
    /// Current active time slice, if any.
    current_slice: Option<TimeSlice>,
}

impl Default for EarlyStopPolicy {
    fn default() -> Self {
        Self::new(Duration::from_millis(TimeSlice::DEFAULT_BUDGET_MS))
    }
}

impl EarlyStopPolicy {
    /// Creates a new early stopping policy with the given per-step budget.
    pub fn new(step_budget: Duration) -> Self {
        Self {
            step_budget,
            steps_executed: 0,
            early_stops: 0,
            current_slice: None,
        }
    }

    /// Begins a new search step, starting the time slice clock.
    pub fn begin_step(&mut self) -> &TimeSlice {
        let mut slice = TimeSlice::new(self.step_budget);
        slice.start();
        self.current_slice = Some(slice);
        self.current_slice.as_ref().unwrap()
    }

    /// Checks whether the current step should be stopped early.
    ///
    /// Returns `true` if the time slice has expired.
    pub fn should_stop(&self) -> bool {
        self.current_slice
            .as_ref()
            .map(|s| s.is_expired())
            .unwrap_or(false)
    }

    /// Ends the current step and selects the most robust child.
    ///
    /// The most robust child is the one with the highest visit count,
    /// as visit count correlates with estimation confidence.
    ///
    /// # Arguments
    ///
    /// * `children` — Slice of (action, visit_count, average_value) tuples
    pub fn end_step(&mut self, children: &[(u32, u64, f64)]) -> Option<RobustChild> {
        let was_early = self.should_stop();
        if was_early {
            self.early_stops += 1;
        }
        self.steps_executed += 1;

        // Stop the clock
        if let Some(ref mut slice) = self.current_slice {
            slice.stop();
        }

        if children.is_empty() {
            return None;
        }

        // Select child with highest visit count (most robust)
        let (best_idx, &(action, visit_count, average_value)) = children
            .iter()
            .enumerate()
            .max_by_key(|(_, (_, visits, _))| *visits)?;

        Some(RobustChild {
            child_index: best_idx,
            action,
            visit_count,
            average_value,
            was_early_stopped: was_early,
        })
    }

    /// Returns the remaining time in the current step.
    pub fn remaining(&self) -> Option<Duration> {
        self.current_slice
            .as_ref()
            .and_then(|s| s.remaining().ok())
    }

    /// Returns the total number of steps executed.
    pub fn steps_executed(&self) -> u64 {
        self.steps_executed
    }

    /// Returns the total number of early stops triggered.
    pub fn early_stops(&self) -> u64 {
        self.early_stops
    }

    /// Returns the early stopping rate.
    pub fn early_stop_rate(&self) -> f64 {
        if self.steps_executed == 0 {
            0.0
        } else {
            self.early_stops as f64 / self.steps_executed as f64
        }
    }

    /// Returns the per-step budget.
    pub fn step_budget(&self) -> Duration {
        self.step_budget
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_time_slice_default() {
        let slice = TimeSlice::default_500ms();
        assert_eq!(slice.budget, Duration::from_millis(500));
    }

    #[test]
    fn test_time_slice_not_started() {
        let slice = TimeSlice::default_500ms();
        assert!(slice.elapsed().is_err());
        assert!(!slice.is_expired());
    }

    #[test]
    fn test_time_slice_starts() {
        let mut slice = TimeSlice::default_500ms();
        slice.start();
        assert!(slice.elapsed().unwrap() < Duration::from_millis(100));
        assert!(!slice.is_expired());
    }

    #[test]
    fn test_early_stop_policy() {
        let mut policy = EarlyStopPolicy::default();
        policy.begin_step();

        // Should not stop immediately (500ms budget)
        assert!(!policy.should_stop());

        let children = vec![
            (0, 100, 0.5),
            (1, 250, 0.7),
            (2, 50, 0.9),
        ];

        let result = policy.end_step(&children).unwrap();
        // Should select action 1 (highest visit count = 250)
        assert_eq!(result.action, 1);
        assert_eq!(result.visit_count, 250);
        assert!(!result.was_early_stopped);
    }

    #[test]
    fn test_empty_children() {
        let mut policy = EarlyStopPolicy::default();
        policy.begin_step();
        let result = policy.end_step(&[]);
        assert!(result.is_none());
    }

    #[test]
    fn test_early_stop_with_tiny_budget() {
        let mut policy = EarlyStopPolicy::new(Duration::from_nanos(1));
        policy.begin_step();
        // With 1ns budget, should expire almost immediately
        std::thread::sleep(Duration::from_micros(10));
        assert!(policy.should_stop());

        let children = vec![(0, 10, 0.5)];
        let result = policy.end_step(&children).unwrap();
        assert!(result.was_early_stopped);
        assert_eq!(policy.early_stops(), 1);
    }

    #[test]
    fn test_statistics() {
        let mut policy = EarlyStopPolicy::default();
        for _ in 0..5 {
            policy.begin_step();
            policy.end_step(&[(0, 1, 0.5)]);
        }
        assert_eq!(policy.steps_executed(), 5);
    }
}
