// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Prefrontal Cortex Router
//!
//! Biomimetic 3-stage classifier inspired by the prefrontal cortex,
//! producing a routing tensor σ = (σ_ded, σ_gen, σ_mcts) that governs
//! which cognitive sub-systems process each query.
//!
//! ## Three Stages
//!
//! 1. **Lexical STEM scanner** — fast keyword/regex pass to identify STEM domain
//! 2. **Semantic complexity classifier** — estimates complexity C ∈ [0, 1]
//! 3. **Dynamic MCTS estimator** — allocates MCTS budget via logistic sigmoid
//!
//! ## Invariants
//!
//! - Deductive floor: σ_ded ≥ 0.30 (always preserves formal reasoning)
//! - Routing tensor components sum ≤ 1.0 (remaining budget is idle)
//! - Logistic multiplier: Mult = 1.0 + 7.0 / (1.0 + e^(-6.0(C − 0.45)))

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors produced by the PFC router.
#[derive(Debug, Error)]
pub enum PFCError {
    /// Complexity score is outside the valid [0, 1] range.
    #[error("complexity score {0} is outside valid range [0, 1]")]
    InvalidComplexity(f64),

    /// Routing tensor components exceed unit budget.
    #[error("routing tensor sum {0} exceeds 1.0")]
    BudgetOverflow(f64),
}

/// STEM domain classification from the lexical scanner.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum STEMCategory {
    /// Pure mathematics, theorem proving, formal logic.
    Mathematics,
    /// Physics, mechanics, electrodynamics.
    Physics,
    /// Chemistry, molecular dynamics, reaction kinetics.
    Chemistry,
    /// Biology, genomics, proteomics.
    Biology,
    /// Computer science, algorithms, complexity theory.
    ComputerScience,
    /// Engineering, materials science, control systems.
    Engineering,
    /// General or unclassified query.
    General,
}

/// Complexity score C ∈ [0, 1] estimated by the semantic classifier.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct ComplexityScore {
    /// Raw complexity value in [0, 1].
    value: f64,
    /// Number of distinct reasoning steps detected.
    reasoning_steps: u32,
    /// Whether the query requires multi-hop inference.
    multi_hop: bool,
}

impl ComplexityScore {
    /// Creates a new complexity score, clamping to [0, 1].
    pub fn new(value: f64, reasoning_steps: u32, multi_hop: bool) -> Self {
        Self {
            value: value.clamp(0.0, 1.0),
            reasoning_steps,
            multi_hop,
        }
    }

    /// Returns the raw complexity value.
    pub fn value(&self) -> f64 {
        self.value
    }

    /// Returns the number of detected reasoning steps.
    pub fn reasoning_steps(&self) -> u32 {
        self.reasoning_steps
    }

    /// Returns whether multi-hop inference is required.
    pub fn multi_hop(&self) -> bool {
        self.multi_hop
    }
}

/// Routing tensor σ = (σ_ded, σ_gen, σ_mcts).
///
/// Each component represents the fraction of cognitive budget allocated
/// to the corresponding sub-system. The sum must be ≤ 1.0.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct RoutingTensor {
    /// Deductive reasoning allocation (floor: 0.30).
    pub sigma_ded: f64,
    /// Generative reasoning allocation.
    pub sigma_gen: f64,
    /// MCTS search allocation.
    pub sigma_mcts: f64,
}

impl RoutingTensor {
    /// Deductive floor — σ_ded is never below this value.
    pub const DEDUCTIVE_FLOOR: f64 = 0.30;

    /// Creates a new routing tensor, enforcing the deductive floor.
    ///
    /// # Errors
    ///
    /// Returns [`PFCError::BudgetOverflow`] if components sum exceeds 1.0.
    pub fn new(sigma_ded: f64, sigma_gen: f64, sigma_mcts: f64) -> Result<Self, PFCError> {
        let sigma_ded = sigma_ded.max(Self::DEDUCTIVE_FLOOR);
        let sum = sigma_ded + sigma_gen + sigma_mcts;
        if sum > 1.0 + f64::EPSILON {
            return Err(PFCError::BudgetOverflow(sum));
        }
        Ok(Self {
            sigma_ded,
            sigma_gen,
            sigma_mcts,
        })
    }

    /// Returns the sum of all routing components.
    pub fn total(&self) -> f64 {
        self.sigma_ded + self.sigma_gen + self.sigma_mcts
    }

    /// Returns true if the deductive floor is respected.
    pub fn respects_floor(&self) -> bool {
        self.sigma_ded >= Self::DEDUCTIVE_FLOOR - f64::EPSILON
    }
}

