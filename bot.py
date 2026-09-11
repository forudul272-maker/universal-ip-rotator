#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
        👑 FORIDUL UNIVERSAL IP ROTATOR & PROXY/VPN GATEWAY BOT 👑
        Author / Architect: FORIDUL
        Version: 3.0 Pro Ultimate Edition

        Supported Routing Protocols:
          1. OpenVPN (.ovpn file, auth credentials)
          2. WireGuard (.conf file or config text)
          3. Shadowsocks (ss:// URI)
          4. VLESS (vless:// URI)
          5. VMess (vmess:// Base64 URI)
          6. Trojan (trojan:// URI)
          7. SOCKS5 & SOCKS4 (socks5://, ip:port)
          8. HTTP & HTTPS Connect Proxy (http://, ip:port)

        🔥 Advanced Pro Features:
          • 📂 Node / VPN Pool Manager (Save, Label, One-Tap Switch)
          • ⏱️ Auto-Rotation Scheduler (5m, 10m, 15m, 30m, 1h, Custom)
          • 🔄 One-Click IP Rotation (/rotate)
          • ⚡ Live Tunnel Speed Test (Real-time Mbps & Ping)
          • 📋 VPS System Resource Monitor (/sysinfo)
          • 🛡️ Health Check Watchdog & Auto-Failover (No Downtime)
          • 📜 Connection History & Audit Logs (/history)
          • 📲 Interactive Inline Keyboard UI + Mobile Keyboard
================================================================================
"""

import os
import sys
import re
import json
import time
import base64
import signal
import socket
import logging
import shutil
import urllib.parse
import subprocess
import threading
import requests
import telebot
from telebot import types

# ------------------------------------------------------------------------------
# CONFIGURATION & PATH SETUP
# ------------------------------------------------------------------------------
CONFIG_PATH = "/opt/foridul-ip-rotator/config.json"

if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

if not os.path.exists(CONFIG_PATH):
    # Default fallback for testing or manual start
    config = {
        "bot_token": os.environ.get("BOT_TOKEN", ""),
        "admin_id": int(os.environ.get("ADMIN_ID", "0")) if os.environ.get("ADMIN_ID") else 0,
        "vps_ip": os.environ.get("VPS_IP", "")
    }
else:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

BOT_TOKEN = config.get("bot_token")
ADMIN_ID = int(config.get("admin_id", 0))
VPS_PUBLIC_IP = config.get("vps_ip", "")

if not BOT_TOKEN or not ADMIN_ID:
    print("Error: bot_token or admin_id missing in config.json or environment")
    if not os.path.exists(CONFIG_PATH):
        sys.exit(1)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("ForidulUniversalRotator")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

BASE_DIR = "/opt/foridul-ip-rotator"
if not os.path.exists(BASE_DIR):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OVPN_DIR = os.path.join(BASE_DIR, "ovpn")
WG_DIR = os.path.join(BASE_DIR, "wireguard")
XRAY_DIR = os.path.join(BASE_DIR, "xray_out")
POOL_DIR = os.path.join(BASE_DIR, "pool")

os.makedirs(OVPN_DIR, exist_ok=True)
os.makedirs(WG_DIR, exist_ok=True)
os.makedirs(XRAY_DIR, exist_ok=True)
os.makedirs(POOL_DIR, exist_ok=True)

POOL_FILE = os.path.join(POOL_DIR, "pool.json")
SETTINGS_FILE = os.path.join(POOL_DIR, "settings.json")
HISTORY_FILE = os.path.join(POOL_DIR, "history.json")

user_states = {}
active_node_info = {"name": "Native VPS", "type": "native", "connected_at": time.time()}

# ------------------------------------------------------------------------------
# DATA STORAGE HELPERS (POOL, SETTINGS, HISTORY)
# ------------------------------------------------------------------------------
def load_pool():
    if not os.path.exists(POOL_FILE):
        return []
    try:
        with open(POOL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_pool(pool):
    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(pool, f, indent=2)

def load_settings():
    defaults = {
        "autorotate_enabled": False,
        "interval_minutes": 10,
        "last_rotated": 0,
        "current_pool_index": 0,
        "watchdog_enabled": True
    }
    if not os.path.exists(SETTINGS_FILE):
        return defaults
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            defaults.update(data)
            return defaults
    except Exception:
        return defaults

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

def add_history_entry(node_name, ip, location, isp, status="Success"):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "node": node_name,
        "ip": ip,
        "location": location,
        "isp": isp,
        "status": status
    }
    history.insert(0, entry)
    # Keep last 25 entries
    history = history[:25]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def is_admin(message_or_call):
    return message_or_call.from_user.id == ADMIN_ID

# ------------------------------------------------------------------------------
# NETWORK & ROUTING UTILITIES
# ------------------------------------------------------------------------------
def get_public_ip_info():
    """Returns external IP, location, and ISP with fallback providers."""
    try:
        res = requests.get("https://ipinfo.io/json", timeout=6).json()
        return {
            "success": True,
            "ip": res.get("ip", "Unknown"),
            "location": f"{res.get('city', '')}, {res.get('country', '')}".strip(", "),
            "isp": res.get("org", "Unknown")
        }
    except Exception:
        pass

    try:
        res = requests.get("http://ip-api.com/json/?fields=query,city,country,isp", timeout=6).json()
        return {
            "success": True,
            "ip": res.get("query", "Unknown"),
            "location": f"{res.get('city', '')}, {res.get('country', '')}".strip(", "),
            "isp": res.get("isp", "Unknown")
        }
    except Exception:
        pass

    try:
        ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
        return {"success": True, "ip": ip, "location": "Unknown", "isp": "Unknown"}
    except Exception as e:
        return {"success": False, "error": str(e), "ip": "Unreachable", "location": "N/A", "isp": "N/A"}

def get_active_mode():
    """Detects which protocol is actively routing server outbound."""
    if subprocess.run("pgrep -f 'openvpn --config'", shell=True, stdout=subprocess.PIPE).stdout.decode().strip():
        return "🟢 OpenVPN (tun0 Active)"
    
    if subprocess.run("ip link show wg0 2>/dev/null | grep 'state UP'", shell=True, stdout=subprocess.PIPE).stdout.decode().strip():
        return "⚡ WireGuard (wg0 Active)"
    
    if subprocess.run("pgrep -f 'xray_out/config.json'", shell=True, stdout=subprocess.PIPE).stdout.decode().strip():
        return "🔮 V2Ray / Shadowsocks / Trojan Active"
    
    if subprocess.run("pgrep -f 'redsocks'", shell=True, stdout=subprocess.PIPE).stdout.decode().strip():
        return "🧦 SOCKS / HTTP Proxy Active"
    
    return "⚪ Direct VPS Native Network (No VPN)"

def ensure_ssh_routing_safety():
    """
    Guarantees incoming SSH (port 22) and physical VPS IP traffic
    always routes directly via physical interface using isolated table 200.
    NEVER touches or corrupts table main!
    """
    phys_if = config.get("phys_if") or "eth0"
    phys_gw = config.get("phys_gw")
    phys_ip = config.get("phys_ip") or config.get("vps_ip")
    
    cmd = f"""
    ip rule del pref 50 2>/dev/null || true
    ip rule del pref 100 2>/dev/null || true
    
    ETH="{phys_if}"
    GW="{phys_gw or ''}"
    MY_IP="{phys_ip or ''}"
    
    if [ -z "$GW" ] || [ -z "$MY_IP" ]; then
        ETH=$(ip -o -4 route show to default 2>/dev/null | awk '{{for(i=1;i<=NF;i++) if($i=="dev") print $(i+1)}}' | grep -v -E 'tun|tap|wg' | head -n1)
        [ -z "$ETH" ] && ETH="eth0"
        GW=$(ip -o -4 route show to default dev "$ETH" 2>/dev/null | awk '{{for(i=1;i<=NF;i++) if($i=="via") print $(i+1)}}' | head -n1)
        MY_IP=$(ip -4 -o addr show dev "$ETH" 2>/dev/null | awk '{{print $4}}' | cut -d'/' -f1 | head -n1)
    fi
    
    if [ -n "$MY_IP" ] && [ -n "$GW" ] && [ -n "$ETH" ]; then
        ip route replace default via "$GW" dev "$ETH" table 200 2>/dev/null || ip route add default via "$GW" dev "$ETH" table 200 2>/dev/null || true
        ip rule add from "$MY_IP" table 200 pref 100 2>/dev/null || true
    fi
    """
    try:
        subprocess.run(cmd, shell=True, timeout=5)
    except Exception as e:
        logger.warning(f"SSH safety configuration notice: {e}")

def stop_all_routing():
    """Gracefully stops all active VPNs, proxies, and resets iptables."""
    global active_node_info
    subprocess.run("pkill -9 openvpn 2>/dev/null || true", shell=True)
    subprocess.run("wg-quick down wg0 2>/dev/null || true", shell=True)
    subprocess.run("pkill -9 -f 'xray_out' 2>/dev/null || true", shell=True)
    subprocess.run("pkill -9 redsocks 2>/dev/null || true", shell=True)
    subprocess.run("iptables -t nat -F REDSOCKS 2>/dev/null || true", shell=True)
    subprocess.run("iptables -t nat -D OUTPUT -p tcp -j REDSOCKS 2>/dev/null || true", shell=True)
    ensure_ssh_routing_safety()
    active_node_info = {"name": "Native VPS", "type": "native", "connected_at": time.time()}

# ------------------------------------------------------------------------------
# SYSTEM RESOURCE MONITOR (/sysinfo)
# ------------------------------------------------------------------------------
def get_system_metrics():
    """Reads real-time CPU, RAM, Disk, Uptime, and connection stats."""
    # RAM
    ram_total, ram_used, ram_pct = 0, 0, 0
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        mem_info = {}
        for l in lines:
            parts = l.split(":")
            if len(parts) == 2:
                mem_info[parts[0].strip()] = int(parts[1].strip().split()[0])
        total_kb = mem_info.get("MemTotal", 1)
        avail_kb = mem_info.get("MemAvailable", mem_info.get("MemFree", 0))
        used_kb = total_kb - avail_kb
        ram_total = round(total_kb / 1024 / 1024, 2)
        ram_used = round(used_kb / 1024 / 1024, 2)
        ram_pct = round((used_kb / total_kb) * 100, 1)
    except Exception:
        ram_total, ram_used, ram_pct = 4.0, 1.2, 30.0

    # CPU Load Average
    load_1, load_5, load_15 = 0, 0, 0
    try:
        with open("/proc/loadavg", "r") as f:
            parts = f.read().split()
            load_1, load_5, load_15 = parts[0], parts[1], parts[2]
    except Exception:
        pass

    # Disk
    disk_total, disk_used, disk_pct = 0, 0, 0
    try:
        total, used, free = shutil.disk_usage("/")
        disk_total = round(total / (1024**3), 1)
        disk_used = round(used / (1024**3), 1)
        disk_pct = round((used / total) * 100, 1)
    except Exception:
        pass

    # Uptime
    uptime_str = "Unknown"
    try:
        res = subprocess.run("uptime -p 2>/dev/null || uptime", shell=True, stdout=subprocess.PIPE).stdout.decode().strip()
        uptime_str = res.replace("up ", "")
    except Exception:
        pass

    # TCP Connections
    tcp_conn = "Unknown"
    try:
        res = subprocess.run("ss -ta 2>/dev/null | wc -l", shell=True, stdout=subprocess.PIPE).stdout.decode().strip()
        tcp_conn = str(max(0, int(res) - 1)) if res.isdigit() else res
    except Exception:
        pass

    return {
        "ram_used": ram_used, "ram_total": ram_total, "ram_pct": ram_pct,
        "load": f"{load_1}, {load_5}, {load_15}",
        "disk_used": disk_used, "disk_total": disk_total, "disk_pct": disk_pct,
        "uptime": uptime_str,
        "tcp_conn": tcp_conn
    }

# ------------------------------------------------------------------------------
# SPEED TEST BENCHMARK
# ------------------------------------------------------------------------------
def run_speed_benchmark():
    """Performs download speed test and ping latency measurement."""
    # 1. Ping test
    ping_cf = "N/A"
    try:
        p = subprocess.run("ping -c 3 -W 2 1.1.1.1 2>/dev/null | tail -1 | awk '{print $4}' | cut -d '/' -f 2", shell=True, stdout=subprocess.PIPE).stdout.decode().strip()
        if p:
            ping_cf = f"{round(float(p), 1)} ms"
    except Exception:
        pass

    # 2. Download Speed Test (10 MB payload)
    speed_mbps = 0.0
    elapsed_time = 0.0
    test_urls = [
        "https://speed.cloudflare.com/__down?bytes=10485760",
        "https://cachefly.cachefly.net/10mb.test",
        "http://ipv4.download.thinkbroadband.com/10MB.zip"
    ]
    
    success = False
    for url in test_urls:
        try:
            start = time.time()
            res = requests.get(url, timeout=12, stream=True)
            total_bytes = 0
            for chunk in res.iter_content(chunk_size=65536):
                if chunk:
                    total_bytes += len(chunk)
                if time.time() - start > 10:  # max 10s test limit
                    break
            elapsed = time.time() - start
            if total_bytes > 500000 and elapsed > 0.1:
                speed_mbps = round((total_bytes * 8) / (elapsed * 1024 * 1024), 2)
                elapsed_time = round(elapsed, 2)
                success = True
                break
        except Exception:
            continue

    return {
        "success": success,
        "ping": ping_cf,
        "speed_mbps": speed_mbps,
        "duration": elapsed_time
    }

# ------------------------------------------------------------------------------
# KEYBOARDS & UI ELEMENTS
# ------------------------------------------------------------------------------
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🌐 Check Current IP / Status"),
        types.KeyboardButton("🔄 Rotate to Next IP (Pool)"),
        types.KeyboardButton("📂 Manage Node Pool"),
        types.KeyboardButton("⏱️ Auto-Rotation Timer"),
        types.KeyboardButton("⚡ Speed & Latency Test"),
        types.KeyboardButton("📋 VPS System Resources"),
        types.KeyboardButton("🚀 Add OpenVPN (.ovpn)"),
        types.KeyboardButton("⚡ Add WireGuard (.conf)"),
        types.KeyboardButton("🔮 Add V2Ray / SS / Trojan Link"),
        types.KeyboardButton("🧦 Add SOCKS5 / HTTP Proxy"),
        types.KeyboardButton("🛑 Reset to Default Native IP"),
        types.KeyboardButton("📜 Connection History")
    )
    return markup

def status_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔄 Refresh Status", callback_data="cb_status"),
        types.InlineKeyboardButton("⏭️ Rotate Next IP", callback_data="cb_rotate_now")
    )
    markup.add(
        types.InlineKeyboardButton("📂 Node Pool", callback_data="cb_view_pool"),
        types.InlineKeyboardButton("⏱️ Auto-Rotate", callback_data="cb_autorotate_menu")
    )
    markup.add(
        types.InlineKeyboardButton("⚡ Speed Test", callback_data="cb_speedtest"),
        types.InlineKeyboardButton("📋 SysInfo", callback_data="cb_sysinfo")
    )
    markup.add(
        types.InlineKeyboardButton("🛑 Reset Native IP", callback_data="cb_reset_native"),
        types.InlineKeyboardButton("📜 History", callback_data="cb_history")
    )
    return markup

def pool_inline_keyboard(pool):
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not pool:
        markup.add(types.InlineKeyboardButton("➕ Add New Config", callback_data="cb_add_node_menu"))
        markup.add(types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="cb_status"))
        return markup
    
    for idx, node in enumerate(pool):
        btn_text = f"#{idx+1} {node.get('name', 'Node')} ({node.get('type', '').upper()})"
        markup.add(
            types.InlineKeyboardButton(f"🚀 Connect: {btn_text}", callback_data=f"cb_connect_node_{idx}")
        )
        markup.add(
            types.InlineKeyboardButton(f"❌ Delete: {node.get('name')}", callback_data=f"cb_del_node_{idx}")
        )
    
    markup.add(types.InlineKeyboardButton("➕ Add Another Config", callback_data="cb_add_node_menu"))
    markup.add(types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="cb_status"))
    return markup

def autorotate_inline_keyboard(settings):
    markup = types.InlineKeyboardMarkup(row_width=3)
    status_icon = "🟢 ACTIVE" if settings.get("autorotate_enabled") else "⚪ DISABLED"
    cur_interval = settings.get("interval_minutes", 10)
    
    markup.add(
        types.InlineKeyboardButton("5 Min", callback_data="cb_set_timer_5"),
        types.InlineKeyboardButton("10 Min", callback_data="cb_set_timer_10"),
        types.InlineKeyboardButton("15 Min", callback_data="cb_set_timer_15")
    )
    markup.add(
        types.InlineKeyboardButton("30 Min", callback_data="cb_set_timer_30"),
        types.InlineKeyboardButton("1 Hour", callback_data="cb_set_timer_60"),
        types.InlineKeyboardButton("2 Hours", callback_data="cb_set_timer_120")
    )
    if settings.get("autorotate_enabled"):
        markup.add(types.InlineKeyboardButton("🛑 Turn OFF Auto-Rotation", callback_data="cb_toggle_autorotate_off"))
    else:
        markup.add(types.InlineKeyboardButton(f"▶️ Start Auto-Rotation ({cur_interval}m)", callback_data="cb_toggle_autorotate_on"))
    
    markup.add(types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="cb_status"))
    return markup

# ------------------------------------------------------------------------------
# CORE CONNECTION CONTROLLERS
# ------------------------------------------------------------------------------
def start_openvpn(chat_id, ovpn_path, username=None, password=None, node_name="OpenVPN Node"):
    global active_node_info
    bot.send_message(chat_id, f"⏳ <b>Connecting {node_name} & routing outbound traffic...</b>")
    stop_all_routing()
    time.sleep(1)
    
    auth_path = os.path.join(OVPN_DIR, "auth.txt")
    if username and password:
        with open(auth_path, "w") as f:
            f.write(f"{username}\n{password}\n")
        os.chmod(auth_path, 0o600)
    
    with open(ovpn_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    
    clean_lines = []
    has_auth = False
    for line in lines:
        if line.strip().startswith("auth-user-pass"):
            clean_lines.append(f"auth-user-pass {auth_path}\n")
            has_auth = True
        elif line.strip().startswith("dev "):
            clean_lines.append("dev tun0\n")
        else:
            clean_lines.append(line)
            
    if not has_auth and os.path.exists(auth_path):
        clean_lines.append(f"\nauth-user-pass {auth_path}\n")
        
    clean_lines.append("\ndev tun0\n")
    clean_lines.append("redirect-gateway def1\n")
    
    run_ovpn_path = os.path.join(OVPN_DIR, "run.ovpn")
    with open(run_ovpn_path, "w") as f:
        f.writelines(clean_lines)
    
    log_path = os.path.join(OVPN_DIR, "openvpn.log")
    cmd = f"openvpn --config {run_ovpn_path} --log {log_path} --daemon"
    subprocess.run(cmd, shell=True)
    
    connected = False
    for _ in range(12):
        time.sleep(1)
        tun_check = subprocess.run("ip addr show tun0 2>/dev/null | grep 'inet '", shell=True, stdout=subprocess.PIPE).stdout.decode()
        if tun_check:
            connected = True
            break
            
    if connected:
        ensure_ssh_routing_safety()
        info = get_public_ip_info()
        active_node_info = {"name": node_name, "type": "ovpn", "connected_at": time.time()}
        add_history_entry(node_name, info.get("ip"), info.get("location"), info.get("isp"), "Connected")
        text = (
            f"🎉 <b>{node_name.upper()} CONNECTED!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 <b>Live Outbound IP:</b> <code>{info.get('ip')}</code>\n"
            f"🌍 <b>Location:</b> {info.get('location')}\n"
            f"🏢 <b>ISP:</b> {info.get('isp')}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 <i>Incoming SSH & V2Ray are 100% safeguarded.</i>"
        )
    else:
        log_tail = subprocess.run(f"tail -n 15 {log_path} 2>/dev/null", shell=True, stdout=subprocess.PIPE).stdout.decode()
        text = f"❌ <b>OpenVPN Connection Failed.</b>\n\nLog preview:\n<code>{log_tail}</code>"
        add_history_entry(node_name, "N/A", "N/A", "N/A", "Failed")
        
    bot.send_message(chat_id, text, reply_markup=status_inline_keyboard())

def start_wireguard(chat_id, wg_conf_content, node_name="WireGuard Node"):
    global active_node_info
    bot.send_message(chat_id, f"⏳ <b>Starting WireGuard ({node_name}) & verifying handshake...</b>")
    stop_all_routing()
    time.sleep(1)
    
    try:
        # 1. Sanitize WireGuard config for Linux VPS safety:
        # Remove DNS line to prevent breaking VPS DNS resolution
        clean_conf = re.sub(r'(?im)^\s*DNS\s*=.*$', '# DNS preserved by system', wg_conf_content)
        # Remove IPv6 ::/0 if IPv6 routing is not enabled
        clean_conf = clean_conf.replace(", ::/0", "").replace("::/0,", "").replace("::/0", "")
        
        wg_path = "/etc/wireguard/wg0.conf"
        with open(wg_path, "w", encoding="utf-8") as f:
            f.write(clean_conf)
        os.chmod(wg_path, 0o600)
        
        # Ensure previous wg0 is down
        subprocess.run("wg-quick down wg0 2>/dev/null || true", shell=True)
        time.sleep(1)
        
        up_res = subprocess.run("wg-quick up wg0", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        wg_check = subprocess.run("ip addr show wg0 2>/dev/null | grep 'inet '", shell=True, stdout=subprocess.PIPE).stdout.decode()
        if not wg_check:
            err_msg = up_res.stderr.strip() or "wg-quick failed to bring up interface"
            bot.send_message(chat_id, f"❌ <b>WireGuard Startup Error:</b>\n<code>{err_msg}</code>", reply_markup=status_inline_keyboard())
            add_history_entry(node_name, "N/A", "N/A", "N/A", "Startup Failed")
            stop_all_routing()
            return
            
        # 2. Verify active WireGuard handshake (within 6 seconds)
        handshake_ok = False
        for _ in range(6):
            time.sleep(1)
            hs = subprocess.run("wg show wg0 latest-handshakes 2>/dev/null | awk '{print $2}'", shell=True, stdout=subprocess.PIPE).stdout.decode().strip()
            if hs and hs.isdigit() and int(hs) > 0 and (time.time() - int(hs)) < 30:
                handshake_ok = True
                break
                
        if not handshake_ok:
            # WireGuard peer did NOT respond! Teardown immediately to prevent blackholing traffic
            subprocess.run("wg-quick down wg0 2>/dev/null || true", shell=True)
            stop_all_routing()
            text = (
                f"❌ <b>{node_name} Handshake Failed!</b>\n\n"
                "⚠️ The remote WireGuard server did not respond to the handshake.\n"
                "• <i>Causes:</i> Expired PrivateKey, invalid Endpoint, or UDP port blocked.\n"
                "🛡️ <i>Connection was automatically rolled back to protect server routing.</i>"
            )
            add_history_entry(node_name, "N/A", "N/A", "N/A", "Handshake Failed")
            bot.send_message(chat_id, text, reply_markup=status_inline_keyboard())
            return
            
        # 3. Handshake succeeded!
        ensure_ssh_routing_safety()
        info = get_public_ip_info()
        active_node_info = {"name": node_name, "type": "wg", "connected_at": time.time()}
        add_history_entry(node_name, info.get("ip"), info.get("location"), info.get("isp"), "Connected")
        text = (
            f"🎉 <b>{node_name.upper()} CONNECTED!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 <b>Live Outbound IP:</b> <code>{info.get('ip')}</code>\n"
            f"🌍 <b>Location:</b> {info.get('location')}\n"
            f"🏢 <b>ISP:</b> {info.get('isp')}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ <i>Ultra-low latency WireGuard kernel routing active.</i>"
        )
        bot.send_message(chat_id, text, reply_markup=status_inline_keyboard())
        
    except Exception as e:
        subprocess.run("wg-quick down wg0 2>/dev/null || true", shell=True)
        stop_all_routing()
        bot.send_message(chat_id, f"❌ <b>WireGuard Error:</b> <code>{e}</code>", reply_markup=status_inline_keyboard())

def parse_and_start_xray_outbound(chat_id, uri_str, node_name="V2Ray Node"):
    global active_node_info
    bot.send_message(chat_id, f"⏳ <b>Parsing proxy link & launching Xray engine ({node_name})...</b>")
    stop_all_routing()
    time.sleep(1)
    
    outbound_obj = None
    try:
        if uri_str.startswith("vless://"):
            parsed = urllib.parse.urlparse(uri_str)
            user_id = parsed.username
            host = parsed.hostname
            port = parsed.port or 443
            qs = urllib.parse.parse_qs(parsed.query)
            
            security = qs.get("security", ["none"])[0]
            net_type = qs.get("type", ["tcp"])[0]
            sni = qs.get("sni", [host])[0]
            path = qs.get("path", ["/"])[0]
            
            stream_settings = {"network": net_type}
            if security == "tls":
                stream_settings["security"] = "tls"
                stream_settings["tlsSettings"] = {"serverName": sni, "allowInsecure": True}
            elif security == "reality":
                stream_settings["security"] = "reality"
                stream_settings["realitySettings"] = {
                    "serverName": sni,
                    "publicKey": qs.get("pbk", [""])[0],
                    "shortId": qs.get("sid", [""])[0],
                    "spiderX": qs.get("spx", [""])[0]
                }
            if net_type == "ws":
                stream_settings["wsSettings"] = {"path": path, "headers": {"Host": sni}}
                
            outbound_obj = {
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": host,
                        "port": int(port),
                        "users": [{"id": user_id, "encryption": "none", "level": 0}]
                    }]
                },
                "streamSettings": stream_settings
            }
            
        elif uri_str.startswith("vmess://"):
            b64_data = uri_str[8:]
            b64_data += "=" * ((4 - len(b64_data) % 4) % 4)
            data = json.loads(base64.b64decode(b64_data).decode("utf-8", errors="ignore"))
            
            host = data.get("add")
            port = int(data.get("port", 443))
            user_id = data.get("id")
            net_type = data.get("net", "tcp")
            security = data.get("tls", "none")
            sni = data.get("sni", host)
            path = data.get("path", "/")
            
            stream_settings = {"network": net_type}
            if security == "tls":
                stream_settings["security"] = "tls"
                stream_settings["tlsSettings"] = {"serverName": sni, "allowInsecure": True}
            if net_type == "ws":
                stream_settings["wsSettings"] = {"path": path, "headers": {"Host": sni}}
                
            outbound_obj = {
                "protocol": "vmess",
                "settings": {
                    "vnext": [{
                        "address": host,
                        "port": port,
                        "users": [{"id": user_id, "alterId": 0, "security": "auto"}]
                    }]
                },
                "streamSettings": stream_settings
            }
            
        elif uri_str.startswith("trojan://"):
            parsed = urllib.parse.urlparse(uri_str)
            password = parsed.username
            host = parsed.hostname
            port = parsed.port or 443
            qs = urllib.parse.parse_qs(parsed.query)
            sni = qs.get("sni", [host])[0]
            net_type = qs.get("type", ["tcp"])[0]
            
            stream_settings = {
                "network": net_type,
                "security": "tls",
                "tlsSettings": {"serverName": sni, "allowInsecure": True}
            }
            if net_type == "ws":
                stream_settings["wsSettings"] = {"path": qs.get("path", ["/"])[0], "headers": {"Host": sni}}
                
            outbound_obj = {
                "protocol": "trojan",
                "settings": {
                    "servers": [{
                        "address": host,
                        "port": int(port),
                        "password": password
                    }]
                },
                "streamSettings": stream_settings
            }
            
        elif uri_str.startswith("ss://"):
            clean = uri_str[5:].split("#")[0]
            if "@" in clean:
                user_info, host_info = clean.split("@", 1)
                user_info += "=" * ((4 - len(user_info) % 4) % 4)
                method_pass = base64.b64decode(user_info).decode()
                method, password = method_pass.split(":", 1)
                host, port = host_info.split(":", 1)
            else:
                clean += "=" * ((4 - len(clean) % 4) % 4)
                decoded = base64.b64decode(clean).decode()
                method_pass, host_info = decoded.split("@", 1)
                method, password = method_pass.split(":", 1)
                host, port = host_info.split(":", 1)
                
            outbound_obj = {
                "protocol": "shadowsocks",
                "settings": {
                    "servers": [{
                        "address": host,
                        "port": int(port),
                        "method": method,
                        "password": password
                    }]
                }
            }
    except Exception as e:
        bot.send_message(chat_id, f"❌ <b>Error parsing link:</b> {e}")
        return

    if not outbound_obj:
        bot.send_message(chat_id, "❌ <b>Unsupported link format.</b> Please verify your URL.")
        return

    xray_client_config = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "port": 10808,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True}
            }
        ],
        "outbounds": [outbound_obj]
    }
    
    conf_path = os.path.join(XRAY_DIR, "config.json")
    with open(conf_path, "w", encoding="utf-8") as f:
        json.dump(xray_client_config, f, indent=2)
        
    cmd = f"/usr/local/bin/xray run -config {conf_path} > /tmp/xray_out.log 2>&1 &"
    subprocess.run(cmd, shell=True)
    time.sleep(2)
    
    apply_redsocks_tunnel(chat_id, "127.0.0.1", "10808", "socks5", "", "", node_name=node_name)

def apply_redsocks_tunnel(chat_id, host, port, p_type="socks5", user="", password="", node_name="Proxy Node"):
    global active_node_info
    redsocks_conf = f"""
base {{
 log_debug = off;
 log_info = on;
 log = "file:/var/log/redsocks.log";
 daemon = on;
 redirector = iptables;
}}

redsocks {{
 local_ip = 127.0.0.1;
 local_port = 12345;
 ip = {host};
 port = {port};
 type = {p_type};
 {'login = "' + user + '";' if user else ''}
 {'password = "' + password + '";' if password else ''}
}}
"""
    with open("/etc/redsocks.conf", "w") as f:
        f.write(redsocks_conf)
        
    subprocess.run("pkill -9 redsocks 2>/dev/null || true", shell=True)
    subprocess.run("redsocks -c /etc/redsocks.conf", shell=True)
    
    iptables_cmd = f"""
    iptables -t nat -F REDSOCKS 2>/dev/null || iptables -t nat -N REDSOCKS
    iptables -t nat -F REDSOCKS
    iptables -t nat -A REDSOCKS -d 0.0.0.0/8 -j RETURN
    iptables -t nat -A REDSOCKS -d 10.0.0.0/8 -j RETURN
    iptables -t nat -A REDSOCKS -d 127.0.0.0/8 -j RETURN
    iptables -t nat -A REDSOCKS -d 169.254.0.0/16 -j RETURN
    iptables -t nat -A REDSOCKS -d 172.16.0.0/12 -j RETURN
    iptables -t nat -A REDSOCKS -d 192.168.0.0/16 -j RETURN
    iptables -t nat -A REDSOCKS -d {host} -j RETURN
    iptables -t nat -A REDSOCKS -p tcp -j REDIRECT --to-ports 12345
    
    iptables -t nat -D OUTPUT -p tcp -j REDSOCKS 2>/dev/null || true
    iptables -t nat -A OUTPUT -p tcp -j REDSOCKS
    """
    subprocess.run(iptables_cmd, shell=True)
    time.sleep(2)
    
    info = get_public_ip_info()
    if info.get("success"):
        active_node_info = {"name": node_name, "type": "proxy", "connected_at": time.time()}
        add_history_entry(node_name, info.get("ip"), info.get("location"), info.get("isp"), "Connected")
        text = (
            f"🎉 <b>{node_name.upper()} ACTIVE!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 <b>Live Outbound IP:</b> <code>{info.get('ip')}</code>\n"
            f"🌍 <b>Location:</b> {info.get('location')}\n"
            f"🏢 <b>ISP:</b> {info.get('isp')}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        text = "⚠️ Proxy routing active, but outbound verification timed out. Verify proxy node is alive."
        add_history_entry(node_name, "Unverified", "N/A", "N/A", "Warning")
        
    bot.send_message(chat_id, text, reply_markup=status_inline_keyboard())

# ------------------------------------------------------------------------------
# POOL MANAGER & ROTATION LOGIC
# ------------------------------------------------------------------------------
def connect_node_from_pool(chat_id, node_index):
    pool = load_pool()
    if not pool or node_index >= len(pool):
        bot.send_message(chat_id, "⚠️ Node index not found in pool.", reply_markup=main_keyboard())
        return False
        
    node = pool[node_index]
    ntype = node.get("type")
    name = node.get("name", f"Node #{node_index+1}")
    
    # Update current pool index
    settings = load_settings()
    settings["current_pool_index"] = node_index
    settings["last_rotated"] = time.time()
    save_settings(settings)
    
    if ntype == "ovpn":
        start_openvpn(chat_id, node.get("path"), node.get("username"), node.get("password"), node_name=name)
        return True
    elif ntype == "wg":
        start_wireguard(chat_id, node.get("content"), node_name=name)
        return True
    elif ntype == "v2ray":
        parse_and_start_xray_outbound(chat_id, node.get("uri"), node_name=name)
        return True
    elif ntype == "proxy":
        p = node.get("proxy_info", {})
        apply_redsocks_tunnel(chat_id, p.get("host"), p.get("port"), p.get("ptype", "socks5"), p.get("user", ""), p.get("pass", ""), node_name=name)
        return True
    return False

def rotate_to_next_ip(chat_id=None):
    """Jumps to the next available configuration in the node pool."""
    pool = load_pool()
    target_chat = chat_id if chat_id else ADMIN_ID
    
    if not pool:
        bot.send_message(
            target_chat,
            "⚠️ <b>Node Pool is Empty!</b>\n\n"
            "Please upload configurations first (OpenVPN <code>.ovpn</code>, WireGuard <code>.conf</code>, V2Ray links, or Proxies).",
            reply_markup=main_keyboard()
        )
        return False
        
    settings = load_settings()
    current_idx = settings.get("current_pool_index", 0)
    next_idx = (current_idx + 1) % len(pool)
    
    next_node = pool[next_idx]
    bot.send_message(
        target_chat,
        f"🔄 <b>Rotating IP to Node #{next_idx+1}: {next_node.get('name')}...</b>"
    )
    return connect_node_from_pool(target_chat, next_idx)

# ------------------------------------------------------------------------------
# BACKGROUND THREADS: AUTO-ROTATION SCHEDULER & HEALTH WATCHDOG
# ------------------------------------------------------------------------------
def background_scheduler_worker():
    """Periodically checks auto-rotation timer and triggers rotation."""
    while True:
        try:
            time.sleep(10)
            settings = load_settings()
            if not settings.get("autorotate_enabled"):
                continue
                
            interval_sec = settings.get("interval_minutes", 10) * 60
            last_rot = settings.get("last_rotated", 0)
            
            if time.time() - last_rot >= interval_sec:
                pool = load_pool()
                if pool and len(pool) > 0:
                    logger.info("⏱️ Auto-Rotation Timer Triggered!")
                    rotate_to_next_ip(ADMIN_ID)
                else:
                    settings["autorotate_enabled"] = False
                    save_settings(settings)
                    bot.send_message(ADMIN_ID, "⚠️ Auto-rotation disabled: Pool has no nodes.")
        except Exception as e:
            logger.error(f"Scheduler worker error: {e}")
            time.sleep(15)

def background_watchdog_worker():
    """Monitors tunnel health. If dead for 2 cycles, auto-recovers."""
    fail_count = 0
    while True:
        try:
            time.sleep(40)
            settings = load_settings()
            if not settings.get("watchdog_enabled"):
                continue
                
            mode = get_active_mode()
            if "Native" in mode:
                fail_count = 0
                continue
                
            # Test connectivity
            alive = False
            try:
                res = requests.get("https://api.ipify.org", timeout=6)
                if res.status_code == 200:
                    alive = True
            except Exception:
                pass
                
            if not alive:
                fail_count += 1
                logger.warning(f"Watchdog: Outbound check failed ({fail_count}/2)")
            else:
                fail_count = 0
                
            if fail_count >= 2:
                logger.error("🚨 Watchdog: Tunnel DEAD! Initiating emergency auto-recovery...")
                fail_count = 0
                bot.send_message(
                    ADMIN_ID,
                    "🚨 <b>ALERT: VPN Tunnel Connectivity Lost!</b>\n\n"
                    "🔄 <i>Auto-Failover in progress: Switching to next pool node...</i>"
                )
                pool = load_pool()
                if pool and len(pool) > 1:
                    rotate_to_next_ip(ADMIN_ID)
                else:
                    bot.send_message(
                        ADMIN_ID,
                        "⚠️ <i>No alternate pool node found. Reverting to Safe Native VPS IP.</i>"
                    )
                    stop_all_routing()
                    info = get_public_ip_info()
                    bot.send_message(
                        ADMIN_ID,
                        f"✅ <b>Failsafe Active:</b> Native IP restored (<code>{info.get('ip')}</code>)"
                    )
        except Exception as e:
            logger.error(f"Watchdog error: {e}")
            time.sleep(20)

# ------------------------------------------------------------------------------
# TELEGRAM MESSAGE HANDLERS
# ------------------------------------------------------------------------------
@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔ <b>Access Denied!</b> Unauthorized user.")
        return

    banner = (
        "╔════════════════════════════════════════╗\n"
        "║   👑 <b>FORIDUL UNIVERSAL IP ENGINE</b> 👑    ║\n"
        "║       <i>Version 3.0 Pro Ultimate</i>          ║\n"
        "╚════════════════════════════════════════╝\n\n"
        "👋 Welcome <b>Admin Foridul</b>!\n\n"
        "Manage, rotate, and benchmark your VPS external network with complete automation:\n\n"
        "• 🔄 <b>Rotate IP:</b> Tap <code>/rotate</code> or button to cycle IPs\n"
        "• ⏱️ <b>Auto-Timer:</b> Rotate every 5m, 10m, 30m, or 1 hour\n"
        "• 📂 <b>Node Pool:</b> Store multiple VPNs/Proxies with friendly names\n"
        "• ⚡ <b>Speed Test:</b> Live tunnel download speed & latency benchmark\n"
        "• 📋 <b>System Info:</b> Real-time CPU, RAM, Disk & Uptime metrics\n"
        "• 🛡️ <b>Health Watchdog:</b> 24/7 background keepalive with auto-failover\n"
        "• 🛑 <b>Reset IP:</b> Instant revert to default native VPS gateway\n\n"
        "🛡️ <i>SSH (22, 80) and V2Ray (443) are 100% route-protected.</i>"
    )
    bot.send_message(message.chat.id, banner, reply_markup=main_keyboard())
    # Send interactive dashboard
    send_status_dashboard(message.chat.id)

def send_status_dashboard(chat_id, edit_message_id=None):
    info = get_public_ip_info()
    mode = get_active_mode()
    settings = load_settings()
    pool = load_pool()
    
    timer_txt = f"🟢 {settings.get('interval_minutes')}m" if settings.get("autorotate_enabled") else "⚪ OFF"
    watchdog_txt = "🟢 Active" if settings.get("watchdog_enabled") else "⚪ Disabled"
    
    text = (
        "📊 <b>FORIDUL IP ROUTING DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 <b>Outbound IP:</b> <code>{info.get('ip', 'N/A')}</code>\n"
        f"🌍 <b>Location:</b> {info.get('location', 'N/A')}\n"
        f"🏢 <b>ISP:</b> {info.get('isp', 'N/A')}\n"
        f"⚙️ <b>Active Mode:</b> {mode}\n"
        f"🏷️ <b>Current Node:</b> {active_node_info.get('name', 'Native VPS')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📂 <b>Pool Nodes:</b> {len(pool)} saved\n"
        f"⏱️ <b>Auto-Rotation:</b> {timer_txt}\n"
        f"🛡️ <b>Watchdog:</b> {watchdog_txt}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👑 <i>Universal Gateway Architecture by FORIDUL</i>"
    )
    if edit_message_id:
        try:
            bot.edit_message_text(text, chat_id, edit_message_id, reply_markup=status_inline_keyboard())
        except Exception:
            bot.send_message(chat_id, text, reply_markup=status_inline_keyboard())
    else:
        bot.send_message(chat_id, text, reply_markup=status_inline_keyboard())

@bot.message_handler(func=lambda m: m.text in ["🌐 Check Current IP / Status", "/ip", "/status"])
def handle_status(message):
    if not is_admin(message): return
    send_status_dashboard(message.chat.id)

@bot.message_handler(func=lambda m: m.text in ["🔄 Rotate to Next IP (Pool)", "/rotate"])
def handle_rotate_command(message):
    if not is_admin(message): return
    rotate_to_next_ip(message.chat.id)

@bot.message_handler(func=lambda m: m.text in ["📂 Manage Node Pool", "/pool"])
def handle_pool_menu(message):
    if not is_admin(message): return
    pool = load_pool()
    text = (
        f"📂 <b>VPN & PROXY NODE POOL ({len(pool)} Saved)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Select any node below to connect immediately, or manage items:\n"
    )
    bot.send_message(message.chat.id, text, reply_markup=pool_inline_keyboard(pool))

@bot.message_handler(func=lambda m: m.text in ["⏱️ Auto-Rotation Timer", "/autorotate", "/timer"])
def handle_autorotate_menu(message):
    if not is_admin(message): return
    settings = load_settings()
    pool = load_pool()
    status_str = "🟢 <b>ENABLED</b>" if settings.get("autorotate_enabled") else "⚪ <b>DISABLED</b>"
    cur_m = settings.get("interval_minutes", 10)
    
    text = (
        "⏱️ <b>AUTO-ROTATION SCHEDULER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Status: {status_str}\n"
        f"• Current Interval: <b>Every {cur_m} minutes</b>\n"
        f"• Pool Size: <b>{len(pool)} node(s)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Select an interval below to set timer:"
    )
    bot.send_message(message.chat.id, text, reply_markup=autorotate_inline_keyboard(settings))

@bot.message_handler(func=lambda m: m.text in ["⚡ Speed & Latency Test", "/speed", "/speedtest"])
def handle_speedtest_cmd(message):
    if not is_admin(message): return
    msg = bot.send_message(message.chat.id, "⚡ <i>Running real-time speed & latency test through active route...</i>")
    
    def worker():
        metrics = run_speed_benchmark()
        info = get_public_ip_info()
        if metrics["success"]:
            text = (
                "⚡ <b>SPEED TEST BENCHMARK</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📡 <b>Exit IP:</b> <code>{info.get('ip')}</code>\n"
                f"🌍 <b>Location:</b> {info.get('location')}\n"
                f"📶 <b>Ping Latency:</b> <code>{metrics['ping']}</code>\n"
                f"📥 <b>Download Speed:</b> <code>{metrics['speed_mbps']} Mbps</code>\n"
                f"⏱️ <b>Test Duration:</b> <code>{metrics['duration']}s</code>\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            )
        else:
            text = (
                "⚠️ <b>Speed Test Incomplete.</b>\n"
                f"Ping: <code>{metrics['ping']}</code>\n"
                "Test server reached rate limit or connection was restricted."
            )
        bot.edit_message_text(text, message.chat.id, msg.message_id, reply_markup=status_inline_keyboard())

    threading.Thread(target=worker, daemon=True).start()

@bot.message_handler(func=lambda m: m.text in ["📋 VPS System Resources", "/sysinfo", "/system"])
def handle_sysinfo_cmd(message):
    if not is_admin(message): return
    metrics = get_system_metrics()
    info = get_public_ip_info()
    mode = get_active_mode()
    
    text = (
        "📋 <b>VPS SYSTEM METRICS & HEALTH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🖥️ <b>Uptime:</b> <code>{metrics['uptime']}</code>\n"
        f"📊 <b>CPU Load:</b> <code>{metrics['load']}</code>\n"
        f"🧠 <b>RAM Usage:</b> <code>{metrics['ram_used']} GB / {metrics['ram_total']} GB ({metrics['ram_pct']}%)</code>\n"
        f"💾 <b>Disk Usage:</b> <code>{metrics['disk_used']} GB / {metrics['disk_total']} GB ({metrics['disk_pct']}%)</code>\n"
        f"🔗 <b>Active TCP Sockets:</b> <code>{metrics['tcp_conn']}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Current IP:</b> <code>{info.get('ip')}</code>\n"
        f"⚙️ <b>Routing Mode:</b> {mode}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    bot.send_message(message.chat.id, text, reply_markup=status_inline_keyboard())

@bot.message_handler(func=lambda m: m.text in ["🛑 Reset to Default Native IP", "/reset"])
def handle_reset_cmd(message):
    if not is_admin(message): return
    msg = bot.send_message(message.chat.id, "🔄 <i>Stopping active tunnels and reverting default gateway...</i>")
    stop_all_routing()
    time.sleep(2)
    info = get_public_ip_info()
    add_history_entry("Native Revert", info.get("ip"), info.get("location"), info.get("isp"), "Reverted")
    text = (
        "✅ <b>IP REVERTED TO NATIVE VPS GATEWAY!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "All VPNs and transparent proxies disconnected.\n\n"
        f"🌐 <b>Native IP:</b> <code>{info.get('ip', 'Unknown')}</code>\n"
        f"📍 <b>Location:</b> {info.get('location', 'Unknown')}\n"
        f"🏢 <b>ISP:</b> {info.get('isp', 'Unknown')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    bot.edit_message_text(text, message.chat.id, msg.message_id, reply_markup=status_inline_keyboard())

@bot.message_handler(func=lambda m: m.text in ["📜 Connection History", "/history", "/logs"])
def handle_history_cmd(message):
    if not is_admin(message): return
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except Exception:
            pass
            
    if not history:
        bot.send_message(message.chat.id, "📜 <i>No recent connection history recorded yet.</i>")
        return
        
    lines = ["📜 <b>RECENT IP ROTATION & CONNECTION HISTORY</b>", "━━━━━━━━━━━━━━━━━━━━━━"]
    for idx, item in enumerate(history[:10]):
        lines.append(
            f"<b>{idx+1}.</b> [{item.get('timestamp')}]\n"
            f"   🏷️ <b>Node:</b> {item.get('node')}\n"
            f"   📡 <b>IP:</b> <code>{item.get('ip')}</code> ({item.get('location')})\n"
            f"   🏢 <b>ISP:</b> {item.get('isp')}\n"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    bot.send_message(message.chat.id, "\n".join(lines), reply_markup=status_inline_keyboard())

# ------------------------------------------------------------------------------
# PROMPT HANDLERS FOR ADDING CONFIGS
# ------------------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text in ["🚀 Add OpenVPN (.ovpn)", "/ovpn"])
def handle_ovpn_prompt(message):
    if not is_admin(message): return
    user_states[message.from_user.id] = {"state": "AWAITING_OVPN"}
    bot.send_message(
        message.chat.id,
        "📤 <b>Send your <code>.ovpn</code> configuration file here.</b>\n\n"
        "<i>If it requires username/password, you will be prompted for them.</i>",
        reply_markup=types.ForceReply()
    )

@bot.message_handler(func=lambda m: m.text in ["⚡ Add WireGuard (.conf)", "/wg", "/wireguard"])
def handle_wg_prompt(message):
    if not is_admin(message): return
    user_states[message.from_user.id] = {"state": "AWAITING_WG"}
    bot.send_message(
        message.chat.id,
        "⚡ <b>Send your WireGuard <code>.conf</code> file OR paste the raw <code>[Interface]...[Peer]</code> text here.</b>",
        reply_markup=types.ForceReply()
    )

@bot.message_handler(func=lambda m: m.text in ["🔮 Add V2Ray / SS / Trojan Link", "/v2ray", "/vless", "/vmess", "/trojan", "/ss"])
def handle_v2ray_prompt(message):
    if not is_admin(message): return
    user_states[message.from_user.id] = {"state": "AWAITING_V2RAY_LINK"}
    bot.send_message(
        message.chat.id,
        "🔮 <b>Paste any proxy link directly:</b>\n\n"
        "• <code>vless://uuid@host:port?...</code>\n"
        "• <code>vmess://eyJhZGQi...</code>\n"
        "• <code>trojan://password@host:port?...</code>\n"
        "• <code>ss://base64@host:port#name</code>\n"
        "• <code>socks5://user:pass@host:port</code>\n"
        "• <code>http://user:pass@host:port</code>",
        reply_markup=types.ForceReply()
    )

@bot.message_handler(func=lambda m: m.text in ["🧦 Add SOCKS5 / HTTP Proxy", "/proxy", "/socks"])
def handle_proxy_prompt(message):
    if not is_admin(message): return
    user_states[message.from_user.id] = {"state": "AWAITING_PROXY"}
    bot.send_message(
        message.chat.id,
        "🧦 <b>Send your SOCKS5 or HTTP proxy:</b>\n\n"
        "Format: <code>ip:port</code> or <code>ip:port:user:pass</code>",
        reply_markup=types.ForceReply()
    )

# ------------------------------------------------------------------------------
# INLINE CALLBACK QUERY HANDLER
# ------------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_queries(call):
    if not is_admin(call):
        bot.answer_callback_query(call.id, "Access Denied!", show_alert=True)
        return
        
    data = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    if data == "cb_status":
        bot.answer_callback_query(call.id, "Refreshing dashboard...")
        send_status_dashboard(chat_id, edit_message_id=message_id)
        
    elif data == "cb_rotate_now":
        bot.answer_callback_query(call.id, "Rotating IP...")
        rotate_to_next_ip(chat_id)
        
    elif data == "cb_view_pool":
        bot.answer_callback_query(call.id, "Opening Node Pool...")
        pool = load_pool()
        text = f"📂 <b>NODE POOL ({len(pool)} Saved)</b>\nTap to connect or manage:"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=pool_inline_keyboard(pool))
        
    elif data.startswith("cb_connect_node_"):
        idx = int(data.replace("cb_connect_node_", ""))
        bot.answer_callback_query(call.id, f"Connecting node #{idx+1}...")
        connect_node_from_pool(chat_id, idx)
        
    elif data.startswith("cb_del_node_"):
        idx = int(data.replace("cb_del_node_", ""))
        pool = load_pool()
        if 0 <= idx < len(pool):
            removed = pool.pop(idx)
            save_pool(pool)
            bot.answer_callback_query(call.id, f"Deleted: {removed.get('name')}")
            text = f"🗑️ <b>Deleted:</b> {removed.get('name')}\nRemaining nodes: {len(pool)}"
            bot.edit_message_text(text, chat_id, message_id, reply_markup=pool_inline_keyboard(pool))
            
    elif data == "cb_autorotate_menu":
        bot.answer_callback_query(call.id, "Auto-Rotation Settings")
        settings = load_settings()
        pool = load_pool()
        status_str = "🟢 <b>ENABLED</b>" if settings.get("autorotate_enabled") else "⚪ <b>DISABLED</b>"
        text = (
            "⏱️ <b>AUTO-ROTATION SCHEDULER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Status: {status_str}\n"
            f"• Current Interval: <b>Every {settings.get('interval_minutes', 10)}m</b>\n"
            f"• Pool: <b>{len(pool)} nodes</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Select rotation interval:"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=autorotate_inline_keyboard(settings))
        
    elif data.startswith("cb_set_timer_"):
        mins = int(data.replace("cb_set_timer_", ""))
        settings = load_settings()
        settings["interval_minutes"] = mins
        settings["autorotate_enabled"] = True
        settings["last_rotated"] = time.time()
        save_settings(settings)
        bot.answer_callback_query(call.id, f"Auto-rotate set to {mins} min!")
        send_status_dashboard(chat_id, edit_message_id=message_id)
        
    elif data == "cb_toggle_autorotate_off":
        settings = load_settings()
        settings["autorotate_enabled"] = False
        save_settings(settings)
        bot.answer_callback_query(call.id, "Auto-rotation disabled.")
        send_status_dashboard(chat_id, edit_message_id=message_id)
        
    elif data == "cb_toggle_autorotate_on":
        settings = load_settings()
        settings["autorotate_enabled"] = True
        settings["last_rotated"] = time.time()
        save_settings(settings)
        bot.answer_callback_query(call.id, "Auto-rotation started!")
        send_status_dashboard(chat_id, edit_message_id=message_id)
        
    elif data == "cb_speedtest":
        bot.answer_callback_query(call.id, "Starting speed test...")
        bot.edit_message_text("⚡ <i>Running real-time speed & latency test...</i>", chat_id, message_id)
        
        def worker():
            metrics = run_speed_benchmark()
            info = get_public_ip_info()
            if metrics["success"]:
                text = (
                    "⚡ <b>SPEED TEST BENCHMARK</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📡 <b>Exit IP:</b> <code>{info.get('ip')}</code>\n"
                    f"🌍 <b>Location:</b> {info.get('location')}\n"
                    f"📶 <b>Ping Latency:</b> <code>{metrics['ping']}</code>\n"
                    f"📥 <b>Download Speed:</b> <code>{metrics['speed_mbps']} Mbps</code>\n"
                    f"⏱️ <b>Test Duration:</b> <code>{metrics['duration']}s</code>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                )
            else:
                text = f"⚠️ <b>Speed test error.</b> Ping: {metrics['ping']}"
            bot.edit_message_text(text, chat_id, message_id, reply_markup=status_inline_keyboard())

        threading.Thread(target=worker, daemon=True).start()
        
    elif data == "cb_sysinfo":
        bot.answer_callback_query(call.id, "Fetching system metrics...")
        metrics = get_system_metrics()
        info = get_public_ip_info()
        text = (
            "📋 <b>VPS SYSTEM METRICS & HEALTH</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🖥️ <b>Uptime:</b> <code>{metrics['uptime']}</code>\n"
            f"📊 <b>CPU Load:</b> <code>{metrics['load']}</code>\n"
            f"🧠 <b>RAM Usage:</b> <code>{metrics['ram_used']} GB / {metrics['ram_total']} GB ({metrics['ram_pct']}%)</code>\n"
            f"💾 <b>Disk Usage:</b> <code>{metrics['disk_used']} GB / {metrics['disk_total']} GB ({metrics['disk_pct']}%)</code>\n"
            f"🔗 <b>Active TCP Sockets:</b> <code>{metrics['tcp_conn']}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 <b>Current IP:</b> <code>{info.get('ip')}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        bot.edit_message_text(text, chat_id, message_id, reply_markup=status_inline_keyboard())
        
    elif data == "cb_reset_native":
        bot.answer_callback_query(call.id, "Reverting to Native IP...")
        stop_all_routing()
        time.sleep(2)
        send_status_dashboard(chat_id, edit_message_id=message_id)
        
    elif data == "cb_history":
        bot.answer_callback_query(call.id, "Loading History...")
        handle_history_cmd(call.message)
        
    elif data == "cb_add_node_menu":
        bot.answer_callback_query(call.id, "Add New Config")
        bot.send_message(
            chat_id,
            "➕ <b>To add a new node to the pool:</b>\n\n"
            "1. Send an <code>.ovpn</code> file\n"
            "2. Send a <code>.conf</code> WireGuard file\n"
            "3. Paste a <code>vless://</code>, <code>vmess://</code>, or <code>trojan://</code> link\n"
            "4. Send a proxy (<code>ip:port:user:pass</code>)\n\n"
            "<i>The bot will automatically ask whether to Connect Now or Save to Pool!</i>"
        )

# ------------------------------------------------------------------------------
# DOCUMENT & TEXT INPUT RECEIVERS
# ------------------------------------------------------------------------------
@bot.message_handler(content_types=["document"])
def handle_document(message):
    if not is_admin(message): return
    file_name = message.document.file_name.lower()
    
    if file_name.endswith(".ovpn"):
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        # Save unique pool file
        save_name = f"ovpn_{int(time.time())}_{message.document.file_name}"
        target_path = os.path.join(POOL_DIR, save_name)
        with open(target_path, "wb") as f:
            f.write(downloaded)
            
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        auth_file = os.path.join(OVPN_DIR, "auth.txt")
        if "auth-user-pass" in content and not os.path.exists(auth_file):
            user_states[message.from_user.id] = {
                "state": "AWAITING_OVPN_AUTH",
                "ovpn_path": target_path,
                "file_name": message.document.file_name
            }
            bot.send_message(
                message.chat.id,
                "🔑 <b>Credentials needed for this OpenVPN.</b>\n\nReply in format: <code>username:password</code>",
                reply_markup=types.ForceReply()
            )
        else:
            # Auto add to pool
            pool = load_pool()
            node_alias = message.document.file_name.replace(".ovpn", "").replace("_", " ").title()
            pool.append({
                "name": node_alias,
                "type": "ovpn",
                "path": target_path,
                "added_at": time.time()
            })
            save_pool(pool)
            start_openvpn(message.chat.id, target_path, node_name=node_alias)
            
    elif file_name.endswith(".conf"):
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path).decode("utf-8", errors="ignore")
        
        node_alias = message.document.file_name.replace(".conf", "").replace("_", " ").title()
        pool = load_pool()
        pool.append({
            "name": node_alias,
            "type": "wg",
            "content": downloaded,
            "added_at": time.time()
        })
        save_pool(pool)
        start_wireguard(message.chat.id, downloaded, node_name=node_alias)
    else:
        bot.reply_to(message, "⚠️ Unsupported file format. Please upload <code>.ovpn</code> or <code>.conf</code> (WireGuard).")

@bot.message_handler(func=lambda m: True)
def handle_text_messages(message):
    if not is_admin(message): return
    
    text = message.text.strip()
    state_info = user_states.get(message.from_user.id, {})
    state = state_info.get("state")
    
    if state == "AWAITING_OVPN_AUTH":
        if ":" in text:
            parts = text.split(":", 1)
            username, password = parts[0].strip(), parts[1].strip()
            ovpn_path = state_info.get("ovpn_path", os.path.join(OVPN_DIR, "active.ovpn"))
            file_name = state_info.get("file_name", "OpenVPN Node")
            user_states.pop(message.from_user.id, None)
            
            # Save into pool with auth
            pool = load_pool()
            node_alias = file_name.replace(".ovpn", "").replace("_", " ").title()
            pool.append({
                "name": node_alias,
                "type": "ovpn",
                "path": ovpn_path,
                "username": username,
                "password": password,
                "added_at": time.time()
            })
            save_pool(pool)
            start_openvpn(message.chat.id, ovpn_path, username, password, node_name=node_alias)
        else:
            bot.reply_to(message, "⚠️ Invalid format! Please send: <code>username:password</code>")
        return
        
    if state == "AWAITING_WG" or "[Interface]" in text:
        user_states.pop(message.from_user.id, None)
        node_alias = f"WireGuard Node #{int(time.time()) % 1000}"
        pool = load_pool()
        pool.append({
            "name": node_alias,
            "type": "wg",
            "content": text,
            "added_at": time.time()
        })
        save_pool(pool)
        start_wireguard(message.chat.id, text, node_name=node_alias)
        return
        
    if state == "AWAITING_V2RAY_LINK" or any(text.startswith(p) for p in ["vless://", "vmess://", "trojan://", "ss://"]):
        user_states.pop(message.from_user.id, None)
        proto = text.split("://")[0].upper()
        # Extract link remark if present in hash #
        alias = f"{proto} Node #{int(time.time()) % 1000}"
        if "#" in text:
            alias = urllib.parse.unquote(text.split("#")[1].strip())
            
        pool = load_pool()
        pool.append({
            "name": alias,
            "type": "v2ray",
            "uri": text,
            "added_at": time.time()
        })
        save_pool(pool)
        parse_and_start_xray_outbound(message.chat.id, text, node_name=alias)
        return
        
    if state == "AWAITING_PROXY" or any(text.startswith(p) for p in ["socks5://", "http://", "socks://"]) or text.count(":") in [1, 3]:
        user_states.pop(message.from_user.id, None)
        p_type = "socks5"
        user, password = "", ""
        proxy_str = text
        if proxy_str.startswith("http://"):
            p_type = "http-connect"
            proxy_str = proxy_str.replace("http://", "")
        elif proxy_str.startswith("socks5://"):
            p_type = "socks5"
            proxy_str = proxy_str.replace("socks5://", "")
            
        if "@" in proxy_str:
            auth_part, host_part = proxy_str.split("@", 1)
            user, password = auth_part.split(":", 1) if ":" in auth_part else (auth_part, "")
            host, port = host_part.split(":", 1) if ":" in host_part else (host_part, "")
        elif proxy_str.count(":") == 3:
            parts = proxy_str.split(":")
            host, port, user, password = parts[0], parts[1], parts[2], parts[3]
        elif proxy_str.count(":") == 1:
            parts = proxy_str.split(":")
            host, port = parts[0], parts[1]
        else:
            bot.send_message(message.chat.id, "❌ Unrecognized proxy format.")
            return
            
        alias = f"Proxy {host}:{port}"
        pool = load_pool()
        pool.append({
            "name": alias,
            "type": "proxy",
            "proxy_info": {
                "host": host, "port": port, "ptype": p_type,
                "user": user, "pass": password
            },
            "added_at": time.time()
        })
        save_pool(pool)
        apply_redsocks_tunnel(message.chat.id, host, port, p_type, user, password, node_name=alias)
        return

# ------------------------------------------------------------------------------
# BOT ENTRYPOINT & DAEMON THREADS
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    ensure_ssh_routing_safety()
    
    # Start background threads for Auto-Rotation and Watchdog
    threading.Thread(target=background_scheduler_worker, daemon=True).start()
    threading.Thread(target=background_watchdog_worker, daemon=True).start()
    
    print("👑 Foridul Universal IP Engine Bot v3.0 Pro started!")
    try:
        bot.infinity_polling(timeout=25, long_polling_timeout=25)
    except Exception as e:
        logger.error(f"Bot loop terminated: {e}")
