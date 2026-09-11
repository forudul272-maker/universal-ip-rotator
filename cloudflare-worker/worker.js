/**
 * 👑 FORIDUL UNIVERSAL IP ROTATOR - CLOUDFLARE LICENSE & ANALYTICS SERVER
 * Host this on Cloudflare Workers (100% Free Forever, 0 Maintenance)
 * 
 * Features:
 *   • 🔐 Master Password Verification
 *   • 🏷️ Custom Multi-Key Generator (Single-use or Multi-use)
 *   • 📊 Real-time Installation Counter & IP Tracker
 *   • 🔔 Instant Telegram Alert on every install
 *   • 💻 Gorgeous Dark-mode Web Admin Dashboard
 */

// Default configuration if KV is not yet bound
const DEFAULT_CONFIG = {
  admin_pin: "1234",               // Dashboard Login PIN
  master_password: "FORIDUL_VIP_2026", // Default Master Install Password
  tg_token: "",                    // Telegram Bot Token (Optional for live alerts)
  tg_chat_id: ""                   // Your Telegram Chat ID
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Helper to get/set KV with memory fallback
    async function getStored(key, defaultVal) {
      if (env && env.LICENSE_KV) {
        const val = await env.LICENSE_KV.get(key, "json");
        return val !== null ? val : defaultVal;
      }
      return defaultVal;
    }

    async function setStored(key, val) {
      if (env && env.LICENSE_KV) {
        await env.LICENSE_KV.put(key, JSON.stringify(val));
      }
    }

    // CORS Headers for API
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // -------------------------------------------------------------------------
    // 1. API: VERIFY LICENSE (/api/verify)
    // -------------------------------------------------------------------------
    if (path === "/api/verify" && request.method === "POST") {
      try {
        const body = await request.json();
        const clientKey = (body.key || "").trim();
        const clientIp = body.ip || request.headers.get("CF-Connecting-IP") || "Unknown";
        const country = request.cf ? (request.cf.country || "Unknown") : "Unknown";
        const city = request.cf ? (request.cf.city || "") : "";

        const config = await getStored("CONFIG", DEFAULT_CONFIG);
        const keys = await getStored("KEYS", {});
        const stats = await getStored("STATS", { total_runs: 0, success: 0, failed: 0 });
        let logs = await getStored("LOGS", []);

        stats.total_runs += 1;

        let isAuthorized = false;
        let keyLabel = "Invalid";
        let reason = "";

        // Check 1: Master Password match
        if (clientKey === config.master_password) {
          isAuthorized = true;
          keyLabel = "Master Password";
        } 
        // Check 2: Custom Client Key match
        else if (keys[clientKey]) {
          const keyData = keys[clientKey];
          if (!keyData.active) {
            reason = "License Key is Deactivated";
          } else if (keyData.max_uses > 0 && keyData.used_count >= keyData.max_uses) {
            reason = "License Key Usage Limit Reached";
          } else {
            isAuthorized = true;
            keyLabel = `Key: ${keyData.client_name || clientKey}`;
            keyData.used_count = (keyData.used_count || 0) + 1;
            keyData.last_ip = clientIp;
            keyData.last_used = new Date().toISOString();
            keys[clientKey] = keyData;
            await setStored("KEYS", keys);
          }
        } else {
          reason = "Invalid License Password";
        }

        // Update stats & logs
        if (isAuthorized) {
          stats.success += 1;
        } else {
          stats.failed += 1;
        }
        await setStored("STATS", stats);

        const newLog = {
          id: Date.now(),
          timestamp: new Date().toLocaleString("en-GB", { timeZone: "Asia/Dhaka" }),
          ip: clientIp,
          location: city ? `${city}, ${country}` : country,
          key_used: clientKey,
          label: keyLabel,
          status: isAuthorized ? "SUCCESS" : "FAILED",
          reason: isAuthorized ? "Authorized" : reason
        };

        logs.unshift(newLog);
        logs = logs.slice(0, 50); // Keep last 50 logs
        await setStored("LOGS", logs);

        // Send Telegram Notification (if configured)
        if (config.tg_token && config.tg_chat_id) {
          ctx.waitUntil((async () => {
            try {
              const icon = isAuthorized ? "🟢 SUCCESS" : "🔴 BLOCKED";
              const tgMsg = `<b>👑 FORIDUL LICENSE ALERT</b>\n` +
                            `━━━━━━━━━━━━━━━━━━━━━━\n` +
                            `<b>Status:</b> ${icon}\n` +
                            `<b>Action:</b> Script Installation\n` +
                            `<b>VPS IP:</b> <code>${clientIp}</code>\n` +
                            `<b>Location:</b> ${city} ${country}\n` +
                            `<b>Key/Pass:</b> <code>${clientKey}</code>\n` +
                            `<b>Label:</b> ${keyLabel}\n` +
                            `<b>Time:</b> ${newLog.timestamp}\n` +
                            `━━━━━━━━━━━━━━━━━━━━━━\n` +
                            `<b>Total Runs:</b> ${stats.total_runs} (Success: ${stats.success})`;
              
              await fetch(`https://api.telegram.org/bot${config.tg_token}/sendMessage`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  chat_id: config.tg_chat_id,
                  text: tgMsg,
                  parse_mode: "HTML"
                })
              });
            } catch (e) {}
          })());
        }

        if (isAuthorized) {
          return new Response(JSON.stringify({
            success: true,
            message: "License Authorized! Starting installation...",
            total_runs: stats.total_runs
          }), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
        } else {
          return new Response(JSON.stringify({
            success: false,
            message: reason || "Access Denied!"
          }), { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } });
        }
      } catch (err) {
        return new Response(JSON.stringify({ success: false, message: "Internal server error" }), { status: 500, headers: corsHeaders });
      }
    }

    // -------------------------------------------------------------------------
    // 2. ADMIN ACTIONS (/api/admin/*)
    // -------------------------------------------------------------------------
    if (path.startsWith("/api/admin/")) {
      const authPin = request.headers.get("X-Admin-Pin");
      const config = await getStored("CONFIG", DEFAULT_CONFIG);

      if (authPin !== config.admin_pin) {
        return new Response(JSON.stringify({ success: false, message: "Unauthorized PIN" }), { status: 401, headers: corsHeaders });
      }

      if (path === "/api/admin/get-data") {
        const stats = await getStored("STATS", { total_runs: 0, success: 0, failed: 0 });
        const keys = await getStored("KEYS", {});
        const logs = await getStored("LOGS", []);
        return new Response(JSON.stringify({
          success: true,
          config: {
            master_password: config.master_password,
            tg_token: config.tg_token ? "••••••••" : "",
            tg_chat_id: config.tg_chat_id || ""
          },
          stats,
          keys,
          logs
        }), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
      }

      if (path === "/api/admin/update-settings" && request.method === "POST") {
        const data = await request.json();
        if (data.master_password) config.master_password = data.master_password.trim();
        if (data.new_pin) config.admin_pin = data.new_pin.trim();
        if (data.tg_token !== undefined && data.tg_token !== "••••••••") config.tg_token = data.tg_token.trim();
        if (data.tg_chat_id !== undefined) config.tg_chat_id = data.tg_chat_id.trim();
        await setStored("CONFIG", config);
        return new Response(JSON.stringify({ success: true, message: "Settings Updated!" }), { headers: corsHeaders });
      }

      if (path === "/api/admin/create-key" && request.method === "POST") {
        const data = await request.json();
        const key = (data.key || "").trim();
        const client_name = (data.client_name || "").trim();
        const max_uses = parseInt(data.max_uses || 1);

        if (!key) return new Response(JSON.stringify({ success: false, message: "Key required" }), { status: 400, headers: corsHeaders });

        const keys = await getStored("KEYS", {});
        keys[key] = {
          client_name: client_name || "Client",
          max_uses: max_uses,
          used_count: 0,
          active: true,
          created_at: new Date().toLocaleDateString()
        };
        await setStored("KEYS", keys);
        return new Response(JSON.stringify({ success: true, message: `Key ${key} created!` }), { headers: corsHeaders });
      }

      if (path === "/api/admin/delete-key" && request.method === "POST") {
        const data = await request.json();
        const key = data.key;
        const keys = await getStored("KEYS", {});
        delete keys[key];
        await setStored("KEYS", keys);
        return new Response(JSON.stringify({ success: true, message: "Key deleted!" }), { headers: corsHeaders });
      }

      if (path === "/api/admin/clear-logs" && request.method === "POST") {
        await setStored("LOGS", []);
        return new Response(JSON.stringify({ success: true, message: "Logs cleared!" }), { headers: corsHeaders });
      }
    }

    // -------------------------------------------------------------------------
    // 3. ADMIN WEB DASHBOARD UI (Single Page App)
    // -------------------------------------------------------------------------
    return new Response(renderAdminHTML(), {
      headers: { "Content-Type": "text/html; charset=utf-8" }
    });
  }
};

