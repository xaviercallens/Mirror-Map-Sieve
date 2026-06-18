// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Co-Processor Proof Pipeline
//!
//! 8-bit quantization pipeline for batch proof tensor verification.
//! Transforms floating-point constraint tensors into quantized
//! representations suitable for co-processor verification engines.
//!
//! ## Quantization Formula
//!
//! ```text
//! Q(x) = clip(round(x / Δ), -128, 127)
//! ```
//!
//! Where Δ = (max - min) / 255 is the quantization step size.
//!
//! ## Pipeline Stages
//!
//! 1. **Quantize** — Convert float constraints to 8-bit representation
//! 2. **Batch** — Group quantized constraints into proof batches
//! 3. **Verify** — Aggregate verification results from co-processor

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors from the co-processor pipeline.
#[derive(Debug, Error)]
pub enum CoProcError {
    /// Quantization range is degenerate (max ≈ min).
    #[error("degenerate quantization range: [{min}, {max}]")]
    DegenerateRange { min: f64, max: f64 },

    /// Empty batch submitted for verification.
    #[error("empty proof batch")]
    EmptyBatch,

    /// Co-processor communication failure.
    #[error("co-processor error: {0}")]
    CoProcFailure(String),
}

/// An 8-bit quantized constraint value.
///
/// Stores the quantized integer value along with the quantization
/// parameters needed for dequantization.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct QuantizedConstraint {
    /// Quantized 8-bit value in [-128, 127].
    pub value: i8,
    /// Original floating-point value (for verification).
    pub original: f64,
    /// Quantization step size Δ.
    pub delta: f64,
    /// Zero-point offset.
    pub zero_point: f64,
}

impl QuantizedConstraint {
    /// Quantizes a floating-point value to 8-bit representation.
    ///
    /// ```text
    /// Q(x) = clip(round(x / Δ), -128, 127)
    /// ```
    ///
    /// # Arguments
    ///
    /// * `value` — The floating-point value to quantize
    /// * `delta` — The quantization step size
    /// * `zero_point` — The zero-point offset
    pub fn quantize(value: f64, delta: f64, zero_point: f64) -> Self {
        let scaled = (value - zero_point) / delta;
        let rounded = scaled.round();
        let clamped = rounded.clamp(-128.0, 127.0) as i8;

        Self {
            value: clamped,
            original: value,
            delta,
            zero_point,
        }
    }

    /// Dequantizes back to floating-point.
    ///
    /// ```text
    /// x_hat = value * Δ + zero_point
    /// ```
    pub fn dequantize(&self) -> f64 {
        self.value as f64 * self.delta + self.zero_point
    }

    /// Returns the quantization error (original - dequantized).
    pub fn quantization_error(&self) -> f64 {
        (self.original - self.dequantize()).abs()
    }
}

/// Computes quantization parameters for a set of values.
///
/// Returns `(delta, zero_point)` where:
/// - `delta = (max - min) / 255`
/// - `zero_point = min`
///
/// # Errors
///
/// Returns [`CoProcError::DegenerateRange`] if the range is too small.
pub fn compute_quant_params(values: &[f64]) -> Result<(f64, f64), CoProcError> {
    if values.is_empty() {
        return Err(CoProcError::DegenerateRange {
            min: 0.0,
            max: 0.0,
        });
    }

    let min = values.iter().cloned().fold(f64::INFINITY, f64::min);
    let max = values.iter().cloned().fold(f64::NEG_INFINITY, f64::max);

    let range = max - min;
    if range < 1e-15 {
        // All values are essentially the same — use unit delta
        return Ok((1.0, min + 128.0));
    }

    let delta = range / 255.0;
    let zero_point = min + 128.0 * delta;
    Ok((delta, zero_point))
}

/// A batch of quantized constraints for co-processor verification.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofBatch {
    /// Batch identifier.
    pub batch_id: u64,
    /// Quantized constraints in this batch.
    pub constraints: Vec<QuantizedConstraint>,
    /// Quantization delta used for this batch.
    pub delta: f64,
    /// Zero-point offset for this batch.
    pub zero_point: f64,
    /// Maximum quantization error in this batch.
    pub max_error: f64,
    /// Mean quantization error in this batch.
    pub mean_error: f64,
}

impl ProofBatch {
    /// Creates a new proof batch by quantizing the given constraint values.
    ///
    /// # Arguments
    ///
    /// * `batch_id` — Unique batch identifier
    /// * `values` — Floating-point constraint values to quantize
    ///
    /// # Errors
    ///
    /// Returns [`CoProcError::EmptyBatch`] if values is empty.
    /// Returns [`CoProcError::DegenerateRange`] if range is degenerate.
    pub fn from_values(batch_id: u64, values: &[f64]) -> Result<Self, CoProcError> {
        if values.is_empty() {
            return Err(CoProcError::EmptyBatch);
        }

        let (delta, zero_point) = compute_quant_params(values)?;

        let constraints: Vec<QuantizedConstraint> = values
            .iter()
            .map(|&v| QuantizedConstraint::quantize(v, delta, zero_point))
            .collect();

        let errors: Vec<f64> = constraints.iter().map(|c| c.quantization_error()).collect();
        let max_error = errors.iter().cloned().fold(0.0f64, f64::max);
        let mean_error = errors.iter().sum::<f64>() / errors.len() as f64;

        Ok(Self {
            batch_id,
            constraints,
            delta,
            zero_point,
            max_error,
            mean_error,
        })
    }

