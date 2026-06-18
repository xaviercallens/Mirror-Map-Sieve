import os
import re
import subprocess
from pathlib import Path
from alexandrie.hub import AlexandrieHub

def escape_latex(text: str) -> str:
    """Escapes special LaTeX characters in plain text."""
    escape_chars = {
        '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_',
        '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\^{}', '\\': r'\textbackslash{}'
    }
    return ''.join(escape_chars.get(c, c) for c in text)

def extract_conjecture_and_formalization(content: str):
    """Simple extraction of Lean docstrings and main code."""
    # Find the main docstring (usually at the top or before the main theorem)
    # Lean docstrings look like /-- ... -/
    docstring_match = re.search(r'/--\s*(.*?)\s*-/', content, re.DOTALL)
    docstring = docstring_match.group(1) if docstring_match else "No specific mathematical conjecture documentation found in the source code."
    
    # Clean up docstring for LaTeX
    # If the docstring contains markdown math ($$ ... $$ or $ ... $), we should try to preserve it or let LaTeX handle it
    # We won't heavily parse the markdown, just replace $$ with \[ \] and $ with $
    docstring = re.sub(r'\$\$(.*?)\$\$', r'\\[\1\\]', docstring, flags=re.DOTALL)
    # We shouldn't escape everything if it has math, but it's tricky.
    # Let's just wrap the docstring in verbatim if we can't parse it well, but it's meant to be read.
    # Actually, if we just put it in a verbatim block it's safe. But mathematicians want nice math!
    # Let's do a simple replace of markdown math.
    
    return docstring, content

def generate_tex(name: str, status: str, content: str) -> str:
    docstring, _ = extract_conjecture_and_formalization(content)
    
    # We will use the listings package to format the Lean code.
    tex_template = r"""\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath, amsthm, amssymb}
\usepackage{fontspec}
\usepackage{unicode-math}
\setmainfont{DejaVu Serif}
\usepackage{geometry}
\geometry{margin=1in}
\usepackage{listings}
\usepackage{xcolor}
\usepackage{hyperref}

\definecolor{codegreen}{rgb}{0,0.6,0}
\definecolor{codegray}{rgb}{0.5,0.5,0.5}
\definecolor{codepurple}{rgb}{0.58,0,0.82}
\definecolor{backcolour}{rgb}{0.98,0.98,0.95}

\lstdefinestyle{mystyle}{
    backgroundcolor=\color{backcolour},   
    commentstyle=\color{codegreen},
    keywordstyle=\color{blue},
    numberstyle=\tiny\color{codegray},
    stringstyle=\color{codepurple},
    basicstyle=\ttfamily\footnotesize,
    breakatwhitespace=false,         
    breaklines=true,                 
    captionpos=b,                    
    keepspaces=true,                 
    numbers=left,                    
    numbersep=5pt,                  
    showspaces=false,                
    showstringspaces=false,
    showtabs=false,                  
    tabsize=2
}
\lstset{style=mystyle}

\title{HorizonMath Verification Report: \\ \textbf{<<NAME>>}}
\author{Socrate AI}
\date{\today}

\begin{document}

\maketitle

\begin{abstract}
This document presents the formal verification status and mathematical context for the HorizonMath conjecture \texttt{<<NAME>>}. The problem has been processed by the Socrate AI pipeline.
The final verification status evaluated against the Lean 4 Kernel is: \textbf{<<STATUS>>}.
\end{abstract}

\section{Mathematical Context and Conjecture}
The following documentation was extracted directly from the formalization source:

\begin{verbatim}
<<DOCSTRING>>
\end{verbatim}

\section{Lean 4 Formalization}
The full Lean 4 source code that was compiled against the Kernel and Mathlib is presented below. 
If the status is \texttt{VERIFIED (ROBUST SANITIZED)}, it indicates that the MCTS pipeline generated structural type errors or incomplete proofs which were iteratively isolated and replaced with \texttt{sorry} gaps to ensure the maximal mathematical subset compiled.

\begin{lstlisting}[language=Python]
<<CONTENT>>
\end{lstlisting}

\end{document}
"""
    # Using Python syntax highlighting as a reasonable proxy for Lean in basic listings
    
    tex = tex_template.replace("<<NAME>>", name.replace("_", "\\_"))
    tex = tex.replace("<<STATUS>>", status.replace("_", "\\_"))
    tex = tex.replace("<<DOCSTRING>>", docstring)
    tex = tex.replace("<<CONTENT>>", content)
    
    return tex

def main():
    hub = AlexandrieHub()
    matches = hub.search_vault("v18_Phase2_")
    
    out_dir = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/mathdemonstration")
    out_dir.mkdir(exist_ok=True)
    
    print(f"Found {len(matches)} artifacts. Generating demonstrations...")
    
    for meta in matches:
        status = meta.metrics.get("status", "UNKNOWN")
        if "VERIFIED" not in status:
            continue
            
        ret = hub.retrieve_artifact(meta.id)
        if not ret:
            continue
            
        m, content = ret
        name = m.id.replace("v18_Phase2_", "")
        
        tex_content = generate_tex(name, status, content)
        tex_path = out_dir / f"{name}_demonstration.tex"
        tex_path.write_text(tex_content, encoding="utf-8")
        
        print(f"Compiling PDF for {name}...")
        res = subprocess.run(
            ["lualatex", "-interaction=nonstopmode", f"{name}_demonstration.tex"],
            cwd=str(out_dir),
            capture_output=True,
            text=True,
            errors="replace"
        )
        if res.returncode == 0:
            print(f"  -> Successfully generated {name}_demonstration.pdf")
        else:
            print(f"  -> Warning: lualatex had warnings/errors for {name}, but PDF might still be generated.")
            # Often pdflatex exits with 1 but generates a pdf.

if __name__ == "__main__":
    main()
