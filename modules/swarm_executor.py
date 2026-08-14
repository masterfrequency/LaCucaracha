#!/usr/bin/env python3
"""
SWARM_EXECUTOR — Parallel Batch Executor
Port of swarm.ts from RedLinux v4.1
Batch-fingerprint targets using concurrent.futures with decoy traffic.

by 🇭🇷PhonkAlphabet
"""

import logging
import time
import socket
import sqlite3
import os
import random
import threading
from typing import List, Dict, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor

log = logging.getLogger("swarm_executor")

DB_PATH = os.environ.get("WORM_DB_PATH", "/opt/hermes/worm_mesh_v5.db")

# ─── PROBES ───
def _tcp_banner(ip: str, port: int, timeout: float = 3.0) -> Optional[str]:
    """TCP banner grab for service fingerprinting."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.sendall(b"\r\n")
        banner = s.recv(256).strip()
        s.close()
        return banner.decode("utf-8", errors="replace")[:128] if banner else None
    except Exception:
        return None


def _icmp_ping(ip: str, timeout: float = 2.0) -> bool:
    """ICMP echo check."""
    try:
        # Uses ping command — root not required for basic check
        import subprocess
        r = subprocess.run(
            ["ping", "-c", "1", "-W", str(int(timeout)), ip],
            capture_output=True, timeout=timeout + 1
        )
        return r.returncode == 0
    except Exception:
        return False


def _http_check(ip: str, port: int, timeout: float = 4.0) -> Optional[str]:
    """HTTP GET to grab server header."""
    try:
        import urllib.request
        req = urllib.request.Request(f"http://{ip}:{port}/", method="GET")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        resp = urllib.request.urlopen(req, timeout=timeout)
        server = resp.headers.get("Server", "")
        return server[:128] if server else None
    except Exception:
        return None


def _tcp_connect(ip: str, port: int, timeout: float = 2.0) -> bool:
    """Simple TCP connect check."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.close()
        return True
    except Exception:
        return False


SERVICE_PORTS = {
    "SSH": [22, 2222],
    "HTTP": [80, 443, 8080, 8443, 3000, 5000, 7000, 8888, 9443, 9999],
    "TELNET": [23],
    "TR069": [7547],
    "MYSQL": [3306],
    "POSTGRES": [5432],
    "MONGO": [27017],
    "REDIS": [6379],
    "SMB": [445, 139],
    "RDP": [3389],
    "VNC": [5900],
    "ELASTIC": [9200],
    "KAFKA": [9092],
    "MSSQL": [1433],
    "ORACLE": [1521],
}

SERVICE_PROBES = {
    "SSH": lambda ip, p, t: _tcp_banner(ip, p, t) if _tcp_connect(ip, p, t) else None,
    "HTTP": lambda ip, p, t: _http_check(ip, p, t),
    "TELNET": lambda ip, p, t: _tcp_banner(ip, p, t),
}


# ─── SWARM NODE ───
class SwarmNode:
    """A single swarm worker that probes one IP:port and stores results."""

    def __init__(self, node_id: str, provider: str, timeout: float = 3.0):
        self.id = node_id
        self.provider = provider
        self.timeout = timeout
        self.status = "pending"
        self.findings = 0
        self.error: Optional[str] = None
        self.result: Optional[Dict] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def execute(self, ip: str, port: int) -> Dict:
        """Run probe and return structured result."""
        self.status = "executing"
        self.start_time = time.time()
        result = {"ip": ip, "port": port, "banner": None, "alive": False,
                  "service": None, "http_server": None, "ttl": 0}

        try:
            # TCP check
            result["alive"] = _tcp_connect(ip, port, self.timeout)
            if not result["alive"]:
                self.status = "completed"
                self.end_time = time.time()
                self.result = result
                return result

            # Service detection
            for svc, ports in SERVICE_PORTS.items():
                if port in ports:
                    result["service"] = svc
                    break

            # Banner grab
            if result["service"] == "SSH":
                banner = _tcp_banner(ip, port, self.timeout)
                if banner:
                    result["banner"] = banner
                    self.findings = 1
            elif result["service"] == "HTTP":
                server = _http_check(ip, port, self.timeout + 1)
                if server:
                    result["http_server"] = server
                    result["banner"] = server
                    self.findings = 1
            else:
                banner = _tcp_banner(ip, port, self.timeout)
                if banner:
                    result["banner"] = banner
                    self.findings = 1

            self.status = "completed"
        except Exception as e:
            self.status = "failed"
            self.error = str(e)[:120]

        self.end_time = time.time()
        self.result = result
        return result


