// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Dynamic Gating Girdles
//!
//! Implements the gating function σ_ded = f(C) that maps complexity
//! scores to deductive reasoning allocation. The function is strictly
//! monotonic, ensuring higher complexity queries always receive at
//! least as much deductive budget as simpler ones.
//!
//! ## Properties
//!
//! - **Strictly monotonic**: C₁ < C₂ ⟹ f(C₁) < f(C₂)
//! - **Deductive floor**: f(0) ≥ 0.30
//! - **Bounded**: f(C) ∈ [floor, ceiling] for all C ∈ [0, 1]
//! - **Smooth**: sigmoid-based for differentiability

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from the gating system.
#[derive(Debug, Error)]
pub enum GatingError {
    /// Complexity value is out of range.
    #[error("complexity {0} is outside [0, 1]")]
    InvalidComplexity(f64),

    /// Configuration constraint violated.
    #[error("invalid gating config: {0}")]
    InvalidConfig(String),
}

/// Configuration for the Dynamic Gating Girdle.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GatingConfig {
    /// Minimum deductive allocation (floor). Default: 0.30.
    pub floor: f64,
    /// Maximum deductive allocation (ceiling). Default: 0.85.
    pub ceiling: f64,
    /// Sigmoid center (inflection point). Default: 0.50.
    pub center: f64,
    /// Sigmoid steepness. Default: 8.0.
    pub steepness: f64,
}

impl Default for GatingConfig {
    fn default() -> Self {
        Self {
            floor: 0.30,
            ceiling: 0.85,
            center: 0.50,
            steepness: 8.0,
        }
    }
}

impl GatingConfig {
    /// Validates the configuration.
    pub fn validate(&self) -> Result<(), GatingError> {
        if self.floor < 0.0 || self.floor > 1.0 {
            return Err(GatingError::InvalidConfig(format!(
                "floor must be in [0, 1], got {}",
                self.floor
            )));
        }
        if self.ceiling < self.floor || self.ceiling > 1.0 {
            return Err(GatingError::InvalidConfig(format!(
                "ceiling must be in [floor, 1], got {}",
                self.ceiling
            )));
        }
        if self.steepness <= 0.0 {
            return Err(GatingError::InvalidConfig(format!(
                "steepness must be > 0, got {}",
                self.steepness
            )));
        }
        Ok(())
    }
}

/// Dynamic Gating Girdle.
///
/// Maps complexity C ∈ [0, 1] to deductive allocation σ_ded via a
/// strictly monotonic sigmoid function:
///
/// ```text
/// σ_ded = floor + (ceiling - floor) · sigmoid(steepness · (C - center))
/// ```
///
/// where sigmoid(x) = 1 / (1 + e^(-x)).
#[derive(Debug, Clone)]
pub struct GatingGirdle {
    config: GatingConfig,
}

impl GatingGirdle {
    /// Creates a new gating girdle with the given configuration.
    ///
    /// # Errors
    ///
    /// Returns [`GatingError::InvalidConfig`] if configuration is invalid.
    pub fn new(config: GatingConfig) -> Result<Self, GatingError> {
        config.validate()?;
        Ok(Self { config })
    }

    /// Creates a gating girdle with default configuration.
    pub fn default_config() -> Self {
        Self {
            config: GatingConfig::default(),
        }
    }

    /// Computes σ_ded = f(C) — the deductive allocation for complexity C.
    ///
    /// This function is strictly monotonic: C₁ < C₂ ⟹ f(C₁) < f(C₂).
    ///
    /// # Arguments
    ///
    /// * `complexity` — Complexity score C ∈ [0, 1]
    ///
    /// # Errors
    ///
    /// Returns [`GatingError::InvalidComplexity`] if C is outside [0, 1].
    pub fn compute_sigma_ded(&self, complexity: f64) -> Result<f64, GatingError> {
        if !(0.0..=1.0).contains(&complexity) {
            return Err(GatingError::InvalidComplexity(complexity));
        }

        let sigmoid = self.sigmoid(complexity);
        let sigma = self.config.floor + (self.config.ceiling - self.config.floor) * sigmoid;

        Ok(sigma)
    }

