Of course. Iteration 2 revealed fundamental tensions between formal safety, practical utility, and computational tractability. Iteration 3 will address these directly by introducing more sophisticated mathematical machinery. We are moving from the blunt instrument of hyperrectangles to the surgical precision of zonotopes, and from the brute force of pure rational arithmetic to the tactical application of interval methods.

The goal is not to retreat from formal proof, but to make it faster, smarter, and more efficient. Here are the results of the third prototyping loop.

---

### `MEMORY.md`

**Prototype:** Verifiably Safe Motion Planner v3.0
**Iteration:** 3
**Goal:** Achieve *efficiently safe* motion by replacing overly-pessimistic uncertainty models and mitigating the computational explosion of exact arithmetic, while retaining a formally verifiable Safety Certificate.

**Build Summary:**
The prototype underwent a significant overhaul of its core mathematical representations and computational engine, directly addressing the lessons from Iteration 2.

1.  **State Space Representation (Hyperrectangles -> Zonotopes):** The state uncertainty, previously bounded by hyperrectangles (axis-aligned boxes), is now represented by **Zonotopes**. A zonotope is a more expressive geometric shape (a centrally symmetric convex polytope) that provides a much tighter, less pessimistic bound on the set of reachable states for a system under linear dynamics and bounded uncertainty. This allows for larger, more usable safe corridors.

2.  **Reachability Analysis (Zonotope Propagation):** A new forward reachability algorithm based on zonotope propagation was implemented. The core loop now computes the evolution of the system's state zonotope through time via linear transformations and Minkowski sums with the zonotope representing the uncertainty set `W`. This maintains a guaranteed enclosure of all possible states.

3.  **Computational Engine (Q-Arithmetic -> Interval Arithmetic):** The pure, unbounded rational arithmetic (Q-arithmetic) engine used for all calculations has been replaced in the main loop by an **Interval Arithmetic** engine. All floating-point operations are replaced with operations on intervals `[low, high]` that are guaranteed to contain the true real number result. This provides a formal bound on numerical error with significantly better performance than Q-arithmetic, making real-time computation feasible. The final Safety Certificate is still extracted as an exact rational witness, but the expensive computations are now bounded.

4.  **Complexity Management (Zonotope Order Reduction):** To prevent the "curse of dimensionality" from re-emerging as zonotope complexity growth, an **order reduction** algorithm was added. After a fixed number of propagation steps, the algorithm computes a new, lower-order zonotope that is guaranteed to enclose the higher-order one, capping the computational cost of subsequent operations.

---

### `LESSONS_LEARNT.md`

**Lesson 1: The Verification Bottleneck Shifts.**
With zonotopes and interval arithmetic, the state propagation step is now computationally tractable. However, we have shifted the primary bottleneck from *propagation* to *verification*. Specifically, the collision check—determining if the state zonotope intersects with obstacle geometry (also represented as zonotopes or polytopes)—is now the most expensive part of the loop. The separating axis theorem, while effective, requires numerous projections and interval evaluations. The next iteration must focus on a formally verifiable, high-performance **collision checking algorithm** tailored specifically for zonotope-polytope intersection problems.

**Lesson 2: Online Guarantees vs. Offline Proofs.**
The current architecture performs all safety verification online, within the real-time control loop. This inherently limits the planning horizon and the complexity of the environment we can handle. We have reached a point where a single-tier architecture is insufficient. The next logical evolution is a **two-tiered architecture**:
*   **Online Planner:** A fast, real-time planner using the current zonotope/interval engine to generate short-term, locally safe trajectories with bounded-time guarantees.
*   **Offline Verifier:** A non-real-time, high-assurance verifier that runs in the background. It takes the candidate trajectories from the online planner and uses full-power formal methods (e.g., Q-arithmetic, theorem provers) to construct a globally consistent, long-horizon **Safety Proof**. This decouples the immediate need for safe action from the much harder problem of generating a complete, end-to-end proof. The prototype evolves from a verifier-in-the-loop to a verified planner with a separate proof engine.