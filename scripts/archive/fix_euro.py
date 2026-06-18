with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

content = content.replace(r'\euro', 'EUR ')

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
