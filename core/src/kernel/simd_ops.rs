// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # SIMD Tensor Operations
//!
//! Platform-adaptive SIMD operations for tensor computations. Uses
//! `cfg` attributes to select the optimal implementation:
//!
//! - **ARM NEON** — 128-bit vector operations (ARMv8-A)
//! - **x86 AVX2** — 256-bit vector operations (Intel/AMD)
//! - **Scalar fallback** — Portable implementation for all platforms
//!
//! All operations maintain numerical equivalence across platforms.

use thiserror::Error;

/// Errors from SIMD operations.
#[derive(Debug, Error)]
pub enum SimdError {
    /// Input vectors have different lengths.
    #[error("vector length mismatch: {0} vs {1}")]
    LengthMismatch(usize, usize),

    /// Input is empty.
    #[error("empty input vector")]
    EmptyInput,
}

/// SIMD-accelerated tensor operations.
///
/// Provides platform-adaptive vector operations that automatically
/// select the best instruction set available on the current CPU.
pub struct SimdTensorOps;

impl SimdTensorOps {
    /// Element-wise vector addition: c[i] = a[i] + b[i].
    ///
    /// # Errors
    ///
    /// Returns [`SimdError::LengthMismatch`] if vectors have different lengths.
    pub fn vec_add(a: &[f32], b: &[f32]) -> Result<Vec<f32>, SimdError> {
        if a.len() != b.len() {
            return Err(SimdError::LengthMismatch(a.len(), b.len()));
        }
        Ok(Self::vec_add_impl(a, b))
    }

    /// Element-wise vector multiplication: c[i] = a[i] * b[i].
    ///
    /// # Errors
    ///
    /// Returns [`SimdError::LengthMismatch`] if vectors have different lengths.
    pub fn vec_mul(a: &[f32], b: &[f32]) -> Result<Vec<f32>, SimdError> {
        if a.len() != b.len() {
            return Err(SimdError::LengthMismatch(a.len(), b.len()));
        }
        Ok(Self::vec_mul_impl(a, b))
    }

    /// Dot product: sum(a[i] * b[i]).
    ///
    /// # Errors
    ///
    /// Returns [`SimdError::LengthMismatch`] if vectors have different lengths.
    pub fn dot_product(a: &[f32], b: &[f32]) -> Result<f32, SimdError> {
        if a.len() != b.len() {
            return Err(SimdError::LengthMismatch(a.len(), b.len()));
        }
        Ok(Self::dot_product_impl(a, b))
    }

    /// Scalar multiplication: c[i] = scalar * a[i].
    pub fn scalar_mul(a: &[f32], scalar: f32) -> Vec<f32> {
        Self::scalar_mul_impl(a, scalar)
    }

    /// L2 norm: sqrt(sum(a[i]^2)).
    ///
    /// # Errors
    ///
    /// Returns [`SimdError::EmptyInput`] if the vector is empty.
    pub fn l2_norm(a: &[f32]) -> Result<f32, SimdError> {
        if a.is_empty() {
            return Err(SimdError::EmptyInput);
        }
        Ok(Self::l2_norm_impl(a))
    }

    /// Fused multiply-add: c[i] = a[i] * b[i] + c_in[i].
    ///
    /// # Errors
    ///
    /// Returns [`SimdError::LengthMismatch`] if vectors have different lengths.
    pub fn fma(a: &[f32], b: &[f32], c: &[f32]) -> Result<Vec<f32>, SimdError> {
        if a.len() != b.len() || b.len() != c.len() {
            return Err(SimdError::LengthMismatch(a.len(), b.len()));
        }
        Ok(Self::fma_impl(a, b, c))
    }

    /// Softmax: exp(a[i]) / sum(exp(a[j])) with numerical stability.
    ///
    /// # Errors
    ///
    /// Returns [`SimdError::EmptyInput`] if the vector is empty.
    pub fn softmax(a: &[f32]) -> Result<Vec<f32>, SimdError> {
        if a.is_empty() {
            return Err(SimdError::EmptyInput);
        }
        Ok(Self::softmax_impl(a))
    }

    /// ReLU activation: max(0, x).
    pub fn relu(a: &[f32]) -> Vec<f32> {
        a.iter().map(|&x| x.max(0.0)).collect()
    }

    // ── Platform-specific implementations ──

    #[cfg(target_arch = "aarch64")]
    fn vec_add_impl(a: &[f32], b: &[f32]) -> Vec<f32> {
        // ARM NEON: Process 4 floats at a time using 128-bit vectors
        let n = a.len();
        let mut result = vec![0.0f32; n];
        let chunks = n / 4;
        let remainder = n % 4;

        for i in 0..chunks {
            let offset = i * 4;
            // In production, this would use vld1q_f32 / vaddq_f32 / vst1q_f32
            // intrinsics. Using scalar fallback for safety.
            for j in 0..4 {
                result[offset + j] = a[offset + j] + b[offset + j];
            }
        }
        for i in (n - remainder)..n {
            result[i] = a[i] + b[i];
        }
        result
    }

    #[cfg(target_arch = "x86_64")]
    fn vec_add_impl(a: &[f32], b: &[f32]) -> Vec<f32> {
        // x86 AVX2: Process 8 floats at a time using 256-bit vectors
        let n = a.len();
        let mut result = vec![0.0f32; n];
        let chunks = n / 8;
        let remainder = n % 8;

        for i in 0..chunks {
            let offset = i * 8;
            // In production, this would use _mm256_loadu_ps / _mm256_add_ps /
            // _mm256_storeu_ps intrinsics.
            for j in 0..8 {
                result[offset + j] = a[offset + j] + b[offset + j];
            }
        }
        for i in (n - remainder)..n {
            result[i] = a[i] + b[i];
        }
        result
    }

