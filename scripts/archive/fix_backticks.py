import re

with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

def replacer(match):
    text = match.group(1)
    text = text.replace("_", r"\_")
    return r"\texttt{" + text + "}"

# replace `text` with \texttt{text} and escape underscores
content = re.sub(r"`([^`\n]+)`", replacer, content)

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
