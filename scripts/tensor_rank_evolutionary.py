#!/usr/bin/env python3
"""
Evolutionary Search for Tensor Rank Decomposition of ⟨4,4,4⟩
=============================================================

(1+λ) Evolutionary Strategy targeting rank-47 decomposition of the
4×4 matrix multiplication tensor T ∈ ℝ^{16×16×16}.

Known bounds:
  - Bläser lower bound: R(⟨4,4,4⟩) ≥ 28 (proven algebraic bound)
  - Refined lower bound: R(⟨4,4,4⟩) ≥ ~34 (Landsberg-Michalek substitution method)
  - Strassen-type: R(⟨4,4,4⟩) ≤ 49 (Strassen's original recursive)
  - AlphaEvolve/AlphaTensor: R(⟨4,4,4⟩) ≤ 48 (best known decomposition)

This experiment attempts to find R=47 by evolutionary search.
"""

import json
import os
import time
import numpy as np
from datetime import datetime


# ─────────────────── Configuration ───────────────────

LAMBDA = 50          # offspring per generation
MU = 10              # parents (elitist selection)
CROSSOVER_PROB = 0.2
SEED = 42

# Mutation probabilities (must sum to 1.0)
P_GAUSSIAN = 0.3
P_SWAP = 0.1
P_RESET = 0.1
P_GRADIENT = 0.3
P_SPARSIFY = 0.1
P_SIGNFLIP = 0.1

# Adaptive sigma
SIGMA_INIT = 0.5
SIGMA_MIN = 0.005
SIGMA_MAX = 2.0
SIGMA_DECAY = 0.95
SIGMA_BOOST = 2.0
STALL_THRESHOLD = 50  # generations without improvement before boosting

# Phase configuration: (rank, generations, description)
PHASES = [
    (48, 500, "Validate: find rank-48 decomposition"),
    (47, 2000, "Main target: search for rank-47"),
    (46, 1000, "Stretch goal: search for rank-46"),
]

OUTPUT_DIR = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/output/tensor_rank_search"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "evolutionary_results.json")
PRINT_EVERY = 50


# ─────────────────── Tensor Construction ───────────────────

def build_matrix_mult_tensor(n: int) -> np.ndarray:
    """
    Build the matrix multiplication tensor ⟨n,n,n⟩.

    T ∈ ℝ^{n²×n²×n²} encodes: (AB)_{ik} = Σ_j A_{ij} B_{jk}

    Index mapping: matrix entry (i,j) → flat index i*n + j
    T[a, b, c] = 1 iff a=(i,j), b=(j,k), c=(i,k) for some i,j,k
    """
    N = n * n
    T = np.zeros((N, N, N), dtype=np.float64)
    for i in range(n):
        for j in range(n):
            for k in range(n):
                a = i * n + j  # A_{ij}
                b = j * n + k  # B_{jk}
                c = i * n + k  # C_{ik} = (AB)_{ik}
                T[a, b, c] = 1.0
    return T


def verify_tensor(T: np.ndarray, n: int) -> bool:
    """Verify the tensor has the expected properties."""
    N = n * n
    assert T.shape == (N, N, N), f"Shape mismatch: {T.shape}"
    assert np.sum(T) == n**3, f"Non-zero count: {np.sum(T)} != {n**3}"
    return True


# ─────────────────── Fitness ───────────────────

def compute_reconstruction(U: np.ndarray, V: np.ndarray, W: np.ndarray) -> np.ndarray:
    """Compute T_hat = Σ_r u_r ⊗ v_r ⊗ w_r via einsum."""
    return np.einsum('ir,jr,kr->ijk', U, V, W)


def fitness(U: np.ndarray, V: np.ndarray, W: np.ndarray, T: np.ndarray) -> float:
    """Frobenius norm squared of residual: ‖T - T_hat‖²_F"""
    T_hat = compute_reconstruction(U, V, W)
    residual = T - T_hat
    return float(np.sum(residual ** 2))


