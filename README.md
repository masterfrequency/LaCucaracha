# 🐛 LA CUCARACHA

**Autonomous Worm Engine — 16-Phase Predator Killchain**

> ⚡️👾 Single-file Python 3 worm. 15,823 lines. 469 functions. 26 core classes. It survives.

---

## 📦 What It Is

La Cucaracha is a fully autonomous, self-propagating worm written as a monolithic Python 3 engine.
It runs a **16-phase killchain** (recon → fingerprint → exploit → backdoor → tunnel → worm deployment
→ intel → report), coordinates itself across a **peer-to-peer mesh**, switches between **six C2
channels**, mutates payloads per target, exfiltrates intelligence, and reports everything to a
**Telegram fleet bot**.

The main engine is one file: `LaCucaracha.py` (~700 KB, 15,823 lines).

---

## 🗂 File Inventory

| File | Lines | Role |
|---|---|---|
| `LaCucaracha.py` | 15,823 | Core worm engine (classes, phases, mesh, C2, exploits) |
| `la_cucaracha_v5.py` | 1,347 | Smart orchestrator v5 (phase timeouts, smart DB, decision engine) |
| `la_cucaracha_smart.py` | 2,312 | Decision engine + Telnet/Web exploit engines |
| `LaCucaracha_bot.py` | 1,117 | Telegram fleet bot (29 commands) |
| `la_cucaracha_plugin_hub.py` | 685 | C2 DB sync / plugin import hub |
| `worm_worker.py` | 388 | Standalone per-target delivery worker |
| `c2_listener_10001.py` | 347 | C2 listener (reverse shells, heel protocols) |
| `payload_server_10004.py` | 175 | Token-gated payload hub server |
| `integrator.py` | 141 | Wires RedLinux modules into the worm pipeline |

Supporting artifacts: `exploits/` (copy_fail, dirtyfrag, heel binaries + dirtyfrag.c),
`payloads/` (MegaLarva.py, beacons: busybox/dvr/shell/mini, fleet scripts, implant.py),
`la_section_A..G.py` (worm split into concatenated sections).

---

## 🧠 Core Classes (LaCucaracha.py)

### Persistence & OPSEC
- **`Database`** (L568) — SQLite persistence layer: targets, credentials, intel, phase state.
- **`OPSECEngine`** (L976) — anti-analysis: anti-VM, anti-debug, process hiding, fileless execution,
  TOR routing, DNS-over-HTTPS, log scrubbing.

### C2 Channels (L1498–1917)
| Class | Purpose |
|---|---|
| `C2Channel` | Base protocol class |
| `HTTPChannel` | HTTP polling / beacon C2 |
| `DNSChannel` | DNS TXT record exfiltration C2 |
| `ICMPChannel` | Covert ICMP tunnel C2 |
| `WebSocketChannel` | WebSocket C2 |
| `TelegramChannel` | Telegram-based C2 |
| `TorChannel` | Onion service C2 (via stem) |
| `C2MultiChannel` | Round-robin failover across all channels |

### Offensive Engines
- **`ICMPEngine`** (L2083) — 27+ ICMP attack types: ping sweep, covert tunneling, reverse shell over
  ICMP, PMTU cache poison (CVE-2026-0933), ICMP redirect, Smurf amplification, OS fingerprinting,
  steganographic beacons, fragment overlap, TTL sweep, timing channel, RIPv2 injection, and
  CKAB L1–L5 credential-injection methods.
- **`PythonAgentLight`** (L4100) — lightweight implant: reverse shell + 27 CVE payloads + DB exploits.
- **`PostExploitEngine`** (L4367) — keylogger, screen capture, packet sniffer, exfiltration,
  ransomware module, persistence installation.
- **`WormReconEngine`** (L4838) — masscan / nmap / Shodan reconnaissance.
- **`WormExploitEngine`** (L5112) — SSH brute force (60+ credential pairs, DB-supplemented),
  Telnet bypass, MQTT wildcard enumeration, CheckPoint VPN (CVE-2026-50751), SSH username injection
  (CVE-2026-35386), database exploit methods.
