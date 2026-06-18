import re

with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

# Replace \acrshort{...} with just the text inside
content = re.sub(r"\\acrshort\{([^}]+)\}", r"\1", content)
content = re.sub(r"\\acrlong\{([^}]+)\}", r"\1", content)
content = re.sub(r"\\acrfull\{([^}]+)\}", r"\1", content)

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
