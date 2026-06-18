with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

content = content.replace("Topological Routing & Charging Algebra", r"Topological Routing \& Charging Algebra")

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