# ─── SWARM ORCHESTRATOR ───
class SwarmOrchestrator:
    """Orchestrate parallel swarm nodes for batch fingerprinting.
       Port of swarm.ts SwarmOrchestrator."""

    PROVIDERS = ["tcp_probe", "banner_grab", "http_probe"]
    MAX_PARALLEL = 25  # Nodes per batch

    def __init__(self, max_workers: int = 50, timeout: float = 3.0,
                 db_path: str = DB_PATH):
        self.max_workers = max_workers
        self.timeout = timeout
        self.db_path = db_path
        self._lock = threading.Lock()

    def _db_update(self, result: Dict):
        """Write probe result back to the worm DB."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            ip = result.get("ip")
            port = result.get("port")
            banner = result.get("banner", "")
            svc = result.get("service", "")
            http_srv = result.get("http_server", "")
            alive = 1 if result.get("alive") else 0

            conn.execute(
                """UPDATE targets SET
                   fp_banner=COALESCE(NULLIF(?, ''), fp_banner),
                   fp_service=COALESCE(NULLIF(?, ''), fp_service),
                   fp_http_server=COALESCE(NULLIF(?, ''), fp_http_server),
                   icmp_alive=MAX(icmp_alive, ?),
                   last_seen=datetime('now')
                   WHERE ip=? AND port=?""",
                (banner, svc, http_srv, alive, ip, port)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.error(f"DB update error: {e}")

    def fingerprint_single(self, ip: str, port: int) -> Optional[Dict]:
        """Fingerprint a single target."""
        node = SwarmNode(f"node-{ip}:{port}", "tcp_probe", self.timeout)
        result = node.execute(ip, port)
        if result.get("alive") or result.get("banner"):
            self._db_update(result)
        return result

    def fingerprint_batch(self, targets: List[tuple],
                          batch_callback: Optional[Callable] = None) -> List[Dict]:
        """Process targets in parallel batches.
           Port of swarm.ts executeSwarmBatch()."""
        results = []
        total = len(targets)

        for i in range(0, total, self.MAX_PARALLEL):
            batch = targets[i:i + self.MAX_PARALLEL]
            batch_results = []

            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(batch))) as exe:
                nodes = [SwarmNode(f"swarm-{j}", random.choice(self.PROVIDERS), self.timeout)
                         for j in range(len(batch))]
                futures = {}
                for node, (ip, port) in zip(nodes, batch):
                    futures[exe.submit(node.execute, ip, port)] = (ip, port, node)

                for future in as_completed(futures):
                    ip, port, node = futures[future]
                    try:
                        r = future.result()
                        if r.get("alive") or r.get("banner"):
                            self._db_update(r)
                            batch_results.append(r)
                    except Exception as e:
                        log.error(f"Node failed on {ip}:{port}: {e}")

            results.extend(batch_results)

            pct = min(100, int((i + len(batch)) / total * 100))
            if batch_callback:
                batch_callback(i + len(batch), total, len(batch_results))
            log.info(f"Swarm batch: {i + len(batch)}/{total} ({pct}%%) — {len(batch_results)} alive")

        return results

    def fingerprint_db_backlog(self, limit: int = 5000,
                                batch_callback: Optional[Callable] = None) -> List[Dict]:
        """Fetch unfingerprinted targets from DB and fingerprint them.
           Targets the 148k unfingerprinted backlog."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT ip, port FROM targets
                   WHERE (fp_service IS NULL OR fp_service = '' OR fp_service = 'unknown')
                     AND tcp_open=1
                   ORDER BY first_seen ASC LIMIT ?""",
                (limit,)
            ).fetchall()
            conn.close()
            targets = [(r["ip"], r["port"]) for r in rows]
            if not targets:
                log.info("No unfingerprinted targets in DB")
                return []
            log.info(f"Swarm assigned {len(targets)} targets from backlog")
            return self.fingerprint_batch(targets, batch_callback)
        except Exception as e:
            log.error(f"DB backlog query failed: {e}")
            return []


# ─── CLI ───
if __name__ == "__main__":
    import sys, json
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    swarm = SwarmOrchestrator()

    if len(sys.argv) > 1 and sys.argv[1] == "backlog":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
        def _cb(done, total, alive):
            if done % 100 == 0:
                print(f"  {done}/{total} — {alive} alive so far")
        results = swarm.fingerprint_db_backlog(limit, _cb)
        print(json.dumps({"total": len(results), "alive": len([r for r in results if r.get("alive")])}))
    elif len(sys.argv) > 2:
        ip = sys.argv[1]
        port = int(sys.argv[2])
        result = swarm.fingerprint_single(ip, port)
        print(json.dumps(result, indent=2))
    else:
        print(f"Usage: {sys.argv[0]} <ip> <port> | backlog [limit]")
