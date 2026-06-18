// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Budget Monitor
//!
//! Real-time cost tracking for frugal-AI enforcement. Monitors
//! compute expenditure against the budget thresholds:
//!
//! - **$100** per experiment
//! - **$500** total across all experiments
//!
//! When thresholds are approached, the monitor emits warnings and
//! can trigger automatic shutdown of expensive operations.

use serde::{Deserialize, Serialize};
use std::time::Instant;
use thiserror::Error;

/// Errors from the budget monitor.
#[derive(Debug, Error)]
pub enum BudgetError {
    /// Experiment budget exceeded.
    #[error("experiment budget exceeded: ${spent:.2} > ${limit:.2}")]
    ExperimentBudgetExceeded { spent: f64, limit: f64 },

    /// Total budget exceeded.
    #[error("total budget exceeded: ${spent:.2} > ${limit:.2}")]
    TotalBudgetExceeded { spent: f64, limit: f64 },

    /// Negative cost recorded.
    #[error("negative cost: ${0:.2}")]
    NegativeCost(f64),
}

/// Budget alert levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum BudgetAlert {
    /// Budget usage is within normal limits (< 50%).
    Normal,
    /// Budget usage is elevated (50–80%).
    Warning,
    /// Budget usage is critical (80–100%).
    Critical,
    /// Budget has been exceeded (> 100%).
    Exceeded,
}

impl BudgetAlert {
    /// Determines the alert level from utilization fraction.
    pub fn from_utilization(utilization: f64) -> Self {
        match utilization {
            u if u >= 1.0 => Self::Exceeded,
            u if u >= 0.8 => Self::Critical,
            u if u >= 0.5 => Self::Warning,
            _ => Self::Normal,
        }
    }
}

/// Budget configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BudgetConfig {
    /// Per-experiment budget limit in USD.
    pub experiment_limit: f64,
    /// Total budget limit in USD.
    pub total_limit: f64,
    /// Whether to auto-stop on budget exceeded.
    pub auto_stop: bool,
    /// Warning threshold as fraction of limit (default: 0.8).
    pub warning_threshold: f64,
}

impl Default for BudgetConfig {
    fn default() -> Self {
        Self {
            experiment_limit: 100.0,
            total_limit: 500.0,
            auto_stop: true,
            warning_threshold: 0.8,
        }
    }
}

/// A single cost entry in the ledger.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostEntry {
    /// Description of the cost source.
    pub description: String,
    /// Cost in USD.
    pub amount: f64,
    /// Elapsed seconds since monitor start.
    pub elapsed_secs: f64,
    /// Experiment index.
    pub experiment: u32,
}

/// Real-time budget monitor.
///
/// Tracks all compute expenditure and enforces the frugal-AI budget
/// constraints ($100/experiment, $500/total).
#[derive(Debug)]
pub struct BudgetMonitor {
    config: BudgetConfig,
    /// Total spend across all experiments.
    total_spent: f64,
    /// Current experiment spend.
    experiment_spent: f64,
    /// Current experiment index.
    current_experiment: u32,
    /// Cost ledger.
    ledger: Vec<CostEntry>,
    /// Start time.
    start_time: Instant,
}

impl BudgetMonitor {
    /// Creates a new budget monitor with the given configuration.
    pub fn new(config: BudgetConfig) -> Self {
        Self {
            config,
            total_spent: 0.0,
            experiment_spent: 0.0,
            current_experiment: 0,
            ledger: Vec::new(),
            start_time: Instant::now(),
        }
    }

    /// Creates a budget monitor with default thresholds ($100/$500).
    pub fn default_thresholds() -> Self {
        Self::new(BudgetConfig::default())
    }

    /// Records a cost expenditure.
    ///
    /// # Arguments
    ///
    /// * `amount` — Cost in USD
    /// * `description` — Human-readable description of the cost source
    ///
    /// # Errors
    ///
    /// Returns [`BudgetError::NegativeCost`] if amount is negative.
    /// Returns [`BudgetError::ExperimentBudgetExceeded`] if experiment limit is hit.
    /// Returns [`BudgetError::TotalBudgetExceeded`] if total limit is hit.
    pub fn record_cost(
        &mut self,
        amount: f64,
        description: impl Into<String>,
    ) -> Result<BudgetAlert, BudgetError> {
        if amount < 0.0 {
            return Err(BudgetError::NegativeCost(amount));
        }

        self.experiment_spent += amount;
        self.total_spent += amount;

        let entry = CostEntry {
            description: description.into(),
            amount,
            elapsed_secs: self.start_time.elapsed().as_secs_f64(),
            experiment: self.current_experiment,
        };
        self.ledger.push(entry);

        // Check experiment limit
        if self.experiment_spent > self.config.experiment_limit {
            tracing::error!(
                spent = self.experiment_spent,
                limit = self.config.experiment_limit,
                "experiment budget exceeded"
            );
            if self.config.auto_stop {
                return Err(BudgetError::ExperimentBudgetExceeded {
                    spent: self.experiment_spent,
                    limit: self.config.experiment_limit,
                });
            }
        }

        // Check total limit
        if self.total_spent > self.config.total_limit {
            tracing::error!(
                spent = self.total_spent,
                limit = self.config.total_limit,
                "total budget exceeded"
            );
            if self.config.auto_stop {
                return Err(BudgetError::TotalBudgetExceeded {
                    spent: self.total_spent,
                    limit: self.config.total_limit,
                });
            }
        }

        let alert = self.current_alert();
        if alert == BudgetAlert::Warning || alert == BudgetAlert::Critical {
            tracing::warn!(
                ?alert,
                experiment_spent = self.experiment_spent,
                total_spent = self.total_spent,
                "budget alert"
            );
        }

        Ok(alert)
    }

