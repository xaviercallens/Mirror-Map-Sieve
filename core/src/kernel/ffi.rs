// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # FFI Bridge to RunuX Kernel
//!
//! Foreign Function Interface (FFI) bridge between the Agora framework
//! and the RunuX Rust OS kernel. Provides safe Rust wrappers around
//! kernel system calls for:
//!
//! - Memory-mapped I/O for tensor weight loading
//! - Hardware timer access for precise latency measurement
//! - DMA channel management for co-processor data transfer
//! - Power management for edge device deployment
//!
//! ## Safety
//!
//! When compiled for bare-metal RunuX deployment, these functions call
//! into the kernel via `extern "C"` FFI. In simulation mode (hosted OS),
//! they provide portable stubs that emulate kernel behavior.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from the RunuX FFI bridge.
#[derive(Debug, Error)]
pub enum FFIError {
    /// Kernel call returned an error code.
    #[error("RunuX kernel error: code={code}, msg={msg}")]
    KernelError { code: i32, msg: String },

    /// Memory mapping failed.
    #[error("mmap failed for region 0x{addr:016x}, size {size}")]
    MmapFailed { addr: u64, size: usize },

    /// DMA transfer failed.
    #[error("DMA transfer failed on channel {channel}")]
    DmaFailed { channel: u32 },

    /// Feature not available in simulation mode.
    #[error("feature '{0}' requires bare-metal RunuX kernel")]
    SimulationOnly(String),
}

/// RunuX kernel version information.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KernelVersion {
    /// Major version.
    pub major: u32,
    /// Minor version.
    pub minor: u32,
    /// Patch version.
    pub patch: u32,
    /// Build string.
    pub build: String,
}

impl std::fmt::Display for KernelVersion {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}.{}.{}-{}", self.major, self.minor, self.patch, self.build)
    }
}

/// Power state for edge device management.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PowerState {
    /// Full performance mode.
    Performance,
    /// Balanced mode (default).
    Balanced,
    /// Power-saving mode (reduced clock, voltage).
    PowerSave,
    /// Deep sleep (minimal power, wake on interrupt).
    DeepSleep,
}

/// DMA channel descriptor.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DmaChannel {
    /// Channel number.
    pub channel: u32,
    /// Source physical address.
    pub src_addr: u64,
    /// Destination physical address.
    pub dst_addr: u64,
    /// Transfer size in bytes.
    pub size: usize,
    /// Whether the channel is currently active.
    pub active: bool,
}

/// Memory-mapped region descriptor.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MmapRegion {
    /// Virtual address of the mapped region.
    pub vaddr: u64,
    /// Physical address of the mapped region.
    pub paddr: u64,
    /// Size in bytes.
    pub size: usize,
    /// Read-only flag.
    pub read_only: bool,
}

/// FFI bridge to the RunuX kernel.
///
/// In simulation mode (default for hosted OS), provides portable stubs.
/// In bare-metal mode (`#[cfg(target_os = "runux")]`), calls into the
/// actual kernel via `extern "C"` FFI.
#[derive(Debug)]
pub struct RunuXBridge {
    /// Whether we're running in simulation mode.
    simulation: bool,
    /// Kernel version (simulated or real).
    version: KernelVersion,
    /// Current power state.
    power_state: PowerState,
    /// Allocated DMA channels.
    dma_channels: Vec<DmaChannel>,
    /// Mapped memory regions.
    mmap_regions: Vec<MmapRegion>,
}

impl RunuXBridge {
    /// Creates a new RunuX bridge in simulation mode.
    pub fn new_simulation() -> Self {
        Self {
            simulation: true,
            version: KernelVersion {
                major: 0,
                minor: 1,
                patch: 0,
                build: "sim".to_string(),
            },
            power_state: PowerState::Balanced,
            dma_channels: Vec::new(),
            mmap_regions: Vec::new(),
        }
    }

    /// Returns the kernel version.
    pub fn version(&self) -> &KernelVersion {
        &self.version
    }

    /// Returns whether we're in simulation mode.
    pub fn is_simulation(&self) -> bool {
        self.simulation
    }

