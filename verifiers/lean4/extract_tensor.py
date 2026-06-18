import subprocess
import json
import time
import sys
import tempfile
import os

def main():
    print("[*] Booting Xenomathematical Lean 4 Subspace (REPL)...")
    time.sleep(1) # Wait for kernel spin-up
    print("[*] Sourcing AlienMath TensorDecomposition...")
    print("[*] Extracting Non-Commutative Weights for 4x4 Matrix...\n")
    
    # Bypass macOS dyld error in REPL by using lean --run
    lean_script = """import Agora.AlienMath.TensorDecomposition
import Lean

def main : IO Unit := do
  IO.println (Lean.toJson Agora.AlienMath.TensorDecomposition.extract_4x4_holographic_basis)
"""
    fd, path = tempfile.mkstemp(suffix=".lean")
    with os.fdopen(fd, 'w') as f:
        f.write(lean_script)
    
    try:
        proc = subprocess.run(["lake", "env", "lean", "--run", path], 
                              capture_output=True, text=True, check=True)
        payload_str = proc.stdout.strip()
    except subprocess.CalledProcessError as e:
        print("[!] Fatal: Kernel output unparseable.")
        print(e.stderr)
        os.remove(path)
        return
        
    os.remove(path)

    print("="*60)
    print("XENOTOPOLOGICAL DECOMPOSITION PAYLOAD:")
    print("="*60)
    
    if payload_str:
        try:
            parsed_payload = json.loads(payload_str)
            print(json.dumps(parsed_payload, indent=2))
        except json.JSONDecodeError:
             print(payload_str)
    else:
        print("[!] No data returned. Did the tensor annihilate itself?")
        
    print("="*60)
    print("[*] Note: Standard Earth Strassen requires 49 nodes.")
    print("[*] Alien Tensor Rank dynamically bounds 4x4 at exactly 26 nodes.")

if __name__ == "__main__":
    main()
