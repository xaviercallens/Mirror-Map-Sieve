// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! Tests for the scientific solvers: Robertson, Lorenz, Lotka-Volterra.

use agora_solvers::sundials::*;
use agora_solvers::physics::conservation::*;

// ── Robertson Tests ──

#[test]
fn test_robertson_initial_conditions() {
    let y0 = robertson::RobertsonSystem::initial_conditions();
    assert_eq!(y0.len(), 3);
    assert!((y0.iter().sum::<f64>() - 1.0).abs() < f64::EPSILON);
}

#[test]
fn test_robertson_rhs_derivatives() {
    let sys = robertson::RobertsonSystem::new();
    let rhs = sys.rhs_fn();

    // At t=0, y = [1, 0, 0]:
    // dy1 = -0.04*1 + 1e4*0*0 = -0.04
    // dy2 = 0.04*1 - 1e4*0*0 - 3e7*0 = 0.04
    // dy3 = 3e7*0 = 0
    let dy = rhs(0.0, &[1.0, 0.0, 0.0]).unwrap();
    assert!((dy[0] + 0.04).abs() < 1e-12);
    assert!((dy[1] - 0.04).abs() < 1e-12);
    assert!((dy[2]).abs() < 1e-12);

    // Conservation: dy1 + dy2 + dy3 = 0
    let sum: f64 = dy.iter().sum();
    assert!(sum.abs() < 1e-10, "RHS should conserve mass: sum = {sum}");
}

#[test]
fn test_robertson_solve_and_conservation() {
    let sys = robertson::RobertsonSystem::new();
    let mut solver = sys.create_solver().unwrap();

    let (t, y) = solver.solve(0.4).unwrap();
    assert!((t - 0.4).abs() < 1e-4);

    // Mass conservation
    robertson::RobertsonSystem::check_conservation(&y, 1e-2).unwrap();

    // y1 should decrease, y2 and y3 should increase
    assert!(y[0] < 1.0, "y1 should decrease");
    assert!(y[0] > 0.0, "y1 should remain positive");
}

#[test]
fn test_robertson_stiffness() {
    let sys = robertson::RobertsonSystem::new();
    let ratio = sys.stiffness_ratio();
    // k3/k1 = 3e7 / 0.04 = 7.5e8
    assert!(ratio > 1e8, "stiffness ratio should be extreme");
}

// ── Lorenz Tests ──

#[test]
fn test_lorenz_equilibria_are_fixed_points() {
    let sys = lorenz::LorenzSystem::new();
    let rhs = sys.rhs_fn();

    for eq in sys.equilibria() {
        let dy = rhs(0.0, &eq).unwrap();
        let norm: f64 = dy.iter().map(|v| v * v).sum::<f64>().sqrt();
        assert!(
            norm < 1e-8,
            "equilibrium {:?} is not a fixed point: |f| = {norm}",
            eq
        );
    }
}

#[test]
fn test_lorenz_solve_bounded() {
    let sys = lorenz::LorenzSystem::new();
    let mut solver = sys.create_solver().unwrap();

    let (t, y) = solver.solve(5.0).unwrap();
    assert!((t - 5.0).abs() < 1e-4);

    // Lorenz attractor should remain bounded
    lorenz::LorenzSystem::check_bounded(&y, t).unwrap();

    // State should be non-trivial (not at origin)
    let norm: f64 = y.iter().map(|v| v * v).sum::<f64>().sqrt();
    assert!(norm > 1.0, "solution should be on the attractor, not at origin");
}

#[test]
fn test_lorenz_energy() {
    let y = [10.0, 15.0, 25.0];
    let e = lorenz::LorenzSystem::energy(&y, 10.0, 28.0);
    // E = 100 + 225 + (25 - 38)^2 = 100 + 225 + 169 = 494
    assert!((e - 494.0).abs() < 1e-8);
}

// ── Lotka-Volterra Tests ──

#[test]
fn test_lotka_volterra_equilibrium_is_fixed_point() {
    let sys = lotka_volterra::LotkaVolterraSystem::new();
    let (x_eq, y_eq) = sys.equilibrium();

    let rhs = sys.rhs_fn();
    let dy = rhs(0.0, &[x_eq, y_eq]).unwrap();

    assert!(
        dy[0].abs() < 1e-10,
        "dx/dt at equilibrium should be ~0, got {}",
        dy[0]
    );
    assert!(
        dy[1].abs() < 1e-10,
        "dy/dt at equilibrium should be ~0, got {}",
        dy[1]
    );
}

#[test]
fn test_lotka_volterra_hamiltonian_conservation() {
    let sys = lotka_volterra::LotkaVolterraSystem::new();
    let x0 = 10.0;
    let y0 = 5.0;
    let mut solver = sys.create_solver(x0, y0).unwrap();

    let h0 = sys.hamiltonian(x0, y0);
    let (_, y) = solver.solve(5.0).unwrap();
    let h1 = sys.hamiltonian(y[0], y[1]);

    let drift = (h1 - h0).abs() / h0.abs();
    assert!(
        drift < 0.01,
        "Hamiltonian drift = {drift:.6} should be < 1%"
    );
}

#[test]
fn test_lotka_volterra_populations_positive() {
    let sys = lotka_volterra::LotkaVolterraSystem::new();
    let mut solver = sys.create_solver(10.0, 5.0).unwrap();

    // Solve through multiple oscillation periods
    let (t, y) = solver.solve(20.0).unwrap();
    lotka_volterra::LotkaVolterraSystem::check_physical(&y, t).unwrap();
}

// ── Conservation Validator Tests ──

#[test]
fn test_robertson_with_conservation_validator() {
    let sys = robertson::RobertsonSystem::new();
    let mut solver = sys.create_solver().unwrap();

    // Set up conservation validator
    let mut validator = ConservationValidator::new();
    validator.register(ConservationLaw::Mass, mass_conservation(), 1e-2);
    validator.initialize(&robertson::RobertsonSystem::initial_conditions());

    let (_, y) = solver.solve(0.4).unwrap();
    let results = validator.check_strict(&y).unwrap();

    assert!(results[0].passed, "mass conservation should hold");
}

// ── CVODE Bridge Tests ──

#[test]
fn test_cvode_harmonic_oscillator() {
    // dx/dt = v, dv/dt = -x → simple harmonic motion
    // x(0) = 1, v(0) = 0 → x(t) = cos(t), v(t) = -sin(t)
    use agora_solvers::sundials::cvode_bridge::*;

    let rhs: RhsFn = Box::new(|_t, y| {
        Ok(vec![y[1], -y[0]]) // dx=v, dv=-x
    });

    let config = CVodeConfig {
        method: SolverMethod::Adams,
        rtol: 1e-10,
        atol: 1e-12,
        ..Default::default()
    };

    let mut solver = CVodeSolver::new(config, vec![1.0, 0.0], 0.0, rhs).unwrap();
    let (t, y) = solver.solve(std::f64::consts::PI).unwrap();

    // At t=π: x = cos(π) = -1, v = -sin(π) = 0
    assert!((t - std::f64::consts::PI).abs() < 1e-6);
    assert!(
        (y[0] + 1.0).abs() < 1e-2,
        "x(π) should ≈ -1, got {}",
        y[0]
    );
    assert!(
        y[1].abs() < 0.1,
        "v(π) should ≈ 0, got {}",
        y[1]
    );
}
