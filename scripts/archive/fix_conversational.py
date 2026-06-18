import re

with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip() == "***" or \
       line.strip().startswith("In this response, I have successfully updated") or \
       re.match(r'^\d+\.\s\*\*', line.strip()) or \
       "Here is the complete modified LaTeX content:" in line or \
       line.strip().startswith("Summary of Chapter"):
        new_lines.append('% ' + line)
    else:
        new_lines.append(line)

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.writelines(new_lines)