/// STEM keyword sets for lexical scanning.
const MATH_KEYWORDS: &[&str] = &[
    "theorem", "proof", "lemma", "integral", "derivative", "topology",
    "algebra", "manifold", "eigenvalue", "convergence", "isomorphism",
    "polynomial", "matrix", "determinant", "vector space", "group theory",
];

const PHYSICS_KEYWORDS: &[&str] = &[
    "quantum", "relativity", "entropy", "hamiltonian", "lagrangian",
    "thermodynamic", "electrodynamic", "momentum", "gravitational",
    "schrödinger", "maxwell", "boltzmann", "photon", "boson", "fermion",
];

const CHEMISTRY_KEYWORDS: &[&str] = &[
    "reaction", "catalyst", "molecule", "oxidation", "reduction",
    "kinetics", "equilibrium", "stoichiometry", "enthalpy", "orbital",
    "covalent", "ionic", "polymer", "spectroscopy", "chromatography",
];

const BIOLOGY_KEYWORDS: &[&str] = &[
    "protein", "gene", "dna", "rna", "enzyme", "cell", "mitosis",
    "genome", "transcription", "ribosome", "phylogenetic", "mutation",
    "phenotype", "genotype", "metabolic", "proteomic", "genomic",
];

const CS_KEYWORDS: &[&str] = &[
    "algorithm", "complexity", "np-hard", "turing", "automaton",
    "compiler", "recursion", "graph theory", "hash", "cryptography",
    "neural network", "backpropagation", "gradient descent", "transformer",
];

/// Prefrontal Cortex Router — the central decision-making module.
///
/// Classifies incoming queries through a 3-stage pipeline and produces
/// a [`RoutingTensor`] that governs cognitive resource allocation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PFCRouter {
    /// Logistic sigmoid inflection point.
    sigmoid_center: f64,
    /// Logistic sigmoid steepness.
    sigmoid_steepness: f64,
    /// Maximum multiplier amplitude.
    max_amplitude: f64,
    /// Number of queries routed.
    queries_routed: u64,
}

impl Default for PFCRouter {
    fn default() -> Self {
        Self::new()
    }
}

impl PFCRouter {
    /// Creates a new PFC router with default parameters.
    ///
    /// Default logistic sigmoid: Mult = 1.0 + 7.0 / (1.0 + e^(-6.0(C − 0.45)))
    pub fn new() -> Self {
        Self {
            sigmoid_center: 0.45,
            sigmoid_steepness: 6.0,
            max_amplitude: 7.0,
            queries_routed: 0,
        }
    }

    /// Creates a PFC router with custom sigmoid parameters.
    pub fn with_params(center: f64, steepness: f64, amplitude: f64) -> Self {
        Self {
            sigmoid_center: center,
            sigmoid_steepness: steepness,
            max_amplitude: amplitude,
            queries_routed: 0,
        }
    }

    /// Stage 1: Lexical STEM scanner.
    ///
    /// Performs a fast keyword-based scan to classify the query domain.
    pub fn scan_stem_category(&self, query: &str) -> STEMCategory {
        let lower = query.to_lowercase();

        let scores = [
            (STEMCategory::Mathematics, Self::keyword_score(&lower, MATH_KEYWORDS)),
            (STEMCategory::Physics, Self::keyword_score(&lower, PHYSICS_KEYWORDS)),
            (STEMCategory::Chemistry, Self::keyword_score(&lower, CHEMISTRY_KEYWORDS)),
            (STEMCategory::Biology, Self::keyword_score(&lower, BIOLOGY_KEYWORDS)),
            (STEMCategory::ComputerScience, Self::keyword_score(&lower, CS_KEYWORDS)),
        ];

        scores
            .iter()
            .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
            .filter(|(_, score)| *score > 0)
            .map(|(cat, _)| *cat)
            .unwrap_or(STEMCategory::General)
    }

    /// Stage 2: Semantic complexity classifier.
    ///
    /// Estimates complexity C ∈ [0, 1] from query features including
    /// length, vocabulary richness, and detected reasoning patterns.
    pub fn estimate_complexity(&self, query: &str) -> ComplexityScore {
        let words: Vec<&str> = query.split_whitespace().collect();
        let word_count = words.len();

        // Length contribution (longer queries tend to be more complex)
        let length_score = (word_count as f64 / 100.0).min(0.4);

        // Vocabulary richness (unique words / total words)
        let unique: std::collections::HashSet<&str> = words.iter().copied().collect();
        let richness = if word_count > 0 {
            unique.len() as f64 / word_count as f64
        } else {
            0.0
        };
        let richness_score = richness * 0.3;

        // Reasoning pattern detection
        let reasoning_patterns = [
            "therefore", "implies", "if and only if", "such that",
            "for all", "there exists", "prove that", "show that",
            "derive", "demonstrate", "contradiction", "induction",
        ];
        let lower = query.to_lowercase();
        let reasoning_hits = reasoning_patterns
            .iter()
            .filter(|p| lower.contains(*p))
            .count();
        let reasoning_score = (reasoning_hits as f64 * 0.1).min(0.3);

        let multi_hop = reasoning_hits >= 2 || word_count > 50;

        let value = (length_score + richness_score + reasoning_score).clamp(0.0, 1.0);
        ComplexityScore::new(value, reasoning_hits as u32, multi_hop)
    }

