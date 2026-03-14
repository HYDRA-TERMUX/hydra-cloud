#!/usr/bin/env python3
# ============================================================
#  HYDRA Cloud Server — High-Speed File Server
#  Upload · Download · Stream · Device Health
#  Optimized for maximum WiFi throughput
# ============================================================

import os, time, math, mimetypes, json, subprocess, threading, stat
from pathlib import Path
from flask import (Flask, request, send_from_directory, jsonify,
                   render_template_string, Response, stream_with_context)
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.expanduser("~/storage/shared/HYDRACloud")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH']    = 32 * 1024 * 1024 * 1024  # 32GB
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# ── SPEED TUNING ─────────────────────────────────────────────
CHUNK_SIZE     = 8 * 1024 * 1024   # 8MB chunks for streaming
UPLOAD_THREADS = 4

def human_size(b):
    if b == 0: return "0 B"
    units = ["B","KB","MB","GB","TB"]
    i = min(int(math.floor(math.log(max(b,1), 1024))), 4)
    return f"{b/(1024**i):.1f} {units[i]}"

def get_mime(name):
    m, _ = mimetypes.guess_type(name)
    return m or "application/octet-stream"

def is_video(name):
    m = get_mime(name)
    return m.startswith("video/") or name.lower().endswith(
        ('.mp4','.mkv','.webm','.avi','.mov','.m4v','.3gp','.flv'))

def is_audio(name):
    m = get_mime(name)
    return m.startswith("audio/") or name.lower().endswith(
        ('.mp3','.flac','.wav','.ogg','.m4a','.aac','.opus','.wma'))

def is_image(name):
    m = get_mime(name)
    return m.startswith("image/") or name.lower().endswith(
        ('.jpg','.jpeg','.png','.gif','.webp','.bmp','.svg','.heic','.avif'))

def media_type(name):
    if is_video(name): return "video"
    if is_audio(name): return "audio"
    if is_image(name): return "image"
    return "file"

