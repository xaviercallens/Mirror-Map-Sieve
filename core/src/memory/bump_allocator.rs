// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Thread-Local Bump Allocator
//!
//! Lock-free bump allocator using `AtomicUsize` for the allocation pointer.
//! Each thread gets its own allocator instance via `thread_local!`,
//! eliminating contention in parallel inference pipelines.
//!
//! ## Design
//!
//! - **Allocation**: O(1) atomic fetch-and-add
//! - **Deallocation**: Not supported (use `reset()` to free all)
//! - **Thread safety**: Lock-free via `AtomicUsize`
//! - **Alignment**: 8-byte aligned allocations by default

use std::sync::atomic::{AtomicUsize, Ordering};
use thiserror::Error;

/// Errors from the bump allocator.
#[derive(Debug, Error)]
pub enum BumpError {
    /// Allocator is out of memory.
    #[error("bump allocator OOM: requested {requested}, available {available}")]
    OutOfMemory { requested: usize, available: usize },

    /// Requested alignment is not a power of two.
    #[error("alignment {0} is not a power of two")]
    InvalidAlignment(usize),
}

/// Thread-local bump allocator with atomic pointer.
///
/// Provides ultra-fast O(1) allocation by advancing an atomic pointer.
/// Memory is freed in bulk via `reset()`.
///
/// # Usage
///
/// ```rust,no_run
/// use agora_core::memory::BumpAllocator;
///
/// let mut allocator = BumpAllocator::new(4096);
/// let buf = allocator.alloc(64).unwrap();
/// buf.fill(0xFF);
/// allocator.reset(); // frees everything
/// ```
pub struct BumpAllocator {
    /// Backing memory.
    data: Vec<u8>,
    /// Current allocation pointer (byte offset from start).
    pointer: AtomicUsize,
    /// Total capacity in bytes.
    capacity: usize,
    /// Number of allocations since last reset.
    alloc_count: AtomicUsize,
    /// Peak usage watermark.
    peak_usage: AtomicUsize,
}

impl BumpAllocator {
    /// Creates a new bump allocator with the given capacity.
    ///
    /// # Arguments
    ///
    /// * `capacity` — Total memory in bytes available for allocation
    pub fn new(capacity: usize) -> Self {
        Self {
            data: vec![0u8; capacity],
            pointer: AtomicUsize::new(0),
            capacity,
            alloc_count: AtomicUsize::new(0),
            peak_usage: AtomicUsize::new(0),
        }
    }

    /// Allocates `size` bytes with default 8-byte alignment.
    ///
    /// # Errors
    ///
    /// Returns [`BumpError::OutOfMemory`] if insufficient space.
    pub fn alloc(&self, size: usize) -> Result<&mut [u8], BumpError> {
        self.alloc_aligned(size, 8)
    }

    /// Allocates `size` bytes with the specified alignment.
    ///
    /// The alignment must be a power of two.
    ///
    /// # Errors
    ///
    /// Returns [`BumpError::InvalidAlignment`] if alignment is not a power of two.
    /// Returns [`BumpError::OutOfMemory`] if insufficient space.
    pub fn alloc_aligned(&self, size: usize, align: usize) -> Result<&mut [u8], BumpError> {
        if !align.is_power_of_two() {
            return Err(BumpError::InvalidAlignment(align));
        }

        loop {
            let current = self.pointer.load(Ordering::Relaxed);

            // Align up
            let aligned = (current + align - 1) & !(align - 1);
            let new_pointer = aligned + size;

            if new_pointer > self.capacity {
                return Err(BumpError::OutOfMemory {
                    requested: size,
                    available: self.capacity.saturating_sub(aligned),
                });
            }

            // CAS to advance the pointer
            match self.pointer.compare_exchange_weak(
                current,
                new_pointer,
                Ordering::AcqRel,
                Ordering::Relaxed,
            ) {
                Ok(_) => {
                    self.alloc_count.fetch_add(1, Ordering::Relaxed);

                    // Update peak usage
                    let _ = self.peak_usage.fetch_max(new_pointer, Ordering::Relaxed);

                    // SAFETY: We own the data, and the CAS ensures no overlapping
                    // allocations. Each successful CAS claims a unique range.
                    let slice = unsafe {
                        let ptr = self.data.as_ptr().add(aligned) as *mut u8;
                        std::slice::from_raw_parts_mut(ptr, size)
                    };
                    return Ok(slice);
                }
                Err(_) => {
                    // CAS failed — retry with updated pointer
                    continue;
                }
            }
        }
    }

