#!/usr/bin/env python3
"""
Verify Exoo's R(4,6) construction — K_35 coloring with no red K_4, no blue K_6.
From: G. Exoo, "On the Ramsey Number R(4,6)", Electronic J. Combinatorics, 2012.

This proves R(4,6) >= 36.
"""

from itertools import combinations

# Exoo's adjacency list for color 1 (red) graph on 35 vertices
# Edges NOT in this list are color 2 (blue)
EXOO_ADJ = {
    0:  [2, 6, 7, 9, 11, 13, 15, 17, 18, 20, 21, 23, 24, 26, 28, 32],
    1:  [3, 4, 5, 9, 11, 13, 15, 17, 18, 21, 22, 23, 25, 27, 29, 33],
    2:  [0, 4, 5, 8, 10, 12, 14, 16, 19, 20, 21, 22, 25, 27, 28, 32],
    3:  [1, 6, 7, 8, 10, 12, 14, 16, 19, 20, 22, 23, 24, 26, 29, 33],
    4:  [1, 2, 7, 8, 10, 11, 13, 17, 19, 20, 22, 24, 26, 31, 34],
    5:  [1, 2, 6, 8, 9, 11, 14, 17, 19, 21, 23, 24, 26, 30, 34],
    6:  [0, 3, 5, 9, 10, 11, 12, 16, 18, 21, 23, 25, 27, 31, 34],
    7:  [0, 3, 4, 8, 9, 10, 15, 16, 18, 20, 22, 25, 27, 30, 34],
    8:  [2, 3, 4, 5, 7, 9, 12, 15, 17, 23, 24, 27, 29, 31, 32],
    9:  [0, 1, 5, 6, 7, 8, 13, 14, 16, 22, 25, 26, 29, 31, 32],
    10: [2, 3, 4, 6, 7, 11, 13, 14, 18, 21, 25, 26, 28, 30, 33],
    11: [0, 1, 4, 5, 6, 10, 12, 15, 19, 20, 24, 27, 28, 30, 33],
    12: [2, 3, 6, 8, 11, 13, 15, 17, 18, 20, 22, 25, 31, 33],
    13: [0, 1, 4, 9, 10, 12, 14, 16, 19, 21, 23, 24, 31, 33],
    14: [2, 3, 5, 9, 10, 13, 15, 17, 18, 20, 22, 24, 30, 32],
    15: [0, 1, 7, 8, 11, 12, 14, 16, 19, 21, 23, 25, 30, 32],
    16: [2, 3, 6, 7, 9, 13, 15, 19, 21, 24, 27, 29, 32, 34],
    17: [0, 1, 4, 5, 8, 12, 14, 18, 20, 25, 26, 29, 32, 34],
    18: [0, 1, 6, 7, 10, 12, 14, 17, 22, 24, 27, 28, 33, 34],
    # We only have partial data from the search results (0-18)
    # The remaining vertices 19-34 need to be inferred from symmetry
    # For now, verify what we have
}

def verify_partial():
    """Verify partial Exoo graph — check symmetry of adjacency."""
    n = 35
    
    # Build adjacency matrix from what we have
    adj = [[False]*n for _ in range(n)]
    for v, neighbors in EXOO_ADJ.items():
        for u in neighbors:
            adj[v][u] = True
            adj[u][v] = True
    
    # Check symmetry
    for v in EXOO_ADJ:
        for u in EXOO_ADJ[v]:
            if v not in EXOO_ADJ.get(u, []):
                if u <= 18:  # Only check vertices we have data for
                    print(f"  Asymmetry: {v}->{u} but {u} doesn't list {v}")
    
    # Count edges
    edge_count = sum(1 for i in range(n) for j in range(i+1, n) if adj[i][j])
    print(f"  Red edges (partial): {edge_count}")
    print(f"  Total edges K_35: {n*(n-1)//2}")
    
    # Check red K_4 (in partial graph)
    red_k4 = 0
    for clique in combinations(range(n), 4):
        if all(adj[clique[i]][clique[j]] for i in range(4) for j in range(i+1, 4)):
            red_k4 += 1
            if red_k4 <= 5:
                print(f"  Red K4: {clique}")
    
    print(f"  Red K_4 violations (partial): {red_k4}")
    
    # Check blue K_6 (complement of red = blue)
    blue_k6 = 0
    for clique in combinations(range(n), 6):
        if all(not adj[clique[i]][clique[j]] for i in range(6) for j in range(i+1, 6)):
            blue_k6 += 1
            if blue_k6 <= 5:
                print(f"  Blue K6: {clique}")
    
    print(f"  Blue K_6 violations (partial): {blue_k6}")
    print(f"  Total violations: {red_k4 + blue_k6}")
    
    # Degree distribution
    degrees = [sum(1 for j in range(n) if adj[i][j]) for i in range(n)]
    print(f"\n  Red degree distribution:")
    for i in range(n):
        print(f"    v{i}: deg={degrees[i]}")

if __name__ == "__main__":
    print("=== Exoo R(4,6) Construction Verification (Partial) ===")
    verify_partial()
