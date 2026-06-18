import os
import subprocess
import logging

logger = logging.getLogger(__name__)

def global_stitch_and_build(theorem_name: str, proof_code: str, output_dir: str = "achievement_output/v18_dryrun/lean_files") -> dict:
    """
    Synthesize the individual REPL-verified tactic blocks into a globally compliant .lean file
    and run 'lake build' to ensure it compiles correctly.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Ensure it has basic headers if missing
    if "import Mathlib" not in proof_code:
        proof_code = "import Mathlib\n\n" + proof_code
        
    file_path = os.path.join(output_dir, f"{theorem_name}.lean")
    
    try:
        with open(file_path, "w") as f:
            f.write(proof_code)
            
        # Optional: Run lake build (assuming we're in a valid lean package dir, or just leanc)
        # Note: If output_dir isn't in a Lake project, `lake build` won't work on the file directly.
        # We can just run `lean {file_path}`.
        res = subprocess.run(["lean", file_path], capture_output=True, text=True, timeout=60)
        
        success = res.returncode == 0
        return {
            "success": success,
            "file_path": file_path,
            "output": res.stdout + "\n" + res.stderr
        }
    except Exception as e:
        logger.error(f"Global stitch failed: {e}")
        return {"success": False, "error": str(e)}
