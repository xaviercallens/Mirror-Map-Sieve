import pandas as pd
import numpy as np
import networkx as nx
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

def generate_synthetic_kaggle_airlines(num_airports=500, num_routes=3000):
    """
    Generates synthetic data mimicking the OpenFlights/Kaggle datasets, 
    but strictly utilizing a Barabasi-Albert model to enforce real-world 
    hub-and-spoke business patterns (power-law degree distribution).
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Generating synthetic airline network with {num_airports} airports and {num_routes} target routes...")
    
    # 1. Generate Airports
    np.random.seed(42)
    lats = np.random.uniform(-90, 90, num_airports)
    lons = np.random.uniform(-180, 180, num_airports)
    airport_ids = np.arange(1, num_airports + 1)
    
    # Assign 'hubs' vs 'regional' based on size
    airports_df = pd.DataFrame({
        'AirportID': airport_ids,
        'Name': [f"Airport_{i}" for i in airport_ids],
        'Latitude': lats,
        'Longitude': lons
    })
    
    # 2. Generate Routes using preferential attachment (hub-and-spoke)
    # BA model guarantees power-law, representing major hubs like ATL, ORD, LHR
    m = max(1, int(num_routes / num_airports))
    G = nx.barabasi_albert_graph(num_airports, m, seed=42)
    
    routes = []
    for u, v in G.edges():
        routes.append({'SourceID': u + 1, 'DestID': v + 1})
        # Add reverse route (flights usually go both ways)
        routes.append({'SourceID': v + 1, 'DestID': u + 1})
        
    routes_df = pd.DataFrame(routes)
    
    # Save to CSV
    airports_path = os.path.join(DATA_DIR, 'synthetic_airports.csv')
    routes_path = os.path.join(DATA_DIR, 'synthetic_routes.csv')
    airports_df.to_csv(airports_path, index=False)
    routes_df.to_csv(routes_path, index=False)
    
    print(f"✅ Data generated: {len(airports_df)} airports, {len(routes_df)} routes.")
    return airports_df, routes_df

def load_network_data():
    """Loads existing data or generates synthetic data if not found."""
    airports_path = os.path.join(DATA_DIR, 'synthetic_airports.csv')
    routes_path = os.path.join(DATA_DIR, 'synthetic_routes.csv')
    
    if not os.path.exists(airports_path) or not os.path.exists(routes_path):
        return generate_synthetic_kaggle_airlines()
    else:
        return pd.read_csv(airports_path), pd.read_csv(routes_path)

def get_networkx_graph():
    _, routes_df = load_network_data()
    G = nx.DiGraph()
    for _, row in routes_df.iterrows():
        G.add_edge(row['SourceID'], row['DestID'])
    return G

if __name__ == "__main__":
    generate_synthetic_kaggle_airlines()
