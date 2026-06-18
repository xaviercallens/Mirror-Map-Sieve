// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Agora Solvers
//!
//! Scientific solvers for the **SocrateAI Scientific Agora** — providing
//! rusty-SUNDIALS bridges for stiff ODE/DAE systems, physics validators,
//! and industrial simulation interfaces.
//!
//! ## Modules
//!
//! - [`sundials`] — CVODE implicit solver bridge, Robertson kinetics,
//!   Lorenz attractor, Lotka-Volterra dynamics, Navier-Stokes interface
//! - [`physics`] — Conservation law validators, boundary condition checks
//! - [`industrial`] — CFD and thermal analysis simulation interfaces
//!
//! ## Design Philosophy
//!
//! All solvers are memory-safe Rust wrappers around high-performance
//! numerical methods. The SUNDIALS bridge provides BDF/Adams methods
//! for stiff and non-stiff systems with adaptive step-size control.

pub mod sundials;
pub mod physics;
pub mod industrial;
