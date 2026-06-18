// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0
//
// High-Performance Ramsey Search in Rust
// =======================================
//
// PERFORMANCE GOAL: ~10M-100M steps/second on a single core
// (vs ~50 steps/s in Python with delta evaluation)
//
// KEY OPTIMIZATIONS:
// 1. Adjacency matrix stored as bitsets for O(1) neighbor queries
// 2. Delta evaluation: only recheck cliques containing the flipped edge
// 3. Pre-computed edge-to-vertex mapping for O(1) lookup
// 4. SIMD-friendly data layout (planned)
// 5. Release mode: LTO + single codegen unit
//
// TARGETS:
// - R(4,6) ∈ [36, 41] — primary target
// - R(3,10) — secondary target (triangle + K10)
// - R(3,13) ≥ 62 — stretch goal

use clap::Parser;
use rand::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs;
use std::time::Instant;

/// High-performance Ramsey number search
#[derive(Parser, Debug)]
#[command(author, version, about)]
struct Args {
    /// Red clique size (s in R(s,t))
    #[arg(short, long, default_value_t = 4)]
    s: usize,

    /// Blue clique size (t in R(s,t))
    #[arg(short, long, default_value_t = 6)]
    t: usize,

    /// Start vertex count
    #[arg(long, default_value_t = 35)]
    n_start: usize,

    /// End vertex count
    #[arg(long, default_value_t = 42)]
    n_end: usize,

    /// Max SA steps per trial
    #[arg(long, default_value_t = 50_000_000)]
    steps: usize,

    /// Number of trials per n
    #[arg(long, default_value_t = 20)]
    trials: usize,

    /// Initial SA temperature
    #[arg(long, default_value_t = 5.0)]
    t_start: f64,

    /// Final SA temperature
    #[arg(long, default_value_t = 0.0001)]
    t_end: f64,

    /// Output file
    #[arg(short, long, default_value = "ramsey_results.json")]
    output: String,
}

#[derive(Serialize, Deserialize, Clone)]
struct SearchResult {
    n: usize,
    s: usize,
    t: usize,
    success: bool,
    violations: i64,
    trial: usize,
    step: usize,
    elapsed_s: f64,
    steps_per_sec: f64,
    method: String,
    coloring: Option<Vec<u8>>,
}

/// Graph coloring for Ramsey search
struct RamseyGraph {
    n: usize,
    s: usize,
    t: usize,
    num_edges: usize,
    // Edge colors: 0 = red, 1 = blue
    coloring: Vec<u8>,
    // Adjacency lists per color: adj[color][v] is a bitset of neighbors
    // Using u64 bitsets (supports up to n=64 vertices)
    adj_red: Vec<u64>,   // adj_red[v] = bitset of red neighbors of v
    adj_blue: Vec<u64>,  // adj_blue[v] = bitset of blue neighbors of v
    // Edge index mapping
    edge_to_verts: Vec<(usize, usize)>,
    edge_index: Vec<Vec<usize>>, // edge_index[u][v] = flat index (u < v)
    // Current violation count
    violations: i64,
}

impl RamseyGraph {
    fn new(n: usize, s: usize, t: usize) -> Self {
        let num_edges = n * (n - 1) / 2;
        let coloring = vec![0u8; num_edges];

        let mut edge_to_verts = Vec::with_capacity(num_edges);
        let mut edge_index = vec![vec![0usize; n]; n];

        let mut idx = 0;
        for u in 0..n {
            for v in (u + 1)..n {
                edge_to_verts.push((u, v));
                edge_index[u][v] = idx;
                edge_index[v][u] = idx;
                idx += 1;
            }
        }

        // Initially all edges are red (color 0)
        let adj_red = vec![0u64; n]; // Will be set in init
        let adj_blue = vec![0u64; n];

        let mut g = RamseyGraph {
            n,
            s,
            t,
            num_edges,
            coloring,
            adj_red,
            adj_blue,
            edge_to_verts,
            edge_index,
            violations: 0,
        };

        // Initialize adjacency bitsets
        g.rebuild_adjacency();
        g.violations = g.count_violations_full();
        g
    }

    fn rebuild_adjacency(&mut self) {
        self.adj_red = vec![0u64; self.n];
        self.adj_blue = vec![0u64; self.n];
        for (idx, &(u, v)) in self.edge_to_verts.iter().enumerate() {
            if self.coloring[idx] == 0 {
                self.adj_red[u] |= 1u64 << v;
                self.adj_red[v] |= 1u64 << u;
            } else {
                self.adj_blue[u] |= 1u64 << v;
                self.adj_blue[v] |= 1u64 << u;
            }
        }
    }

