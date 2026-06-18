with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

content = content.replace(r'\usepackage{amsmath, amssymb, amsthm, graphicx}', r'\usepackage{amsmath, amssymb, amsthm, graphicx, tikz}')

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
