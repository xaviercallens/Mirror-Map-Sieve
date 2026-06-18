import json
import re

with open("/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/callens_conjectures_enriched.json") as f:
    data = json.load(f)

with open("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/lmms-lab-writer/apps/web/src/app/openroom/page.tsx") as f:
    page = f.read()

# Replace CONJECTURES array using a lambda
new_conjectures_str = "const CONJECTURES = " + json.dumps(data, indent=4) + ";"
page = re.sub(r'const CONJECTURES = \[.*?\];', lambda _: new_conjectures_str, page, flags=re.DOTALL)

# Rebrand titles
page = page.replace("The Open Room", "Open Room of Socrate Agora")
page = page.replace("A collaborative sanctuary for the human and AI mathematical community.", "A collaborative sanctuary for the human and AI mathematical community, dedicated to rigorous scientific discovery and peer review.")

# I previously replaced the old impact block with the Mistral critique block. 
# Let's find the Mistral critique block and replace it with a combined block that has BOTH physics/medical and Mistral critique.
mistral_block = """                                            <div className="p-5 rounded-xl bg-gradient-to-br from-slate-900/40 to-black border border-slate-700/50 shadow-inner">
                                                <h4 className="text-sm font-semibold text-emerald-300 uppercase tracking-wider mb-2 flex items-center">
                                                    <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                                                    Mistral Peer Review (Scientific Rigor)
                                                </h4>
                                                <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-700">
                                                    {conj.mistral_critique}
                                                </div>
                                            </div>"""

combined_block = """                                            <div className="grid grid-cols-1 gap-4">
                                                <div className="p-5 rounded-xl bg-gradient-to-br from-indigo-900/40 to-black border border-indigo-500/20 shadow-inner">
                                                    <h4 className="text-sm font-semibold text-indigo-200 uppercase tracking-wider mb-2 flex items-center">
                                                        <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
                                                        Potential Gain (Physics & Medicine)
                                                    </h4>
                                                    <p className="text-sm text-indigo-100/80 leading-relaxed">
                                                        {conj.physics_medical_context}
                                                    </p>
                                                </div>
                                                <div className="p-5 rounded-xl bg-gradient-to-br from-slate-900/40 to-black border border-slate-700/50 shadow-inner">
                                                    <h4 className="text-sm font-semibold text-emerald-300 uppercase tracking-wider mb-2 flex items-center">
                                                        <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                                                        Mistral Peer Review (Scientific Rigor & Verification)
                                                    </h4>
                                                    <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap max-h-[300px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-700">
                                                        {conj.mistral_critique}
                                                    </div>
                                                </div>
                                            </div>"""

page = page.replace(mistral_block, combined_block)

with open("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/lmms-lab-writer/apps/web/src/app/openroom/page.tsx", "w") as f:
    f.write(page)

print("Updated page.tsx with enriched context.")
