// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Thermal Analysis Interface
//!
//! High-level interface for thermal simulation and heat transfer analysis,
//! integrated with the Agora solver infrastructure.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from thermal simulations.
#[derive(Debug, Error)]
pub enum ThermalError {
    /// Invalid simulation configuration.
    #[error("invalid thermal config: {0}")]
    InvalidConfig(String),

    /// Solver diverged.
    #[error("thermal solver diverged: max temperature = {max_temp:.1} K")]
    SolverDiverged { max_temp: f64 },

    /// Temperature exceeds material limits.
    #[error("temperature {temp:.1} K exceeds material limit {limit:.1} K")]
    MaterialLimitExceeded { temp: f64, limit: f64 },
}

/// Heat transfer modes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum HeatTransferMode {
    /// Pure conduction (Fourier's law).
    Conduction,
    /// Forced convection.
    ForcedConvection,
    /// Natural convection.
    NaturalConvection,
    /// Combined conduction + convection.
    Conjugate,
    /// Radiation (Stefan-Boltzmann).
    Radiation,
}

/// Material thermal properties.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalMaterial {
    /// Material name.
    pub name: String,
    /// Thermal conductivity k (W/(m·K)).
    pub conductivity: f64,
    /// Specific heat capacity cp (J/(kg·K)).
    pub specific_heat: f64,
    /// Density ρ (kg/m³).
    pub density: f64,
    /// Maximum operating temperature (K).
    pub max_temperature: f64,
    /// Emissivity ε (0–1, for radiation).
    pub emissivity: f64,
}

impl ThermalMaterial {
    /// Thermal diffusivity α = k / (ρ·cp) in m²/s.
    pub fn diffusivity(&self) -> f64 {
        self.conductivity / (self.density * self.specific_heat)
    }

    /// Creates a standard copper material.
    pub fn copper() -> Self {
        Self {
            name: "Copper".to_string(),
            conductivity: 401.0,
            specific_heat: 385.0,
            density: 8960.0,
            max_temperature: 1358.0, // melting point
            emissivity: 0.07,
        }
    }

    /// Creates a standard aluminum material.
    pub fn aluminum() -> Self {
        Self {
            name: "Aluminum".to_string(),
            conductivity: 237.0,
            specific_heat: 897.0,
            density: 2700.0,
            max_temperature: 933.0,
            emissivity: 0.09,
        }
    }

    /// Creates a standard silicon material (for chip thermal analysis).
    pub fn silicon() -> Self {
        Self {
            name: "Silicon".to_string(),
            conductivity: 149.0,
            specific_heat: 710.0,
            density: 2330.0,
            max_temperature: 1687.0,
            emissivity: 0.65,
        }
    }
}

/// Thermal simulation configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalConfig {
    /// Grid dimensions (nx, ny, nz).
    pub grid_dims: (usize, usize, usize),
    /// Domain size (lx, ly, lz) in meters.
    pub domain_size: (f64, f64, f64),
    /// Material properties.
    pub material: ThermalMaterial,
    /// Heat transfer mode.
    pub mode: HeatTransferMode,
    /// Ambient temperature (K).
    pub ambient_temperature: f64,
    /// Heat source power (W).
    pub heat_source_power: f64,
    /// Convective heat transfer coefficient h (W/(m²·K)).
    pub convective_coefficient: f64,
    /// Maximum solver iterations.
    pub max_iterations: u64,
    /// Convergence tolerance.
    pub tolerance: f64,
    /// Whether to run steady-state (true) or transient (false).
    pub steady_state: bool,
    /// Time step for transient simulation (s).
    pub dt: f64,
    /// Total simulation time (s).
    pub total_time: f64,
}

impl Default for ThermalConfig {
    fn default() -> Self {
        Self {
            grid_dims: (32, 32, 1),
            domain_size: (0.1, 0.1, 0.01),
            material: ThermalMaterial::silicon(),
            mode: HeatTransferMode::Conduction,
            ambient_temperature: 300.0, // 27°C
            heat_source_power: 10.0,    // 10 W
            convective_coefficient: 25.0,
            max_iterations: 10_000,
            tolerance: 1e-6,
            steady_state: true,
            dt: 0.01,
            total_time: 1.0,
        }
    }
}

/// Thermal simulation result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalResult {
    /// Temperature field (flattened grid) in Kelvin.
    pub temperature: Vec<f64>,
    /// Maximum temperature in the domain (K).
    pub max_temperature: f64,
    /// Minimum temperature in the domain (K).
    pub min_temperature: f64,
    /// Mean temperature (K).
    pub mean_temperature: f64,
    /// Total heat flux (W).
    pub total_heat_flux: f64,
    /// Number of iterations.
    pub iterations: u64,
    /// Final residual.
    pub residual: f64,
    /// Whether the solver converged.
    pub converged: bool,
}

/// Thermal analysis simulation engine.
pub struct ThermalSimulation {
    config: ThermalConfig,
}

