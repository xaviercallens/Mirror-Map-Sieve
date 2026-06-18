import json
import subprocess
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def pre_load_env(workspace_dir: str, imports: str = "import Mathlib") -> Tuple[Optional[int], Optional[subprocess.Popen]]:
    """
    Pre-loads Lean modules (like Mathlib) and returns the cached env ID and the REPL process.
    This saves time per REPL instantiation by reusing the Mathlib env.
    """
    logger.info(f"Starting Lean REPL in {workspace_dir} to pre-load: {imports}")
    process = subprocess.Popen(
        ["lake", "env", "lean", "--run", ".lake/packages/REPL/REPL/Main.lean"],
        cwd=workspace_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    cmd_dict = {"cmd": imports}
    cmd_str = json.dumps(cmd_dict) + "\n\n"
    
    try:
        process.stdin.write(cmd_str)
        process.stdin.flush()
        
        buf = ""
        while True:
            line = process.stdout.readline()
            if not line:
                break
                
            if not buf and not line.strip().startswith("{"):
                continue
                
            buf += line
            try:
                res = json.loads(buf)
                if "env" in res:
                    env_id = res["env"]
                    logger.info(f"Successfully cached environment ID: {env_id}")
                    return env_id, process
                elif "messages" in res:
                    logger.warning(f"REPL returned messages but no env ID: {res['messages']}")
                    return None, process
            except json.JSONDecodeError:
                pass
                
    except Exception as e:
        logger.error(f"Error communicating with REPL: {e}")
        
    return None, process

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    env_id, proc = pre_load_env("verifiers/lean4")
    if env_id is not None:
        print(f"Env ID: {env_id}")
    if proc:
        proc.kill()
