#!/bin/bash
# ==============================================================================
#                 👑 FORIDUL UNIVERSAL IP ROTATOR INSTALLER 👑
#   Supports: OpenVPN, WireGuard, VLESS, VMess, Trojan, Shadowsocks, SOCKS, HTTP
# ==============================================================================

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

clear

echo -e "${CYAN}${BOLD}"
echo "███████╗ ██████╗ ██████╗ ██╗██████╗ ██╗   ██╗██╗     "
echo "██╔════╝██╔═══██╗██╔══██╗██║██╔══██╗██║   ██║██║     "
echo "█████╗  ██║   ██║██████╔╝██║██║  ██║██║   ██║██║     "
echo "██╔══╝  ██║   ██║██╔══██╗██║██║  ██║██║   ██║██║     "
echo "██║     ╚██████╔╝██║  ██║██║██████╔╝╚██████╔╝███████╗"
echo "╚═╝      ╚═════╝ ╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝ ╚══════╝"
echo -e "${YELLOW}      ★ UNIVERSAL ALL-IN-ONE VPN & PROXY ENGINE ★      ${NC}"
echo -e "${MAGENTA}                 Developed by: FORIDUL                 ${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}\n"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Please run this script as root! (sudo bash install.sh)${NC}"
    exit 1
fi

# Reset any broken policies/routes from past attempts
ip rule del pref 50 2>/dev/null || true
ip rule del pref 100 2>/dev/null || true
pkill -9 openvpn 2>/dev/null || true
wg-quick down wg0 2>/dev/null || true
pkill -9 redsocks 2>/dev/null || true
pkill -9 -f "xray_out" 2>/dev/null || true
iptables -t nat -F REDSOCKS 2>/dev/null || true
iptables -t nat -D OUTPUT -p tcp -j REDSOCKS 2>/dev/null || true

# Ensure DNS resolvers are functional
if ! grep -q "nameserver" /etc/resolv.conf 2>/dev/null; then
    echo "nameserver 1.1.1.1" > /etc/resolv.conf
    echo "nameserver 8.8.8.8" >> /etc/resolv.conf
fi

# Detect physical interface, gateway, and server IP (NEVER get fooled by VPNs)
ETH=$(ip -o -4 route show to default 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev") print $(i+1)}' | grep -v -E 'tun|tap|wg' | head -n1)
[ -z "$ETH" ] && ETH="eth0"
GW=$(ip -o -4 route show to default dev "$ETH" 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="via") print $(i+1)}' | head -n1)
VPS_IP=$(ip -4 -o addr show dev "$ETH" 2>/dev/null | awk '{print $4}' | cut -d'/' -f1 | head -n1)

