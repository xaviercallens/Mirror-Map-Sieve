with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

content = content.replace(r'\begin{align}ed}', r'\begin{aligned}')
content = content.replace(r'\end{align}ed}', r'\end{aligned}')
content = content.replace(r'\begin{equation}ed}', r'\begin{equationed}') # Just in case

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
