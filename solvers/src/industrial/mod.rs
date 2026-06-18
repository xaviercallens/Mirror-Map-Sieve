// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Industrial Simulation Interfaces
//!
//! High-level interfaces for Computational Fluid Dynamics (CFD) and
//! thermal analysis simulations, integrated with the Agora solver
//! infrastructure and physics validators.

pub mod cfd;
pub mod thermal;

pub use cfd::{CfdSimulation, CfdConfig, CfdResult};
pub use thermal::{ThermalSimulation, ThermalConfig, ThermalResult};
