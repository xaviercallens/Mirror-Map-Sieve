// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! Unit tests for memory management: arena allocation, bump allocator.

use agora_core::memory::*;

// ── Three-Zone Arena Tests ──

#[test]
fn test_arena_lifecycle() {
    let config = ArenaConfig {
        weight_zone_bytes: 1024,
        kv_cache_pages: 4,
        scratch_zone_bytes: 4096,
    };
    let mut arena = ThreeZoneArena::new(&config);

    // Load weights
    let weights = vec![0xAA_u8; 512];
    arena.weights.load(&weights).unwrap();
    assert_eq!(arena.weights.size(), 512);

    // Seal weights
    arena.weights.seal();
    assert!(arena.weights.is_sealed());
    assert!(arena.weights.load(&[0]).is_err());

    // Allocate KV cache pages
    let page = arena.kv_cache.allocate_page();
    page[0] = 0xFF;
    assert_eq!(arena.kv_cache.active_pages(), 1);

    // Allocate scratch
    let scratch = arena.scratch.alloc(256).unwrap();
    scratch.fill(0xBB);
    assert!(arena.scratch.used() >= 256);

    // Reset scratch
    arena.reset_scratch();
    assert_eq!(arena.scratch.used(), 0);
}

#[test]
fn test_kv_cache_lru_order() {
    let config = ArenaConfig {
        weight_zone_bytes: 0,
        kv_cache_pages: 3,
        scratch_zone_bytes: 0,
    };
    let mut arena = ThreeZoneArena::new(&config);

    // Allocate 3 pages
    arena.kv_cache.allocate_page(); // page 0
    arena.kv_cache.allocate_page(); // page 1
    arena.kv_cache.allocate_page(); // page 2
    assert_eq!(arena.kv_cache.active_pages(), 3);

    // Access page 0 (promote to MRU)
    assert!(arena.kv_cache.access_page(0).is_some());

    // Allocate page 3 — should evict LRU (page 1)
    arena.kv_cache.allocate_page(); // page 3

    // Page 1 should be evicted, pages 0, 2, 3 should remain
    assert!(arena.kv_cache.access_page(1).is_none(), "page 1 should be evicted");
    assert!(arena.kv_cache.access_page(0).is_some(), "page 0 should survive (was promoted)");
}

#[test]
fn test_scratch_zone_exhaustion() {
    let mut scratch = ScratchZone::new(128);
    let _ = scratch.alloc(64).unwrap();
    let _ = scratch.alloc(48).unwrap();
    // Should fail — only ~16 bytes left, but we're asking for 32
    assert!(scratch.alloc(32).is_err());
}

// ── Bump Allocator Tests ──

#[test]
fn test_bump_allocator_concurrent_safety() {
    use std::sync::Arc;
    use std::thread;

    let allocator = Arc::new(BumpAllocator::new(1024 * 1024)); // 1 MB

    let mut handles = Vec::new();
    for _ in 0..4 {
        let alloc = allocator.clone();
        handles.push(thread::spawn(move || {
            for _ in 0..100 {
                let buf = alloc.alloc(64).unwrap();
                buf.fill(0xCC);
            }
        }));
    }

    for handle in handles {
        handle.join().unwrap();
    }

    // Total: 4 threads × 100 allocs × 64 bytes = 25,600 bytes (+ alignment)
    assert!(allocator.alloc_count() == 400);
    assert!(allocator.used() >= 25_600);
}

#[test]
fn test_bump_allocator_alignment_guarantees() {
    let allocator = BumpAllocator::new(8192);

    // Allocate with various alignments
    for align in [1, 2, 4, 8, 16, 32, 64] {
        let _buf = allocator.alloc_aligned(32, align).unwrap();
        let used_after = allocator.used();
        let start_offset = used_after - 32;
        assert_eq!(
            start_offset % align,
            0,
            "allocation offset {start_offset} not {align}-byte aligned"
        );
    }
}

#[test]
fn test_bump_allocator_utilization() {
    let allocator = BumpAllocator::new(4096);
    assert!((allocator.utilization() - 0.0).abs() < f64::EPSILON);

    allocator.alloc(2048).unwrap();
    assert!(allocator.utilization() > 0.4);
    assert!(allocator.utilization() < 0.6);
}

// ── NUMA Pinning Tests ──

#[test]
fn test_numa_huge_page_alignment() {
    let mut pinning = NumaPinning::new();
    let buf = pinning.allocate_aligned(1024).unwrap();

    // Should be rounded up to 2 MB huge page
    assert_eq!(buf.len(), 2 * 1024 * 1024);
    assert_eq!(pinning.allocation_count(), 1);
    assert_eq!(pinning.total_allocated(), 2 * 1024 * 1024);
}
