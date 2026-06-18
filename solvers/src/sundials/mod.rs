// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # SUNDIALS Solver Bridges
//!
//! Memory-safe Rust bridges to SUNDIALS stiff ODE/DAE solvers. Provides
//! the CVODE implicit solver with BDF method, plus reference implementations
//! of classical stiff and chaotic systems:
//!
//! - **Robertson** — Stiff chemical kinetics (3-species, span 10¹¹)
//! - **Lorenz** — Chaotic attractor (σ=10, ρ=28, β=8/3)
//! - **Lotka-Volterra** — Predator-prey population dynamics
//! - **Navier-Stokes** — 2D steady-state solver interface

pub mod cvode_bridge;
pub mod robertson;
pub mod lorenz;
pub mod lotka_volterra;
pub mod navier_stokes;

pub use cvode_bridge::{CVodeSolver, CVodeConfig, SolverStats};
pub use robertson::RobertsonSystem;
pub use lorenz::LorenzSystem;
pub use lotka_volterra::LotkaVolterraSystem;
pub use navier_stokes::NavierStokesSolver;
