**

*   **Determinism is a System-Level Property, Not a Component-Level One:** The HIL validation of the single FPGA in Iteration 4 proved the node's performance was invariant. However, this guarantee is immediately voided by conventional networking and control planes. Inter-node communication and strategy deployment must be treated as part of the deterministic system, not as external inputs. Standard IP-based networks are unacceptable; a lightweight, time-triggered protocol is required.

*   **Formal Methods are Non-Negotiable for Concurrent Systems:** RTL simulation is insufficient for verifying a dynamic, multi-node system. The state space of possible interactions and update timings is infinite. By modeling the system in TLA+, we could *prove* invariants—such as "a strategy-bank switch will never occur mid-calculation"—that are impossible to exhaustively test through simulation. This moves our validation from empirical testing to mathematical certainty.

*   **The Control Plane Must