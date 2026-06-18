with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    lines = f.readlines()

in_theorem = False
for i, line in enumerate(lines):
    if r'\begin{theorem}' in line:
        in_theorem = True
    elif in_theorem and r'\end{proof}' in line:
        # Check if we missed an \end{theorem}
        # It's highly likely this \end{proof} was meant to be \end{theorem}
        lines[i] = line.replace(r'\end{proof}', r'\end{theorem}')
        in_theorem = False
    elif in_theorem and r'\end{theorem}' in line:
        in_theorem = False

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.writelines(lines)
