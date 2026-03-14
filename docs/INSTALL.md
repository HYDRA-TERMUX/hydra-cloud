# Installation Guide

Complete step-by-step installation for first-time users.

---

## Prerequisites

### Install Termux (F-Droid version only)

> ⚠️ Do NOT use the Play Store version — it is outdated and broken.

1. Install [F-Droid](https://f-droid.org) on your Android device
2. Open F-Droid, search for **Termux**, install it
3. Open Termux

Direct link: https://f-droid.org/packages/com.termux/

---

## Installation Steps

### Step 1 — Update Termux packages

```bash
pkg update -y && pkg upgrade -y
```

### Step 2 — Install git

```bash
pkg install git -y
```

### Step 3 — Clone HYDRA

```bash
git clone https://github.com/YOUR_USERNAME/hydra-cloud
cd hydra-cloud
```

### Step 4 — Make launcher executable

```bash
chmod +x hydra.sh
```

### Step 5 — Run first-time setup

```bash
bash hydra.sh
```

Select **option 1 — First-time setup**.

This automatically:
- Updates Termux packages
- Installs Python, curl, wget, termux-api, iproute2
- Grants storage permissions (tap ALLOW when prompted)
- Installs Flask and flask-cors via pip
- Copies `hydra_server.py` to `~/.hydra/`
- Creates `~/storage/shared/HYDRACloud/` upload folder

---

## After Installation: Disable Battery Optimization

For the server to stay alive when your screen is off, disable battery optimization for Termux:

1. Android **Settings** → **Apps** → **Termux** → **Battery**
2. Select **Unrestricted** (or "Don't optimize")
3. Also disable **Auto-start management** if present

> On Xiaomi/Redmi/MIUI: Settings → Battery & Performance → App battery saver → Termux → No restrictions

---

## Starting HYDRA

```bash
bash hydra.sh
# Select option 2
```

Output:
```
  ✓  HYDRA engine started (PID 12345)

  HYDRA is running on your network!

  This phone:   http://127.0.0.1:8888
  WiFi LAN:     http://192.168.1.105:8888
  Upload dir:   /data/data/com.termux/files/home/storage/shared/HYDRACloud
```

Open the **WiFi LAN URL** on any device on the same WiFi.

---

## Verifying Everything Works

```bash
python --version           # Should print Python 3.x
python -c "import flask; print('Flask OK')"
ls ~/.hydra/hydra_server.py
```

---

## Updating HYDRA

```bash
cd hydra-cloud
git pull
cp hydra_server.py ~/.hydra/hydra_server.py
```

---

## Uninstalling

```bash
bash hydra.sh   # Option 7 — stop server first
rm -rf ~/.hydra
# Optionally remove uploaded files:
rm -rf ~/storage/shared/HYDRACloud
```
