with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

content = content.replace(r'\newtheorem{definition}[theorem]{Definition}', r'\newtheorem{definition}[theorem]{Definition}' + '\n' + r'\newtheorem{remark}[theorem]{Remark}' + '\n' + r'\newtheorem{example}[theorem]{Example}')

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
