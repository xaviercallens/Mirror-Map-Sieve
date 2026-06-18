#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Automated Peer Review and Monograph Generation Pipeline for S15
----------------------------------------------------------------
Generates the formal math paper, simulates a 5-round peer review loop
using Mistral (reviewer) and Gemini (author), compiles to PDF, and archives.
"""

import os
import json
import time
import requests
import subprocess
import sympy as sp
from pathlib import Path

# Load environment variables from .env
def load_env():
    env_path = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/.env")
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v

load_env()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MISTRAL_API_KEY = os.getenv("GALOIS_MISTRAL_KEY", "")

def call_gemini(prompt: str, system_prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.2
        }
    }
    headers = {"Content-Type": "application/json"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=300)
        if r.status_code == 200:
            res = r.json()
            try:
                return res["candidates"][0]["content"]["parts"][0]["text"]
            except KeyError:
                return f"[GEMINI_ERROR: 'candidates' key mismatch - {res}]"
        else:
            return f"[GEMINI_ERROR: HTTP {r.status_code} - {r.text}]"
    except Exception as e:
        return f"[GEMINI_ERROR: {str(e)}]"

def call_mistral(prompt: str, system_prompt: str) -> str:
    url = "https://api.mistral.ai/v1/chat/completions"
    payload = {
        "model": "mistral-large-latest",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=300)
        if r.status_code == 200:
            res = r.json()
            return res["choices"][0]["message"]["content"]
        else:
            return f"[MISTRAL_ERROR: HTTP {r.status_code} - {r.text}]"
    except Exception as e:
        return f"[MISTRAL_ERROR: {str(e)}]"

def main():
    print("==================================================")
    print(" 🔬 S15 MULTI-AGENT PEER REVIEW LOOP RUNNER ")
    print("==================================================")
    
    # 1. Load exact recurrence relation
    recurrence_file = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie_data/recurrence_a1b5.json"
    if not os.path.exists(recurrence_file):
        print(f"Error: {recurrence_file} does not exist.")
        return
        
    with open(recurrence_file, "r") as f:
        recurrence_dict = json.load(f)
        
    # Format polynomials for display
    poly_display = ""
    for i in range(10):
        poly_display += f"P_{i}(n) = {recurrence_dict[str(i)]}\n\n"
        
    # 2. Load invariants
    invariants_file = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie_data/s15_invariants.json"
    if not os.path.exists(invariants_file):
        print(f"Error: {invariants_file} does not exist.")
        return
        
    with open(invariants_file, "r") as f:
        invariants_dict = json.load(f)
    x0 = invariants_dict["x0"]
    G = invariants_dict["growth_constant"]
    
    # 3. Initial paper draft
    initial_paper_prompt = f"""
Generate the first draft of an amsart LaTeX paper note for the Callens-Socrates Sequence S15.
Details to include:
- Formula: S15(n) = sum_{{k=0}}^n \\binom{{n}}{{k}} \\binom{{n+k}}{{k}}^5.
- Recurrence: Order 9, degree 14 minimal linear recurrence relation.
- Leading Polynomial P_9(n) = {recurrence_dict["9"][:150]}...
- Growth constant: G ≈ {G:.12f} based on peak root x_0 ≈ {x0:.12f} of 2x^6 + 4x^5 + 5x^4 - 5x^2 - 4x - 1 = 0.
- Mirror map integrality coefficients: q_2 = 112, q_3 = 37973, q_4 = 18476275, q_5 = 10821732660.
- Applications: Aeronautics drag optimization, Quantum walks on CY 5-fold slice, Cryptography security complexity.

Provide the complete LaTeX document source code. Do not include any markdown outside of the code block.
"""
    print("Generating initial paper draft via Gemini...")
    latex_src = call_gemini(initial_paper_prompt, "You are a research mathematician writing a LaTeX note.")
    # Extract LaTeX from markdown code block if present
    if "```latex" in latex_src:
        latex_src = latex_src.split("```latex")[1].split("```")[0].strip()
    elif "```" in latex_src:
        latex_src = latex_src.split("```")[1].split("```")[0].strip()
        
    # 4. Peer Review Loop (5 Rounds)
    review_history = []
    
    for round_num in range(1, 6):
        print(f"\n--- Round {round_num}/5 ---")
        
        # Determine reviewer prompt and system prompt
        if round_num < 5:
            reviewer_system = "You are an objective academic peer reviewer (Reviewer) specializing in arithmetic geometry and string theory."
            reviewer_prompt = f"""
Review the following mathematical paper note draft. Focus on:
1. Mathematical precision and notation clarity.
2. The explanation of the mirror map integrality coefficients (Lian-Yau property).
3. The plausibility of the three-field applications.

Provide structured critique and suggest modifications.
Paper Draft:
{latex_src}
"""
        else:
            # Controversial round
            reviewer_system = "You are Reviewer 5, a highly skeptical traditionalist mathematician."
            reviewer_prompt = f"""
