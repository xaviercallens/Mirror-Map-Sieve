with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

replacements = {
    'α': 'alpha',
    'β': 'beta',
    'γ': 'gamma',
    'δ': 'delta',
    'ε': 'epsilon',
    'ζ': 'zeta',
    'η': 'eta',
    'θ': 'theta',
    'ι': 'iota',
    'κ': 'kappa',
    'λ': 'lambda',
    'μ': 'mu',
    'ν': 'nu',
    'ξ': 'xi',
    'ο': 'omicron',
    'π': 'pi',
    'ρ': 'rho',
    'σ': 'sigma',
    'τ': 'tau',
    'υ': 'upsilon',
    'φ': 'phi',
    'χ': 'chi',
    'ψ': 'psi',
    'ω': 'omega',
    'Γ': 'Gamma',
    'Δ': 'Delta',
    'Θ': 'Theta',
    'Λ': 'Lambda',
    'Ξ': 'Xi',
    'Π': 'Pi',
    'Σ': 'Sigma',
    'Υ': 'Upsilon',
    'Φ': 'Phi',
    'Ψ': 'Psi',
    'Ω': 'Omega',
}

for k, v in replacements.items():
    content = content.replace(k, v)

# remove any remaining non-ascii char to guarantee compilation
content = ''.join(char if ord(char) < 128 else '' for char in content)

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
