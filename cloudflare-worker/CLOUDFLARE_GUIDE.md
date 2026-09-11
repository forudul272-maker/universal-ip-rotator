# 🌐 Cloudflare Worker License Server Setup Guide (2 Minutes)

Host your license server on **Cloudflare Workers** — 100% Free Forever, 0 Maintenance, Never goes offline.

---

### 🚀 Step 1: Create Worker on Cloudflare

1. Login to your [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. In the left sidebar, click on **Compute (Workers & Pages)** ➔ **Overview**.
3. Click **Create Application** ➔ Click **Create Worker**.
4. Give it a name (for example: `foridul-license-manager`).
5. Click **Deploy**.

---

### 💾 Step 2: Create KV Storage (Persistent Database)

1. In the left sidebar, go to **Workers & Pages** ➔ **KV**.
2. Click **Create namespace**.
3. Name it: `LICENSE_KV` and click **Add**.
4. Now go back to your worker: **Workers & Pages** ➔ click on your worker (`foridul-license-manager`).
5. Go to **Settings** tab ➔ **Variables and Secrets** (or **Bindings**).
6. Under **KV Namespace Bindings**, click **Add binding**:
   - Variable name: `LICENSE_KV`
   - KV namespace: select `LICENSE_KV`
7. Click **Save and Deploy**.

---

### 📋 Step 3: Paste Worker Code

1. On your worker page, click **Edit Code** (top right).
2. Delete the default code and copy-paste all code from [worker.js](worker.js).
3. Click **Deploy** (top right).

---

### 🔗 Step 4: Update Your `install.sh`

1. Copy your worker URL (e.g., `https://foridul-license-manager.yourname.workers.dev`).
2. Open `install.sh` in your repo and replace:
   ```bash
   LICENSE_SERVER="https://YOUR_WORKER_SUBDOMAIN.workers.dev"
   ```
   with your actual URL:
   ```bash
   LICENSE_SERVER="https://foridul-license-manager.yourname.workers.dev"
   ```
3. Commit and push to GitHub!

---

### 👑 Step 5: Access Admin Dashboard

Open your worker URL in your mobile or computer browser:
`https://foridul-license-manager.yourname.workers.dev`

- **Default Login PIN:** `1234`
- **Default Master Password:** `FORIDUL_VIP_2026`

**What you can do from the Dashboard:**
1. 🔑 **Change Master Password** anytime with 1 click.
2. 🏷️ **Generate Custom Keys** (e.g. `VIP-TANVIR`, single-use or unlimited).
3. 📊 **View Live Run Count** & successful vs blocked installations.
4. 📋 **Live Audit Table** with exact VPS IP, Country, Timestamp, and Key used.
5. 🔔 **Telegram Alerts:** Add Bot Token & Chat ID to get pinged every time someone installs!