function renderAdminHTML() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>👑 FORIDUL License Manager & Analytics</title>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card: rgba(18, 24, 38, 0.85);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent: #3b82f6;
      --accent-glow: rgba(59, 130, 246, 0.35);
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    body { background-color: var(--bg); color: var(--text); min-height: 100vh; padding: 20px; }
    .container { max-width: 1000px; margin: 0 auto; }
    
    /* Header */
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; padding-bottom: 15px; border-bottom: 1px solid var(--card-border); }
    .header h1 { font-size: 1.5rem; font-weight: 800; background: linear-gradient(135deg, #60a5fa, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .header p { font-size: 0.85rem; color: var(--text-muted); }
    
    /* Login Modal */
    #login-overlay { position: fixed; inset: 0; background: rgba(11, 15, 25, 0.95); display: flex; align-items: center; justify-content: center; z-index: 999; }
    .login-box { background: var(--card); border: 1px solid var(--card-border); padding: 30px; border-radius: 16px; width: 320px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }
    
    /* Cards Grid */
    .grid-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }
    .stat-card { background: var(--card); border: 1px solid var(--card-border); padding: 20px; border-radius: 14px; position: relative; overflow: hidden; backdrop-filter: blur(10px); }
    .stat-card h3 { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
    .stat-card .val { font-size: 2rem; font-weight: 800; color: #fff; }
    
    /* Panels */
    .panel { background: var(--card); border: 1px solid var(--card-border); border-radius: 14px; padding: 22px; margin-bottom: 25px; backdrop-filter: blur(10px); }
    .panel-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }
    
    /* Forms & Inputs */
    .form-row { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
    .input-group { flex: 1; min-width: 200px; }
    label { display: block; font-size: 0.8rem; color: var(--text-muted); margin-bottom: 6px; }
    input { width: 100%; background: rgba(255,255,255,0.04); border: 1px solid var(--card-border); padding: 10px 14px; border-radius: 8px; color: #fff; font-size: 0.9rem; outline: none; }
    input:focus { border-color: var(--accent); box-shadow: 0 0 10px var(--accent-glow); }
    button { background: var(--accent); color: #fff; border: none; padding: 10px 18px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
    button:hover { opacity: 0.9; transform: translateY(-1px); }
    button.btn-danger { background: var(--danger); }
    button.btn-sm { padding: 6px 10px; font-size: 0.75rem; }
    
    /* Table */
    .table-container { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.85rem; }
    th { padding: 10px; color: var(--text-muted); border-bottom: 1px solid var(--card-border); font-weight: 600; }
    td { padding: 12px 10px; border-bottom: 1px solid rgba(255,255,255,0.03); }
    .badge { padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; }
    .badge-success { background: rgba(16, 185, 129, 0.15); color: #34d399; }
    .badge-danger { background: rgba(239, 68, 68, 0.15); color: #f87171; }
    
    .hidden { display: none !important; }
  </style>
</head>
<body>

  <!-- Login Modal -->
  <div id="login-overlay">
    <div class="login-box">
      <h2 style="margin-bottom: 8px;">🔐 Admin Access</h2>
      <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom: 18px;">Default PIN is <b>1234</b></p>
      <input type="password" id="pin-input" placeholder="Enter Admin PIN" style="margin-bottom:15px; text-align:center; font-size:1.2rem; letter-spacing:4px;">
      <button onclick="login()" style="width:100%;">Unlock Dashboard</button>
      <p id="login-err" style="color:var(--danger); font-size:0.8rem; margin-top:10px;" class="hidden">Incorrect PIN!</p>
    </div>
  </div>

  <div class="container hidden" id="dashboard">
    <!-- Header -->
    <div class="header">
      <div>
        <h1>👑 FORIDUL License & Script Tracker</h1>
        <p>Global Cloudflare Edge Security & Real-time Installation Monitor</p>
      </div>
      <div>
        <button onclick="logout()" class="btn-sm" style="background:rgba(255,255,255,0.1);">Logout</button>
      </div>
    </div>

    <!-- Stats Grid -->
    <div class="grid-stats">
      <div class="stat-card">
        <h3>Total Script Runs</h3>
        <div class="val" id="stat-total">0</div>
      </div>
      <div class="stat-card">
        <h3>Successful Installs</h3>
        <div class="val" id="stat-success" style="color:var(--success)">0</div>
      </div>
      <div class="stat-card">
        <h3>Blocked / Failed</h3>
        <div class="val" id="stat-failed" style="color:var(--danger)">0</div>
      </div>
      <div class="stat-card">
        <h3>Active Custom Keys</h3>
        <div class="val" id="stat-keys" style="color:var(--warning)">0</div>
      </div>
    </div>

    <!-- Master Password & Settings -->
    <div class="panel">
      <div class="panel-title">🔑 Master Installation Password & Alerts</div>
      <div class="form-row">
        <div class="input-group">
          <label>Current Master Password (For All Installs)</label>
          <input type="text" id="master-pass" placeholder="e.g. FORIDUL_VIP_2026">
        </div>
        <div class="input-group">
          <label>Telegram Bot Token (Live Alert)</label>
          <input type="text" id="tg-token" placeholder="Optional Telegram Bot Token">
        </div>
        <div class="input-group">
          <label>Telegram Chat ID</label>
          <input type="text" id="tg-chat-id" placeholder="Your Telegram User ID">
        </div>
      </div>
      <div class="form-row">
        <div class="input-group">
          <label>Change Admin PIN (Current: 1234)</label>
          <input type="password" id="new-pin" placeholder="New PIN (Leave blank to keep)">
        </div>
      </div>
      <button onclick="saveSettings()">💾 Save Settings & Update Password</button>
    </div>

    <!-- Custom Client License Keys -->
    <div class="panel">
      <div class="panel-title">
        <span>🏷️ Custom Client Keys (Single or Multi-Use)</span>
      </div>
      <div class="form-row">
        <div class="input-group">
          <label>Client / User Name</label>
          <input type="text" id="new-client-name" placeholder="e.g. Tanvir VPS 1">
        </div>
        <div class="input-group">
          <label>Custom Key (or leave blank to auto-generate)</label>
          <input type="text" id="new-client-key" placeholder="e.g. FORIDUL-VIP-99">
        </div>
        <div class="input-group" style="max-width:140px;">
          <label>Max Installs</label>
          <input type="number" id="new-max-uses" value="1" min="0" placeholder="0 = Unlimited">
        </div>
        <div style="align-self:flex-end;">
          <button onclick="createKey()">➕ Add Key</button>
        </div>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Key Code</th>
              <th>Client</th>
              <th>Allowed Runs</th>
              <th>Times Used</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="keys-table-body">
            <tr><td colspan="5" style="text-align:center;">No custom keys added yet.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Live Execution Logs -->
    <div class="panel">
      <div class="panel-title">
        <span>📋 Live Installation Activity (Last 50 Runs)</span>
        <button onclick="clearLogs()" class="btn-sm btn-danger">Clear History</button>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>VPS IP</th>
              <th>Location</th>
              <th>Key Used</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="logs-table-body">
            <tr><td colspan="5" style="text-align:center;">No activity logged yet.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>

  <script>
    let currentPin = localStorage.getItem("foridul_admin_pin") || "";

    async function login() {
      const pin = document.getElementById("pin-input").value.trim();
      const res = await fetch("/api/admin/get-data", {
        headers: { "X-Admin-Pin": pin }
      });
      if (res.ok) {
        currentPin = pin;
        localStorage.setItem("foridul_admin_pin", pin);
        document.getElementById("login-overlay").classList.add("hidden");
        document.getElementById("dashboard").classList.remove("hidden");
        loadDashboard();
      } else {
        document.getElementById("login-err").classList.remove("hidden");
      }
    }

    function logout() {
      localStorage.removeItem("foridul_admin_pin");
      location.reload();
    }

    async function loadDashboard() {
      try {
        const res = await fetch("/api/admin/get-data", {
          headers: { "X-Admin-Pin": currentPin }
        });
        const data = await res.json();
        if (!data.success) return;

        // Stats
        document.getElementById("stat-total").innerText = data.stats.total_runs;
        document.getElementById("stat-success").innerText = data.stats.success;
        document.getElementById("stat-failed").innerText = data.stats.failed;
        document.getElementById("stat-keys").innerText = Object.keys(data.keys).length;

        // Settings
        document.getElementById("master-pass").value = data.config.master_password;
        document.getElementById("tg-token").value = data.config.tg_token;
        document.getElementById("tg-chat-id").value = data.config.tg_chat_id;

        // Keys Table
        const kb = document.getElementById("keys-table-body");
        kb.innerHTML = "";
        const keyList = Object.entries(data.keys);
        if (keyList.length === 0) {
          kb.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No custom keys yet. (Master password is active)</td></tr>';
        } else {
          keyList.forEach(([k, v]) => {
            const tr = document.createElement("tr");
            const maxStr = v.max_uses === 0 ? "Unlimited" : v.max_uses;
            tr.innerHTML = \`
              <td><code>\${k}</code></td>
              <td><b>\${v.client_name}</b></td>
              <td>\${maxStr}</td>
              <td>\${v.used_count || 0}</td>
              <td><button onclick="deleteKey('\${k}')" class="btn-sm btn-danger">Delete</button></td>
            \`;
            kb.appendChild(tr);
          });
        }

        // Logs Table
        const lb = document.getElementById("logs-table-body");
        lb.innerHTML = "";
        if (data.logs.length === 0) {
          lb.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No script runs yet.</td></tr>';
        } else {
          data.logs.forEach(l => {
            const tr = document.createElement("tr");
            const badgeClass = l.status === "SUCCESS" ? "badge-success" : "badge-danger";
            tr.innerHTML = \`
              <td>\${l.timestamp}</td>
              <td><code>\${l.ip}</code></td>
              <td>\${l.location || 'N/A'}</td>
              <td><code>\${l.key_used}</code> (\${l.label})</td>
              <td><span class="badge \${badgeClass}">\${l.status}</span></td>
            \`;
            lb.appendChild(tr);
          });
        }
      } catch (err) {
        console.error(err);
      }
    }

    async function saveSettings() {
      const master_password = document.getElementById("master-pass").value.trim();
      const tg_token = document.getElementById("tg-token").value.trim();
      const tg_chat_id = document.getElementById("tg-chat-id").value.trim();
      const new_pin = document.getElementById("new-pin").value.trim();

      const res = await fetch("/api/admin/update-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Pin": currentPin },
        body: JSON.stringify({ master_password, tg_token, tg_chat_id, new_pin })
      });
      const d = await res.json();
      if (d.success) {
        alert("✅ Settings Saved Successfully!");
        if (new_pin) {
          currentPin = new_pin;
          localStorage.setItem("foridul_admin_pin", new_pin);
        }
        loadDashboard();
      }
    }

    async function createKey() {
      let key = document.getElementById("new-client-key").value.trim();
      const client_name = document.getElementById("new-client-name").value.trim();
      const max_uses = document.getElementById("new-max-uses").value;

      if (!key) {
        key = "FORIDUL-" + Math.random().toString(36).substring(2, 7).toUpperCase();
      }

      const res = await fetch("/api/admin/create-key", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Pin": currentPin },
        body: JSON.stringify({ key, client_name, max_uses })
      });
      const d = await res.json();
      if (d.success) {
        alert("✅ Key Created: " + key);
        document.getElementById("new-client-key").value = "";
        document.getElementById("new-client-name").value = "";
        loadDashboard();
      }
    }

    async function deleteKey(key) {
      if (!confirm("Are you sure you want to delete key: " + key + "?")) return;
      await fetch("/api/admin/delete-key", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Pin": currentPin },
        body: JSON.stringify({ key })
      });
      loadDashboard();
    }

    async function clearLogs() {
      if (!confirm("Clear all logs?")) return;
      await fetch("/api/admin/clear-logs", {
        method: "POST",
        headers: { "X-Admin-Pin": currentPin }
      });
      loadDashboard();
    }

    // Auto-login if PIN stored
    if (currentPin) {
      document.getElementById("pin-input").value = currentPin;
      login();
    }
  </script>
</body>
</html>`;
}
