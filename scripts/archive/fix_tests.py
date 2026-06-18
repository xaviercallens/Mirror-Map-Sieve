import os
import glob

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # We want to replace the mock_reg / asyncio.sleep blocks with real_app.on_event mock
    # And replace the older mocker.patch("asyncio.create_task") if it exists
    
    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if "real_app = FastAPI()" in line:
            new_lines.append(line)
            # Find the indentation
            indent = line.split("real_app")[0]
            new_lines.append(f'{indent}mocker.patch.object(real_app, "on_event", return_value=lambda f: f)')
            i += 1
            continue
            
        if "mock_reg = mocker.patch(\"agents.common.registry.AgentRegistry\")" in line:
            # skip this and the next 2 lines
            i += 3
            continue
            
        new_lines.append(line)
        i += 1
        
    with open(filepath, 'w') as f:
        f.write('\n'.join(new_lines))

for path in ["tests/common/test_a2a.py", "tests/common/test_a2a_pubsub.py", "tests/common/test_a2a_background.py"]:
    fix_file(path)
