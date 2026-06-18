import os
import glob
import re
from agents.galileo.tools.precision_validator import validate_against_horizonmath
from agents.galois.auth import GaloisAuthManager

def extract_python_from_lean(lean_code: str) -> str:
    """Uses Gemini to translate the Lean 4 constant definition into a Python mpmath function."""
    auth = GaloisAuthManager()
    if not auth.gemini_client:
        return ""
        
    prompt = f"""You are Galileo's translator. Extract the exact mathematical constant defined in this Lean 4 code and convert it to a Python function using `mpmath`.

Requirements:
- Output a single function: `def proposed_solution():`
- Return the evaluated value using `mpmath`.
- Do not make up formulas. If the constant is defined as `sorry`, return `def proposed_solution(): return None`.
- Only output the raw python code. No markdown fences.

Lean 4 Code:
```lean4
{lean_code}
```
"""
    try:
        response = auth.gemini_client.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"```(?:python)?\n?", "", raw).strip().rstrip("`").strip()
        return raw
    except Exception:
        return ""

def run_galileo_15_problems():
    v16_dir = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/achievement_output/v16_offline"
    lean_files = glob.glob(os.path.join(v16_dir, "*.lean"))
    lean_files.sort()
    
    results = []
    
    print("Running strict Galileo numerical verification (isolated from numerics ground-truth)...")
    
    for lean_file in lean_files:
        problem_id = os.path.basename(lean_file).replace(".lean", "")
        
        with open(lean_file, "r") as f:
            lean_code = f.read()
            
        print(f"Extracting closed form for {problem_id}...")
        extracted_python = extract_python_from_lean(lean_code)
        
        if extracted_python and "def proposed_solution" in extracted_python:
            res = validate_against_horizonmath(problem_id, extracted_python)
        else:
            res = {"valid": False, "message": "Failed to extract a closed form (likely a sorry gap in the definition)"}
            
        results.append({
            "problem": problem_id,
            "galileo_valid": res.get("valid", False),
            "galileo_message": res.get("message", ""),
            "galileo_diff": res.get("metrics", {}).get("diff", "N/A")
        })
        
    # Write report
    report_path = "/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/galileo_15_problems_status.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("# Galileo Agent Numerical Verification Status\\n\\n")
        f.write("> **Note**: This test run is STRICTLY ISOLATED from the `numerics/` ground-truth solvers. Closed forms are extracted directly from the Lean 4 sketches.\\n\\n")
        for r in results:
            status = "VERIFIED ✓" if r["galileo_valid"] else "FAILED ✗"
            f.write(f"## {r['problem']}\\n")
            f.write(f"- **Status**: `{status}`\\n")
            f.write(f"- **Message**: {r['galileo_message']}\\n")
            f.write(f"- **Diff**: {r['galileo_diff']}\\n\\n")
            
    print("Galileo report generated.")

if __name__ == "__main__":
    run_galileo_15_problems()