def component_contributions(U: np.ndarray, V: np.ndarray, W: np.ndarray) -> np.ndarray:
    """
    Compute the 'contribution' of each rank-1 component.
    Defined as ‖u_r‖ · ‖v_r‖ · ‖w_r‖ (product of norms).
    """
    R = U.shape[1]
    contribs = np.zeros(R)
    for r in range(R):
        contribs[r] = np.linalg.norm(U[:, r]) * np.linalg.norm(V[:, r]) * np.linalg.norm(W[:, r])
    return contribs


# ─────────────────── Mutation Operators ───────────────────

def mutate_gaussian(U, V, W, sigma, rng):
    """Add Gaussian noise N(0, σ) to all entries."""
    Uc = U + rng.normal(0, sigma, U.shape)
    Vc = V + rng.normal(0, sigma, V.shape)
    Wc = W + rng.normal(0, sigma, W.shape)
    return Uc, Vc, Wc


def mutate_swap(U, V, W, rng):
    """Swap two rank-1 components entirely."""
    R = U.shape[1]
    if R < 2:
        return U.copy(), V.copy(), W.copy()
    i, j = rng.choice(R, size=2, replace=False)
    Uc, Vc, Wc = U.copy(), V.copy(), W.copy()
    Uc[:, [i, j]] = Uc[:, [j, i]]
    Vc[:, [i, j]] = Vc[:, [j, i]]
    Wc[:, [i, j]] = Wc[:, [j, i]]
    return Uc, Vc, Wc


def mutate_reset(U, V, W, rng, T):
    """Replace the worst component (smallest contribution) with a random one."""
    N = U.shape[0]
    contribs = component_contributions(U, V, W)
    worst = np.argmin(contribs)
    scale = 1.0 / np.sqrt(N)
    Uc, Vc, Wc = U.copy(), V.copy(), W.copy()
    Uc[:, worst] = rng.normal(0, scale, N)
    Vc[:, worst] = rng.normal(0, scale, N)
    Wc[:, worst] = rng.normal(0, scale, N)
    return Uc, Vc, Wc


def mutate_gradient(U, V, W, T, lr=0.01, n_components=3):
    """
    Targeted gradient descent step for the worst n_components.

    Gradient of ‖T - T_hat‖²_F w.r.t. U[:, r]:
        ∂L/∂U[:, r] = -2 * R_{(1)} · (W[:, r] ⊗ V[:, r])
    where R_{(1)} is mode-1 unfolding of residual, and ⊗ is Khatri-Rao product.
    We use the direct elementwise approach for clarity.
    """
    N = U.shape[0]
    R = U.shape[1]
    residual = T - compute_reconstruction(U, V, W)

    contribs = component_contributions(U, V, W)
    worst_indices = np.argsort(contribs)[:n_components]

    Uc, Vc, Wc = U.copy(), V.copy(), W.copy()

    for r in worst_indices:
        # Gradient for U[:, r]: -2 * Σ_{j,k} residual[i,j,k] * V[j,r] * W[k,r]
        grad_u = -2.0 * np.einsum('ijk,jr,kr->i', residual, V[:, r:r+1], W[:, r:r+1]).ravel()
        # Gradient for V[:, r]
        grad_v = -2.0 * np.einsum('ijk,ir,kr->j', residual, U[:, r:r+1], W[:, r:r+1]).ravel()
        # Gradient for W[:, r]
        grad_w = -2.0 * np.einsum('ijk,ir,jr->k', residual, U[:, r:r+1], V[:, r:r+1]).ravel()

        # Clip gradients for stability
        grad_u = np.clip(grad_u, -10, 10)
        grad_v = np.clip(grad_v, -10, 10)
        grad_w = np.clip(grad_w, -10, 10)

        Uc[:, r] -= lr * grad_u
        Vc[:, r] -= lr * grad_v
        Wc[:, r] -= lr * grad_w

    return Uc, Vc, Wc


