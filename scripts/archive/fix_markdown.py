with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip().startswith('#'):
        line = '%' + line
    elif line.strip().startswith('* **') or line.strip().startswith('**'):
        # also comment out obvious markdown bullets if they cause issues, but maybe they don't break LaTeX unless they have weird chars
        pass
    # fix unescaped underscores outside of math mode... wait that's hard to do perfectly with regex
    new_lines.append(line)

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.writelines(new_lines)
