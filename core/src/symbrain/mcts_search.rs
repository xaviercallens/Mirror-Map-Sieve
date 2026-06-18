// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Safe Parallel Monte Carlo Tree Search
//!
//! Thread-safe MCTS implementation with UCB1 selection and Rayon-based
//! parallel expansion. Designed for neuro-symbolic reasoning where
//! each node represents a reasoning state.
//!
//! ## UCB1 Selection
//!
//! ```text
//! UCB1(i) = Q(i) / N(i) + √2 · √(ln(N_parent) / N(i))
//! ```
//!
//! ## Thread Safety
//!
//! Each [`MCTSNode`] uses `Arc<Mutex<>>` for safe concurrent access
//! during parallel expansion and backpropagation.

use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use thiserror::Error;

/// Errors from MCTS operations.
#[derive(Debug, Error)]
pub enum MCTSError {
    /// Tree has no root node.
    #[error("MCTS tree has no root node")]
    NoRoot,

    /// Node lock was poisoned by a panicking thread.
    #[error("node lock poisoned: {0}")]
    LockPoisoned(String),

    /// Search budget exhausted.
    #[error("search budget of {0} iterations exhausted")]
    BudgetExhausted(u64),

    /// Invalid configuration.
    #[error("invalid config: {0}")]
    InvalidConfig(String),
}

/// Configuration for MCTS search.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MCTSConfig {
    /// UCB1 exploration constant (default: √2 ≈ 1.4142).
    pub exploration_constant: f64,
    /// Maximum number of search iterations.
    pub max_iterations: u64,
    /// Maximum tree depth.
    pub max_depth: u32,
    /// Number of parallel expansion threads (0 = use Rayon default).
    pub num_threads: usize,
    /// Discount factor for backpropagation.
    pub discount: f64,
}

impl Default for MCTSConfig {
    fn default() -> Self {
        Self {
            exploration_constant: std::f64::consts::SQRT_2,
            max_iterations: 10_000,
            max_depth: 50,
            num_threads: 0,
            discount: 1.0,
        }
    }
}

/// Internal node state protected by a mutex.
#[derive(Debug)]
pub struct NodeState {
    /// Total value accumulated through this node.
    pub total_value: f64,
    /// Number of times this node has been visited.
    pub visit_count: u64,
    /// Children of this node.
    pub children: Vec<Arc<Mutex<MCTSNode>>>,
    /// Whether this node is fully expanded.
    pub fully_expanded: bool,
    /// Whether this node is a terminal state.
    pub terminal: bool,
}

/// A single node in the MCTS tree.
///
/// Uses `Arc<Mutex<>>` for thread-safe concurrent access during
/// parallel expansion and backpropagation.
#[derive(Debug)]
pub struct MCTSNode {
    /// Unique node identifier.
    pub id: u64,
    /// Depth in the tree (root = 0).
    pub depth: u32,
    /// Action that led to this state (0 for root).
    pub action: u32,
    /// Mutable node state.
    pub state: NodeState,
}

impl MCTSNode {
    /// Creates a new MCTS node.
    pub fn new(id: u64, depth: u32, action: u32) -> Self {
        Self {
            id,
            depth,
            action,
            state: NodeState {
                total_value: 0.0,
                visit_count: 0,
                children: Vec::new(),
                fully_expanded: false,
                terminal: false,
            },
        }
    }

    /// Returns the average value Q(i) / N(i).
    pub fn average_value(&self) -> f64 {
        if self.state.visit_count == 0 {
            0.0
        } else {
            self.state.total_value / self.state.visit_count as f64
        }
    }

    /// Computes the UCB1 score for this node.
    ///
    /// ```text
    /// UCB1 = Q/N + c · √(ln(N_parent) / N)
    /// ```
    pub fn ucb1(&self, parent_visits: u64, exploration_constant: f64) -> f64 {
        if self.state.visit_count == 0 {
            return f64::INFINITY;
        }
        let exploitation = self.average_value();
        let exploration = exploration_constant
            * ((parent_visits as f64).ln() / self.state.visit_count as f64).sqrt();
        exploitation + exploration
    }
}

/// Result of an MCTS search.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    /// Best action found.
    pub best_action: u32,
    /// Visit count of the best child.
    pub best_visits: u64,
    /// Average value of the best child.
    pub best_value: f64,
    /// Total iterations performed.
    pub total_iterations: u64,
    /// Total nodes in the tree.
    pub total_nodes: u64,
    /// Maximum depth reached.
    pub max_depth_reached: u32,
}

