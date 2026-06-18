with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

content = content.replace(r'\newtheorem{example}[theorem]{Example}', r'\newtheorem{example}[theorem]{Example}' + '\n' + r'\newtheorem{axiom}[theorem]{Axiom}' + '\n' + r'\newtheorem{corollary}[theorem]{Corollary}' + '\n' + r'\newtheorem{lemma}[theorem]{Lemma}')

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
