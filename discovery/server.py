#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Discovery Pipeline HTTP Server — Cloud Run Wrapper

Wraps the combinatorial identity discovery pipeline as an
HTTP service for Cloud Run deployment. Supports:

- GET /         → Status page with pipeline info
- GET /run      → Trigger a pipeline run
- GET /results  → Return latest results as JSON
- GET /health   → Health check

This is a lightweight Flask-less server using Python's built-in
http.server module (zero dependencies).
"""

import http.server
import json
import os
import sys
import time
import traceback
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from discovery.pipeline import run_discovery_pipeline


# Cache latest results in memory
_latest_results = None
_last_run_time = None


class DiscoveryHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for the discovery pipeline."""

    def do_GET(self):
        """Route GET requests to appropriate handlers."""
        if self.path == "/" or self.path == "":
            self._handle_status()
        elif self.path == "/run":
            self._handle_run()
        elif self.path == "/results":
            self._handle_results()
        elif self.path == "/health":
            self._handle_health()
        else:
            self.send_error(404, f"Not Found: {self.path}")

    def _handle_status(self):
        """Return pipeline status page."""
        global _latest_results, _last_run_time
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>🔬 Discovery Pipeline — Socrate AI Lab</title>
    <style>
        body {{ font-family: 'Inter', system-ui, sans-serif;
               max-width: 800px; margin: 50px auto; padding: 20px;
               background: #0a0a1a; color: #e0e0e0; }}
        h1 {{ color: #7c3aed; }}
        a {{ color: #818cf8; }}
        .card {{ background: #1a1a2e; border-radius: 12px;
                 padding: 20px; margin: 15px 0;
                 border: 1px solid #2a2a4e; }}
        .stat {{ font-size: 2em; font-weight: bold; color: #7c3aed; }}
        code {{ background: #2a2a4e; padding: 2px 6px; border-radius: 4px; }}
    </style>
</head>
<body>
    <h1>🔬 Combinatorial Identity Discovery Pipeline</h1>
    <p>Socrate AI Lab — Mathematical Discovery Engine v0.1.0</p>

    <div class="card">
        <h2>Pipeline Status</h2>
        <p>Last run: <strong>{_last_run_time or 'Never'}</strong></p>
        <p>Latest results: <strong>{'Available' if _latest_results else 'None'}</strong></p>
        {f'<p class="stat">{_latest_results["summary"]["verified"]} verified, '
         f'{_latest_results["summary"]["potentially_new"]} potentially new</p>'
         if _latest_results else ''}
    </div>

    <div class="card">
        <h2>Actions</h2>
        <p><a href="/run">▶️ Run Pipeline</a> — Generate and test identities</p>
        <p><a href="/results">📊 View Results</a> — JSON output</p>
        <p><a href="/health">💚 Health Check</a></p>
    </div>

    <div class="card">
        <h2>Design Principles</h2>
        <ul>
            <li>Zero sorry, zero axiom — non-negotiable</li>
            <li>Computational falsification before formalization</li>
            <li>Exact ℚ-arithmetic (no floating-point errors)</li>
            <li>Non-triviality checking on every result</li>
        </ul>
    </div>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def _handle_run(self):
        """Trigger a pipeline run and return results."""
        global _latest_results, _last_run_time
        try:
            results = run_discovery_pipeline(max_n=30)
            _latest_results = results
            _last_run_time = time.strftime("%Y-%m-%d %H:%M:%S UTC")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(results, indent=2,
                                         default=str).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            error = {
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
            self.wfile.write(json.dumps(error, indent=2).encode())

    def _handle_results(self):
        """Return latest results."""
        global _latest_results
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        data = _latest_results or {"status": "no results yet",
                                     "hint": "GET /run to trigger"}
        self.wfile.write(json.dumps(data, indent=2, default=str).encode())

    def _handle_health(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "healthy",
                                      "version": "0.1.0"}).encode())


def main():
    port = int(os.environ.get("PORT", 8080))
    server = http.server.HTTPServer(("0.0.0.0", port), DiscoveryHandler)
    print(f"🔬 Discovery Pipeline server starting on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