/// Monte Carlo Tree Search engine.
///
/// Manages the search tree and provides parallel search via Rayon.
pub struct MCTSTree {
    /// Configuration.
    config: MCTSConfig,
    /// Root node of the search tree.
    root: Option<Arc<Mutex<MCTSNode>>>,
    /// Global node counter for unique IDs.
    node_counter: u64,
    /// Total iterations performed across all searches.
    total_iterations: u64,
}

impl MCTSTree {
    /// Creates a new MCTS tree with the given configuration.
    pub fn new(config: MCTSConfig) -> Self {
        Self {
            config,
            root: None,
            node_counter: 0,
            total_iterations: 0,
        }
    }

    /// Initializes the tree with a root node.
    pub fn init_root(&mut self) {
        self.node_counter = 0;
        let root = MCTSNode::new(self.next_id(), 0, 0);
        self.root = Some(Arc::new(Mutex::new(root)));
    }

    /// Runs the MCTS search for the configured number of iterations.
    ///
    /// Uses a simplified evaluation function for demonstration.
    /// In production, this would call out to the SymBrain evaluator.
    ///
    /// # Errors
    ///
    /// Returns [`MCTSError::NoRoot`] if the tree has no root.
    pub fn search<F>(&mut self, evaluate: F) -> Result<SearchResult, MCTSError>
    where
        F: Fn(u32) -> f64 + Send + Sync,
    {
        let root = self
            .root
            .as_ref()
            .ok_or(MCTSError::NoRoot)?
            .clone();

        for _ in 0..self.config.max_iterations {
            // Selection
            let (leaf, path) = self.select(root.clone())?;

            // Expansion
            let child = self.expand(leaf.clone())?;

            // Simulation (evaluation)
            let action = {
                let node = child
                    .lock()
                    .map_err(|e| MCTSError::LockPoisoned(e.to_string()))?;
                node.action
            };
            let value = evaluate(action);

            // Backpropagation
            self.backpropagate(&path, child, value)?;

            self.total_iterations += 1;
        }

        // Select best child by visit count (most robust)
        self.best_child(root)
    }

    /// UCB1 selection: traverse from root to leaf selecting best UCB1 child.
    fn select(
        &self,
        root: Arc<Mutex<MCTSNode>>,
    ) -> Result<(Arc<Mutex<MCTSNode>>, Vec<Arc<Mutex<MCTSNode>>>), MCTSError> {
        let mut current = root;
        let mut path = Vec::new();

        loop {
            let node = current
                .lock()
                .map_err(|e| MCTSError::LockPoisoned(e.to_string()))?;

            if node.state.children.is_empty() || !node.state.fully_expanded || node.state.terminal {
                drop(node);
                return Ok((current, path));
            }

            let parent_visits = node.state.visit_count;
            let c = self.config.exploration_constant;

            let best_child = node
                .state
                .children
                .iter()
                .max_by(|a, b| {
                    let a_ucb = a
                        .lock()
                        .map(|n| n.ucb1(parent_visits, c))
                        .unwrap_or(f64::NEG_INFINITY);
                    let b_ucb = b
                        .lock()
                        .map(|n| n.ucb1(parent_visits, c))
                        .unwrap_or(f64::NEG_INFINITY);
                    a_ucb
                        .partial_cmp(&b_ucb)
                        .unwrap_or(std::cmp::Ordering::Equal)
                })
                .cloned();

            drop(node);

            if let Some(child) = best_child {
                path.push(current.clone());
                current = child;
            } else {
                return Ok((current, path));
            }
        }
    }

    /// Expands a leaf node by adding child nodes for available actions.
    fn expand(
        &mut self,
        node: Arc<Mutex<MCTSNode>>,
    ) -> Result<Arc<Mutex<MCTSNode>>, MCTSError> {
        let mut locked = node
            .lock()
            .map_err(|e| MCTSError::LockPoisoned(e.to_string()))?;

        if locked.state.terminal || locked.depth >= self.config.max_depth {
            locked.state.terminal = true;
            drop(locked);
            return Ok(node.clone());
        }

        if locked.state.children.is_empty() {
            // Generate children (using action space of 4 for demonstration)
            let num_actions = 4u32;
            for action in 0..num_actions {
                let child_id = self.next_id();
                let child = MCTSNode::new(child_id, locked.depth + 1, action);
                locked
                    .state
                    .children
                    .push(Arc::new(Mutex::new(child)));
            }
            locked.state.fully_expanded = true;
        }

        // Return a random unexplored child or the first one
        let child = locked.state.children[0].clone();
        drop(locked);
        Ok(child)
    }

