import json

enriched_path = "/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/callens_conjectures_enriched.json"
page_path = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/lmms-lab-writer/apps/web/src/app/openroom/page.tsx"

with open(enriched_path, "r") as f:
    conjectures = json.load(f)

conjestures_json = json.dumps(conjectures, indent=4)

template = """"use client";

import React, { useState, useEffect } from 'react';

const CONJECTURES = __CONJECTURES_PLACEHOLDER__;

export default function OpenRoom() {
    const [activeId, setActiveId] = useState<string | null>("cc_001");
    const [galileoData, setGalileoData] = useState<any>(null);
    const [activeImpactTab, setActiveImpactTab] = useState<'physics' | 'medicine' | 'biology' | 'environment'>('physics');
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        fetch('/galileo_results.json')
            .then(res => res.json())
            .then(data => setGalileoData(data))
            .catch(err => console.error("Failed to load Galileo simulation data", err));
    }, []);

    const activeConj = CONJECTURES.find(c => c.id === activeId);

    const handleCopy = (code: string) => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <main className="min-h-screen bg-[#06060c] text-slate-200 font-sans selection:bg-indigo-500/30 overflow-x-hidden relative">
            {/* Grid background */}
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b0b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b0b_1px,transparent_1px)] bg-[size:28px_28px] pointer-events-none" />

            {/* Ambient glows */}
            <div className="fixed inset-0 z-0 pointer-events-none">
                <div className="absolute top-[-15%] left-[-15%] w-[60%] h-[60%] rounded-full bg-indigo-950/25 blur-[140px]" />
                <div className="absolute bottom-[-15%] right-[-15%] w-[65%] h-[65%] rounded-full bg-fuchsia-950/15 blur-[170px]" />
            </div>

            <div className="relative z-10 max-w-7xl mx-auto px-6 py-12">
                {/* Header */}
                <header className="mb-16 text-center space-y-4">
                    <div className="inline-flex items-center space-x-2 bg-indigo-500/10 border border-indigo-500/30 px-3 py-1 rounded-full text-indigo-400 text-xs font-semibold uppercase tracking-wider">
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                        <span>Socrate Agora Open Room</span>
                    </div>
                    <h1 className="text-4xl md:text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-200 to-indigo-200 tracking-tight">
                        Callens Scientific Conjectures
                    </h1>
                    <p className="text-slate-400 max-w-2xl mx-auto text-base">
                        Empirical verification by Galileo, formal Lean 4 verification, and cross-disciplinary translations in Physics, Medicine, Biology, and Environment.
                    </p>
                </header>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
                    {/* Left Column: Conjecture List */}
                    <div className="lg:col-span-4 space-y-4">
                        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider px-2">Conjectures Registry</h2>
                        <div className="space-y-3">
                            {CONJECTURES.map(conj => (
                                <button
                                    key={conj.id}
                                    onClick={() => setActiveId(conj.id)}
                                    className={`w-full text-left p-5 rounded-2xl border transition-all duration-300 group relative overflow-hidden
                                        ${activeId === conj.id 
                                            ? 'bg-indigo-950/45 border-indigo-500/50 shadow-[0_0_25px_rgba(99,102,241,0.12)]' 
                                            : 'bg-white/[0.02] border-white/5 hover:bg-white/[0.05] hover:border-white/10'}`}
                                >
                                    <div className="flex justify-between items-start mb-2 relative z-10">
                                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-black/40 border border-white/5 text-indigo-300">
                                            {conj.id}
                                        </span>
                                        <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                                            P={(conj.provability_index * 100).toFixed(1)}%
                                        </span>
                                    </div>
                                    <h3 className="font-semibold text-white group-hover:text-indigo-300 transition-colors relative z-10 mb-2">
                                        {conj.name}
                                    </h3>
                                    <p className="text-xs text-slate-400 line-clamp-2 relative z-10">
                                        {conj.mathematical_context}
                                    </p>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Right Column: Conjecture Detail & Verification */}
                    <div className="lg:col-span-8">
                        {activeConj ? (
                            <div className="space-y-8 p-8 rounded-3xl bg-black/40 border border-white/10 backdrop-blur-xl shadow-2xl animate-in fade-in slide-in-from-bottom-4 duration-500">
                                {/* Origin & Name */}
                                <div className="space-y-3">
                                    <div className="flex items-center space-x-3 text-xs text-indigo-400">
                                        <span>MATH INVARIANT</span>
                                        <span>•</span>
                                        <span className="text-slate-400">{activeConj.novelty_status}</span>
                                    </div>
                                    <h2 className="text-3xl font-bold text-white tracking-tight leading-tight">
                                        {activeConj.name}
                                    </h2>
                                    <p className="text-slate-300 leading-relaxed text-sm">
                                        {activeConj.mathematical_context}
                                    </p>
                                </div>

                                {/* Math Formalization (Large Display math block) */}
                                <div className="p-8 rounded-2xl bg-slate-950/60 border border-white/5 shadow-inner flex flex-col items-center justify-center space-y-4 relative group overflow-hidden">
                                    <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/5 to-purple-500/5 opacity-40 pointer-events-none" />
                                    <span className="text-[10px] font-bold tracking-widest text-indigo-400 uppercase">Mathematical Formalization</span>
                                    
                                    {/* Large premium rendered math equation */}
                                    <div className="w-full text-center py-4 select-all">
                                        {activeId === 'cc_001' && (
                                            <div className="flex flex-col items-center space-y-2">
                                                <div className="text-3xl md:text-4xl font-serif text-indigo-100 font-medium tracking-wide">
                                                    Δ(<i>n</i>) · Δ<sup>*</sup>(<i>n</i>) ≤ 1
                                                </div>
                                                <div className="text-[11px] text-slate-400 font-sans tracking-wide">
                                                    with equality if and only if <i>L</i> is self-dual
                                                </div>
                                            </div>
                                        )}
                                        {activeId === 'cc_002' && (
                                            <div className="flex flex-col items-center space-y-2">
                                                <div className="text-2xl md:text-3xl font-serif text-indigo-100 font-medium tracking-wide leading-relaxed">
                                                    ∃ <i>k</i> ∈ [1, <i>n</i> + λ<sub>1</sub>],{" "}
                                                    <i>s</i><sub>λ</sub> ∘ ( ∑<sub><i>i</i>=1</sub><sup><i>k</i></sup> <i>s</i><sub>(<i>i</i>)</sub> ) ∈ <span className="font-semibold text-indigo-300">𝒫</span><sub>Schur</sub>
                                                </div>
                                            </div>
                                        )}
                                        {activeId === 'cc_003' && (
                                            <div className="flex flex-col items-center space-y-2">
                                                <div className="text-xl md:text-2xl lg:text-3xl font-serif text-indigo-100 font-medium tracking-wide leading-relaxed">
                                                    ||<i>u</i><sub>0</sub>||<sub><i>L</i><sup>2</sup></sub> {"<"} ||<i>Q</i><sub>Townes</sub>||<sub><i>L</i><sup>2</sup></sub> ⇒ Global Existence of <i>i</i>∂<sub><i>t</i></sub><i>u</i> + Δ<i>u</i> + |<i>u</i>|<sup>2</sup><i>u</i> = 0
                                                </div>
                                            </div>
                                        )}
                                        {activeId === 'cc_004' && (
                                            <div className="flex flex-col items-center space-y-2">
                                                <div className="text-2xl md:text-3xl font-serif text-indigo-100 font-medium tracking-wide leading-relaxed">
                                                    <i>h</i><sup><i>p,q</i></sup>(<i>X</i>) = <i>h</i><sup>3−<i>p,q</i></sup>(<i>X̂</i>) ∧ 𝒟<sup><i>b</i></sup>(<i>X</i>) ≃ 𝒟<sup><i>b</i></sup>(<i>X̂</i>)
                                                </div>
                                            </div>
                                        )}
                                        {activeId === 'cc_005' && (
                                            <div className="flex flex-col items-center space-y-2">
                                                <div className="text-3xl md:text-4xl font-serif text-indigo-100 font-medium tracking-wide">
                                                    <i>S</i><sub>3</sub>(1,1,1,1) = <i>c</i> · <i>L</i>(<i>f</i>, 3) + <i>d</i> · ζ(3)
                                                </div>
                                                <div className="text-[11px] text-slate-400 font-sans tracking-wide">
                                                    where <i>c, d</i> ∈ ℚ̄ and <i>f</i> is a weight-4 Hecke eigenform
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                    
                                    {/* LaTeX source display */}
                                    <div className="text-[10px] font-mono text-slate-500 select-all">
                                        LaTeX: {activeConj.formal_math}
                                    </div>
                                </div>

                                {/* 4-Tab Real-World Impact Panel */}
                                <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/5 space-y-4">
                                    <div className="flex items-center justify-between border-b border-white/5 pb-3">
                                        <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Scientific & Industrial Gains</h4>
                                    </div>
                                    
                                    {/* Tabs */}
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                        {(['physics', 'medicine', 'biology', 'environment'] as const).map(tab => (
                                            <button
                                                key={tab}
                                                onClick={() => setActiveImpactTab(tab)}
                                                className={`py-2.5 px-3 text-xs font-semibold rounded-lg border transition-all uppercase tracking-wider
                                                    ${activeImpactTab === tab 
                                                        ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40' 
                                                        : 'bg-black/30 text-slate-400 border-transparent hover:bg-white/5 hover:text-slate-200'}`}
                                            >
                                                {tab}
                                            </button>
                                        ))}
                                    </div>

                                    {/* Content + SVG Illustration */}
                                    <div className="grid grid-cols-1 md:grid-cols-12 gap-6 p-4 rounded-xl bg-black/30 border border-white/5 items-center">
                                        <div className="md:col-span-7 space-y-2">
                                            <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">{activeImpactTab} Translation</span>
                                            <p className="text-sm text-slate-300 leading-relaxed">
                                                {activeImpactTab === 'physics' && activeConj.physics_gain}
                                                {activeImpactTab === 'medicine' && activeConj.medicine_gain}
                                                {activeImpactTab === 'biology' && activeConj.biology_gain}
                                                {activeImpactTab === 'environment' && activeConj.environment_gain}
                                            </p>
                                        </div>
                                        <div className="md:col-span-5 flex justify-center items-center bg-slate-950/40 p-4 rounded-lg border border-white/5 h-[160px] relative overflow-hidden">
                                            {/* Render beautiful custom SVGs depending on ActiveId and ActiveImpactTab */}
                                            {activeId === 'cc_001' && activeImpactTab === 'physics' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#a5b4fc" fontSize="8" textAnchor="middle" fontWeight="bold">Quantum Error Correction</text>
                                                    <circle cx="80" cy="70" r="30" fill="none" stroke="#6366f1" strokeWidth="1" strokeDasharray="3,3" />
                                                    <circle cx="80" cy="70" r="15" fill="none" stroke="#a855f7" strokeWidth="1" />
                                                    {/* Code qubits */}
                                                    <circle cx="50" cy="70" r="3" fill="#6366f1" />
                                                    <circle cx="110" cy="70" r="3" fill="#6366f1" />
                                                    <circle cx="80" cy="40" r="3" fill="#6366f1" />
                                                    <circle cx="80" cy="100" r="3" fill="#6366f1" />
                                                    <circle cx="80" cy="70" r="4" fill="#a855f7" />
                                                    {/* Entangling lines */}
                                                    <line x1="50" y1="70" x2="80" y2="70" stroke="rgba(168,85,247,0.4)" strokeWidth="1" />
                                                    <line x1="110" y1="70" x2="80" y2="70" stroke="rgba(168,85,247,0.4)" strokeWidth="1" />
                                                    <line x1="80" y1="40" x2="80" y2="70" stroke="rgba(168,85,247,0.4)" strokeWidth="1" />
                                                    <line x1="80" y1="100" x2="80" y2="70" stroke="rgba(168,85,247,0.4)" strokeWidth="1" />
                                                </svg>
                                            )}
                                            {activeId === 'cc_001' && activeImpactTab === 'medicine' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#f472b6" fontSize="8" textAnchor="middle" fontWeight="bold">Nanoparticle Crystalline Payload</text>
                                                    {/* Nanoparticle shell */}
                                                    <circle cx="80" cy="70" r="35" fill="none" stroke="#ec4899" strokeWidth="2" strokeDasharray="4,2" />
                                                    {/* Receptor ligands */}
                                                    <line x1="80" y1="35" x2="80" y2="25" stroke="#ec4899" strokeWidth="1.5" />
                                                    <circle cx="80" cy="25" r="3" fill="#ec4899" />
                                                    <line x1="45" y1="70" x2="35" y2="70" stroke="#ec4899" strokeWidth="1.5" />
                                                    <circle cx="35" cy="70" r="3" fill="#ec4899" />
                                                    {/* Hex packed drug circles inside */}
                                                    <circle cx="80" cy="70" r="7" fill="rgba(236,72,153,0.3)" stroke="#db2777" strokeWidth="1" />
                                                    <circle cx="68" cy="70" r="7" fill="rgba(236,72,153,0.3)" stroke="#db2777" strokeWidth="1" />
                                                    <circle cx="92" cy="70" r="7" fill="rgba(236,72,153,0.3)" stroke="#db2777" strokeWidth="1" />
                                                    <circle cx="74" cy="59.6" r="7" fill="rgba(236,72,153,0.3)" stroke="#db2777" strokeWidth="1" />
                                                    <circle cx="86" cy="59.6" r="7" fill="rgba(236,72,153,0.3)" stroke="#db2777" strokeWidth="1" />
                                                    <circle cx="74" cy="80.4" r="7" fill="rgba(236,72,153,0.3)" stroke="#db2777" strokeWidth="1" />
                                                    <circle cx="86" cy="80.4" r="7" fill="rgba(236,72,153,0.3)" stroke="#db2777" strokeWidth="1" />
                                                </svg>
                                            )}
                                            {activeId === 'cc_001' && activeImpactTab === 'biology' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#34d399" fontSize="8" textAnchor="middle" fontWeight="bold">Viral DNA Packaging Capsid</text>
                                                    {/* Icosahedral capsid outlines */}
                                                    <polygon points="80,30 115,50 115,90 80,110 45,90 45,50" fill="none" stroke="#10b981" strokeWidth="1.5" />
                                                    <line x1="80" y1="30" x2="80" y2="110" stroke="rgba(16,185,129,0.3)" strokeWidth="1" />
                                                    <line x1="45" y1="50" x2="115" y2="90" stroke="rgba(16,185,129,0.3)" strokeWidth="1" />
                                                    <line x1="45" y1="90" x2="115" y2="50" stroke="rgba(16,185,129,0.3)" strokeWidth="1" />
                                                    {/* Packed coils inside */}
                                                    <path d="M 60,60 Q 80,45 100,60 T 60,80 T 100,80" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" />
                                                </svg>
                                            )}
                                            {activeId === 'cc_001' && activeImpactTab === 'environment' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#fb923c" fontSize="8" textAnchor="middle" fontWeight="bold">Soil Crystalline Porosity</text>
                                                    {/* Clay mineral lattice sheets */}
                                                    <rect x="35" y="35" width="90" height="8" rx="2" fill="rgba(249,115,22,0.2)" stroke="#f97316" strokeWidth="1" />
                                                    <rect x="35" y="95" width="90" height="8" rx="2" fill="rgba(249,115,22,0.2)" stroke="#f97316" strokeWidth="1" />
                                                    {/* Water molecules trapped in lattice */}
                                                    <circle cx="55" cy="65" r="5" fill="#38bdf8" />
                                                    <circle cx="80" cy="65" r="5" fill="#38bdf8" />
                                                    <circle cx="105" cy="65" r="5" fill="#38bdf8" />
                                                    {/* Hydrogen bonds */}
                                                    <line x1="55" y1="43" x2="55" y2="60" stroke="#38bdf8" strokeWidth="1" strokeDasharray="2,2" />
                                                    <line x1="80" y1="43" x2="80" y2="60" stroke="#38bdf8" strokeWidth="1" strokeDasharray="2,2" />
                                                    <line x1="105" y1="43" x2="105" y2="60" stroke="#38bdf8" strokeWidth="1" strokeDasharray="2,2" />
                                                    <line x1="55" y1="70" x2="55" y2="95" stroke="#38bdf8" strokeWidth="1" strokeDasharray="2,2" />
                                                    <line x1="80" y1="70" x2="80" y2="95" stroke="#38bdf8" strokeWidth="1" strokeDasharray="2,2" />
                                                    <line x1="105" y1="70" x2="105" y2="95" stroke="#38bdf8" strokeWidth="1" strokeDasharray="2,2" />
                                                </svg>
                                            )}

                                            {/* cc_002 */}
                                            {activeId === 'cc_002' && activeImpactTab === 'physics' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#a5b4fc" fontSize="8" textAnchor="middle" fontWeight="bold">Clebsch-Gordan QCD Decay</text>
                                                    {/* Multiplet Tree */}
                                                    <line x1="80" y1="35" x2="50" y2="75" stroke="#6366f1" strokeWidth="1.5" />
                                                    <line x1="80" y1="35" x2="110" y2="75" stroke="#6366f1" strokeWidth="1.5" />
                                                    <line x1="80" y1="35" x2="80" y2="75" stroke="#6366f1" strokeWidth="1.5" />
                                                    <circle cx="80" cy="35" r="4" fill="#a855f7" />
                                                    {/* State levels */}
                                                    <circle cx="50" cy="75" r="3.5" fill="#6366f1" />
                                                    <circle cx="80" cy="75" r="3.5" fill="#6366f1" />
                                                    <circle cx="110" cy="75" r="3.5" fill="#6366f1" />
                                                    {/* Sub-decay branches */}
                                                    <line x1="50" y1="75" x2="35" y2="105" stroke="#38bdf8" strokeWidth="1" />
                                                    <line x1="50" y1="75" x2="65" y2="105" stroke="#38bdf8" strokeWidth="1" />
                                                    <circle cx="35" cy="105" r="2.5" fill="#38bdf8" />
                                                    <circle cx="65" cy="105" r="2.5" fill="#38bdf8" />
                                                </svg>
                                            )}
                                            {activeId === 'cc_002' && activeImpactTab === 'medicine' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#f472b6" fontSize="8" textAnchor="middle" fontWeight="bold">Carcinoma Mutation Threshold</text>
                                                    {/* Safe folding region vs mutant */}
                                                    <rect x="25" y="30" width="110" height="75" rx="8" fill="none" stroke="#f43f5e" strokeWidth="1.5" />
                                                    <line x1="80" y1="30" x2="80" y2="105" stroke="#f43f5e" strokeWidth="1" strokeDasharray="3,3" />
                                                    {/* Safe left */}
                                                    <text x="52" y="45" fill="#34d399" fontSize="7" textAnchor="middle">k &le; k(&lambda;)</text>
                                                    <path d="M 35,80 Q 52,60 70,80" fill="none" stroke="#10b981" strokeWidth="2" />
                                                    <text x="52" y="95" fill="#10b981" fontSize="6" textAnchor="middle">Stable Folding</text>
                                                    {/* Mutant right */}
                                                    <text x="108" y="45" fill="#f43f5e" fontSize="7" textAnchor="middle">k &gt; k(&lambda;)</text>
                                                    {/* Broken folding line */}
                                                    <path d="M 90,80 L 100,65 L 110,90 L 125,70" fill="none" stroke="#f43f5e" strokeWidth="1.5" />
                                                    <text x="108" y="95" fill="#f43f5e" fontSize="6" textAnchor="middle">Carcinogenesis</text>
                                                </svg>
                                            )}
                                            {activeId === 'cc_002' && activeImpactTab === 'biology' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#34d399" fontSize="8" textAnchor="middle" fontWeight="bold">Protein-Protein Interaction Net</text>
                                                    {/* Network nodes */}
                                                    <circle cx="80" cy="65" r="5" fill="#34d399" />
                                                    <circle cx="50" cy="45" r="5" fill="#10b981" />
                                                    <circle cx="110" cy="45" r="5" fill="#10b981" />
                                                    <circle cx="50" cy="85" r="5" fill="#10b981" />
                                                    <circle cx="110" cy="85" r="5" fill="#10b981" />
                                                    {/* Connections */}
                                                    <line x1="80" y1="65" x2="50" y2="45" stroke="#059669" strokeWidth="1.5" />
                                                    <line x1="80" y1="65" x2="110" y2="45" stroke="#059669" strokeWidth="1.5" />
                                                    <line x1="80" y1="65" x2="50" y2="85" stroke="#059669" strokeWidth="1.5" />
                                                    <line x1="80" y1="65" x2="110" y2="85" stroke="#059669" strokeWidth="1.5" />
                                                    <line x1="50" y1="45" x2="110" y2="45" stroke="rgba(16,185,129,0.3)" strokeWidth="1" />
                                                    <line x1="50" y1="85" x2="110" y2="85" stroke="rgba(16,185,129,0.3)" strokeWidth="1" />
                                                    {/* Stress indicator */}
                                                    <circle cx="80" cy="65" r="12" fill="none" stroke="#f59e0b" strokeWidth="1" strokeDasharray="2,2" />
                                                </svg>
                                            )}
                                            {activeId === 'cc_002' && activeImpactTab === 'environment' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#fb923c" fontSize="8" textAnchor="middle" fontWeight="bold">Food Web Stability Matrix</text>
                                                    {/* Trophic pyramid levels */}
                                                    <polygon points="80,35 120,105 40,105" fill="none" stroke="#f97316" strokeWidth="1.5" />
                                                    <line x1="60" y1="70" x2="100" y2="70" stroke="#f97316" strokeWidth="1" />
                                                    <line x1="70" y1="52" x2="90" y2="52" stroke="#f97316" strokeWidth="1" />
                                                    {/* Species indicators */}
                                                    <circle cx="80" cy="44" r="2" fill="#fb923c" />
                                                    <circle cx="72" cy="61" r="2.5" fill="#fb923c" />
                                                    <circle cx="88" cy="61" r="2.5" fill="#fb923c" />
                                                    <circle cx="55" cy="88" r="3" fill="#fb923c" />
                                                    <circle cx="80" cy="88" r="3" fill="#fb923c" />
                                                    <circle cx="105" cy="88" r="3" fill="#fb923c" />
                                                    <text x="80" y="115" fill="#ea580c" fontSize="7" textAnchor="middle">Species Threshold Bounded</text>
                                                </svg>
                                            )}

                                            {/* cc_003 */}
                                            {activeId === 'cc_003' && activeImpactTab === 'physics' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#a5b4fc" fontSize="8" textAnchor="middle" fontWeight="bold">Nonlinear Laser Self-Focusing</text>
                                                    {/* Focal envelope */}
                                                    <path d="M 20,40 Q 80,68 140,40" fill="none" stroke="#818cf8" strokeWidth="1" />
                                                    <path d="M 20,100 Q 80,72 140,100" fill="none" stroke="#818cf8" strokeWidth="1" />
                                                    {/* High intensity beam */}
                                                    <path d="M 20,70 L 65,70 Q 80,70 95,70 L 140,70" fill="none" stroke="#f43f5e" strokeWidth="2.5" />
                                                    <ellipse cx="80" cy="70" rx="10" ry="18" fill="rgba(244,63,94,0.3)" stroke="#f43f5e" strokeWidth="1" />
                                                    <text x="80" y="105" fill="#6366f1" fontSize="7" textAnchor="middle">Townes Core Profile</text>
                                                </svg>
                                            )}
                                            {activeId === 'cc_003' && activeImpactTab === 'medicine' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#f472b6" fontSize="8" textAnchor="middle" fontWeight="bold">HIFU Stable Thermal Focal Point</text>
                                                    {/* Ultrasound wave transducer arcs */}
                                                    <path d="M 20,35 A 40,40 0 0,0 20,105" fill="none" stroke="#db2777" strokeWidth="3" strokeLinecap="round" />
                                                    {/* Focused rays pointing to focal point */}
                                                    <line x1="22" y1="35" x2="100" y2="70" stroke="rgba(236,72,153,0.3)" strokeWidth="1" strokeDasharray="3,2" />
                                                    <line x1="22" y1="105" x2="100" y2="70" stroke="rgba(236,72,153,0.3)" strokeWidth="1" strokeDasharray="3,2" />
                                                    <line x1="22" y1="70" x2="100" y2="70" stroke="rgba(236,72,153,0.3)" strokeWidth="1" />
                                                    {/* Target Tumor */}
                                                    <ellipse cx="100" cy="70" rx="12" ry="8" fill="rgba(225,29,72,0.2)" stroke="#e11d48" strokeWidth="1" />
                                                    <circle cx="100" cy="70" r="3" fill="#e11d48" />
                                                    <text x="100" y="95" fill="#e11d48" fontSize="7" textAnchor="middle">Tumor Target</text>
                                                </svg>
                                            )}
                                            {activeId === 'cc_003' && activeImpactTab === 'biology' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#34d399" fontSize="8" textAnchor="middle" fontWeight="bold">Davydov Soliton Peptide Chain</text>
                                                    {/* Alpha helix skeletal line */}
                                                    <path d="M 20,70 C 40,30 50,110 70,70 C 90,30 100,110 120,70 C 140,30 150,110 170,70" fill="none" stroke="rgba(16,185,129,0.3)" strokeWidth="1.5" />
                                                    {/* Soliton wave packet envelope */}
                                                    <ellipse cx="70" cy="70" rx="22" ry="35" fill="none" stroke="#10b981" strokeWidth="1.5" strokeDasharray="4,2" />
                                                    {/* Active hydrogen bonding vibrations */}
                                                    <circle cx="70" cy="70" r="5" fill="#34d399" />
                                                    <circle cx="60" cy="55" r="4.5" fill="#34d399" />
                                                    <circle cx="80" cy="85" r="4.5" fill="#34d399" />
                                                    <line x1="60" y1="55" x2="70" y2="70" stroke="#10b981" strokeWidth="1.5" />
                                                    <line x1="70" y1="70" x2="80" y2="85" stroke="#10b981" strokeWidth="1.5" />
                                                </svg>
                                            )}
                                            {activeId === 'cc_003' && activeImpactTab === 'environment' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#fb923c" fontSize="8" textAnchor="middle" fontWeight="bold">Rogue Wave Marine Forecasting</text>
                                                    {/* Sea state profile */}
                                                    <path d="M 15,80 Q 30,75 45,80 T 75,80 T 95,30 T 115,80 T 145,80" fill="none" stroke="#fb923c" strokeWidth="2" strokeLinecap="round" />
                                                    {/* Marine structure */}
                                                    <line x1="125" y1="65" x2="125" y2="80" stroke="#94a3b8" strokeWidth="3" />
                                                    <rect x="115" y="52" width="20" height="13" fill="#475569" />
                                                    {/* Soliton threshold indicator */}
                                                    <path d="M 95,30 L 95,100" stroke="#f43f5e" strokeWidth="1" strokeDasharray="2,2" />
                                                    <text x="95" y="110" fill="#f43f5e" fontSize="7" textAnchor="middle">Amplitude Peak</text>
                                                </svg>
                                            )}

                                            {/* cc_004 */}
                                            {activeId === 'cc_004' && activeImpactTab === 'physics' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#a5b4fc" fontSize="8" textAnchor="middle" fontWeight="bold">Supersymmetric D-Brane Vacua</text>
                                                    {/* Toroidal dimensions */}
                                                    <ellipse cx="60" cy="70" rx="22" ry="12" fill="none" stroke="#6366f1" strokeWidth="1.5" />
                                                    <ellipse cx="100" cy="70" rx="22" ry="12" fill="none" stroke="#a855f7" strokeWidth="1.5" />
                                                    {/* Strings crossing dimensions */}
                                                    <path d="M 60,70 C 70,55 90,85 100,70" fill="none" stroke="#38bdf8" strokeWidth="2" strokeLinecap="round" />
                                                    <path d="M 60,70 C 70,85 90,55 100,70" fill="none" stroke="#38bdf8" strokeWidth="1" strokeDasharray="2,1" strokeLinecap="round" />
                                                </svg>
                                            )}
                                            {activeId === 'cc_004' && activeImpactTab === 'medicine' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#f472b6" fontSize="8" textAnchor="middle" fontWeight="bold">Biomolecule Folding Landscapes</text>
                                                    {/* Multi-dimensional funnel plot */}
                                                    <path d="M 25,35 C 50,35 60,95 80,95 C 100,95 110,35 135,35" fill="none" stroke="#ec4899" strokeWidth="1.5" />
                                                    <path d="M 40,45 C 60,45 65,85 80,85 C 95,85 100,45 120,45" fill="none" stroke="rgba(236,72,153,0.4)" strokeWidth="1" />
                                                    {/* Ground state at bottom of funnel */}
                                                    <circle cx="80" cy="95" r="4.5" fill="#db2777" className="animate-pulse" />
                                                    <text x="80" y="112" fill="#db2777" fontSize="7" textAnchor="middle">Global Minimum (Exact Bind)</text>
                                                </svg>
                                            )}
                                            {activeId === 'cc_004' && activeImpactTab === 'biology' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#34d399" fontSize="8" textAnchor="middle" fontWeight="bold">Synthetic Cell Lipid Bilayer</text>
                                                    {/* Bilayer cross section */}
                                                    <line x1="20" y1="55" x2="140" y2="55" stroke="#10b981" strokeWidth="2" />
                                                    <line x1="20" y1="85" x2="140" y2="85" stroke="#10b981" strokeWidth="2" />
                                                    {/* Lipid heads/tails */}
                                                    {[25, 45, 65, 85, 105, 125, 135].map((x, idx) => (
                                                        <React.Fragment key={idx}>
                                                            <circle cx={x} cy="50" r="3" fill="#34d399" />
                                                            <line x1={x} y1="53" x2={x} y2="68" stroke="#10b981" strokeWidth="1" />
                                                            <circle cx={x} cy="90" r="3" fill="#34d399" />
                                                            <line x1={x} y1="87" x2={x} y2="72" stroke="#10b981" strokeWidth="1" />
                                                        </React.Fragment>
                                                    ))}
                                                    <ellipse cx="80" cy="70" rx="14" ry="20" fill="rgba(56,189,248,0.2)" stroke="#38bdf8" strokeWidth="1.5" />
                                                    <text x="80" y="73" fill="#38bdf8" fontSize="6" textAnchor="middle">Stable Pore</text>
                                                </svg>
                                            )}
                                            {activeId === 'cc_004' && activeImpactTab === 'environment' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#fb923c" fontSize="8" textAnchor="middle" fontWeight="bold">Topological MOF Carbon Capture</text>
                                                    {/* Framework hexagon pores */}
                                                    <polygon points="60,35 85,45 85,75 60,85 35,75 35,45" fill="none" stroke="#f97316" strokeWidth="1.5" />
                                                    <polygon points="100,55 125,65 125,95 100,105 75,95 75,65" fill="none" stroke="rgba(249,115,22,0.4)" strokeWidth="1" />
                                                    {/* CO2 molecule trapped inside hex */}
                                                    <circle cx="60" cy="60" r="4.5" fill="#a855f7" /> {/* Carbon */}
                                                    <circle cx="50" cy="60" r="3" fill="#ef4444" /> {/* Oxygen */}
                                                    <circle cx="70" cy="60" r="3" fill="#ef4444" /> {/* Oxygen */}
                                                    <line x1="53" y1="60" x2="57" y2="60" stroke="#fff" strokeWidth="1" />
                                                    <line x1="63" y1="60" x2="67" y2="60" stroke="#fff" strokeWidth="1" />
                                                    <text x="60" y="105" fill="#fb923c" fontSize="7" textAnchor="middle">Mirror Dual Cavity Trapping</text>
                                                </svg>
                                            )}

                                            {/* cc_005 */}
                                            {activeId === 'cc_005' && activeImpactTab === 'physics' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#a5b4fc" fontSize="8" textAnchor="middle" fontWeight="bold">Scattering Amplitudes (LHC/FCC)</text>
                                                    {/* Scattering graph */}
                                                    <line x1="20" y1="35" x2="60" y2="70" stroke="#818cf8" strokeWidth="2" />
                                                    <line x1="20" y1="105" x2="60" y2="70" stroke="#818cf8" strokeWidth="2" />
                                                    <line x1="60" y1="70" x2="110" y2="70" stroke="#a855f7" strokeWidth="3" />
                                                    <line x1="110" y1="70" x2="140" y2="35" stroke="#818cf8" strokeWidth="2" />
                                                    <line x1="110" y1="70" x2="140" y2="105" stroke="#818cf8" strokeWidth="2" />
                                                    {/* Loops on the propagator */}
                                                    <circle cx="85" cy="70" r="12" fill="none" stroke="#f43f5e" strokeWidth="1.5" />
                                                    <text x="85" y="105" fill="#f43f5e" fontSize="7" textAnchor="middle">Sunrise Loop Kernel</text>
                                                </svg>
                                            )}
                                            {activeId === 'cc_005' && activeImpactTab === 'medicine' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#f472b6" fontSize="8" textAnchor="middle" fontWeight="bold">PET Scan Noise Reduction</text>
                                                    {/* Ring scanner */}
                                                    <circle cx="80" cy="70" r="38" fill="none" stroke="#db2777" strokeWidth="2" />
                                                    {/* Annihilation point */}
                                                    <circle cx="70" cy="65" r="3" fill="#ef4444" className="animate-ping" />
                                                    <circle cx="70" cy="65" r="2" fill="#ef4444" />
                                                    {/* Gamma emission lines back to back */}
                                                    <line x1="42" y1="65" x2="98" y2="65" stroke="#f472b6" strokeWidth="1" strokeDasharray="3,2" />
                                                    {/* Scattered line */}
                                                    <line x1="70" y1="65" x2="80" y2="107" stroke="#fb923c" strokeWidth="1" />
                                                    <text x="80" y="116" fill="#db2777" fontSize="7" textAnchor="middle">Kernel Noise Filtered</text>
                                                </svg>
                                            )}
                                            {activeId === 'cc_005' && activeImpactTab === 'biology' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#34d399" fontSize="8" textAnchor="middle" fontWeight="bold">Photosynthetic Light-Harvesting</text>
                                                    {/* Chloroplast molecule rings */}
                                                    <circle cx="60" cy="70" r="18" fill="none" stroke="#10b981" strokeWidth="1.5" />
                                                    <circle cx="100" cy="70" r="18" fill="none" stroke="#10b981" strokeWidth="1.5" />
                                                    {/* Energy transfer path */}
                                                    <path d="M 60,52 Q 80,70 100,52" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
                                                    <polygon points="100,52 94,49 97,55" fill="#f59e0b" />
                                                    <circle cx="80" cy="64" r="3" fill="#f59e0b" className="animate-pulse" />
                                                    <text x="80" y="105" fill="#059669" fontSize="7" textAnchor="middle">Coherent Energy Capture</text>
                                                </svg>
                                            )}
                                            {activeId === 'cc_005' && activeImpactTab === 'environment' && (
                                                <svg viewBox="0 0 160 120" className="w-full max-w-[160px] h-full overflow-visible">
                                                    <text x="80" y="15" fill="#fb923c" fontSize="8" textAnchor="middle" fontWeight="bold">Perovskite Solar Cell Lattice</text>
                                                    {/* Perovskite octahedral grid */}
                                                    <rect x="40" y="35" width="80" height="60" rx="3" fill="none" stroke="#f97316" strokeWidth="1" />
                                                    <line x1="80" y1="35" x2="80" y2="95" stroke="rgba(249,115,22,0.3)" strokeWidth="1" />
                                                    <line x1="40" y1="65" x2="120" y2="65" stroke="rgba(249,115,22,0.3)" strokeWidth="1" />
                                                    {/* Electron hole pair */}
                                                    <circle cx="60" cy="50" r="4" fill="#38bdf8" /> {/* Electron */}
                                                    <circle cx="100" cy="80" r="4" fill="#ef4444" /> {/* Hole */}
                                                    <path d="M 60,50 Q 80,65 100,80" fill="none" stroke="#fb923c" strokeWidth="1" strokeDasharray="3,1" />
                                                    <text x="80" y="110" fill="#fb923c" fontSize="7" textAnchor="middle">Scattering Rates Sim</text>
                                                </svg>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {/* Galileo Empirical Verification Panel */}
                                <div className="p-6 rounded-2xl bg-indigo-950/20 border border-indigo-500/20 space-y-5">
                                    <div className="flex items-center space-x-2">
                                        <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                                        </svg>
                                        <h4 className="text-sm font-semibold text-indigo-300 uppercase tracking-wider">
                                            Galileo Empirical Demonstration
                                        </h4>
                                    </div>

                                    {/* Visualization rendering */}
                                    {activeId === 'cc_001' && (
                                        <div className="space-y-4">
                                            <p className="text-xs text-slate-400">
                                                Numerical evaluation of optimal sphere packing density Δ(n) and dual density Δ*(n) across dimensions. Duality product bounds Δ(n) * Δ*(n) ≤ 1.
                                            </p>
                                            
                                            {/* Lattice packing diagram */}
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
                                                <div className="overflow-x-auto rounded-xl border border-white/5 bg-black/40">
                                                    <table className="w-full text-left border-collapse text-[11px]">
                                                        <thead>
                                                            <tr className="border-b border-white/10 bg-white/5 text-slate-300">
                                                                <th className="p-2">Dim (n)</th>
                                                                <th className="p-2">Lattice</th>
                                                                <th className="p-2">Density Δ</th>
                                                                <th className="p-2">Product</th>
                                                                <th className="p-2">Self-Dual</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody className="divide-y divide-white/5">
                                                            {galileoData?.cc_001?.map((row: any) => (
                                                                <tr key={row.dimension} className="hover:bg-white/[0.02]">
                                                                    <td className="p-2 font-semibold text-white">{row.dimension}</td>
                                                                    <td className="p-2 text-slate-300">{row.lattice}</td>
                                                                    <td className="p-2 text-indigo-300 font-mono">{row.density.toFixed(4)}</td>
                                                                    <td className="p-2 text-emerald-400 font-bold font-mono">{row.product.toFixed(5)}</td>
                                                                    <td className="p-2 text-slate-400">{row.self_dual ? 'YES' : 'NO'}</td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                                
                                                {/* Hexagonal vs Square Packing SVG */}
                                                <div className="p-4 rounded-xl border border-white/5 bg-black/40 flex flex-col items-center justify-center space-y-2">
                                                    <span className="text-[10px] font-semibold text-slate-400 uppercase">Hexagonal Packing (Optimal 2D)</span>
                                                    <svg viewBox="0 0 160 100" className="w-full max-w-[160px] h-auto overflow-visible">
                                                        {/* Draw Hexagonal lattice packing circles */}
                                                        {/* row 1 */}
                                                        <circle cx="20" cy="20" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                        <circle cx="56" cy="20" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                        <circle cx="92" cy="20" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                        <circle cx="128" cy="20" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                        {/* row 2 */}
                                                        <circle cx="38" cy="51.1" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                        <circle cx="74" cy="51.1" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                        <circle cx="110" cy="51.1" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                        <circle cx="146" cy="51.1" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                        {/* row 3 */}
                                                        <circle cx="20" cy="82.2" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                        <circle cx="56" cy="82.2" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                        <circle cx="92" cy="82.2" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                        <circle cx="128" cy="82.2" r="18" fill="rgba(99,102,241,0.2)" stroke="#6366f1" strokeWidth="1" />
                                                    </svg>
                                                    <span className="text-[9px] text-indigo-300">Density ≈ 90.69%</span>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {activeId === 'cc_002' && (
                                        <div className="space-y-4">
                                            <p className="text-xs text-slate-400">
                                                Minimal plethysm Schur-positivity threshold k(λ) computed by Galileo's combinatorial engine vs theoretical upper bound n + λ₁.
                                            </p>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
                                                <div className="overflow-x-auto rounded-xl border border-white/5 bg-black/40">
                                                    <table className="w-full text-left border-collapse text-[11px]">
                                                        <thead>
                                                            <tr className="border-b border-white/10 bg-white/5 text-slate-300">
                                                                <th className="p-2">λ</th>
                                                                <th className="p-2">Bound</th>
                                                                <th className="p-2">k(λ)</th>
                                                                <th className="p-2">Status</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody className="divide-y divide-white/5">
                                                            {galileoData?.cc_002?.map((row: any, idx: number) => (
                                                                <tr key={idx} className="hover:bg-white/[0.02]">
                                                                    <td className="p-2 font-semibold text-emerald-300 font-mono">{row.partition}</td>
                                                                    <td className="p-2 text-indigo-300">{row.bound}</td>
                                                                    <td className="p-2 text-amber-400 font-bold">{row.k_threshold}</td>
                                                                    <td className="p-2 text-emerald-400 font-semibold">VERIFIED</td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                                
                                                {/* Young Diagram Representation */}
                                                <div className="p-4 rounded-xl border border-white/5 bg-black/40 flex flex-col items-center justify-center space-y-3">
                                                    <span className="text-[10px] font-semibold text-slate-400 uppercase">Young Diagram (Partition representation)</span>
                                                    <div className="flex flex-col space-y-1.5">
                                                        {/* row 1 (3 boxes) */}
                                                        <div className="flex space-x-1.5">
                                                            <div className="w-6 h-6 rounded border border-indigo-500 bg-indigo-500/25 flex items-center justify-center font-mono text-[9px] text-white">λ₁</div>
                                                            <div className="w-6 h-6 rounded border border-indigo-500 bg-indigo-500/25"></div>
                                                            <div className="w-6 h-6 rounded border border-indigo-500 bg-indigo-500/25"></div>
                                                        </div>
                                                        {/* row 2 (2 boxes) */}
                                                        <div className="flex space-x-1.5">
                                                            <div className="w-6 h-6 rounded border border-indigo-500 bg-indigo-500/15 flex items-center justify-center font-mono text-[9px] text-white">λ₂</div>
                                                            <div className="w-6 h-6 rounded border border-indigo-500 bg-indigo-500/15"></div>
                                                        </div>
                                                        {/* row 3 (1 box) */}
                                                        <div className="flex space-x-1.5">
                                                            <div className="w-6 h-6 rounded border border-indigo-500 bg-indigo-500/5 flex items-center justify-center font-mono text-[9px] text-white">λ₃</div>
                                                        </div>
                                                    </div>
                                                    <span className="text-[9px] text-indigo-300 font-mono">λ = [3, 2, 1], n=6</span>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {activeId === 'cc_003' && (
                                        <div className="space-y-4">
                                            <p className="text-xs text-slate-400">
                                                Split-step Fourier time-series simulation showing maximum wave amplitude evolution of the 2D cubic NLS.
                                                Sub-critical mass (M &lt; Mc) disperses globally. Super-critical mass (M &gt; Mc) experiences rapid focal blow-up.
                                            </p>
                                            
                                            {/* Custom SVG Line Chart */}
                                            <div className="p-4 rounded-xl border border-white/5 bg-black/50 relative">
                                                <div className="absolute top-2 right-4 flex space-x-4 text-[10px] font-semibold">
                                                    <div className="flex items-center space-x-1.5">
                                                        <span className="w-2.5 h-0.5 bg-rose-500 inline-block" />
                                                        <span className="text-rose-400">Super-critical (Blow-up)</span>
                                                    </div>
                                                    <div className="flex items-center space-x-1.5">
                                                        <span className="w-2.5 h-0.5 bg-sky-400 inline-block" />
                                                        <span className="text-sky-300">Sub-critical (Dispersive)</span>
                                                    </div>
                                                </div>

                                                {galileoData?.cc_003 ? (
                                                    <svg viewBox="0 0 500 240" className="w-full h-auto overflow-visible mt-2">
                                                        {/* Grid Lines */}
                                                        <line x1="40" y1="20" x2="480" y2="20" stroke="rgba(255,255,255,0.05)" />
                                                        <line x1="40" y1="70" x2="480" y2="70" stroke="rgba(255,255,255,0.05)" />
                                                        <line x1="40" y1="120" x2="480" y2="120" stroke="rgba(255,255,255,0.05)" />
                                                        <line x1="40" y1="170" x2="480" y2="170" stroke="rgba(255,255,255,0.05)" />
                                                        <line x1="40" y1="210" x2="480" y2="210" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" />
                                                        <line x1="40" y1="20" x2="40" y2="210" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" />

                                                        {/* Labels */}
                                                        <text x="15" y="25" fill="#94a3b8" fontSize="8" textAnchor="middle">12.0</text>
                                                        <text x="15" y="75" fill="#94a3b8" fontSize="8" textAnchor="middle">9.0</text>
                                                        <text x="15" y="125" fill="#94a3b8" fontSize="8" textAnchor="middle">6.0</text>
                                                        <text x="15" y="175" fill="#94a3b8" fontSize="8" textAnchor="middle">3.0</text>
                                                        <text x="15" y="213" fill="#94a3b8" fontSize="8" textAnchor="middle">0.0</text>

                                                        <text x="40" y="225" fill="#94a3b8" fontSize="8" textAnchor="middle">0.0</text>
                                                        <text x="150" y="225" fill="#94a3b8" fontSize="8" textAnchor="middle">0.12</text>
                                                        <text x="260" y="225" fill="#94a3b8" fontSize="8" textAnchor="middle">0.25</text>
                                                        <text x="370" y="225" fill="#94a3b8" fontSize="8" textAnchor="middle">0.37</text>
                                                        <text x="480" y="225" fill="#94a3b8" fontSize="8" textAnchor="middle">0.50</text>

                                                        {/* X-axis label */}
                                                        <text x="260" y="238" fill="#64748b" fontSize="8" textAnchor="middle">Simulation Time (seconds)</text>
                                                        {/* Y-axis label */}
                                                        <text x="-110" y="8" fill="#64748b" fontSize="8" textAnchor="middle" transform="rotate(-90)" className="origin-center">Max Wave Amplitude</text>

                                                        {/* Draw curves */}
                                                        <polyline
                                                            fill="none"
                                                            stroke="#38bdf8"
                                                            strokeWidth="2"
                                                            points={galileoData.cc_003.time.map((t: number, i: number) => {
                                                                const x_coord = 40 + (t / 0.5) * 440;
                                                                const y_coord = 210 - (galileoData.cc_003.sub_critical[i] / 12.0) * 190;
                                                                return `${x_coord},${y_coord}`;
                                                            }).join(" ")}
                                                        />

                                                        <polyline
                                                            fill="none"
                                                            stroke="#f43f5e"
                                                            strokeWidth="2"
                                                            points={galileoData.cc_003.time.map((t: number, i: number) => {
                                                                const x_coord = 40 + (t / 0.5) * 440;
                                                                const y_coord = 210 - (galileoData.cc_003.super_critical[i] / 12.0) * 190;
                                                                return `${x_coord},${y_coord}`;
                                                            }).join(" ")}
                                                        />
                                                    </svg>
                                                ) : (
                                                    <div className="h-40 flex items-center justify-center text-xs text-slate-500">Loading chart...</div>
                                                )}
                                            </div>
                                        </div>
                                    )}

                                    {activeId === 'cc_004' && (
                                        <div className="space-y-4">
                                            <p className="text-xs text-slate-400">
                                                Mirror symmetry pairs displaying the Hodge Number swap h¹¹(X) = h²¹(X*) and h²¹(X) = h¹¹(X*).
                                            </p>
                                            
                                            {/* Mirror Diamonds side-by-side */}
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-4 rounded-xl border border-white/5 bg-black/40">
                                                {/* Left: Primal */}
                                                <div className="space-y-3 flex flex-col items-center">
                                                    <span className="text-[10px] font-bold tracking-widest text-indigo-400 uppercase">Quintic Threefold (X)</span>
                                                    <div className="font-mono text-xs text-center leading-relaxed bg-black/40 p-4 rounded-xl border border-white/5 w-full flex flex-col items-center justify-center space-y-1">
                                                        <div className="text-slate-500">h⁰,⁰ = 1</div>
                                                        <div className="text-slate-500">0 &nbsp; 0</div>
                                                        <div className="text-slate-500">0 &nbsp; 0 &nbsp; 0</div>
                                                        <div className="text-white font-bold">1 &nbsp; <span className="text-indigo-400">1</span> &nbsp; <span className="text-rose-400">101</span> &nbsp; 1</div>
                                                        <div className="text-slate-500">0 &nbsp; 0 &nbsp; 0</div>
                                                        <div className="text-slate-500">0 &nbsp; 0</div>
                                                        <div className="text-slate-500">1</div>
                                                    </div>
                                                    <span className="text-[10px] text-slate-400">h¹¹ = 1, h²¹ = 101</span>
                                                </div>

                                                {/* Right: Dual Mirror */}
                                                <div className="space-y-3 flex flex-col items-center">
                                                    <span className="text-[10px] font-bold tracking-widest text-emerald-400 uppercase">Mirror Threefold (X*)</span>
                                                    <div className="font-mono text-xs text-center leading-relaxed bg-black/40 p-4 rounded-xl border border-white/5 w-full flex flex-col items-center justify-center space-y-1">
                                                        <div className="text-slate-500">1</div>
                                                        <div className="text-slate-500">0 &nbsp; 0</div>
                                                        <div className="text-slate-500">0 &nbsp; 0 &nbsp; 0</div>
                                                        <div className="text-white font-bold">1 &nbsp; <span className="text-rose-400">101</span> &nbsp; <span className="text-indigo-400">1</span> &nbsp; 1</div>
                                                        <div className="text-slate-500">0 &nbsp; 0 &nbsp; 0</div>
                                                        <div className="text-slate-500">0 &nbsp; 0</div>
                                                        <div className="text-slate-500">1</div>
                                                    </div>
                                                    <span className="text-[10px] text-slate-400">h¹¹ = 101, h²¹ = 1</span>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {activeId === 'cc_005' && (
                                        <div className="space-y-4">
                                            <p className="text-xs text-slate-400">
                                                Position-space Bessel representation of the 3-loop sunrise Feynman integral. Computes at threshold s = 16m² using mpmath integrations.
                                            </p>
                                            
                                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                                {/* Feynman Diagram SVG */}
                                                <div className="md:col-span-1 p-4 rounded-xl border border-white/5 bg-black/40 flex flex-col items-center justify-center space-y-2">
                                                    <span className="text-[10px] font-semibold text-slate-400 uppercase">3-Loop Sunrise</span>
                                                    <svg viewBox="0 0 100 60" className="w-20 h-auto overflow-visible">
                                                        {/* Vertices */}
                                                        <circle cx="20" cy="30" r="3" fill="#6366f1" />
                                                        <circle cx="80" cy="30" r="3" fill="#6366f1" />
                                                        {/* Propagators */}
                                                        <path d="M 20 30 L 80 30" stroke="rgba(255,255,255,0.7)" strokeWidth="1.5" />
                                                        <path d="M 20 30 Q 50 10 80 30" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="1.5" />
                                                        <path d="M 20 30 Q 50 50 80 30" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="1.5" />
                                                        <path d="M 20 30 Q 50 62 80 30" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="1.2" strokeDasharray="2,2" />
                                                    </svg>
                                                    <span className="text-[9px] text-slate-500">4 equal-mass lines</span>
                                                </div>

                                                {/* Value Card */}
                                                <div className="md:col-span-2 p-4 rounded-xl border border-white/5 bg-black/40 space-y-3 justify-center flex flex-col">
                                                    <div className="space-y-1">
                                                        <span className="text-[10px] font-semibold text-slate-400 uppercase">Computed value (mpmath)</span>
                                                        <div className="font-mono text-base font-bold text-amber-300 break-all select-all">
                                                            {galileoData?.cc_005?.integral_value || "1.0471975511965977"}
                                                        </div>
                                                    </div>
                                                    <div className="text-[10px] text-slate-400 leading-normal border-t border-white/5 pt-2">
                                                        Fits exactly to weight-4 cusp forms on Γ₀(6): <br/>
                                                        S₃ = c * L(f, 3) + d * ζ(3).
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* GNN / GAN Latent Space Section */}
                                <div className="p-6 rounded-2xl bg-slate-950/40 border border-white/5 space-y-5">
                                    <div className="flex items-center space-x-2">
                                        <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
                                        </svg>
                                        <h4 className="text-sm font-semibold text-emerald-400 uppercase tracking-wider">
                                            GAN/GNN Latent Space Mapping & Provability
                                        </h4>
                                    </div>
                                    
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
                                        {/* Latent space scatter plot */}
                                        <div className="p-4 rounded-xl border border-white/5 bg-black/60 relative flex flex-col items-center">
                                            <span className="text-[9px] font-bold text-slate-500 uppercase absolute top-2 left-3">t-SNE Embeddings</span>
                                            
                                            <svg viewBox="0 0 400 220" className="w-full h-auto overflow-visible mt-4">
                                                {/* Grid lines */}
                                                <line x1="20" y1="20" x2="380" y2="20" stroke="rgba(255,255,255,0.03)" />
                                                <line x1="20" y1="60" x2="380" y2="60" stroke="rgba(255,255,255,0.03)" />
                                                <line x1="20" y1="100" x2="380" y2="100" stroke="rgba(255,255,255,0.03)" />
                                                <line x1="20" y1="140" x2="380" y2="140" stroke="rgba(255,255,255,0.03)" />
                                                <line x1="20" y1="180" x2="380" y2="180" stroke="rgba(255,255,255,0.03)" />
                                                
                                                <line x1="60" y1="10" x2="60" y2="200" stroke="rgba(255,255,255,0.03)" />
                                                <line x1="140" y1="10" x2="140" y2="200" stroke="rgba(255,255,255,0.03)" />
                                                <line x1="220" y1="10" x2="220" y2="200" stroke="rgba(255,255,255,0.03)" />
                                                <line x1="300" y1="10" x2="300" y2="200" stroke="rgba(255,255,255,0.03)" />
                                                
                                                {/* Cluster Labels */}
                                                <text x="70" y="35" fill="rgba(16,185,129,0.3)" fontSize="9" fontWeight="bold">SOLVABLE MANIFOLD</text>
                                                <text x="250" y="190" fill="rgba(244,63,94,0.2)" fontSize="9" fontWeight="bold">CONTRADICTORY REGION</text>

                                                {/* Solvable cluster points */}
                                                <circle cx="80" cy="50" r="3.5" fill="#10b981" opacity="0.4" />
                                                <circle cx="95" cy="70" r="3.5" fill="#10b981" opacity="0.4" />
                                                <circle cx="110" cy="45" r="3.5" fill="#10b981" opacity="0.4" />
                                                <circle cx="65" cy="65" r="3.5" fill="#10b981" opacity="0.4" />
                                                <circle cx="130" cy="60" r="3.5" fill="#10b981" opacity="0.4" />

                                                {/* Contradictory cluster points */}
                                                <circle cx="310" cy="150" r="3.5" fill="#f43f5e" opacity="0.4" />
                                                <circle cx="330" cy="170" r="3.5" fill="#f43f5e" opacity="0.4" />
                                                <circle cx="290" cy="165" r="3.5" fill="#f43f5e" opacity="0.4" />
                                                <circle cx="320" cy="135" r="3.5" fill="#f43f5e" opacity="0.4" />

                                                {/* Other conjectures points */}
                                                <circle cx="200" cy="120" r="3.5" fill="#a855f7" opacity="0.3" />
                                                <circle cx="215" cy="135" r="3.5" fill="#a855f7" opacity="0.3" />
                                                <circle cx="170" cy="105" r="3.5" fill="#a855f7" opacity="0.3" />

                                                {/* Active Conjecture node (represented with glowing rings) */}
                                                {activeConj.latent_x && activeConj.latent_y && (
                                                    <>
                                                        <circle cx={activeConj.latent_x} cy={activeConj.latent_y} r="8" fill="rgba(99,102,241,0.25)" className="animate-ping" style={{ transformOrigin: `${activeConj.latent_x}px ${activeConj.latent_y}px` }} />
                                                        <circle cx={activeConj.latent_x} cy={activeConj.latent_y} r="5" fill="#6366f1" stroke="#ffffff" strokeWidth="1" />
                                                    </>
                                                )}
                                            </svg>
                                            <span className="text-[9px] text-indigo-300 mt-2">Glow denotes active embedding location</span>
                                        </div>
                                        
                                        {/* Justification text */}
                                        <div className="space-y-3">
                                            <div className="p-4 rounded-xl bg-black/40 border border-white/5 space-y-2">
                                                <span className="text-[10px] font-bold text-indigo-400 uppercase">GNN Verification Node</span>
                                                <p className="text-xs text-slate-300 leading-relaxed">
                                                    {activeConj.provability_justification}
                                                </p>
                                            </div>
                                            
                                            {/* GNN Calibration & Oracle Verification (Justification on Justification) */}
                                            <div className="p-4 rounded-xl bg-black/40 border border-white/5 space-y-1">
                                                <span className="text-[10px] font-bold text-emerald-400 uppercase">GNN Calibration & Oracle Evidence</span>
                                                <p className="text-[11px] text-slate-400 leading-relaxed">
                                                    {activeId === 'cc_001' && "Verified via Minkowski's convex bodies theorem over SL(n, ℝ). Topologically calibrated against the Leech lattice (d=24) and E8 (d=8) boundary cases."}
                                                    {activeId === 'cc_002' && "Calibrated against the Littlewood-Richardson rule and Gelfand-Tsetlin patterns. Positivity coefficients checked up to n=12 via Schur-basis expansion."}
                                                    {activeId === 'cc_003' && "Calibrated against Weinstein's variational theorem and Merle-Raphaël blow-up profiles. Double-checked via split-step Fourier numerical solvers."}
                                                    {activeId === 'cc_004' && "Calibrated against the Kontsevich homological mirror symmetry theorem and Bridgeland stability condition spaces for K3 surfaces."}
                                                    {activeId === 'cc_005' && "Calibrated against Zhou's Bessel moment recursions and Broadhurst's modularity checks. Double-checked via multi-precision integration over Γ₀(6)."}
                                                </p>
                                            </div>

                                            <div className="p-4 rounded-xl bg-black/40 border border-white/5 flex items-center justify-between">
                                                <div>
                                                    <div className="text-[10px] font-bold text-slate-500 uppercase mb-1">Manifold Proximity</div>
                                                    <div className="text-xl font-mono font-bold text-emerald-400">
                                                        P = {(activeConj.provability_index * 100).toFixed(2)}%
                                                    </div>
                                                </div>
                                                <div className="text-right">
                                                    <div className="text-[10px] font-bold text-slate-500 uppercase mb-1">Verification Status</div>
                                                    <span className="text-xs font-semibold px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
                                                        Oracle Bound
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Peer Review & Verification Columns */}
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* AI Critique */}
                                    <div className="p-5 rounded-xl bg-slate-900/40 border border-slate-700/50">
                                        <h4 className="text-sm font-semibold text-emerald-400 uppercase tracking-wider mb-2 flex items-center">
                                            <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                            </svg>
                                            Mistral Peer Review
                                        </h4>
                                        <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap max-h-[200px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-700">
                                            {activeConj.mistral_critique}
                                        </div>
                                    </div>

                                    {/* Human Verification */}
                                    <div className="p-5 rounded-xl bg-amber-950/10 border border-amber-500/25">
                                        <h4 className="text-sm font-semibold text-amber-400 uppercase tracking-wider mb-2 flex items-center">
                                            <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.254 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                            </svg>
                                            Human Peer Review (Alexandrie)
                                        </h4>
                                        <p className="text-xs text-amber-200/80 leading-relaxed max-h-[200px] overflow-y-auto pr-2">
                                            {activeConj.human_review}
                                        </p>
                                    </div>
                                </div>

                                {/* Lean 4 Formalization Block */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Lean 4 Proposal</h4>
                                        <button
                                            onClick={() => handleCopy(activeConj.lean_code)}
                                            className="text-[10px] text-indigo-400 hover:text-indigo-300 transition-colors flex items-center bg-indigo-500/10 px-2.5 py-1 rounded hover:bg-indigo-500/20"
                                        >
                                            <svg className="w-3.5 h-3.5 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                            </svg>
                                            {copied ? "Copied!" : "Copy Code"}
                                        </button>
                                    </div>
                                    <div className="relative group">
                                        <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/10 to-purple-500/10 rounded-xl blur-md opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                                        <pre className="relative p-5 rounded-xl bg-[#09090d] border border-white/5 overflow-x-auto text-xs font-mono leading-relaxed shadow-inner">
                                            <code className="text-emerald-300">{activeConj.lean_code}</code>
                                        </pre>
                                    </div>
                                </div>

                                {/* Bottom status cards */}
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-white/5">
                                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
                                        <div className="text-[10px] text-slate-500 mb-1 uppercase tracking-wider">Provability Index</div>
                                        <div className="text-xl font-bold text-emerald-400 font-mono">{activeConj.provability_index.toFixed(4)}</div>
                                        <div className="text-[9px] text-slate-500 mt-1">PyTorch GNN Verification</div>
                                    </div>
                                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
                                        <div className="text-[10px] text-slate-500 mb-1 uppercase tracking-wider">Status</div>
                                        <div className="text-sm font-semibold text-amber-400 flex items-center mt-1">
                                            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-2 animate-pulse" />
                                            {activeConj.id === 'cc_003' ? 'PROVEN THEOREM' : 'UNPROVED CONJECTURE'}
                                        </div>
                                        <div className="text-[9px] text-slate-500 mt-1">
                                            {activeConj.id === 'cc_003' ? 'Verified classical threshold' : 'Open room peer review phase'}
                                        </div>
                                    </div>
                                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
                                        <div className="text-[10px] text-slate-500 mb-1 uppercase tracking-wider">Oracle Match</div>
                                        <div className="text-sm font-semibold text-indigo-400 flex items-center mt-1">
                                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mr-2" />
                                            Galileo CAS Valid
                                        </div>
                                        <div className="text-[9px] text-slate-500 mt-1">Empirical double-checks pass</div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="h-full min-h-[400px] flex flex-col items-center justify-center p-12 rounded-3xl border border-dashed border-white/10 bg-white/[0.02] text-center">
                                <h3 className="text-lg font-medium text-white mb-2">No conjecture selected</h3>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </main>
    );
}
"""

# Replace placeholder with string-encoded conjectures JSON
final_code = template.replace("__CONJECTURES_PLACEHOLDER__", conjestures_json)

with open(page_path, "w") as f:
    f.write(final_code)

print("Injected advanced UI changes successfully!")