def get_files():
    files = []
    try:
        for f in sorted(Path(UPLOAD_FOLDER).iterdir(),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file():
                s = f.stat()
                files.append({
                    "name":     f.name,
                    "size":     human_size(s.st_size),
                    "bytes":    s.st_size,
                    "modified": time.strftime("%d %b %Y, %H:%M",
                                             time.localtime(s.st_mtime)),
                    "type":     media_type(f.name),
                    "mime":     get_mime(f.name),
                })
    except Exception:
        pass
    return files

def get_device_health():
    health = {}
    try:
        # Battery level
        bat = subprocess.run(
            ["termux-battery-status"], capture_output=True, text=True, timeout=3)
        if bat.returncode == 0:
            bd = json.loads(bat.stdout)
            health["battery_pct"]    = bd.get("percentage", 0)
            health["battery_status"] = bd.get("status", "unknown").lower()
            health["battery_temp"]   = bd.get("temperature", 0)
            health["plugged"]        = bd.get("plugged", "unknown")
        else:
            # fallback read from sysfs
            for p in ["/sys/class/power_supply/battery/capacity",
                      "/sys/class/power_supply/BAT0/capacity"]:
                if os.path.exists(p):
                    health["battery_pct"] = int(open(p).read().strip())
                    break
    except Exception:
        health["battery_pct"] = 0

    try:
        # CPU temp
        for p in ["/sys/class/thermal/thermal_zone0/temp",
                  "/sys/class/thermal/thermal_zone1/temp"]:
            if os.path.exists(p):
                health["cpu_temp"] = round(int(open(p).read().strip()) / 1000, 1)
                break
    except Exception:
        health["cpu_temp"] = 0

    try:
        # RAM
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                k, v = line.split(":")
                mem[k.strip()] = int(v.strip().split()[0])
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", 0)
        used  = total - avail
        health["ram_total"]   = human_size(total * 1024)
        health["ram_used"]    = human_size(used * 1024)
        health["ram_pct"]     = round(used / max(total, 1) * 100)
    except Exception:
        health["ram_total"] = health["ram_used"] = "?"
        health["ram_pct"] = 0

    try:
        # Storage
        sv = os.statvfs(UPLOAD_FOLDER)
        total_s = sv.f_blocks * sv.f_frsize
        free_s  = sv.f_bavail * sv.f_frsize
        used_s  = total_s - free_s
        health["storage_total"] = human_size(total_s)
        health["storage_used"]  = human_size(used_s)
        health["storage_free"]  = human_size(free_s)
        health["storage_pct"]   = round(used_s / max(total_s, 1) * 100)
    except Exception:
        health["storage_total"] = health["storage_free"] = "?"
        health["storage_pct"] = 0

    try:
        # WiFi info
        wifi = subprocess.run(
            ["termux-wifi-connectioninfo"], capture_output=True, text=True, timeout=3)
        if wifi.returncode == 0:
            wd = json.loads(wifi.stdout)
            health["wifi_ssid"]  = wd.get("ssid", "unknown")
            health["wifi_speed"] = wd.get("link_speed_mbps", 0)
            health["wifi_rssi"]  = wd.get("rssi", 0)
    except Exception:
        health["wifi_ssid"]  = "unknown"
        health["wifi_speed"] = 0
        health["wifi_rssi"]  = 0

    try:
        # Uptime
        with open("/proc/uptime") as f:
            up = float(f.read().split()[0])
        h, m = divmod(int(up), 3600)
        m //= 60
        health["uptime"] = f"{h}h {m}m"
    except Exception:
        health["uptime"] = "?"

    return health

# ── ROUTES ───────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/files")
def api_files():
    files = get_files()
    total = sum(f["bytes"] for f in files)
    try:
        sv = os.statvfs(UPLOAD_FOLDER)
        free = sv.f_bavail * sv.f_frsize
    except Exception:
        free = 0
    return jsonify({
        "files":      files,
        "count":      len(files),
        "total_size": human_size(total),
        "free_space": human_size(free),
    })

@app.route("/api/health")
def api_health():
    return jsonify(get_device_health())

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part"})
    f = request.files["file"]
    if not f.filename:
        return jsonify({"success": False, "error": "Empty filename"})
    safe = secure_filename(f.filename)
    dest = os.path.join(UPLOAD_FOLDER, safe)
    base, ext = os.path.splitext(safe)
    c = 1
    while os.path.exists(dest):
        dest = os.path.join(UPLOAD_FOLDER, f"{base}_{c}{ext}")
        c += 1
    # Write in large chunks for speed
    with open(dest, "wb") as out:
        while True:
            buf = f.stream.read(CHUNK_SIZE)
            if not buf:
                break
            out.write(buf)
    fsize = os.path.getsize(dest)
    return jsonify({"success": True, "filename": os.path.basename(dest),
                    "size": human_size(fsize)})

@app.route("/download/<path:filename>")
def download(filename):
    safe = os.path.basename(filename)
    fpath = os.path.join(UPLOAD_FOLDER, safe)
    if not os.path.exists(fpath):
        return "Not found", 404

    fsize = os.path.getsize(fpath)
    mime  = get_mime(safe)
    range_header = request.headers.get("Range")

    def generate_full():
        with open(fpath, "rb") as fh:
            while True:
                buf = fh.read(CHUNK_SIZE)
                if not buf:
                    break
                yield buf

    def generate_range(start, end):
        with open(fpath, "rb") as fh:
            fh.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                buf = fh.read(min(CHUNK_SIZE, remaining))
                if not buf:
                    break
                remaining -= len(buf)
                yield buf

    # Range request (for video seeking / resumable download)
    if range_header:
        ranges = range_header.replace("bytes=", "").split("-")
        start = int(ranges[0]) if ranges[0] else 0
        end   = int(ranges[1]) if ranges[1] else fsize - 1
        end   = min(end, fsize - 1)
        length = end - start + 1
        resp = Response(
            stream_with_context(generate_range(start, end)),
            206,
            headers={
                "Content-Range":       f"bytes {start}-{end}/{fsize}",
                "Accept-Ranges":       "bytes",
                "Content-Length":      str(length),
                "Content-Type":        mime,
                "Content-Disposition": f'inline; filename="{safe}"',
                "Cache-Control":       "no-cache",
                "X-Accel-Buffering":   "no",
            },
            direct_passthrough=True,
        )
        return resp

    # Full download — with speed headers
    resp = Response(
        stream_with_context(generate_full()),
        200,
        headers={
            "Content-Length":      str(fsize),
            "Content-Type":        mime,
            "Content-Disposition": f'attachment; filename="{safe}"',
            "Accept-Ranges":       "bytes",
            "Cache-Control":       "no-cache",
            "X-Accel-Buffering":   "no",
        },
        direct_passthrough=True,
    )
    return resp

@app.route("/stream/<path:filename>")
def stream_media(filename):
    """Streaming endpoint for in-browser media player with range support."""
    safe  = os.path.basename(filename)
    fpath = os.path.join(UPLOAD_FOLDER, safe)
    if not os.path.exists(fpath):
        return "Not found", 404
    fsize = os.path.getsize(fpath)
    mime  = get_mime(safe)
    range_header = request.headers.get("Range")

    def gen(start, end):
        with open(fpath, "rb") as fh:
            fh.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                buf = fh.read(min(CHUNK_SIZE, remaining))
                if not buf:
                    break
                remaining -= len(buf)
                yield buf

    start = 0
    end   = fsize - 1
    status = 200
    if range_header:
        parts = range_header.replace("bytes=", "").split("-")
        start = int(parts[0]) if parts[0] else 0
        end   = int(parts[1]) if parts[1] else fsize - 1
        end   = min(end, fsize - 1)
        status = 206

    length = end - start + 1
    headers = {
        "Content-Type":      mime,
        "Content-Length":    str(length),
        "Accept-Ranges":     "bytes",
        "Cache-Control":     "no-cache",
        "X-Accel-Buffering": "no",
    }
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{fsize}"

    return Response(stream_with_context(gen(start, end)),
                    status=status, headers=headers, direct_passthrough=True)

@app.route("/delete/<path:filename>", methods=["DELETE"])
def delete(filename):
    safe  = os.path.basename(filename)
    fpath = os.path.join(UPLOAD_FOLDER, safe)
    if os.path.exists(fpath):
        os.remove(fpath)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Not found"})

# ── HTML FRONTEND ─────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HYDRA Cloud</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg:       #050810;
  --bg2:      #080d18;
  --bg3:      #0c1220;
  --card:     #0f1628;
  --border:   #1a2540;
  --border2:  #243050;
  --accent:   #00d4ff;
  --accent2:  #0090cc;
  --green:    #00ff88;
  --red:      #ff3d5a;
  --amber:    #ffb800;
  --purple:   #a855f7;
  --text:     #e2eaf5;
  --muted:    #6b82a8;
  --dim:      #3a4d6e;
  --font-hd:  'Rajdhani', sans-serif;
  --font-mono:'JetBrains Mono', monospace;
  --font-body:'Inter', sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:var(--font-body);min-height:100vh;overflow-x:hidden}