def mutate_sparsify(U, V, W, threshold=0.05):
    """Zero out entries with |value| < threshold."""
    Uc = U.copy()
    Vc = V.copy()
    Wc = W.copy()
    Uc[np.abs(Uc) < threshold] = 0.0
    Vc[np.abs(Vc) < threshold] = 0.0
    Wc[np.abs(Wc) < threshold] = 0.0
    return Uc, Vc, Wc


def mutate_signflip(U, V, W, rng):
    """Randomly flip signs of all three factor vectors in one component."""
    R = U.shape[1]
    r = rng.integers(0, R)
    Uc, Vc, Wc = U.copy(), V.copy(), W.copy()
    # Flip signs on U and V (net effect preserved in W)
    # Actually flip one of them randomly for diversity
    which = rng.integers(0, 3)
    if which == 0:
        Uc[:, r] *= -1
        Vc[:, r] *= -1
    elif which == 1:
        Vc[:, r] *= -1
        Wc[:, r] *= -1
    else:
        Uc[:, r] *= -1
        Wc[:, r] *= -1
    return Uc, Vc, Wc


def apply_mutation(U, V, W, sigma, T, rng):
    """Apply one randomly chosen mutation operator."""
    roll = rng.random()
    cumulative = 0.0

    cumulative += P_GAUSSIAN
    if roll < cumulative:
        return mutate_gaussian(U, V, W, sigma, rng)

    cumulative += P_SWAP
    if roll < cumulative:
        return mutate_swap(U, V, W, rng)

    cumulative += P_RESET
    if roll < cumulative:
        return mutate_reset(U, V, W, rng, T)

    cumulative += P_GRADIENT
    if roll < cumulative:
        return mutate_gradient(U, V, W, T)

    cumulative += P_SPARSIFY
    if roll < cumulative:
        return mutate_sparsify(U, V, W)

    # SIGNFLIP (remainder)
    return mutate_signflip(U, V, W, rng)


# ─────────────────── Crossover ───────────────────

def crossover(parent_a, parent_b, rng):
    """Uniform crossover: for each component, pick from parent A or B."""
    Ua, Va, Wa = parent_a
    Ub, Vb, Wb = parent_b
    R = Ua.shape[1]

    Uc = Ua.copy()
    Vc = Va.copy()
    Wc = Wa.copy()

    for r in range(R):
        if rng.random() < 0.5:
            Uc[:, r] = Ub[:, r]
            Vc[:, r] = Vb[:, r]
            Wc[:, r] = Wb[:, r]

    return Uc, Vc, Wc


# ─────────────────── Initialization ───────────────────

def init_random(N: int, R: int, rng) -> tuple:
    """Initialize with Gaussian N(0, 1/√N)."""
    scale = 1.0 / np.sqrt(N)
    U = rng.normal(0, scale, (N, R))
    V = rng.normal(0, scale, (N, R))
    W = rng.normal(0, scale, (N, R))
    return U, V, W


def init_from_reduction(best_solution: tuple, target_rank: int, rng, sigma_perturb=0.1) -> tuple:
    """
    Initialize for lower rank by dropping the weakest component
    from a higher-rank solution and perturbing.
    """
    U, V, W = best_solution
    current_rank = U.shape[1]

    if target_rank >= current_rank:
        # Just perturb
        return (
            U.copy() + rng.normal(0, sigma_perturb, U.shape),
            V.copy() + rng.normal(0, sigma_perturb, V.shape),
            W.copy() + rng.normal(0, sigma_perturb, W.shape),
        )

    # Drop weakest components
    contribs = component_contributions(U, V, W)
    keep = np.argsort(contribs)[::-1][:target_rank]  # keep strongest

    Ur = U[:, keep].copy() + rng.normal(0, sigma_perturb, (U.shape[0], target_rank))
    Vr = V[:, keep].copy() + rng.normal(0, sigma_perturb, (V.shape[0], target_rank))
    Wr = W[:, keep].copy() + rng.normal(0, sigma_perturb, (W.shape[0], target_rank))

    return Ur, Vr, Wr


