import asyncio
from agents.hypatie.agent import HypatieAgent
from alexandrie.hub import AlexandrieHub
import os

if "SSL_CERT_FILE" in os.environ and os.path.isdir(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

async def main():
    hub = AlexandrieHub()
    v16_results = []
    matches = hub.search_vault("v16_Phase2_")
    for meta in matches:
        ret = hub.retrieve_artifact(meta.id)
        if ret:
            m, content = ret
            v16_results.append({
                "name": m.id.replace("v16_Phase2_", ""),
                "status": m.metrics.get("status", "FAILED"),
                "cost": m.metrics.get("cost", 0.0),
                "tier": m.metrics.get("tier", "L4"),
                "content": content
            })

    hypatia = HypatieAgent()
    hypatia_res = await hypatia.run(
        "Generate symbrain_v16_horizonmath_monograph.tex incorporating all 50 Phase 2 results. Include the sanitized sorry proofs.", 
        results=v16_results, 
        template="symbrain_v12_horizonmath_top10_v3.tex"
    )
                      
    tex_content = hypatia_res.answer.get("latex_synthesizer", {}).get("latex_code", "")
    if not tex_content:
        tex_content = str(hypatia_res.answer)
        
    out_tex_path = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/achievement_output/symbrain_v16_horizonmath_monograph.tex"
    os.makedirs(os.path.dirname(out_tex_path), exist_ok=True)
    with open(out_tex_path, "w") as f:
        f.write(tex_content)
    print(f"Saved monograph to {out_tex_path}")

if __name__ == "__main__":
    asyncio.run(main())