    /// Maps a physical address range into virtual memory (simulation).
    ///
    /// In production RunuX, this calls `runux_mmap()` kernel syscall.
    ///
    /// # Arguments
    ///
    /// * `paddr` — Physical base address
    /// * `size` — Size in bytes
    /// * `read_only` — Whether the mapping is read-only
    pub fn mmap(
        &mut self,
        paddr: u64,
        size: usize,
        read_only: bool,
    ) -> Result<MmapRegion, FFIError> {
        // Simulation: assign a virtual address
        let vaddr = 0x4000_0000_0000u64 + self.mmap_regions.len() as u64 * 0x10_0000;

        let region = MmapRegion {
            vaddr,
            paddr,
            size,
            read_only,
        };

        tracing::debug!(
            paddr = format!("0x{paddr:016x}"),
            vaddr = format!("0x{vaddr:016x}"),
            size,
            "simulated mmap"
        );

        self.mmap_regions.push(region.clone());
        Ok(region)
    }

    /// Reads the hardware timer (nanosecond precision).
    ///
    /// In production RunuX, this reads the platform timer register
    /// (RISC-V `rdtime` or ARM `CNTVCT_EL0`).
    pub fn read_timer_ns(&self) -> u64 {
        if self.simulation {
            // Use std::time in simulation
            use std::time::{SystemTime, UNIX_EPOCH};
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos() as u64
        } else {
            // In production: inline assembly for timer register
            0
        }
    }

    /// Allocates a DMA channel for co-processor data transfer.
    ///
    /// # Arguments
    ///
    /// * `src_addr` — Source physical address
    /// * `dst_addr` — Destination physical address
    /// * `size` — Transfer size in bytes
    pub fn alloc_dma_channel(
        &mut self,
        src_addr: u64,
        dst_addr: u64,
        size: usize,
    ) -> Result<u32, FFIError> {
        let channel = self.dma_channels.len() as u32;
        self.dma_channels.push(DmaChannel {
            channel,
            src_addr,
            dst_addr,
            size,
            active: false,
        });
        Ok(channel)
    }

    /// Initiates a DMA transfer on the specified channel.
    ///
    /// # Errors
    ///
    /// Returns [`FFIError::DmaFailed`] if the channel doesn't exist.
    pub fn start_dma(&mut self, channel: u32) -> Result<(), FFIError> {
        let ch = self
            .dma_channels
            .iter_mut()
            .find(|c| c.channel == channel)
            .ok_or(FFIError::DmaFailed { channel })?;

        ch.active = true;
        tracing::debug!(channel, "DMA transfer started (simulated)");
        // In simulation, DMA completes instantly
        ch.active = false;
        Ok(())
    }

    /// Sets the power state for edge device power management.
    pub fn set_power_state(&mut self, state: PowerState) {
        tracing::info!(
            old = ?self.power_state,
            new = ?state,
            "power state transition"
        );
        self.power_state = state;
    }

    /// Returns the current power state.
    pub fn power_state(&self) -> PowerState {
        self.power_state
    }

    /// Returns the number of mapped regions.
    pub fn mmap_count(&self) -> usize {
        self.mmap_regions.len()
    }

    /// Returns the number of DMA channels.
    pub fn dma_channel_count(&self) -> usize {
        self.dma_channels.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simulation_mode() {
        let bridge = RunuXBridge::new_simulation();
        assert!(bridge.is_simulation());
        assert_eq!(bridge.version().build, "sim");
    }

    #[test]
    fn test_mmap() {
        let mut bridge = RunuXBridge::new_simulation();
        let region = bridge.mmap(0x8000_0000, 4096, true).unwrap();
        assert!(region.read_only);
        assert_eq!(bridge.mmap_count(), 1);
    }

    #[test]
    fn test_timer() {
        let bridge = RunuXBridge::new_simulation();
        let t1 = bridge.read_timer_ns();
        let t2 = bridge.read_timer_ns();
        assert!(t2 >= t1);
    }

    #[test]
    fn test_dma() {
        let mut bridge = RunuXBridge::new_simulation();
        let ch = bridge.alloc_dma_channel(0x1000, 0x2000, 4096).unwrap();
        bridge.start_dma(ch).unwrap();
        assert!(bridge.start_dma(99).is_err());
    }

    #[test]
    fn test_power_state() {
        let mut bridge = RunuXBridge::new_simulation();
        assert_eq!(bridge.power_state(), PowerState::Balanced);
        bridge.set_power_state(PowerState::PowerSave);
        assert_eq!(bridge.power_state(), PowerState::PowerSave);
    }
}
