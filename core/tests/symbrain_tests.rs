// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! Unit tests for the SymBrain cognitive engine components.

use agora_core::symbrain::*;
use std::time::Duration;

// ── PFC Router Tests ──

#[test]
fn test_pfc_router_math_query() {
    let mut router = PFCRouter::new();
    let (tensor, category, complexity) =
        router.route("prove the convergence of the eigenvalue sequence for the Hermitian matrix").unwrap();

    assert_eq!(category, STEMCategory::Mathematics);
    assert!(tensor.respects_floor());
    assert!(tensor.total() <= 1.0 + f64::EPSILON);
    assert!(complexity.value() > 0.0);
}

#[test]
fn test_pfc_router_physics_query() {
    let mut router = PFCRouter::new();
    let (_, category, _) =
        router.route("derive the Hamiltonian for quantum harmonic oscillator").unwrap();

    // Should detect physics (hamiltonian, quantum)
    assert!(
        category == STEMCategory::Physics || category == STEMCategory::Mathematics,
        "expected Physics or Mathematics, got {category:?}"
    );
}

#[test]
fn test_pfc_router_simple_query() {
    let mut router = PFCRouter::new();
    let (tensor, _, complexity) = router.route("what is 2+2").unwrap();

    assert!(complexity.value() < 0.5, "simple query should have low complexity");
    assert!(tensor.sigma_ded >= RoutingTensor::DEDUCTIVE_FLOOR);
}

#[test]
fn test_logistic_multiplier_range() {
    let router = PFCRouter::new();
    // At C=0 (lowest complexity)
    let mult_low = router.logistic_multiplier(0.0);
    // At C=1 (highest complexity)
    let mult_high = router.logistic_multiplier(1.0);

    // Multiplier should be ≥ 1.0 and increase with complexity
    assert!(mult_low >= 1.0);
    assert!(mult_high >= 1.0);
    assert!(mult_high > mult_low, "multiplier should increase with complexity");
}

// ── Dynamic Gating Tests ──

#[test]
fn test_gating_monotonicity_dense() {
    let gate = GatingGirdle::default_config();
    // Test with 10,000 samples
    assert!(gate.verify_monotonicity(10_000));
}

#[test]
fn test_gating_full_spectrum() {
    let gate = GatingGirdle::default_config();
    let mut prev_ded = 0.0;

    for i in 0..=100 {
        let c = i as f64 / 100.0;
        let (ded, gen_val, mcts) = gate.compute_full_gating(c).unwrap();

        // All components non-negative
        assert!(ded >= 0.0);
        assert!(gen_val >= 0.0);
        assert!(mcts >= 0.0);

        // Components sum to 1.0
        let sum = ded + gen_val + mcts;
        assert!(
            (sum - 1.0).abs() < 1e-10,
            "sum at C={c} is {sum}"
        );

        // Deductive floor
        assert!(ded >= 0.30 - f64::EPSILON, "floor violated at C={c}");

        // Strict monotonicity of σ_ded
        if i > 0 {
            assert!(
                ded > prev_ded,
                "monotonicity violated: f({}) = {} <= f({}) = {}",
                c,
                ded,
                (i - 1) as f64 / 100.0,
                prev_ded
            );
        }
        prev_ded = ded;
    }
}

// ── Early Stopping Tests ──

#[test]
fn test_early_stopping_workflow() {
    let mut policy = EarlyStopPolicy::default();

    // Simulate 3 search steps
    for step in 0..3 {
        policy.begin_step();

        // Simulate children with varying visit counts
        let children = vec![
            (0, 50 + step * 10, 0.4),
            (1, 100 + step * 20, 0.6),
            (2, 30 + step * 5, 0.8),
        ];

        let result = policy.end_step(&children).unwrap();
        // Action 1 should always win (highest visit count)
        assert_eq!(result.action, 1);
    }

    assert_eq!(policy.steps_executed(), 3);
}

#[test]
fn test_early_stopping_selects_most_visited() {
    let mut policy = EarlyStopPolicy::default();
    policy.begin_step();

    // Child with highest value (0.99) but low visits should NOT be selected
    // Child with highest visits (1000) should be selected
    let children = vec![
        (0, 1000, 0.3),  // most visited
        (1, 10, 0.99),   // highest value but undersampled
        (2, 500, 0.5),
    ];

    let result = policy.end_step(&children).unwrap();
    assert_eq!(result.action, 0, "should select most visited, not highest value");
    assert_eq!(result.visit_count, 1000);
}

#[test]
fn test_time_slice_budget() {
    let slice = TimeSlice::default_500ms();
    assert_eq!(slice.budget, Duration::from_millis(500));
}
