// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Lotka-Volterra Predator-Prey Dynamics
//!
//! Classical predator-prey model describing oscillatory population
//! dynamics between two interacting species.
//!
//! ## System of ODEs
//!
//! ```text
//! dx/dt = αx - βxy     (prey growth)
//! dy/dt = δxy - γy     (predator growth)
//! ```
//!
//! Where:
//! - x = prey population
//! - y = predator population
//! - α = prey birth rate
//! - β = predation rate
//! - γ = predator death rate
//! - δ = predator reproduction efficiency
//!
//! ## Conservation
//!
//! The system has a conserved quantity (Hamiltonian):
//! ```text
//! H(x, y) = δx - γ ln(x) + βy - α ln(y) = constant
//! ```

use super::cvode_bridge::{CVodeConfig, CVodeSolver, RhsFn, SolverMethod};
use thiserror::Error;

/// Errors from the Lotka-Volterra system.
#[derive(Debug, Error)]
pub enum LotkaVolterraError {
    /// Solver error.
    #[error("solver error: {0}")]
    SolverError(#[from] super::cvode_bridge::CVodeError),

    /// Population went negative (unphysical).
    #[error("negative population at t = {t}: x = {x}, y = {y}")]
    NegativePopulation { t: f64, x: f64, y: f64 },

    /// Invalid parameter.
    #[error("invalid parameter: {0}")]
    InvalidParameter(String),
}

/// Lotka-Volterra predator-prey system.
#[derive(Debug, Clone)]
pub struct LotkaVolterraSystem {
    /// Prey birth rate α.
    pub alpha: f64,
    /// Predation rate β.
    pub beta: f64,
    /// Predator death rate γ.
    pub gamma: f64,
    /// Predator reproduction efficiency δ.
    pub delta: f64,
}

impl Default for LotkaVolterraSystem {
    fn default() -> Self {
        Self {
            alpha: 1.1,
            beta: 0.4,
            gamma: 0.4,
            delta: 0.1,
        }
    }
}

impl LotkaVolterraSystem {
    /// Creates a Lotka-Volterra system with default parameters.
    pub fn new() -> Self {
        Self::default()
    }

    /// Creates a system with custom parameters.
    ///
    /// # Errors
    ///
    /// Returns [`LotkaVolterraError::InvalidParameter`] if any parameter is non-positive.
    pub fn with_params(
        alpha: f64,
        beta: f64,
        gamma: f64,
        delta: f64,
    ) -> Result<Self, LotkaVolterraError> {
        if alpha <= 0.0 || beta <= 0.0 || gamma <= 0.0 || delta <= 0.0 {
            return Err(LotkaVolterraError::InvalidParameter(
                "all parameters must be positive".to_string(),
            ));
        }
        Ok(Self {
            alpha,
            beta,
            gamma,
            delta,
        })
    }

    /// Returns the right-hand side function for the CVODE solver.
    pub fn rhs_fn(&self) -> RhsFn {
        let alpha = self.alpha;
        let beta = self.beta;
        let gamma = self.gamma;
        let delta = self.delta;

        Box::new(move |_t, y| {
            let x = y[0]; // prey
            let y_val = y[1]; // predator

            let dx = alpha * x - beta * x * y_val;
            let dy = delta * x * y_val - gamma * y_val;

            Ok(vec![dx, dy])
        })
    }

    /// Returns standard initial conditions.
    pub fn initial_conditions() -> Vec<f64> {
        vec![10.0, 5.0] // [prey, predator]
    }

    /// Creates a CVODE solver for this system.
    pub fn create_solver(
        &self,
        x0: f64,
        y0: f64,
    ) -> Result<CVodeSolver, LotkaVolterraError> {
        let config = CVodeConfig {
            method: SolverMethod::Adams,
            rtol: 1e-8,
            atol: 1e-10,
            max_steps: 500_000,
            max_order: 5,
            initial_step: 0.01,
            min_step: 1e-15,
            max_step: 0.1,
        };

        let solver = CVodeSolver::new(config, vec![x0, y0], 0.0, self.rhs_fn())?;
        Ok(solver)
    }

    /// Computes the conserved Hamiltonian H(x, y).
    ///
    /// ```text
    /// H = δx - γ ln(x) + βy - α ln(y)
    /// ```
    ///
    /// This quantity should be constant along any trajectory.
    pub fn hamiltonian(&self, x: f64, y: f64) -> f64 {
        self.delta * x - self.gamma * x.ln() + self.beta * y - self.alpha * y.ln()
    }

    /// Returns the non-trivial equilibrium point (x*, y*).
    ///
    /// ```text
    /// x* = γ/δ,  y* = α/β
    /// ```
    pub fn equilibrium(&self) -> (f64, f64) {
        (self.gamma / self.delta, self.alpha / self.beta)
    }

    /// Estimates the oscillation period using linearization.
    ///
    /// Near the equilibrium, the oscillation period is approximately:
    /// ```text
    /// T = 2π / √(αγ)
    /// ```
    pub fn estimated_period(&self) -> f64 {
        2.0 * std::f64::consts::PI / (self.alpha * self.gamma).sqrt()
    }

    /// Checks that populations remain physical (non-negative).
    pub fn check_physical(y: &[f64], t: f64) -> Result<(), LotkaVolterraError> {
        if y[0] < -1e-10 || y[1] < -1e-10 {
            Err(LotkaVolterraError::NegativePopulation {
                t,
                x: y[0],
                y: y[1],
            })
        } else {
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_equilibrium() {
        let sys = LotkaVolterraSystem::new();
        let (x_eq, y_eq) = sys.equilibrium();

        // At equilibrium, RHS should be zero
        let rhs = sys.rhs_fn();
        let dy = rhs(0.0, &[x_eq, y_eq]).unwrap();
        assert!((dy[0]).abs() < 1e-10, "dx/dt at equilibrium = {}", dy[0]);
        assert!((dy[1]).abs() < 1e-10, "dy/dt at equilibrium = {}", dy[1]);
    }

    #[test]
    fn test_hamiltonian_conservation() {
        let sys = LotkaVolterraSystem::new();
        let mut solver = sys.create_solver(10.0, 5.0).unwrap();

        let h0 = sys.hamiltonian(10.0, 5.0);

        let (t, y) = solver.solve(5.0).unwrap();
        assert!((t - 5.0).abs() < 1e-6);

        let h1 = sys.hamiltonian(y[0], y[1]);

        // Hamiltonian should be approximately conserved
        let drift = (h1 - h0).abs() / h0.abs();
        assert!(
            drift < 0.01,
            "Hamiltonian drift = {:.6} (H0={h0:.6}, H1={h1:.6})",
            drift
        );
    }

    #[test]
    fn test_physical_populations() {
        let sys = LotkaVolterraSystem::new();
        let mut solver = sys.create_solver(10.0, 5.0).unwrap();

        let (t, y) = solver.solve(10.0).unwrap();
        LotkaVolterraSystem::check_physical(&y, t).unwrap();
    }

    #[test]
    fn test_invalid_params() {
        assert!(LotkaVolterraSystem::with_params(-1.0, 0.4, 0.4, 0.1).is_err());
    }

    #[test]
    fn test_period_estimate() {
        let sys = LotkaVolterraSystem::new();
        let period = sys.estimated_period();
        // With α=1.1, γ=0.4: T ≈ 2π/√0.44 ≈ 9.47
        assert!(period > 5.0 && period < 20.0);
    }
}