    /// Resets the allocator, freeing all allocations.
    ///
    /// # Safety
    ///
    /// Callers must ensure no references to allocated memory are live
    /// when this is called.
    pub fn reset(&self) {
        self.pointer.store(0, Ordering::Release);
        self.alloc_count.store(0, Ordering::Release);
    }

    /// Returns the current byte offset (bytes allocated).
    pub fn used(&self) -> usize {
        self.pointer.load(Ordering::Relaxed)
    }

    /// Returns the total capacity.
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Returns the available bytes.
    pub fn available(&self) -> usize {
        self.capacity.saturating_sub(self.used())
    }

    /// Returns the number of allocations since last reset.
    pub fn alloc_count(&self) -> usize {
        self.alloc_count.load(Ordering::Relaxed)
    }

    /// Returns the peak usage watermark.
    pub fn peak_usage(&self) -> usize {
        self.peak_usage.load(Ordering::Relaxed)
    }

    /// Returns utilization as a fraction.
    pub fn utilization(&self) -> f64 {
        self.used() as f64 / self.capacity as f64
    }
}

// BumpAllocator uses interior mutability (AtomicUsize) so it can be
// shared across threads with proper synchronization on reset.
unsafe impl Sync for BumpAllocator {}

impl std::fmt::Debug for BumpAllocator {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("BumpAllocator")
            .field("capacity", &self.capacity)
            .field("used", &self.used())
            .field("alloc_count", &self.alloc_count())
            .field("peak_usage", &self.peak_usage())
            .finish()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_alloc() {
        let allocator = BumpAllocator::new(4096);
        let buf = allocator.alloc(64).unwrap();
        assert_eq!(buf.len(), 64);
        buf.fill(0xAA);
        assert!(allocator.used() >= 64);
    }

    #[test]
    fn test_oom() {
        let allocator = BumpAllocator::new(64);
        assert!(allocator.alloc(128).is_err());
    }

    #[test]
    fn test_reset() {
        let allocator = BumpAllocator::new(4096);
        allocator.alloc(100).unwrap();
        allocator.alloc(100).unwrap();
        assert!(allocator.used() >= 200);

        allocator.reset();
        assert_eq!(allocator.used(), 0);
        assert_eq!(allocator.alloc_count(), 0);
    }

    #[test]
    fn test_alignment() {
        let allocator = BumpAllocator::new(4096);
        // Allocate 1 byte, then 64-byte aligned
        allocator.alloc(1).unwrap();
        let buf = allocator.alloc_aligned(32, 64).unwrap();
        let offset = buf.as_ptr() as usize - allocator.data.as_ptr() as usize;
        assert_eq!(offset % 64, 0, "allocation should be 64-byte aligned relative to base");
    }

    #[test]
    fn test_invalid_alignment() {
        let allocator = BumpAllocator::new(4096);
        assert!(allocator.alloc_aligned(32, 3).is_err()); // 3 is not power of 2
    }

    #[test]
    fn test_sequential_allocations() {
        let allocator = BumpAllocator::new(4096);
        for i in 0..10 {
            let buf = allocator.alloc(32).unwrap();
            buf.fill(i as u8);
        }
        assert_eq!(allocator.alloc_count(), 10);
        assert!(allocator.peak_usage() >= 320);
    }
}
