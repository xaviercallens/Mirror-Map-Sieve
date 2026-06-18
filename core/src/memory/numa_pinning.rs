// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # NUMA-Aware Allocation
//!
//! Stubs for NUMA-aware memory allocation with 2 MB huge page alignment.
//! On platforms without NUMA support, these functions fall back to
//! standard aligned allocation.
//!
//! ## Design
//!
//! In production RunuX kernel deployment, these functions call into the
//! kernel's NUMA allocator via FFI. This module provides the interface
//! and a portable fallback implementation.
//!
//! ## Huge Pages
//!
//! All allocations use 2 MB (2^21 byte) alignment to leverage transparent
//! huge pages (THP) or explicit hugetlbfs mappings, reducing TLB pressure
//! for large weight tensors.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Huge page size: 2 MB.
pub const HUGE_PAGE_SIZE: usize = 2 * 1024 * 1024;

/// Huge page alignment: 2 MB.
pub const HUGE_PAGE_ALIGN: usize = HUGE_PAGE_SIZE;

/// Errors from NUMA allocation.
#[derive(Debug, Error)]
pub enum NumaError {
    /// Requested NUMA node does not exist.
    #[error("NUMA node {0} does not exist (max: {1})")]
    InvalidNode(usize, usize),

    /// Allocation failed.
    #[error("NUMA allocation failed: {0} bytes on node {1}")]
    AllocationFailed(usize, usize),

    /// Huge page allocation is not supported on this platform.
    #[error("huge page allocation not supported on this platform")]
    HugePagesUnsupported,
}

/// Configuration for huge page allocation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HugePageConfig {
    /// Page size in bytes (default: 2 MB).
    pub page_size: usize,
    /// Whether to use transparent huge pages.
    pub transparent: bool,
    /// Target NUMA node (None = any node).
    pub numa_node: Option<usize>,
    /// Whether to pre-fault pages on allocation.
    pub prefault: bool,
}

impl Default for HugePageConfig {
    fn default() -> Self {
        Self {
            page_size: HUGE_PAGE_SIZE,
            transparent: true,
            numa_node: None,
            prefault: false,
        }
    }
}

/// NUMA topology information.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NumaTopology {
    /// Number of NUMA nodes.
    pub num_nodes: usize,
    /// Number of CPUs per node.
    pub cpus_per_node: Vec<usize>,
    /// Memory available per node in bytes.
    pub memory_per_node: Vec<usize>,
}

impl Default for NumaTopology {
    fn default() -> Self {
        // Single-node fallback (typical for non-NUMA systems)
        Self {
            num_nodes: 1,
            cpus_per_node: vec![num_cpus_available()],
            memory_per_node: vec![0], // unknown
        }
    }
}

/// Returns the number of available CPUs (portable fallback).
fn num_cpus_available() -> usize {
    std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(1)
}

/// NUMA-aware memory pinning controller.
///
/// In production, this interfaces with the RunuX kernel's NUMA allocator.
/// This portable implementation provides a fallback using standard
/// aligned allocation.
#[derive(Debug)]
pub struct NumaPinning {
    /// Current NUMA topology.
    topology: NumaTopology,
    /// Huge page configuration.
    huge_page_config: HugePageConfig,
    /// Total bytes allocated through this controller.
    total_allocated: usize,
    /// Number of allocations.
    allocation_count: u64,
}

impl NumaPinning {
    /// Creates a new NUMA pinning controller with default topology.
    pub fn new() -> Self {
        Self {
            topology: NumaTopology::default(),
            huge_page_config: HugePageConfig::default(),
            total_allocated: 0,
            allocation_count: 0,
        }
    }

    /// Creates a NUMA pinning controller with explicit topology.
    pub fn with_topology(topology: NumaTopology, config: HugePageConfig) -> Self {
        Self {
            topology,
            huge_page_config: config,
            total_allocated: 0,
            allocation_count: 0,
        }
    }

    /// Allocates `size` bytes with 2 MB huge page alignment.
    ///
    /// Returns a `Vec<u8>` with the requested alignment. On platforms
    /// without huge page support, falls back to standard alignment.
    ///
    /// # Errors
    ///
    /// Returns [`NumaError::InvalidNode`] if the target NUMA node is invalid.
    pub fn allocate_aligned(&mut self, size: usize) -> Result<Vec<u8>, NumaError> {
        if let Some(node) = self.huge_page_config.numa_node {
            if node >= self.topology.num_nodes {
                return Err(NumaError::InvalidNode(
                    node,
                    self.topology.num_nodes - 1,
                ));
            }
        }

        // Round up to huge page size
        let aligned_size = (size + HUGE_PAGE_SIZE - 1) & !(HUGE_PAGE_SIZE - 1);

        // Portable fallback: standard Vec<u8> allocation
        // In production RunuX deployment, this would call mmap with
        // MAP_HUGETLB | MAP_POPULATE and mbind for NUMA pinning.
        let buffer = vec![0u8; aligned_size];

        self.total_allocated += aligned_size;
        self.allocation_count += 1;

        tracing::debug!(
            size = aligned_size,
            numa_node = ?self.huge_page_config.numa_node,
            "NUMA-aligned allocation"
        );

        Ok(buffer)
    }

    /// Returns the NUMA topology.
    pub fn topology(&self) -> &NumaTopology {
        &self.topology
    }

    /// Returns the total bytes allocated.
    pub fn total_allocated(&self) -> usize {
        self.total_allocated
    }

    /// Returns the number of allocations performed.
    pub fn allocation_count(&self) -> u64 {
        self.allocation_count
    }

    /// Returns the huge page configuration.
    pub fn huge_page_config(&self) -> &HugePageConfig {
        &self.huge_page_config
    }

    /// Detects the actual NUMA topology of the current system.
    ///
    /// On non-NUMA systems (macOS, single-socket), returns a
    /// single-node topology.
    pub fn detect_topology() -> NumaTopology {
        // Portable fallback — always reports single NUMA node
        NumaTopology::default()
    }
}

impl Default for NumaPinning {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_topology() {
        let topo = NumaTopology::default();
        assert_eq!(topo.num_nodes, 1);
        assert!(!topo.cpus_per_node.is_empty());
    }

    #[test]
    fn test_allocate_aligned() {
        let mut pinning = NumaPinning::new();
        let buf = pinning.allocate_aligned(1024).unwrap();
        // Should be rounded up to 2 MB
        assert!(buf.len() >= HUGE_PAGE_SIZE);
        assert_eq!(pinning.allocation_count(), 1);
    }

    #[test]
    fn test_invalid_numa_node() {
        let mut pinning = NumaPinning::with_topology(
            NumaTopology::default(),
            HugePageConfig {
                numa_node: Some(99),
                ..Default::default()
            },
        );
        assert!(pinning.allocate_aligned(1024).is_err());
    }

    #[test]
    fn test_detect_topology() {
        let topo = NumaPinning::detect_topology();
        assert!(topo.num_nodes >= 1);
    }
}
