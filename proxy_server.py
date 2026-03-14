#!/usr/bin/env python3
"""
proxy_server.py — Local CORS proxy for Polymarket Gamma API

Serves:
  - /gamma/*  → proxies to https://gamma-api.polymarket.com/* with CORS headers
  - /*        → serves static files from the project directory

Usage:
    cd "/Users/erichout/ai child companion"
    python3 proxy_server.py
    
Then open: http://localhost:9090/polymarket-research.html
"""

import os
import subprocess
import http.server
import urllib.request
import urllib.error
import json
from pathlib import Path

# ── Load .env from root folder ─────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

PORT = 9090
GAMMA_BASE = "https://gamma-api.polymarket.com"


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/research":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                query = data.get("query", "")
                is_deep = data.get("deep", False)
                if not query:
                    raise ValueError("Missing query")

                print(f"🕵️  Executing {'Deep' if is_deep else 'Standard'} Research for: {query}")
                
                cmd = ["python3", "polymarket_agent.py", query, "--json"]
                if is_deep:
                    cmd.append("--deep")

                # Run the agent script
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=180 # 3 min timeout for browser-use
                )
                
                # Check for errors
                if result.returncode != 0:
                     self.send_response(500)
                     self.send_header("Access-Control-Allow-Origin", "*")
                     self.end_headers()
                     self.wfile.write(json.dumps({"error": result.stderr or "Agent failed"}).encode())
                     return

                # Send back the raw JSON from the agent
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(result.stdout.strip().encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        
        elif self.path == "/ai/summary":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                # Load GOOGLE_API_KEY from env
                api_key = os.environ.get("GOOGLE_API_KEY")
                if not api_key:
                    raise ValueError("GOOGLE_API_KEY not found in server environment")

                # Proxy the request to Gemini
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={api_key}"
                req = urllib.request.Request(
                    url,
                    data=post_data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    res_data = resp.read()
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(res_data)
            except Exception as e:
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        if self.path.startswith("/gamma"):
            # Strip /gamma prefix and forward to Gamma API
            gamma_path = self.path[len("/gamma"):]
            gamma_url = GAMMA_BASE + gamma_path
            try:
                req = urllib.request.Request(gamma_url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; PolyLens/1.0)",
                    "Accept": "application/json",
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read()
                    content_type = resp.headers.get("Content-Type", "application/json")
                # Send response with CORS headers
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"Upstream error")
            except Exception as e:
                self.send_response(502)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(f"Proxy error: {e}".encode())
        else:
            # Serve static files normally
            super().do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress verbose logs for static files, show API calls
        if "/gamma" in args[0]:
            super().log_message(format, *args)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"🚀  PolyLens dev server running at http://localhost:{PORT}")
    print(f"    Open: http://localhost:{PORT}/polymarket-research.html")
    print(f"    Gamma proxy: http://localhost:{PORT}/gamma/events?...")
    print(f"    Press Ctrl+C to stop.\n")
    with http.server.HTTPServer(("", PORT), ProxyHandler) as server:
        server.serve_forever()
