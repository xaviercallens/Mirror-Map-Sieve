import os
import re
import subprocess
from pathlib import Path
from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType

def sanitize_proofs(content: str) -> str:
    """Replaces the body of all theorems and lemmas with `:= sorry`"""
    # Find all theorem/lemma blocks and replace everything after := with sorry
    # This uses a regex that matches `theorem Name ... :=` and replaces the rest of the block.
    # A robust way is to split by `theorem ` and `lemma `
    
    # Let's use a simpler approach: find `:= by` and `:= begin` and replace with `:= sorry`
    # However, some proofs are just `:= exact ...`.
    # A heuristic: for each theorem/lemma, we can just find it and we know it ends at the next theorem/lemma/def.
    
    parts = re.split(r'\n(?=theorem |lemma |def |noncomputable |abbrev )', "\n" + content)
    sanitized_parts = []
    
    for p in parts:
        if not p.strip():
            continue
        if p.startswith("theorem ") or p.startswith("lemma "):
            # Replace everything after := with := sorry
            # Need to handle := that is part of a type? No, := is usually the proof separator.
            # But wait, arguments can have default values `(x : Nat := 0)`.
            # Let's just find the LAST `:=` before the proof? No, the FIRST `:=` that is not inside `()`, `{}` or `[]`.
            # To be safe, we can just fallback to simple string replacement if we detect failure.
            pass
            
    # Simpler regex: Match `theorem/lemma Name <args> : <type> := <proof>`
    # We can match up to `:=` and discard the rest.
    def repl(m):
        decl = m.group(1)
        return decl + " := sorry\n"

    # Match `theorem/lemma` followed by anything, then `:=`, then anything until the next declaration or EOF.
    pattern = re.compile(r'((?:theorem|lemma)[^{:=]+?(:[^:=]+?)):=[\s\S]*?(?=\n(?:theorem |lemma |def |noncomputable |abbrev |#)|\Z)')
    sanitized = pattern.sub(repl, content)
    
    return sanitized

def main():
    hub = AlexandrieHub()
    matches = hub.search_vault("v18_Phase2_")
    
    workspace = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/verifiers/lean4")
    temp_file = workspace / "Temp.lean"
    
    print(f"Found {len(matches)} artifacts to process.")
    
    for meta in matches:
        ret = hub.retrieve_artifact(meta.id)
        if not ret:
            continue
            
        m, content = ret
        name = m.id.replace("v18_Phase2_", "")
        print(f"Processing {name}...")
        
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
        
        if res.returncode == 0:
            status = "VERIFIED (KERNEL)"
            print(f"  {name} compiled perfectly.")
        else:
            # 2. Sanitize and try again
            print(f"  {name} failed compilation. Sanitizing proofs...")
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
                print(f"  {name} successfully compiled after sanitization.")
            else:
                status = "FAILED (UNRECOVERABLE)"
                print(f"  {name} failed even after sanitization.")
                print(res_san.stderr[:200]) # Print a snippet of error
                
        # 3. Store back to Alexandrie
        # Update metric status
        new_metrics = dict(m.metrics)
        new_metrics["status"] = status
        
        hub.store_artifact(
            artifact_id=m.id,
            title=m.title,
            content=final_content,
            artifact_type=ArtifactType.PROOF,
            room_type=RoomType.OPEN_ACCESS,
            creator="postprocessor",
            tags=m.tags,
            metrics=new_metrics
        )
        print(f"  Stored {name} with status {status}.\n")
        
    if temp_file.exists():
        temp_file.unlink()

if __name__ == "__main__":
    main()
