import { useState } from 'react';

function CryptographicGeometer() {
  const [manifoldId, setManifoldId] = useState('c5_manifold_default');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSolve = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('https://runux-math-kernel-service-cfhmhmvv5a-uc.a.run.app/api/solve/calabi_yau', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ manifold_id: manifoldId })
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
      <h2>The Cryptographic Geometer</h2>
      <p style={{ color: 'var(--text-secondary)' }}>
        Leverage the hypergeometric reductions of c_5 period identities to generate new topological lattices 
        resistant to both classical lattice-reduction (LLL) and quantum Grover searches.
      </p>
      
      <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', marginTop: '2rem' }}>
        <div style={{ flex: '1 1 300px' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Manifold Topology ID:
          </label>
          <input 
            type="text" 
            value={manifoldId} 
            onChange={(e) => setManifoldId(e.target.value)} 
          />
          <button onClick={handleSolve} disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Integrating...' : 'Compute Period Integral & Verify Identity'}
          </button>

          {error && <div style={{ color: '#ef4444', marginTop: '1rem' }}>Error: {error}</div>}

          {result && (
            <div style={{ marginTop: '2rem', padding: '1.5rem', background: 'rgba(0,0,0,0.3)', borderRadius: '8px' }}>
              <h3 style={{ color: 'var(--accent-purple)' }}>Integration Results</h3>
              <p><strong>Manifold ID:</strong> {result.manifold_id}</p>
              <p><strong>Period Value:</strong> {result.period_value}</p>
              <p>
                <strong>Identity Verification:</strong>{' '}
                <span style={{ color: result.verified_identity ? '#10b981' : '#ef4444', fontWeight: 'bold' }}>
                  {result.verified_identity ? 'VERIFIED (Hypergeometric Match)' : 'FAILED'}
                </span>
              </p>
              <p><strong>Numerical Integration Time:</strong> {result.execution_time_ms} ms</p>
            </div>
          )}
        </div>

        <div style={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <img 
            src="/assets/crypto_optimized.png" 
            alt="Cryptography Topology Comparison" 
            style={{ width: '100%', maxWidth: '400px', borderRadius: '12px', border: '1px solid var(--accent-purple)', boxShadow: '0 0 20px rgba(192, 132, 252, 0.2)' }} 
          />
          <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '1rem' }}>
            Comparison: Traditional rigid lattice cryptography (left) vs. our novel Calabi-Yau topological boundaries (right).
          </p>
        </div>
      </div>

      <div style={{ marginTop: '3rem', padding: '1.5rem', border: '1px solid var(--glass-border)', borderRadius: '8px' }}>
        <h3 style={{ color: 'var(--text-primary)' }}>Mathematical Context & Intellectual Property</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
          This module computes hypergeomtric reductions of c_5 Picard-Fuchs periods, generating novel post-quantum lattice boundaries.
          Developed using an exact/numerical hybrid Rust Architecture by Xavier Callens and Socrate AI.
        </p>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <a href="/documents/Periodex.lean" target="_blank" rel="noopener noreferrer">
            <button style={{ fontSize: '0.8rem' }}>View Lean 4 Invariants</button>
          </a>
          <a href="/documents/quantum_crypto_applications.md" target="_blank" rel="noopener noreferrer">
            <button style={{ fontSize: '0.8rem' }}>View Applications (MD)</button>
          </a>
          <a href="/documents/eiffel_patent_claims.tex" target="_blank" rel="noopener noreferrer">
            <button style={{ fontSize: '0.8rem' }}>View Patent Claims (TeX)</button>
          </a>
        </div>
      </div>
    </div>
  );
}

export default CryptographicGeometer;
