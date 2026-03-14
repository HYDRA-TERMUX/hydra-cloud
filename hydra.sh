#!/data/data/com.termux/files/usr/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║              HYDRA Cloud Server — Termux Launcher        ║
# ║      High-Speed File Upload · Download · Stream          ║
# ╚══════════════════════════════════════════════════════════╝

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

PORT=8888
HYDRA_DIR="$HOME/.hydra"
SERVER_PY="$HYDRA_DIR/hydra_server.py"
UPLOAD_DIR="$HOME/storage/shared/HYDRACloud"
LOG_FILE="$HYDRA_DIR/hydra.log"

info()    { echo -e "${CYAN}  ◈${NC}  $1"; }
ok()      { echo -e "${GREEN}  ✓${NC}  $1"; }
warn()    { echo -e "${YELLOW}  ⚠${NC}  $1"; }
err()     { echo -e "${RED}  ✗${NC}  $1"; }
section() { echo -e "\n${BOLD}${CYAN}  ── $1 ──${NC}\n"; }

banner() {
  clear
  echo -e "${CYAN}${BOLD}"
  echo "  ██╗  ██╗██╗   ██╗██████╗ ██████╗  █████╗ "
  echo "  ██║  ██║╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗"
  echo "  ███████║ ╚████╔╝ ██║  ██║██████╔╝███████║"
  echo "  ██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██╔══██║"
  echo "  ██║  ██║   ██║   ██████╔╝██║  ██║██║  ██║"
  echo "  ╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝"
  echo -e "${NC}${PURPLE}          Cloud Server  ·  Powered by HYDRA${NC}"
  echo ""
}

show_menu() {
  banner
  echo -e "  ${BOLD}Select an option:${NC}\n"
  echo -e "  ${CYAN}1)${NC} ${BOLD}First-time setup${NC}        Install all dependencies"
  echo -e "  ${CYAN}2)${NC} ${BOLD}Start (LAN + localhost)${NC}  Access on WiFi network"
  echo -e "  ${CYAN}3)${NC} ${BOLD}Start localhost only${NC}    This phone only"
  echo -e "  ${CYAN}4)${NC} ${BOLD}Server status${NC}           Check what's running"
  echo -e "  ${CYAN}5)${NC} ${BOLD}Speed test${NC}              Test your WiFi performance"
  echo -e "  ${CYAN}6)${NC} ${BOLD}View logs${NC}               See server activity"
  echo -e "  ${CYAN}7)${NC} ${BOLD}Stop everything${NC}         Kill all HYDRA processes"
  echo -e "  ${CYAN}8)${NC} ${BOLD}Exit${NC}"
  echo ""
  read -p "  Enter choice [1-8]: " CHOICE
  echo ""
}

# ── INSTALL ───────────────────────────────────────────────────
do_install() {
  section "Updating Termux"
  pkg update -y && pkg upgrade -y
  ok "Packages updated"

  section "Installing system packages"
  pkg install -y python wget curl termux-api iproute2
  ok "System packages ready"

  section "Requesting storage permission"
  info "A permission dialog will appear — tap ALLOW"
  termux-setup-storage
  sleep 4

  section "Installing Python dependencies"
  python -m pip install --upgrade pip --break-system-packages -q 2>/dev/null || \
  python -m pip install --upgrade pip -q

  pip install flask flask-cors --break-system-packages -q 2>/dev/null || \
  pip install flask flask-cors -q
  ok "Flask installed"

  section "Setting up HYDRA directory"
  mkdir -p "$HYDRA_DIR"
  mkdir -p "$UPLOAD_DIR"

  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [ -f "$SCRIPT_DIR/hydra_server.py" ]; then
    cp "$SCRIPT_DIR/hydra_server.py" "$SERVER_PY"
    ok "Server app installed from local copy"
  else
    warn "hydra_server.py not found next to this script."
    warn "Place hydra_server.py in the same folder as this script, then re-run setup."
  fi

  section "Configuring Android battery optimization"
  warn "IMPORTANT — do this manually for stable background operation:"
  echo ""
  echo -e "  ${YELLOW}1.${NC} Settings → Apps → Termux → Battery"
  echo -e "  ${YELLOW}2.${NC} Select 'Unrestricted' or 'Don't optimize'"
  echo -e "  ${YELLOW}3.${NC} Also disable 'Auto-start management' restrictions"
  echo ""

  ok "HYDRA setup complete!"
  echo -e "\n  Run this script again and choose ${CYAN}option 2${NC} to start."
}

