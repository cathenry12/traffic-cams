import os
import time
import json
import logging
import schedule
import requests
import datetime
import subprocess
import glob
import cv2
import shutil
import threading
from flask import Flask, render_template_string, send_from_directory, request, redirect, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG_FILE = "config.json"
DATA_DIR = "data"

app = Flask(__name__)

# --- WEB DASHBOARD LOGIC ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Traffic Cam Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(22, 28, 45, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --accent-green: #10b981;
            --accent-blue: #0ea5e9;
            --accent-amber: #f59e0b;
            --accent-red: #ef4444;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }

        body {
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, var(--bg-color) 70%);
            background-color: var(--bg-color);
            color: var(--text-main);
            padding: 30px 20px;
            max-width: 1250px;
            margin: auto;
            min-height: 100vh;
        }

        h1, h2, h3 {
            font-weight: 600;
        }

        h1 {
            text-align: center;
            font-size: 2.8rem;
            margin-bottom: 40px;
            font-weight: 800;
            background: linear-gradient(to right, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.03em;
        }

        /* Glassmorphism Cards */
        .glass-card {
            background: var(--card-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .glass-card:hover {
            border-color: rgba(255, 255, 255, 0.15);
            transform: translateY(-2px);
        }

        .section-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 24px;
            margin-bottom: 30px;
        }

        .camera-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 24px;
            margin-top: 30px;
        }

        .camera-card {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        img, video {
            width: 100%;
            border-radius: 12px;
            margin-top: 15px;
            background: #020617;
            min-height: 220px;
            object-fit: cover;
            border: 1px solid var(--border-color);
        }

        h2 {
            margin: 0 0 15px 0;
            font-size: 1.4rem;
            color: #ffffff;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .meta {
            font-size: 0.85em;
            color: var(--text-muted);
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .video-list {
            margin-top: 20px;
            font-size: 0.9em;
            max-height: 180px;
            overflow-y: auto;
            padding-right: 8px;
            border-top: 1px solid var(--border-color);
            padding-top: 15px;
        }

        .video-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 8px;
            margin-bottom: 8px;
            border: 1px solid transparent;
            transition: all 0.2s;
        }

        .video-item:hover {
            background: rgba(255, 255, 255, 0.06);
            border-color: rgba(255, 255, 255, 0.05);
        }

        .video-link {
            color: var(--accent-amber);
            text-decoration: none;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .video-link:hover {
            color: #fbbf24;
            text-decoration: underline;
        }

        input, select {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            color: white;
            padding: 10px 14px;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.95rem;
            transition: all 0.2s;
            outline: none;
            width: 100%;
            box-sizing: border-box;
        }

        input:focus, select:focus {
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.15);
        }

        button {
            cursor: pointer;
            padding: 10px 18px;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            font-family: inherit;
            font-size: 0.95rem;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }

        .btn-add {
            background: var(--accent-green);
            color: #042f1a;
        }
        .btn-add:hover {
            background: #34d399;
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.3);
        }

        .btn-edit {
            background: rgba(14, 165, 233, 0.15);
            color: #38bdf8;
            font-size: 0.85em;
            padding: 6px 12px;
            border: 1px solid rgba(14, 165, 233, 0.3);
        }
        .btn-edit:hover {
            background: var(--accent-blue);
            color: #0f172a;
        }

        .btn-delete {
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            font-size: 0.85em;
            padding: 6px 12px;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        .btn-delete:hover {
            background: var(--accent-red);
            color: white;
        }

        .btn-manual {
            background: var(--accent-amber);
            color: #451a03;
        }
        .btn-manual:hover {
            background: #fbbf24;
            box-shadow: 0 0 15px rgba(245, 158, 11, 0.3);
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 12px;
        }

        label {
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 500;
        }

        /* Storage Progress Bar */
        .progress-bar-container {
            width: 100%;
            height: 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
            overflow: hidden;
            margin: 10px 0;
            border: 1px solid rgba(255, 255, 255, 0.03);
        }

        .progress-bar {
            height: 100%;
            background: linear-gradient(to right, var(--accent-blue), var(--accent-green));
            border-radius: 5px;
            transition: width 0.5s ease-in-out;
        }

        .storage-stat-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
            margin-bottom: 4px;
        }

        .storage-stat-row span:last-child {
            font-weight: 600;
        }

        /* Scrollbar customizing */
        ::-webkit-scrollbar {
            width: 6px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.15);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.3);
        }
    </style>
