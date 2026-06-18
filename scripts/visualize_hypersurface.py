#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Hypersurface Projection Visualizer
---------------------------------
Generates a stunning 3D surface plot of a projection slice of the 5D rational function
defining the Callens-Schmidt sequence, and saves it to the artifacts directory.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from pathlib import Path

# Use a sleek modern styling theme
plt.style.use('dark_background')

def main():
    print("Generating hypersurface projection plot...")
    
    # Generate grid
    x2 = np.linspace(-1.5, 0.9, 200)
    x3 = np.linspace(-1.5, 0.9, 200)
    X2, X3 = np.meshgrid(x2, x3)
    
    # Hypersurface projection slice equation: x1 = 1 / ((1 - x2) * (1 - x3))
    # We mask values close to the poles to prevent infinite spikes in rendering
    denom = (1.0 - X2) * (1.0 - X3)
    X1 = 1.0 / denom
    X1[np.abs(denom) < 0.05] = np.nan
    X1[X1 > 10.0] = np.nan
    X1[X1 < -10.0] = np.nan
    
    fig = plt.figure(figsize=(10, 8), dpi=150)
    ax = fig.add_subplot(111, projection='3d')
    
    # Render with a stunning plasma color gradient
    surf = ax.plot_surface(X2, X3, X1, cmap=cm.plasma, edgecolor='none', alpha=0.95, linewidth=0, antialiased=True)
    
    # Customize axis properties for clean design
    ax.set_title("Callens-Schmidt Hypersurface 3D Projection", fontsize=16, color="#ffcc00", pad=20, weight='bold')
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
    
    ax.view_init(elev=28, azim=-128)
    
    # Add floating subtitle as text
    fig.text(0.5, 0.04, r"Slice projection: $1 - x_1(1-x_2)(1-x_3) = 0$ of the 5-variable Calabi-Yau rational generator",
             ha="center", fontsize=11, color="#888888", style="italic")
             
    # Save directly to the artifacts folder
    artifact_path = Path("/Users/xcallens/.gemini/antigravity/brain/97f6aad0-8120-443d-9423-480ea442100a/hypersurface_projection.png")
    plt.savefig(artifact_path, bbox_inches='tight', transparent=True)
    plt.close()
    
    print(f"🎉 Plot successfully saved to {artifact_path}")

if __name__ == "__main__":
    main()
