import numpy as np
import matplotlib.pyplot as plt

def generate_lattice_visualization(filename):
    np.random.seed(42)
    
    # Define a 2D lattice basis
    b1 = np.array([2.0, 0.5])
    b2 = np.array([-0.5, 2.0])
    
    points = []
    for i in range(-5, 6):
        for j in range(-5, 6):
            points.append(i * b1 + j * b2)
    points = np.array(points)
    
    # Generate some LWE noise points
    target_point = 2 * b1 + 1 * b2
    noise = np.random.normal(0, 0.3, size=(50, 2))
    lwe_samples = target_point + noise
    
    plt.figure(figsize=(8, 6))
    
    # Plot lattice points
    plt.scatter(points[:, 0], points[:, 1], c='gray', alpha=0.5, label='Lattice $\Lambda$')
    
    # Plot the LWE samples
    plt.scatter(lwe_samples[:, 0], lwe_samples[:, 1], c='red', s=10, alpha=0.8, label='LWE Samples ($As + e$)')
    
    # Plot the target lattice point
    plt.scatter(target_point[0], target_point[1], c='blue', marker='x', s=100, label='Secret Point ($As$)')
    
    # Draw basis vectors
    plt.arrow(0, 0, b1[0], b1[1], head_width=0.2, head_length=0.2, fc='black', ec='black', length_includes_head=True, zorder=5)
    plt.arrow(0, 0, b2[0], b2[1], head_width=0.2, head_length=0.2, fc='black', ec='black', length_includes_head=True, zorder=5)
    plt.text(b1[0]/2, b1[1]/2 - 0.4, '$b_1$', fontsize=12)
    plt.text(b2[0]/2 - 0.4, b2[1]/2, '$b_2$', fontsize=12)
    
    plt.title('Module-LWE Concept: Finding the Secret Lattice Point Given Noisy Samples')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.axis('equal')
    
    plt.savefig(filename, bbox_inches='tight', dpi=300)
    print(f"Saved {filename}")

if __name__ == '__main__':
    generate_lattice_visualization('docs/math/images/lattice_cryptography.pdf')
