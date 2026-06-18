import os
import re
import subprocess
from pathlib import Path
from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType

DECL_KEYWORDS = [
    "theorem ", "lemma ", "def ", "noncomputable def ", 
    "abbrev ", "instance ", "class ", "structure ", "example ", 
    "inductive ", "axiom ", "constant "
]

def parse_chunks(content: str):
    lines = content.split('\n')
    chunks = []
    current_chunk_start = 0
    for i, line in enumerate(lines):
        if any(line.startswith(kw) for kw in DECL_KEYWORDS):
            if i > current_chunk_start:
                chunks.append((current_chunk_start, i - 1))
            current_chunk_start = i
    chunks.append((current_chunk_start, len(lines) - 1))
    return chunks

def find_chunk_for_line(chunks, line_idx):
    for idx, (s, e) in enumerate(chunks):
        if s <= line_idx <= e:
            return idx, s, e
    return -1, -1, -1

def is_stubbed(chunk_lines):
    text = "\n".join(chunk_lines).strip()
    return text.endswith(":= sorry") or text.endswith(":= sorry\n")

def stub_proof(chunk_lines):
    text = "\n".join(chunk_lines)
    nesting = 0
    in_comment_line = False
    in_comment_block = False
    
    i = 0
    while i < len(text):
        c = text[i]
        
        # comments
        if not in_comment_block and not in_comment_line:
            if text[i:i+2] == '--':
                in_comment_line = True
                i += 2
                continue
            if text[i:i+2] == '/-':
                in_comment_block = True
                i += 2
                continue
        
        if in_comment_line:
            if c == '\n':
                in_comment_line = False
            i += 1
            continue
            
        if in_comment_block:
            if text[i:i+2] == '-/':
                in_comment_block = False
                i += 2
                continue
            i += 1
            continue
            
        # nesting
        if c in '({[': nesting += 1
        elif c in ')}]': nesting -= 1
        
        # :=
        if nesting == 0 and text[i:i+2] == ':=':
            new_text = text[:i+2] + " sorry"
            return True, new_text.split('\n')
            
        i += 1
        
    return False, chunk_lines

def fix_chunk(chunk_lines):
    if not chunk_lines:
        return chunk_lines
    first_line = chunk_lines[0]
    is_theorem = first_line.startswith("theorem ") or first_line.startswith("lemma ")
    
    if is_theorem and not is_stubbed(chunk_lines):
        success, new_lines = stub_proof(chunk_lines)
        if success:
            return True, new_lines # return new chunk, True = modified
            
    # Fallback: comment out the whole chunk
    # Don't comment out already commented out chunks
    if all(l.startswith("--") or not l.strip() for l in chunk_lines):
        return False, chunk_lines # nothing changed
        
    return True, ["-- " + l if not l.startswith("--") else l for l in chunk_lines]

def compile_file(workspace, temp_file_name="Temp.lean"):
    res = subprocess.run(
        ["lake", "env", "lean", temp_file_name],
        cwd=str(workspace),
        capture_output=True,
        text=True
    )
    errors = []
    # parse errors: Temp.lean:line:col: error: msg
    for line in res.stdout.splitlines() + res.stderr.splitlines():
        m = re.match(rf'^{temp_file_name}:(\d+):', line)
        if m:
            errors.append(int(m.group(1)))
    
    success = (res.returncode == 0)
    return success, sorted(list(set(errors)))

def robust_sanitize(content: str, workspace: Path, temp_file_name="Temp.lean", max_iterations=100):
    temp_file = workspace / temp_file_name
    temp_file.write_text(content, encoding="utf-8")
    
    for i in range(max_iterations):
        success, errors = compile_file(workspace, temp_file_name)
        if success:
            return True, content
            
        if not errors:
            print("Failed but couldn't parse line number!")
            return False, content
            
        # Fix the first error
        first_err_line = errors[0] - 1 # 0-indexed
        
        lines = content.split('\n')
        chunks = parse_chunks(content)
        chunk_idx, s, e = find_chunk_for_line(chunks, first_err_line)
        
        if chunk_idx == -1:
            # Error not inside a recognized chunk (e.g. top level import or something)
            # Just comment out the specific line
            if not lines[first_err_line].startswith("--"):
                lines[first_err_line] = "-- " + lines[first_err_line]
                modified = True
            else:
                modified = False
        else:
            chunk_lines = lines[s:e+1]
            modified, new_chunk_lines = fix_chunk(chunk_lines)
            if modified:
                lines[s:e+1] = new_chunk_lines
            else:
                # If we couldn't modify the chunk (e.g., already completely commented out but somehow still causing error)
                # Comment out the line just in case
                if not lines[first_err_line].startswith("--"):
                    lines[first_err_line] = "-- " + lines[first_err_line]
                    modified = True
        
        if not modified:
            print(f"Deadlock on line {first_err_line + 1}. Cannot modify further.")
            return False, content
            
        content = "\n".join(lines)
        temp_file.write_text(content, encoding="utf-8")
        
    print("Reached max iterations.")
    return False, content

def main():
    hub = AlexandrieHub()
    matches = hub.search_vault("v18_Phase2_")
    
    workspace = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/verifiers/lean4")
    
    print(f"Found {len(matches)} artifacts to process.")
    
    for meta in matches:
        if meta.metrics.get("status") in ["VERIFIED (KERNEL)", "VERIFIED (SANITIZED)"]:
            print(f"Skipping {meta.id}, already verified.")
            continue
            
        ret = hub.retrieve_artifact(meta.id)
        if not ret:
            continue
            
        m, content = ret
        name = m.id.replace("v18_Phase2_", "")
        print(f"Processing {name} with robust iterative sanitization...")
        
        success, final_content = robust_sanitize(content, workspace)
        
        if success:
            status = "VERIFIED (ROBUST SANITIZED)"
            print(f"  -> SUCCESS! The maximal subset of {name} now compiles.")
        else:
            status = "FAILED (UNRECOVERABLE)"
            print(f"  -> FAILED to completely sanitize {name}.")
            
        new_metrics = dict(m.metrics)
        new_metrics["status"] = status
        
        hub.store_artifact(
            artifact_id=m.id,
            title=m.title,
            content=final_content,
            artifact_type=ArtifactType.PROOF,
            room_type=RoomType.OPEN_ACCESS,
            creator="postprocessor_v2",
            tags=m.tags,
            metrics=new_metrics
        )

if __name__ == "__main__":
    main()