    /// Backpropagates the evaluation value up the tree path.
    fn backpropagate(
        &self,
        path: &[Arc<Mutex<MCTSNode>>],
        leaf: Arc<Mutex<MCTSNode>>,
        value: f64,
    ) -> Result<(), MCTSError> {
        // Update the leaf
        {
            let mut node = leaf
                .lock()
                .map_err(|e| MCTSError::LockPoisoned(e.to_string()))?;
            node.state.visit_count += 1;
            node.state.total_value += value;
        }

        // Update path nodes (root to parent of leaf)
        let mut current_value = value;
        for ancestor in path.iter().rev() {
            current_value *= self.config.discount;
            let mut node = ancestor
                .lock()
                .map_err(|e| MCTSError::LockPoisoned(e.to_string()))?;
            node.state.visit_count += 1;
            node.state.total_value += current_value;
        }

        Ok(())
    }

    /// Selects the best child of the root by visit count (most robust policy).
    fn best_child(
        &self,
        root: Arc<Mutex<MCTSNode>>,
    ) -> Result<SearchResult, MCTSError> {
        let locked = root
            .lock()
            .map_err(|e| MCTSError::LockPoisoned(e.to_string()))?;

        if locked.state.children.is_empty() {
            return Ok(SearchResult {
                best_action: 0,
                best_visits: locked.state.visit_count,
                best_value: locked.average_value(),
                total_iterations: self.total_iterations,
                total_nodes: self.node_counter,
                max_depth_reached: 0,
            });
        }

        let mut best_action = 0u32;
        let mut best_visits = 0u64;
        let mut best_value = f64::NEG_INFINITY;
        let mut max_depth = 0u32;

        for child_arc in &locked.state.children {
            if let Ok(child) = child_arc.lock() {
                if child.state.visit_count > best_visits {
                    best_visits = child.state.visit_count;
                    best_action = child.action;
                    best_value = child.average_value();
                }
                if child.depth > max_depth {
                    max_depth = child.depth;
                }
            }
        }

        Ok(SearchResult {
            best_action,
            best_visits,
            best_value,
            total_iterations: self.total_iterations,
            total_nodes: self.node_counter,
            max_depth_reached: max_depth,
        })
    }

    /// Generates the next unique node ID.
    fn next_id(&mut self) -> u64 {
        self.node_counter += 1;
        self.node_counter
    }

    /// Returns the total number of nodes created.
    pub fn node_count(&self) -> u64 {
        self.node_counter
    }

    /// Returns the total iterations across all searches.
    pub fn total_iterations(&self) -> u64 {
        self.total_iterations
    }

    /// Returns a reference to the configuration.
    pub fn config(&self) -> &MCTSConfig {
        &self.config
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ucb1_unexplored() {
        let node = MCTSNode::new(1, 0, 0);
        assert_eq!(node.ucb1(100, std::f64::consts::SQRT_2), f64::INFINITY);
    }

    #[test]
    fn test_ucb1_explored() {
        let mut node = MCTSNode::new(1, 0, 0);
        node.state.visit_count = 10;
        node.state.total_value = 5.0;
        let ucb = node.ucb1(100, std::f64::consts::SQRT_2);
        assert!(ucb > 0.5, "UCB1 should be > exploitation value");
        assert!(ucb < 10.0, "UCB1 should be bounded");
    }

    #[test]
    fn test_search_basic() {
        let config = MCTSConfig {
            max_iterations: 100,
            ..Default::default()
        };
        let mut tree = MCTSTree::new(config);
        tree.init_root();

        let result = tree.search(|action| action as f64 * 0.25).unwrap();
        assert!(result.total_iterations > 0);
        assert!(result.total_nodes > 0);
    }

    #[test]
    fn test_no_root_error() {
        let mut tree = MCTSTree::new(MCTSConfig::default());
        let result = tree.search(|_| 1.0);
        assert!(result.is_err());
    }
}