    /// Count all violations — O(C(n,s) + C(n,t))
    fn count_violations_full(&self) -> i64 {
        let mut count = 0i64;

        // Red K_s violations
        count += self.count_cliques_of_color(self.s, 0);
        // Blue K_t violations
        count += self.count_cliques_of_color(self.t, 1);

        count
    }

    /// Count monochromatic cliques of given size and color using bitset intersection
    fn count_cliques_of_color(&self, k: usize, color: u8) -> i64 {
        let adj = if color == 0 { &self.adj_red } else { &self.adj_blue };
        let mut count = 0i64;

        // Recursive clique enumeration with bitset pruning
        let all_vertices: u64 = (1u64 << self.n) - 1;
        self.enumerate_cliques(adj, k, 0, all_vertices, &mut count);

        count
    }

    fn enumerate_cliques(
        &self,
        adj: &[u64],
        remaining: usize,
        min_vertex: usize,
        candidates: u64,
        count: &mut i64,
    ) {
        if remaining == 0 {
            *count += 1;
            return;
        }

        let mut cands = candidates & !((1u64 << min_vertex) - 1); // only vertices >= min_vertex

        while cands != 0 {
            let v = cands.trailing_zeros() as usize;
            if v >= self.n {
                break;
            }
            // Next vertex must be adjacent to v in the given color
            let new_candidates = candidates & adj[v];
            self.enumerate_cliques(adj, remaining - 1, v + 1, new_candidates, count);
            cands &= !(1u64 << v);
        }
    }

    /// Delta evaluation: change in violations when flipping edge (u,v)
    /// Only checks cliques containing BOTH u and v
    fn delta_flip(&self, u: usize, v: usize, old_color: u8, new_color: u8) -> i64 {
        let mut delta = 0i64;

        // For red (color 0) K_s: check (s-2)-cliques in common red neighbors of u,v
        // that DON'T include u or v
        let red_common = self.adj_red[u] & self.adj_red[v] & !((1u64 << u) | (1u64 << v));
        let blue_common = self.adj_blue[u] & self.adj_blue[v] & !((1u64 << u) | (1u64 << v));

        if self.s >= 2 {
            // Count (s-2)-cliques in red_common (all-red neighbors of both u and v)
            let red_cliques = self.count_cliques_in_set(&self.adj_red, self.s - 2, red_common);
            // If old_color was red (0), these were violations. If new_color is red, they become violations.
            if old_color == 0 {
                delta -= red_cliques;
            }
            if new_color == 0 {
                delta += red_cliques;
            }
        }

        if self.t >= 2 {
            // Count (t-2)-cliques in blue_common
            let blue_cliques = self.count_cliques_in_set(&self.adj_blue, self.t - 2, blue_common);
            if old_color == 1 {
                delta -= blue_cliques;
            }
            if new_color == 1 {
                delta += blue_cliques;
            }
        }

        delta
    }

    /// Count cliques of given size within a vertex set, using adjacency for the given color
    fn count_cliques_in_set(&self, adj: &[u64], k: usize, vertex_set: u64) -> i64 {
        if k == 0 {
            return 1;
        }
        let mut count = 0i64;
        let mut remaining = vertex_set;
        while remaining != 0 {
            let v = remaining.trailing_zeros() as usize;
            if v >= self.n {
                break;
            }
            let new_set = remaining & adj[v] & !((1u64 << (v + 1)) - 1); // vertices > v that are adj
            // Actually we need vertices in vertex_set that are > v and adjacent to v
            let new_set = remaining & adj[v] & !(((1u64 << (v + 1)) - 1));
            self.count_cliques_recursive(adj, k - 1, new_set, &mut count);
            remaining &= !(1u64 << v);
        }
        count
    }

    fn count_cliques_recursive(&self, adj: &[u64], remaining: usize, candidates: u64, count: &mut i64) {
        if remaining == 0 {
            *count += 1;
            return;
        }
        let mut cands = candidates;
        while cands != 0 {
            let v = cands.trailing_zeros() as usize;
            if v >= self.n {
                break;
            }
            let new_cands = cands & adj[v] & !((1u64 << (v + 1)) - 1);
            self.count_cliques_recursive(adj, remaining - 1, new_cands, count);
            cands &= !(1u64 << v);
        }
    }

