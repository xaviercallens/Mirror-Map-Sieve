import os
import json
from alexandrie.hub import AlexandrieHub

def analyze():
    hub = AlexandrieHub()
    matches = hub.search_vault("v18_Phase2_")
    
    total_cost = 0.0
    verified_count = 0
    failed_count = 0
    
    verified_problems = []
    failed_problems = []
    
    # Store comprehensive details
    details = []
    
    for meta in matches:
        ret = hub.retrieve_artifact(meta.id)
        if not ret:
            continue
        
        m, content = ret
        name = m.id.replace("v18_Phase2_", "")
        status = m.metrics.get("status", "FAILED")
        cost = m.metrics.get("cost", 0.0)
        tier = m.metrics.get("tier", "L4")
        
        total_cost += cost
        
        sorry_count = content.count("sorry")
        
        if "VERIFIED" in status:
            verified_count += 1
            verified_problems.append(name)
        else:
            failed_count += 1
            failed_problems.append(name)
            
        details.append({
            "name": name,
            "status": status,
            "cost": cost,
            "tier": tier,
            "remaining_sorries": sorry_count
        })
        
    details.sort(key=lambda x: (x["status"] != "VERIFIED", x["name"]))
    
    report = f"# Phase 2 Comprehensive Analysis\n\n"
    report += f"## Executive Summary\n"
    report += f"- **Total Problems Analyzed**: {len(details)}\n"
    report += f"- **Successfully Verified**: {verified_count}\n"
    report += f"- **Failed**: {failed_count}\n"
    report += f"- **Total Computational Cost**: ${total_cost:.2f}\n\n"
    
    report += f"## Verified Problems\n"
    for p in verified_problems:
        report += f"- {p}\n"
        
    report += f"\n## Detailed Breakdown\n"
    report += "| Problem Name | Status | Tier | Cost | Remaining Sorries |\n"
    report += "|--------------|--------|------|------|-------------------|\n"
    for d in details:
        report += f"| {d['name']} | {d['status']} | {d['tier']} | ${d['cost']:.2f} | {d['remaining_sorries']} |\n"
        
    out_path = "/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/phase2_comprehensive_analysis.md"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(report)
        
    print(f"Generated comprehensive report at {out_path}")

if __name__ == "__main__":
    analyze()