/* Grid background */
body::before{
  content:'';position:fixed;inset:0;
  background-image:
    linear-gradient(rgba(0,212,255,.03) 1px,transparent 1px),
    linear-gradient(90deg,rgba(0,212,255,.03) 1px,transparent 1px);
  background-size:40px 40px;
  pointer-events:none;z-index:0
}

/* ── HEADER ── */
.header{
  position:relative;
  background:linear-gradient(180deg,#060c1a 0%,var(--bg) 100%);
  border-bottom:1px solid var(--border);
  padding:0 24px;
  display:flex;align-items:center;justify-content:space-between;
  height:64px;z-index:10
}
.logo{display:flex;align-items:center;gap:12px}
.logo-icon{
  width:38px;height:38px;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  border-radius:8px;display:flex;align-items:center;justify-content:center;
  font-size:20px;box-shadow:0 0 20px rgba(0,212,255,.4)
}
.logo-text{font-family:var(--font-hd);font-size:26px;font-weight:700;
  letter-spacing:3px;color:var(--accent);text-shadow:0 0 20px rgba(0,212,255,.5)}
.logo-sub{font-family:var(--font-mono);font-size:9px;color:var(--muted);
  letter-spacing:2px;text-transform:uppercase;margin-top:1px}
.header-status{display:flex;align-items:center;gap:8px;
  font-family:var(--font-mono);font-size:11px;color:var(--muted)}
.status-dot{width:6px;height:6px;border-radius:50%;background:var(--green);
  box-shadow:0 0 6px var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}

/* ── TABS ── */
.tabs{
  display:flex;gap:0;
  border-bottom:1px solid var(--border);
  background:var(--bg2);
  position:sticky;top:0;z-index:9;
  padding:0 24px;
}
.tab{
  padding:14px 20px;
  font-family:var(--font-hd);font-size:14px;font-weight:600;
  letter-spacing:1px;text-transform:uppercase;color:var(--muted);
  cursor:pointer;border-bottom:2px solid transparent;
  transition:all .2s;white-space:nowrap
}
.tab:hover{color:var(--text)}
.tab.active{color:var(--accent);border-bottom-color:var(--accent)}

/* ── MAIN ── */
.main{padding:24px;max-width:1100px;margin:0 auto;position:relative;z-index:1}
.panel{display:none}.panel.active{display:block}

/* ── UPLOAD ZONE ── */
.upload-zone{
  border:2px dashed var(--border2);border-radius:16px;
  padding:48px 24px;text-align:center;
  background:linear-gradient(135deg,rgba(0,212,255,.03),rgba(0,0,0,0));
  cursor:pointer;transition:all .3s;margin-bottom:24px;position:relative;overflow:hidden
}
.upload-zone::before{
  content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse at 50% 0%,rgba(0,212,255,.08),transparent 70%);
  opacity:0;transition:opacity .3s
}
.upload-zone:hover::before,.upload-zone.drag::before{opacity:1}
.upload-zone:hover,.upload-zone.drag{border-color:var(--accent);background:rgba(0,212,255,.05)}
.upload-icon{font-size:48px;margin-bottom:16px;filter:drop-shadow(0 0 12px rgba(0,212,255,.4))}
.upload-title{font-family:var(--font-hd);font-size:22px;font-weight:700;
  color:var(--accent);letter-spacing:2px;margin-bottom:8px}
.upload-hint{font-size:13px;color:var(--muted);line-height:1.6}
.upload-btn{
  display:inline-flex;align-items:center;gap:8px;
  margin-top:20px;padding:12px 28px;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  color:#000;font-family:var(--font-hd);font-size:15px;font-weight:700;
  letter-spacing:1px;border:none;border-radius:8px;cursor:pointer;
  box-shadow:0 0 24px rgba(0,212,255,.4);transition:all .2s
}
.upload-btn:hover{transform:translateY(-1px);box-shadow:0 0 32px rgba(0,212,255,.6)}
#file-input{display:none}

/* ── PROGRESS ── */
.progress-wrap{
  background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:20px;margin-bottom:20px;display:none
}
.progress-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.progress-label{font-family:var(--font-mono);font-size:12px;color:var(--accent)}
.progress-speed{font-family:var(--font-mono);font-size:12px;color:var(--green)}
.progress-bg{height:6px;background:var(--bg3);border-radius:3px;overflow:hidden;margin-bottom:8px}
.progress-fill{height:100%;width:0%;
  background:linear-gradient(90deg,var(--accent2),var(--accent));
  border-radius:3px;transition:width .2s;
  box-shadow:0 0 8px var(--accent)}
.progress-info{display:flex;justify-content:space-between;
  font-family:var(--font-mono);font-size:11px;color:var(--muted)}

/* ── STATS ROW ── */
.stats-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}
.stat-card{
  background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:16px;display:flex;flex-direction:column;gap:4px
}
.stat-label{font-family:var(--font-mono);font-size:10px;color:var(--muted);
  letter-spacing:1px;text-transform:uppercase}
.stat-val{font-family:var(--font-hd);font-size:22px;font-weight:700;color:var(--text)}
.stat-sub{font-size:11px;color:var(--muted)}

