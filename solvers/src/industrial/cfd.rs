// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # CFD Simulation Interface
//!
//! High-level interface for Computational Fluid Dynamics simulations,
//! integrated with the Agora solver infrastructure and physics validators.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from CFD simulations.
#[derive(Debug, Error)]
pub enum CfdError {
    /// Invalid simulation configuration.
    #[error("invalid CFD config: {0}")]
    InvalidConfig(String),

    /// Solver diverged.
    #[error("CFD solver diverged at iteration {iteration}: residual = {residual:.2e}")]
    SolverDiverged { iteration: u64, residual: f64 },

    /// CFL condition violated.
    #[error("CFL = {cfl} exceeds limit {limit}")]
    CflViolation { cfl: f64, limit: f64 },
}

/// Turbulence model selection.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TurbulenceModel {
    /// Laminar (no turbulence model).
    Laminar,
    /// Spalart-Allmaras one-equation model.
    SpalartAllmaras,
    /// k-ε two-equation model.
    KEpsilon,
    /// k-ω SST model (recommended for general use).
    KOmegaSST,
    /// Large Eddy Simulation.
    LES,
}

/// CFD simulation configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CfdConfig {
    /// Grid dimensions (nx, ny, nz).
    pub grid_dims: (usize, usize, usize),
    /// Domain size (lx, ly, lz) in meters.
    pub domain_size: (f64, f64, f64),
    /// Kinematic viscosity (m²/s).
    pub viscosity: f64,
    /// Fluid density (kg/m³).
    pub density: f64,
    /// Inlet velocity (m/s).
    pub inlet_velocity: f64,
    /// Turbulence model.
    pub turbulence_model: TurbulenceModel,
    /// Maximum CFL number.
    pub cfl_limit: f64,
    /// Time step (0 for steady-state).
    pub dt: f64,
    /// Maximum solver iterations.
    pub max_iterations: u64,
    /// Convergence tolerance.
    pub tolerance: f64,
}

impl Default for CfdConfig {
    fn default() -> Self {
        Self {
            grid_dims: (64, 64, 1),
            domain_size: (1.0, 1.0, 0.1),
            viscosity: 1.5e-5,
            density: 1.225,
            inlet_velocity: 1.0,
            turbulence_model: TurbulenceModel::Laminar,
            cfl_limit: 1.0,
            dt: 0.0,
            max_iterations: 10_000,
            tolerance: 1e-6,
        }
    }
}

impl CfdConfig {
    /// Computes the Reynolds number based on domain length.
    pub fn reynolds_number(&self) -> f64 {
        self.inlet_velocity * self.domain_size.0 / self.viscosity
    }

    /// Computes the CFL number for a given time step.
    pub fn cfl_number(&self) -> f64 {
        if self.dt <= 0.0 {
            return 0.0;
        }
        let dx = self.domain_size.0 / self.grid_dims.0 as f64;
        self.inlet_velocity * self.dt / dx
    }

    /// Returns the total number of grid cells.
    pub fn total_cells(&self) -> usize {
        self.grid_dims.0 * self.grid_dims.1 * self.grid_dims.2
    }
}

/// CFD simulation result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CfdResult {
    /// Velocity field magnitude (flattened grid).
    pub velocity_magnitude: Vec<f64>,
    /// Pressure field (flattened grid).
    pub pressure: Vec<f64>,
    /// Final residual.
    pub residual: f64,
    /// Number of iterations.
    pub iterations: u64,
    /// Whether the solver converged.
    pub converged: bool,
    /// Computed drag coefficient (if applicable).
    pub drag_coefficient: Option<f64>,
    /// Computed lift coefficient (if applicable).
    pub lift_coefficient: Option<f64>,
}

/// CFD simulation engine.
///
/// Provides a high-level interface for setting up and running
/// CFD simulations with the Agora solver stack.
pub struct CfdSimulation {
    config: CfdConfig,
}

impl CfdSimulation {
    /// Creates a new CFD simulation.
    ///
    /// # Errors
    ///
    /// Returns [`CfdError::InvalidConfig`] if configuration is invalid.
    pub fn new(config: CfdConfig) -> Result<Self, CfdError> {
        if config.viscosity <= 0.0 {
            return Err(CfdError::InvalidConfig(
                "viscosity must be positive".to_string(),
            ));
        }
        if config.grid_dims.0 < 4 || config.grid_dims.1 < 4 {
            return Err(CfdError::InvalidConfig(
                "grid must be at least 4×4".to_string(),
            ));
        }

        let cfl = config.cfl_number();
        if cfl > config.cfl_limit {
            return Err(CfdError::CflViolation {
                cfl,
                limit: config.cfl_limit,
            });
        }

        Ok(Self { config })
    }

    /// Runs the CFD simulation.
    ///
    /// This is a placeholder that returns a zero-initialized result.
    /// In production, this would dispatch to the Navier-Stokes solver
    /// with the configured turbulence model.
    pub fn run(&self) -> Result<CfdResult, CfdError> {
        let n = self.config.total_cells();

        tracing::info!(
            re = self.config.reynolds_number(),
            cells = n,
            turbulence = ?self.config.turbulence_model,
            "starting CFD simulation"
        );

        Ok(CfdResult {
            velocity_magnitude: vec![0.0; n],
            pressure: vec![0.0; n],
            residual: 0.0,
            iterations: 0,
            converged: true,
            drag_coefficient: None,
            lift_coefficient: None,
        })
    }

    /// Returns the configuration.
    pub fn config(&self) -> &CfdConfig {
        &self.config
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reynolds_number() {
        let config = CfdConfig {
            inlet_velocity: 10.0,
            viscosity: 1e-5,
            domain_size: (1.0, 1.0, 0.1),
            ..Default::default()
        };
        assert!((config.reynolds_number() - 1e6).abs() < 1.0);
    }

    #[test]
    fn test_cfl_violation() {
        let config = CfdConfig {
            dt: 1.0, // very large time step
            inlet_velocity: 100.0,
            cfl_limit: 1.0,
            ..Default::default()
        };
        assert!(CfdSimulation::new(config).is_err());
    }

    #[test]
    fn test_run_simulation() {
        let sim = CfdSimulation::new(CfdConfig::default()).unwrap();
        let result = sim.run().unwrap();
        assert!(result.converged);
    }
}
