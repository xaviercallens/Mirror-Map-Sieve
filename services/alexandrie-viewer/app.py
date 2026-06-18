#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Alexandrie Vault — Private Monograph Viewer with LaTeX Rendering.

Serves monographs stored in the Alexandrie vault's private room on GCS,
with KaTeX-based LaTeX rendering for .tex files and PDF embedding for .pdf files.

Deployed on Cloud Run with IAM-based authentication.

Patent: US-PAT-PEND-2026-0525
"""
from __future__ import annotations

import html
import os
import re
import time
from pathlib import Path

from flask import Flask, Response, abort, redirect, render_template_string, request
from google.cloud import storage

app = Flask(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
BUCKET_NAME = os.environ.get("AGORA_VAULT_BUCKET", "socrateai-alexandrie-vault")
PRIVATE_PREFIX = "private/monographs/"
MONOGRAPHS_PREFIX = "monographs/"
ALLOWED_EXTENSIONS = {".pdf", ".tex", ".html"}

# ── GCS Client ─────────────────────────────────────────────────────────────────
_gcs_client = None
_bucket = None


def get_bucket():
    """Lazily initialize GCS client and bucket."""
    global _gcs_client, _bucket
    if _gcs_client is None:
        _gcs_client = storage.Client()
        _bucket = _gcs_client.bucket(BUCKET_NAME)
    return _bucket


# ── LaTeX to HTML Conversion ──────────────────────────────────────────────────

def tex_to_html(tex_content: str, title: str) -> str:
    """Convert LaTeX source to a KaTeX-rendered HTML page."""
    # Extract preamble info
    author_match = re.search(r"\\author\{([^}]+)\}", tex_content)
    date_match = re.search(r"\\date\{([^}]+)\}", tex_content)
    author = author_match.group(1) if author_match else "Socrate AI Lab"
    date = date_match.group(1) if date_match else ""

    # Extract body content (between \begin{document} and \end{document})
    body_match = re.search(
        r"\\begin\{document\}(.+?)\\end\{document\}",
        tex_content,
        re.DOTALL,
    )
    body = body_match.group(1) if body_match else tex_content

    # Remove \maketitle, \tableofcontents
    body = re.sub(r"\\maketitle", "", body)
    body = re.sub(r"\\tableofcontents", "", body)

    # Convert LaTeX structures to HTML
    # Sections
    body = re.sub(r"\\part\{([^}]+)\}", r'<h1 class="part">\1</h1>', body)
    body = re.sub(r"\\chapter\{([^}]+)\}", r'<h1 class="chapter">\1</h1>', body)
    body = re.sub(r"\\section\{([^}]+)\}", r"<h2>\1</h2>", body)
    body = re.sub(r"\\subsection\{([^}]+)\}", r"<h3>\1</h3>", body)
    body = re.sub(r"\\subsubsection\{([^}]+)\}", r"<h4>\1</h4>", body)

    # Text formatting
    body = re.sub(r"\\textbf\{([^}]+)\}", r"<strong>\1</strong>", body)
    body = re.sub(r"\\textit\{([^}]+)\}", r"<em>\1</em>", body)
    body = re.sub(r"\\emph\{([^}]+)\}", r"<em>\1</em>", body)
    body = re.sub(r"\\texttt\{([^}]+)\}", r"<code>\1</code>", body)
    body = re.sub(r"\\url\{([^}]+)\}", r'<a href="\1">\1</a>', body)

    # Math environments → KaTeX delimiters
    body = re.sub(r"\$\$(.+?)\$\$", r'<div class="math-display">\\[\1\\]</div>', body, flags=re.DOTALL)
    body = re.sub(r"\\begin\{equation\*?\}(.+?)\\end\{equation\*?\}", r'<div class="math-display">\\[\1\\]</div>', body, flags=re.DOTALL)
    body = re.sub(r"\\begin\{align\*?\}(.+?)\\end\{align\*?\}", r'<div class="math-display">\\[\1\\]</div>', body, flags=re.DOTALL)

    # Theorem environments
    for env in ("theorem", "lemma", "definition", "proposition", "corollary", "remark", "proof"):
        label = env.capitalize()
        if env == "proof":
            body = re.sub(
                rf"\\begin\{{{env}\}}(.+?)\\end\{{{env}\}}",
                rf'<div class="env-{env}"><strong>{label}.</strong>\1 <span class="qed">∎</span></div>',
                body, flags=re.DOTALL,
            )
        else:
            body = re.sub(
                rf"\\begin\{{{env}\}}(.+?)\\end\{{{env}\}}",
                rf'<div class="env-{env}"><strong>{label}.</strong>\1</div>',
                body, flags=re.DOTALL,
            )

    # Lists
    body = re.sub(r"\\begin\{itemize\}", "<ul>", body)
    body = re.sub(r"\\end\{itemize\}", "</ul>", body)
    body = re.sub(r"\\begin\{enumerate\}(\[.*?\])?", "<ol>", body)
    body = re.sub(r"\\end\{enumerate\}", "</ol>", body)
    body = re.sub(r"\\item\s*", "<li>", body)

    # Code listings
    body = re.sub(
        r"\\begin\{lstlisting\}(\[.*?\])?\s*(.+?)\\end\{lstlisting\}",
        r'<pre class="code-block"><code>\2</code></pre>',
        body, flags=re.DOTALL,
    )
    body = re.sub(
        r"\\begin\{verbatim\}(.+?)\\end\{verbatim\}",
        r'<pre class="code-block"><code>\1</code></pre>',
        body, flags=re.DOTALL,
    )

    # tcolorbox
    body = re.sub(
        r"\\begin\{tcolorbox\}(\[.*?\])?\s*(.+?)\\end\{tcolorbox\}",
        r'<div class="tcolorbox">\2</div>',
        body, flags=re.DOTALL,
    )

    # Tables (basic)
    body = re.sub(r"\\begin\{tabular\}\{[^}]+\}", '<table class="latex-table">', body)
    body = re.sub(r"\\end\{tabular\}", "</table>", body)
    body = re.sub(r"\\begin\{longtable\}\{[^}]+\}", '<table class="latex-table">', body)
    body = re.sub(r"\\end\{longtable\}", "</table>", body)
    body = re.sub(r"\\hline", "", body)
    body = re.sub(r"\\toprule|\\midrule|\\bottomrule", "", body)

    # Table rows
    def convert_table_rows(text):
        lines = text.split("\n")
        result = []
        for line in lines:
            if "&" in line and "\\\\" in line:
                cells = line.replace("\\\\", "").split("&")
                row = "<tr>" + "".join(f"<td>{c.strip()}</td>" for c in cells) + "</tr>"
                result.append(row)
            else:
                result.append(line)
        return "\n".join(result)
    body = convert_table_rows(body)

    # Figures (placeholder)
    body = re.sub(
        r"\\begin\{figure\}(\[.*?\])?\s*(.+?)\\end\{figure\}",
        r'<figure class="latex-figure">\2</figure>',
        body, flags=re.DOTALL,
    )
    body = re.sub(r"\\includegraphics(\[.*?\])?\{([^}]+)\}", r'<img src="/static/\2" alt="Figure">', body)
    body = re.sub(r"\\caption\{([^}]+)\}", r"<figcaption>\1</figcaption>", body)

    # Clean up remaining LaTeX commands
    body = re.sub(r"\\label\{[^}]+\}", "", body)
    body = re.sub(r"\\ref\{[^}]+\}", "[ref]", body)
    body = re.sub(r"\\cite\{([^}]+)\}", r"[\1]", body)
    body = re.sub(r"\\footnote\{([^}]+)\}", r'<sup class="footnote">\1</sup>', body)
    body = re.sub(r"\\noindent\s*", "", body)
    body = re.sub(r"\\bigskip|\\medskip|\\smallskip", "<br>", body)
    body = re.sub(r"\\newpage|\\clearpage", '<hr class="page-break">', body)
    body = re.sub(r"\\vspace\{[^}]+\}", "", body)
    body = re.sub(r"\\hspace\{[^}]+\}", "", body)

    # Paragraphs
    body = re.sub(r"\n\n+", "</p><p>", body)
    body = f"<p>{body}</p>"

    return body, author, date


# ── HTML Templates ─────────────────────────────────────────────────────────────

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alexandrie Vault — Private Monograph Library</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@300;400&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f0f13;
            --surface: #1a1a22;
            --surface-hover: #22222e;
            --border: #2a2a38;
            --text: #e4e4ed;
            --text-muted: #8888a0;
            --accent: #7c6cf0;
            --accent-glow: rgba(124, 108, 240, 0.15);
            --gold: #d4a853;
            --pdf-badge: #e74c3c;
            --tex-badge: #27ae60;
            --html-badge: #3498db;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-bottom: 1px solid var(--border);
            padding: 2rem 0;
            text-align: center;
        }
        .header h1 {
            font-family: 'EB Garamond', Georgia, serif;
            font-size: 2.4rem;
            font-weight: 600;
            background: linear-gradient(135deg, var(--gold), #f0d78c);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.3rem;
        }
        .header .subtitle {
            color: var(--text-muted);
            font-size: 0.95rem;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        .header .patent {
            color: var(--accent);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            margin-top: 0.5rem;
            opacity: 0.7;
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.2rem;
            text-align: center;
        }
        .stat-card .number {
            font-size: 2rem;
            font-weight: 600;
            color: var(--accent);
        }
        .stat-card .label {
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .section-title {
            font-family: 'EB Garamond', serif;
            font-size: 1.5rem;
            color: var(--gold);
            margin: 2rem 0 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }
        .monograph-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 1.2rem;
        }
        .monograph-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            transition: all 0.3s ease;
            text-decoration: none;
            color: var(--text);
            display: block;
            position: relative;
            overflow: hidden;
        }
        .monograph-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent), var(--gold));
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .monograph-card:hover {
            background: var(--surface-hover);
            border-color: var(--accent);
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        }
        .monograph-card:hover::before { opacity: 1; }
        .monograph-card .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.8rem;
        }
        .badge-pdf { background: var(--pdf-badge); color: white; }
        .badge-tex { background: var(--tex-badge); color: white; }
        .badge-html { background: var(--html-badge); color: white; }
        .monograph-card .title {
            font-family: 'EB Garamond', serif;
            font-size: 1.15rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            line-height: 1.3;
        }
        .monograph-card .meta {
            font-size: 0.8rem;
            color: var(--text-muted);
        }
        .monograph-card .size {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--accent);
            margin-top: 0.5rem;
        }
        .footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.8rem;
            border-top: 1px solid var(--border);
            margin-top: 3rem;
        }
        .room-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
            margin-left: 0.5rem;
        }
        .room-private {
            background: rgba(231, 76, 60, 0.15);
            color: #e74c3c;
            border: 1px solid rgba(231, 76, 60, 0.3);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏛️ Alexandrie Vault</h1>
        <div class="subtitle">Private Monograph Library — Socrate AI Lab</div>
        <div class="patent">US-PAT-PEND-2026-0525 · Xavier Callens</div>
    </div>
    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <div class="number">{{ total_count }}</div>
                <div class="label">Monographs</div>
            </div>
            <div class="stat-card">
                <div class="number">{{ pdf_count }}</div>
                <div class="label">PDF Documents</div>
            </div>
            <div class="stat-card">
                <div class="number">{{ tex_count }}</div>
                <div class="label">LaTeX Sources</div>
            </div>
            <div class="stat-card">
                <div class="number">{{ total_size_mb }}</div>
                <div class="label">Total Size (MB)</div>
            </div>
        </div>

        <h2 class="section-title">📄 PDF Monographs</h2>
        <div class="monograph-grid">
            {% for m in pdf_monographs %}
            <a class="monograph-card" href="/view/{{ m.name }}">
                <span class="badge badge-pdf">PDF</span>
                <span class="room-badge room-private">🔒 Private</span>
                <div class="title">{{ m.display_name }}</div>
                <div class="meta">{{ m.updated }}</div>
                <div class="size">{{ m.size_str }}</div>
            </a>
            {% endfor %}
        </div>

        <h2 class="section-title">📝 LaTeX Sources (Rendered)</h2>
        <div class="monograph-grid">
            {% for m in tex_monographs %}
            <a class="monograph-card" href="/view/{{ m.name }}">
                <span class="badge badge-tex">TEX</span>
                <span class="room-badge room-private">🔒 Private</span>
                <div class="title">{{ m.display_name }}</div>
                <div class="meta">{{ m.updated }}</div>
                <div class="size">{{ m.size_str }}</div>
            </a>
            {% endfor %}
        </div>
    </div>
    <div class="footer">
        © 2026 Xavier Callens / Socrate AI Lab · Alexandrie Scientific Key Vault<br>
        <small>Deployed on Google Cloud Run · Authenticated via IAM</small>
    </div>
</body>
</html>"""


