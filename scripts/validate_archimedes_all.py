#!/usr/bin/env python3
import asyncio
import json
import time
from pathlib import Path

from agents.archimedes.agent import ArchimedesAgent
from agents.euler.agent import EulerAgent

BRAIN_DIR = Path('/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330')
DATA_DIR = BRAIN_DIR / 'scratch/HorizonMath/data'
OUTPUT_DIR = Path('/Users/xcallens/xdev/SocrateAI-Scientific-Agora/achievement_output')
V16_DIR = OUTPUT_DIR / 'v16_offline'
V14_DIR = OUTPUT_DIR / 'v14_results'
V14_BRAIN = BRAIN_DIR / 'achievement_output' / 'v14_results'
V3_BRAIN = BRAIN_DIR / 'achievement_output' / 'v3_results'

def load_sketch(pid):
    """Fallback logic to find the best sketch: v16_offline > v14 > v12"""
    # 1. v16_offline
    f16 = V16_DIR / f"{pid}_v16_offline.json"
    if f16.exists():
        d = json.loads(f16.read_text())
        return d.get('lean4_sketch', ''), d.get('conjecture_statement', ''), "v16_offline", d.get('domain', 'unknown')
        
    # 2. v14
    f14 = V14_DIR / f"{pid}_v14.json"
    if not f14.exists(): f14 = V14_BRAIN / f"{pid}_v14.json"
    if f14.exists():
        d = json.loads(f14.read_text())
        return d.get('lean4_sketch', ''), d.get('conjecture_statement', ''), "v14", d.get('domain', 'unknown')
        
    # 3. v12 (v3_results)
    # v3 uses problem_*_<pid>.json_
    if V3_BRAIN.exists():
        for f in V3_BRAIN.glob(f"problem_*_{pid}.json_*"):
            if f.exists():
                try:
                    d = json.loads(f.read_text())
                    return d.get('lean4_sketch', ''), d.get('conjecture_statement', ''), "v12", d.get('domain', 'unknown')
                except:
                    continue
                
    return "", "", "missing", "unknown"

async def main():
    print("Initializing Archimedes and Euler agents...")
    archimedes = ArchimedesAgent()
    euler = EulerAgent()
    
    problems_full = json.loads((DATA_DIR / 'problems_full.json').read_text())
    
    recap = []
    
    for i, prob in enumerate(problems_full):
        pid = prob.get('pid') or prob.get('id')
        expected_domain = prob.get('domain', 'unknown')
        
        sketch, statement, source, loaded_domain = load_sketch(pid)
        domain = loaded_domain if loaded_domain != "unknown" else expected_domain
        sorry_count = sketch.lower().count("sorry") if sketch else 0
        
        print(f"\\n[{i+1}/{len(problems_full)}] {pid} | Source: {source} | Sorry: {sorry_count}")
        
        archimedes_applied = False
        archimedes_reduction = 0
        
        if sorry_count > 0:
            print(f"  -> Running Archimedes (Method of Exhaustion) to close {sorry_count} gaps...")
            try:
                arch_res = await archimedes.run(
                    query=f"Prove sub-lemmas for HorizonMath problem: {pid}",
                    lean4_sketch=sketch,
                    domain=domain,
                    theorem_header=statement[:120] if statement else "",
                    pid=pid
                )
                arch_data = arch_res.answer
                if arch_data and arch_data.get("reduction", 0) > 0:
                    sketch = arch_data.get("lean4_sketch", sketch)
                    new_sorry = arch_data.get("sorry_count", sorry_count)
                    archimedes_reduction = arch_data.get("reduction", 0)
                    archimedes_applied = True
                    print(f"  -> Archimedes success: {sorry_count} -> {new_sorry} (-{archimedes_reduction})")
                    sorry_count = new_sorry
                else:
                    print("  -> Archimedes could not reduce gaps.")
            except Exception as e:
                print(f"  -> Archimedes error: {e}")
                
        print("  -> Verifying with Euler (Lean 4 compiler)...")
        verdict = "INCOMPLETE"
        try:
            euler_payload = (
                f"Problem: {pid} | Domain: {domain}\\n"
                f"Conjecture: {statement[:600]}\\n"
                f"Lean 4 Sketch:\\n{sketch[:2000]}\\n"
            )
            euler_res = await euler.run(
                f"Verify the conjecture for '{pid}'.\\n{euler_payload}\\n"
                f"CRITICAL — Zero-Sorry Guillotine (ZSG):\\n"
                f"  • sorry_count = {sorry_count}. If > 0 → verdict MUST be INCOMPLETE\\n"
                f"  • Only VERIFIED if sorry_count == 0 AND all goals closed\\n"
            )
            euler_conf = euler_res.confidence
            if euler_conf >= 0.85 and sorry_count == 0:
                verdict = "VERIFIED"
            elif euler_conf >= 0.65:
                verdict = "INCOMPLETE"
            else:
                verdict = "REFUTED"
        except Exception as e:
            print(f"  -> Euler error: {e}")
            verdict = "ERROR"
            
        print(f"  -> Final Verdict: {verdict}")
        
        recap.append({
            "pid": pid,
            "domain": domain,
            "source": source,
            "sorry_before_archimedes": sorry_count + archimedes_reduction if archimedes_applied else sorry_count,
            "sorry_after_archimedes": sorry_count,
            "archimedes_applied": archimedes_applied,
            "verdict": verdict
        })
        
    print("\\n=== GENERATING REPORT ===")
    report = "# 50 HorizonMath Problems: Validation & Status Recap\\n\\n"
    report += "| Problem | Domain | Source | Sorry (Start) | Sorry (End) | Archimedes | Verdict |\\n"
    report += "|---|---|---|---|---|---|---|\\n"
    
    for r in recap:
        arch_emoji = "⚙️ Used" if r["archimedes_applied"] else "➖ Skipped"
        verdict_emoji = "✅ VERIFIED" if r["verdict"] == "VERIFIED" else ("🔶 " + r["verdict"])
        report += f"| `{r['pid']}` | {r['domain']} | {r['source']} | {r['sorry_before_archimedes']} | {r['sorry_after_archimedes']} | {arch_emoji} | {verdict_emoji} |\\n"
        
    (OUTPUT_DIR / "validate_archimedes_all_report.md").write_text(report)
    print(f"Report saved to {OUTPUT_DIR / 'validate_archimedes_all_report.md'}")
    
if __name__ == "__main__":
    asyncio.run(main())
