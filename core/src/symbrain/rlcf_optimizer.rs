// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Ricci-Lévy Curvature Flow Optimizer
//!
//! Weight optimizer based on Ricci curvature flow with Lévy α-stable
//! stochastic perturbation. Uses a Newton step with Preconditioned
//! Conjugate Gradient (PCG) Hessian solver (max 5 CG iterations).
//!
//! ## Mathematical Formulation
//!
//! ```text
//! θ_{t+1} = θ_t - η H⁻¹ ∇L(θ_t) + σ_t ⊙ dZ_t
//! ```
//!
//! Where:
//! - H⁻¹ is approximated via PCG with Jacobi diagonal preconditioner
//! - dZ_t is a Lévy α-stable random variable (α = 1.8)
//! - σ_t is the PFC modulation vector from the routing tensor
//!
//! The Lévy noise enables escape from sharp local minima while the
//! curvature-aware Newton step provides fast local convergence.

use rand::Rng;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from the RLCF optimizer.
#[derive(Debug, Error)]
pub enum RLCFError {
    /// Gradient vector has wrong dimension.
    #[error("dimension mismatch: expected {expected}, got {got}")]
    DimensionMismatch { expected: usize, got: usize },

    /// PCG solver failed to converge.
    #[error("PCG solver did not converge in {0} iterations")]
    PCGNotConverged(usize),

    /// Invalid configuration parameter.
    #[error("invalid config: {0}")]
    InvalidConfig(String),
}

/// Configuration for the RLCF optimizer.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RLCFConfig {
    /// Learning rate η.
    pub learning_rate: f64,
    /// Lévy stability parameter α ∈ (0, 2]. Default: 1.8.
    pub levy_alpha: f64,
    /// Lévy scale parameter γ. Default: 0.01.
    pub levy_scale: f64,
    /// Maximum PCG iterations. Default: 5.
    pub max_pcg_iters: usize,
    /// PCG convergence tolerance. Default: 1e-6.
    pub pcg_tolerance: f64,
    /// Dimension of the parameter space.
    pub dimension: usize,
}

impl Default for RLCFConfig {
    fn default() -> Self {
        Self {
            learning_rate: 0.001,
            levy_alpha: 1.8,
            levy_scale: 0.01,
            max_pcg_iters: 5,
            pcg_tolerance: 1e-6,
            dimension: 64,
        }
    }
}

/// A single RLCF update step containing the parameter delta.
#[derive(Debug, Clone)]
pub struct UpdateStep {
    /// Newton direction (H⁻¹ ∇L).
    pub newton_direction: Vec<f64>,
    /// Lévy noise term (σ_t ⊙ dZ_t).
    pub levy_noise: Vec<f64>,
    /// Final parameter update (combined).
    pub delta: Vec<f64>,
    /// Number of PCG iterations used.
    pub pcg_iterations: usize,
    /// PCG residual norm at termination.
    pub pcg_residual: f64,
}

/// Ricci-Lévy Curvature Flow Optimizer.
///
/// Combines second-order curvature information with Lévy-flight stochastic
/// exploration for robust optimization on complex loss landscapes.
#[derive(Debug)]
pub struct RLCFOptimizer {
    config: RLCFConfig,
    /// Diagonal Hessian approximation (Jacobi preconditioner).
    hessian_diag: Vec<f64>,
    /// Current parameter vector.
    params: Vec<f64>,
    /// Step counter.
    step_count: u64,
}

impl RLCFOptimizer {
    /// Creates a new RLCF optimizer with the given configuration.
    ///
    /// # Errors
    ///
    /// Returns [`RLCFError::InvalidConfig`] if parameters are out of range.
    pub fn new(config: RLCFConfig) -> Result<Self, RLCFError> {
        if config.levy_alpha <= 0.0 || config.levy_alpha > 2.0 {
            return Err(RLCFError::InvalidConfig(format!(
                "levy_alpha must be in (0, 2], got {}",
                config.levy_alpha
            )));
        }
        if config.dimension == 0 {
            return Err(RLCFError::InvalidConfig(
                "dimension must be > 0".to_string(),
            ));
        }

        let dim = config.dimension;
        Ok(Self {
            config,
            hessian_diag: vec![1.0; dim],
            params: vec![0.0; dim],
            step_count: 0,
        })
    }

    /// Returns the current parameter vector.
    pub fn params(&self) -> &[f64] {
        &self.params
    }

