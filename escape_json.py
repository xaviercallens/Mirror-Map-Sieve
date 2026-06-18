import re

with open("output/hypatia_aeronautics_monograph.tex", "r") as f:
    content = f.read()

prefix = r"\chapter{Mistral Peer Review \& Remaining Work}"
if prefix in content:
    pre, post = content.split(prefix, 1)
    
    # Escape special characters in the 'post' section
    post = post.replace("\\\\", "TMP_BACKSLASH") # Protect existing backslashes? Actually JSON has actual \
    
    # Let's just do targeted replaces.
    # We want to replace _ with \_ unless it's already \_
    post = re.sub(r'(?<!\\)_', r'\_', post)
    # Replace $ with \$ unless it's already \$
    post = re.sub(r'(?<!\\)\$', r'\$', post)
    # Replace & with \& unless it's already \&
    post = re.sub(r'(?<!\\)&', r'\&', post)
    
    # Let's write it back
    with open("output/hypatia_aeronautics_monograph.tex", "w") as f:
        f.write(pre + prefix + post)

