// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Three-Zone Arena Allocator
//!
//! Memory arena with three specialized zones for SymBrain inference:
//!
//! - **WeightZone** — Read-only memory-mapped region for frozen model weights.
//!   In production, this is backed by mmap; here we simulate with aligned `Vec<u8>`.
//! - **KVCacheZone** — Paged LRU cache with 64 KB pages for key-value attention caches.
//! - **ScratchZone** — Bump-allocated transient workspace for intermediate tensors.
//!
//! ## Design
//!
//! The three-zone layout prevents weight corruption (read-only zone),
//! enables efficient KV cache management (LRU eviction), and provides
//! zero-overhead scratch allocation (bump pointer).

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use thiserror::Error;

/// Page size for KV cache: 64 KB.
pub const KV_PAGE_SIZE: usize = 64 * 1024;

/// Errors from the arena allocator.
#[derive(Debug, Error)]
pub enum ArenaError {
    /// Attempted to write to the read-only weight zone.
    #[error("attempted write to read-only weight zone")]
    WeightZoneReadOnly,

    /// KV cache has no available pages.
    #[error("KV cache exhausted: {used}/{total} pages in use")]
    KVCacheExhausted { used: usize, total: usize },

    /// Scratch zone out of memory.
    #[error("scratch zone OOM: requested {requested} bytes, {available} available")]
    ScratchOOM { requested: usize, available: usize },

    /// Invalid zone configuration.
    #[error("invalid arena config: {0}")]
    InvalidConfig(String),
}

/// Configuration for the three-zone arena.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArenaConfig {
    /// Size of the weight zone in bytes.
    pub weight_zone_bytes: usize,
    /// Number of KV cache pages (each 64 KB).
    pub kv_cache_pages: usize,
    /// Size of the scratch zone in bytes.
    pub scratch_zone_bytes: usize,
}

impl Default for ArenaConfig {
    fn default() -> Self {
        Self {
            weight_zone_bytes: 256 * 1024 * 1024, // 256 MB
            kv_cache_pages: 1024,                   // 64 MB
            scratch_zone_bytes: 64 * 1024 * 1024,  // 64 MB
        }
    }
}

/// Read-only weight zone — stores frozen model weights.
///
/// In production deployment, this would be backed by `mmap(PROT_READ)`.
/// The simulation uses a read-only `Vec<u8>` with explicit access control.
#[derive(Debug)]
pub struct WeightZone {
    /// Raw weight data (read-only after initialization).
    data: Vec<u8>,
    /// Whether the zone has been sealed (made read-only).
    sealed: bool,
}

impl WeightZone {
    /// Creates a new weight zone with the given capacity.
    pub fn new(capacity: usize) -> Self {
        Self {
            data: Vec::with_capacity(capacity),
            sealed: false,
        }
    }

    /// Loads weight data into the zone. Must be called before sealing.
    ///
    /// # Errors
    ///
    /// Returns [`ArenaError::WeightZoneReadOnly`] if the zone is sealed.
    pub fn load(&mut self, data: &[u8]) -> Result<(), ArenaError> {
        if self.sealed {
            return Err(ArenaError::WeightZoneReadOnly);
        }
        self.data.extend_from_slice(data);
        Ok(())
    }

    /// Seals the zone, making it read-only.
    pub fn seal(&mut self) {
        self.sealed = true;
    }

    /// Returns a read-only slice of the weight data.
    pub fn data(&self) -> &[u8] {
        &self.data
    }

    /// Returns the size of loaded weights in bytes.
    pub fn size(&self) -> usize {
        self.data.len()
    }

    /// Returns whether the zone is sealed.
    pub fn is_sealed(&self) -> bool {
        self.sealed
    }
}

/// A single 64 KB KV cache page.
#[derive(Debug, Clone)]
pub struct KVPage {
    /// Page data.
    data: Vec<u8>,
    /// Logical page ID.
    page_id: u64,
    /// Number of accesses (for LRU tracking).
    access_count: u64,
}

impl KVPage {
    /// Creates a new empty KV page.
    fn new(page_id: u64) -> Self {
        Self {
            data: vec![0u8; KV_PAGE_SIZE],
            page_id,
            access_count: 0,
        }
    }
}

/// KV Cache Zone — paged LRU cache with 64 KB pages.
///
/// Manages key-value attention cache entries with LRU eviction.
/// When the cache is full, the least recently used page is evicted.
#[derive(Debug)]
pub struct KVCacheZone {
    /// Active pages in LRU order (front = most recent).
    pages: VecDeque<KVPage>,
    /// Maximum number of pages.
    max_pages: usize,
    /// Next page ID.
    next_page_id: u64,
    /// Total evictions.
    evictions: u64,
}

impl KVCacheZone {
    /// Creates a new KV cache zone with the given page capacity.
    pub fn new(max_pages: usize) -> Self {
        Self {
            pages: VecDeque::with_capacity(max_pages),
            max_pages,
            next_page_id: 0,
            evictions: 0,
        }
    }

    /// Allocates a new KV page, evicting LRU if necessary.
    ///
    /// Returns a mutable reference to the new page's data.
    pub fn allocate_page(&mut self) -> &mut [u8] {
        if self.pages.len() >= self.max_pages {
            // Evict LRU (back of deque)
            self.pages.pop_back();
            self.evictions += 1;
        }

        let page = KVPage::new(self.next_page_id);
        self.next_page_id += 1;
        self.pages.push_front(page);

        &mut self.pages.front_mut().unwrap().data
    }