- **`CloudExploitEngine`** (L5931) — AWS/Azure/GCP metadata SSRF, Kubelet API, Docker API, S3, RDS.
- **`ARPEngine`** (L6124) — ARP scan / spoof / poison.
- **`DNSPoisonEngine`** (L6241) — DNS cache poisoning.
- **`LateralMoveEngine`** (L6364) — SSH jump, WMI, PsExec lateral movement.
- **`PolymorphicPayloadGenerator`** (L6674) — 4 payload types: python reverse shell, bash reverse
  shell, worm replicator (self-copying), encrypted staged loader (XOR two-stage).
- **`TCPPayloadMutationEngine`** (L6934) — per-target TCP fingerprint mutation for adaptive payloads.
- **`DDoSDivisionEngine`** (L7030) — SYN/UDP/ICMP/HTTP floods + Slowloris.
- **`WormDeploymentEngine`** (L7310) — SSH push, HTTP deploy, self-replication, Docker ICMP bypass
  (CVE-2026-12539), PMTU poison (CVE-2026-0933), persistent beacon scripts.

### Mesh & Autonomy
- **`WormNode`** (L3037) — mesh node: Fernet AES transport, heartbeat, bootstrap, consensus voting.
- **`MeshNetworkEngine`** (L3380) — DHT-style mesh: `PING/PONG`, `NODE_LIST`, `PAYLOAD_SYNC`,
  `CONSENSUS_VOTE`, `STATE_SYNC`, `ANNOUNCE`, `SPLIT_BRAIN_RECOVERY` message types +
  `ConsistentHashRing` for node distribution.
- **`SmartDecisionEngine`** (L8317) — action state machine: DISCOVER / EXPLOIT / REPLICATE / SPREAD /
  TRADE / SLEEP, with consecutive-empty rotation and rate limiting.
- **`WormMeshEngine`** (L8542) — `run_full_cycle()`: recon → exploit → payload → deploy → mesh spread
  → trade & mutate, with autonomous-navigation epoch loop.
- **`WormMaster`** (L10552) — CLI master control.

### Killchain (16-Phase)
- **`KillchainDB`** (L11831) — extended SQLite schema (37 columns per target).
- **`DecisionEngine16`** (L12301) — IF/THEN per-phase decisions with hit/empty streaks, phase
  rotation, latency-adaptive thread factor.
- **`KillchainOrchestrator`** (L14276) — runs the 16-phase pipeline.
- **`TelegramReporter`** (L14888) — batched Telegram reporting (short events, decisions, phase
  reports, epoch summaries, final report).
- **`EnhancedKillchainOrchestrator`** (L15327) — resource-aware epoch loop: CPU/RAM/disk throttling,
  latency sampling, early-exit sustainment mode.

---

## 🔫 The 16-Phase Killchain

```
📡 ICMP → 🔍 TCP → 🖥️ FP → 🧨 CVE → 🌐 WEB → ⚙️ EMBED → 🧟 GENZAI
→ 🏢 ENTERPRISE → 🔑 BRUTE → 🚪 BACKDOOR → 🔌 TUNNEL → 🐛 WORM
→ 🧠 INTEL → 💤 SLEEP → 🔄 CROSSFEED → 📦 REPORT
```

| # | Phase | Function | What it does |
|---|---|---|---|
| 1 | ICMP | `phase_icmp_sweep` | ICMP alive-host sweep across subnets |
| 2 | TCP | `phase_tcp_scan` | masscan port sweep |
| 3 | FP | `phase_fingerprint` / `phase_fp_scan_v2` | Banner grab, OS/TTL detection, **honeypot detection** |
| 4 | CVE | `phase_cve_scan` | Known-vulnerability probing |
| 5 | WEB | `phase_web_exploit` | Credential spray against web panels |
| 6 | EMBED | `phase_embed_exploit` | EmbedXPL-Forge IoT exploitation |
| 7 | GENZAI | `phase_genzai_merge` | Genzai IoT fingerprinting + credential DB merge |
| 8 | ENTERPRISE | `phase_enterprise_exploit` | SMB / MSSQL / RDP / Oracle |
| 9 | BRUTE | `phase_brute_force` | Multi-service credential spray |
| 10 | BACKDOOR | `phase_backdoor` | Persistence installation |
| 11 | TUNNEL | `phase_tunnel` | Reverse tunnel establishment |
| 12 | WORM | `phase_worm_deploy` | Payload propagation to targets |
| 13 | INTEL | `phase_intel` | Data extraction from pwned hosts |
| 14 | SLEEP | `phase_sleep` | Adaptive pause (rate control / evasion) |
| 15 | CROSSFEED | `phase_crossfeed` | Cross-contaminate intel between targets |
| 16 | REPORT | `phase_report` | Comprehensive intel report |

