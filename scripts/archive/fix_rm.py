with open("output/rm_monograph.tex", "r") as f:
    content = f.read()

content = content.replace("Formal Bounds (Euler & Pythagore)", r"Formal Bounds (Euler \& Pythagore)")

with open("output/rm_monograph.tex", "w") as f:
    f.write(content)