    /// Sets the current parameter vector.
    ///
    /// # Errors
    ///
    /// Returns [`RLCFError::DimensionMismatch`] if dimensions don't match.
    pub fn set_params(&mut self, params: Vec<f64>) -> Result<(), RLCFError> {
        if params.len() != self.config.dimension {
            return Err(RLCFError::DimensionMismatch {
                expected: self.config.dimension,
                got: params.len(),
            });
        }
        self.params = params;
        Ok(())
    }

    /// Updates the diagonal Hessian approximation (Jacobi preconditioner).
    ///
    /// # Errors
    ///
    /// Returns [`RLCFError::DimensionMismatch`] if dimensions don't match.
    pub fn update_hessian_diag(&mut self, diag: Vec<f64>) -> Result<(), RLCFError> {
        if diag.len() != self.config.dimension {
            return Err(RLCFError::DimensionMismatch {
                expected: self.config.dimension,
                got: diag.len(),
            });
        }
        self.hessian_diag = diag;
        Ok(())
    }

    /// Performs one RLCF update step.
    ///
    /// Computes: `θ_{t+1} = θ_t - η H⁻¹ ∇L + σ_t ⊙ dZ_t`
    ///
    /// # Arguments
    ///
    /// * `gradient` — ∇L(θ_t), the loss gradient at current parameters
    /// * `pfc_modulation` — σ_t, the PFC routing modulation vector
    ///
    /// # Errors
    ///
    /// Returns [`RLCFError::DimensionMismatch`] on dimension mismatch.
    pub fn step(
        &mut self,
        gradient: &[f64],
        pfc_modulation: &[f64],
    ) -> Result<UpdateStep, RLCFError> {
        let dim = self.config.dimension;

        if gradient.len() != dim {
            return Err(RLCFError::DimensionMismatch {
                expected: dim,
                got: gradient.len(),
            });
        }
        if pfc_modulation.len() != dim {
            return Err(RLCFError::DimensionMismatch {
                expected: dim,
                got: pfc_modulation.len(),
            });
        }

        // PCG solve: H⁻¹ ∇L with Jacobi preconditioner
        let (newton_dir, pcg_iters, pcg_residual) =
            self.pcg_solve(gradient)?;

        // Lévy α-stable noise: dZ_t
        let levy = self.sample_levy_noise();

        // PFC modulation: σ_t ⊙ dZ_t
        let modulated_noise: Vec<f64> = pfc_modulation
            .iter()
            .zip(levy.iter())
            .map(|(s, z)| s * z)
            .collect();

        // Full update: -η * newton_dir + noise
        let eta = self.config.learning_rate;
        let delta: Vec<f64> = newton_dir
            .iter()
            .zip(modulated_noise.iter())
            .map(|(n, noise)| -eta * n + noise)
            .collect();

        // Apply update
        for (p, d) in self.params.iter_mut().zip(delta.iter()) {
            *p += d;
        }
        self.step_count += 1;

        Ok(UpdateStep {
            newton_direction: newton_dir,
            levy_noise: modulated_noise,
            delta,
            pcg_iterations: pcg_iters,
            pcg_residual,
        })
    }

    /// Returns the number of optimization steps taken.
    pub fn step_count(&self) -> u64 {
        self.step_count
    }

