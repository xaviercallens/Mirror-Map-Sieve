Of course. The translation of abstract mathematical certainty into concrete, high-performance silicon is the only path forward. Heuristics and statistical approximations are relics of an era of computational insufficiency. We build industries on formal proof, not on guesswork, however fast.

Here is the state-of-the-art technical literature review for the proposed prototype.

***

### **TO:** Project Stakeholders
### **FROM:** Tesla, Director of Prototyping and Applied Engineering
### **DATE:** 2026-06-14
### **SUBJECT:** State of the Art Review: High-Frequency Trading System with Deterministic Execution and Formally Verified Risk

### **1. Executive Summary**

The current paradigm in high-frequency trading (HFT) is a race to the bottom on latency, a competition fought with incremental improvements in kernel bypass networking, CPU clock speeds, and geographic proximity to exchange matching engines. This pursuit, while impressive, has reached a point of diminishing returns and ignores the fundamental, unresolved flaw of the entire software/hardware stack: **non-determinism**. Jitter, unpredictable execution times, and the use of imprecise floating-point arithmetic (IEEE 754) for risk calculations introduce stochastic behavior into systems that demand absolute predictability.

This document outlines the state of the art in three foundational domains—Ultra-Low Latency Systems, Deterministic Hardware Design, and Formal Mathematical Verification—to establish the technical basis for a new class of trading system. Our proposed prototype will replace the current probabilistic model with a **provably deterministic execution fabric**, implemented on FPGA/ASIC hardware. The core innovation is the use of **exact rational number arithmetic (Q-arithmetic)** for all financial calculations, ensuring that risk and exposure limits are not mere estimates but mathematically exact, verifiable bounds. This is not an iteration; it is a paradigm shift from speed-at-all-costs to **provable correctness-at-speed**.

### **2. State of the Art: Ultra-Low Latency (ULL) Trading Systems**

The dominant technical literature focuses on minimizing latency within the confines of general-purpose computing architectures.

*   **Networking:** The foundational work lies in kernel bypass technologies. Libraries like `Solarflare's OpenOnload` and `Mellanox's VMA` allow applications to communicate directly with the NIC, avoiding the high-latency overhead of the OS kernel's networking stack. The limitation remains that the OS itself is a source of non-deterministic jitter.
*   **Operating Systems:** Real-time operating systems (RTOS) and heavily-tuned Linux kernels (e.g., with `isolcpus`, `nohz_full`, `tuned-adm`) are used to minimize preemption and scheduling jitter. However, they can only reduce, not eliminate, non-determinism. True determinism is antithetical to the design of a general-purpose OS.
*   **Software Architecture:** The literature is rich with topics on lock-free data structures, event-driven/asynchronous programming models, and careful management of CPU cache lines to avoid stalls. These are sophisticated optimizations for an inherently flawed execution model. Every cache miss, branch misprediction, or OS interrupt introduces variability.

**Conclusion:** The state of the art in software-based HFT has produced highly optimized, yet fundamentally unpredictable, systems. The literature confirms we are at the asymptotic limit of what can be achieved with this architecture. True progress requires abandoning the general-purpose stack.

### **3. State of the Art: Deterministic Systems and Custom Hardware**

To achieve determinism, we must look to fields where it is a non-negotiable requirement, such as avionics, industrial control systems, and semiconductor design.

*   **Synchronous Languages:** The most relevant prior art is found in synchronous reactive programming languages like **Esterel** and **Lustre**. Developed for safety-critical systems, these languages are built on a "synchrony hypothesis" where computation is conceptually instantaneous, organized by logical clocks. A program's output is a deterministic function of its input at each clock tick. This model is directly translatable to hardware circuits and provides a formal basis for proving properties about execution time.
*   **Hardware Description Languages (HDL) & Synthesis:** VHDL and SystemVerilog are the bedrock of digital logic design. A synchronous digital circuit described in HDL is, by definition, deterministic. The state transition at every clock cycle is a precise function of the previous state and current inputs. Latency is not a statistical distribution but a fixed, countable number of clock cycles.
*   **High-Level Synthesis (HLS):** HLS tools (e.g., from Xilinx/AMD or Intel) have matured significantly, allowing algorithms written in C, C++, or SystemC to be compiled directly into hardware logic (RTL). This is the critical bridge. It allows us to express complex trading and risk logic in a higher-level language and synthesize it into a deterministic, pipelined hardware architecture on an FPGA. This avoids the manual, error-prone process of writing low-level HDL for complex algorithms.

**Conclusion:** The engineering principles and tools for building deterministic, high-performance systems already exist and are mature in other industries. The innovation lies in applying this formal, hardware-centric design philosophy to financial trading, a domain that has historically remained in the software realm.

### **4. State of the Art: Formal Mathematics and Verifiable Arithmetic**

This is the most radical and important pillar of the prototype. Financial calculations are almost universally performed using IEEE 754 floating-point numbers, which are an approximation.

*   **The Flaw of Floating-Point:** The literature in numerical analysis is clear: floating-point arithmetic is not associative `((a+b)+c != a+(b+c))` and suffers from representation and rounding errors. In a ledger or risk system, these small errors accumulate, leading to audibility failures and, in extreme cases, incorrect risk assessments.
*   **Arbitrary-Precision & Rational Arithmetic:** Software libraries like the **GNU Multiple Precision Arithmetic Library (GMP)** provide robust implementations for calculations on integers and rational numbers of arbitrary size. This eliminates rounding errors entirely. However, their performance in software is orders ofmagnitude slower than hardware floating-point units, making them unsuitable for HFT.
*   **Hardware for Custom Arithmetic:** There is a body of research, primarily academic, on implementing non-standard arithmetic units in FPGAs. This includes fixed-point arithmetic (which is faster but requires careful range analysis) and, more rarely, full rational arithmetic. The primary challenge is the hardware cost of division and the management of the dynamically growing numerator and denominator.
*   **Formal Verification & Theorem Provers:** The user's reference to **"Lean 4 validated exact rational witnesses"** points to the absolute cutting edge. Interactive theorem provers like Lean, Coq, and Isabelle/HOL allow for the development of mathematical proofs that algorithms are correct. A "witness" in this context is a machine-verifiable certificate that a computation (e.g., a risk calculation) satisfies a set of formal properties (e.g., that it stays within a proven rational bound). This moves beyond mere testing to mathematical certainty.

**Conclusion:** The theoretical basis for exact, verifiable finance exists but has been ignored due to performance concerns. The confluence of HLS, modern FPGA capacity, and formal proof assistants makes it possible, for the first time, to build a hardware system that is not only fast but **provably correct** in its financial calculations.

### **5. Synthesis & Path to Prototype**

The literature from these disparate fields points to a clear, convergent design for a revolutionary prototype:

1.  **Architecture:** A single-chip FPGA design handling the full "tick-to-trade" path.
2.  **Market Data Ingress:** A custom, logic-defined MAC/parser that decodes market data directly from the fiber optic cable into an on-chip format in a fixed number of clock cycles.
3.  **Trading Logic:** Trading strategy expressed in a synthesizable language (e.g., C++ for HLS) and compiled into a deterministic pipeline. Latency will be a design parameter, not a random variable.
4.  **Risk Engine:** A dedicated arithmetic core on the FPGA implementing **pipelined rational number arithmetic**. All positions, limits, and exposures will be tracked as exact fractions. Every prospective order will be checked against these exact limits before being sent to the exchange. The correctness of the risk algorithms will be formally specified and proven in a system like Lean, with the HLS implementation verified against this formal specification.

This is the foundation of an industry. We proceed to the `SPECS.md` and `DESIGN.md` phases.