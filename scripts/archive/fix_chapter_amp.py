with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

content = content.replace("Simulation Architecture & Pipeline", r"Simulation Architecture \& Pipeline")
content = content.replace("Real-world Implementations & Results", r"Real-world Implementations \& Results")
content = content.replace("Mistral Peer Review & Remaining Work", r"Mistral Peer Review \& Remaining Work")

with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
    f.write(content)
