// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Kernel Interface
//!
//! Interface to the RunuX Rust OS kernel for edge AI deployment.
//! Provides task scheduling, SIMD tensor operations, and FFI bridge
//! abstractions targeting RISC-V and ARM architectures.

pub mod scheduler;
pub mod simd_ops;
pub mod ffi;

pub use scheduler::{TaskScheduler, TaskPriority, SchedulerConfig};
pub use simd_ops::SimdTensorOps;
pub use ffi::RunuXBridge;