# ─────────────────── Main Evolution Loop ───────────────────

def run_phase(T, R, n_gens, description, prev_best=None, rng=None):
    """
    Run one phase of the evolutionary search.

    Returns: (best_fitness, best_solution, history)
    """
    N = T.shape[0]  # 16 for ⟨4,4,4⟩
    print(f"\n{'='*70}")
    print(f"Phase: {description}")
    print(f"Target rank: R={R}, Generations: {n_gens}")
    print(f"Population: λ={LAMBDA}, Parents: μ={MU}")
    print(f"{'='*70}")

    # Initialize population
    population = []
    for i in range(LAMBDA):
        if prev_best is not None and i < MU:
            # Seed some individuals from previous best
            ind = init_from_reduction(prev_best, R, rng, sigma_perturb=0.1 + 0.05 * i)
        elif prev_best is not None and i < LAMBDA // 2:
            # More aggressive perturbation
            ind = init_from_reduction(prev_best, R, rng, sigma_perturb=0.3 + 0.1 * rng.random())
        else:
            # Random initialization
            ind = init_random(N, R, rng)
        population.append(ind)

    # Evaluate initial population
    fitnesses = [fitness(U, V, W, T) for U, V, W in population]

    # Sort and select parents
    sorted_idx = np.argsort(fitnesses)
    parents = [population[i] for i in sorted_idx[:MU]]
    parent_fits = [fitnesses[i] for i in sorted_idx[:MU]]

    best_fit = parent_fits[0]
    best_sol = parents[0]
    best_gen = 0

    sigma = SIGMA_INIT
    stall_count = 0

    history = {
        "generations": [],
        "best_fitness_trace": [],
        "sigma_trace": [],
    }

    t_start = time.time()

    for gen in range(1, n_gens + 1):
        # Generate offspring
        offspring = []
        for _ in range(LAMBDA):
            # Select parent
            p_idx = rng.integers(0, MU)
            parent = parents[p_idx]

            # Optional crossover
            if rng.random() < CROSSOVER_PROB and MU > 1:
                p2_idx = rng.integers(0, MU)
                while p2_idx == p_idx:
                    p2_idx = rng.integers(0, MU)
                child = crossover(parent, parents[p2_idx], rng)
            else:
                child = (parent[0].copy(), parent[1].copy(), parent[2].copy())

            # Mutation
            child = apply_mutation(child[0], child[1], child[2], sigma, T, rng)
            offspring.append(child)

        # Evaluate offspring
        off_fits = [fitness(U, V, W, T) for U, V, W in offspring]

        # Combine parents + offspring, select top MU
        combined = list(zip(parent_fits, parents)) + list(zip(off_fits, offspring))
        combined.sort(key=lambda x: x[0])
        parent_fits = [x[0] for x in combined[:MU]]
        parents = [x[1] for x in combined[:MU]]

        # Update best
        if parent_fits[0] < best_fit:
            improvement = best_fit - parent_fits[0]
            best_fit = parent_fits[0]
            best_sol = parents[0]
            best_gen = gen
            stall_count = 0
            sigma *= SIGMA_DECAY  # reduce noise on improvement
        else:
            stall_count += 1

        # Adaptive sigma
        if stall_count >= STALL_THRESHOLD:
            sigma = min(sigma * SIGMA_BOOST, SIGMA_MAX)
            stall_count = 0
            # Also inject some fresh random individuals
            for i in range(min(3, MU)):
                fresh = init_random(N, R, rng)
                idx = MU - 1 - i
                parents[idx] = fresh
                parent_fits[idx] = fitness(fresh[0], fresh[1], fresh[2], T)

        sigma = max(sigma, SIGMA_MIN)

        # Record history periodically
        if gen % PRINT_EVERY == 0 or gen == 1 or gen == n_gens:
            elapsed = time.time() - t_start
            history["generations"].append(gen)
            history["best_fitness_trace"].append(float(best_fit))
            history["sigma_trace"].append(float(sigma))

            # Relative error
            T_norm_sq = float(np.sum(T ** 2))
            rel_err = best_fit / T_norm_sq if T_norm_sq > 0 else float('inf')

            print(
                f"  Gen {gen:5d} | Best: {best_fit:12.6f} | "
                f"Rel: {rel_err:.2e} | σ: {sigma:.4f} | "
                f"Mean: {np.mean(parent_fits):12.4f} | "
                f"Time: {elapsed:.1f}s"
            )

    elapsed_total = time.time() - t_start

    # Final analysis
    T_norm_sq = float(np.sum(T ** 2))
    rel_err = best_fit / T_norm_sq
    reconstruction = compute_reconstruction(best_sol[0], best_sol[1], best_sol[2])
    max_entry_error = float(np.max(np.abs(T - reconstruction)))

    print(f"\n  Phase complete in {elapsed_total:.1f}s")
    print(f"  Best fitness: {best_fit:.8f}")
    print(f"  Relative error: {rel_err:.2e}")
    print(f"  Max entry error: {max_entry_error:.6f}")
    print(f"  Best found at generation: {best_gen}")

    # Check if we found an exact decomposition (within tolerance)
    is_exact = best_fit < 1e-6
    if is_exact:
        print(f"  *** EXACT DECOMPOSITION FOUND (fitness < 1e-6) ***")
    is_near = best_fit < 0.1
    if is_near and not is_exact:
        print(f"  *** NEAR decomposition (fitness < 0.1) ***")

    result = {
        "rank": R,
        "description": description,
        "best_fitness": float(best_fit),
        "relative_error": float(rel_err),
        "max_entry_error": float(max_entry_error),
        "best_generation": best_gen,
        "total_generations": n_gens,
        "elapsed_seconds": elapsed_total,
        "is_exact": is_exact,
        "is_near": is_near,
        "final_sigma": float(sigma),
        "history": history,
    }

    return best_fit, best_sol, result


