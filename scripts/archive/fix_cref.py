import re

with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

# Remove \usepackage{cleveref}
content = content.replace(r"\usepackage{cleveref}", "")

# Replace \cref{...} with Section \ref{...}
content = re.sub(r"\\cref", r"Section~\\ref", content)

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