### 🧠 Decision Logic (IF/THEN)
`DecisionEngine16` decides the next phase from results + streaks:
- ICMP found hosts → **TCP**; empty → retry ICMP
- TCP open ports → **FP**; 2× empty → rotate to **ICMP**
- FP done → **CVE**; CVE miss 2× → skip to **WEB**
- WEB pwned → **EMBED** → **GENZAI** → **ENTERPRISE** → **BRUTE**
- Success streaks advance the chain; empty streaks rotate scope

---

## 🕸️ Mesh Networking

Nodes form a self-healing DHT mesh:
- **Bootstrap** via seed peers, **heartbeat** liveness, **ANNOUNCE** on join
- **PAYLOAD_SYNC** — nodes trade worm payloads / mutations
- **CONSENSUS_VOTE** — distributed voting (target priorities, phase decisions)
- **STATE_SYNC** — database state replication between nodes
- **SPLIT_BRAIN_RECOVERY** — re-merge partitioned meshes
- `ConsistentHashRing` assigns targets to nodes; max spread hops configurable (`--hops`)

## 🔌 C2 Channels

Six channels + failover (`C2MultiChannel`): HTTP polling, DNS TXT exfil, ICMP covert tunnel,
WebSocket, Telegram bot, TOR onion. Channel selection is round-robin with automatic failover —
if one channel dies, beacons rotate to the next.

---

## 💥 Exploit Surface

- **SSH brute force** — 60+ built-in credential pairs + DB-supplemented creds, RST-guard (skips
  blocked IPs with backoff)
- **Telnet** — default creds + CVE-2026 bypass login
- **MQTT** — wildcard topic enumeration
- **CheckPoint VPN** — CVE-2026-50751
- **SSH injection** — CVE-2026-35386 username injection
- **Web panels** — credential spray on admin/panel paths
- **Databases** — MySQL, PostgreSQL, MongoDB, Redis, MSSQL, Oracle, SMB
- **Cloud** — AWS/Azure/GCP metadata SSRF, Kubelet, Docker API, S3, RDS
- **Network** — ARP spoof/poison, DNS cache poisoning, RIPv2 injection
- **ICMP** — 27+ attack types incl. PMTU poison (CVE-2026-0933), Smurf, redirect, tunneling
- **Docker** — ICMP-based container escape / bypass (CVE-2026-12539)

Service priority map targets IoT-first: TR-069 (7547), Telnet (23), HTTP/HTTPS (80/443/8080/8443),
web apps (3000/5000/8888/9200), DBs (3306/5432/27017/6379), then SMB/RDP/VNC/SSH.

---

## 📦 Payloads & Propagation

`PolymorphicPayloadGenerator` builds per-target payloads:
1. **python_reverse_shell** — Python one-liner shell
2. **bash_reverse_shell** — bash /dev/tcp shell
3. **worm_replicator** — self-copying payload that re-deploys the worm
4. **encrypted_staged** — XOR two-stage encrypted loader

`TCPPayloadMutationEngine` mutates payload bytes per target TCP fingerprint (`--adaptive-payload`)
to evade signature detection. Deployment vectors: SSH push, HTTP drop, TFTP/wget/curl chains,
self-replication via mesh. The worm pulls itself from the payload hub
(`http://HUB:10004/LaCucaracha.py`) and runs filelessly.

---

## 📡 C2 Infrastructure

| Component | Port | Role |
|---|---|---|
| `payload_server_10004.py` | 10004 | Token-gated payload hub — serves worm + exploit binaries + beacons |
| `c2_listener_10001.py` | 10001 | Reverse shells + heel beacon/exec/report protocols, token validation |
| `LaCucaracha_bot.py` | — | Telegram fleet command bot |

Both servers validate a **rotating daily token** (date-derived, shared-secret HMAC) — requests
without a valid token are rejected.