    /// Apply a color flip and update adjacency + violations
    fn flip_edge(&mut self, edge_idx: usize, new_color: u8) {
        let (u, v) = self.edge_to_verts[edge_idx];
        let old_color = self.coloring[edge_idx];

        if old_color == new_color {
            return;
        }

        // Compute delta BEFORE modifying
        let delta = self.delta_flip(u, v, old_color, new_color);

        // Update coloring
        self.coloring[edge_idx] = new_color;

        // Update adjacency bitsets
        if old_color == 0 {
            self.adj_red[u] &= !(1u64 << v);
            self.adj_red[v] &= !(1u64 << u);
        } else {
            self.adj_blue[u] &= !(1u64 << v);
            self.adj_blue[v] &= !(1u64 << u);
        }
        if new_color == 0 {
            self.adj_red[u] |= 1u64 << v;
            self.adj_red[v] |= 1u64 << u;
        } else {
            self.adj_blue[u] |= 1u64 << v;
            self.adj_blue[v] |= 1u64 << u;
        }

        self.violations += delta;
    }

    /// Undo a flip (restore old color)
    fn unflip_edge(&mut self, edge_idx: usize, old_color: u8) {
        self.flip_edge(edge_idx, old_color);
    }

    /// Initialize with Paley graph coloring
    fn init_paley(&mut self) {
        let n = self.n;
        // Find prime p >= n with p ≡ 1 (mod 4)
        let mut p = n;
        loop {
            if p % 4 == 1 && is_prime(p) {
                break;
            }
            p += 1;
            if p > n + 100 {
                return; // No suitable prime found, keep current coloring
            }
        }

        // Quadratic residues mod p
        let mut qr = vec![false; p];
        for x in 1..p {
            qr[(x * x) % p] = true;
        }

        // Assign colors
        for (idx, &(u, v)) in self.edge_to_verts.iter().enumerate() {
            let diff = if v > u { v - u } else { u - v };
            let d = diff % p;
            self.coloring[idx] = if qr[d] { 0 } else { 1 };
        }

        self.rebuild_adjacency();
        self.violations = self.count_violations_full();
    }

    /// Initialize with random coloring
    fn init_random(&mut self, rng: &mut impl Rng) {
        for c in self.coloring.iter_mut() {
            *c = rng.gen_range(0..2);
        }
        self.rebuild_adjacency();
        self.violations = self.count_violations_full();
    }
}

fn is_prime(n: usize) -> bool {
    if n < 2 {
        return false;
    }
    if n < 4 {
        return true;
    }
    if n % 2 == 0 || n % 3 == 0 {
        return false;
    }
    let mut i = 5;
    while i * i <= n {
        if n % i == 0 || n % (i + 2) == 0 {
            return false;
        }
        i += 6;
    }
    true
}

