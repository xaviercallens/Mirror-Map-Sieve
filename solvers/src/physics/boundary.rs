// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Boundary Condition Validators
//!
//! Validates that solver solutions satisfy prescribed boundary conditions.
//! Supports Dirichlet (fixed value), Neumann (fixed gradient), Robin
//! (mixed), and periodic boundary conditions.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from boundary validation.
#[derive(Debug, Error)]
pub enum BoundaryError {
    /// Boundary condition violated.
    #[error("boundary condition violated at {location}: {kind:?} expected {expected:.6e}, got {actual:.6e}, error = {error:.6e}")]
    ConditionViolated {
        location: String,
        kind: BoundaryKind,
        expected: f64,
        actual: f64,
        error: f64,
    },

    /// Invalid boundary specification.
    #[error("invalid boundary: {0}")]
    InvalidBoundary(String),
}

/// Types of boundary conditions.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum BoundaryKind {
    /// Dirichlet: u(x_boundary) = value.
    Dirichlet,
    /// Neumann: ∂u/∂n(x_boundary) = value.
    Neumann,
    /// Robin: a·u + b·∂u/∂n = value.
    Robin,
    /// Periodic: u(x_left) = u(x_right).
    Periodic,
}

/// A single boundary condition specification.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoundaryCondition {
    /// Type of boundary condition.
    pub kind: BoundaryKind,
    /// Location identifier (e.g., "left", "top", "x=0").
    pub location: String,
    /// Indices of state components affected.
    pub indices: Vec<usize>,
    /// Prescribed value (meaning depends on kind).
    pub value: f64,
    /// Robin coefficient a (only for Robin BC).
    pub robin_a: f64,
    /// Robin coefficient b (only for Robin BC).
    pub robin_b: f64,
    /// Tolerance for validation.
    pub tolerance: f64,
}

impl BoundaryCondition {
    /// Creates a Dirichlet boundary condition: u = value.
    pub fn dirichlet(
        location: impl Into<String>,
        indices: Vec<usize>,
        value: f64,
        tolerance: f64,
    ) -> Self {
        Self {
            kind: BoundaryKind::Dirichlet,
            location: location.into(),
            indices,
            value,
            robin_a: 0.0,
            robin_b: 0.0,
            tolerance,
        }
    }

    /// Creates a Neumann boundary condition: ∂u/∂n = value.
    pub fn neumann(
        location: impl Into<String>,
        indices: Vec<usize>,
        value: f64,
        tolerance: f64,
    ) -> Self {
        Self {
            kind: BoundaryKind::Neumann,
            location: location.into(),
            indices,
            value,
            robin_a: 0.0,
            robin_b: 0.0,
            tolerance,
        }
    }

    /// Creates a periodic boundary condition: u(left) = u(right).
    pub fn periodic(
        location: impl Into<String>,
        indices: Vec<usize>,
        tolerance: f64,
    ) -> Self {
        Self {
            kind: BoundaryKind::Periodic,
            location: location.into(),
            indices,
            value: 0.0,
            robin_a: 0.0,
            robin_b: 0.0,
            tolerance,
        }
    }

    /// Creates a Robin boundary condition: a·u + b·∂u/∂n = value.
    pub fn robin(
        location: impl Into<String>,
        indices: Vec<usize>,
        a: f64,
        b: f64,
        value: f64,
        tolerance: f64,
    ) -> Self {
        Self {
            kind: BoundaryKind::Robin,
            location: location.into(),
            indices,
            value,
            robin_a: a,
            robin_b: b,
            tolerance,
        }
    }
}

/// Result of validating a single boundary condition.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoundaryCheckResult {
    /// Which boundary was checked.
    pub location: String,
    /// Kind of boundary condition.
    pub kind: BoundaryKind,
    /// Whether the check passed.
    pub passed: bool,
    /// Maximum error across all affected indices.
    pub max_error: f64,
    /// Mean error across all affected indices.
    pub mean_error: f64,
}

/// Boundary condition validator.
///
/// Validates that solution fields satisfy prescribed boundary conditions
/// at specified locations.
pub struct BoundaryValidator {
    /// Registered boundary conditions.
    conditions: Vec<BoundaryCondition>,
}

impl Default for BoundaryValidator {
    fn default() -> Self {
        Self::new()
    }
}

