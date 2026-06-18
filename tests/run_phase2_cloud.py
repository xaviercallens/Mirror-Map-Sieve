import asyncio
import os
import glob
import json
import logging
from dotenv import load_dotenv
load_dotenv(override=True)
from agents.turing.agent import TuringAgent
from agents.socrates.agent import SocratesAgent
from agents.euler.agent import EulerAgent
from agents.archimedes.agent import ArchimedesAgent
from agents.galileo.agent import GalileoAgent
from agents.hypatie.agent import HypatieAgent
from agents.galileo.tools.precision_validator import validate_against_horizonmath

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Phase2Deploy")

if "SSL_CERT_FILE" in os.environ and os.path.isdir(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

async def run_phase2():
    turing = TuringAgent()
    socrates = SocratesAgent()
    
    v16_dir = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/achievement_output/v16_offline"
    lean_files = glob.glob(os.path.join(v16_dir, "*.lean"))
    
    # Analyze problems
    problem_stats = []
    for f in lean_files:
        name = os.path.basename(f).replace(".lean", "")
        with open(f, "r") as fd:
            content = fd.read()
        sorry_count = content.count("sorry")
        problem_stats.append((name, sorry_count, f, content))
        
    problem_stats.sort(key=lambda x: x[1])
    
    # Pick 15 simple (fewest sorry) and 15 complex (most sorry)
    simple = problem_stats[:15]
    complex_probs = problem_stats[-15:]
    target_problems = simple + complex_probs
    
    logger.info(f"Selected 30 problems: 15 simple (avg sorry {sum(x[1] for x in simple)/15:.1f}), 15 complex (avg sorry {sum(x[1] for x in complex_probs)/15:.1f})")
    
    # Turing limits and monitoring
    total_cost = 0.0
    BUDGET_LIMIT = 150.0
    
    completed_tasks = 0
    start_time = asyncio.get_event_loop().time()
    
    async def process_problem(prob_info):
        nonlocal completed_tasks
        name, sorry_count, filepath, content = prob_info
        
        # Determine class and GPU tier based on user override
        solv_class = "class_3" if sorry_count > 5 else "class_2"
        gpu_tier = "H100" if solv_class == "class_3" else "L4"
        nodes = 1 if gpu_tier == "H100" else 4
        
        # 1. Turing Deploy
        turing_res = await turing.run(
            f"Deploy SymBrain for {name} using {nodes}x {gpu_tier}",
            gpu_type=gpu_tier,
            deployment_nodes=nodes,
            solvability_class=solv_class
        )
        
        # 2. Socrates Rule Check
        soc_res = await socrates.run(f"Enforce Zero-Sorry Guillotine on {name} pipeline execution.")
        
        # 3. Archimedes Gap Resolution (Semantic REPL + Topological)
        archimedes = ArchimedesAgent()
        arch_res = await archimedes.run(f"Resolve sorry gaps for {name}.", lean4_sketch=content, domain="mathematical_physics")
        resolved_content = arch_res.answer.get("lean4_sketch", content)
        
        # 4. Euler Formal Path to Verified
        euler = EulerAgent()
        euler_res = await euler.run(f"Run path to verified for {name}.", proof_code=resolved_content)
        
        # 5. Galileo Numerical Evaluation
        galileo = GalileoAgent()
        galileo_res = await galileo.run(f"Numerically validate closed form formulas for {name}.", lean4_code=resolved_content)
        
        status = "VERIFIED" if euler_res.answer.get("status") == "VERIFIED" else "FAILED"
        if galileo_res.answer.get("success"):
            status += " (GALILEO PASSED)"
        
        cost = turing_res.cost_usd + soc_res.cost_usd + arch_res.cost_usd + euler_res.cost_usd + galileo_res.cost_usd
        
        from alexandrie.hub import AlexandrieHub
        from alexandrie.metadata import ArtifactType, RoomType
        hub = AlexandrieHub()
        hub.store_artifact(
            artifact_id=f"v18_Phase2_{name}",
            title=f"Phase 2 REPL Result for {name}",
            content=resolved_content,
            artifact_type=ArtifactType.PROOF,
            room_type=RoomType.OPEN_ACCESS,
            creator="socrates_coordinator",
            tags=["symbrain-v18-phase2"],
            metrics={"status": status, "cost": cost, "tier": gpu_tier}
        )
        
        completed_tasks += 1
        
        return {
            "name": name,
            "tier": gpu_tier,
            "status": status,
            "cost": cost
        }

    # Execute problems concurrently, but run a background monitor loop
    async def monitor_budget():
        while True:
            await asyncio.sleep(600) # Every 10 mins
            current_time = asyncio.get_event_loop().time()
            elapsed = current_time - start_time
            
            # ETA calculation
            if completed_tasks > 0:
                avg_time_per_task = elapsed / completed_tasks
                remaining_tasks = len(target_problems) - completed_tasks
                eta_seconds = remaining_tasks * avg_time_per_task
                eta_str = f"{eta_seconds / 60:.1f} minutes"
            else:
                eta_str = "Calculating..."
                
            logger.info("Turing 10-minute Budget Monitor running...")
            bill_res = await turing.run("Check GCP billing efficiency.", execution_history=[])
            est_cost = bill_res.answer.get("billing_report", {}).get("estimated_accumulated_cost_usd", total_cost)
            
            logger.info(f"Progress: {completed_tasks}/{len(target_problems)} problems solved.")
            logger.info(f"ETA: {eta_str}")
            logger.info(f"Current Estimated Accumulated Cost: ${est_cost:.2f} / ${BUDGET_LIMIT:.2f}")
            
            if est_cost > 130.0:
                logger.warning("Budget limit approaching! Turing tearing down deployment.")
                await turing.run("Tear down symbrain_swarm immediately.", service_name="symbrain_swarm")
                break
                
    monitor_task = asyncio.create_task(monitor_budget())
    
    # Process tasks with concurrency limit
    sem = asyncio.Semaphore(3)
    async def process_with_sem(p):
        async with sem:
            return await process_problem(p)
            
    tasks = [process_with_sem(p) for p in target_problems]
    results = await asyncio.gather(*tasks)
    
    monitor_task.cancel()
    
    total_run_cost = sum(r['cost'] for r in results)
    
    # Write Phase 2 Report
    out_dir = "/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts"
    with open(f"{out_dir}/phase2_30_problems_report.md", "w") as f:
        f.write("# Phase 2 Dry Run: 30 Problems (Cloud)\\n\\n")
        f.write(f"Total Deployment Cost: ${total_run_cost:.2f}\\n\\n")
        for res in results:
            f.write(f"- **{res['name']}** [{res['tier']}]: {res['status']} (${res['cost']:.2f})\\n")
            
    # Hypatia Monograph Generation
    from alexandrie.hub import AlexandrieHub
    hub = AlexandrieHub()
    v18_results = []
    # Search vault for v18_Phase2 artifacts to pass to Hypatia
    matches = hub.search_vault("v18_Phase2_")
    for meta in matches:
        ret = hub.retrieve_artifact(meta.id)
        if ret:
            m, content = ret
            v18_results.append({
                "name": m.id.replace("v18_Phase2_", ""),
                "status": m.metrics.get("status", "FAILED"),
                "cost": m.metrics.get("cost", 0.0),
                "tier": m.metrics.get("tier", "L4"),
                "content": content
            })

    hypatia = HypatieAgent()
    hypatia_res = await hypatia.run("Generate symbrain_v18_phase2_monograph.tex taking v16 monograph as example.", 
                      results=v18_results, 
                      template="symbrain_v16_horizonmath_monograph.tex")
                      
    tex_content = hypatia_res.answer.get("latex_synthesizer", {}).get("latex_code", "")
    if not tex_content:
        tex_content = str(hypatia_res.answer)
        
    out_tex_path = "achievement_output/v18_dryrun/symbrain_v18_phase2_monograph.tex"
    os.makedirs(os.path.dirname(out_tex_path), exist_ok=True)
    with open(out_tex_path, "w") as f:
        f.write(tex_content)
    logger.info(f"Saved monograph to {out_tex_path}")
                      
    logger.info("Phase 2 deployment and generation complete.")

if __name__ == "__main__":
    asyncio.run(run_phase2())
