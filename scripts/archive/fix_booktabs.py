with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

content = content.replace(r'\usepackage{amsmath, amssymb, amsthm, graphicx, tikz}', r'\usepackage{amsmath, amssymb, amsthm, graphicx, tikz, booktabs}')

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
