import glob
import os

files = glob.glob('agents/**/*.py', recursive=True) + glob.glob('examples/*.py')
for f in files:
    with open(f, 'r') as fd:
        content = fd.read()
    if 'gemini-2.5-pro' in content:
        new_content = content.replace('gemini-2.5-pro', 'gemini-2.5-pro')
        with open(f, 'w') as fd:
            fd.write(new_content)
        print(f"Updated {f}")
