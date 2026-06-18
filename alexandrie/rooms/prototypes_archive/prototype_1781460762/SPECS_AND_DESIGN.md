Of course. The preliminary documents were a sketch. Now, we architect the industry. A specification that cannot be tested is a fantasy. A design that does not directly map to a specification is a liability.

The following documents are the refined blueprint for the PROMETHEUS prototype. They are rigorous, testable, and form the contractual basis for all engineering that follows. Every requirement is bound to a verifiable outcome.

***

### `SPECS.md`

```markdown
# Formal Specification: Telesurgical System with A Priori Safety Guarantees
# Document ID: TS-SAFE-SPEC-001
# Version: 2.0 (Refined for Test-Driven Implementation)

---

## 1.0 System Overview

This document specifies the requirements for the PROMETHEUS (Predictive Robotic Operator with Mathematically Enforced Therapeutic Heuristics) system. The system's defining feature is the **Verification Kernel**, a formally verified software component that acts as a provably safe intermediary between surgeon intent and robotic action. It provides mathematical guarantees of safety *before* any physical action is executed.

This specification is the single source of truth. All design, implementation, and validation efforts must be traceable to these requirements.

## 2.0 Functional Requirements

### 2.1. Command & State Management
*   **SPEC-F-01**: The system SHALL intercept every command from the Master Control Unit (MCU) that would result in a state change of the Slave System Unit (SSU).
    *   **Verification**: `TEST-V-F-01`: Log all MCU commands and kernel interceptions. Verify 100% capture rate in simulation.
*   **SPEC-F-02**: For each intercepted command, the Verification Kernel SHALL generate a formal "Safety Certificate" or a "Rejection Proof". An SSU state change is only permitted with a valid Safety Certificate.
    *   **Verification**: `TEST-V-F-02`: Unit tests for the Verification Kernel that provide known-safe and known-unsafe command vectors. Assert that certificates are generated only for the safe vectors and rejections for all others.

### 2.2. Predictive Modeling & Safety Verification
*   **SPEC-F-03**: The system SHALL maintain a Dynamic Tissue Model (DTM) representing the surgical field, defined by geometric boundaries and biomechanical properties (e.g., elasticity, plasticity).
    *   **Verification**: `TEST-V-F-03`: Simulation environment to load and query DTM parameters. Verify model consistency and data integrity.
*   **SPEC-F-04**: The Verification Kernel SHALL use the DTM to predict the resulting state (position, force) of the SSU effector *before* executing the physical move.
    *   **Verification**: `TEST-V-F-04`: Compare predicted state vectors from the kernel against actual outcomes from a high-fidelity physics simulation. Discrepancy must be within a defined tolerance `ε_force` and `ε_pos`.
*   **SPEC-F-05**: The Safety Certificate SHALL only be generated if the predicted state does not violate predefined safety constraints. Constraints include:
    *   **SPEC-F-05a (Geometric)**: Effector shall not cross defined geometric boundaries (e.g., "no-fly zones").
    *   **SPEC-F-05b (Force)**: Applied force shall not exceed a specified maximum pressure `P_max` on any tissue surface point.
    *   **Verification**: `TEST-V-F-05`: A suite of tests where command vectors are designed to intentionally violate geometric and force constraints. Confirm that the kernel generates a Rejection Proof in 100% of these cases.

### 2.3. Haptic Feedback
*   **SPEC-F-06**: The Master Control Unit SHALL render haptic feedback to the operator.
*   **SPEC-F-07**: This haptic feedback SHALL be based on the *predicted forces* calculated by the Verification Kernel, not the measured forces from the SSU. This provides preemptive feedback.
    *   **Verification**: `TEST-V-F-07`: In a simulated environment, apply a command that would lead to a predicted force increase. Verify that the haptic feedback is rendered *before* the simulated SSU effector makes contact or applies said force. Measure latency.

## 3.0 Non-Functional Requirements

### 3.1. Performance
*   **SPEC-NF-01**: The end-to-end latency for the verification loop (MCU command -> Kernel verification -> SSU execution) SHALL NOT exceed 5 milliseconds.
    *   **Verification**: `TEST-V-NF-01`: High-resolution timing analysis under maximum computational load for the DTM and kernel prover.
*   **SPEC-NF-02**: The Verification Kernel's execution path SHALL be deterministic and provably free of race conditions and deadlocks.
    *   **Verification**: `TEST-V-NF-02`: Static analysis of the kernel's source code. Formal proof of determinism using a chosen methodology (e.g., SPARK/Ada flow analysis, Coq/Lean proof).

### 3.2. Reliability & Formal Verification
*   **SPEC-NF-03**: The logical implementation of the Verification Kernel's core safety predicate (`IsSafe(command, state) -> bool`) SHALL be formally proven correct against this specification using a theorem prover (e.g., Lean 4, Coq, or Isabelle/HOL).
    *   **Verification**: `TEST-V-NF-03`: The completed formal proof itself is the deliverable.  It must be reviewed and accepted.
*   **SPEC-NF-04**: The system SHALL fail-safe. Any fault, timeout, or uncaught exception within the Verification Kernel SHALL result in an immediate halt of the SSU and a Rejection Proof.
    *   **Verification**: `TEST-V-NF-04`: Fault injection testing. Induce errors in the kernel and verify the SSU enters a safe, locked state.
```