/// Simulated Annealing search
fn sa_search(
    n: usize,
    s: usize,
    t: usize,
    max_steps: usize,
    num_trials: usize,
    t_start: f64,
    t_end: f64,
) -> SearchResult {
    let num_edges = n * (n - 1) / 2;
    let mut rng = thread_rng();

    println!(
        "\n{}\n  SA SEARCH: R({},{}) >= {}?  (K_{}, {} edges)\n  {} trials x {} steps\n{}",
        "=".repeat(60),
        s, t, n + 1, n, num_edges,
        num_trials, max_steps,
        "=".repeat(60)
    );

    let overall_start = Instant::now();
    let mut global_best_v = i64::MAX;
    let mut global_best_coloring: Option<Vec<u8>> = None;

    for trial in 0..num_trials {
        let mut graph = RamseyGraph::new(n, s, t);

        // Alternate initialization
        if trial % 2 == 0 {
            graph.init_paley();
        } else {
            graph.init_random(&mut rng);
        }

        let mut best_v = graph.violations;
        let mut best_coloring = graph.coloring.clone();
        let trial_start = Instant::now();

        for step in 0..max_steps {
            let progress = step as f64 / max_steps as f64;
            let temp = t_start * (t_end / t_start).powf(progress);

            // Random edge flip
            let edge = rng.gen_range(0..num_edges);
            let old_color = graph.coloring[edge];
            let new_color = 1 - old_color;

            // Compute delta
            let (u, v) = graph.edge_to_verts[edge];
            let delta = graph.delta_flip(u, v, old_color, new_color);

            // SA acceptance
            let accept = if delta <= 0 {
                true
            } else {
                rng.gen::<f64>() < (-delta as f64 / temp).exp()
            };

            if accept {
                graph.flip_edge(edge, new_color);

                if graph.violations < best_v {
                    best_v = graph.violations;
                    best_coloring = graph.coloring.clone();
                }

                if graph.violations == 0 {
                    let elapsed = overall_start.elapsed().as_secs_f64();
                    let rate = step as f64 / trial_start.elapsed().as_secs_f64();

                    // VERIFY — Lesson #6: always verify!
                    let verify_v = graph.count_violations_full();
                    if verify_v == 0 {
                        println!(
                            "  🎯 SOLUTION at trial {}, step {}! {:.1}s ({:.0} steps/s) — VERIFIED ✅",
                            trial, step, elapsed, rate
                        );
                        return SearchResult {
                            n, s, t,
                            success: true,
                            violations: 0,
                            trial,
                            step,
                            elapsed_s: elapsed,
                            steps_per_sec: rate,
                            method: "rust_sa_delta".to_string(),
                            coloring: Some(best_coloring),
                        };
                    } else {
                        eprintln!(
                            "  ⚠️ Delta bug! Claimed 0 but verify={}. Recalibrating...",
                            verify_v
                        );
                        graph.violations = verify_v;
                    }
                }
            }

            // Progress report
            if step % 5_000_000 == 0 && step > 0 {
                let elapsed = overall_start.elapsed().as_secs_f64();
                let rate = step as f64 / trial_start.elapsed().as_secs_f64();
                println!(
                    "    T{} S{:>10}: v={}, best={}, T={:.4}, {:.0} steps/s, {:.1}s",
                    trial, step, graph.violations, best_v, temp, rate, elapsed
                );
            }
        }

        if best_v < global_best_v {
            global_best_v = best_v;
            global_best_coloring = Some(best_coloring);
        }

        let elapsed = overall_start.elapsed().as_secs_f64();
        let rate = max_steps as f64 / trial_start.elapsed().as_secs_f64();
        println!(
            "  Trial {}: best={} (global={}), {:.0} steps/s, {:.1}s",
            trial, best_v, global_best_v, rate, elapsed
        );
    }

    let elapsed = overall_start.elapsed().as_secs_f64();
    SearchResult {
        n, s, t,
        success: false,
        violations: global_best_v,
        trial: num_trials,
        step: max_steps,
        elapsed_s: elapsed,
        steps_per_sec: (max_steps * num_trials) as f64 / elapsed,
        method: "rust_sa_delta".to_string(),
        coloring: global_best_coloring,
    }
}

fn main() {
    let args = Args::parse();

    println!("\n🦀 RUST RAMSEY SEARCH");
    println!("   Target: R({},{}) >= {} .. {}", args.s, args.t, args.n_start + 1, args.n_end + 1);
    println!("   Budget: {} trials x {} steps per n", args.trials, args.steps);
    println!("   Temp: {} -> {}", args.t_start, args.t_end);

    let mut results = Vec::new();
    let mut best_proven = args.n_start.saturating_sub(1);

    for n in args.n_start..=args.n_end {
        println!("\n{}", "#".repeat(70));
        println!("#  TARGET: K_{} -> R({},{}) >= {}", n, args.s, args.t, n + 1);
        println!("{}", "#".repeat(70));

        let result = sa_search(n, args.s, args.t, args.steps, args.trials, args.t_start, args.t_end);

        if result.success {
            best_proven = n;
            println!("\n  ✅ R({},{}) >= {} PROVEN!", args.s, args.t, n + 1);
        } else {
            println!("\n  ❌ K_{}: stuck at {} violations", n, result.violations);
            if result.violations > 50 {
                println!("  Too many violations — stopping.");
                results.push(result);
                break;
            }
        }

        results.push(result);
    }

    // Summary
    println!("\n{}", "=".repeat(70));
    println!("  SUMMARY: R({},{}) >= {}", args.s, args.t, best_proven + 1);
    println!("{}", "=".repeat(70));
    for r in &results {
        let status = if r.success { "✅" } else { "❌" };
        println!(
            "  n={}: {} v={} ({:.1}s, {:.0} steps/s)",
            r.n, status, r.violations, r.elapsed_s, r.steps_per_sec
        );
    }

    // Save results
    let output = serde_json::json!({
        "s": args.s,
        "t": args.t,
        "best_proven": best_proven + 1,
        "results": results,
    });

    fs::write(&args.output, serde_json::to_string_pretty(&output).unwrap())
        .expect("Failed to write output");
    println!("\n  Saved to {}", args.output);
}
