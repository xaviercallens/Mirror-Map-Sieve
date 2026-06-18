import subprocess
import json
import logging

logger = logging.getLogger(__name__)

class LeanREPL:
    """Persistent connection to Lean 4 REPL via stdin/stdout."""
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.process = subprocess.Popen(
            ["lake", "env", "lean", "--run", ".lake/packages/REPL/REPL/Main.lean"],
            cwd=workspace_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    def send_command(self, cmd_dict: dict) -> dict:
        """Send a JSON command to the REPL and read the response."""
        cmd_str = json.dumps(cmd_dict)
        try:
            # repl requires an empty line or just a newline depending on mode,
            # but a single JSON string followed by \n usually suffices.
            self.process.stdin.write(cmd_str + "\n\n")
            self.process.stdin.flush()
            
            buf = ""
            while True:
                line = self.process.stdout.readline()
                logger.debug(f"Raw REPL output: {repr(line)}")
                if not line:
                    stderr = self.process.stderr.read()
                    logger.error(f"REPL crashed or closed. stderr: {stderr}")
                    return {}
                
                # If buf is empty, discard lines until we see '{'
                if not buf and not line.strip().startswith("{"):
                    logger.debug(f"Raw REPL output (skipped): {repr(line)}")
                    continue
                    
                buf += line
                try:
                    res = json.loads(buf)
                    return res
                except json.JSONDecodeError:
                    # Still waiting for the rest of the JSON object
                    pass
        except Exception as e:
            logger.error(f"Error communicating with REPL: {e}")
            return {}

    def init_proof(self, file_content: str) -> dict:
        """Send the initial Lean file content containing sorry stubs."""
        return self.send_command({"cmd": file_content})
        
    def execute_tactic(self, state: int, tactic_string: str) -> dict:
        """Execute a tactic at a specific proof state."""
        return self.send_command({"tactic": tactic_string, "proofState": state})

    def close(self):
        """Close the REPL process."""
        try:
            self.process.stdin.close()
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
