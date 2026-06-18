import google.generativeai as genai
import os
import json
import asyncio

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

model = genai.GenerativeModel(
    model_name='gemini-1.5-pro',
    system_instruction="You are an expert mathematician and physicist acting as 'Gemini 3.1 Pro Deep Think'. Provide a rigorous, critical, and profound peer review of the following Callens conjectures. Focus on the mathematical background, the Lean 4 formalizations, Galileo experimentations, the remaining steps, and overall viability. Format the output beautifully using Markdown."
)

async def review_conjecture(conjecture_data, reviewer_id):
    prompt = f"""Please provide Peer Review #{reviewer_id} for the following set of 4 Callens conjectures and their details:

{json.dumps(conjecture_data, indent=2)}

Include:
1. Analysis of the Mathematical Background
2. Feasibility of the Lean 4 formalization and sorry completions
3. Review of the Galileo numerical experimentations
4. Assessment of remaining steps to fully verify the conjectures
5. Overall scientific and business potential.

Do this with the persona of a different highly critical peer reviewer for each ID:
- If ID is 1: Act as a pure mathematician who is extremely skeptical of numerical approximations and demands rigorous formal proofs.
- If ID is 2: Act as an applied physicist and computational scientist who focuses on the physical relevance, business potential, and numerical stability of the Galileo experiments.
- If ID is 3: Act as a formal verification expert who focuses specifically on the Lean 4 implementation, the use of axioms, and the path to resolving remaining 'sorry' states.
"""
    
    response = await model.generate_content_async(prompt)
    return response.text

async def main():
    with open("/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/callens_conjectures_enriched.json", "r") as f:
        conjectures = json.load(f)
        
    reviews = []
    for i in range(1, 4):
        print(f"Conducting Review #{i}...")
        review = await review_conjecture(conjectures, i)
        reviews.append(f"## Peer Review #{i}\n\n{review}")
        
    with open("/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/peer_reviews.md", "w") as f:
        f.write("# 3 Peer Reviews by Gemini 3.1 Pro Deep Think\n\n")
        f.write("\n\n---\n\n".join(reviews))
        
    print("Peer reviews saved to artifacts/peer_reviews.md")

if __name__ == "__main__":
    asyncio.run(main())
