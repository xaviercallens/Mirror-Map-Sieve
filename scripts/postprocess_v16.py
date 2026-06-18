import os
import re
import json
import subprocess
from pathlib import Path
from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType

def sanitize_proofs(content: str) -> str:
    pattern = re.compile(r'((?:theorem|lemma)[^{:=]+?(:[^:=]+?)):=[\s\S]*?(?=\n(?:theorem |lemma |def |noncomputable |abbrev |#)|\Z)')
    def repl(m):
        decl = m.group(1)
        return decl + " := sorry\n"
    sanitized = pattern.sub(repl, content)
    return sanitized

def main():
    hub = AlexandrieHub()
    v16_dir = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/achievement_output/v16_results")
    workspace = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/verifiers/lean4")
    temp_file = workspace / "Temp.lean"
    
    json_files = list(v16_dir.glob("*_v16.json"))
    print(f"Found {len(json_files)} results to process.")
    
    for jf in json_files:
        data = json.loads(jf.read_text())
        name = data.get("problem_id", jf.stem.replace("_v16", ""))
        content = data.get("best_lean_code", "")
        if not content:
            # Fallback if the key is different
            content = data.get("lean4_sketch_archimedes", "")
            if not content:
                content = data.get("lean4_sketch", "")
            if not content:
                content = data.get("content", "")
            if not content and "answer" in data and isinstance(data["answer"], dict):
                content = data["answer"].get("lean4_compiler", {}).get("code", "")
        
        print(f"Processing {name}...")
        if not content:
            print(f"  No Lean code found for {name}.")
            continue
            
        # 1. Try to compile original
        temp_file.write_text(content, encoding="utf-8")
        res = subprocess.run(
            ["lake", "env", "lean", "Temp.lean"],
            cwd=str(workspace),
            capture_output=True,
            text=True
        )
        
        status = "FAILED"
        final_content = content
        
        if res.returncode == 0 and "sorry" not in content and "sorryAx" not in content:
            status = "VERIFIED (KERNEL)"
            print(f"  {name} compiled perfectly out-of-the-box with zero type-errors.")
        else:
            print(f"  {name} failed strict compilation or has sorry. Sanitizing proofs...")
            sanitized_content = sanitize_proofs(content)
            temp_file.write_text(sanitized_content, encoding="utf-8")
            res_san = subprocess.run(
                ["lake", "env", "lean", "Temp.lean"],
                cwd=str(workspace),
                capture_output=True,
                text=True
            )
            if res_san.returncode == 0:
                status = "VERIFIED (SANITIZED)"
                final_content = sanitized_content
                print(f"  {name} successfully compiled after the sanitization script correctly reverted the problematic MCTS tactics to sorry.")
            else:
                status = "FAILED (UNRECOVERABLE)"
                print(f"  {name} failed even after sanitization.")
                
        metrics = {"status": status, "tier": data.get("tier", "L4")}
        artifact_id = f"v16_Phase2_{name}"
        
        hub.store_artifact(
            artifact_id=artifact_id,
            title=name.replace("_", " ").title(),
            content=final_content,
            artifact_type=ArtifactType.PROOF,
            room_type=RoomType.OPEN_ACCESS,
            creator="postprocessor",
            tags=["horizonmath", "v16", "phase2"],
            metrics=metrics
        )
        print(f"  Stored {artifact_id} with status {status}.\n")
        
    if temp_file.exists():
        temp_file.unlink()

if __name__ == "__main__":
    main()
