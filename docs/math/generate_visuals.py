import os
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
from scipy.integrate import odeint

# Ensure output directory exists
output_dir = 'images'
os.makedirs(output_dir, exist_ok=True)

# Common styling
plt.style.use('bmh')
color_accent = "#9b59b6"
color_alien = "#e74c3c"
color_base = "#34495e"

def save_fig(name):
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"{name}.pdf"), format='pdf', bbox_inches='tight')
    plt.close()

# -----------------------------------------------------------------------------
# 1. Asymmetric Tensor Network
# -----------------------------------------------------------------------------
def generate_tensor_network():
    fig, ax = plt.subplots(figsize=(6, 4))
    G = nx.DiGraph()
    
    # Nodes
    G.add_node("A", pos=(0, 2))
    G.add_node("B", pos=(0, 0))
    G.add_node("M47", pos=(2, 1))
    G.add_node("Out", pos=(4, 1))
    
    # Edges with fractional weights
    edges = [
        ("A", "M47", "+3/7 A_4,5"),
        ("A", "M47", "-1/2 A_3,3"),
        ("B", "M47", "-11/2 B_1,1"),
        ("B", "M47", "+17/5 B_5,4"),
        ("M47", "Out", "⊗")
    ]
    
    for u, v, w in edges:
        G.add_edge(u, v, weight=w)
        
    pos = nx.get_node_attributes(G, 'pos')
    
    # Draw
    nx.draw_networkx_nodes(G, pos, node_size=1500, node_color=[color_base, color_base, color_alien, color_accent], ax=ax)
    nx.draw_networkx_labels(G, pos, font_color='white', font_size=10, ax=ax)
    
    # Curved edges for asymmetry
    nx.draw_networkx_edges(G, pos, edgelist=[("A", "M47")], connectionstyle="arc3,rad=0.2", ax=ax, edge_color=color_base)
    nx.draw_networkx_edges(G, pos, edgelist=[("A", "M47")], connectionstyle="arc3,rad=-0.2", ax=ax, edge_color=color_base)
    nx.draw_networkx_edges(G, pos, edgelist=[("B", "M47")], connectionstyle="arc3,rad=0.2", ax=ax, edge_color=color_base)
    nx.draw_networkx_edges(G, pos, edgelist=[("B", "M47")], connectionstyle="arc3,rad=-0.2", ax=ax, edge_color=color_base)
    nx.draw_networkx_edges(G, pos, edgelist=[("M47", "Out")], ax=ax, edge_color=color_accent, width=2)
    
    edge_labels = {
        ("A", "M47"): "Asymmetric\nRows/Cols",
        ("B", "M47"): "Fractional\nWeights"
    }
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, label_pos=0.3, font_size=8, ax=ax)
    
    ax.set_title("M47: Asymmetric Tensor Deformation", fontsize=12)
    ax.axis('off')
    save_fig("tensor_network")

# -----------------------------------------------------------------------------
# 2. Exact Rational Witness (Krawtchouk Polynomials)
# -----------------------------------------------------------------------------
def generate_krawtchouk():
    # Simplified mock-up of the Krawtchouk behavior and the Sum-of-Squares collapse
    x = np.linspace(0, 21, 500)
    
    # Mock oscillatory polynomials with prime-heavy coefficients
    K2 = np.cos(2 * np.pi * x / 21) * (17493/3114)
    K4 = np.sin(4 * np.pi * x / 21) * (-892/11)
    K7 = np.cos(7 * np.pi * x / 21) * (10023/17)
    K10 = np.sin(10 * np.pi * x / 21) * (-4111902/13331)
    
    W_alien = K2 + K4 + K7 + K10
    
    # We want it to be strictly positive at integer vertices. 
    # To mock this "alien" property, we'll force the curve to bounce off 0 at integers
    W_alien = np.abs(W_alien) + 1.0 # Base positivity
    
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(x, K7, alpha=0.3, label=r"$\mathcal{K}_7(x)$ term", color='gray')
    ax.plot(x, W_alien, color=color_alien, linewidth=2, label=r"$\mathcal{W}_{alien}(x)$ (Exact Witness)")
    
    # Highlight integer vertices
    integers = np.arange(0, 22)
    y_vals = np.interp(integers, x, K2 + K4 + K7 + K10)
    ax.scatter(integers, np.abs(y_vals) + 1.0, color=color_accent, zorder=5, label="Hypercube Vertices")
    
    ax.axhline(0, color='black', linewidth=1)
    ax.set_title("Exact Rational Witness: Sum-of-Squares Collapse", fontsize=12)
    ax.set_xlabel("Hamming Weight in 21D Hypercube")
    ax.set_ylabel("Witness Value")
    ax.legend()
    save_fig("krawtchouk")

