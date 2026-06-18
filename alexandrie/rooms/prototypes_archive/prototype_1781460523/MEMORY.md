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