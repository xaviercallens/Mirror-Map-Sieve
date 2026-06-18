# Prototyping Final Delivery

## Topic
High-Frequency Trading System with Deterministic Execution (FPGA/ASIC execution using exact rational bounds on risk/exposure)

## Literature Review
See LITERATURE_REVIEW.md

## Specification and Design
See SPECS_AND_DESIGN.md

## Final Memory
**

*   **Iteration 1 Complete.**
*   **Goal:** Validate deterministic execution and exact rational risk bounds.
*   **Outcome:** Core logic is **VALIDATED** through a high-fidelity Python simulation. Q-arithmetic for risk management is proven correct.
*   **Key Finding:** The software simulation confirms the logical design but highlights the unacceptable performance overhead of software-based rational arithmetic. The path forward requires transitioning the validated logic to a fixed-point numerical representation suitable for direct hardware synthesis (FPGA/ASIC).

*   **Iteration 2 Complete.**
*   **Goal:** Validate a hardware-ready, fixed-point (Q48.16) numerical model against the exact rational model from Iteration 1.
*   **Outcome:** The fixed-point model is **VALIDATED**. Numeric equivalence is confirmed across all test vectors, proving the design is sound for hardware synthesis without sacrificing the specified determinism.

*   **Iteration 3 Complete.**
*   **Goal:** Translate 

## Final Lessons Learnt
**

*   **Determinism is a System-Level Property, Not a Component-Level One:** The HIL validation of the single FPGA in Iteration 4 proved the node's performance was invariant. However, this guarantee is immediately voided by conventional networking and control planes. Inter-node communication and strategy deployment must be treated as part of the deterministic system, not as external inputs. Standard IP-based networks are unacceptable; a lightweight, time-triggered protocol is required.

*   **Formal Methods are Non-Negotiable for Concurrent Systems:** RTL simulation is insufficient for verifying a dynamic, multi-node system. The state space of possible interactions and update timings is infinite. By modeling the system in TLA+, we could *prove* invariants—such as "a strategy-bank switch will never occur mid-calculation"—that are impossible to exhaustively test through simulation. This moves our validation from empirical testing to mathematical certainty.

*   **The Control Plane Must
