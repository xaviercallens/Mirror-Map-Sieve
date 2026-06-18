import asyncio
import structlog

from agents.galileo.agent import GalileoAgent

# Setup simple logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer()
    ]
)

async def main():
    print("="*80)
    print("🔬 GALILEO AGENT: Numeric Validation of Alien Lyapunov Functional")
    print("="*80)
    
    agent = GalileoAgent()
    
    # Query designed to trigger the new PDE validation tool
    query = (
        "Run an empirical numeric simulation of the Kuramoto-Sivashinsky equation "
        "and validate the monotonic decay of the Pathological Alien Lyapunov Functional."
    )
    
    print(f"\n[QUERY] {query}\n")
    
    # Run the agent
    result = await agent.run(query)
    
    print("\n" + "="*80)
    print("✅ GALILEO VALIDATION COMPLETE")
    print("="*80)
    
    # Display the results
    print(f"\nCost: ${result.cost_usd:.2f}")
    print(f"Confidence: {result.confidence * 100:.1f}%\n")
    
    # Extract the tool result
    tool_results = result.answer
    if "pde_alien_validator" in tool_results:
        pde_res = tool_results["pde_alien_validator"]
        if pde_res.get("success"):
            print("🚀 **PDE Validation Results:**")
            print(f"  - Validation Passed: {pde_res.get('validation_passed')}")
            print(f"  - Max dV/dt: {pde_res.get('max_dV_dt'):.4e}")
            print(f"  - Mean dV/dt: {pde_res.get('mean_dV_dt'):.4e}")
            print(f"  - Initial V: {pde_res.get('V_initial'):.4e}")
            print(f"  - Final V: {pde_res.get('V_final'):.4e}")
            print(f"  - Time points simulated: {pde_res.get('time_points')}")
            print(f"\nMessage: {pde_res.get('message')}")
        else:
            print(f"❌ PDE Integration Failed: {pde_res.get('message')}")
    else:
        print("❌ ERROR: pde_alien_validator tool was not invoked.")
        print(f"Tools invoked: {list(tool_results.keys())}")

if __name__ == "__main__":
    asyncio.run(main())
