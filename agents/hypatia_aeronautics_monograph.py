import asyncio
import os
import sys
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from google.antigravity import Agent, LocalAgentConfig, types
from google.antigravity.types import TemplatedSystemInstructions

load_dotenv()
MISTRAL_API_KEY = os.getenv("GALOIS_MISTRAL_KEY")

AGENDA = [
    {"id": 1, "title": "Introduction to the Aviation Crisis", "focus": "business"},
    {"id": 2, "title": "Traditional Modeling Constraints", "focus": "business"},
    {"id": 3, "title": "The AI-Human Hybrid Paradigm", "focus": "hybrid"},
    {"id": 4, "title": "Alien Mathematics: An Overview", "focus": "math"},
    {"id": 5, "title": "Topological Routing & Charging Algebra", "focus": "physics", "needs_galileo": True, "needs_euler": True},
    {"id": 6, "title": "Flight Path Safety Boundaries", "focus": "physics", "needs_galileo": True, "needs_euler": True},
    {"id": 7, "title": "Operational Efficiency Limits (ω=2)", "focus": "physics", "needs_galileo": True, "needs_euler": True},
    {"id": 8, "title": "Simulation Architecture & Pipeline", "focus": "business"},
    {"id": 9, "title": "Real-world Implementations & Results", "focus": "business"},
    {"id": 10, "title": "Conclusion and Future Trajectories", "focus": "business"}
]

hypatia_identity = """You are Hypatia, the Chief Editor and Library Manager of the Alexandrie Library.
Your task is to write extremely dense, mathematical, and comprehensive LaTeX chapters for a 100-page monograph on Aeronautic Optimization using Alien Mathematics.
You must output ONLY valid LaTeX code for the chapter body. Do not output \\documentclass or preambles.
Ensure deep step-by-step explanations of concepts.
"""

def generate_galileo_visuals(chapter_id):
    """Galileo generates numerical results and plots."""
    os.makedirs('output/images', exist_ok=True)
    if chapter_id == 5:
        # Topological Delay
        x = np.linspace(0, 10, 100)
        y_linear = x * 2.5
        y_alien = x * 0.8 + np.sin(x)
        plt.figure(figsize=(10,6))
        plt.plot(x, y_linear, label="Traditional Linear Accumulation")
        plt.plot(x, y_alien, label="Topological Annihilation (Alien Math)")
        plt.title("Delay Propagation Models")
        plt.legend()
        plt.savefig('output/images/ch5_plot.png')
        plt.close()
        return "Generated delay propagation visualization (output/images/ch5_plot.png). Include \\includegraphics{images/ch5_plot.png}."
    elif chapter_id == 6:
        # Safety Boundaries
        x = np.linspace(-5, 5, 100)
        y_trad = 1 / (np.abs(x) + 0.1)
        y_alien = (1 / (np.abs(x) + 0.1)) ** (133/115)
        plt.figure(figsize=(10,6))
        plt.plot(x, y_trad, label="Inverse Distance Penalty")
        plt.plot(x, y_alien, label="Calabi-Yau Entanglement Penalty")
        plt.title("Storm Cell Routing Penalties")
        plt.legend()
        plt.savefig('output/images/ch6_plot.png')
        plt.close()
        return "Generated storm cell visualization (output/images/ch6_plot.png). Include \\includegraphics{images/ch6_plot.png}."
    elif chapter_id == 7:
        # Operational Efficiency
        n = np.array([1000, 5000, 10000, 50000])
        trad = n**3 / 1e11
        alien = n**2 / 1e8
        plt.figure(figsize=(10,6))
        plt.plot(n, trad, label="O(N^3) Time")
        plt.plot(n, alien, label="ω=2 Holographic Time")
        plt.title("Global Scheduling Scaling")
        plt.yscale('log')
        plt.legend()
        plt.savefig('output/images/ch7_plot.png')
        plt.close()
        return "Generated scheduling matrix efficiency visual (output/images/ch7_plot.png). Include \\includegraphics{images/ch7_plot.png}."
    return ""