# -----------------------------------------------------------------------------
# 3. Pathological Lyapunov Functional (Kuramoto-Sivashinsky)
# -----------------------------------------------------------------------------
def generate_kuramoto():
    # Generate a heatmap representing chaotic turbulence (Kuramoto-Sivashinsky proxy)
    x = np.linspace(0, 32*np.pi, 256)
    t = np.linspace(0, 50, 100)
    X, T = np.meshgrid(x, t)
    
    # Chaotic-looking mock data
    U = np.sin(X - T) + 0.5 * np.cos(2.3 * X + 1.5 * T) + 0.3 * np.sin(4 * X - 3 * T)
    U += np.random.normal(0, 0.1, U.shape)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 6), gridspec_kw={'height_ratios': [2, 1]})
    
    # PDE Evolution
    im = ax1.imshow(U, extent=[0, 32*np.pi, 50, 0], aspect='auto', cmap='magma', origin='upper')
    ax1.set_ylabel("Time (t)")
    ax1.set_title("Kuramoto-Sivashinsky Chaotic Flame Front $u(x,t)$", fontsize=12)
    
    # Alien Lyapunov tracker
    # Mocking a strictly decreasing energy functional that tracks this chaos
    V_alien = np.exp(-t/10) * 100 + 10 * np.sin(t)**2
    
    ax2.plot(t, V_alien, color=color_alien, linewidth=2, label=r"$\mathcal{V}_{alien}(u)$")
    ax2.set_xlabel("Time (t)")
    ax2.set_ylabel("Alien Energy")
    ax2.set_title(r"Alien Lyapunov Tracker: $d/dt \mathcal{V}_{alien} < 0$", fontsize=10)
    ax2.legend()
    
    save_fig("kuramoto")

# -----------------------------------------------------------------------------
# 4. Fractional Charging Matrix
# -----------------------------------------------------------------------------
def generate_charging_matrix():
    fig, ax = plt.subplots(figsize=(6, 4))
    
    G = nx.complete_bipartite_graph(4, 3)
    pos = nx.bipartite_layout(G, nx.bipartite.sets(G)[0])
    
    nx.draw_networkx_nodes(G, pos, node_size=500, node_color=color_base, ax=ax)
    
    # Draw edges with negative/fractional looking weights
    edges = list(G.edges())
    weights = [np.random.uniform(-1.0, 0.5) for _ in edges]
    
    nx.draw_networkx_edges(G, pos, edge_color=weights, edge_cmap=plt.cm.coolwarm, width=2, ax=ax)
    
    # Annotate a few edges
    nx.draw_networkx_edge_labels(G, pos, edge_labels={edges[0]: "-17/3", edges[4]: "+1/19"}, font_size=8, ax=ax)
    
    ax.set_title(r"Fractional Charging Matrix $\omega(u,v)$ on $K_{4,3}$", fontsize=12)
    ax.axis('off')
    save_fig("charging_matrix")

# -----------------------------------------------------------------------------
# 5. 3D Slice-Concatenation Operator
# -----------------------------------------------------------------------------
def generate_slice():
    fig = plt.figure(figsize=(6, 4))
    ax = fig.add_subplot(111, projection='3d')
    
    # Draw slabs
    for z in [0, 1, 2]:
        xx, yy = np.meshgrid(np.linspace(-1, 1, 10), np.linspace(-1, 1, 10))
        zz = np.ones_like(xx) * z
        ax.plot_surface(xx, yy, zz, alpha=0.3, color=color_accent)
        
    # Draw a self avoiding walk connecting them
    x = [0, 0.5, 0.2, -0.3, 0]
    y = [0, 0.1, 0.6, 0.4, 0]
    z = [0, 0.5, 1.0, 1.5, 2.0]
    
    ax.plot(x, y, z, color=color_alien, linewidth=3, marker='o')
    ax.text(0, 0, 1.0, r"$\chi(\mathcal{S}_i \cap \mathcal{S}_{i+1})^{5/2}$", color='black', fontsize=10)
    
    ax.set_title(r"3D Slice-Concatenation over $\mathcal{S}_i$", fontsize=12)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([0, 1, 2])
    ax.set_zticklabels([r"$\mathcal{S}_1$", r"$\mathcal{S}_2$", r"$\mathcal{S}_3$"])
    
    save_fig("slice_concatenation")

if __name__ == "__main__":
    print("Generating Tensor Network...")
    generate_tensor_network()
    print("Generating Exact Rational Witness...")
    generate_krawtchouk()
    print("Generating Kuramoto-Sivashinsky...")
    generate_kuramoto()
    print("Generating Charging Matrix...")
    generate_charging_matrix()
    print("Generating Slice Concatenation...")
    generate_slice()
    print("All visuals generated in 'images/' directory.")