    /// PCG solve with Jacobi diagonal preconditioner.
    ///
    /// Solves H x = b where H is approximated by its diagonal.
    /// Limited to `max_pcg_iters` iterations.
    fn pcg_solve(&self, rhs: &[f64]) -> Result<(Vec<f64>, usize, f64), RLCFError> {
        let dim = self.config.dimension;
        let max_iter = self.config.max_pcg_iters;
        let tol = self.config.pcg_tolerance;

        // Initial guess x = 0
        let mut x = vec![0.0; dim];
        // r = b - H*x = b (since x=0)
        let mut r: Vec<f64> = rhs.to_vec();
        // Preconditioner: M = diag(H), so M⁻¹ r = r / diag(H)
        let mut z: Vec<f64> = r
            .iter()
            .zip(self.hessian_diag.iter())
            .map(|(ri, hi)| {
                let h = if hi.abs() < 1e-12 { 1.0 } else { *hi };
                ri / h
            })
            .collect();
        let mut p = z.clone();
        let mut rz_dot: f64 = r.iter().zip(z.iter()).map(|(a, b)| a * b).sum();

        let mut iters = 0;
        let mut residual = r.iter().map(|v| v * v).sum::<f64>().sqrt();

        for _ in 0..max_iter {
            if residual < tol {
                break;
            }

            // H*p ≈ diag(H) * p (diagonal approximation)
            let hp: Vec<f64> = p
                .iter()
                .zip(self.hessian_diag.iter())
                .map(|(pi, hi)| pi * hi)
                .collect();

            let p_hp: f64 = p.iter().zip(hp.iter()).map(|(a, b)| a * b).sum();
            if p_hp.abs() < 1e-30 {
                break;
            }

            let alpha = rz_dot / p_hp;

            for i in 0..dim {
                x[i] += alpha * p[i];
                r[i] -= alpha * hp[i];
            }

            // Update preconditioned residual
            z = r
                .iter()
                .zip(self.hessian_diag.iter())
                .map(|(ri, hi)| {
                    let h = if hi.abs() < 1e-12 { 1.0 } else { *hi };
                    ri / h
                })
                .collect();

            let rz_dot_new: f64 = r.iter().zip(z.iter()).map(|(a, b)| a * b).sum();
            let beta = rz_dot_new / rz_dot.max(1e-30);
            rz_dot = rz_dot_new;

            for i in 0..dim {
                p[i] = z[i] + beta * p[i];
            }

            residual = r.iter().map(|v| v * v).sum::<f64>().sqrt();
            iters += 1;
        }

        Ok((x, iters, residual))
    }

    /// Samples Lévy α-stable noise using Chambers-Mallows-Stuck method.
    ///
    /// For α = 1.8, this produces heavy-tailed noise that enables
    /// escape from sharp local minima (Lévy flights).
    fn sample_levy_noise(&self) -> Vec<f64> {
        let mut rng = rand::thread_rng();
        let alpha = self.config.levy_alpha;
        let scale = self.config.levy_scale;

        (0..self.config.dimension)
            .map(|_| {
                // Chambers-Mallows-Stuck algorithm
                let u: f64 = rng.gen_range(-std::f64::consts::FRAC_PI_2..std::f64::consts::FRAC_PI_2);
                let w: f64 = -rng.r#gen::<f64>().ln(); // Exponential(1)

                if (alpha - 1.0).abs() < 1e-10 {
                    // Cauchy case
                    u.tan() * scale
                } else {
                    let inv_alpha = 1.0 / alpha;
                    let factor = (std::f64::consts::FRAC_PI_2 * alpha).cos().powf(inv_alpha);
                    let s = ((alpha * u).sin() / u.cos().powf(inv_alpha))
                        * (((1.0 - alpha) * u).cos() / w).powf((1.0 - alpha) * inv_alpha);
                    s * scale / factor
                }
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_defaults() {
        let cfg = RLCFConfig::default();
        assert!((cfg.levy_alpha - 1.8).abs() < f64::EPSILON);
        assert_eq!(cfg.max_pcg_iters, 5);
    }

    #[test]
    fn test_invalid_alpha() {
        let cfg = RLCFConfig {
            levy_alpha: 3.0,
            ..Default::default()
        };
        assert!(RLCFOptimizer::new(cfg).is_err());
    }

    #[test]
    fn test_dimension_mismatch() {
        let mut opt = RLCFOptimizer::new(RLCFConfig::default()).unwrap();
        let bad_grad = vec![0.0; 10]; // wrong dimension
        let modulation = vec![1.0; 64];
        assert!(opt.step(&bad_grad, &modulation).is_err());
    }

    #[test]
    fn test_step_produces_update() {
        let mut opt = RLCFOptimizer::new(RLCFConfig {
            dimension: 4,
            ..Default::default()
        })
        .unwrap();

        let gradient = vec![1.0, -0.5, 0.3, 0.0];
        let modulation = vec![0.5, 0.5, 0.5, 0.5];
        let step = opt.step(&gradient, &modulation).unwrap();

        assert_eq!(step.delta.len(), 4);
        assert_eq!(opt.step_count(), 1);
    }

    #[test]
    fn test_pcg_converges_on_identity() {
        let opt = RLCFOptimizer::new(RLCFConfig {
            dimension: 4,
            ..Default::default()
        })
        .unwrap();

        // With identity Hessian, PCG should return the RHS directly
        let rhs = vec![1.0, 2.0, 3.0, 4.0];
        let (solution, _, residual) = opt.pcg_solve(&rhs).unwrap();

        for (s, r) in solution.iter().zip(rhs.iter()) {
            assert!((s - r).abs() < 1e-4, "expected {r}, got {s}");
        }
        assert!(residual < 1e-4);
    }
}
