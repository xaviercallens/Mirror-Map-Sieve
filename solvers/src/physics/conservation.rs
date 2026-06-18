// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Conservation Law Validators
//!
//! Validates mass, charge, and energy conservation across solver
//! time steps. Provides post-integration checks to detect numerical
//! drift and ensure physical fidelity.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from conservation validation.
#[derive(Debug, Error)]
pub enum ConservationError {
    /// A conservation law was violated.
    #[error("{law:?} conservation violated: initial = {initial:.6e}, final = {current:.6e}, drift = {drift:.6e}")]
    LawViolated {
        law: ConservationLaw,
        initial: f64,
        current: f64,
        drift: f64,
    },

    /// State vector has wrong dimension.
    #[error("state dimension mismatch: expected {expected}, got {got}")]
    DimensionMismatch { expected: usize, got: usize },
}

/// Types of conservation laws.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConservationLaw {
    /// Mass conservation: total mass is preserved.
    Mass,
    /// Charge conservation: total electric charge is preserved.
    Charge,
    /// Energy conservation: total energy is preserved.
    Energy,
    /// Momentum conservation: total momentum is preserved.
    Momentum,
    /// Custom conserved quantity.
    Custom,
}

/// Result of a conservation check.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConservationResult {
    /// Which law was checked.
    pub law: ConservationLaw,
    /// Initial value of the conserved quantity.
    pub initial_value: f64,
    /// Current value of the conserved quantity.
    pub current_value: f64,
    /// Absolute drift.
    pub absolute_drift: f64,
    /// Relative drift (if initial != 0).
    pub relative_drift: f64,
    /// Whether the check passed.
    pub passed: bool,
    /// Tolerance used.
    pub tolerance: f64,
}

/// Type alias for conserved quantity computation functions.
///
/// Takes a state vector and returns the scalar conserved quantity.
pub type ConservedQuantityFn = Box<dyn Fn(&[f64]) -> f64 + Send + Sync>;

/// Conservation law validator.
///
/// Stores the initial values of conserved quantities and checks
/// them against current values after each solver step.
pub struct ConservationValidator {
    /// Registered conservation laws with their computation functions.
    laws: Vec<(ConservationLaw, ConservedQuantityFn)>,
    /// Initial values of conserved quantities.
    initial_values: Vec<f64>,
    /// Tolerance for each law.
    tolerances: Vec<f64>,
    /// Whether initial values have been set.
    initialized: bool,
}

impl ConservationValidator {
    /// Creates a new empty validator.
    pub fn new() -> Self {
        Self {
            laws: Vec::new(),
            initial_values: Vec::new(),
            tolerances: Vec::new(),
            initialized: false,
        }
    }

    /// Registers a conservation law with its computation function.
    ///
    /// # Arguments
    ///
    /// * `law` — Type of conservation law
    /// * `compute` — Function that computes the conserved quantity from state
    /// * `tolerance` — Maximum acceptable drift
    pub fn register(
        &mut self,
        law: ConservationLaw,
        compute: ConservedQuantityFn,
        tolerance: f64,
    ) {
        self.laws.push((law, compute));
        self.tolerances.push(tolerance);
    }

    /// Initializes the validator with the initial state.
    ///
    /// Must be called before [`check`].
    pub fn initialize(&mut self, state: &[f64]) {
        self.initial_values = self
            .laws
            .iter()
            .map(|(_, compute)| compute(state))
            .collect();
        self.initialized = true;
    }

    /// Checks all registered conservation laws against the current state.
    ///
    /// Returns a vector of results, one per registered law.
    pub fn check(&self, state: &[f64]) -> Vec<ConservationResult> {
        self.laws
            .iter()
            .enumerate()
            .map(|(i, (law, compute))| {
                let initial = if self.initialized {
                    self.initial_values[i]
                } else {
                    0.0
                };
                let current = compute(state);
                let absolute_drift = (current - initial).abs();
                let relative_drift = if initial.abs() > 1e-30 {
                    absolute_drift / initial.abs()
                } else {
                    absolute_drift
                };
                let tolerance = self.tolerances[i];
                let passed = relative_drift <= tolerance;

                ConservationResult {
                    law: *law,
                    initial_value: initial,
                    current_value: current,
                    absolute_drift,
                    relative_drift,
                    passed,
                    tolerance,
                }
            })
            .collect()
    }

    /// Checks all laws and returns an error for the first violation.
    pub fn check_strict(&self, state: &[f64]) -> Result<Vec<ConservationResult>, ConservationError> {
        let results = self.check(state);

        for result in &results {
            if !result.passed {
                return Err(ConservationError::LawViolated {
                    law: result.law,
                    initial: result.initial_value,
                    current: result.current_value,
                    drift: result.relative_drift,
                });
            }
        }

        Ok(results)
    }

    /// Returns the number of registered laws.
    pub fn num_laws(&self) -> usize {
        self.laws.len()
    }
}

impl Default for ConservationValidator {
    fn default() -> Self {
        Self::new()
    }
}

/// Creates a mass conservation function (sum of state components).
pub fn mass_conservation() -> ConservedQuantityFn {
    Box::new(|state: &[f64]| state.iter().sum())
}

/// Creates an energy conservation function (sum of squares / 2).
pub fn kinetic_energy() -> ConservedQuantityFn {
    Box::new(|state: &[f64]| state.iter().map(|x| x * x).sum::<f64>() * 0.5)
}

/// Creates a charge conservation function with given charge weights.
pub fn charge_conservation(charges: Vec<f64>) -> ConservedQuantityFn {
    Box::new(move |state: &[f64]| {
        state
            .iter()
            .zip(&charges)
            .map(|(s, q)| s * q)
            .sum()
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mass_conservation() {
        let mut validator = ConservationValidator::new();
        validator.register(ConservationLaw::Mass, mass_conservation(), 1e-6);

        let state0 = vec![1.0, 0.0, 0.0]; // Robertson initial
        validator.initialize(&state0);

        let state1 = vec![0.9, 0.05, 0.05]; // Slight drift
        let results = validator.check(&state1);
        assert!(results[0].passed);

        let state2 = vec![0.9, 0.05, 0.1]; // Conservation violated
        let results = validator.check(&state2);
        assert!(!results[0].passed);
    }

    #[test]
    fn test_strict_check() {
        let mut validator = ConservationValidator::new();
        validator.register(ConservationLaw::Mass, mass_conservation(), 1e-6);
        validator.initialize(&[1.0, 2.0, 3.0]);

        // Sum = 6.0, should pass
        let result = validator.check_strict(&[2.0, 1.0, 3.0]);
        assert!(result.is_ok());

        // Sum = 7.0, should fail
        let result = validator.check_strict(&[2.0, 2.0, 3.0]);
        assert!(result.is_err());
    }

    #[test]
    fn test_energy_conservation() {
        let mut validator = ConservationValidator::new();
        validator.register(ConservationLaw::Energy, kinetic_energy(), 1e-4);
        validator.initialize(&[1.0, 1.0, 1.0]); // E = 1.5

        let results = validator.check(&[1.0, 1.0, 1.0]);
        assert!(results[0].passed);
        assert!((results[0].absolute_drift).abs() < 1e-10);
    }
}
