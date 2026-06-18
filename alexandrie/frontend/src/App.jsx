import { useState } from 'react';
import QuantumTopologist from './pages/QuantumTopologist';
import CryptographicGeometer from './pages/CryptographicGeometer';
import ArithmeticGeometer from './pages/ArithmeticGeometer';
import AlienMathIP from './pages/AlienMathIP';
import LeanStressTest from './pages/LeanStressTest';
import AdvancedTaste from './pages/AdvancedTaste';
import './index.css';

function App() {
  const [activeRoom, setActiveRoom] = useState('quantum');

  return (
    <div className="app-container">
      <header>
        <h1 className="gradient-text">Alexandrie Open Rooms</h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>
          Bridging pure mathematical discovery and industrial applications in physics and computer science.
        </p>
        
        <nav>
          <a 
            href="#" 
            className={activeRoom === 'quantum' ? 'active' : ''} 
            onClick={(e) => { e.preventDefault(); setActiveRoom('quantum'); }}
          >
            Room 1: The Quantum Topologist
          </a>
          <a 
            href="#" 
            className={activeRoom === 'crypto' ? 'active' : ''} 
            onClick={(e) => { e.preventDefault(); setActiveRoom('crypto'); }}
          >
            Room 2: The Cryptographic Geometer
          </a>
          <a 
            href="#" 
            className={activeRoom === 'arithmetic' ? 'active' : ''} 
            onClick={(e) => { e.preventDefault(); setActiveRoom('arithmetic'); }}
          >
            Room 3: The Arithmetic Geometer
          </a>
          <a 
            href="#" 
            className={activeRoom === 'ip' ? 'active' : ''} 
            onClick={(e) => { e.preventDefault(); setActiveRoom('ip'); }}
            style={{ color: '#ffcc00' }}
          >
            Room 4 (Private): Alien Math IP
          </a>
          <a 
            href="#" 
            className={activeRoom === 'stress' ? 'active' : ''} 
            onClick={(e) => { e.preventDefault(); setActiveRoom('stress'); }}
            style={{ color: '#ffcc00' }}
          >
            Room 5 (Private): Lean Stress Test
          </a>
          <a 
            href="#" 
            className={activeRoom === 'taste' ? 'active' : ''} 
            onClick={(e) => { e.preventDefault(); setActiveRoom('taste'); }}
            style={{ color: '#ffcc00' }}
          >
            Room 6 (Private): Mathematical Taste
          </a>
        </nav>
      </header>
 
      <main>
        {activeRoom === 'quantum' && <QuantumTopologist />}
        {activeRoom === 'crypto' && <CryptographicGeometer />}
        {activeRoom === 'arithmetic' && <ArithmeticGeometer />}
        {activeRoom === 'ip' && <AlienMathIP />}
        {activeRoom === 'stress' && <LeanStressTest />}
        {activeRoom === 'taste' && <AdvancedTaste />}
      </main>
      
      <footer style={{ marginTop: '4rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
        &copy; 2026 Xavier Callens and Socrate AI. All rights reserved.
      </footer>
    </div>
  );
}

export default App;