# ── PRE-START CHECKS ──────────────────────────────────────────
check_ready() {
  if ! command -v python &>/dev/null; then
    err "Python not found. Run option 1 first."; return 1; fi
  if [ ! -f "$SERVER_PY" ]; then
    err "hydra_server.py not found at $SERVER_PY"
    err "Run option 1 (setup) first or copy hydra_server.py to $HYDRA_DIR/"; return 1; fi
  python -c "import flask" 2>/dev/null || {
    err "Flask not installed. Run option 1 first."; return 1; }
  mkdir -p "$UPLOAD_DIR"
  return 0
}

# ── START ENGINE ──────────────────────────────────────────────
start_engine() {
  section "Acquiring wake lock"
  termux-wake-lock 2>/dev/null && ok "Wake lock acquired" || \
    warn "termux-api not found — install for wake lock support"

  section "Launching HYDRA server"
  python "$SERVER_PY" "$PORT" >> "$LOG_FILE" 2>&1 &
  PY_PID=$!
  sleep 2

  if kill -0 $PY_PID 2>/dev/null; then
    ok "HYDRA engine started (PID $PY_PID)"
    echo "$PY_PID" > "$HYDRA_DIR/hydra.pid"
    return 0
  else
    err "Server failed to start. Check: tail -20 $LOG_FILE"
    return 1
  fi
}

