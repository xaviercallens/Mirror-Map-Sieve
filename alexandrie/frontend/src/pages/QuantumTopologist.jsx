import { useState } from 'react';

function QuantumTopologist() {
  const [nValue, setNValue] = useState(10);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSolve = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('https://runux-math-kernel-service-cfhmhmvv5a-uc.a.run.app/api/solve/kn_crossing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ n: parseInt(nValue) })
      });
      if (!response.ok) throw new Error('Network response was not ok');
      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel">
      <h2>The Quantum Topologist</h2>
      <p style={{ color: 'var(--text-secondary)' }}>
        Explore applications of the Zarankiewicz crossing number conjecture solver. 
        Optimize superconducting logic layout by finding embeddings that strictly minimize edge crossings.
      </p>
      
      <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', marginTop: '2rem' }}>
        <div style={{ flex: '1 1 300px' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Graph Size (K_n):
          </label>
          <input 
            type="number" 
            value={nValue} 
            onChange={(e) => setNValue(e.target.value)} 
            min="1"
          />
          <button onClick={handleSolve} disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Computing...' : 'Calculate Embedded Crossing Number'}
          </button>
          
          {error && <div style={{ color: '#ef4444', marginTop: '1rem' }}>Error: {error}</div>}

          {result && (
            <div style={{ marginTop: '2rem', padding: '1.5rem', background: 'rgba(0,0,0,0.3)', borderRadius: '8px' }}>
              <h3 style={{ color: 'var(--accent-cyan)' }}>Solver Results (n = {result.n})</h3>
              <p><strong>Theoretical Bound (Zarankiewicz):</strong> {result.theoretical_bound}</p>
              <p><strong>Computed Heuristic Minimum:</strong> {result.computed_heuristic}</p>
              <p><strong>Solver Execution Time:</strong> {result.execution_time_ms} ms</p>
            </div>
          )}
        </div>
        
        <div style={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <img 
            src="/assets/quantum_optimized.png" 
            alt="Quantum Optimization Comparison" 
            style={{ width: '100%', maxWidth: '400px', borderRadius: '12px', border: '1px solid var(--accent-cyan)', boxShadow: '0 0 20px rgba(34, 211, 238, 0.2)' }} 
          />
          <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '1rem' }}>
            Comparison: Traditional high-crossing routing (left) vs. our math solver's crossing-free planar embedding (right).
          </p>
        </div>
      </div>

      <div style={{ marginTop: '3rem', padding: '1.5rem', border: '1px solid var(--glass-border)', borderRadius: '8px' }}>
        <h3 style={{ color: 'var(--text-primary)' }}>Mathematical Context & Intellectual Property</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
          This solver targets Guy's/Zarankiewicz’s Conjecture, optimizing layout crossings for VLSI and Quantum architectures.
          Developed using a Hexagonal Rust Architecture by Xavier Callens and Socrate AI.
        </p>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <a href="/documents/Zarankiewicz.lean" target="_blank" rel="noopener noreferrer">
            <button style={{ fontSize: '0.8rem' }}>View Lean 4 Formal Proof</button>
          </a>
          <a href="/documents/quantum_crypto_applications.md" target="_blank" rel="noopener noreferrer">
            <button style={{ fontSize: '0.8rem' }}>View Applications (MD)</button>
          </a>
          <a href="/documents/eiffel_patent_claims.pdf" target="_blank" rel="noopener noreferrer">
            <button style={{ fontSize: '0.8rem' }}>View Patent Claims (PDF)</button>
          </a>
        </div>
      </div>
    </div>
  );
}

export default QuantumTopologist;
