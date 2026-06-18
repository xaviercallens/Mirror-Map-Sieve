// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Memory Management
//!
//! Three-zone arena allocator with NUMA-aware pinning and thread-local
//! bump allocation for the SymBrain cognitive engine.
//!
//! ## Zones
//!
//! - **WeightZone** — Read-only memory-mapped region for frozen model weights
//! - **KVCacheZone** — Paged LRU cache with 64 KB pages for KV attention cache
//! - **ScratchZone** — Bump-allocated transient workspace for intermediate tensors

pub mod arena;
pub mod numa_pinning;
pub mod bump_allocator;

pub use arena::{ThreeZoneArena, WeightZone, KVCacheZone, ScratchZone, ArenaConfig};
pub use numa_pinning::{NumaPinning, HugePageConfig};
pub use bump_allocator::BumpAllocator;
