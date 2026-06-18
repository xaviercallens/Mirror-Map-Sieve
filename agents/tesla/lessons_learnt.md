# Tesla Lessons Learnt
*   **Lesson 1**: Always follow strict type interface constraints defined in `AbstractAgent`. Misunderstanding the signature of `_stop_timer()` or using non-existent fields like `current_run_cost` caused debug loops.
*   **Lesson 2**: Float-free arithmetic is entirely practical and robust for safety-critical simulations.
*   **Lesson 3**: Local simulation scripts must be made executable and decoupled from third-party services so they can be easily rerun during CI/CD checks.