    /// Accesses a page by ID, promoting it to MRU position.
    ///
    /// Returns `None` if the page was evicted or never allocated.
    pub fn access_page(&mut self, page_id: u64) -> Option<&mut [u8]> {
        let pos = self
            .pages
            .iter()
            .position(|p| p.page_id == page_id)?;

        // Promote to front (MRU)
        let mut page = self.pages.remove(pos)?;
        page.access_count += 1;
        self.pages.push_front(page);

        Some(&mut self.pages.front_mut().unwrap().data)
    }

    /// Returns the number of active pages.
    pub fn active_pages(&self) -> usize {
        self.pages.len()
    }

    /// Returns the total number of evictions.
    pub fn evictions(&self) -> u64 {
        self.evictions
    }

    /// Returns the cache hit rate (approximation based on eviction ratio).
    pub fn utilization(&self) -> f64 {
        self.pages.len() as f64 / self.max_pages as f64
    }
}

/// Scratch Zone — bump-allocated transient workspace.
///
/// Fast linear allocation with reset-on-demand for intermediate
/// computation buffers. Not thread-safe; use the thread-local
/// [`super::bump_allocator::BumpAllocator`] for concurrent access.
#[derive(Debug)]
pub struct ScratchZone {
    /// Backing memory.
    data: Vec<u8>,
    /// Current bump pointer offset.
    offset: usize,
    /// Number of resets.
    resets: u64,
}

impl ScratchZone {
    /// Creates a new scratch zone with the given capacity.
    pub fn new(capacity: usize) -> Self {
        Self {
            data: vec![0u8; capacity],
            offset: 0,
            resets: 0,
        }
    }

    /// Allocates `size` bytes from the scratch zone.
    ///
    /// # Errors
    ///
    /// Returns [`ArenaError::ScratchOOM`] if insufficient space.
    pub fn alloc(&mut self, size: usize) -> Result<&mut [u8], ArenaError> {
        let aligned_size = (size + 7) & !7; // 8-byte alignment
        if self.offset + aligned_size > self.data.len() {
            return Err(ArenaError::ScratchOOM {
                requested: size,
                available: self.data.len() - self.offset,
            });
        }

        let start = self.offset;
        self.offset += aligned_size;
        Ok(&mut self.data[start..start + size])
    }

    /// Resets the scratch zone, freeing all allocations.
    ///
    /// This is O(1) — just resets the bump pointer.
    pub fn reset(&mut self) {
        self.offset = 0;
        self.resets += 1;
    }

    /// Returns the number of bytes currently allocated.
    pub fn used(&self) -> usize {
        self.offset
    }

    /// Returns the total capacity.
    pub fn capacity(&self) -> usize {
        self.data.len()
    }

    /// Returns the number of bytes available.
    pub fn available(&self) -> usize {
        self.data.len() - self.offset
    }

    /// Returns the number of resets performed.
    pub fn resets(&self) -> u64 {
        self.resets
    }
}

/// The complete three-zone arena allocator.
pub struct ThreeZoneArena {
    /// Read-only weight storage.
    pub weights: WeightZone,
    /// Paged LRU KV cache.
    pub kv_cache: KVCacheZone,
    /// Bump-allocated scratch space.
    pub scratch: ScratchZone,
}

impl ThreeZoneArena {
    /// Creates a new three-zone arena from configuration.
    pub fn new(config: &ArenaConfig) -> Self {
        Self {
            weights: WeightZone::new(config.weight_zone_bytes),
            kv_cache: KVCacheZone::new(config.kv_cache_pages),
            scratch: ScratchZone::new(config.scratch_zone_bytes),
        }
    }

    /// Returns total memory footprint in bytes.
    pub fn total_bytes(&self) -> usize {
        self.weights.size()
            + self.kv_cache.active_pages() * KV_PAGE_SIZE
            + self.scratch.capacity()
    }

    /// Resets the scratch zone, keeping weights and KV cache intact.
    pub fn reset_scratch(&mut self) {
        self.scratch.reset();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_weight_zone_seal() {
        let mut wz = WeightZone::new(1024);
        wz.load(&[1, 2, 3, 4]).unwrap();
        wz.seal();
        assert!(wz.load(&[5]).is_err());
        assert_eq!(wz.data(), &[1, 2, 3, 4]);
    }

    #[test]
    fn test_kv_cache_lru_eviction() {
        let mut kv = KVCacheZone::new(2);
        kv.allocate_page(); // page 0
        kv.allocate_page(); // page 1
        assert_eq!(kv.active_pages(), 2);

        kv.allocate_page(); // page 2 — evicts page 0
        assert_eq!(kv.active_pages(), 2);
        assert_eq!(kv.evictions(), 1);
        assert!(kv.access_page(0).is_none()); // page 0 was evicted
    }

    #[test]
    fn test_scratch_zone_alloc_and_reset() {
        let mut sz = ScratchZone::new(256);
        let buf = sz.alloc(64).unwrap();
        assert_eq!(buf.len(), 64);
        assert!(sz.used() >= 64);

        sz.reset();
        assert_eq!(sz.used(), 0);
        assert_eq!(sz.resets(), 1);
    }

    #[test]
    fn test_scratch_zone_oom() {
        let mut sz = ScratchZone::new(64);
        assert!(sz.alloc(128).is_err());
    }

    #[test]
    fn test_three_zone_arena() {
        let config = ArenaConfig {
            weight_zone_bytes: 1024,
            kv_cache_pages: 4,
            scratch_zone_bytes: 2048,
        };
        let mut arena = ThreeZoneArena::new(&config);
        arena.weights.load(&[0u8; 100]).unwrap();
        arena.kv_cache.allocate_page();
        arena.scratch.alloc(512).unwrap();
        assert!(arena.total_bytes() > 0);
    }
}
