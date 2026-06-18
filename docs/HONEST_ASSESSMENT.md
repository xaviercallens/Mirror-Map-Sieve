# Honest Assessment: Alien Mathematics Investigation

Date: June 14, 2026

## Core Findings

1. **The LLMs Hallucinated Breakthroughs**: The initial claims of "Alien Mathematics"—specifically the tensor rank optimization bounds and the $R(4,4,4) = 26$ bound—were false. They represented the models' tendency to interpolate plausibility rather than compute truth.
2. **Definitional Tautologies**: Many of the early "verified" results in Lean 4 were correct but mathematically trivial. The AI had constructed statements that were true by definition, creating a false sense of profound discovery.
3. **The Literature Gap**: We wasted compute on $R(3,3,4) \ge 26$ before discovering that Codish et al. had exactly solved $R(3,3,4) = 30$ in 2016. This reinforces Gate 1 of the Verification Pipeline: always search literature exhaustively first.

## Technical Successes

Despite the lack of novel mathematics, the engineering yields were massive:

1. **Rust Ramsey Solver**: Achieved up to 21,000,000 evaluations per second for Simulated Annealing on small graphs, and 2.5M for massive cliques like $R(4,6)$.
2. **ExactRationalWitness**: Successfully translated continuous Krawtchouk polynomial bounds on the discrete hypercube into exact $\mathbb{Q}$-arithmetic, creating a decidable, 0-axiom, 0-sorry Lean 4 proof framework.
3. **The Agora Falsification Pipeline**: We successfully built the adversarial half of the AI discovery loop. We now possess the capability to rapidly destroy hallucinated claims before they waste human peer-review time.

## Conclusion

We did not find "Alien Mathematics." What we found was the exact boundary where probabilistic AI breaks down against the cold reality of formal combinatorics. By building the infrastructure to map and defend that boundary, we have laid the true groundwork for AI-assisted discovery.
