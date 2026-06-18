with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

content = content.replace("Euler & Pythagore", r"Euler \& Pythagore")
content = content.replace("Routing & Charging", r"Routing \& Charging")

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