    /// Computes the full gating vector (σ_ded, σ_gen, σ_mcts) from complexity.
    ///
    /// - σ_ded = f(C) via the monotonic sigmoid
    /// - σ_mcts = (1 - σ_ded) × mcts_fraction(C)
    /// - σ_gen = 1 - σ_ded - σ_mcts
    ///
    /// # Errors
    ///
    /// Returns [`GatingError::InvalidComplexity`] if C is outside [0, 1].
    pub fn compute_full_gating(
        &self,
        complexity: f64,
    ) -> Result<(f64, f64, f64), GatingError> {
        let sigma_ded = self.compute_sigma_ded(complexity)?;

        // Higher complexity → more MCTS budget
        let mcts_fraction = complexity * 0.5; // up to 50% of remaining budget
        let remaining = 1.0 - sigma_ded;
        let sigma_mcts = remaining * mcts_fraction;
        let sigma_gen = remaining - sigma_mcts;

        Ok((sigma_ded, sigma_gen, sigma_mcts))
    }

    /// Verifies strict monotonicity by checking the derivative is positive.
    ///
    /// The derivative of the sigmoid-based gating function is always positive
    /// for steepness > 0, which guarantees strict monotonicity.
    pub fn verify_monotonicity(&self, num_samples: usize) -> bool {
        if num_samples < 2 {
            return true;
        }

        let step = 1.0 / (num_samples - 1) as f64;
        let mut prev = self
            .compute_sigma_ded(0.0)
            .unwrap_or(self.config.floor);

        for i in 1..num_samples {
            let c = (i as f64 * step).min(1.0);
            let current = self
                .compute_sigma_ded(c)
                .unwrap_or(self.config.floor);
            if current <= prev {
                return false;
            }
            prev = current;
        }
        true
    }

    /// Estimates complexity from raw query features.
    ///
    /// Features: (word_count, unique_words, reasoning_depth, domain_specificity)
    pub fn estimate_complexity(
        word_count: usize,
        unique_words: usize,
        reasoning_depth: u32,
        domain_specificity: f64,
    ) -> f64 {
        let length_factor = (word_count as f64 / 200.0).min(0.3);
        let vocab_factor = if word_count > 0 {
            (unique_words as f64 / word_count as f64) * 0.2
        } else {
            0.0
        };
        let depth_factor = (reasoning_depth as f64 * 0.1).min(0.3);
        let domain_factor = domain_specificity.clamp(0.0, 0.2);

        (length_factor + vocab_factor + depth_factor + domain_factor).clamp(0.0, 1.0)
    }

    /// Returns a reference to the configuration.
    pub fn config(&self) -> &GatingConfig {
        &self.config
    }

    /// Internal sigmoid function: 1 / (1 + e^(-steepness * (x - center))).
    fn sigmoid(&self, x: f64) -> f64 {
        let exponent = -self.config.steepness * (x - self.config.center);
        1.0 / (1.0 + exponent.exp())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deductive_floor() {
        let gate = GatingGirdle::default_config();
        let sigma = gate.compute_sigma_ded(0.0).unwrap();
        assert!(
            sigma >= 0.30 - f64::EPSILON,
            "σ_ded at C=0 should be ≥ 0.30, got {sigma}"
        );
    }

    #[test]
    fn test_strict_monotonicity() {
        let gate = GatingGirdle::default_config();
        assert!(gate.verify_monotonicity(1000));
    }

    #[test]
    fn test_bounded_output() {
        let gate = GatingGirdle::default_config();
        for i in 0..=100 {
            let c = i as f64 / 100.0;
            let sigma = gate.compute_sigma_ded(c).unwrap();
            assert!(sigma >= 0.30 - f64::EPSILON, "below floor at C={c}");
            assert!(sigma <= 0.85 + f64::EPSILON, "above ceiling at C={c}");
        }
    }

    #[test]
    fn test_invalid_complexity() {
        let gate = GatingGirdle::default_config();
        assert!(gate.compute_sigma_ded(-0.1).is_err());
        assert!(gate.compute_sigma_ded(1.1).is_err());
    }

    #[test]
    fn test_full_gating_sums_to_one() {
        let gate = GatingGirdle::default_config();
        let (ded, gen_val, mcts) = gate.compute_full_gating(0.5).unwrap();
        let sum = ded + gen_val + mcts;
        assert!(
            (sum - 1.0).abs() < 1e-10,
            "gating components should sum to 1.0, got {sum}"
        );
    }

    #[test]
    fn test_complexity_estimation() {
        let c = GatingGirdle::estimate_complexity(100, 60, 3, 0.15);
        assert!(c > 0.0 && c <= 1.0);
    }
}