### 🤖 Telegram Bot — 29 Commands
`start help status stats logs dashboard targets claim top whois ping scan exploit deploy mesh nodes
reset delete aggressive predator harvest autostart autostop exfil broadcast exec shutdown killswitch
telegram`

Fleet ops from chat: launch scans (`/scan <CIDR>`), trigger exploits/deploys, view targets/dashboard,
toggle aggressive & predator modes, harvest credentials, start/stop autopilot, broadcast commands to
all nodes, remote exec, shutdown, and killswitch.

---

## 🛠 CLI Reference (LaCucaracha.py)

```
--scan              Run reconnaissance phase
--deploy            Run full deploy cycle
--serve             Start payload hub server (DEFAULT: enabled)
--mesh              Start mesh node (spread + trade + mutate)
--full-cycle        Run complete autonomous cycle
--auto              FULLY AUTONOMOUS: scan → exploit → replicate/spread → repeat
--replicate         Enable worm self-replication in autonomous mode
--sweep             AUTO SWEEP: iterate /24 subnets across a /16 range
--prefix            First two octets for sweep (e.g. 56.78)
--tg-token / --chat-id / --sweep-report
--status / --stats  Engine statistics
--clean             Reset all database data
--db                Database path (default: /opt/hermes/worm_mesh.db)
--subnet            Target subnet (default 0.0.0.0/0)
--rate              Masscan packet rate (default 10000)
--batch             Exploit batch size
--hops              Max mesh spread hops
--epochs            Max autonomous navigation epochs
--hub-port          Payload hub port (10004)
--callback-ip/--callback-port   Reverse shell callback
--seed-peers        Mesh bootstrap peers
--shodan-key        Shodan API key
--aggressive        Wider scans, deeper fingerprinting, more vectors
--adaptive-payload  Per-target TCP-fingerprint payload mutation
--ddos-on-obstacle  Spawn DDoS nodes on WAF/firewall obstacles
--icmp-tunnel / --reverse-icmp / --icmp-redirect / --icmp-mtu / --icmp-smurf
--icmp-poison-ping / --icmp-rogue-router / --icmp-os-fingerprint / --icmp-address-mask
--pmtu-poison / --pmtu-poison-all    CVE-2026-0933 PMTU cache corruption
--mqtt-enum         MQTT wildcard enumeration
--ssh-inject        SSH username injection (CVE-2026-35386)
```

---

## 🗄 Database Schema (KillchainDB targets)

37 columns tracking per-target state through the entire killchain:
`ip, port, protocol, fp_os, fp_banner, fp_service, fp_ttl, fp_http_server, icmp_alive, tcp_open,
cve_scanned, cve_vulns, web_pwned, embed_pwned, genzai_merged, enterprise_pwned, brute_pwned,
backdoor_installed, tunnel_active, worm_deployed, intel_collected, crossfeed_count,
report_generated, first_seen, last_seen, ...`

---

## 🔁 How It Works — End to End

1. **Boot** — payload hub serves on 10004, C2 listener on 10001, mesh node joins via seed peers.
2. **Recon** — ICMP sweep → masscan TCP → fingerprinting with honeypot detection.
3. **Decide** — `DecisionEngine16` picks the next phase from results and streaks.
4. **Exploit** — CVE probe → web spray → IoT embed → genzai merge → enterprise → brute force.
5. **Backdoor & Tunnel** — persistence + reverse tunnels on every pwned host.
6. **Worm deploy** — payload pulled from hub, executed filelessly; worm replicates itself.
7. **Mesh spread** — new nodes bootstrap, announce, sync payloads, vote consensus, trade mutations.
8. **Intel** — keylog/screen/sniffer/exfil from targets; crossfeed between hosts.
9. **Report** — Telegram batched summaries + epoch reports.
10. **Sustain** — once 50+ worm nodes and 100+ intel logs exist (epoch ≥ 3), breaks to sustainment
    mode instead of burning resources.

Resource-aware: CPU > 85% / RAM > 85% / disk < 100 MB → throttle; high latency → reduced thread
factor. It keeps itself alive and quiet.

---

## ⚠️ Intended Use

Research, authorized red-team operations, adversary simulation, and defensive education.
**Unauthorized use against systems you do not own is illegal.** The author is not responsible for
misuse.

---

⚡️👾 **LA CUCARACHA** — by 🇭🇷 PhonkAlphabet
