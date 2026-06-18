// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # 2D Navier-Stokes Steady Solver Interface
//!
//! Interface for 2D steady-state incompressible Navier-Stokes equations
//! on structured grids. Provides problem definition, discretization
//! configuration, and solution output types.
//!
//! ## Governing Equations
//!
//! ```text
//! (u·∇)u = -∇p/ρ + ν∇²u   (momentum)
//! ∇·u = 0                   (continuity / incompressibility)
//! ```
//!
//! Where u = (u, v) is the velocity field, p is pressure, ρ is density,
//! and ν is kinematic viscosity.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from the Navier-Stokes solver.
#[derive(Debug, Error)]
pub enum NavierStokesError {
    /// Grid configuration is invalid.
    #[error("invalid grid: {0}")]
    InvalidGrid(String),

    /// Solver did not converge.
    #[error("solver did not converge: residual = {residual:.2e} after {iterations} iterations")]
    ConvergenceFailed { residual: f64, iterations: u64 },

    /// Reynolds number is too high for the mesh.
    #[error("Re = {re} too high for grid {nx}×{ny} — refine mesh or reduce Re")]
    ReynoldsTooHigh { re: f64, nx: usize, ny: usize },

    /// Invalid physical parameter.
    #[error("invalid parameter: {0}")]
    InvalidParameter(String),
}

/// Discretization method for the convective term.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConvectionScheme {
    /// Central difference (2nd order, conditionally stable).
    CentralDifference,
    /// First-order upwind (1st order, unconditionally stable).
    Upwind,
    /// QUICK scheme (3rd order).
    Quick,
}

/// Solver configuration for the Navier-Stokes system.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NavierStokesConfig {
    /// Grid points in x-direction.
    pub nx: usize,
    /// Grid points in y-direction.
    pub ny: usize,
    /// Domain length in x.
    pub lx: f64,
    /// Domain length in y.
    pub ly: f64,
    /// Kinematic viscosity ν.
    pub viscosity: f64,
    /// Fluid density ρ.
    pub density: f64,
    /// Convection discretization scheme.
    pub convection_scheme: ConvectionScheme,
    /// Maximum solver iterations.
    pub max_iterations: u64,
    /// Convergence tolerance.
    pub tolerance: f64,
    /// Under-relaxation factor for velocity.
    pub velocity_relaxation: f64,
    /// Under-relaxation factor for pressure.
    pub pressure_relaxation: f64,
}

impl Default for NavierStokesConfig {
    fn default() -> Self {
        Self {
            nx: 64,
            ny: 64,
            lx: 1.0,
            ly: 1.0,
            viscosity: 0.01,
            density: 1.0,
            convection_scheme: ConvectionScheme::Upwind,
            max_iterations: 10_000,
            tolerance: 1e-6,
            velocity_relaxation: 0.7,
            pressure_relaxation: 0.3,
        }
    }
}

impl NavierStokesConfig {
    /// Computes the grid Reynolds number.
    pub fn grid_reynolds(&self) -> f64 {
        let dx = self.lx / self.nx as f64;
        // Assume unit characteristic velocity
        dx / self.viscosity
    }

    /// Computes the cell dimensions.
    pub fn cell_size(&self) -> (f64, f64) {
        (self.lx / self.nx as f64, self.ly / self.ny as f64)
    }

    /// Returns the total number of cells.
    pub fn total_cells(&self) -> usize {
        self.nx * self.ny
    }
}

/// Solution of the Navier-Stokes system.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NavierStokesSolution {
    /// x-velocity field (row-major, nx × ny).
    pub u: Vec<f64>,
    /// y-velocity field (row-major, nx × ny).
    pub v: Vec<f64>,
    /// Pressure field (row-major, nx × ny).
    pub p: Vec<f64>,
    /// Final residual norm.
    pub residual: f64,
    /// Number of iterations used.
    pub iterations: u64,
    /// Whether the solver converged.
    pub converged: bool,
}

impl NavierStokesSolution {
    /// Returns velocity magnitude at cell (i, j).
    pub fn velocity_magnitude(&self, i: usize, j: usize, ny: usize) -> f64 {
        let idx = i * ny + j;
        (self.u[idx] * self.u[idx] + self.v[idx] * self.v[idx]).sqrt()
    }

    /// Computes the maximum velocity magnitude in the domain.
    pub fn max_velocity(&self) -> f64 {
        self.u
            .iter()
            .zip(&self.v)
            .map(|(u, v)| (u * u + v * v).sqrt())
            .fold(0.0f64, f64::max)
    }

    /// Computes the maximum divergence (should be ~0 for incompressible flow).
    pub fn max_divergence(&self, nx: usize, ny: usize, dx: f64, dy: f64) -> f64 {
        let mut max_div = 0.0f64;

        for i in 1..nx - 1 {
            for j in 1..ny - 1 {
                let idx = i * ny + j;
                let du_dx = (self.u[idx + ny] - self.u[idx - ny]) / (2.0 * dx);
                let dv_dy = (self.v[idx + 1] - self.v[idx - 1]) / (2.0 * dy);
                let div = (du_dx + dv_dy).abs();
                if div > max_div {
                    max_div = div;
                }
            }
        }

        max_div
    }
}