if [ -z "$VPS_IP" ]; then
    VPS_IP=$(curl -s --max-time 3 https://api.ipify.org || echo "Unknown")
fi

echo -e "${GREEN}✓ Physical Interface:${NC} ${ETH}"
echo -e "${GREEN}✓ Default Gateway:   ${NC} ${GW}"
echo -e "${GREEN}✓ Server Physical IP:${NC} ${VPS_IP}\n"

# ==============================================================================
#                  🔐 CLOUDFLARE LICENSE & ACCESS VERIFICATION
# ==============================================================================
LICENSE_SERVER="https://foridul-license-manager.sg-foridul.workers.dev"

echo -e "${YELLOW}${BOLD}━━━━━━━━━━━━ 🔐 LICENSE AUTHENTICATION ━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Protected by Foridul Cloudflare Edge Security System${NC}\n"

AUTH_SUCCESS=0
for attempt in 1 2 3; do
    read -p "👉 Enter Installation Password / Key: " INPUT_KEY </dev/tty
    INPUT_KEY=$(echo "$INPUT_KEY" | xargs)
    
    if [ -z "$INPUT_KEY" ]; then
        echo -e "${RED}⚠️ Password/Key cannot be empty! (Attempt ${attempt}/3)${NC}"
        continue
    fi
    
    echo -e "${CYAN}⏳ Verifying license with Cloudflare server...${NC}"
    
    # Call Cloudflare Worker API
    AUTH_RESP=$(curl -s --max-time 10 -X POST "${LICENSE_SERVER}/api/verify" \
        -H "Content-Type: application/json" \
        -d "{\"key\": \"$INPUT_KEY\", \"ip\": \"$VPS_IP\"}" 2>/dev/null || true)
    
    if echo "$AUTH_RESP" | grep -q '"success":true'; then
        AUTH_SUCCESS=1
        echo -e "${GREEN}${BOLD}✓ License Authorized Successfully! Access Granted.${NC}\n"
        break
    else
        ERR_MSG=$(echo "$AUTH_RESP" | grep -oP '(?<="message":")[^"]*' || echo "Invalid password or authorization failed")
        echo -e "${RED}❌ ${ERR_MSG} (Attempt ${attempt}/3)${NC}\n"
    fi
done

if [ "$AUTH_SUCCESS" -ne 1 ]; then
    echo -e "${RED}${BOLD}══════════════════════════════════════════════════════${NC}"
    echo -e "${RED}${BOLD}  🚫 ACCESS DENIED! YOU ARE NOT AUTHORIZED TO INSTALL ${NC}"
    echo -e "${YELLOW}  Please contact Admin FORIDUL for an active license key. ${NC}"
    echo -e "${RED}${BOLD}══════════════════════════════════════════════════════${NC}\n"
    exit 1
fi
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# Collect Telegram Credentials
echo -e "${YELLOW}${BOLD}━━━━━━━━━━━━━ 🤖 TELEGRAM BOT SETUP ━━━━━━━━━━━━━${NC}"

while [ -z "$BOT_TOKEN" ]; do
    read -p "👉 Enter Telegram Bot Token (API Key): " BOT_TOKEN </dev/tty
    BOT_TOKEN=$(echo "$BOT_TOKEN" | xargs)
    if [ -z "$BOT_TOKEN" ]; then
        echo -e "${RED}⚠️ Bot Token cannot be empty! Please enter valid token.${NC}"
    fi
done

while [ -z "$ADMIN_ID" ]; do
    read -p "👉 Enter Admin Telegram User ID: " ADMIN_ID </dev/tty
    ADMIN_ID=$(echo "$ADMIN_ID" | xargs)
    if [ -z "$ADMIN_ID" ]; then
        echo -e "${RED}⚠️ Admin ID cannot be empty!${NC}"
    fi
done

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo -e "${CYAN}⏳ [1/5] Updating and installing system packages (OpenVPN, WireGuard, Redsocks)...${NC}"
apt-get update -y
apt-get install -y python3 python3-pip python3-venv openvpn wireguard wireguard-tools redsocks iptables curl iproute2 git net-tools

echo -e "\n${CYAN}⏳ [2/5] Setting up Python virtual environment & installing libraries...${NC}"
INSTALL_DIR="/opt/foridul-ip-rotator"
mkdir -p "${INSTALL_DIR}/ovpn" "${INSTALL_DIR}/wireguard" "${INSTALL_DIR}/xray_out" "${INSTALL_DIR}/pool" "/etc/wireguard"

# Python Virtualenv
python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --upgrade pip
if ! "${INSTALL_DIR}/venv/bin/pip" install pyTelegramBotAPI requests; then
    echo "⚠️ Retrying with direct Cloudflare DNS..."
    echo "nameserver 1.1.1.1" > /etc/resolv.conf
    echo "nameserver 8.8.8.8" >> /etc/resolv.conf
    "${INSTALL_DIR}/venv/bin/pip" install pyTelegramBotAPI requests
fi

# Write Configuration (with exact physical network info)
cat <<EOF > "${INSTALL_DIR}/config.json"
{
  "bot_token": "${BOT_TOKEN}",
  "admin_id": "${ADMIN_ID}",
  "vps_ip": "${VPS_IP}",
  "phys_if": "${ETH}",
  "phys_gw": "${GW}",
  "phys_ip": "${VPS_IP}"
}
EOF
chmod 600 "${INSTALL_DIR}/config.json"

echo -e "${CYAN}⏳ [3/5] Deploying Universal Bot Controller...${NC}"
# Download clean bot.py from GitHub repository
curl -sSL "https://raw.githubusercontent.com/forudul272-maker/universal-ip-rotator/main/bot.py" -o "${INSTALL_DIR}/bot.py"
if [ ! -s "${INSTALL_DIR}/bot.py" ] && [ -f "$(dirname "$0")/bot.py" ]; then
    cp "$(dirname "$0")/bot.py" "${INSTALL_DIR}/bot.py"
fi
chmod +x "${INSTALL_DIR}/bot.py"

echo -e "${CYAN}⏳ [4/5] Safeguarding SSH and VPS management routing...${NC}"
# Configure isolated policy routing table 200 for physical interface (100% SSH protection)
if [ -n "$VPS_IP" ] && [ -n "$GW" ] && [ -n "$ETH" ]; then
    ip route replace default via "$GW" dev "$ETH" table 200 2>/dev/null || ip route add default via "$GW" dev "$ETH" table 200 2>/dev/null || true
    ip rule del pref 100 2>/dev/null || true
    ip rule add from "$VPS_IP" table 200 pref 100 2>/dev/null || true
fi
sleep 1

echo -e "${CYAN}⏳ [5/5] Creating and starting systemd background service...${NC}"
cat << EOF > /etc/systemd/system/foridul-ip-rotator.service
[Unit]
Description=Foridul Universal IP Route and Rotator Bot
After=network.target network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/bot.py
Restart=always
RestartSec=5
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable foridul-ip-rotator.service
systemctl restart foridul-ip-rotator.service --no-block

sleep 3

if systemctl is-active --quiet foridul-ip-rotator.service; then
    echo -e "\n${GREEN}${BOLD}======================================================${NC}"
    echo -e "${GREEN}${BOLD}   🎉 UNIVERSAL INSTALLATION COMPLETED BY FORIDUL!    ${NC}"
    echo -e "${GREEN}${BOLD}======================================================${NC}"
    echo -e "${CYAN}• Supported Protocols:${NC} ${YELLOW}OpenVPN, WireGuard, VLESS, VMess, Trojan, Shadowsocks, SOCKS5, HTTP${NC}"
    echo -e "${CYAN}• Bot Service:${NC} ${GREEN}Active & Running (systemctl status foridul-ip-rotator)${NC}"
    echo -e "${CYAN}• Admin User ID:${NC} ${YELLOW}${ADMIN_ID}${NC}"
    echo -e "${CYAN}• Server Physical IP:${NC} ${YELLOW}${VPS_IP}${NC}"
    echo -e "\n${MAGENTA}👉 Open your Telegram Bot and send ${BOLD}/start${NC}${MAGENTA} to begin!${NC}\n"
else
    echo -e "\n${RED}⚠️ Service started with warnings. Check logs: journalctl -u foridul-ip-rotator -e${NC}\n"
fi