/* ── FILTER BAR ── */
.filter-bar{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.filter-btn{
  padding:6px 14px;border-radius:20px;font-size:12px;font-weight:500;
  cursor:pointer;border:1px solid var(--border);background:transparent;
  color:var(--muted);transition:all .2s;font-family:var(--font-body)
}
.filter-btn:hover{border-color:var(--border2);color:var(--text)}
.filter-btn.active{background:var(--accent);color:#000;border-color:var(--accent);font-weight:600}
.search-box{
  flex:1;min-width:160px;padding:6px 14px;
  background:var(--card);border:1px solid var(--border);border-radius:20px;
  color:var(--text);font-size:12px;font-family:var(--font-mono);outline:none
}
.search-box:focus{border-color:var(--accent)}

/* ── FILE LIST ── */
.file-list{display:flex;flex-direction:column;gap:8px}
.file-item{
  background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:14px 16px;display:flex;align-items:center;gap:14px;
  transition:all .2s;cursor:default
}
.file-item:hover{border-color:var(--border2);background:#121929}
.file-thumb{
  width:48px;height:48px;border-radius:8px;flex-shrink:0;
  background:var(--bg3);border:1px solid var(--border);
  display:flex;align-items:center;justify-content:center;font-size:22px;
  overflow:hidden;position:relative
}
.file-thumb img{width:100%;height:100%;object-fit:cover}
.file-info{flex:1;min-width:0}
.file-name{font-size:14px;font-weight:500;color:var(--text);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-bottom:3px}
.file-meta{font-family:var(--font-mono);font-size:11px;color:var(--muted)}
.type-badge{
  font-family:var(--font-mono);font-size:9px;font-weight:500;
  padding:2px 7px;border-radius:4px;margin-left:8px;text-transform:uppercase;letter-spacing:1px
}
.badge-video{background:rgba(168,85,247,.2);color:#c084fc;border:1px solid rgba(168,85,247,.3)}
.badge-audio{background:rgba(0,255,136,.15);color:var(--green);border:1px solid rgba(0,255,136,.2)}
.badge-image{background:rgba(255,184,0,.15);color:var(--amber);border:1px solid rgba(255,184,0,.2)}
.badge-file{background:rgba(0,212,255,.1);color:var(--accent);border:1px solid rgba(0,212,255,.2)}

.file-actions{display:flex;gap:6px;flex-shrink:0}
.btn{
  padding:7px 14px;border-radius:6px;font-size:12px;font-weight:500;
  cursor:pointer;border:none;text-decoration:none;display:inline-flex;
  align-items:center;gap:5px;transition:all .2s;white-space:nowrap;
  font-family:var(--font-body)
}
.btn-play{background:rgba(168,85,247,.2);color:#c084fc;border:1px solid rgba(168,85,247,.4)}
.btn-play:hover{background:rgba(168,85,247,.4)}
.btn-dl{background:rgba(0,212,255,.1);color:var(--accent);border:1px solid rgba(0,212,255,.3)}
.btn-dl:hover{background:rgba(0,212,255,.2)}
.btn-del{background:rgba(255,61,90,.1);color:var(--red);border:1px solid rgba(255,61,90,.3)}
.btn-del:hover{background:rgba(255,61,90,.2)}

.empty{text-align:center;padding:60px;color:var(--muted);font-size:14px}
.empty-icon{font-size:48px;margin-bottom:12px;opacity:.3}

/* ── MEDIA PLAYER ── */
.player-modal{
  display:none;position:fixed;inset:0;z-index:100;
  background:rgba(0,0,0,.92);backdrop-filter:blur(8px);
  align-items:center;justify-content:center;flex-direction:column
}
.player-modal.open{display:flex}
.player-wrap{
  width:min(90vw,900px);background:var(--bg2);border:1px solid var(--border);
  border-radius:16px;overflow:hidden;position:relative
}
.player-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:14px 20px;border-bottom:1px solid var(--border)
}
.player-title{font-family:var(--font-hd);font-size:16px;font-weight:600;
  color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:70%}
.player-close{
  width:32px;height:32px;border-radius:8px;background:rgba(255,61,90,.15);
  color:var(--red);border:1px solid rgba(255,61,90,.3);cursor:pointer;
  display:flex;align-items:center;justify-content:center;font-size:18px;
  transition:all .2s;flex-shrink:0
}
.player-close:hover{background:rgba(255,61,90,.3)}
.player-body{padding:0}

video#main-video{width:100%;max-height:70vh;display:block;background:#000}
audio#main-audio{width:100%;margin:20px 0;display:block}
#image-viewer{text-align:center;padding:20px}
#image-viewer img{max-width:100%;max-height:70vh;border-radius:8px;object-fit:contain}

.audio-art{
  padding:40px;text-align:center;background:linear-gradient(135deg,var(--bg3),var(--bg2))
}
.audio-disc{
  width:120px;height:120px;border-radius:50%;
  background:linear-gradient(135deg,var(--accent2),var(--purple));
  margin:0 auto 20px;display:flex;align-items:center;justify-content:center;
  font-size:48px;box-shadow:0 0 40px rgba(0,212,255,.3);
  animation:spin 8s linear infinite;animation-play-state:paused
}
.audio-disc.playing{animation-play-state:running}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── HEALTH PANEL ── */
.health-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.health-card{
  background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px
}
.health-card-title{
  font-family:var(--font-hd);font-size:13px;font-weight:600;
  letter-spacing:2px;text-transform:uppercase;color:var(--muted);margin-bottom:16px;
  display:flex;align-items:center;gap:8px
}
.health-card-title span{font-size:16px}
.gauge-row{display:flex;align-items:center;gap:12px;margin-bottom:10px}
.gauge-label{font-size:12px;color:var(--muted);min-width:80px}
.gauge-bg{flex:1;height:8px;background:var(--bg3);border-radius:4px;overflow:hidden}
.gauge-fill{height:100%;border-radius:4px;transition:width .6s ease}
.gauge-val{font-family:var(--font-mono);font-size:12px;min-width:42px;text-align:right}
.health-big{font-family:var(--font-hd);font-size:40px;font-weight:700;line-height:1}
.health-big-label{font-size:12px;color:var(--muted);margin-top:4px}
.health-row{display:flex;justify-content:space-between;align-items:center;
  padding:8px 0;border-bottom:1px solid var(--border)}
.health-row:last-child{border:none}
.health-row-key{font-size:12px;color:var(--muted)}
.health-row-val{font-family:var(--font-mono);font-size:12px;color:var(--text)}
.bat-icon{font-size:28px}
.wifi-signal{display:flex;align-items:flex-end;gap:2px;height:16px}
.wifi-bar{width:4px;border-radius:2px;background:var(--dim)}
.wifi-bar.on{background:var(--green)}

/* ── SPEED MONITOR ── */
.speed-panel{
  background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:20px;margin-bottom:24px
}
.speed-row{display:flex;gap:20px;flex-wrap:wrap}
.speed-item{flex:1;min-width:140px;text-align:center}
.speed-val{font-family:var(--font-hd);font-size:32px;font-weight:700;color:var(--accent)}
.speed-label{font-family:var(--font-mono);font-size:10px;color:var(--muted);
  letter-spacing:1px;text-transform:uppercase;margin-top:2px}

/* ── TOAST ── */
.toast{
  position:fixed;bottom:24px;right:24px;z-index:200;
  background:var(--card);border:1px solid var(--border);
  border-radius:10px;padding:12px 18px;font-size:13px;
  display:none;animation:toastin .3s ease;
  box-shadow:0 8px 32px rgba(0,0,0,.5);
  font-family:var(--font-body)
}
@keyframes toastin{from{transform:translateY(16px);opacity:0}to{transform:translateY(0);opacity:1}}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px}

@media(max-width:600px){
  .file-actions{flex-direction:column}
  .tabs{padding:0 12px}
  .tab{padding:12px 12px;font-size:12px}
  .main{padding:16px}
  .stats-row{grid-template-columns:1fr 1fr}
}
</style>
</head>
<body>

<div class="header">
  <div class="logo">
    <div class="logo-icon">⚡</div>
    <div>
      <div class="logo-text">HYDRA</div>
      <div class="logo-sub">Cloud Server</div>
    </div>
  </div>
  <div class="header-status">
    <div class="status-dot"></div>
    <span id="header-ip">ONLINE</span>
  </div>
</div>

<div class="tabs">
  <div class="tab active" onclick="switchTab('files')">📁 Files</div>
  <div class="tab" onclick="switchTab('upload')">⬆ Upload</div>
  <div class="tab" onclick="switchTab('health')">💻 Device</div>
</div>

<!-- ── FILES PANEL ── -->
<div class="main">
<div id="panel-files" class="panel active">
  <div class="stats-row" id="stats-row">
    <div class="stat-card">
      <div class="stat-label">Total Files</div>
      <div class="stat-val" id="s-count">—</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Used Space</div>
      <div class="stat-val" id="s-used">—</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Free Space</div>
      <div class="stat-val" id="s-free">—</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Last Updated</div>
      <div class="stat-val" id="s-time" style="font-size:16px">—</div>
    </div>
  </div>

  <div class="filter-bar">
    <button class="filter-btn active" onclick="setFilter('all',this)">All</button>
    <button class="filter-btn" onclick="setFilter('video',this)">🎬 Videos</button>
    <button class="filter-btn" onclick="setFilter('audio',this)">🎵 Music</button>
    <button class="filter-btn" onclick="setFilter('image',this)">🖼 Images</button>
    <button class="filter-btn" onclick="setFilter('file',this)">📄 Docs</button>
    <input class="search-box" id="search-box" placeholder="Search files…" oninput="renderFiles()">
  </div>

  <div class="file-list" id="file-list">
    <div class="empty"><div class="empty-icon">📭</div>Loading files…</div>
  </div>
</div>

<!-- ── UPLOAD PANEL ── -->
<div id="panel-upload" class="panel">
  <div class="upload-zone" id="drop-zone"
       onclick="document.getElementById('file-input').click()">
    <div class="upload-icon">⚡</div>
    <div class="upload-title">HYDRA UPLOAD</div>
    <div class="upload-hint">
      Drop files here or tap to browse<br>
      Photos · Videos · Music · Documents · APKs · Any file up to 32GB
    </div>
    <input type="file" id="file-input" multiple onchange="uploadFiles(this.files)">
    <button class="upload-btn"
            onclick="event.stopPropagation();document.getElementById('file-input').click()">
      ⚡ Choose Files
    </button>
  </div>

  <div class="progress-wrap" id="progress-wrap">
    <div class="progress-header">
      <span class="progress-label" id="prog-label">Uploading…</span>
      <span class="progress-speed" id="prog-speed"></span>
    </div>
    <div class="progress-bg"><div class="progress-fill" id="prog-bar"></div></div>
    <div class="progress-info">
      <span id="prog-transferred"></span>
      <span id="prog-pct">0%</span>
    </div>
  </div>

  <div class="speed-panel" id="speed-panel" style="display:none">
    <div style="font-family:var(--font-hd);font-size:12px;letter-spacing:2px;
      color:var(--muted);text-transform:uppercase;margin-bottom:16px">Last Transfer Stats</div>
    <div class="speed-row">
      <div class="speed-item">
        <div class="speed-val" id="spd-avg">—</div>
        <div class="speed-label">Avg Speed</div>
      </div>
      <div class="speed-item">
        <div class="speed-val" id="spd-peak">—</div>
        <div class="speed-label">Peak Speed</div>
      </div>
      <div class="speed-item">
        <div class="speed-val" id="spd-time">—</div>
        <div class="speed-label">Duration</div>
      </div>
      <div class="speed-item">
        <div class="speed-val" id="spd-size">—</div>
        <div class="speed-label">File Size</div>
      </div>
    </div>
  </div>
</div>

<!-- ── HEALTH PANEL ── -->
<div id="panel-health" class="panel">
  <div class="health-grid" id="health-grid">
    <div class="health-card">
      <div class="health-card-title"><span>🔋</span> Battery</div>
      <div style="display:flex;align-items:center;gap:20px">
        <div class="bat-icon" id="bat-icon">🔋</div>
        <div>
          <div class="health-big" id="bat-pct">—</div>
          <div class="health-big-label" id="bat-status">Loading…</div>
        </div>
      </div>
      <div style="margin-top:16px">
        <div class="gauge-row">
          <span class="gauge-label">Charge</span>
          <div class="gauge-bg"><div class="gauge-fill" id="bat-bar" style="background:var(--green);width:0%"></div></div>
          <span class="gauge-val" id="bat-pct2">—</span>
        </div>
      </div>
      <div class="health-row"><span class="health-row-key">Temperature</span><span class="health-row-val" id="bat-temp">—</span></div>
      <div class="health-row"><span class="health-row-key">Power source</span><span class="health-row-val" id="bat-plug">—</span></div>
    </div>

    <div class="health-card">
      <div class="health-card-title"><span>🧠</span> Memory (RAM)</div>
      <div class="gauge-row">
        <span class="gauge-label">Used</span>
        <div class="gauge-bg"><div class="gauge-fill" id="ram-bar" style="background:var(--accent);width:0%"></div></div>
        <span class="gauge-val" id="ram-pct">—</span>
      </div>
      <div class="health-row"><span class="health-row-key">Used</span><span class="health-row-val" id="ram-used">—</span></div>
      <div class="health-row"><span class="health-row-key">Total</span><span class="health-row-val" id="ram-total">—</span></div>
    </div>

    <div class="health-card">
      <div class="health-card-title"><span>💾</span> Storage</div>
      <div class="gauge-row">
        <span class="gauge-label">Used</span>
        <div class="gauge-bg"><div class="gauge-fill" id="stor-bar" style="background:var(--amber);width:0%"></div></div>
        <span class="gauge-val" id="stor-pct">—</span>
      </div>
      <div class="health-row"><span class="health-row-key">Used</span><span class="health-row-val" id="stor-used">—</span></div>
      <div class="health-row"><span class="health-row-key">Free</span><span class="health-row-val" id="stor-free">—</span></div>
      <div class="health-row"><span class="health-row-key">Total</span><span class="health-row-val" id="stor-total">—</span></div>
    </div>

    <div class="health-card">
      <div class="health-card-title"><span>📡</span> WiFi</div>
      <div class="health-row"><span class="health-row-key">Network</span><span class="health-row-val" id="wifi-ssid">—</span></div>
      <div class="health-row"><span class="health-row-key">Link speed</span><span class="health-row-val" id="wifi-speed">—</span></div>
      <div class="health-row"><span class="health-row-key">Signal (RSSI)</span><span class="health-row-val" id="wifi-rssi">—</span></div>
      <div class="health-row"><span class="health-row-key">CPU temp</span><span class="health-row-val" id="cpu-temp">—</span></div>
      <div class="health-row"><span class="health-row-key">Uptime</span><span class="health-row-val" id="uptime">—</span></div>
    </div>
  </div>
</div>
</div><!-- /main -->

<!-- ── MEDIA PLAYER ── -->
<div class="player-modal" id="player-modal">
  <div class="player-wrap">
    <div class="player-header">
      <div class="player-title" id="player-title">—</div>
      <button class="player-close" onclick="closePlayer()">✕</button>
    </div>
    <div class="player-body" id="player-body"></div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
// ── STATE ──────────────────────────────────────────────────
let allFiles   = [];
let curFilter  = 'all';
let lastTransfer = {};

// ── TABS ───────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('panel-'+name).classList.add('active');
  event.target.classList.add('active');
  if(name==='health') loadHealth();
}

// ── TOAST ──────────────────────────────────────────────────
function toast(msg, ok=true) {
  const t=document.getElementById('toast');
  t.textContent=msg;
  t.style.borderColor=ok?'var(--green)':'var(--red)';
  t.style.color=ok?'var(--green)':'var(--red)';
  t.style.display='block';
  clearTimeout(t._tid);
  t._tid=setTimeout(()=>t.style.display='none',3500);
}

// ── FILE ICONS ─────────────────────────────────────────────
function fileIcon(type,name) {
  if(type==='video') return '🎬';
  if(type==='audio') return '🎵';
  if(type==='image') return `<img src="/stream/${encodeURIComponent(name)}" alt="" loading="lazy" onerror="this.parentElement.textContent='🖼️'">`;
  const ext=name.split('.').pop().toLowerCase();
  const m={pdf:'📕',zip:'🗜️',rar:'🗜️',tar:'🗜️',gz:'🗜️',
           apk:'📱',exe:'⚙️',doc:'📝',docx:'📝',xls:'📊',xlsx:'📊',
           ppt:'📊',pptx:'📊',txt:'📄',py:'🐍',js:'📜',html:'🌐',
           sql:'🗄️',json:'📋',xml:'📋',csv:'📊'};
  return m[ext]||'📄';
}

function badgeHTML(type) {
  const map={video:'badge-video',audio:'badge-audio',image:'badge-image',file:'badge-file'};
  return `<span class="type-badge ${map[type]||'badge-file'}">${type}</span>`;
}

// ── LOAD FILES ─────────────────────────────────────────────
function loadFiles() {
  fetch('/api/files').then(r=>r.json()).then(data=>{
    allFiles=data.files;
    document.getElementById('s-count').textContent=data.count;
    document.getElementById('s-used').textContent=data.total_size;
    document.getElementById('s-free').textContent=data.free_space;
    document.getElementById('s-time').textContent=new Date().toLocaleTimeString();
    renderFiles();
  }).catch(()=>{});
}

function setFilter(f,btn) {
  curFilter=f;
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  renderFiles();
}

function renderFiles() {
  const q=(document.getElementById('search-box').value||'').toLowerCase();
  const filtered=allFiles.filter(f=>{
    if(curFilter!=='all'&&f.type!==curFilter) return false;
    if(q&&!f.name.toLowerCase().includes(q)) return false;
    return true;
  });
  const list=document.getElementById('file-list');
  if(!filtered.length){
    list.innerHTML=`<div class="empty"><div class="empty-icon">🔍</div>No files found</div>`;
    return;
  }

  const canPlay=f=>f.type==='video'||f.type==='audio'||f.type==='image';

  list.innerHTML=filtered.map(f=>`
    <div class="file-item">
      <div class="file-thumb">${fileIcon(f.type,f.name)}</div>
      <div class="file-info">
        <div class="file-name">${f.name}${badgeHTML(f.type)}</div>
        <div class="file-meta">${f.size} &nbsp;·&nbsp; ${f.modified}</div>
      </div>
      <div class="file-actions">
        ${canPlay(f)?`<button class="btn btn-play" onclick="openPlayer('${esc(f.name)}','${f.type}')">▶ Play</button>`:''}
        <a class="btn btn-dl" href="/download/${encodeURIComponent(f.name)}" download>⬇ Save</a>
        <button class="btn btn-del" onclick="deleteFile('${esc(f.name)}')">🗑</button>
      </div>
    </div>
  `).join('');
}

function esc(s){return s.replace(/'/g,"\\'")}

function deleteFile(name) {
  if(!confirm(`Delete "${name}"?`)) return;
  fetch('/delete/'+encodeURIComponent(name),{method:'DELETE'})
    .then(r=>r.json()).then(d=>{
      toast(d.success?`🗑 Deleted: ${name}`:`Error: ${d.error}`,d.success);
      if(d.success) loadFiles();
    });
}

// ── MEDIA PLAYER ───────────────────────────────────────────
function openPlayer(name, type) {
  const modal=document.getElementById('player-modal');
  const body=document.getElementById('player-body');
  document.getElementById('player-title').textContent=name;
  const url='/stream/'+encodeURIComponent(name);

  if(type==='video') {
    body.innerHTML=`<video id="main-video" controls autoplay preload="auto"
      style="width:100%;max-height:70vh;display:block;background:#000">
      <source src="${url}">
      Your browser does not support this video.
    </video>`;
  } else if(type==='audio') {
    body.innerHTML=`
      <div class="audio-art">
        <div class="audio-disc playing" id="audio-disc">🎵</div>
        <div style="font-family:var(--font-hd);font-size:18px;color:var(--text);
          margin-bottom:16px;letter-spacing:1px">${name}</div>
        <audio id="main-audio" controls autoplay preload="auto"
          style="width:100%;border-radius:8px"
          onpause="document.getElementById('audio-disc').classList.remove('playing')"
          onplay="document.getElementById('audio-disc').classList.add('playing')">
          <source src="${url}">
        </audio>
      </div>`;
  } else if(type==='image') {
    body.innerHTML=`<div id="image-viewer">
      <img src="${url}" alt="${name}" style="max-width:100%;max-height:80vh;border-radius:8px;object-fit:contain">
      <div style="padding:12px;font-family:var(--font-mono);font-size:11px;color:var(--muted);text-align:center">${name}</div>
    </div>`;
  }
  modal.classList.add('open');
}

function closePlayer() {
  const modal=document.getElementById('player-modal');
  modal.classList.remove('open');
  document.getElementById('player-body').innerHTML='';
}
document.getElementById('player-modal').addEventListener('click',e=>{
  if(e.target===e.currentTarget) closePlayer();
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closePlayer()});

// ── UPLOAD ─────────────────────────────────────────────────
function fmtBytes(b) {
  if(b<1024) return b+'B';
  if(b<1024*1024) return (b/1024).toFixed(1)+'KB';
  if(b<1024*1024*1024) return (b/1024/1024).toFixed(1)+'MB';
  return (b/1024/1024/1024).toFixed(2)+'GB';
}

function uploadFiles(files) {
  if(!files.length) return;
  switchTabByName('upload');
  const wrap=document.getElementById('progress-wrap');
  const bar=document.getElementById('prog-bar');
  const label=document.getElementById('prog-label');
  const speed=document.getElementById('prog-speed');
  const xferText=document.getElementById('prog-transferred');
  const pctText=document.getElementById('prog-pct');
  wrap.style.display='block';

  let i=0;
  let totalPeak=0;

  function next(){
    if(i>=files.length){
      wrap.style.display='none';
      toast(`✅ ${files.length} file(s) uploaded!`);
      loadFiles();
      document.getElementById('panel-files').classList.add('active');
      document.getElementById('panel-upload').classList.remove('active');
      return;
    }
    const f=files[i++];
    const fd=new FormData();
    fd.append('file',f);
    label.textContent=`Uploading ${i}/${files.length}: ${f.name}`;

    const xhr=new XMLHttpRequest();
    const t0=Date.now();
    let peakSpeed=0;
    let lastLoaded=0,lastTime=t0;

    xhr.upload.onprogress=e=>{
      if(!e.lengthComputable) return;
      const pct=e.loaded/e.total*100;
      bar.style.width=pct+'%';
      pctText.textContent=pct.toFixed(1)+'%';
      xferText.textContent=fmtBytes(e.loaded)+' / '+fmtBytes(e.total);

      const now=Date.now();
      const dt=(now-lastTime)/1000;
      if(dt>0.2){
        const sp=(e.loaded-lastLoaded)/dt;
        if(sp>peakSpeed) peakSpeed=sp;
        if(sp>totalPeak) totalPeak=sp;
        speed.textContent=fmtBytes(sp)+'/s';
        lastLoaded=e.loaded; lastTime=now;
      }
    };

    xhr.onload=()=>{
      const dt=(Date.now()-t0)/1000;
      const avg=f.size/dt;
      lastTransfer={avg:fmtBytes(avg)+'/s',peak:fmtBytes(peakSpeed)+'/s',
        time:dt.toFixed(1)+'s',size:fmtBytes(f.size)};
      document.getElementById('spd-avg').textContent=lastTransfer.avg;
      document.getElementById('spd-peak').textContent=lastTransfer.peak;
      document.getElementById('spd-time').textContent=lastTransfer.time;
      document.getElementById('spd-size').textContent=lastTransfer.size;
      document.getElementById('speed-panel').style.display='block';

      try{
        const r=JSON.parse(xhr.responseText);
        if(!r.success) toast(`✗ ${r.error}`,false);
      }catch(e){}
      bar.style.width='0%';
      next();
    };
    xhr.onerror=()=>{toast(`✗ Upload failed: ${f.name}`,false);next()};
    xhr.open('POST','/upload');
    xhr.send(fd);
  }
  next();
}

function switchTabByName(name){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('panel-'+name).classList.add('active');
  const tabs={files:0,upload:1,health:2};
  document.querySelectorAll('.tab')[tabs[name]]?.classList.add('active');
}

// ── DRAG DROP ──────────────────────────────────────────────
const dz=document.getElementById('drop-zone');
dz.addEventListener('dragover',e=>{e.preventDefault();dz.classList.add('drag')});
dz.addEventListener('dragleave',()=>dz.classList.remove('drag'));
dz.addEventListener('drop',e=>{
  e.preventDefault();dz.classList.remove('drag');
  uploadFiles(e.dataTransfer.files);
});

// ── DEVICE HEALTH ──────────────────────────────────────────
function loadHealth(){
  fetch('/api/health').then(r=>r.json()).then(h=>{
    // Battery
    const pct=h.battery_pct||0;
    document.getElementById('bat-pct').textContent=pct+'%';
    document.getElementById('bat-pct2').textContent=pct+'%';
    document.getElementById('bat-status').textContent=h.battery_status||'—';
    document.getElementById('bat-plug').textContent=h.plugged||'—';
    document.getElementById('bat-temp').textContent=h.battery_temp?h.battery_temp+'°C':'—';
    document.getElementById('bat-bar').style.width=pct+'%';
    document.getElementById('bat-bar').style.background=
      pct>60?'var(--green)':pct>30?'var(--amber)':'var(--red)';
    document.getElementById('bat-icon').textContent=
      h.battery_status==='charging'?'⚡':(pct>60?'🔋':pct>30?'🪫':'🔴');

    // RAM
    const rp=h.ram_pct||0;
    document.getElementById('ram-pct').textContent=rp+'%';
    document.getElementById('ram-used').textContent=h.ram_used||'—';
    document.getElementById('ram-total').textContent=h.ram_total||'—';
    document.getElementById('ram-bar').style.width=rp+'%';
    document.getElementById('ram-bar').style.background=
      rp>80?'var(--red)':rp>60?'var(--amber)':'var(--accent)';

    // Storage
    const sp=h.storage_pct||0;
    document.getElementById('stor-pct').textContent=sp+'%';
    document.getElementById('stor-used').textContent=h.storage_used||'—';
    document.getElementById('stor-free').textContent=h.storage_free||'—';
    document.getElementById('stor-total').textContent=h.storage_total||'—';
    document.getElementById('stor-bar').style.width=sp+'%';
    document.getElementById('stor-bar').style.background=
      sp>80?'var(--red)':'var(--amber)';

    // WiFi
    document.getElementById('wifi-ssid').textContent=h.wifi_ssid||'—';
    document.getElementById('wifi-speed').textContent=h.wifi_speed?h.wifi_speed+' Mbps':'—';
    document.getElementById('wifi-rssi').textContent=h.wifi_rssi?h.wifi_rssi+' dBm':'—';
    document.getElementById('cpu-temp').textContent=h.cpu_temp?h.cpu_temp+'°C':'—';
    document.getElementById('uptime').textContent=h.uptime||'—';
  }).catch(()=>{});
}

// ── INIT ───────────────────────────────────────────────────
loadFiles();
setInterval(loadFiles,15000);
setInterval(()=>{
  if(document.getElementById('panel-health').classList.contains('active')) loadHealth();
},30000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    print(f"""
  ╔══════════════════════════════════════════╗
  ║     HYDRA Cloud Server — ONLINE          ║
  ║     Upload · Download · Stream           ║
  ╚══════════════════════════════════════════╝

  📁  Files: {UPLOAD_FOLDER}
  🌐  Local: http://0.0.0.0:{port}
  ⚡  Chunk: {CHUNK_SIZE // (1024*1024)}MB streaming chunks
    """)
    # Use threaded=True for concurrent connections (upload + download simultaneously)
    app.run(host="0.0.0.0", port=port, debug=False,
            threaded=True, use_reloader=False)
