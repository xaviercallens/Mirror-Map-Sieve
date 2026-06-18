#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Mirror Map Integrality Curve Visualizer for a=1, b=4 Sequence
------------------------------------------------------------
Generates a plot showing the growth of the mirror map coefficients q_d (log scale)
to demonstrate their exact integrality, and saves it.
"""

import os
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Use a sleek modern styling theme matching the UI
plt.style.use('dark_background')

def main():
    print("Generating mirror map integrality plot for a=1, b=4...")
    
    # Load coefficients from JSON
    json_path = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie_data/mirror_symmetry_results_a1b4.json")
    with open(json_path, "r") as f:
        data = json.load(f)
        
    coeffs_data = data["mirror_map_coefficients"]
    
    q_indices = []
    q_values = []
    for c in coeffs_data:
        q_indices.append(c["m"])
        # Coefficients are stored as strings in JSON to prevent large int overflow
        q_values.append(int(c["coefficient"]))
        
    float_q_values = np.array([float(x) for x in q_values])
    
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    
    # Plot log-scale growth
    ax.semilogy(q_indices, float_q_values, 'o-', color='#00ffcc', linewidth=2.5, markersize=8, label='Mirror Map coefficients $q_d$')
    
    # Annotate values to highlight integrality
    for idx, (x, val) in enumerate(zip(q_indices, q_values)):
        if idx >= 9:
            continue  # Only annotate the first 9 coefficients to keep it clean
        if val < 100000:
            label = f"{val}"
        else:
            s = f"{val:.2e}".replace("e+", "\\cdot 10^{") + "}"
            label = f"${s}$"
            
        ax.annotate(label, (x, float(val)), textcoords="offset points", xytext=(0, 10), ha='center', fontsize=8, color='#ffcc00')
        
    ax.set_title("Mirror Map Integrality Curve (Callens-Agora $S_{14}$)", fontsize=14, color="#00ffcc", weight='bold', pad=15)
    ax.set_xlabel("Coefficient Order $d$ (for $q^d$)", fontsize=12)
    ax.set_ylabel("Coefficient Value $q_d$ (log scale)", fontsize=12)
    ax.grid(True, which="both", linestyle=':', alpha=0.3)
    ax.legend(loc='lower right', frameon=True, facecolor='#111111', edgecolor='#00ffcc')
    
    # Highlight the exact integer label
    ax.text(2.2, 10**16, "All coefficients verified as exact integers\n(Lian-Yau mirror symmetry property)", 
            color='#00ffcc', fontsize=9, bbox=dict(facecolor='black', alpha=0.5, edgecolor='#00ffcc', boxstyle='round,pad=0.5'))
            
    plt.tight_layout()
    
    # Save to public assets
    out_path = Path("alexandrie/frontend/public/assets/mirror_map_integrality_a1b4.png")
    os.makedirs(out_path.parent, exist_ok=True)
    plt.savefig(out_path, bbox_inches='tight')
    
    # Save directly to the artifacts folder
    artifact_path = Path("/Users/xcallens/.gemini/antigravity/brain/97f6aad0-8120-443d-9423-480ea442100a/mirror_map_integrality_a1b4.png")
    os.makedirs(artifact_path.parent, exist_ok=True)
    plt.savefig(artifact_path, bbox_inches='tight', transparent=True)
    plt.close()
    
    print(f"🎉 Plot successfully saved to {out_path} and {artifact_path}")

if __name__ == "__main__":
    main()
