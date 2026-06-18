import re
with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

# Remove markdown code blocks that the LLM might have injected
content = re.sub(r'```latex\n', '', content)
content = re.sub(r'```\n', '', content)

# Replace abstract environment for the book class
content = content.replace(r'\begin{abstract}', r'\section*{Abstract}')
content = content.replace(r'\end{abstract}', '')

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
