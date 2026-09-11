# 👑 FORIDUL Universal IP Rotator & VPN Gateway Bot (v3.0 Pro)

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Ubuntu%20%7C%20Debian-green)
![Telegram](https://img.shields.io/badge/Telegram-Bot%20API-blue?logo=telegram)
![License](https://img.shields.io/badge/License-MIT-orange)

An all-in-one automated Telegram Bot and Gateway Controller for Linux VPS. Control, route, and rotate your server's outbound public IP across **EVERY major VPN and proxy protocol**, with built-in auto-rotation timers, speed testing, system resource monitoring, and anti-lockout SSH routing safety.

---

## 🔥 Key Features

- **🌐 Multi-Protocol Outbound Routing:**
  - 🚀 **OpenVPN** (`.ovpn` files with auto-auth handling)
  - ⚡ **WireGuard** (`.conf` files or raw interface text)
  - 🔮 **V2Ray / Xray** (`vless://`, `vmess://`, `trojan://`, `ss://`)
  - 🧦 **Proxies** (`socks5://`, `http://`, `ip:port:user:pass`)
- **📂 Node & VPN Pool Manager:** Save multiple VPNs and proxies with custom aliases and switch nodes with 1 tap (`/pool`).
- **⏱️ Auto-Rotation Scheduler:** Auto-rotate your public IP every **5m, 10m, 15m, 30m, 1h, or 2h** via background worker (`/autorotate`).
- **🔄 Instant IP Rotation:** Cycle instantly to the next available IP in your pool (`/rotate`).
- **⚡ Live Speed & Latency Test:** Benchmark real-time download speed (Mbps) and ping latency through active route (`/speedtest`).
- **📋 VPS System Health Monitor:** Monitor real-time CPU Load, RAM usage %, Disk usage %, and Server Uptime (`/sysinfo`).
- **🛡️ 24/7 Watchdog & Auto-Failover:** Background keepalive automatically detects dead tunnels and switches nodes or reverts to safe native IP so your VPS is never locked out.
- **🔒 Route-Protected SSH & V2Ray:** Policy routing guarantees SSH (Port 22, 80) and V2Ray (Port 443) remain permanently reachable on original VPS IP.
- **📜 Connection History:** Stores audit logs of previous IP rotations and ISPs (`/history`).

---

## ⚡ Quick One-Line Installation (VPS)

Run this single command on your Ubuntu / Debian server (as root):

```bash
bash <(curl -sSL https://raw.githubusercontent.com/forudul272-maker/universal-ip-rotator/main/install.sh)
```

The installer will prompt for:
1. **Installation License Password** (Default: `FORIDUL_VIP_2026`)
2. **Telegram Bot Token** (from [@BotFather](https://t.me/BotFather))
3. **Admin Telegram User ID** (from [@userinfobot](https://t.me/userinfobot))

It then verifies license with your Cloudflare Worker server, installs all dependencies, configures systemd, and starts the bot automatically!

---

## 🛠️ Manual Installation (Git Clone)

```bash
# 1. Clone this repository
git clone https://github.com/forudul272-maker/universal-ip-rotator.git
cd universal-ip-rotator

# 2. Make installer executable & run
chmod +x install.sh
sudo bash install.sh
```

---

## 🤖 Telegram Bot Commands

| Command | Action |
|---|---|
| `/start` | Open the main interactive control dashboard |
| `/ip` or `/status` | Check live outbound IP, ISP, country, and active mode |
| `/rotate` | Instantly rotate outbound IP to next node in pool |
| `/pool` | View and manage saved VPN / Proxy pool |
| `/autorotate` | Configure auto-rotation timer interval (5m, 10m, 30m, 1h) |
| `/speedtest` | Run live download speed and ping latency benchmark |
| `/sysinfo` | View real-time CPU, RAM, Disk, and server uptime stats |
| `/reset` | Safely revert server to native default VPS IP |
| `/history` | View the last 25 IP rotations and timestamp logs |

---

## ⚙️ Service Management

To check status, restart, or view real-time logs on the VPS:

```bash
# Check service status
systemctl status foridul-ip-rotator

# Restart bot
systemctl restart foridul-ip-rotator

# View live logs
journalctl -u foridul-ip-rotator -f
```

---

## 🔒 Security Note

- Never commit `config.json` containing your real Telegram Bot Token or server IP to public repositories.
- The included `.gitignore` will automatically prevent secret files from being committed.

---

## 👤 Author

**FORIDUL** — Universal Network Routing & Proxy Automation Engine.
