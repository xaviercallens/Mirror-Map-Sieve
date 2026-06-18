#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
OEIS Submission Draft Generator for Callens-Socrates Sequence (S15)
-----------------------------------------------------------------
Generates the copy-pasteable submission draft in standard OEIS format,
reading recurrence relation coefficients and invariants dynamically.
"""

import os
import json
from math import comb
from pathlib import Path

def compute_seq(n):
    return sum(comb(n, k) * (comb(n+k, k)**5) for k in range(n+1))

def main():
    print("Generating OEIS submission draft for Callens-Socrates sequence...")
    
    # Load exact recurrence relation
    recurrence_file = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie_data/recurrence_a1b5.json"
    if not os.path.exists(recurrence_file):
        print(f"Error: {recurrence_file} does not exist.")
        return
        
    with open(recurrence_file, "r") as f:
        recurrence_dict = json.load(f)
        
    # Load invariants
    invariants_file = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie_data/s15_invariants.json"
    if not os.path.exists(invariants_file):
        print(f"Error: {invariants_file} does not exist.")
        return
        
    with open(invariants_file, "r") as f:
        invariants_dict = json.load(f)
    x0 = invariants_dict["x0"]
    G = invariants_dict["growth_constant"]
    
    terms = [compute_seq(n) for n in range(12)]
    terms_str = ",".join(map(str, terms))
    
    recurrence_lines = []
    for i in range(10):
        poly_str = recurrence_dict[str(i)]
        suffix = " + " if i < 9 else " = 0"
        term_name = "S(n)" if i == 0 else f"S(n+{i})"
        recurrence_lines.append(f"%F {poly_str} * {term_name}{suffix}")
    recurrence_text = "\n".join(recurrence_lines)
    
    python_snippet = (
        "from math import comb\n"
        "def S(n):\n"
        "    return sum(comb(n, k) * (comb(n+k, k)**5) for k in range(n+1))\n"
        "print([S(n) for n in range(12)])"
    )
    
    maple_snippet = (
        "S := n -> sum(binomial(n, k) * binomial(n+k, k)^5, k=0..n):\n"
        "seq(S(n), n=0..11);"
    )
    
    mathematica_snippet = (
        "S[n_] := Sum[Binomial[n, k] * Binomial[n+k, k]^5, {k, 0, n}];\n"
        "Table[S[n], {n, 0, 11}]"
    )
    
    oeis_draft = f"""%I 
%S {terms_str}
%N Callens-Socrates sequence: S(n) = Sum_{{k=0..n}} binomial(n, k) * binomial(n+k, k)^5.
%C Satisfies modular Lucas congruence property S(p*n) == S(n) (mod p) for all primes p.
%C Expressed as the diagonal of the 6-variable rational function F(x_1, x_2, x_3, x_4, x_5, x_6) = 1 / (1 - x_1*(1-x_2)*(1-x_3)*(1-x_4)*(1-x_5)*(1-x_6) - x_1*x_2*x_3*x_4*x_5*x_6).
%F S(n) = Sum_{{k=0..n}} binomial(n, k) * binomial(n+k, k)^5.
%F Asymptotic growth constant (Callens-Socrates growth constant): G = {G:.12f}..., where x0 is the unique root in (0,1) of 2*x^6 + 4*x^5 + 5*x^4 - 5*x^2 - 4*x - 1 = 0 (x0 = {x0:.12f}...).
%F Minimal recurrence relation (order 9, degree 14):
%F (Note: Recurrence coefficients are extremely large integer polynomials)
{recurrence_text}
%o (Python)
%o {python_snippet}
%o (Maple)
%o {maple_snippet}
%o (Mathematica)
%o {mathematica_snippet}
"""
    # Save to artifacts
    draft_path = Path("/Users/xcallens/.gemini/antigravity/brain/97f6aad0-8120-443d-9423-480ea442100a/oeis_submission_draft_a1b5.txt")
    with open(draft_path, "w") as f:
        f.write(oeis_draft)
        
    # Copy to frontend documents
    frontend_doc_path = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie/frontend/public/documents/oeis_submission_draft_a1b5.txt")
    frontend_doc_path.parent.mkdir(parents=True, exist_ok=True)
    with open(frontend_doc_path, "w") as f:
        f.write(oeis_draft)
        
    print(f"📝 Generated OEIS submission draft at {draft_path} and {frontend_doc_path}")

if __name__ == "__main__":
    main()
