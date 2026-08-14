#!/usr/bin/env python3
"""Feed targets from chimera target files into LaCucaracha's worm DB."""
import sys, os, re
sys.path.insert(0, '/opt/hermes')

# Import the WormDB class directly from LaCucaracha.py
from LaCucaracha import WormDB

TARGET_FILES = [
    '/opt/chimera/all_targets_consolidated.txt',
    '/opt/chimera/dvr_telnet_targets.txt',
    '/opt/chimera/fleet_targets.txt',
    '/opt/chimera/fresh_targets_consolidated.txt',
]

def parse_ip_port(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return None, None
    # Handle IP:port format
    match = re.match(r'^(\d+\.\d+\.\d+\.\d+):(\d+)$', line)
    if match:
        return match.group(1), int(match.group(2))
    # Handle bare IP
    match = re.match(r'^(\d+\.\d+\.\d+\.\d+)$', line)
    if match:
        return match.group(1), None
    return None, None

def guess_service(port):
    port_map = {
        23: ('telnet', 'tcp'),
        22: ('ssh', 'tcp'),
        80: ('http', 'tcp'),
        443: ('https', 'tcp'),
        8080: ('http-proxy', 'tcp'),
        161: ('snmp', 'udp'),
        502: ('modbus', 'tcp'),
        69: ('tftp', 'udp'),
        445: ('smb', 'tcp'),
        3389: ('rdp', 'tcp'),
        3306: ('mysql', 'tcp'),
        6379: ('redis', 'tcp'),
    }
    return port_map.get(port, ('', 'tcp'))

def main():
    db_path = '/opt/hermes/la_cucaracha.db'
    if not os.path.exists(db_path):
        print(f"ERROR: DB not found at {db_path}")
        sys.exit(1)

    print(f"Connecting to {db_path}")
    db = WormDB(db_path=db_path)
    total = 0
    skipped = 0
    errors = 0

    for fpath in TARGET_FILES:
        if not os.path.exists(fpath):
            print(f"  SKIP: {fpath} not found")
            continue
        count = 0
        with open(fpath) as f:
            for line in f:
                ip, port = parse_ip_port(line)
                if not ip:
                    continue
                # Default port 23 (telnet) if none specified
                if port is None:
                    port = 23
                service, protocol = guess_service(port)
                try:
                    db.add_target(ip, port=int(port), protocol=protocol,
                                  service=service, scan_source='chimera_feed')
                    count += 1
                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"  ERROR: {ip}:{port} -> {e}")
        print(f"  {fpath}: {count} targets injected")
        total += count

    print(f"\nTotal injected: {total}")
    print(f"Total errors: {errors}")
    print(f"DB target count: {db.target_count()}")

if __name__ == '__main__':
    main()
