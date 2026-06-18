// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Physics Validators
//!
//! Conservation law validators and boundary condition checkers for
//! scientific simulations. Ensures mass, charge, and energy conservation
//! across solver time steps.

pub mod conservation;
pub mod boundary;

pub use conservation::{ConservationValidator, ConservationLaw, ConservationResult};
pub use boundary::{BoundaryCondition, BoundaryValidator, BoundaryKind};
