import re
import os

with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if r"\includegraphics" in line:
        # Extract filename
        match = re.search(r'\\includegraphics.*?\{(.*?)\}', line)
        if match:
            filename = match.group(1)
            # if not exist, just skip
            if not os.path.exists(filename) and not os.path.exists(f"images/{filename}") and not os.path.exists(f"output/{filename}"):
                print(f"Removing missing image: {filename}")
                continue
    new_lines.append(line)

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.writelines(new_lines)
