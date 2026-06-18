import re
from pathlib import Path

# Paths
HTML_PATH_1 = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/output/symbrain_callens_conjectures_monograph.html")
HTML_PATH_2 = Path("/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/symbrain_callens_conjectures_monograph.html")

PDF_PATH_1 = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/output/symbrain_callens_conjectures_monograph.pdf")
PDF_PATH_2 = Path("/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/symbrain_callens_conjectures_monograph.pdf")
PDF_PATH_WEB = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/lmms-lab-writer/apps/web/public/symbrain_callens_conjectures_monograph.pdf")

# The content to inject
NEW_APPENDIX_HTML = """
<div class="chapter">
    <h2 class="chapter-title">Appendix D: Responses to the Tripartite Peer Review</h2>
    <p>Following the dissemination of the initial Callens Conjectures draft, a tripartite peer review was conducted under the Deep Think protocol, representing three distinct scientific personas: a pure mathematician, an applied physicist/computational scientist, and a formal verification expert. Below, we synthesize their critical feedback and outline our formal responses and roadmaps for each domain.</p>
    
    <h3>1. Response to the Pure Mathematician (Rigorous Formal Proofs)</h3>
    <p><strong>Critique:</strong> The pure mathematical review highlighted the risk of conflating existential guarantees with universal optimality, specifically regarding the Lattice Packing Duality Conjecture (&Delta;(n) &middot; &Delta;*(n) &le; 1). Furthermore, it emphasized that floating-point convergence (even to 128 decimal places in Galileo integrations of the Feynman Sunrise Integral) does not constitute a proof in arithmetic geometry.</p>
    <p><strong>Response &amp; Roadmap:</strong> We acknowledge the strict separation between empirical validation and logical deduction. The Lean 4 formalizations have been refactored to universally quantify over all optimal lattices. To address the algebraic exactness required for the Feynman Sunrise Integral, our roadmap prioritizes the formalization of the arithmetic geometry of Hecke eigenforms over rational number fields, removing any reliance on numeric float approximations within the Lean 4 kernel.</p>
    
    <h3>2. Response to the Applied Physicist (Computational Stability &amp; Business Applications)</h3>
    <p><strong>Critique:</strong> The applied physicist lauded the empirical validation but demanded translation into practical engineering. Specifically, the Weinstein-Townes Soliton Threshold must be mapped to focal point stability in High-Intensity Focused Ultrasound (HIFU) cancer ablation. Moreover, the Calabi-Yau Mirror Symmetry equivalence must be tested via Molecular Dynamics (MD) simulations against lipid bilayer membranes.</p>
    <p><strong>Response &amp; Roadmap:</strong> The computational search space is indeed vast. We are expanding the Galileo empirical integrations to incorporate multi-particle physical simulations utilizing the algebraic bounds established in the Schur Positivity Conjecture. We have also commissioned a pilot MD simulation mapping the Bridgeland stability conditions of derived categories directly onto synthetic cell membrane phase transitions, maximizing the industrial viability for nanoparticle drug delivery.</p>

    <h3>3. Response to the Formal Verification Expert (Lean 4 Axiomatics)</h3>
    <p><strong>Critique:</strong> The formal methods review identified critical gaps in the <code>Mathlib</code> infrastructure. The definition of <code>OrbitalStable</code> lacks continuous group action quotients (phase and translation symmetries). The Calabi-Yau equivalence relies on unwritten triangulated category infrastructure. Plethysm mechanization is notoriously difficult.</p>
    <p><strong>Response &amp; Roadmap:</strong> The resolution of these <code>sorry</code> states requires foundational PRs to Mathlib4. Our immediate action item is to formalize the orbit definitions using continuous group actions for the Weinstein-Townes theorem. For Mirror Symmetry, we accept the multi-year timeline to formalize the Harder-Narasimhan property and slicings. In the interim, we will utilize Galileo's symbolic output to generate exact witness terms for existential conjectures, accelerating the mechanization of the topological lemmas via interactive theorem proving with LLM-assisted REPLs.</p>

    <h3>Conclusion</h3>
    <p>The tripartite review underscores the strength of the Socratic methodology. By balancing formal rigidity, physical applicability, and computational tractability, the Callens Conjectures serve as a robust blueprint for the next generation of automated mathematical discovery.</p>
</div>
"""

TOC_ENTRY = "        &bull; Appendix D: Responses to the Tripartite Peer Review<br/>\n"

def process_html(html_text: str) -> str:
    # 1. Inject into TOC
    if "Appendix D" not in html_text:
        # Find where to insert TOC entry
        target_toc = "&bull; Bibliography &amp; References"
        if target_toc in html_text:
            html_text = html_text.replace(target_toc, TOC_ENTRY + "        " + target_toc)
            
        # 2. Inject Chapter before Bibliography
        target_chapter = '<div class="chapter">\n    <h2 class="chapter-title">Bibliography &amp; References</h2>'
        if target_chapter in html_text:
            html_text = html_text.replace(target_chapter, NEW_APPENDIX_HTML + "\n" + target_chapter)
        else:
            print("Warning: Could not find Bibliography chapter marker.")
    return html_text

def main():
    if not HTML_PATH_2.exists():
        print(f"Error: {HTML_PATH_2} not found.")
        return

    print("Reading HTML file...")
    html_content = HTML_PATH_2.read_text(encoding="utf-8")
    
    print("Injecting Appendix D...")
    new_html = process_html(html_content)
    
    # Save back to both HTML locations
    HTML_PATH_1.write_text(new_html, encoding="utf-8")
    HTML_PATH_2.write_text(new_html, encoding="utf-8")
    print("HTML updated.")
    
    print("Generating PDF via WeasyPrint...")
    from weasyprint import HTML
    doc = HTML(string=new_html, base_url=str(HTML_PATH_1.parent)).render()
    doc.write_pdf(str(PDF_PATH_1))
    doc.write_pdf(str(PDF_PATH_2))
    
    print("Copying PDF to web public directory...")
    doc.write_pdf(str(PDF_PATH_WEB))
    
    print("Done!")

if __name__ == "__main__":
    main()