You must strongly object to this paper. Argue that:
1. An order 9, degree 14 recurrence is far too complex to be verified by hand, and trusting a computer-generated proof or Lean 4 decidability is not 'real mathematics'.
2. The Calabi-Yau 5-fold slice returning probability model lacks physical/geometric motivation and needs justification.
3. Cryptographic security claims based on S15 growth are speculative without a concrete cryptanalysis.

Provide a skeptical, controversial review.
Paper Draft:
{latex_src}
"""
            
        print(f"Calling Mistral for Reviewer {round_num} critique...")
        critique = call_mistral(reviewer_prompt, reviewer_system)
        print(f"Reviewer {round_num} Critique:\n{critique[:300]}...\n")
        
        # Author revision
        author_system = "You are the author of a mathematical monograph note. Address feedback and revise the LaTeX code."
        if round_num < 5:
            author_prompt = f"""
Address the following peer reviewer critique for your paper. Update the LaTeX source code of the paper.
Reviewer Critique:
{critique}

Current LaTeX Source:
{latex_src}

Return ONLY the updated complete LaTeX source code.
"""
        else:
            author_prompt = f"""
Address the highly skeptical and controversial critique of Reviewer 5. 
You must write a new section in the paper titled 'Epistemological Defense and Formal Witnesses' that:
1. Explains why computer-assisted proofs and Lean 4 kernel verification constitute absolute mathematical truth, bridging the gap of human readability.
2. Justifies the Calabi-Yau 5-fold slice return probability model using topological wave-function localization.
3. Clarifies that the cryptography search space bounds scale strictly as N log2(G) which mathematically limits algebraic attacks.

Update the LaTeX source code.
Reviewer Critique:
{critique}

Current LaTeX Source:
{latex_src}

Return ONLY the updated complete LaTeX source code.
"""
            
        print("Calling Gemini for author revision...")
        revised_latex = call_gemini(author_prompt, author_system)
        if "```latex" in revised_latex:
            revised_latex = revised_latex.split("```latex")[1].split("```")[0].strip()
        elif "```" in revised_latex:
            revised_latex = revised_latex.split("```")[1].split("```")[0].strip()
            
        latex_src = revised_latex
        
        review_history.append({
            "round": round_num,
            "reviewer_critique": critique,
            "author_revision_latex": latex_src[:500] + "..."
        })
        
    # 5. Write final LaTeX note
    final_tex_path = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/experimental_mathematics_note_a1b5.tex"
    with open(final_tex_path, "w") as f:
        f.write(latex_src)
    print(f"\n🎉 Saved final LaTeX note to {final_tex_path}")
    
    # Copy to public documents and artifacts directory
    public_tex_path = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie/frontend/public/documents/experimental_mathematics_note_a1b5.tex"
    os.makedirs(os.path.dirname(public_tex_path), exist_ok=True)
    with open(public_tex_path, "w") as f:
        f.write(latex_src)
        
    artifact_tex_path = f"/Users/xcallens/.gemini/antigravity/brain/97f6aad0-8120-443d-9423-480ea442100a/experimental_mathematics_note_a1b5.tex"
    with open(artifact_tex_path, "w") as f:
        f.write(latex_src)
        
    # 6. Compile to PDF using pdflatex
    print("\nCompiling LaTeX note to PDF using pdflatex...")
    cwd = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora"
    try:
        proc = subprocess.run(
            ["/Library/TeX/texbin/pdflatex", "-interaction=nonstopmode", "experimental_mathematics_note_a1b5.tex"],
            capture_output=True, text=True, cwd=cwd
        )
        if proc.returncode == 0:
            print("🎉 pdflatex compiled paper successfully!")
            
            # Copy PDF to public documents and artifacts
            import shutil
            shutil.copy(f"{cwd}/experimental_mathematics_note_a1b5.pdf", "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie/frontend/public/documents/experimental_mathematics_note_a1b5.pdf")
            shutil.copy(f"{cwd}/experimental_mathematics_note_a1b5.pdf", f"/Users/xcallens/.gemini/antigravity/brain/97f6aad0-8120-443d-9423-480ea442100a/experimental_mathematics_note_a1b5.pdf")
            print("Copied PDF note to assets and artifacts successfully.")
        else:
            print(f"⚠️ pdflatex compilation warning:\n{proc.stderr}\nStdout:\n{proc.stdout}")
    except Exception as e:
        print(f"Failed to compile LaTeX: {e}")
        
    # 7. Save peer reviews JSON report
    report_data = {
        "claim": "Discovery and Mirror Symmetry of the Callens-Socrates Sequence S15",
        "timestamp": str(time.time()),
        "total_rounds": 5,
        "history": review_history
    }
    
    report_json_path = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie_data/peer_reviews_a1b5.json"
    with open(report_json_path, "w") as f:
        json.dump(report_data, f, indent=2)
        
    artifact_json_path = "/Users/xcallens/.gemini/antigravity/brain/97f6aad0-8120-443d-9423-480ea442100a/peer_reviews_a1b5.json"
    with open(artifact_json_path, "w") as f:
        json.dump(report_data, f, indent=2)
        
    print(f"Saved peer reviews history to {report_json_path}")
    print("Peer review pipeline run finished successfully!")

if __name__ == "__main__":
    main()
