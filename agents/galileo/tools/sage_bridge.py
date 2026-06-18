import subprocess
import json
import tempfile
import os
from typing import Dict, Any

def sage_compute(script_content: str, timeout: int = 60) -> Dict[str, Any]:
    """
    Executes a SageMath script via subprocess and returns the parsed JSON output.
    """
    sage_cmd = os.environ.get('SAGE_CMD', 'sage')
    
    # We wrap the user script to ensure it outputs a JSON.
    wrapped_script = f"""
import json
import sys

def main():
    try:
        # User script starts
{chr(10).join('        ' + line for line in script_content.split(chr(10)))}
        # User script ends
    except Exception as e:
        print(json.dumps({{"error": str(e), "status": "failure"}}))
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sage', delete=False) as f:
        f.write(wrapped_script)
        temp_path = f.name
        
    try:
        result = subprocess.run(
            [sage_cmd, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            return {
                'error': f"SageMath process failed with return code {result.returncode}",
                'stderr': result.stderr,
                'status': 'failure'
            }
            
        try:
            # Look for the last line of stdout which should be JSON
            output_lines = result.stdout.strip().split('\n')
            last_line = output_lines[-1] if output_lines else '{}'
            data = json.loads(last_line)
            return data
        except json.JSONDecodeError:
            return {
                'error': 'Failed to parse JSON output from SageMath.',
                'raw_output': result.stdout,
                'status': 'failure'
            }
            
    except subprocess.TimeoutExpired:
        return {'error': f"SageMath execution timed out after {timeout} seconds.", 'status': 'failure'}
    except FileNotFoundError:
        return {'error': f"SageMath executable '{sage_cmd}' not found. Please install SageMath or set SAGE_CMD.", 'status': 'failure'}
    except Exception as e:
        return {'error': str(e), 'status': 'failure'}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