</head>
<body>
    <h1>🚦 Traffic Camera Dashboard</h1>

    <div class="section-grid">
        <!-- Storage Utilization Widget -->
        <div class="glass-card" style="border-left: 4px solid var(--accent-blue);">
            <h3 style="margin-top: 0; color: var(--accent-blue); display: flex; align-items: center; gap: 8px;">💾 Storage Status</h3>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                <div class="storage-stat-row">
                    <span>App Data size:</span>
                    <span style="color: var(--accent-green);">{{ storage.app_size }}</span>
                </div>
                <div class="storage-stat-row">
                    <span>Disk Used:</span>
                    <span>{{ storage.disk_used }}</span>
                </div>
                <div class="storage-stat-row">
                    <span>Disk Capacity:</span>
                    <span>{{ storage.disk_total }}</span>
                </div>
                <div class="storage-stat-row">
                    <span>Disk Available:</span>
                    <span style="color: var(--accent-blue);">{{ storage.disk_free }}</span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: {{ storage.disk_percent }}%;"></div>
                </div>
                <div style="font-size: 0.75rem; text-align: right; color: var(--text-muted);">
                    Disk utilization: {{ storage.disk_percent|round(1) }}%
                </div>
            </div>
        </div>

        <!-- Global Settings -->
        <div class="glass-card" style="border-left: 4px solid var(--accent-green);">
            <h3 style="margin-top: 0; color: var(--accent-green); display: flex; align-items: center; gap: 8px;">⚙️ Global Settings</h3>
            <form action="/settings" method="POST">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div class="form-group">
                        <label>Capture Interval (sec)</label>
                        <input type="number" name="interval" value="{{ config.capture_interval_seconds }}">
                    </div>
                    <div class="form-group">
                        <label>Playback FPS</label>
                        <input type="number" name="fps" value="{{ config.playback_fps }}">
                    </div>
                    <div class="form-group">
                        <label>Auto-Schedule (Time)</label>
                        <input type="text" name="schedule" value="{{ config.generate_timelapse_schedule }}">
                    </div>
                    <div class="form-group" style="flex-direction: row; align-items: center; gap: 8px; margin-top: 25px;">
                        <input type="checkbox" name="delete_images" id="delete_images_chk" {% if config.delete_images_after_compile %}checked{% endif %} style="width: auto;">
                        <label for="delete_images_chk" style="margin: 0; cursor: pointer;">Auto-delete images</label>
                    </div>
                </div>
                <button type="submit" class="btn-add" style="width: 100%; margin-top: 15px;">Update Settings</button>
            </form>
        </div>
    </div>

    <div class="section-grid">
        <!-- Manual Generation -->
        <div class="glass-card" style="border-left: 4px solid var(--accent-amber);">
            <h3 style="margin-top: 0; color: var(--accent-amber); display: flex; align-items: center; gap: 8px;">🎬 Manual Daily Time-lapse</h3>
            <form action="/generate_manual" method="POST">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div class="form-group">
                        <label>Select Camera</label>
                        <select name="cam_id" id="manual-cam" onchange="updateStats()">
                            {% for cam in cameras %}
                                <option value="{{ cam.id }}">{{ cam.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Select Date</label>
                        <select name="date" id="manual-date" onchange="updateStats()">
                            {% for d in available_dates %}
                                <option value="{{ d }}">{{ d }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>FPS Override</label>
                        <input type="number" name="fps" value="{{ config.playback_fps }}">
                    </div>
                    <div class="form-group">
                        <label>Custom Name (Optional)</label>
                        <input type="text" name="custom_name" placeholder="e.g. morning_rush">
                    </div>
                    <div class="form-group" style="flex-direction: row; align-items: center; gap: 8px; margin-top: 25px;">
                        <input type="checkbox" name="delete_images" id="manual_delete_chk" style="width: auto;">
                        <label for="manual_delete_chk" style="margin: 0; cursor: pointer;">Delete raw images</label>
                    </div>
                </div>
                <div id="stats-display" style="font-size: 0.8em; color: var(--accent-amber); margin: 10px 0;">Select a date to see image count...</div>
                <button type="submit" class="btn-manual" style="width: 100%;">🚀 Generate Now</button>
            </form>
        </div>

        <!-- Merge Range of Videos -->
        <div class="glass-card" style="border-left: 4px solid #818cf8;">
            <h3 style="margin-top: 0; color: #818cf8; display: flex; align-items: center; gap: 8px;">🔗 Merge Video Date Range</h3>
            <form action="/merge_videos" method="POST">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div class="form-group" style="grid-column: span 2;">
                        <label>Select Camera</label>
                        <select name="cam_id" required>
                            {% for cam in cameras %}
                                <option value="{{ cam.id }}">{{ cam.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Start Date</label>
                        <input type="date" name="start_date" required>
                    </div>
                    <div class="form-group">
                        <label>End Date</label>
                        <input type="date" name="end_date" required>
                    </div>
                    <div class="form-group" style="flex-direction: row; align-items: center; gap: 8px; margin-top: 15px; grid-column: span 2;">
                        <input type="checkbox" name="delete_sources" id="merge_delete_chk" style="width: auto;">
                        <label for="merge_delete_chk" style="margin: 0; cursor: pointer;">Delete source videos after merge</label>
                    </div>
                </div>
                <button type="submit" class="btn-manual" style="width: 100%; margin-top: 15px; background: #818cf8; color: #1e1b4b;">🔗 Merge Videos</button>
            </form>
        </div>
    </div>

    <!-- Add Camera -->
    <div class="glass-card" style="border-left: 4px solid var(--accent-blue); margin-bottom: 30px;">
        <h3 style="margin-top: 0; color: var(--accent-blue);">➕ Add New Camera</h3>
        <form action="/add" method="POST" style="display: flex; flex-wrap: wrap; gap: 15px; align-items: flex-end;">
            <div class="form-group" style="flex: 1; min-width: 200px; margin-bottom: 0;">
                <label>Camera Name</label>
                <input type="text" name="name" placeholder="Camera Name" required>
            </div>
            <div class="form-group" style="flex: 2; min-width: 300px; margin-bottom: 0;">
                <label>Camera Feed URL</label>
                <input type="url" name="url" placeholder="Camera Feed URL" required style="width: 100%;">
            </div>
            <button type="submit" class="btn-add" style="height: 44px; padding: 0 24px;">Add Camera</button>
        </form>
    </div>

    <div class="camera-grid">
        {% for cam in cameras %}
        <div class="glass-card camera-card">
            <div>
                <h2>
                    <span>{{ cam.name }}</span>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn-edit" onclick="toggleEdit({{ cam.id }})">Edit</button>
                        <form action="/delete/{{ cam.id }}" method="POST" style="display:inline;" onsubmit="return confirm('Delete?');">
                            <button type="submit" class="btn-delete">Del</button>
                        </form>
                    </div>
                </h2>
                
                <div id="edit-{{ cam.id }}" style="display:none; margin: 15px 0; background: rgba(0,0,0,0.2); padding: 15px; border-radius: 12px; border: 1px solid var(--border-color);">
                    <form action="/edit/{{ cam.id }}" method="POST">
                        <div class="form-group">
                            <label>Name</label>
                            <input type="text" name="name" value="{{ cam.name }}">
                        </div>
                        <div class="form-group">
                            <label>URL</label>
                            <input type="url" name="url" value="{{ cam.url }}">
                        </div>
                        <div style="display: flex; gap: 8px; margin-top: 10px;">
                            <button type="submit" class="btn-edit" style="background: var(--accent-blue); color: white;">Save</button>
                            <button type="button" onclick="toggleEdit({{ cam.id }})" style="background: rgba(255,255,255,0.1); color: white;">Cancel</button>
                        </div>
                    </form>
                </div>

                <div class="meta" style="word-break: break-all; opacity: 0.7;">🔗 {{ cam.url }}</div>
                <div class="meta">⏱️ Latest: {{ cam.latest_time }}</div>
                
                <div style="margin: 15px 0;">
                    <a href="/gallery/{{ cam.id }}/{{ cam.latest_time.split(' ')[0] }}" style="color: var(--accent-green); text-decoration: none; font-size: 0.95em; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;">📁 View Today's Images &rarr;</a>
                </div>

                {% if cam.latest_img %}
                    <img src="/data/{{ cam.latest_img }}" alt="Latest Image">
                {% else %}
                    <div style="height:220px; display:flex; align-items:center; justify-content:center; background:rgba(0,0,0,0.3); border-radius:12px; border: 1px dashed var(--border-color); color: var(--text-muted);">No images captured yet</div>
                {% endif %}
            </div>
            
            <div class="video-list">
                <strong style="display: block; margin-bottom: 10px; color: var(--accent-blue);">🎥 Video Archive:</strong>
                {% for vid in cam.videos %}
                    <div class="video-item">
                        <a class="video-link" href="/data/{{ vid.path }}" target="_blank">🎬 {{ vid.date }}</a>
                        <form action="/delete_video/{{ vid.path }}" method="POST" onsubmit="return confirm('Delete this video?');" style="margin: 0;">
                            <button type="submit" style="background: none; color: var(--accent-red); padding: 0; font-size: 1.25em; border: none; cursor: pointer;">&times;</button>
                        </form>
                    </div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    </div>

    <script>
        function toggleEdit(id) {
            const el = document.getElementById('edit-' + id);
            el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }

        async function updateStats() {
            const camId = document.getElementById('manual-cam').value;
            const date = document.getElementById('manual-date').value;
            const display = document.getElementById('stats-display');
            if (camId === "" || !date) {
                display.innerText = "Select a camera and date first.";
                return;
            }
            
            display.innerText = "Checking...";
            try {
                const res = await fetch(`/stats/${camId}/${encodeURIComponent(date)}`);
                if (!res.ok) throw new Error("Server error");
                const data = await res.json();
                display.innerText = `Folder contains ${data.count} images for this time-lapse.`;
            } catch (err) {
                console.error(err);
                display.innerText = "Error: Could not fetch stats. Check logs.";
            }
        }
    </script>
</body>
</html>
"""

def get_storage_stats():
    total_size = 0
    if os.path.exists(DATA_DIR):
        for dirpath, dirnames, filenames in os.walk(DATA_DIR):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass
    try:
        usage = shutil.disk_usage(DATA_DIR if os.path.exists(DATA_DIR) else ".")
        disk_total = usage.total
        disk_free = usage.free
    except Exception:
        disk_total = 0
        disk_free = 0
    return {
        "app_size_bytes": total_size,
        "disk_total_bytes": disk_total,
        "disk_free_bytes": disk_free
    }

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / (1024**2):.2f} MB"
    else:
        return f"{size_bytes / (1024**3):.2f} GB"

def concat_videos_opencv(video_paths, output_path):
    if not video_paths:
        return False
    try:
        cap = cv2.VideoCapture(video_paths[0])
        if not cap.isOpened():
            return False
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        if fps <= 0: fps = 30
        if width <= 0 or height <= 0:
            width, height = 640, 480
            
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        for path in video_paths:
            vc = cv2.VideoCapture(path)
            while vc.isOpened():
                ret, frame = vc.read()
                if not ret:
                    break
                if frame.shape[1] != width or frame.shape[0] != height:
                    frame = cv2.resize(frame, (width, height))
                out.write(frame)
            vc.release()
        out.release()
        return True
    except Exception as e:
        logging.error(f"Error in OpenCV video concatenation: {e}")
        return False

def do_merge_videos(video_paths, output_path, delete_sources=False):
    logging.info(f"Merging {len(video_paths)} videos into {output_path}")
    list_file = output_path + ".txt"
    with open(list_file, 'w', encoding='utf-8') as f:
        for p in video_paths:
            abs_path = os.path.abspath(p).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")
            
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", output_path
    ]
    
    success = False
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            logging.info(f"Finished merging videos via FFmpeg: {output_path}")
            success = True
        else:
            logging.error(f"FFmpeg merge failed: {result.stderr}")
    except Exception as e:
        logging.error(f"Error running FFmpeg merge: {e}")
        
    if os.path.exists(list_file):
        os.remove(list_file)
        
    if not success:
        logging.info("Falling back to OpenCV video merging")
        success = concat_videos_opencv(video_paths, output_path)
        if success:
            logging.info(f"Finished merging videos via OpenCV: {output_path}")
        else:
            logging.error("OpenCV video merging failed as well.")

    if success and delete_sources:
        logging.info(f"Deleting {len(video_paths)} source videos after successful merge.")
        for p in video_paths:
            try:
                # Do not delete the merged video itself if it somehow matches
                if os.path.exists(p) and os.path.abspath(p) != os.path.abspath(output_path):
                    os.remove(p)
                    logging.info(f"Deleted source video: {p}")
            except Exception as e:
                logging.error(f"Error deleting source video {p}: {e}")

@app.route('/merge_videos', methods=['POST'])
def merge_videos():
    cam_id = int(request.form.get('cam_id'))
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    delete_sources = 'delete_sources' in request.form
    
    config = load_config()
    if 0 <= cam_id < len(config['cameras']):
        name = config['cameras'][cam_id]['name']
        safe_name = name.replace("/", "_").replace("\\", "_")
        cam_root = os.path.join(DATA_DIR, name)
        
        if not os.path.exists(cam_root):
            return "Camera directory not found", 404
            
        try:
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
        except ValueError:
            return "Invalid date format. Use YYYY-MM-DD.", 400
            
        all_files = os.listdir(cam_root)
        matching_vids = []
        for f in all_files:
            if f.endswith('.mp4') and f.startswith(f"{safe_name}_"):
                date_part = f.replace(f"{safe_name}_", "").replace(".mp4", "")
                try:
                    f_date = datetime.datetime.strptime(date_part, "%Y-%m-%d")
                    if start_date <= f_date <= end_date:
                        matching_vids.append((f_date, os.path.join(cam_root, f)))
                except ValueError:
                    continue
                    
        matching_vids.sort()
        
        if len(matching_vids) == 0:
            return "No videos found in that range for this camera", 400
            
        output_name = f"{safe_name}_merged_{start_date_str}_to_{end_date_str}.mp4"
        output_path = os.path.join(cam_root, output_name)
        video_paths = [path for date, path in matching_vids]
        
        threading.Thread(target=lambda: do_merge_videos(video_paths, output_path, delete_sources)).start()
        
    return redirect('/')

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

@app.route('/settings', methods=['POST'])
def update_settings():
    config = load_config()
    config['capture_interval_seconds'] = int(request.form.get('interval', 60))
    config['playback_fps'] = int(request.form.get('fps', 30))
    config['generate_timelapse_schedule'] = request.form.get('schedule', '00:00')
    config['delete_images_after_compile'] = 'delete_images' in request.form
    save_config(config)
    setup_scheduler() # Refresh the scheduler with new settings
    return redirect('/')

@app.route('/stats/<int:cam_id>/<date>')
def get_stats(cam_id, date):
    config = load_config()
    if 0 <= cam_id < len(config['cameras']):
        name = config['cameras'][cam_id]['name']
        cam_dir = os.path.join(DATA_DIR, name, date)
        count = 0
        if os.path.exists(cam_dir):
            count = len([f for f in os.listdir(cam_dir) if f.endswith('.jpg')])
        return jsonify({"count": count})
    return jsonify({"count": 0})

@app.route('/generate_manual', methods=['POST'])
def generate_manual():
    cam_id = int(request.form.get('cam_id'))
    date_str = request.form.get('date')
    fps = int(request.form.get('fps', 30))
    custom_name = request.form.get('custom_name', "").strip()
    delete_images = 'delete_images' in request.form
    
    config = load_config()
    if 0 <= cam_id < len(config['cameras']):
        name = config['cameras'][cam_id]['name']
        target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        # Pass the specific camera name to ONLY generate for that one
        threading.Thread(target=lambda: generate_timelapse(
            target_date=target_date, 
            manual_fps=fps, 
            manual_delete=delete_images,
            target_cam_name=name,
            custom_name=custom_name
        )).start()
        
    return redirect('/')

@app.route('/delete_video/<path:filename>', methods=['POST'])
def delete_video(filename):
    # Security check: Ensure the filename is within the DATA_DIR and is an mp4
    if not filename.endswith('.mp4'):
        return "Invalid file type", 400
    
    full_path = os.path.join(DATA_DIR, filename)
    if os.path.exists(full_path):
        os.remove(full_path)
        logging.info(f"Deleted video archive: {full_path}")
    return redirect('/')
@app.route('/gallery/<int:cam_id>/<date>')
def gallery(cam_id, date):
    config = load_config()
    if 0 <= cam_id < len(config['cameras']):
        name = config['cameras'][cam_id]['name']
        cam_dir = os.path.join(DATA_DIR, name, date)
        images = []
        if os.path.exists(cam_dir):
            all_imgs = sorted([f for f in os.listdir(cam_dir) if f.endswith('.jpg')])
            for img in all_imgs:
                images.append({
                    "name": img,
                    "path": f"{name}/{date}/{img}".replace("\\", "/")
                })
        return render_template_string(GALLERY_TEMPLATE, name=name, date=date, images=images)
    return redirect('/')

GALLERY_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Gallery - {{ name }}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; background: #1a1a1a; color: white; padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
        .img-container { background: #333; padding: 5px; border-radius: 8px; text-align: center; }
        img { width: 100%; border-radius: 4px; cursor: pointer; }
        .back { display: inline-block; margin-bottom: 20px; color: #00ff88; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <a href="/" class="back">← Back to Dashboard</a>
    <h1>🖼️ {{ name }} - {{ date }}</h1>
    <p>Showing {{ images|length }} images. Click to open full size.</p>
    <div class="grid">
        {% for img in images %}
        <div class="img-container">
            <a href="/data/{{ img.path }}" target="_blank">
                <img src="/data/{{ img.path }}" alt="{{ img.name }}" loading="lazy">
            </a>
            <div style="font-size: 0.7em; margin-top: 5px; color: #888;">{{ img.name }}</div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    config = load_config()
    camera_data = []
    available_dates = set()
    
    # Calculate storage stats
    stats = get_storage_stats()
    disk_used_bytes = stats["disk_total_bytes"] - stats["disk_free_bytes"]
    storage_info = {
        "app_size": format_size(stats["app_size_bytes"]),
        "disk_used": format_size(disk_used_bytes),
        "disk_total": format_size(stats["disk_total_bytes"]),
        "disk_free": format_size(stats["disk_free_bytes"]),
        "disk_percent": (disk_used_bytes / stats["disk_total_bytes"] * 100) if stats["disk_total_bytes"] > 0 else 0
    }
    
    # Efficiently find available dates and latest images
    for idx, cam in enumerate(config.get("cameras", [])):
        name = cam.get("name")
        cam_root = os.path.join(DATA_DIR, name)
        latest_img = None
        latest_time = "N/A"
        
        if os.path.exists(cam_root):
            date_folders = sorted([d for d in os.listdir(cam_root) if os.path.isdir(os.path.join(cam_root, d)) and "-" in d], reverse=True)
            for d in date_folders:
                available_dates.add(d)
            
            if date_folders:
                latest_date_dir = os.path.join(cam_root, date_folders[0])
                images = sorted([f for f in os.listdir(latest_date_dir) if f.endswith('.jpg')])
                if images:
                    latest_img_name = images[-1]
                    latest_img = f"{name}/{date_folders[0]}/{latest_img_name}".replace("\\", "/")
                    latest_time = f"{date_folders[0]} {latest_img_name.replace('.jpg', '').replace('-', ':')}"

        # Find all videos
        videos = []
        if os.path.exists(cam_root):
            safe_name = name.replace("/", "_").replace("\\", "_")
            all_vids = sorted([f for f in os.listdir(cam_root) if f.endswith('.mp4')], reverse=True)
            for v in all_vids:
                date_part = v.replace(f"{safe_name}_", "").replace(".mp4", "")
                videos.append({"path": f"{name}/{v}".replace("\\", "/"), "date": date_part})

        camera_data.append({
            "id": idx, "name": name, "url": cam.get("url"),
            "latest_img": latest_img, "latest_time": latest_time, "videos": videos
        })
    
    return render_template_string(HTML_TEMPLATE, 
                                cameras=camera_data, 
                                config=config, 
                                storage=storage_info,
                                available_dates=sorted(list(available_dates), reverse=True))

@app.route('/add', methods=['POST'])
def add_camera():
    from flask import request, redirect
    name = request.form.get('name')
    url = request.form.get('url')
    if name and url:
        config = load_config()
        config['cameras'].append({'name': name, 'url': url})
        save_config(config)
    return redirect('/')

@app.route('/edit/<int:cam_id>', methods=['POST'])
def edit_camera(cam_id):
    from flask import request, redirect
    name = request.form.get('name')
    url = request.form.get('url')
    config = load_config()
    if 0 <= cam_id < len(config['cameras']):
        config['cameras'][cam_id] = {'name': name, 'url': url}
        save_config(config)
    return redirect('/')

@app.route('/delete/<int:cam_id>', methods=['POST'])
def delete_camera(cam_id):
    from flask import redirect
    config = load_config()
    if 0 <= cam_id < len(config['cameras']):
        config['cameras'].pop(cam_id)
        save_config(config)
    return redirect('/')

@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory(os.path.abspath(DATA_DIR), filename)

# --- CAPTURE LOGIC ---

def load_config():
    if not os.path.exists(CONFIG_FILE):
        logging.error(f"Configuration file {CONFIG_FILE} not found.")
        return None
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def capture_frame_from_stream(url, output_path):
    """Extracts a single frame from a video stream URL using OpenCV."""
    try:
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            logging.error(f"Failed to open video stream: {url}")
            return False
        
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(output_path, frame)
            cap.release()
            return True
        else:
            logging.error(f"Failed to read frame from stream: {url}")
            cap.release()
            return False
    except Exception as e:
        logging.error(f"Error capturing from stream {url}: {e}")
        return False

def capture_image_from_url(url, output_path):
    """Downloads an image from a URL using requests."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        logging.error(f"Error downloading image from {url}: {e}")
        return False

def capture_camera(camera):
    name = camera.get("name")
    url = camera.get("url")
    if not name or not url:
        logging.warning("Skipping camera with missing name or url.")
        return

    # Create directory structure: data/<camera_name>/<YYYY-MM-DD>/
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H-%M-%S")
    
    cam_dir = os.path.join(DATA_DIR, name, date_str)
    os.makedirs(cam_dir, exist_ok=True)
    
    output_path = os.path.join(cam_dir, f"{time_str}.jpg")
    
    # Decide capture method based on extension or just try stream if it contains m3u8/mp4
    # Wait, some image urls don't have .jpg, so we can try requests first, and if it fails or it's a known video extension, use cv2.
    # A simple heuristic:
    if url.endswith('.m3u8') or url.endswith('.mp4'):
        success = capture_frame_from_stream(url, output_path)
    else:
        # For typical traffic cams, they are often JPEGs
        success = capture_image_from_url(url, output_path)
        # If it fails, maybe it's a stream without an extension? We could fallback:
        if not success:
            logging.info(f"Falling back to stream capture for {name}")
            success = capture_frame_from_stream(url, output_path)

    if success:
        logging.info(f"Captured frame for {name} at {output_path}")

def job_capture_all():
    config = load_config()
    if not config:
        return
    for cam in config.get("cameras", []):
        capture_camera(cam)

def fallback_opencv(images, output_video, fps, size):
    logging.info("Using OpenCV fallback for video generation.")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video, fourcc, fps, size)
    for image_path in images:
        frame = cv2.imread(image_path)
        if frame is not None:
            frame = cv2.resize(frame, size)
            out.write(frame)
    out.release()

def generate_timelapse(target_date=None, manual_fps=None, manual_delete=None, target_cam_name=None, custom_name=None):
    config = load_config()
    if not config:
        return
    
    fps = manual_fps if manual_fps is not None else config.get("playback_fps", 30)
    delete_images = manual_delete if manual_delete is not None else config.get("delete_images_after_compile", False)
    
    if target_date:
        date_str = target_date.strftime("%Y-%m-%d")
    else:
        # Generate timelapse for yesterday
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
    
    for cam in config.get("cameras", []):
        name = cam.get("name")
        
        # If a target camera was specified, skip all others
        if target_cam_name and name != target_cam_name:
            continue
            
        # Sanitize name for filename (remove slashes)
        safe_name = name.replace("/", "_").replace("\\", "_")
        
        cam_dir = os.path.join(DATA_DIR, name, date_str)
        
        if not os.path.exists(cam_dir):
            logging.info(f"No images found for {name} on {date_str}. Skipping.")
            continue
            
        # Use custom name if provided, otherwise default to camera_date.mp4
        if custom_name:
            safe_custom = "".join([c for c in custom_name if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
            output_video = os.path.join(DATA_DIR, name, f"{safe_custom}.mp4")
        else:
            output_video = os.path.join(DATA_DIR, name, f"{safe_name}_{date_str}.mp4")
        
        images = sorted(glob.glob(os.path.join(cam_dir, "*.jpg")))
        if not images:
            continue
            
        # Read first image to get dimensions
        first_frame = cv2.imread(images[0])
        if first_frame is None:
            logging.error(f"Failed to read first image {images[0]}")
            continue
            
        height, width, layers = first_frame.shape
        # FORCE EVEN DIMENSIONS (Crucial for many codecs to prevent smearing)
        width = (width // 2) * 2
        height = (height // 2) * 2
        size = (width, height)
        
        logging.info(f"Compiling {len(images)} images for {name} into {output_video} at {fps} FPS. Size: {width}x{height}")
        
        # Generate a temporary file list for ffmpeg
        list_file = os.path.join(cam_dir, "ffmpeg_list.txt")
        with open(list_file, 'w', encoding='utf-8') as f:
            for image_path in images:
                # Use forward slashes for ffmpeg compatibility
                abs_path = os.path.abspath(image_path).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
        
        logging.info(f"Compiling {len(images)} images for {name} using FFmpeg.")
        
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", 
            "-r", str(fps), "-i", list_file,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            output_video
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and os.path.exists(output_video) and os.path.getsize(output_video) > 1000:
                logging.info(f"Finished timelapse via FFmpeg: {output_video}")
            else:
                error_msg = result.stderr if result.stderr else "Unknown error or zero-size file"
                logging.error(f"FFmpeg failed or produced empty file: {error_msg}")
                # Fallback to OpenCV if FFmpeg is missing/fails
                fallback_opencv(images, output_video, fps, size)
        except Exception as e:
            logging.error(f"Error running FFmpeg: {e}")
            fallback_opencv(images, output_video, fps, size)
        
        # Clean up list file
        if os.path.exists(list_file):
            os.remove(list_file)
        logging.info(f"Finished timelapse: {output_video}")
        
        if delete_images:
            logging.info(f"Deleting raw images in {cam_dir}")
            for img_path in images:
                try:
                    os.remove(img_path)
                except Exception as e:
                    logging.error(f"Error removing {img_path}: {e}")
            try:
                os.rmdir(cam_dir)
            except OSError:
                pass

def setup_scheduler():
    config = load_config()
    if not config: return
    
    schedule.clear()
    interval = config.get("capture_interval_seconds", 60)
    schedule_time = config.get("generate_timelapse_schedule", "00:00")
    
    logging.info(f"Scheduling captures every {interval} seconds.")
    schedule.every(interval).seconds.do(job_capture_all)
    
    logging.info(f"Scheduling daily timelapse generation at {schedule_time}.")
    schedule.every().day.at(schedule_time).do(generate_timelapse)

def run():
    # Start the web dashboard in a separate thread
    logging.info("Starting web dashboard on port 5000...")
    web_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False))
    web_thread.daemon = True
    web_thread.start()

    setup_scheduler()
    
    # Run a capture immediately
    job_capture_all()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run()
