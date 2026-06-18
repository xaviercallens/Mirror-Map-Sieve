import os
import sys
from pathlib import Path

def test_no_hardcoded_mocks():
    bad_patterns = [
        "math.sin(time.time()",
        "simulate_nim_output",
        "Hardcoded context extract",
        '"induction": 0.85,',
        "_mock_",
        "simulate_",
        "time.sleep",
    ]
    
    agents_dir = Path("agents")
    violations = []
    
    for path in agents_dir.rglob("*.py"):
        if "test" in str(path):
            continue
        content = path.read_text(encoding="utf-8")
        for pattern in bad_patterns:
            if pattern in content:
                violations.append(f"{path}: found {pattern}")
                
    if violations:
        print("STUB VIOLATIONS FOUND:")
        for v in violations:
            print(f" - {v}")
        sys.exit(1)
        
if __name__ == "__main__":
    test_no_hardcoded_mocks()