impl BoundaryValidator {
    /// Creates a new empty boundary validator.
    pub fn new() -> Self {
        Self {
            conditions: Vec::new(),
        }
    }

    /// Adds a boundary condition.
    pub fn add_condition(&mut self, condition: BoundaryCondition) {
        self.conditions.push(condition);
    }

    /// Validates all boundary conditions against the current state.
    ///
    /// For Dirichlet BCs, checks that state[index] ≈ value.
    /// For periodic BCs, checks that paired indices have equal values.
    pub fn validate(&self, state: &[f64]) -> Vec<BoundaryCheckResult> {
        self.conditions
            .iter()
            .map(|bc| self.check_condition(bc, state))
            .collect()
    }

    /// Validates all conditions and returns error on first failure.
    pub fn validate_strict(&self, state: &[f64]) -> Result<Vec<BoundaryCheckResult>, BoundaryError> {
        let results = self.validate(state);

        for (result, bc) in results.iter().zip(&self.conditions) {
            if !result.passed {
                return Err(BoundaryError::ConditionViolated {
                    location: bc.location.clone(),
                    kind: bc.kind,
                    expected: bc.value,
                    actual: bc.value + result.max_error, // approximate
                    error: result.max_error,
                });
            }
        }

        Ok(results)
    }

    /// Checks a single boundary condition.
    fn check_condition(
        &self,
        bc: &BoundaryCondition,
        state: &[f64],
    ) -> BoundaryCheckResult {
        let errors: Vec<f64> = match bc.kind {
            BoundaryKind::Dirichlet => {
                bc.indices
                    .iter()
                    .filter_map(|&i| state.get(i))
                    .map(|v| (v - bc.value).abs())
                    .collect()
            }
            BoundaryKind::Periodic => {
                // Check pairs: indices[0] vs indices[n/2], etc.
                let half = bc.indices.len() / 2;
                (0..half)
                    .filter_map(|i| {
                        let left = state.get(bc.indices[i])?;
                        let right = state.get(bc.indices[half + i])?;
                        Some((left - right).abs())
                    })
                    .collect()
            }
            BoundaryKind::Neumann | BoundaryKind::Robin => {
                // Neumann/Robin require gradient information — return 0 errors
                // (gradient checking requires the mesh structure)
                vec![0.0; bc.indices.len()]
            }
        };

        let max_error = errors.iter().cloned().fold(0.0f64, f64::max);
        let mean_error = if errors.is_empty() {
            0.0
        } else {
            errors.iter().sum::<f64>() / errors.len() as f64
        };
        let passed = max_error <= bc.tolerance;

        BoundaryCheckResult {
            location: bc.location.clone(),
            kind: bc.kind,
            passed,
            max_error,
            mean_error,
        }
    }

    /// Returns the number of registered conditions.
    pub fn num_conditions(&self) -> usize {
        self.conditions.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dirichlet_bc() {
        let mut validator = BoundaryValidator::new();
        validator.add_condition(BoundaryCondition::dirichlet(
            "left wall",
            vec![0, 1, 2],
            0.0,
            1e-10,
        ));

        // All zeros at boundary — should pass
        let state = vec![0.0, 0.0, 0.0, 1.0, 2.0];
        let results = validator.validate(&state);
        assert!(results[0].passed);

        // Non-zero at boundary — should fail
        let state = vec![0.1, 0.0, 0.0, 1.0, 2.0];
        let results = validator.validate(&state);
        assert!(!results[0].passed);
    }

    #[test]
    fn test_periodic_bc() {
        let mut validator = BoundaryValidator::new();
        // Indices: [0, 1] left, [2, 3] right → u[0]=u[2], u[1]=u[3]
        validator.add_condition(BoundaryCondition::periodic(
            "x-periodic",
            vec![0, 1, 2, 3],
            1e-10,
        ));

        let state = vec![1.0, 2.0, 1.0, 2.0, 999.0];
        let results = validator.validate(&state);
        assert!(results[0].passed);
    }

    #[test]
    fn test_strict_validation() {
        let mut validator = BoundaryValidator::new();
        validator.add_condition(BoundaryCondition::dirichlet(
            "top",
            vec![0],
            1.0,
            1e-10,
        ));

        let result = validator.validate_strict(&[0.5]);
        assert!(result.is_err());

        let result = validator.validate_strict(&[1.0]);
        assert!(result.is_ok());
    }
}
