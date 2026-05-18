#!/usr/bin/env python
"""Start the NeuroAtlas viewer.

Usage:
    uv run scripts/atlas.py          # serves on port 8080
    uv run scripts/atlas.py 9000     # custom port
"""
import http.server
import os
import sys
import webbrowser

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

os.chdir(REPO_ROOT)

handler = http.server.SimpleHTTPRequestHandler
handler.log_message = lambda *a: None  # silence request logs

URL = f"http://localhost:{PORT}/tools/neuro-atlas/"
print(f"NeuroAtlas viewer → {URL}")
print("Stop with Ctrl+C")
try:
    webbrowser.open(URL)
except Exception:
    pass

with http.server.HTTPServer(("", PORT), handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
