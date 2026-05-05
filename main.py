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
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #1a1a1a; color: white; padding: 20px; max-width: 1200px; margin: auto; }
        .camera-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
        .camera-card { background: #2a2a2a; border-radius: 12px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); position: relative; }
        img, video { width: 100%; border-radius: 8px; margin-top: 10px; background: #000; min-height: 200px; }
        h1 { text-align: center; color: #00ff88; margin-bottom: 30px; }
        h2 { margin: 0; color: #00d2ff; display: flex; justify-content: space-between; align-items: center; }
        .meta { font-size: 0.8em; color: #888; margin-bottom: 10px; }
        .video-list { margin-top: 15px; font-size: 0.9em; max-height: 150px; overflow-y: auto; padding-right: 5px; }
        .video-link { display: block; color: #ffcc00; text-decoration: none; margin-bottom: 5px; }
        .video-link:hover { text-decoration: underline; }
        
        .section { background: #333; padding: 20px; border-radius: 12px; margin-bottom: 20px; border-left: 4px solid #00ff88; }
        .section-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 768px) { .section-grid { grid-template-columns: 1fr; } }
        
        input, select { background: #444; border: 1px solid #555; color: white; padding: 8px; border-radius: 4px; margin-bottom: 10px; }
        button { cursor: pointer; padding: 8px 15px; border-radius: 4px; border: none; font-weight: bold; transition: 0.2s; }
        .btn-add { background: #00ff88; color: #1a1a1a; }
        .btn-edit { background: #00d2ff; color: #1a1a1a; font-size: 0.8em; }
        .btn-delete { background: #ff4444; color: white; font-size: 0.8em; }
        .btn-manual { background: #ffcc00; color: #1a1a1a; }
        
        .form-group { display: flex; flex-direction: column; }
        label { font-size: 0.8em; color: #888; margin-bottom: 4px; }
    </style>
</head>
<body>
    <h1>🚦 Traffic Camera Dashboard</h1>

    <div class="section-grid">
        <!-- Global Settings -->
        <div class="section">
            <h3>⚙️ Global Settings</h3>
            <form action="/settings" method="POST">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
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
                    <div class="form-group" style="flex-direction: row; align-items: center; gap: 10px;">
                        <input type="checkbox" name="delete_images" {% if config.delete_images_after_compile %}checked{% endif %}>
                        <label style="margin: 0;">Auto-delete images</label>
                    </div>
                </div>
                <button type="submit" class="btn-add" style="width: 100%; margin-top: 10px;">Update All Settings</button>
            </form>
        </div>

        <!-- Manual Generation -->
        <div class="section" style="border-left-color: #ffcc00;">
            <h3>🎬 Manual Time-lapse</h3>
            <form action="/generate_manual" method="POST">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
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
                        <label>FPS Overide</label>
                        <input type="number" name="fps" value="{{ config.playback_fps }}">
                    </div>
                    <div class="form-group" style="flex-direction: row; align-items: center; gap: 10px;">
                        <input type="checkbox" name="delete_images" checked>
                        <label style="margin: 0;">Delete raw images</label>
                    </div>
                </div>
                <div id="stats-display" style="font-size: 0.8em; color: #ffcc00; margin-bottom: 10px;">Select a date to see image count...</div>
                <button type="submit" class="btn-manual" style="width: 100%;">🚀 Generate Now</button>
            </form>
        </div>
    </div>

    <!-- Add Camera -->
    <div class="section" style="border-left-color: #00d2ff;">
        <h3>➕ Add New Camera</h3>
        <form action="/add" method="POST" style="display: flex; flex-wrap: wrap; gap: 10px;">
            <input type="text" name="name" placeholder="Camera Name" required>
            <input type="url" name="url" placeholder="Camera Feed URL" required style="flex-grow: 1;">
            <button type="submit" class="btn-add">Add Camera</button>
        </form>
    </div>

    <div class="camera-grid">
        {% for cam in cameras %}
        <div class="camera-card">
            <h2>
                {{ cam.name }}
                <div style="display: flex; gap: 5px;">
                    <button class="btn-edit" onclick="toggleEdit({{ cam.id }})">Edit</button>
                    <form action="/delete/{{ cam.id }}" method="POST" style="display:inline;" onsubmit="return confirm('Delete?');">
                        <button type="submit" class="btn-delete">Del</button>
                    </form>
                </div>
            </h2>
            
            <div id="edit-{{ cam.id }}" style="display:none; margin-top:10px; background:#333; padding:10px; border-radius:8px;">
                <form action="/edit/{{ cam.id }}" method="POST">
                    <input type="text" name="name" value="{{ cam.name }}" style="width:90%">
                    <input type="url" name="url" value="{{ cam.url }}" style="width:90%">
                    <button type="submit" class="btn-edit">Save</button>
                    <button type="button" onclick="toggleEdit({{ cam.id }})" style="background:#666; color:white;">X</button>
                </form>
            </div>

            <div class="meta" style="word-break: break-all; opacity: 0.5;">{{ cam.url }}</div>
            <div class="meta">Latest: {{ cam.latest_time }}</div>
            
            <div style="margin-bottom: 10px;">
                <a href="/gallery/{{ cam.id }}/{{ cam.latest_time.split(' ')[0] }}" style="color: #00ff88; text-decoration: none; font-size: 0.9em; font-weight: bold;">📁 View Today's Images</a>
            </div>

            {% if cam.latest_img %}
                <img src="/data/{{ cam.latest_img }}" alt="Latest">
            {% else %}
                <div style="height:200px; display:flex; align-items:center; justify-content:center; background:#333; border-radius:8px;">No images</div>
            {% endif %}
            
            <div class="video-list">
                <strong>Archive:</strong>
                {% for vid in cam.videos %}
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                        <a class="video-link" href="/data/{{ vid.path }}" target="_blank" style="margin-bottom: 0;">🎬 {{ vid.date }}</a>
                        <form action="/delete_video/{{ vid.path }}" method="POST" onsubmit="return confirm('Delete this video?');">
                            <button type="submit" style="background: none; color: #ff4444; padding: 0; font-size: 1.2em;">&times;</button>
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
        
        // Initial check - don't run on load to prevent Firefox hangs
        // document.addEventListener('DOMContentLoaded', updateStats);
    </script>
</body>
</html>
"""

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
    delete_images = 'delete_images' in request.form
    
    config = load_config()
    if 0 <= cam_id < len(config['cameras']):
        name = config['cameras'][cam_id]['name']
        target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        threading.Thread(target=lambda: generate_timelapse(target_date=target_date, manual_fps=fps, manual_delete=delete_images)).start()
        
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
                # Fast way to get latest image without globbing everything
                images = sorted([f for f in os.listdir(latest_date_dir) if f.endswith('.jpg')])
                if images:
                    latest_img_name = images[-1]
                    latest_img = f"{name}/{date_folders[0]}/{latest_img_name}".replace("\\", "/")
                    latest_time = f"{date_folders[0]} {latest_img_name.replace('.jpg', '').replace('-', ':')}"

        # Find all videos (these are in the camera root, so no recursion needed)
        videos = []
        if os.path.exists(cam_root):
            safe_name = name.replace("/", "_").replace("\\", "_")
            all_vids = sorted([f for f in os.listdir(cam_root) if f.endswith('.mp4')], reverse=True)
            for v in all_vids:
                # Use sanitized name for matching
                date_part = v.replace(f"{safe_name}_", "").replace(".mp4", "")
                videos.append({"path": f"{name}/{v}".replace("\\", "/"), "date": date_part})

        camera_data.append({
            "id": idx, "name": name, "url": cam.get("url"),
            "latest_img": latest_img, "latest_time": latest_time, "videos": videos
        })
    
    return render_template_string(HTML_TEMPLATE, 
                                cameras=camera_data, 
                                config=config, 
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

def generate_timelapse(target_date=None, manual_fps=None, manual_delete=None):
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
    
    logging.info(f"Starting timelapse generation for date: {date_str} (FPS: {fps}, Delete: {delete_images})")
    
    for cam in config.get("cameras", []):
        name = cam.get("name")
        # Sanitize name for filename (remove slashes)
        safe_name = name.replace("/", "_").replace("\\", "_")
        
        cam_dir = os.path.join(DATA_DIR, name, date_str)
        
        if not os.path.exists(cam_dir):
            logging.info(f"No images found for {name} on {date_str}. Skipping.")
            continue
            
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
        with open(list_file, 'w') as f:
            for image_path in images:
                # ffmpeg requires paths in a specific format in the list file
                f.write(f"file '{os.path.abspath(image_path)}'\\n")
        
        logging.info(f"Compiling {len(images)} images for {name} using FFmpeg.")
        
        # FFmpeg command:
        # -y: overwrite
        # -r: input framerate
        # -f concat: use the list file
        # -safe 0: allow absolute paths
        # -c:v libx264: use H.264
        # -pix_fmt yuv420p: ensure compatibility with all players
        # -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2": ensure even dimensions
        cmd = [
            "ffmpeg", "-y", "-r", str(fps), 
            "-f", "concat", "-safe", "0", "-i", list_file,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            output_video
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logging.info(f"Finished timelapse via FFmpeg: {output_video}")
            else:
                logging.error(f"FFmpeg failed: {result.stderr}")
                # Fallback to OpenCV if FFmpeg is missing/fails
                fallback_opencv(images, output_video, fps, size)
        except Exception as e:
            logging.error(f"Error running FFmpeg: {e}")
        
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
