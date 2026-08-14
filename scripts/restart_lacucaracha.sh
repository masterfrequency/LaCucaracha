#!/bin/bash
# La Cucaracha — restart in autonomous Telegram mode
cd "$(dirname "$0")"
exec python3 -u LaCucaracha.py --auto --telegram --subnet 0.0.0.0/0 --batch 100 --hops 5