***

### `DESIGN.md`

```markdown
# System Design Architecture: PROMETHEUS Prototype
# Document ID: TS-SAFE-DESIGN-001
# Version: 2.0 (Traceable to SPECS.md v2.0)

---

## 1.0 Architectural Vision

This design realizes the requirements of `TS-SAFE-SPEC-001`. The architecture is predicated on the principle of **"Verify, then Execute."** It physically and logically isolates the untrusted, high-variability surgeon input from the safety-critical patient-side hardware with the **Verification Kernel**. This is not a passive monitor; it is an active, provably correct guard.

The system is a real-time, hybrid control system. The design prioritizes determinism, low latency, and mathematical provability over statistical performance.

## 2.0 System Architecture Diagram

```mermaid
flowchart TD
    subgraph "Operating Theater"
        SSU[Slave System Unit (SSU - Patient side)]
        H_SSU(SSU Hardware Controller)
        DTM_P[Physical Tissue]

        SSU -- "Physical Action" --> DTM_P
        DTM_P -- "Sensor Data" --> H_SSU
    end

    subgraph "Surgeon's Console"
        MCU[Master Control Unit (MCU)]
        HFC[Haptic Feedback Controller]

        MCU -- "1. Surgeon Command Vector" --> VK
        HFC -- "5b. Haptic Command" --> MCU
    end

    subgraph "PROMETHEUS Core (Real-Time OS)"
        VK[Verification Kernel]
        DTM[Dynamic Tissue Model (Software)]
        SP[Safety Predicates (SPEC-F-05)]

        VK -- "2. Predict State" --> DTM
        VK -- "3. Check Predicates" --> SP
        DTM -- "State Prediction" --> VK
        SP -- "IsSafe? (bool)" --> VK
        VK -- "4a. Permitted Vector (If Safe)" --> H_SSU
        VK -- "5a. Predicted Force" --> HFC
    end

    style VK fill:#bde,stroke:#333,stroke-width:2px
    style DTM fill:#f9f,stroke:#333,stroke-width:2px
```
*Figure 1: High-Level Control & Verification Loop.*

## 3.0 Component Design

### 3.1. Master Control Unit (MCU)
*   **Function**: Captures surgeon's kinematic intent (position, orientation). Renders haptic feedback.
*   **Interface**: Outputs a standardized `Command Vector` (e.g., `Δx, Δy, Δz, Δα, Δβ, Δγ`).
*   **Traceability**: `SPEC-F-01`, `SPEC-F-06`.

### 3.2. Verification Kernel (The Core Innovation)
*   **Function**: A deterministic, formally verified software module that decides if a `Command Vector` is safe. This is the heart of the system.
*   **Inputs**:
    1.  `Command Vector` from MCU.
    2.  `Current State` from SSU sensors (position, force).
    3.  `Dynamic Tissue Model` (read-only access).
*   **Logic**:
    1.  Receive `Command Vector`.
    2.  Query the DTM to predict the `Resulting State` (new position, new force profile).
    3.  Evaluate the `IsSafe(Resulting State)` predicate against the loaded `Safety Predicates` (geometric and force constraints).
    4.  If `true`, generate a `Safety Certificate` and forward the (potentially modified) `Command Vector` to the SSU.
    5.  If `false`, generate a `Rejection Proof` and discard the command.
    6.  In all cases, send the `Predicted Force` profile to the Haptic Feedback Controller.
*   **Outputs**:
    1.  `Permitted Command Vector` to SSU.
    2.  `Predicted Force Vector` to HFC.
*   **Implementation**: To be implemented in a language amenable to formal verification, such as SPARK/Ada, F*, or a provably safe subset of C/C++.
*   **Traceability**: `SPEC-F-02`, `SPEC-F-04`, `SPEC-F-05`, `SPEC-NF-01`, `SPEC-NF-02`, `SPEC-NF-03`, `SPEC-NF-04`.

### 3.3. Dynamic Tissue Model (DTM)
*   **Function**: A real-time, finite element model (FEM) or mass-spring-damper system that represents the soft tissue in the surgical field. Its purpose is not perfect realism, but deterministic and fast prediction.
*   **Interface**: Provides a function `Predict(Command, CurrentState) -> ResultingState`.
*   **Traceability**: `SPEC-F-03`.

### 3.4. Slave System Unit (SSU)
*   **Function**: The patient-side robotic arm. It is a "dumb" actuator in this design. It only executes `Permitted Command Vectors` that have been certified by the kernel. It does not possess any higher-level intelligence.
*   **Interface**: Executes validated kinematic commands. Provides high-frequency state data (position, force sensors) back to the system.
*   **Traceability**: `SPEC-F-01`.

## 4.0 Next Steps & Goals

**Phase**: Build & Validate 1.

1.  **Goal**: Implement the Verification Kernel as a standalone module.
2.  **Goal**: Develop a deterministic, software-only DTM simulator.
3.  **Validation**: Author unit tests (`TEST-V-F-02`, `TEST-V-F-04`, `TEST-V-F-05`) to drive the implementation of the kernel. The kernel must pass these tests against the simulator.
4.  **Validation**: Benchmark kernel execution time to validate performance against `SPEC-NF-01`.

This iterative loop—building to specification and validating against tests—is the only path to creating a foundation for this new industry. We proceed with the implementation of the kernel.
```