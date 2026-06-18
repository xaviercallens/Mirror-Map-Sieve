import re

with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

content = content.replace(r'\end{equation', r'\end{equation}')
content = content.replace(r'\end{align', r'\end{align}')
content = content.replace(r'\begin{equation', r'\begin{equation}')
content = content.replace(r'\begin{align', r'\begin{align}')
# Also fix any multiple }} just in case it was correct
content = content.replace(r'\end{equation}}', r'\end{equation}')
content = content.replace(r'\end{align}}', r'\end{align}')
content = content.replace(r'\begin{equation}}', r'\begin{equation}')
content = content.replace(r'\begin{align}}', r'\begin{align}')

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
