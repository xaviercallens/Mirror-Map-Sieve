with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

prefix = r"\chapter{Mistral Peer Review \& Remaining Work}"
if prefix in content:
    pre, post = content.split(prefix, 1)
    
    # Just append \end{document} if it's not already there
    if r"\end{document}" not in pre:
        pre += "\n\\end{document}\n"
        
    with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
        f.write(pre)
