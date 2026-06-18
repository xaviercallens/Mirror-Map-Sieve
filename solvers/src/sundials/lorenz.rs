// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Lorenz Chaotic Attractor
//!
//! The Lorenz system — a classic example of deterministic chaos
//! arising from simplified atmospheric convection equations.
//!
//! ## System of ODEs
//!
//! ```text
//! dx/dt = σ(y - x)
//! dy/dt = x(ρ - z) - y
//! dz/dt = xy - βz
//! ```
//!
//! ## Standard Parameters
//!
//! - σ (sigma) = 10 — Prandtl number
//! - ρ (rho) = 28 — Rayleigh number
//! - β (beta) = 8/3 — geometric factor
//!
//! With these parameters, the system exhibits a strange attractor
//! with sensitive dependence on initial conditions (butterfly effect).

use super::cvode_bridge::{CVodeConfig, CVodeSolver, RhsFn, SolverMethod};
use thiserror::Error;

/// Errors from the Lorenz system.
#[derive(Debug, Error)]
pub enum LorenzError {
    /// Solver error.
    #[error("solver error: {0}")]
    SolverError(#[from] super::cvode_bridge::CVodeError),

    /// Solution diverged (numerical instability).
    #[error("solution diverged: |state| = {norm} at t = {t}")]
    Diverged { t: f64, norm: f64 },
}

/// Lorenz chaotic attractor system.
///
/// The strange attractor has fractal dimension ≈ 2.06 and the
/// largest Lyapunov exponent ≈ 0.9056.
#[derive(Debug, Clone)]
pub struct LorenzSystem {
    /// Prandtl number σ.
    pub sigma: f64,
    /// Rayleigh number ρ.
    pub rho: f64,
    /// Geometric factor β.
    pub beta: f64,
}

impl Default for LorenzSystem {
    fn default() -> Self {
        Self {
            sigma: 10.0,
            rho: 28.0,
            beta: 8.0 / 3.0,
        }
    }
}

impl LorenzSystem {
    /// Creates a Lorenz system with standard parameters (σ=10, ρ=28, β=8/3).
    pub fn new() -> Self {
        Self::default()
    }

    /// Creates a Lorenz system with custom parameters.
    pub fn with_params(sigma: f64, rho: f64, beta: f64) -> Self {
        Self { sigma, rho, beta }
    }

    /// Returns the right-hand side function for the CVODE solver.
    pub fn rhs_fn(&self) -> RhsFn {
        let sigma = self.sigma;
        let rho = self.rho;
        let beta = self.beta;

        Box::new(move |_t, y| {
            let x = y[0];
            let y_val = y[1];
            let z = y[2];

            let dx = sigma * (y_val - x);
            let dy = x * (rho - z) - y_val;
            let dz = x * y_val - beta * z;

            Ok(vec![dx, dy, dz])
        })
    }

    /// Returns standard initial conditions near the attractor.
    ///
    /// These are slightly off the unstable equilibrium to ensure
    /// the trajectory converges to the attractor.
    pub fn initial_conditions() -> Vec<f64> {
        vec![1.0, 1.0, 1.0]
    }

    /// Creates a CVODE solver configured for the Lorenz system.
    ///
    /// Uses Adams method since the system is non-stiff.
    pub fn create_solver(&self) -> Result<CVodeSolver, LorenzError> {
        let config = CVodeConfig {
            method: SolverMethod::Adams,
            rtol: 1e-8,
            atol: 1e-10,
            max_steps: 500_000,
            max_order: 5,
            initial_step: 0.001,
            min_step: 1e-15,
            max_step: 0.01,
        };

        let solver = CVodeSolver::new(
            config,
            Self::initial_conditions(),
            0.0,
            self.rhs_fn(),
        )?;

        Ok(solver)
    }

    /// Checks whether the solution has diverged.
    ///
    /// For the standard Lorenz attractor, the state should remain
    /// bounded: |x|, |y| < 30, |z| < 50 approximately.
    pub fn check_bounded(y: &[f64], t: f64) -> Result<(), LorenzError> {
        let norm = y.iter().map(|v| v * v).sum::<f64>().sqrt();
        if norm > 1000.0 {
            Err(LorenzError::Diverged { t, norm })
        } else {
            Ok(())
        }
    }

    /// Returns the equilibrium points of the system.
    ///
    /// For ρ > 1, there are three equilibria:
    /// - Origin: (0, 0, 0) — always unstable for ρ > 1
    /// - C⁺: (√(β(ρ-1)), √(β(ρ-1)), ρ-1) — unstable for standard params
    /// - C⁻: (-√(β(ρ-1)), -√(β(ρ-1)), ρ-1) — unstable for standard params
    pub fn equilibria(&self) -> Vec<[f64; 3]> {
        let mut eq = vec![[0.0, 0.0, 0.0]];

        if self.rho > 1.0 {
            let c = (self.beta * (self.rho - 1.0)).sqrt();
            eq.push([c, c, self.rho - 1.0]);
            eq.push([-c, -c, self.rho - 1.0]);
        }

        eq
    }

    /// Computes the energy-like quantity E = x² + y² + (z - σ - ρ)².
    ///
    /// This is not a conserved quantity but provides a measure
    /// of the state's distance from the attractor center.
    pub fn energy(y: &[f64], sigma: f64, rho: f64) -> f64 {
        let x = y[0];
        let yv = y[1];
        let z = y[2];
        x * x + yv * yv + (z - sigma - rho) * (z - sigma - rho)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rhs_at_origin() {
        let sys = LorenzSystem::new();
        let rhs = sys.rhs_fn();
        let dy = rhs(0.0, &[0.0, 0.0, 0.0]).unwrap();
        assert!((dy[0]).abs() < 1e-10);
        assert!((dy[1]).abs() < 1e-10);
        assert!((dy[2]).abs() < 1e-10);
    }

    #[test]
    fn test_equilibria() {
        let sys = LorenzSystem::new();
        let eq = sys.equilibria();
        assert_eq!(eq.len(), 3);
        // Check C+ equilibrium
        let c_plus = &eq[1];
        let expected_z = sys.rho - 1.0;
        assert!((c_plus[2] - expected_z).abs() < 1e-10);
    }

    #[test]
    fn test_solve_short_time() {
        let sys = LorenzSystem::new();
        let mut solver = sys.create_solver().unwrap();

        let (t, y) = solver.solve(1.0).unwrap();
        assert!((t - 1.0).abs() < 1e-6);

        // Solution should remain bounded
        LorenzSystem::check_bounded(&y, t).unwrap();
    }

    #[test]
    fn test_standard_params() {
        let sys = LorenzSystem::new();
        assert!((sys.sigma - 10.0).abs() < f64::EPSILON);
        assert!((sys.rho - 28.0).abs() < f64::EPSILON);
        assert!((sys.beta - 8.0 / 3.0).abs() < f64::EPSILON);
    }
}
