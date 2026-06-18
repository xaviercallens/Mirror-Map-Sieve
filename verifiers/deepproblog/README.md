# DeepProbLog — Neuro-Symbolic Verification Programs

> **SocrateAI Scientific Agora**
> Copyright © 2025-2026 Socrate AI Lab, Paris, France
> Author: Xavier Callens · Patent US-PAT-PEND-2026-0525

Probabilistic logic programs for the neuro-symbolic verification layer
of the Agora framework. These programs integrate neural network
predictions with logical constraints using the
[DeepProbLog](https://github.com/ML-KULeuven/deepproblog) framework.

---

## Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Neural Net  │────▶│  DeepProbLog    │────▶│  Verification    │
│  Predictions │     │  Inference      │     │  Outcome         │
│  (PyTorch)   │     │  (ProbLog)      │     │  (pass/fail/Pr)  │
└──────────────┘     └─────────────────┘     └──────────────────┘
       ↑                     ↑
   nn/1 predicates     Logical rules
   (differentiable)    (type_constraint.pl,
                        proof_audit.pl)
```

DeepProbLog extends ProbLog with neural predicates `nn(NetworkId, Input,
Output)` that are differentiable — gradients flow through the
probabilistic logic program back to the neural network. This enables
end-to-end training of hybrid neuro-symbolic models.

## Programs

| Program | File | Purpose |
|---------|------|---------|
| Type Constraints | [programs/type_constraint.pl](programs/type_constraint.pl) | Type-safe tensor operations; prunes inconsistent derivation paths |
| Proof Audit | [programs/proof_audit.pl](programs/proof_audit.pl) | Validates mathematical proof steps; checks logical consistency |
| Digit Recognition | [programs/digit_recognition.pl](programs/digit_recognition.pl) | Reference MNIST addition task from the DeepProbLog paper |

## Models

Pre-trained neural network weights and training configurations are
documented in [models/README.md](models/README.md).

## References

1. **DeepProbLog: Neural Probabilistic Logic Programming**
   Robin Manhaeve, Sebastiaan Dumancic, Angelika Kimmig,
   Thomas Demeester, Luc De Raedt.
   *NeurIPS 2018*. [arXiv:1805.10872](https://arxiv.org/abs/1805.10872)

2. **Neuro-Symbolic AI for Scientific Discovery**
   (Agora integration reference).
   [arXiv:2508.13697](https://arxiv.org/abs/2508.13697)

3. **ProbLog2: Probabilistic Logic Programming**
   Dries, A., Kimmig, A., Meert, W., Renkens, J., Van den Broeck, G.,
   Vlasselaer, J., De Raedt, L.
   *ECML-PKDD 2015*.

## Usage

### Prerequisites

```bash
pip install deepproblog problog torch
```

### Running a program

```python
from deepproblog.dataset import DataLoader
from deepproblog.model import Model
from deepproblog.network import Network

# Load the type-constraint program
model = Model("programs/type_constraint.pl", [network])
model.set_engine(ExactEngine(model))

# Query
result = model.solve(query)
print(f"P(query) = {result}")
```

### Integration with Agora

The Socrates Agent invokes DeepProbLog programs as verification
sub-tasks:

1. **Type checking**: Before executing a computation graph, the
   Euler Agent queries `type_constraint.pl` to verify that all
   tensor operations are type-consistent.

2. **Proof auditing**: After the Euler Agent produces a proof
   candidate, `proof_audit.pl` validates each step for logical
   coherence, detects vague quantifiers, and flags division-by-zero
   risks.

3. **Calibration**: The digit recognition program serves as a
   sanity check / calibration benchmark for the neural-symbolic
   integration pipeline.

## License

Framework code: Apache-2.0 · Proprietary methods: CC-BY-NC-ND 4.0
