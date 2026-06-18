import re

with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

content = re.sub(r'language=[lL]ean[4]?,?', '', content)

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
