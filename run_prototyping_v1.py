import asyncio
import structlog
from agents.pipelines.prototyping_pipeline import PrototypingPipeline

logger = structlog.get_logger(__name__)

async def main():
    # Use Gemini 3.1 Pro High if available, otherwise gemini-2.5-pro
    model = "gemini-2.5-pro"
    
    pipeline = PrototypingPipeline(model=model, num_loops=5)
    
    inventions = [
        "Verifiably Safe Motion Planning for Autonomous Systems (Guaranteed collision-free drone/car trajectories via hypercube safety corridors)",
        "High-Frequency Trading System with Deterministic Execution (FPGA/ASIC execution using exact rational bounds on risk/exposure)",
        "Precision Robotics for Telesurgery with Force-Feedback Guarantees (Formally verifying safety before moving a robotic arm in human tissue)"
    ]
    
    logger.info("Starting Prototyping Pipeline on 3 inventions", num_inventions=len(inventions))
    
    results = []
    for i, inv in enumerate(inventions):
        logger.info(f"--- Running Prototype for Invention {i+1} ---", invention=inv[:40])
        res = await pipeline.run({"topic": inv})
        results.append(res)
        logger.info(f"--- Completed Invention {i+1} ---", duration=res.total_duration_s)
        
    logger.info("All prototyping completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