    /// Returns the number of constraints in this batch.
    pub fn len(&self) -> usize {
        self.constraints.len()
    }

    /// Returns true if the batch is empty.
    pub fn is_empty(&self) -> bool {
        self.constraints.is_empty()
    }

    /// Dequantizes all constraints back to floating-point.
    pub fn dequantize_all(&self) -> Vec<f64> {
        self.constraints.iter().map(|c| c.dequantize()).collect()
    }

    /// Returns the raw i8 values for co-processor transfer.
    pub fn raw_i8_values(&self) -> Vec<i8> {
        self.constraints.iter().map(|c| c.value).collect()
    }
}

/// Result of co-processor verification.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationResult {
    /// Batch ID that was verified.
    pub batch_id: u64,
    /// Whether all constraints passed verification.
    pub all_passed: bool,
    /// Number of constraints that passed.
    pub passed_count: usize,
    /// Number of constraints that failed.
    pub failed_count: usize,
    /// Indices of failed constraints.
    pub failed_indices: Vec<usize>,
    /// Maximum residual norm across all constraints.
    pub max_residual: f64,
    /// Verification latency in microseconds.
    pub latency_us: u64,
}

impl VerificationResult {
    /// Creates a verification result from individual constraint checks.
    ///
    /// # Arguments
    ///
    /// * `batch_id` — The batch that was verified
    /// * `residuals` — Residual values for each constraint
    /// * `tolerance` — Maximum acceptable residual
    /// * `latency_us` — Verification time in microseconds
    pub fn from_residuals(
        batch_id: u64,
        residuals: &[f64],
        tolerance: f64,
        latency_us: u64,
    ) -> Self {
        let mut failed_indices = Vec::new();
        let mut max_residual = 0.0f64;

        for (i, &r) in residuals.iter().enumerate() {
            let abs_r = r.abs();
            if abs_r > max_residual {
                max_residual = abs_r;
            }
            if abs_r > tolerance {
                failed_indices.push(i);
            }
        }

        let failed_count = failed_indices.len();
        let passed_count = residuals.len() - failed_count;

        Self {
            batch_id,
            all_passed: failed_count == 0,
            passed_count,
            failed_count,
            failed_indices,
            max_residual,
            latency_us,
        }
    }

    /// Returns the pass rate as a fraction.
    pub fn pass_rate(&self) -> f64 {
        let total = self.passed_count + self.failed_count;
        if total == 0 {
            1.0
        } else {
            self.passed_count as f64 / total as f64
        }
    }
}

/// Aggregates multiple verification results into a summary.
pub fn aggregate_results(results: &[VerificationResult]) -> VerificationResult {
    let mut total_passed = 0usize;
    let mut total_failed = 0usize;
    let mut all_failed_indices = Vec::new();
    let mut max_residual = 0.0f64;
    let mut total_latency = 0u64;
    let mut offset = 0usize;

    for r in results {
        total_passed += r.passed_count;
        total_failed += r.failed_count;
        for &idx in &r.failed_indices {
            all_failed_indices.push(offset + idx);
        }
        if r.max_residual > max_residual {
            max_residual = r.max_residual;
        }
        total_latency += r.latency_us;
        offset += r.passed_count + r.failed_count;
    }

    VerificationResult {
        batch_id: 0, // aggregate has no single batch ID
        all_passed: total_failed == 0,
        passed_count: total_passed,
        failed_count: total_failed,
        failed_indices: all_failed_indices,
        max_residual,
        latency_us: total_latency,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_quantize_dequantize_roundtrip() {
        let delta = 0.1;
        let zero_point = 0.0;
        let q = QuantizedConstraint::quantize(0.55, delta, zero_point);
        let dq = q.dequantize();
        assert!(
            (dq - 0.55).abs() < delta,
            "roundtrip error should be < Δ"
        );
    }

    #[test]
    fn test_quantize_clamps() {
        let q_max = QuantizedConstraint::quantize(1000.0, 1.0, 0.0);
        assert_eq!(q_max.value, 127);

        let q_min = QuantizedConstraint::quantize(-1000.0, 1.0, 0.0);
        assert_eq!(q_min.value, -128);
    }

    #[test]
    fn test_batch_creation() {
        let values = vec![0.1, 0.5, 0.9, 1.3, 2.0];
        let batch = ProofBatch::from_values(1, &values).unwrap();
        assert_eq!(batch.len(), 5);
        assert!(batch.max_error < batch.delta + 1e-10);
    }

    #[test]
    fn test_empty_batch_error() {
        let result = ProofBatch::from_values(1, &[]);
        assert!(result.is_err());
    }

    #[test]
    fn test_verification_result() {
        let residuals = vec![0.001, 0.002, 0.5, 0.001];
        let result =
            VerificationResult::from_residuals(1, &residuals, 0.01, 100);
        assert!(!result.all_passed);
        assert_eq!(result.failed_count, 1);
        assert_eq!(result.failed_indices, vec![2]);
        assert!((result.pass_rate() - 0.75).abs() < f64::EPSILON);
    }

    #[test]
    fn test_aggregate_results() {
        let r1 = VerificationResult::from_residuals(1, &[0.001, 0.002], 0.01, 50);
        let r2 = VerificationResult::from_residuals(2, &[0.001, 0.5], 0.01, 60);
        let agg = aggregate_results(&[r1, r2]);
        assert_eq!(agg.passed_count, 3);
        assert_eq!(agg.failed_count, 1);
        assert_eq!(agg.latency_us, 110);
    }
}