def main():
    print("=" * 70)
    print("Evolutionary Tensor Rank Decomposition Search")
    print("Target: ⟨4,4,4⟩ matrix multiplication tensor")
    print("=" * 70)
    print()

    # Known bounds reference
    print("Known bounds for R(⟨4,4,4⟩):")
    print("  Lower: R ≥ 28   (Bläser 1999, algebraic)")
    print("  Lower: R ≥ ~34  (Landsberg-Michalek, substitution method)")
    print("  Upper: R ≤ 49   (Strassen recursive)")
    print("  Upper: R ≤ 48   (AlphaEvolve / AlphaTensor, best known)")
    print(f"  This search targets: R = 47")
    print()

    # Build tensor
    n = 4
    N = n * n  # 16
    T = build_matrix_mult_tensor(n)
    verify_tensor(T, n)
    T_norm_sq = float(np.sum(T ** 2))

    print(f"Tensor shape: {T.shape}")
    print(f"Non-zero entries: {int(np.sum(T != 0))}")
    print(f"‖T‖²_F = {T_norm_sq}")
    print(f"Population: λ={LAMBDA}, Parents: μ={MU}")
    print(f"Mutation: σ_init={SIGMA_INIT}, decay={SIGMA_DECAY}, boost@stall={SIGMA_BOOST}")
    print()

    rng = np.random.default_rng(SEED)
    all_results = []
    prev_best = None
    t_global = time.time()

    for rank, n_gens, desc in PHASES:
        best_fit, best_sol, result = run_phase(
            T, rank, n_gens, desc, prev_best=prev_best, rng=rng
        )
        all_results.append(result)
        prev_best = best_sol

        # If we found an exact R=48 decomposition, great foundation
        # If we found exact R=47, that's a breakthrough
        if result["is_exact"] and rank <= 47:
            print(f"\n{'*'*70}")
            print(f"BREAKTHROUGH: Exact rank-{rank} decomposition found!")
            print(f"This would improve the best known upper bound.")
            print(f"{'*'*70}\n")

    total_time = time.time() - t_global

    # Summary
    print(f"\n{'='*70}")
    print("EXPERIMENT SUMMARY")
    print(f"{'='*70}")
    print(f"Total runtime: {total_time:.1f}s ({total_time/60:.1f} min)")
    print()
    print(f"{'Rank':>6} | {'Best Fitness':>14} | {'Rel Error':>12} | {'Exact?':>7} | {'Time (s)':>10}")
    print("-" * 65)
    for r in all_results:
        print(
            f"  R={r['rank']:2d} | {r['best_fitness']:14.6f} | "
            f"{r['relative_error']:12.2e} | {'YES' if r['is_exact'] else 'no':>7} | "
            f"{r['elapsed_seconds']:10.1f}"
        )
    print()

    # Interpretation
    r48 = all_results[0]
    r47 = all_results[1] if len(all_results) > 1 else None
    r46 = all_results[2] if len(all_results) > 2 else None

    print("Interpretation:")
    if r48["is_exact"]:
        print(f"  ✓ R=48: Exact decomposition found (validates AlphaEvolve result)")
    else:
        print(f"  ✗ R=48: No exact decomposition found (residual={r48['best_fitness']:.6f})")
        print(f"    Note: evolutionary search may need more generations or better initialization")

    if r47 and r47["is_exact"]:
        print(f"  ★ R=47: EXACT DECOMPOSITION FOUND!")
        print(f"    This would be a new upper bound: R(⟨4,4,4⟩) ≤ 47")
    elif r47:
        gap = r47["best_fitness"] - (0 if r48["is_exact"] else r48["best_fitness"])
        print(f"  ✗ R=47: No exact decomposition (residual={r47['best_fitness']:.6f})")
        print(f"    Minimum relative error: {r47['relative_error']:.2e}")

    if r46 and r46["is_exact"]:
        print(f"  ★ R=46: EXACT DECOMPOSITION FOUND!")
    elif r46:
        print(f"  ✗ R=46: No exact decomposition (residual={r46['best_fitness']:.6f})")

    # Save results
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output = {
        "experiment": "evolutionary_tensor_rank_search",
        "tensor": "⟨4,4,4⟩ matrix multiplication",
        "tensor_shape": [N, N, N],
        "tensor_frobenius_norm_sq": T_norm_sq,
        "algorithm": "(1+λ) Evolutionary Strategy",
        "parameters": {
            "lambda": LAMBDA,
            "mu": MU,
            "crossover_prob": CROSSOVER_PROB,
            "sigma_init": SIGMA_INIT,
            "sigma_decay": SIGMA_DECAY,
            "sigma_boost": SIGMA_BOOST,
            "stall_threshold": STALL_THRESHOLD,
            "seed": SEED,
            "mutation_probs": {
                "gaussian": P_GAUSSIAN,
                "swap": P_SWAP,
                "reset": P_RESET,
                "gradient": P_GRADIENT,
                "sparsify": P_SPARSIFY,
                "signflip": P_SIGNFLIP,
            },
        },
        "known_bounds": {
            "blaser_lower": 28,
            "landsberg_michalek_lower": 34,
            "strassen_upper": 49,
            "alphaevolve_upper": 48,
        },
        "phases": all_results,
        "total_runtime_seconds": total_time,
        "timestamp": datetime.now().isoformat(),
    }

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {OUTPUT_FILE}")
    print("Done.")


if __name__ == "__main__":
    main()