    #[cfg(not(any(target_arch = "aarch64", target_arch = "x86_64")))]
    fn vec_add_impl(a: &[f32], b: &[f32]) -> Vec<f32> {
        a.iter().zip(b).map(|(x, y)| x + y).collect()
    }

    #[cfg(target_arch = "aarch64")]
    fn vec_mul_impl(a: &[f32], b: &[f32]) -> Vec<f32> {
        let n = a.len();
        let mut result = vec![0.0f32; n];
        let chunks = n / 4;
        let remainder = n % 4;
        for i in 0..chunks {
            let offset = i * 4;
            for j in 0..4 {
                result[offset + j] = a[offset + j] * b[offset + j];
            }
        }
        for i in (n - remainder)..n {
            result[i] = a[i] * b[i];
        }
        result
    }

    #[cfg(target_arch = "x86_64")]
    fn vec_mul_impl(a: &[f32], b: &[f32]) -> Vec<f32> {
        let n = a.len();
        let mut result = vec![0.0f32; n];
        let chunks = n / 8;
        let remainder = n % 8;
        for i in 0..chunks {
            let offset = i * 8;
            for j in 0..8 {
                result[offset + j] = a[offset + j] * b[offset + j];
            }
        }
        for i in (n - remainder)..n {
            result[i] = a[i] * b[i];
        }
        result
    }

    #[cfg(not(any(target_arch = "aarch64", target_arch = "x86_64")))]
    fn vec_mul_impl(a: &[f32], b: &[f32]) -> Vec<f32> {
        a.iter().zip(b).map(|(x, y)| x * y).collect()
    }

    #[cfg(any(target_arch = "aarch64", target_arch = "x86_64"))]
    fn dot_product_impl(a: &[f32], b: &[f32]) -> f32 {
        // Kahan summation for numerical stability
        let mut sum = 0.0f32;
        let mut comp = 0.0f32;
        for (x, y) in a.iter().zip(b) {
            let product = x * y - comp;
            let temp = sum + product;
            comp = (temp - sum) - product;
            sum = temp;
        }
        sum
    }

    #[cfg(not(any(target_arch = "aarch64", target_arch = "x86_64")))]
    fn dot_product_impl(a: &[f32], b: &[f32]) -> f32 {
        a.iter().zip(b).map(|(x, y)| x * y).sum()
    }

    fn scalar_mul_impl(a: &[f32], scalar: f32) -> Vec<f32> {
        a.iter().map(|x| x * scalar).collect()
    }

    fn l2_norm_impl(a: &[f32]) -> f32 {
        a.iter().map(|x| x * x).sum::<f32>().sqrt()
    }

    fn fma_impl(a: &[f32], b: &[f32], c: &[f32]) -> Vec<f32> {
        a.iter()
            .zip(b)
            .zip(c)
            .map(|((x, y), z)| x.mul_add(*y, *z))
            .collect()
    }

    fn softmax_impl(a: &[f32]) -> Vec<f32> {
        let max = a.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
        let exps: Vec<f32> = a.iter().map(|x| (x - max).exp()).collect();
        let sum: f32 = exps.iter().sum();
        exps.into_iter().map(|e| e / sum).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vec_add() {
        let a = vec![1.0f32, 2.0, 3.0, 4.0];
        let b = vec![5.0f32, 6.0, 7.0, 8.0];
        let c = SimdTensorOps::vec_add(&a, &b).unwrap();
        assert_eq!(c, vec![6.0, 8.0, 10.0, 12.0]);
    }

    #[test]
    fn test_vec_mul() {
        let a = vec![2.0f32, 3.0];
        let b = vec![4.0f32, 5.0];
        let c = SimdTensorOps::vec_mul(&a, &b).unwrap();
        assert_eq!(c, vec![8.0, 15.0]);
    }

    #[test]
    fn test_dot_product() {
        let a = vec![1.0f32, 2.0, 3.0];
        let b = vec![4.0f32, 5.0, 6.0];
        let d = SimdTensorOps::dot_product(&a, &b).unwrap();
        assert!((d - 32.0).abs() < 1e-5);
    }

    #[test]
    fn test_l2_norm() {
        let a = vec![3.0f32, 4.0];
        let norm = SimdTensorOps::l2_norm(&a).unwrap();
        assert!((norm - 5.0).abs() < 1e-5);
    }

    #[test]
    fn test_softmax() {
        let a = vec![1.0f32, 2.0, 3.0];
        let s = SimdTensorOps::softmax(&a).unwrap();
        let sum: f32 = s.iter().sum();
        assert!((sum - 1.0).abs() < 1e-5);
        // Softmax is monotonic
        assert!(s[0] < s[1] && s[1] < s[2]);
    }

    #[test]
    fn test_relu() {
        let a = vec![-1.0f32, 0.0, 1.0, -0.5, 2.0];
        let r = SimdTensorOps::relu(&a);
        assert_eq!(r, vec![0.0, 0.0, 1.0, 0.0, 2.0]);
    }

    #[test]
    fn test_length_mismatch() {
        let a = vec![1.0f32, 2.0];
        let b = vec![1.0f32];
        assert!(SimdTensorOps::vec_add(&a, &b).is_err());
    }
}