get_local_ip() {
  local IP=""

  # Method 1: ip route to 1.1.1.1
  IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K[\d.]+' | head -1)
  [ -n "$IP" ] && echo "$IP" && return

  # Method 2: ip addr — 192.168.x.x
  IP=$(ip addr 2>/dev/null | grep -oP '(?<=inet )192\.168\.[0-9]+\.[0-9]+' | head -1)
  [ -n "$IP" ] && echo "$IP" && return

  # Method 3: ip addr — 10.x.x.x
  IP=$(ip addr 2>/dev/null | grep -oP '(?<=inet )10\.[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  [ -n "$IP" ] && echo "$IP" && return

  # Method 4: ifconfig wlan0
  IP=$(ifconfig wlan0 2>/dev/null | grep -oP '(?<=inet addr:)[0-9.]+' | head -1)
  [ -n "$IP" ] && echo "$IP" && return

  # Method 5: termux-wifi-connectioninfo
  if command -v termux-wifi-connectioninfo &>/dev/null; then
    IP=$(termux-wifi-connectioninfo 2>/dev/null | python -c \
      "import sys,json;d=json.load(sys.stdin);print(d.get('ip',''))" 2>/dev/null)
    [ -n "$IP" ] && [ "$IP" != "None" ] && [ "$IP" != "" ] && echo "$IP" && return
  fi

  echo ""
}

# ── OPTION 2: LAN + LOCALHOST ─────────────────────────────────
start_lan() {
  check_ready || return
  start_engine || return

  LOCAL_IP=$(get_local_ip)
  echo ""
  echo -e "  ${BOLD}${GREEN}HYDRA is running on your network!${NC}\n"
  echo -e "  ${CYAN}This phone:${NC}   http://127.0.0.1:$PORT"
  [ -n "$LOCAL_IP" ] && {
    echo -e "  ${CYAN}WiFi LAN:${NC}     http://${LOCAL_IP}:$PORT"
    echo -e "  ${CYAN}Upload dir:${NC}   $UPLOAD_DIR"
    echo ""
    echo -e "  ${YELLOW}Open the LAN URL on any device connected to the same WiFi${NC}"
  }
  echo ""
  info "Press Ctrl+C to stop."
  trap "kill $PY_PID 2>/dev/null; termux-wake-unlock 2>/dev/null; ok 'HYDRA stopped.'" EXIT INT
  wait $PY_PID
}

# ── OPTION 3: LOCALHOST ONLY ──────────────────────────────────
start_local_only() {
  check_ready || return
  start_engine || return

  LOCAL_IP=$(get_local_ip)
  echo ""
  echo -e "  ${BOLD}${GREEN}HYDRA is running!${NC}\n"
  echo -e "  ${CYAN}This phone:${NC}   http://127.0.0.1:$PORT"
  [ -n "$LOCAL_IP" ] && \
  echo -e "  ${CYAN}WiFi LAN:${NC}     http://${LOCAL_IP}:$PORT"
  echo -e "  ${CYAN}Upload dir:${NC}   $UPLOAD_DIR"
  echo ""
  info "Press Ctrl+C to stop."
  trap "kill $PY_PID 2>/dev/null; termux-wake-unlock 2>/dev/null; ok 'HYDRA stopped.'" EXIT INT
  wait $PY_PID
}

# ── OPTION 4: STATUS ──────────────────────────────────────────
show_status() {
  section "HYDRA Status"

  if pgrep -f "hydra_server.py" &>/dev/null; then
    PID=$(pgrep -f "hydra_server.py")
    ok "HYDRA server: RUNNING (PID $PID) on port $PORT"
  else
    warn "HYDRA server: STOPPED"
  fi

  LOCAL_IP=$(get_local_ip)
  NFILES=$(ls "$UPLOAD_DIR" 2>/dev/null | wc -l)
  FSIZE=$(du -sh "$UPLOAD_DIR" 2>/dev/null | cut -f1)
  FREE=$(df -h "$UPLOAD_DIR" 2>/dev/null | awk 'NR==2{print $4}')

  echo ""
  echo -e "  ${BOLD}Storage:${NC}"
  echo -e "  Upload dir:   $UPLOAD_DIR"
  echo -e "  Files stored: $NFILES files ($FSIZE used)"
  echo -e "  Free space:   $FREE"
  echo ""
  echo -e "  ${BOLD}Network:${NC}"
  [ -n "$LOCAL_IP" ] && echo -e "  LAN URL:  http://${LOCAL_IP}:$PORT"
  echo -e "  Localhost: http://127.0.0.1:$PORT"
}

# ── OPTION 5: SPEED TEST ──────────────────────────────────────
speed_test() {
  section "WiFi Speed Test"
  info "Testing your connection speed..."

  if command -v termux-wifi-connectioninfo &>/dev/null; then
    WIFI=$(termux-wifi-connectioninfo 2>/dev/null)
    if [ -n "$WIFI" ]; then
      SSID=$(echo "$WIFI" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('ssid','?'))" 2>/dev/null)
      SPEED=$(echo "$WIFI" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('link_speed_mbps','?'))" 2>/dev/null)
      RSSI=$(echo "$WIFI" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('rssi','?'))" 2>/dev/null)
      echo ""
      ok "WiFi Network:  $SSID"
      ok "Link Speed:    ${SPEED} Mbps"
      ok "Signal (RSSI): ${RSSI} dBm"
    fi
  fi

  info "Testing local disk write speed..."
  TEST_FILE="$HYDRA_DIR/.speedtest"
  DD_OUT=$(dd if=/dev/zero of="$TEST_FILE" bs=64M count=1 2>&1)
  WRITE_SPEED=$(echo "$DD_OUT" | grep -oE '[0-9.]+ [MG]B/s' | tail -1)
  rm -f "$TEST_FILE"
  [ -n "$WRITE_SPEED" ] && ok "Disk write speed: $WRITE_SPEED" || \
    info "Disk write test complete"

  echo ""
  info "Tips for maximum transfer speed:"
  echo ""
  echo -e "  ${GREEN}✓${NC} Use 5GHz WiFi band (faster than 2.4GHz)"
  echo -e "  ${GREEN}✓${NC} Stay close to the WiFi router"
  echo -e "  ${GREEN}✓${NC} Keep phone plugged in (prevents CPU throttling)"
  echo -e "  ${GREEN}✓${NC} Disable other apps during large transfers"
  echo -e "  ${GREEN}✓${NC} HYDRA uses 8MB chunk streaming for max throughput"
}

# ── OPTION 6: LOGS ───────────────────────────────────────────
view_logs() {
  section "HYDRA Server Logs"
  if [ -f "$LOG_FILE" ]; then
    tail -50 "$LOG_FILE"
  else
    warn "No log file found yet. Start the server first."
  fi
}

# ── OPTION 7: STOP ───────────────────────────────────────────
stop_all() {
  section "Stopping HYDRA"
  pkill -f "hydra_server.py" && ok "HYDRA server stopped" || info "Server was not running"
  termux-wake-unlock 2>/dev/null && ok "Wake lock released"
  rm -f "$HYDRA_DIR/hydra.pid"
}

# ── MAIN ─────────────────────────────────────────────────────
show_menu
case $CHOICE in
  1) do_install ;;
  2) start_lan ;;
  3) start_local_only ;;
  4) show_status ;;
  5) speed_test ;;
  6) view_logs ;;
  7) stop_all ;;
  8) echo -e "\n  ${CYAN}HYDRA offline. Stay powerful.${NC}\n"; exit 0 ;;
  *) err "Invalid choice."; exit 1 ;;
esac