VIEWER_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} — Alexandrie Vault</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@300;400&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
        onload="renderMathInElement(document.body, {delimiters: [
            {left: '\\\\[', right: '\\\\]', display: true},
            {left: '\\\\(', right: '\\\\)', display: false},
            {left: '$', right: '$', display: false}
        ]});"></script>
    <style>
        :root {
            --bg: #fafaf8;
            --text: #1a1a1a;
            --accent: #7c6cf0;
            --gold: #b8860b;
            --border: #e0ddd5;
        }
        * { box-sizing: border-box; }
        body {
            font-family: 'EB Garamond', Georgia, serif;
            font-size: 12pt;
            line-height: 1.8;
            color: var(--text);
            background: var(--bg);
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }
        .nav-bar {
            position: sticky;
            top: 0;
            background: rgba(250, 250, 248, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--border);
            padding: 0.8rem 0;
            margin-bottom: 2rem;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .nav-bar a {
            color: var(--accent);
            text-decoration: none;
            font-family: 'Inter', sans-serif;
            font-size: 0.9rem;
        }
        .nav-bar .room {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: #e74c3c;
            padding: 2px 8px;
            border: 1px solid rgba(231,76,60,0.3);
            border-radius: 12px;
        }
        h1 { font-size: 2rem; color: var(--gold); margin: 1.5rem 0 0.5rem; border-bottom: 2px solid var(--border); padding-bottom: 0.5rem; }
        h1.part { font-size: 2.4rem; text-align: center; margin: 3rem 0 1rem; }
        h1.chapter { font-size: 2.2rem; }
        h2 { font-size: 1.5rem; color: #333; margin: 1.5rem 0 0.8rem; }
        h3 { font-size: 1.2rem; color: #555; margin: 1rem 0 0.5rem; }
        h4 { font-size: 1.05rem; color: #666; }
        .math-display { text-align: center; margin: 1.5rem 0; overflow-x: auto; }
        .env-theorem, .env-lemma, .env-definition, .env-proposition, .env-corollary {
            background: #f5f0ff;
            border-left: 4px solid var(--accent);
            padding: 1rem 1.2rem;
            margin: 1.2rem 0;
            border-radius: 0 8px 8px 0;
        }
        .env-proof {
            background: #f9f9f5;
            border-left: 4px solid var(--gold);
            padding: 1rem 1.2rem;
            margin: 1.2rem 0;
            border-radius: 0 8px 8px 0;
        }
        .env-remark {
            background: #f0f7ff;
            border-left: 4px solid #3498db;
            padding: 1rem 1.2rem;
            margin: 1.2rem 0;
        }
        .qed { float: right; }
        .code-block {
            background: #1e1e2e;
            color: #cdd6f4;
            padding: 1rem 1.2rem;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            line-height: 1.5;
            margin: 1rem 0;
        }
        .tcolorbox {
            background: linear-gradient(135deg, #f8f6ff, #f0eeff);
            border: 1px solid #d4d0f0;
            border-radius: 8px;
            padding: 1.2rem;
            margin: 1rem 0;
        }
        .latex-table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }
        .latex-table td, .latex-table th {
            border: 1px solid var(--border);
            padding: 0.5rem 0.8rem;
            text-align: left;
        }
        .latex-table tr:nth-child(even) { background: #f5f5f0; }
        .latex-figure { text-align: center; margin: 1.5rem 0; }
        .latex-figure img { max-width: 100%; border-radius: 4px; }
        figcaption { font-style: italic; color: #666; margin-top: 0.5rem; font-size: 0.9rem; }
        .footnote { font-size: 0.8rem; color: var(--accent); }
        .page-break { border: none; border-top: 2px dashed var(--border); margin: 2rem 0; }
        .author-info { color: #666; font-style: italic; margin-bottom: 2rem; }
        @media print {
            .nav-bar { display: none; }
            body { max-width: none; }
        }
    </style>
</head>
<body>
    <div class="nav-bar">
        <a href="/">← Back to Library</a>
        <span class="room">🔒 PRIVATE ROOM</span>
    </div>
    <h1>{{ title }}</h1>
    <div class="author-info">{{ author }}{% if date %} · {{ date }}{% endif %}</div>
    {{ content | safe }}
</body>
</html>"""


PDF_VIEWER_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{{ title }} — Alexandrie Vault</title>
    <style>
        * { margin: 0; padding: 0; }
        body { background: #1a1a22; }
        .nav-bar {
            background: #0f0f13;
            padding: 0.8rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #2a2a38;
        }
        .nav-bar a { color: #7c6cf0; text-decoration: none; font-family: sans-serif; font-size: 0.9rem; }
        .nav-bar .title { color: #d4a853; font-family: Georgia, serif; font-size: 1.1rem; }
        .nav-bar .room { color: #e74c3c; font-family: monospace; font-size: 0.75rem; }
        iframe, embed {
            width: 100%;
            height: calc(100vh - 50px);
            border: none;
        }
    </style>
</head>
<body>
    <div class="nav-bar">
        <a href="/">← Back to Library</a>
        <span class="title">{{ title }}</span>
        <span class="room">🔒 PRIVATE</span>
    </div>
    <embed src="/raw/{{ filename }}" type="application/pdf" width="100%" height="100%">
</body>
</html>"""


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """List all monographs in the private room."""
    bucket = get_bucket()
    monographs = []

    for prefix in (PRIVATE_PREFIX, MONOGRAPHS_PREFIX):
        blobs = bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            ext = Path(blob.name).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            name = blob.name
            display = Path(blob.name).stem.replace("_", " ").replace("-", " ").title()
            size = blob.size or 0
            updated = blob.updated.strftime("%Y-%m-%d %H:%M") if blob.updated else ""
            monographs.append({
                "name": name,
                "display_name": display,
                "ext": ext,
                "size": size,
                "size_str": f"{size / 1024:.0f} KB" if size < 1_000_000 else f"{size / 1_000_000:.1f} MB",
                "updated": updated,
            })

    # Deduplicate by stem (prefer private room)
    seen = {}
    for m in monographs:
        stem = Path(m["name"]).stem
        if stem not in seen or PRIVATE_PREFIX in m["name"]:
            seen[stem] = m
    monographs = sorted(seen.values(), key=lambda x: x["updated"], reverse=True)

    pdf_monographs = [m for m in monographs if m["ext"] == ".pdf"]
    tex_monographs = [m for m in monographs if m["ext"] == ".tex"]
    total_size = sum(m["size"] for m in monographs)

    return render_template_string(
        INDEX_TEMPLATE,
        pdf_monographs=pdf_monographs,
        tex_monographs=tex_monographs,
        total_count=len(monographs),
        pdf_count=len(pdf_monographs),
        tex_count=len(tex_monographs),
        total_size_mb=f"{total_size / 1_000_000:.1f}",
    )


@app.route("/view/<path:blob_name>")
def view(blob_name: str):
    """View a monograph — renders TeX with KaTeX, embeds PDF."""
    bucket = get_bucket()
    blob = bucket.blob(blob_name)

    if not blob.exists():
        abort(404, f"Monograph not found: {blob_name}")

    ext = Path(blob_name).suffix.lower()
    display_name = Path(blob_name).stem.replace("_", " ").replace("-", " ").title()

    if ext == ".tex":
        content = blob.download_as_text(encoding="utf-8")
        body_html, author, date = tex_to_html(content, display_name)
        return render_template_string(
            VIEWER_TEMPLATE,
            title=display_name,
            author=author,
            date=date,
            content=body_html,
        )
    elif ext == ".pdf":
        return render_template_string(
            PDF_VIEWER_TEMPLATE,
            title=display_name,
            filename=blob_name,
        )
    else:
        abort(400, f"Unsupported file type: {ext}")


@app.route("/raw/<path:blob_name>")
def raw(blob_name: str):
    """Serve raw file content from GCS."""
    bucket = get_bucket()
    blob = bucket.blob(blob_name)

    if not blob.exists():
        abort(404)

    ext = Path(blob_name).suffix.lower()
    content = blob.download_as_bytes()

    content_type = {
        ".pdf": "application/pdf",
        ".tex": "text/plain; charset=utf-8",
        ".html": "text/html; charset=utf-8",
    }.get(ext, "application/octet-stream")

    return Response(content, content_type=content_type)


@app.route("/health")
def health():
    return {"status": "healthy", "service": "alexandrie-viewer"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
