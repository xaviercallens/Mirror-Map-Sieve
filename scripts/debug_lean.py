import subprocess
from pathlib import Path
from alexandrie.hub import AlexandrieHub

hub = AlexandrieHub()
matches = hub.search_vault("v18_Phase2_feigenbaum_alpha")
if matches:
    meta = matches[0]
    _, content = hub.retrieve_artifact(meta.id)
    workspace = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/verifiers/lean4")
    temp_file = workspace / "TempDebug.lean"
    temp_file.write_text(content, encoding="utf-8")
    res = subprocess.run(["lake", "env", "lean", "TempDebug.lean"], cwd=str(workspace), capture_output=True, text=True)
    print("STDOUT:")
    print(res.stdout)
    print("STDERR:")
    print(res.stderr)
