# Contributing to the Mirror Map Sieve

We welcome contributions from pure mathematicians, computer scientists, and AI engineers.

## Open Problems

1. **Geometry Validations**: We have extracted the $S_{20}$ Callens-ALIX sequence and proved Lian-Yau integrality up to $d=16$. Further extensions to higher degrees or computing exact Gromov-Witten invariants from these periods are welcome.
2. **AI Hardware Attention**: Optimizing the `Callens-AL` sparse-block kernel for Triton or writing CUDA/C++ bindings.
3. **Hypergeometric Search**: Assisting in exploring other $S_{a,b}$ diagonal sequences.

## How to Contribute

1. **Fork the Repository**
2. **Create a Branch** (`git checkout -b feature/your-feature`)
3. **Commit your Changes** (`git commit -m 'feat: Add some feature'`)
4. **Push to the Branch** (`git push origin feature/your-feature`)
5. **Open a Pull Request**

Please ensure that any mathematical proofs included are verified in Lean 4 with 0 axioms and 0 `sorry` statements.