    /// Stage 3: Compute the routing tensor via logistic sigmoid.
    ///
    /// Logistic multiplier: `Mult = 1.0 + 7.0 / (1.0 + e^(-6.0(C − 0.45)))`
    ///
    /// The multiplier scales the MCTS allocation; higher complexity
    /// queries receive more search budget.
    ///
    /// # Errors
    ///
    /// Returns [`PFCError::InvalidComplexity`] if C is outside [0, 1].
    pub fn route(&mut self, query: &str) -> Result<(RoutingTensor, STEMCategory, ComplexityScore), PFCError> {
        let category = self.scan_stem_category(query);
        let complexity = self.estimate_complexity(query);
        let c = complexity.value();

        if !(0.0..=1.0).contains(&c) {
            return Err(PFCError::InvalidComplexity(c));
        }

        // Logistic sigmoid multiplier
        let mult = self.logistic_multiplier(c);

        // Base allocations
        let base_ded = RoutingTensor::DEDUCTIVE_FLOOR;
        let base_mcts = 0.10 * mult;
        let remaining = (1.0 - base_ded - base_mcts).max(0.0);
        let sigma_gen = remaining * 0.6;
        let sigma_mcts = base_mcts.min(1.0 - base_ded - sigma_gen);

        let tensor = RoutingTensor::new(base_ded, sigma_gen, sigma_mcts)?;
        self.queries_routed += 1;

        tracing::info!(
            category = ?category,
            complexity = c,
            multiplier = mult,
            sigma_ded = tensor.sigma_ded,
            sigma_gen = tensor.sigma_gen,
            sigma_mcts = tensor.sigma_mcts,
            "PFC routing decision"
        );

        Ok((tensor, category, complexity))
    }

    /// Computes the logistic sigmoid multiplier.
    ///
    /// `Mult = 1.0 + max_amplitude / (1.0 + e^(-steepness * (C - center)))`
    pub fn logistic_multiplier(&self, c: f64) -> f64 {
        let exponent = -self.sigmoid_steepness * (c - self.sigmoid_center);
        1.0 + self.max_amplitude / (1.0 + exponent.exp())
    }

    /// Returns the total number of queries routed.
    pub fn queries_routed(&self) -> u64 {
        self.queries_routed
    }

    /// Counts keyword matches in the query.
    fn keyword_score(query: &str, keywords: &[&str]) -> usize {
        keywords.iter().filter(|kw| query.contains(*kw)).count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deductive_floor() {
        let tensor = RoutingTensor::new(0.10, 0.20, 0.10).unwrap();
        assert!(tensor.sigma_ded >= RoutingTensor::DEDUCTIVE_FLOOR);
    }

    #[test]
    fn test_budget_overflow() {
        let result = RoutingTensor::new(0.50, 0.40, 0.20);
        assert!(result.is_err());
    }

    #[test]
    fn test_stem_classification() {
        let router = PFCRouter::new();
        assert_eq!(
            router.scan_stem_category("prove the theorem about eigenvalue convergence"),
            STEMCategory::Mathematics
        );
        assert_eq!(
            router.scan_stem_category("quantum entanglement and entropy"),
            STEMCategory::Physics
        );
    }

    #[test]
    fn test_logistic_multiplier() {
        let router = PFCRouter::new();
        // At C = 0.45 (center), multiplier ≈ 1.0 + 7.0/2.0 = 4.5
        let mult = router.logistic_multiplier(0.45);
        assert!((mult - 4.5).abs() < 0.01);
    }

    #[test]
    fn test_routing() {
        let mut router = PFCRouter::new();
        let (tensor, cat, _) = router.route("prove the theorem").unwrap();
        assert!(tensor.respects_floor());
        assert!(tensor.total() <= 1.0 + f64::EPSILON);
        assert_eq!(cat, STEMCategory::Mathematics);
        assert_eq!(router.queries_routed(), 1);
    }
}
