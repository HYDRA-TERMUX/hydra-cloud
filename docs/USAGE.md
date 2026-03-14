# Usage Guide

---

## Starting the Server

```bash
bash hydra.sh
```

### Menu Options

| Option | Description |
|--------|-------------|
| `1` | First-time setup — installs all dependencies |
| `2` | Start server (LAN + localhost) — recommended |
| `3` | Start localhost only — private, phone only |
| `4` | Server status — check if running, show storage info |
| `5` | Speed test — WiFi link speed and disk write speed |
| `6` | View logs — last 50 lines of the server log |
| `7` | Stop everything — kill the server process |
| `8` | Exit |

---

## Web Interface Tabs

Open `http://192.168.x.x:8888` in any browser on the same WiFi.

### Files Tab

- Lists all uploaded files sorted newest first
- Shows filename, size, date, and file type icon
- Click any filename to download it directly
- Video/audio/image files show a **▶ Play** button for in-browser streaming
- **Delete** button permanently removes a file

### Upload Tab

- Drag-and-drop files onto the drop zone, or click to browse
- Multiple files can be selected at once
- Real-time progress bar shows live speed, bytes transferred, and peak speed

### Health Tab

Live device monitoring updated every 30 seconds:

- 🔋 Battery percentage, status, temperature, plug type
- 🧠 RAM used / total with percentage bar
- 💾 Storage used / free / total
- 📶 WiFi SSID, link speed (Mbps), signal (RSSI dBm)
- 🌡️ CPU temperature
- ⏱️ System uptime

---

## Transferring Files

**Laptop → Phone (upload):**
1. Open the web UI on your laptop browser
2. Go to Upload tab, drag and drop files
3. Files save to phone storage at `~/storage/shared/HYDRACloud/`

**Phone → Laptop (download):**
1. Open the web UI on your laptop browser
2. Click any filename in the Files tab

**Streaming video/audio:**
1. Open the web UI on any device
2. Click ▶ next to a media file
3. In-browser player opens with full seek support

Supported formats: MP4, MKV, WebM, AVI, MOV, MP3, FLAC, WAV, OGG, M4A, AAC, and more.

---

## Tips for Maximum Speed

- Use **5GHz WiFi** — significantly faster than 2.4GHz
- Keep the phone **plugged in** to prevent CPU throttling
- Close background apps during large transfers
- Stay within good range of your router
- HYDRA streams in 8MB chunks internally for best throughput

---

## File Storage Location

Uploaded files are saved to:
```
~/storage/shared/HYDRACloud/
```

On Android this is accessible as `/sdcard/HYDRACloud/` in any file manager app.

---

## Running in Background

HYDRA acquires a wake lock on startup (`termux-wake-lock`) to stay alive with the screen off.

To keep the Termux session alive:
- Swipe down from Termux's notification to keep the session running
- Ensure battery optimization is disabled (see [INSTALL.md](INSTALL.md))

---

## API Usage Examples

```bash
# List all files (JSON)
curl http://192.168.x.x:8888/api/files

# Upload a file
curl -X POST -F "file=@/path/to/video.mp4" http://192.168.x.x:8888/upload

# Download a file
curl -O http://192.168.x.x:8888/download/video.mp4

# Get device health (JSON)
curl http://192.168.x.x:8888/api/health

# Delete a file
curl -X DELETE http://192.168.x.x:8888/delete/video.mp4
```
