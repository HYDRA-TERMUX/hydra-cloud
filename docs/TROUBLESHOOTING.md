# Troubleshooting Guide

---

## Server Won't Start

**"Python not found"**
```bash
pkg install python -y
```

**"Flask not installed"**
```bash
pip install flask flask-cors --break-system-packages
```

**"hydra_server.py not found"**
```bash
cp /path/to/hydra_server.py ~/.hydra/hydra_server.py
```

**"Server failed to start — check logs"**
```bash
tail -30 ~/.hydra/hydra.log
```
Common causes: port 8888 already in use, or a Python import error.

---

## Can't Connect from Another Device

**Check the server is running:**
```bash
bash hydra.sh   # option 4 — Status
```

**Check both devices are on the same WiFi** — mobile data or a phone hotspot won't work for LAN mode.

**Find the correct IP:**
```bash
ip route get 1.1.1.1 | grep -oP 'src \K[\d.]+'
```

**Check your laptop's firewall** — allow inbound connections on port 8888:
- Windows: Windows Defender Firewall → Allow an app → add port 8888
- Linux: `sudo ufw allow 8888`

---

## Upload Fails Mid-Transfer

- Check available storage: `df -h ~/storage`
- Check logs: `tail -20 ~/.hydra/hydra.log`
- For large files (>1GB), ensure battery optimization is disabled for Termux
- Try a smaller file first to verify basic connectivity works

---

## Server Stops When Screen Turns Off

Disable battery optimization for Termux:

1. Settings → Apps → Termux → Battery → **Unrestricted**

On Xiaomi/MIUI devices:
- Settings → Battery & Performance → App battery saver → Termux → No restrictions
- Settings → Apps → Manage apps → Termux → Autostart → **Enable**

HYDRA also calls `termux-wake-lock` automatically on startup.

---

## Video Won't Play in Browser

- Use **Chrome or Firefox** — Safari has limited codec support for some formats
- MKV files with uncommon codecs may not play in-browser — use the Download button instead
- Make sure the file uploaded completely (check size in the Files tab)

---

## Storage Permission Denied

```bash
termux-setup-storage
# Tap ALLOW in the dialog, then restart Termux
```

---

## "termux-api not found" Warning

```bash
pkg install termux-api -y
```

Also install the companion app [Termux:API](https://f-droid.org/packages/com.termux.api/) from F-Droid.

---

## Port Already in Use

```bash
# Find what's using 8888
ss -tlnp | grep 8888

# Kill existing HYDRA processes
pkill -f hydra_server.py

# Or change the port — edit hydra.sh line:  PORT=8888  →  PORT=9999
```

---

## Full Reset

```bash
pkill -f hydra_server.py   # Stop server
rm ~/.hydra/hydra.log      # Clear logs
bash hydra.sh              # Re-run option 1 (setup)
```

---

## Getting Help

Open an [issue on GitHub](https://github.com/YOUR_USERNAME/hydra-cloud/issues) using the Bug Report template. Include:

- Android version and device model
- Termux version: `termux-info | head -5`
- Last 30 log lines: `tail -30 ~/.hydra/hydra.log`
- Steps to reproduce the problem