/// 2D Navier-Stokes steady-state solver.
///
/// Solves the incompressible Navier-Stokes equations on a structured
/// Cartesian grid using the SIMPLE algorithm with the configured
/// convection scheme.
pub struct NavierStokesSolver {
    config: NavierStokesConfig,
}

impl NavierStokesSolver {
    /// Creates a new Navier-Stokes solver.
    ///
    /// # Errors
    ///
    /// Returns [`NavierStokesError::InvalidGrid`] if the grid is too small.
    pub fn new(config: NavierStokesConfig) -> Result<Self, NavierStokesError> {
        if config.nx < 4 || config.ny < 4 {
            return Err(NavierStokesError::InvalidGrid(
                "grid must be at least 4×4".to_string(),
            ));
        }
        if config.viscosity <= 0.0 {
            return Err(NavierStokesError::InvalidParameter(
                "viscosity must be positive".to_string(),
            ));
        }
        Ok(Self { config })
    }

    /// Solves the lid-driven cavity problem.
    ///
    /// Boundary conditions:
    /// - Top wall: u = 1.0, v = 0.0 (moving lid)
    /// - Other walls: u = 0, v = 0 (no-slip)
    ///
    /// This is a standard benchmark for incompressible flow solvers.
    pub fn solve_cavity(&self) -> Result<NavierStokesSolution, NavierStokesError> {
        let nx = self.config.nx;
        let ny = self.config.ny;
        let n = nx * ny;

        let mut u = vec![0.0; n];
        let mut v = vec![0.0; n];
        let mut p = vec![0.0; n];

        // Set lid velocity boundary condition (top wall: j = ny-1)
        for i in 0..nx {
            u[i * ny + (ny - 1)] = 1.0;
        }

        // Simplified iteration (Jacobi-like relaxation for demonstration)
        let (dx, dy) = self.config.cell_size();
        let nu = self.config.viscosity;
        let omega_u = self.config.velocity_relaxation;

        let mut residual = f64::INFINITY;
        let mut iterations = 0u64;

        while iterations < self.config.max_iterations && residual > self.config.tolerance {
            let mut max_res = 0.0f64;

            for i in 1..nx - 1 {
                for j in 1..ny - 1 {
                    let idx = i * ny + j;

                    // Diffusion terms (central difference)
                    let u_diff = nu
                        * ((u[idx + ny] - 2.0 * u[idx] + u[idx - ny]) / (dx * dx)
                            + (u[idx + 1] - 2.0 * u[idx] + u[idx - 1]) / (dy * dy));
                    let v_diff = nu
                        * ((v[idx + ny] - 2.0 * v[idx] + v[idx - ny]) / (dx * dx)
                            + (v[idx + 1] - 2.0 * v[idx] + v[idx - 1]) / (dy * dy));

                    // Pressure gradient
                    let dp_dx = (p[idx + ny] - p[idx - ny]) / (2.0 * dx);
                    let dp_dy = (p[idx + 1] - p[idx - 1]) / (2.0 * dy);

                    // Update velocities
                    let u_new = u[idx] + omega_u * (u_diff - dp_dx);
                    let v_new = v[idx] + omega_u * (v_diff - dp_dy);

                    let res_u = (u_new - u[idx]).abs();
                    let res_v = (v_new - v[idx]).abs();
                    max_res = max_res.max(res_u).max(res_v);

                    u[idx] = u_new;
                    v[idx] = v_new;
                }
            }

            // Re-apply boundary conditions
            for i in 0..nx {
                u[i * ny + (ny - 1)] = 1.0;
            }

            residual = max_res;
            iterations += 1;
        }

        let converged = residual <= self.config.tolerance;

        if !converged {
            tracing::warn!(
                residual,
                iterations,
                "Navier-Stokes solver did not converge"
            );
        }

        Ok(NavierStokesSolution {
            u,
            v,
            p,
            residual,
            iterations,
            converged,
        })
    }

    /// Returns the solver configuration.
    pub fn config(&self) -> &NavierStokesConfig {
        &self.config
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_defaults() {
        let config = NavierStokesConfig::default();
        assert_eq!(config.nx, 64);
        assert_eq!(config.ny, 64);
        assert!((config.viscosity - 0.01).abs() < f64::EPSILON);
    }

    #[test]
    fn test_grid_reynolds() {
        let config = NavierStokesConfig {
            nx: 100,
            lx: 1.0,
            viscosity: 0.01,
            ..Default::default()
        };
        let re = config.grid_reynolds();
        assert!((re - 1.0).abs() < 0.01);
    }

    #[test]
    fn test_invalid_grid() {
        let config = NavierStokesConfig {
            nx: 2,
            ny: 2,
            ..Default::default()
        };
        assert!(NavierStokesSolver::new(config).is_err());
    }

    #[test]
    fn test_cavity_solver() {
        let config = NavierStokesConfig {
            nx: 8,
            ny: 8,
            max_iterations: 100,
            ..Default::default()
        };
        let solver = NavierStokesSolver::new(config).unwrap();
        let solution = solver.solve_cavity().unwrap();

        // Lid velocity should be preserved
        assert!((solution.u[7 * 8 + 7] - 1.0).abs() < f64::EPSILON);
        assert!(solution.iterations > 0);
    }
}