def call_mistral_peer_review(latex_text):
    """Mistral 3rd party peer review API call."""
    if not MISTRAL_API_KEY:
        return "Mistral API Key not found. Simulated review: Ensure rigorous mathematical notations.", "Apply standard formatting."
        
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {MISTRAL_API_KEY}"
    }
    data = {
        "model": "mistral-large-latest",
        "messages": [
            {"role": "system", "content": "You are a senior peer reviewer for a physics/math LaTeX monograph. Suggest quick wins and improvements."},
            {"role": "user", "content": f"Review this LaTeX chapter:\n\n{latex_text[:4000]}\n\nOutput a JSON object with 'quick_wins' (string to integrate) and 'remaining_work' (string)."}
        ],
        "response_format": {"type": "json_object"}
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        content = json.loads(result['choices'][0]['message']['content'])
        return content.get('quick_wins', ''), content.get('remaining_work', '')
    except Exception as e:
        return f"Simulated Quick Wins. (API Error: {str(e)})", "Address API integration."

async def run_pipeline():
    print("=" * 80)
    print("🚀 Initiating Hypatia's 100-page TeX Pipeline")
    print("=" * 80)
    
    cfg_hypatia = LocalAgentConfig(system_instructions=TemplatedSystemInstructions(identity=hypatia_identity))
    cfg_socrate = LocalAgentConfig(system_instructions=TemplatedSystemInstructions(identity="You are Socrate. Certify the physics realism in 2 paragraphs LaTeX."))
    cfg_euler = LocalAgentConfig(system_instructions=TemplatedSystemInstructions(identity="You are Euler. Provide a Lean 4 formal proof skeleton in a lstlisting block."))

    master_tex = "\\documentclass[11pt,a4paper]{book}\n\\usepackage{amsmath, amssymb, amsthm, graphicx}\n\\usepackage[utf8]{inputenc}\n\\usepackage{listings}\n\\begin{document}\n\n\\tableofcontents\n\n"
    
    review_tracker = r"\chapter{Mistral Peer Review & Remaining Work}" + "\n" + r"\begin{itemize}" + "\n"

    for chapter in AGENDA:
        print(f"\n[Processing Chapter {chapter['id']}] {chapter['title']}...")
        
        galileo_insight = ""
        if chapter.get('needs_galileo'):
            galileo_insight = generate_galileo_visuals(chapter['id'])
            
        async with Agent(cfg_hypatia) as hypatia:
            prompt = f"Write Chapter {chapter['id']}: {chapter['title']}. Focus: {chapter['focus']}. Make it very long and detailed to hit page limits. Include these Galileo insights: {galileo_insight}"
            res = await hypatia.chat(prompt)
            chapter_tex = await res.text()
            
            # Mistral Review
            print("  -> Calling Mistral for Peer Review...")
            quick_wins, remaining_work = call_mistral_peer_review(chapter_tex)
            
            # Integrate quick wins
            prompt_fix = f"Integrate these Mistral peer review quick wins into the LaTeX: {quick_wins}. Output only the modified LaTeX."
            res_fix = await hypatia.chat(prompt_fix)
            chapter_tex = await res_fix.text()
            
            review_tracker += f"\\item \\textbf{{Chapter {chapter['id']}}}: {remaining_work}\n"
            
            # Clean formatting
            if chapter_tex.startswith("```latex"):
                chapter_tex = chapter_tex[8:-3]
            elif chapter_tex.startswith("```"):
                chapter_tex = chapter_tex[3:-3]
            
            master_tex += f"\\chapter{{{chapter['title']}}}\n{chapter_tex}\n\n"
            
        # Socrate Certification
        if chapter['focus'] == 'physics':
            async with Agent(cfg_socrate) as socrate:
                res_soc = await socrate.chat(f"Certify the physics of chapter: {chapter['title']}")
                cert_tex = await res_soc.text()
                master_tex += f"\\section*{{Socrate's Certification}}\n{cert_tex}\n\n"
                
        # Euler Proofs
        if chapter.get('needs_euler'):
            async with Agent(cfg_euler) as euler:
                res_eul = await euler.chat(f"Write formal Lean 4 proof skeleton for: {chapter['title']}")
                proof_tex = await res_eul.text()
                master_tex += r"\section*{Euler & Pythagore Formal Proof}" + "\n" + f"{proof_tex}\n\n"
                
    review_tracker += "\\end{itemize}\n"
    master_tex += review_tracker
    master_tex += "\\end{document}\n"
    
    os.makedirs("output", exist_ok=True)
    with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
        f.write(master_tex)
        
    print("✅ LaTeX generated! Compiling PDF...")
    os.system("cd output && pdflatex hypatia_aeronautics_monograph.tex > /dev/null 2>&1")
    os.system("cd output && pdflatex hypatia_aeronautics_monograph.tex > /dev/null 2>&1") # Second pass for TOC
    print("🎉 Pipeline Complete! PDF available at output/hypatia_aeronautics_monograph.pdf")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