impl ThermalSimulation {
    /// Creates a new thermal simulation.
    ///
    /// # Errors
    ///
    /// Returns [`ThermalError::InvalidConfig`] if configuration is invalid.
    pub fn new(config: ThermalConfig) -> Result<Self, ThermalError> {
        if config.material.conductivity <= 0.0 {
            return Err(ThermalError::InvalidConfig(
                "thermal conductivity must be positive".to_string(),
            ));
        }
        if config.ambient_temperature <= 0.0 {
            return Err(ThermalError::InvalidConfig(
                "ambient temperature must be positive (Kelvin)".to_string(),
            ));
        }
        if config.grid_dims.0 < 2 || config.grid_dims.1 < 2 {
            return Err(ThermalError::InvalidConfig(
                "grid must be at least 2×2".to_string(),
            ));
        }

        Ok(Self { config })
    }

    /// Runs the thermal simulation.
    ///
    /// Solves the heat equation:
    /// ```text
    /// ρ·cp·∂T/∂t = k·∇²T + Q  (transient)
    /// k·∇²T + Q = 0            (steady-state)
    /// ```
    pub fn run(&self) -> Result<ThermalResult, ThermalError> {
        let n = self.config.grid_dims.0 * self.config.grid_dims.1 * self.config.grid_dims.2.max(1);
        let t_ambient = self.config.ambient_temperature;

        tracing::info!(
            cells = n,
            mode = ?self.config.mode,
            material = &self.config.material.name,
            "starting thermal simulation"
        );

        // Initialize temperature field to ambient
        let mut temperature = vec![t_ambient; n];

        // Apply heat source to center cells
        let nx = self.config.grid_dims.0;
        let ny = self.config.grid_dims.1;
        let cx = nx / 2;
        let cy = ny / 2;

        // Simplified steady-state solver (Jacobi iteration)
        let k = self.config.material.conductivity;
        let dx = self.config.domain_size.0 / nx as f64;
        let dy = self.config.domain_size.1 / ny as f64;
        let q_vol = self.config.heat_source_power / (dx * dy * self.config.domain_size.2.max(0.001));

        let mut residual = f64::INFINITY;
        let mut iterations = 0u64;

        while iterations < self.config.max_iterations && residual > self.config.tolerance {
            let mut max_res = 0.0f64;
            let old_temp = temperature.clone();

            for i in 1..nx - 1 {
                for j in 1..ny - 1 {
                    let idx = i * ny + j;

                    let laplacian = (old_temp[idx + ny] + old_temp[idx - ny] - 2.0 * old_temp[idx])
                        / (dx * dx)
                        + (old_temp[idx + 1] + old_temp[idx - 1] - 2.0 * old_temp[idx])
                            / (dy * dy);

                    // Heat source at center
                    let source = if (i as isize - cx as isize).unsigned_abs() <= 2
                        && (j as isize - cy as isize).unsigned_abs() <= 2
                    {
                        q_vol / k
                    } else {
                        0.0
                    };

                    let t_new = old_temp[idx] + 0.25 * (k * laplacian / k + source) * dx * dx;
                    let change = (t_new - old_temp[idx]).abs();
                    if change > max_res {
                        max_res = change;
                    }
                    temperature[idx] = t_new;
                }
            }

            residual = max_res;
            iterations += 1;
        }

        let max_temperature = temperature.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let min_temperature = temperature.iter().cloned().fold(f64::INFINITY, f64::min);
        let mean_temperature = temperature.iter().sum::<f64>() / n as f64;

        // Check material limits
        if max_temperature > self.config.material.max_temperature {
            tracing::warn!(
                max_temp = max_temperature,
                limit = self.config.material.max_temperature,
                "temperature exceeds material limit"
            );
        }

        let converged = residual <= self.config.tolerance;

        Ok(ThermalResult {
            temperature,
            max_temperature,
            min_temperature,
            mean_temperature,
            total_heat_flux: self.config.heat_source_power,
            iterations,
            residual,
            converged,
        })
    }

    /// Returns the Biot number: Bi = h·L/k.
    ///
    /// Bi < 0.1 indicates lumped capacitance model is valid.
    pub fn biot_number(&self) -> f64 {
        let l = self.config.domain_size.2.max(0.001); // characteristic length
        self.config.convective_coefficient * l / self.config.material.conductivity
    }

    /// Returns the configuration.
    pub fn config(&self) -> &ThermalConfig {
        &self.config
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_material_diffusivity() {
        let cu = ThermalMaterial::copper();
        let alpha = cu.diffusivity();
        // Copper: α ≈ 1.16e-4 m²/s
        assert!(alpha > 1e-5 && alpha < 1e-3);
    }

    #[test]
    fn test_thermal_simulation() {
        let config = ThermalConfig {
            grid_dims: (8, 8, 1),
            max_iterations: 100,
            ..Default::default()
        };
        let sim = ThermalSimulation::new(config).unwrap();
        let result = sim.run().unwrap();

        assert!(result.max_temperature >= result.min_temperature);
        assert!(result.iterations > 0);
    }

    #[test]
    fn test_biot_number() {
        let sim = ThermalSimulation::new(ThermalConfig::default()).unwrap();
        let bi = sim.biot_number();
        assert!(bi > 0.0);
    }

    #[test]
    fn test_invalid_config() {
        let config = ThermalConfig {
            ambient_temperature: -10.0,
            ..Default::default()
        };
        assert!(ThermalSimulation::new(config).is_err());
    }
}