    /// Begins a new experiment, resetting per-experiment counters.
    pub fn begin_experiment(&mut self) {
        self.current_experiment += 1;
        self.experiment_spent = 0.0;
        tracing::info!(experiment = self.current_experiment, "new experiment started");
    }

    /// Returns the current budget alert level.
    pub fn current_alert(&self) -> BudgetAlert {
        let exp_util = self.experiment_spent / self.config.experiment_limit;
        let total_util = self.total_spent / self.config.total_limit;
        let max_util = exp_util.max(total_util);
        BudgetAlert::from_utilization(max_util)
    }

    /// Returns the experiment utilization fraction.
    pub fn experiment_utilization(&self) -> f64 {
        self.experiment_spent / self.config.experiment_limit
    }

    /// Returns the total utilization fraction.
    pub fn total_utilization(&self) -> f64 {
        self.total_spent / self.config.total_limit
    }

    /// Returns the remaining experiment budget.
    pub fn experiment_remaining(&self) -> f64 {
        (self.config.experiment_limit - self.experiment_spent).max(0.0)
    }

    /// Returns the remaining total budget.
    pub fn total_remaining(&self) -> f64 {
        (self.config.total_limit - self.total_spent).max(0.0)
    }

    /// Returns the total spent so far.
    pub fn total_spent(&self) -> f64 {
        self.total_spent
    }

    /// Returns the current experiment spent.
    pub fn experiment_spent(&self) -> f64 {
        self.experiment_spent
    }

    /// Returns the full cost ledger.
    pub fn ledger(&self) -> &[CostEntry] {
        &self.ledger
    }

    /// Returns the budget configuration.
    pub fn config(&self) -> &BudgetConfig {
        &self.config
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normal_spending() {
        let mut monitor = BudgetMonitor::default_thresholds();
        let alert = monitor.record_cost(10.0, "GPU inference").unwrap();
        assert_eq!(alert, BudgetAlert::Normal);
        assert!((monitor.total_spent() - 10.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_experiment_budget_exceeded() {
        let mut monitor = BudgetMonitor::default_thresholds();
        let result = monitor.record_cost(150.0, "expensive operation");
        assert!(result.is_err());
    }

    #[test]
    fn test_total_budget_exceeded() {
        let mut monitor = BudgetMonitor::default_thresholds();
        for i in 0..5 {
            monitor.begin_experiment();
            monitor.record_cost(90.0, format!("experiment {i}")).unwrap();
        }
        // Total is now $450, next should exceed $500
        monitor.begin_experiment();
        let result = monitor.record_cost(90.0, "over budget");
        assert!(result.is_err());
    }

    #[test]
    fn test_warning_threshold() {
        let mut monitor = BudgetMonitor::default_thresholds();
        monitor.record_cost(55.0, "half budget").unwrap();
        assert_eq!(monitor.current_alert(), BudgetAlert::Warning);
    }

    #[test]
    fn test_critical_threshold() {
        let mut monitor = BudgetMonitor::default_thresholds();
        monitor.record_cost(85.0, "near limit").unwrap();
        assert_eq!(monitor.current_alert(), BudgetAlert::Critical);
    }

    #[test]
    fn test_negative_cost() {
        let mut monitor = BudgetMonitor::default_thresholds();
        assert!(monitor.record_cost(-5.0, "invalid").is_err());
    }

    #[test]
    fn test_new_experiment_resets() {
        let mut monitor = BudgetMonitor::default_thresholds();
        monitor.record_cost(50.0, "first run").unwrap();
        monitor.begin_experiment();
        assert!((monitor.experiment_spent() - 0.0).abs() < f64::EPSILON);
        assert!((monitor.total_spent() - 50.0).abs() < f64::EPSILON);
    }
}
