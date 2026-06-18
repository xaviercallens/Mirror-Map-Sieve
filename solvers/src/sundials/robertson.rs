// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Robertson Stiff Chemical Kinetics
//!
//! Classic stiff test problem from H.H. Robertson (1966).
//! Three-species chemical reaction system with widely separated
//! time scales spanning 10¹¹.
//!
//! ## System of ODEs
//!
//! ```text
//! dy₁/dt = -0.04·y₁ + 10⁴·y₂·y₃
//! dy₂/dt =  0.04·y₁ - 10⁴·y₂·y₃ - 3×10⁷·y₂²
//! dy₃/dt =  3×10⁷·y₂²
//! ```
//!
//! ## Initial Conditions
//!
//! y₁(0) = 1.0, y₂(0) = 0.0, y₃(0) = 0.0
//!
//! ## Conservation Law
//!
//! y₁ + y₂ + y₃ = 1.0 for all t (mass conservation).

use super::cvode_bridge::{CVodeConfig, CVodeSolver, RhsFn, SolverMethod};
use thiserror::Error;

/// Errors from the Robertson system.
#[derive(Debug, Error)]
pub enum RobertsonError {
    /// Solver error.
    #[error("solver error: {0}")]
    SolverError(#[from] super::cvode_bridge::CVodeError),

    /// Conservation law violated.
    #[error("conservation violated: sum = {sum} (expected 1.0, error = {error})")]
    ConservationViolated { sum: f64, error: f64 },
}

/// Robertson stiff chemical kinetics system.
///
/// The system has three rate constants:
/// - k₁ = 0.04 (slow)
/// - k₂ = 10⁴ (fast)
/// - k₃ = 3×10⁷ (very fast)
///
/// This extreme stiffness ratio (k₃/k₁ ~ 10⁹) makes the system
/// a standard benchmark for stiff ODE solvers.
pub struct RobertsonSystem {
    /// Rate constant k₁.
    pub k1: f64,
    /// Rate constant k₂.
    pub k2: f64,
    /// Rate constant k₃.
    pub k3: f64,
}

impl Default for RobertsonSystem {
    fn default() -> Self {
        Self {
            k1: 0.04,
            k2: 1.0e4,
            k3: 3.0e7,
        }
    }
}

impl RobertsonSystem {
    /// Creates a Robertson system with default rate constants.
    pub fn new() -> Self {
        Self::default()
    }

    /// Creates a Robertson system with custom rate constants.
    pub fn with_rates(k1: f64, k2: f64, k3: f64) -> Self {
        Self { k1, k2, k3 }
    }

    /// Returns the right-hand side function for the CVODE solver.
    pub fn rhs_fn(&self) -> RhsFn {
        let k1 = self.k1;
        let k2 = self.k2;
        let k3 = self.k3;

        Box::new(move |_t, y| {
            let y1 = y[0];
            let y2 = y[1];
            let y3 = y[2];

            let dy1 = -k1 * y1 + k2 * y2 * y3;
            let dy2 = k1 * y1 - k2 * y2 * y3 - k3 * y2 * y2;
            let dy3 = k3 * y2 * y2;

            Ok(vec![dy1, dy2, dy3])
        })
    }

    /// Returns the standard initial conditions: [1.0, 0.0, 0.0].
    pub fn initial_conditions() -> Vec<f64> {
        vec![1.0, 0.0, 0.0]
    }

    /// Creates a CVODE solver configured for this stiff system.
    ///
    /// Uses BDF method with tight tolerances appropriate for
    /// the extreme stiffness ratio.
    pub fn create_solver(&self) -> Result<CVodeSolver, RobertsonError> {
        let config = CVodeConfig {
            method: SolverMethod::BDF,
            rtol: 1e-4,
            atol: 1e-8,
            max_steps: 1_000_000,
            max_order: 5,
            initial_step: 1e-4,
            min_step: 1e-15,
            max_step: 0.0,
        };

        let solver = CVodeSolver::new(
            config,
            Self::initial_conditions(),
            0.0,
            self.rhs_fn(),
        )?;

        Ok(solver)
    }

    /// Checks the conservation law: y₁ + y₂ + y₃ = 1.0.
    ///
    /// # Arguments
    ///
    /// * `y` — State vector [y₁, y₂, y₃]
    /// * `tolerance` — Maximum acceptable deviation from 1.0
    pub fn check_conservation(y: &[f64], tolerance: f64) -> Result<(), RobertsonError> {
        let sum: f64 = y.iter().sum();
        let error = (sum - 1.0).abs();
        if error > tolerance {
            Err(RobertsonError::ConservationViolated { sum, error })
        } else {
            Ok(())
        }
    }

    /// Returns the stiffness ratio k₃/k₁.
    pub fn stiffness_ratio(&self) -> f64 {
        self.k3 / self.k1
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_initial_conservation() {
        let y0 = RobertsonSystem::initial_conditions();
        RobertsonSystem::check_conservation(&y0, 1e-15).unwrap();
    }

    #[test]
    fn test_rhs_at_t0() {
        let sys = RobertsonSystem::new();
        let rhs = sys.rhs_fn();
        let y0 = RobertsonSystem::initial_conditions();

        let dy = rhs(0.0, &y0).unwrap();
        // dy1/dt = -0.04 * 1.0 + 10^4 * 0.0 * 0.0 = -0.04
        assert!((dy[0] - (-0.04)).abs() < 1e-10);
        // dy2/dt = 0.04 * 1.0 - ... = 0.04
        assert!((dy[1] - 0.04).abs() < 1e-10);
        // dy3/dt = 0
        assert!((dy[2] - 0.0).abs() < 1e-10);
    }

    #[test]
    fn test_stiffness_ratio() {
        let sys = RobertsonSystem::new();
        assert!((sys.stiffness_ratio() - 7.5e8).abs() < 1e3);
    }

    #[test]
    fn test_solve_short_time() {
        let sys = RobertsonSystem::new();
        let mut solver = sys.create_solver().unwrap();

        let (t, y) = solver.solve(0.4).unwrap();
        assert!((t - 0.4).abs() < 1e-6);

        // Check conservation (should hold to solver tolerance)
        RobertsonSystem::check_conservation(&y, 1e-2).unwrap();

        // y1 should have decreased from 1.0
        assert!(y[0] < 1.0, "y1 should decrease, got {}", y[0]);
    }
}
