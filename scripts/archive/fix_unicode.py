with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

replacements = {
    'ℝ': 'R',
    '∀': 'forall',
    '∃': 'exists',
    '∈': 'in',
    '⊂': 'subset',
    '→': '->',
    '⇒': '=>',
    '⟨': '<',
    '⟩': '>',
    '≤': '<=',
    '≥': '>=',
    '×': 'x',
    '±': '+-',
    '°': 'deg',
    '∑': 'sum',
    '∏': 'prod',
    '∆': 'Delta',
    '∇': 'nabla',
    '∞': 'infinity',
    '≈': '~',
    '≠': '!=',
    '≡': '==',
    '∩': 'intersect',
    '∪': 'union',
}

for k, v in replacements.items():
    content = content.replace(k, v)

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
