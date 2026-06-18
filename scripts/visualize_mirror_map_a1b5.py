#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Hypersurface and Mirror Map Visualizer for Callens-Socrates Sequence (S15)
--------------------------------------------------------------------------
Generates:
1. 3D surface plot of a projection slice of the 6-variable Calabi-Yau rational function.
2. Log-scale curve showing the growth and exact integrality of the mirror map coefficients.
"""

import os
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from pathlib import Path

# Use a sleek modern styling theme matching the UI
plt.style.use('dark_background')

def generate_hypersurface_projection():
    print("Generating hypersurface projection plot for a=1, b=5...")
    
    # Generate grid
    x2 = np.linspace(-1.5, 0.9, 200)
    x3 = np.linspace(-1.5, 0.9, 200)
    X2, X3 = np.meshgrid(x2, x3)
    
    # Slice equation: x1 = 8 / (1 - x2 - x3 + 2*x2*x3)
    denom = 1.0 - X2 - X3 + 2.0 * X2 * X3
    X1 = 8.0 / denom
    X1[np.abs(denom) < 0.05] = np.nan
    X1[X1 > 30.0] = np.nan
    X1[X1 < -30.0] = np.nan
    
    fig = plt.figure(figsize=(10, 8), dpi=150)
    ax = fig.add_subplot(111, projection='3d')
    
    # Render with a stunning magma color gradient
    surf = ax.plot_surface(X2, X3, X1, cmap=cm.magma, edgecolor='none', alpha=0.95, linewidth=0, antialiased=True)
    
    # Customize axis properties for clean design
    ax.set_title("Callens-Socrates Hypersurface 3D Projection", fontsize=16, color="#00ffcc", pad=20, weight='bold')
    ax.set_xlabel(r"$x_2$ Coordinate", labelpad=10, color="#ffffff")
    ax.set_ylabel(r"$x_3$ Coordinate", labelpad=10, color="#ffffff")
    ax.set_zlabel(r"$x_1 = f(x_2, x_3)$ Projection", labelpad=10, color="#ffffff")
    
    # Customize grid appearance
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor('none')
    ax.yaxis.pane.set_edgecolor('none')
    ax.zaxis.pane.set_edgecolor('none')
    
    ax.view_init(elev=25, azim=-135)
    
    # Add floating subtitle as text
    fig.text(0.5, 0.04, r"Slice projection: $1 - x_1(1-x_2)(1-x_3)(1-x_4)(1-x_5)(1-x_6) - x_1 x_2 x_3 x_4 x_5 x_6 = 0$ at $x_4=x_5=x_6=0.5$",
             ha="center", fontsize=11, color="#888888", style="italic")
             
    # Save directly to the artifacts folder
    artifact_path = Path("/Users/xcallens/.gemini/antigravity/brain/97f6aad0-8120-443d-9423-480ea442100a/hypersurface_projection_a1b5.png")
    plt.savefig(artifact_path, bbox_inches='tight', transparent=True)
    
    # Also save to frontend public assets
    frontend_path = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie/frontend/public/assets/hypersurface_projection_a1b5.png")
    frontend_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(frontend_path, bbox_inches='tight', transparent=True)
    
    plt.close()
    print(f"Saved: {artifact_path} and {frontend_path}")

def generate_mirror_map_integrality():
    print("Generating mirror map integrality plot for a=1, b=5...")
    
    # Load coefficients from JSON
    json_path = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie_data/mirror_symmetry_results_a1b5.json")
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
        
    ax.set_title("Mirror Map Integrality Curve (Callens-Socrates $S_{15}$)", fontsize=14, color="#00ffcc", weight='bold', pad=15)
    ax.set_xlabel("Coefficient Order $d$ (for $q^d$)", fontsize=12)
    ax.set_ylabel("Coefficient Value $q_d$ (log scale)", fontsize=12)
    ax.grid(True, which="both", linestyle=':', alpha=0.3)
    ax.legend(loc='lower right', frameon=True, facecolor='#111111', edgecolor='#00ffcc')
    
    # Highlight the exact integer label
    ax.text(2.2, 10**22, "All coefficients verified as exact integers\n(Lian-Yau mirror symmetry property)", 
            color='#00ffcc', fontsize=9, bbox=dict(facecolor='black', alpha=0.5, edgecolor='#00ffcc', boxstyle='round,pad=0.5'))
            
    plt.tight_layout()
    
    # Save to public assets
    out_path = Path("alexandrie/frontend/public/assets/mirror_map_integrality_a1b5.png")
    os.makedirs(out_path.parent, exist_ok=True)
    plt.savefig(out_path, bbox_inches='tight')
    
    # Save directly to the artifacts folder
    artifact_path = Path("/Users/xcallens/.gemini/antigravity/brain/97f6aad0-8120-443d-9423-480ea442100a/mirror_map_integrality_a1b5.png")
    os.makedirs(artifact_path.parent, exist_ok=True)
    plt.savefig(artifact_path, bbox_inches='tight', transparent=True)
    plt.close()
    
    print(f"Saved: {out_path} and {artifact_path}")

def main():
    generate_hypersurface_projection()
    generate_mirror_map_integrality()
    print("All S15 visualizations completed successfully.")

if __name__ == "__main__":
    main()
