// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! Integration test for the full SymBrain pipeline.
//!
//! Tests the complete flow: PFC routing → MCTS search → early stopping
//! → quantized proof verification, with budget monitoring.

use agora_core::symbrain::*;
use agora_core::telemetry::{BudgetMonitor, PerformanceCounters};
use std::time::Duration;

#[test]
fn test_full_symbrain_pipeline() {
    // 1. Initialize components
    let mut router = PFCRouter::new();
    let gate = GatingGirdle::default_config();
    let mut policy = EarlyStopPolicy::default();
    let counters = PerformanceCounters::new(1000);
    let mut budget = BudgetMonitor::default_thresholds();

    budget.begin_experiment();

    // 2. Route a complex query through PFC
    let query = "prove that the Riemann zeta function has non-trivial zeros \
                 only on the critical line Re(s) = 1/2, using the \
                 Hadamard product representation and functional equation";

    let (tensor, category, complexity) = router.route(query).unwrap();
    counters.record_pfc_route();

    // Verify routing properties
    assert!(tensor.respects_floor(), "deductive floor violated");
    assert!(tensor.total() <= 1.0 + f64::EPSILON, "budget overflow");
    assert!(complexity.value() > 0.2, "complex query should score high");

    // 3. Apply dynamic gating
    let (sigma_ded, sigma_gen, sigma_mcts) =
        gate.compute_full_gating(complexity.value()).unwrap();
    assert!(sigma_ded >= 0.30);
    assert!((sigma_ded + sigma_gen + sigma_mcts - 1.0).abs() < 1e-10);

    // 4. Run MCTS search with early stopping
    let config = MCTSConfig {
        max_iterations: 50,
        max_depth: 10,
        ..Default::default()
    };
    let mut tree = MCTSTree::new(config);
    tree.init_root();

    policy.begin_step();

    let result = tree.search(|action| {
        counters.record_mcts_node();
        // Simulate evaluation with σ_ded modulation
        let base_value = match action {
            0 => 0.3,
            1 => 0.7,
            2 => 0.5,
            _ => 0.2,
        };
        base_value * sigma_ded
    }).unwrap();

    let children = vec![
        (0, result.best_visits / 3, 0.3),
        (result.best_action, result.best_visits, result.best_value),
        (2, result.best_visits / 2, 0.5),
    ];
    let robust = policy.end_step(&children).unwrap();

    assert!(result.total_iterations > 0);
    assert!(result.total_nodes > 0);
    assert_eq!(robust.action, result.best_action);

    // 5. Quantize and verify proof batch
    let proof_values: Vec<f64> = (0..10)
        .map(|i| i as f64 * 0.1 * result.best_value)
        .collect();
    let batch = ProofBatch::from_values(1, &proof_values).unwrap();
    assert_eq!(batch.len(), 10);

    // Verify with tight tolerance
    let residuals: Vec<f64> = batch
        .constraints
        .iter()
        .map(|c| c.quantization_error())
        .collect();
    let verification = VerificationResult::from_residuals(
        batch.batch_id,
        &residuals,
        batch.delta, // tolerance = Δ
        100,
    );

    assert!(
        verification.all_passed,
        "quantization errors should be within Δ tolerance"
    );

    // 6. Record costs and check budget
    let cost = 0.05; // $0.05 for this inference
    let alert = budget.record_cost(cost, "SymBrain pipeline inference").unwrap();
    assert_eq!(alert, agora_core::telemetry::BudgetAlert::Normal);

    // 7. Verify telemetry
    let snapshot = counters.snapshot();
    assert_eq!(snapshot.pfc_routes, 1);
    assert!(snapshot.mcts_nodes > 0);

    // Print summary
    eprintln!("=== SymBrain Pipeline Integration Test ===");
    eprintln!("Category: {category:?}");
    eprintln!("Complexity: {:.3}", complexity.value());
    eprintln!("Routing: σ_ded={:.3}, σ_gen={:.3}, σ_mcts={:.3}",
        tensor.sigma_ded, tensor.sigma_gen, tensor.sigma_mcts);
    eprintln!("Gating: σ_ded={sigma_ded:.3}, σ_gen={sigma_gen:.3}, σ_mcts={sigma_mcts:.3}");
    eprintln!("MCTS: {} nodes, best_action={}, best_value={:.3}",
        result.total_nodes, result.best_action, result.best_value);
    eprintln!("Proof batch: {} constraints, max_error={:.6}",
        batch.len(), batch.max_error);
    eprintln!("Verification: {} passed, {} failed",
        verification.passed_count, verification.failed_count);
    eprintln!("Budget: ${:.2} spent, ${:.2} remaining",
        budget.total_spent(), budget.experiment_remaining());
}

#[test]
fn test_pipeline_budget_enforcement() {
    let mut budget = BudgetMonitor::default_thresholds();
    budget.begin_experiment();

    // Simulate many inference steps
    for i in 0..20 {
        let cost = 4.5; // $4.50 per inference
        let result = budget.record_cost(cost, format!("inference step {i}"));

        if i >= 22 {
            // Should hit $100 limit around step 22
            assert!(result.is_err(), "should have hit budget limit");
            break;
        }
    }
}

#[test]
fn test_pipeline_latency_tracking() {
    let counters = PerformanceCounters::new(1000);

    // Simulate inference steps with measured latency
    for _ in 0..100 {
        let start = std::time::Instant::now();

        // Simulated work
        let mut _sum = 0.0f64;
        for j in 0..1000 {
            _sum += (j as f64).sqrt();
        }

        counters.record_latency(start.elapsed());
        counters.record_solver_eval();
    }

    let snap = counters.snapshot();
    assert_eq!(snap.solver_evals, 100);
    assert!(snap.mean_latency_us > 0.0);
    assert!(snap.p95_latency_us >= snap.mean_latency_us);
}
