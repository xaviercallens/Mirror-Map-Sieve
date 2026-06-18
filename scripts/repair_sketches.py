#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
Script to repair truncated Lean 4 sketches in achievement_output/v16_offline/.
If a file has no theorem or is empty, it generates a fresh Lean 4 sketch.
If a file has a truncated theorem definition, it completes and repairs it.
Uses raw REST Vertex AI calls with strict timeout and retries to prevent hanging.
"""
from __future__ import annotations

import os
import glob
import json
import re
import sys
import time
from pathlib import Path
import google.auth
import google.auth.transport.requests
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
V16_DIR = REPO_ROOT / "achievement_output" / "v16_offline"
PROBLEMS_JSON = Path("/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/scratch/HorizonMath/data/problems_full.json")

def call_gemini_vertex(prompt: str, retries: int = 3, timeout: int = 120) -> str:
    credentials, project = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    token = credentials.token
    
    url = "https://us-central1-aiplatform.googleapis.com/v1/projects/gen-lang-client-0625573011/locations/us-central1/publishers/google/models/gemini-2.5-flash:generateContent"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    backoff = 2
    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 200:
                res_json = response.json()
                return res_json['candidates'][0]['content']['parts'][0]['text']
            else:
                print(f"    [Attempt {attempt+1}/{retries}] Vertex API Error (status {response.status_code}): {response.text}")
        except Exception as e:
            print(f"    [Attempt {attempt+1}/{retries}] Request failed: {e}")
        if attempt < retries - 1:
            time.sleep(backoff)
            backoff *= 2
        
    raise RuntimeError("Failed to call Vertex AI after maximum retries.")

def main():
    if not PROBLEMS_JSON.exists():
        print(f"Error: {PROBLEMS_JSON} does not exist.")
        return
        
    with open(PROBLEMS_JSON, "r") as f:
        problems = json.load(f)
    
    problems_by_id = {p["id"]: p for p in problems}
    
    lean_files = sorted(V16_DIR.glob("*.lean"))
    print(f"Found {len(lean_files)} Lean files to inspect.")
    
    for idx, f in enumerate(lean_files, 1):
        pid = f.stem
        print(f"[{idx}/{len(lean_files)}] Inspecting {pid}...")
        
        with open(f, "r") as fd:
            content = fd.read()
            
        prob = problems_by_id.get(pid)
        if not prob:
            print(f"  -> Warning: No problem metadata found for {pid}")
            continue
            
        prompt_text = prob.get("prompt", "")
        
        # Check if it has a theorem definition
        has_theorem = "theorem " in content or "def " in content
        
        lines = content.splitlines()
        last_non_empty = [l for l in lines if l.strip()]
        
        is_truncated = False
        if last_non_empty:
            last_line = last_non_empty[-1].strip()
            if any(last_line.endswith(x) for x in ["-", "+", "=", "→", "*", "/", "∧", "∨", "↔", "(", ",", "theor"]):
                is_truncated = True
            else:
                valid_ends = [".", "}", "sorry", "ring", "simp", "rfl", "positivity", "omega", "norm_num", "decide", "aesop", "tauto", "linarith", "continuity", "measurability", "cast", "gcongr", "axiom", "Prop", "ℝ", "Prop :=", "Type", "Type*", "Prop", ":= by", "by rfl", "by ring", "end", "noncomputable", "⟩", ")", "]", "\"", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
                ends_validly = any(last_line.endswith(x) for x in valid_ends) or last_line.startswith("end") or last_line.startswith("--") or last_line.endswith("-/")
                is_truncated = not ends_validly
            
        if not has_theorem or len(content.strip()) < 100 or is_truncated:
            if not has_theorem or len(content.strip()) < 100:
                print(f"  -> File is empty or has no theorem. Generating a fresh sketch...")
                prompt = f"""You are Galois, a Lean 4 formalization expert.
Please write a complete, valid Lean 4 proof sketch for the following mathematical problem.

Problem ID: {pid}
Conjecture/Prompt: {prompt_text}

Your Lean 4 code should:
1. Include standard imports (e.g. Mathlib.Tactic, Mathlib.Analysis.SpecialFunctions.Integrals, etc. as appropriate).
2. Declare the conjecture/theorem with its proper parameters and type signature.
3. Ensure that any unproven steps or the main proof ends with `sorry` stubs so the code compiles as a valid sketch.
4. Do not use placeholders or leave incomplete syntax. The code must be syntactically valid Lean 4.

Provide ONLY the complete Lean 4 code. Do not wrap it in markdown block quotes (no ```lean blocks), just output plain Lean code.
"""
            else:
                print(f"  -> File appears truncated. Last line: '{last_line}'. Repairing...")
                prompt = f"""You are Galois, a Lean 4 formalization expert.
The following Lean 4 file has been truncated at the end due to a length limit during generation.

Problem ID: {pid}
Conjecture/Prompt: {prompt_text}

Here is the content of the truncated file:
```lean
{content}
```

Please repair the truncated lines.
Specifically:
1. Complete the theorem declaration (e.g. {pid}_conjecture) with its proper parameters and type signature.
2. Add sorry gaps where appropriate so the code is syntactically valid Lean 4 (e.g. no half-finished expressions).
3. Retain the imports, helper definitions, and comments already present in the file.
4. Ensure the file has valid Lean 4 syntax. Do not leave unfinished lines.

Provide ONLY the complete, repaired Lean 4 code. Do not wrap it in markdown block quotes (no ```lean blocks), just output plain Lean code.
"""
            try:
                repaired_code = call_gemini_vertex(prompt)
                repaired_code = repaired_code.strip()
                
                # Strip markdown fences if LLM generated them anyway
                repaired_code = re.sub(r"^```(?:lean4?|lean)?\n?", "", repaired_code)
                repaired_code = repaired_code.rstrip("`").strip()
                
                with open(f, "w") as out_fd:
                    out_fd.write(repaired_code)
                print(f"  -> Successfully updated.")
            except Exception as e:
                print(f"  -> Error calling Gemini: {e}")
        else:
            print("  -> File is already complete.")

if __name__ == "__main__":
    main()
