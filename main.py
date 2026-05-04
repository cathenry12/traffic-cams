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
from flask import Flask, render_template_string, send_from_directory

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG_FILE = "config.json"
DATA_DIR = "data"

app = Flask(__name__)

# --- WEB DASHBOARD LOGIC ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Traffic Cam Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
        .camera-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .camera-card { background: #2a2a2a; border-radius: 12px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        img, video { width: 100%; border-radius: 8px; margin-top: 10px; }
        h1 { text-align: center; color: #00ff88; }
        h2 { margin: 0; color: #00d2ff; }
        .meta { font-size: 0.8em; color: #888; margin-bottom: 10px; }
        .video-list { margin-top: 15px; font-size: 0.9em; }
        .video-link { display: block; color: #ffcc00; text-decoration: none; margin-bottom: 5px; }
        .video-link:hover { text-decoration: underline; }
    </style>
    <meta http-equiv="refresh" content="60">
</head>
<body>
    <h1>🚦 Traffic Camera Dashboard</h1>
    <div class="camera-grid">
        {% for cam in cameras %}
        <div class="camera-card">
            <h2>{{ cam.name }}</h2>
            <div class="meta">Latest Capture: {{ cam.latest_time }}</div>
            {% if cam.latest_img %}
                <img src="/data/{{ cam.latest_img }}" alt="Latest Capture">
            {% else %}
                <div style="height:200px; display:flex; align-items:center; justify-content:center; background:#333; border-radius:8px;">No images yet</div>
            {% endif %}
            
            <div class="video-list">
                <strong>Time-lapses:</strong>
                {% for vid in cam.videos %}
                    <a class="video-link" href="/data/{{ vid.path }}" target="_blank">🎬 {{ vid.date }}</a>
                {% endfor %}
            </div>
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
    for cam in config.get("cameras", []):
        name = cam.get("name")
        # Find latest image
        all_images = sorted(glob.glob(os.path.join(DATA_DIR, name, "**", "*.jpg"), recursive=True))
        latest_img = None
        latest_time = "N/A"
        if all_images:
            latest_img_path = all_images[-1]
            latest_img = latest_img_path.replace(DATA_DIR + os.sep, "").replace("\\", "/")
            latest_time = os.path.basename(latest_img_path).replace(".jpg", "").replace("-", ":")

        # Find all videos
        all_videos = sorted(glob.glob(os.path.join(DATA_DIR, name, "*.mp4")), reverse=True)
        videos = []
        for v in all_videos:
            v_name = os.path.basename(v)
            date_part = v_name.replace(f"{name}_", "").replace(".mp4", "")
            videos.append({"path": f"{name}/{v_name}".replace("\\", "/"), "date": date_part})

        camera_data.append({
            "name": name,
            "latest_img": latest_img,
            "latest_time": latest_time,
            "videos": videos
        })
    return render_template_string(HTML_TEMPLATE, cameras=camera_data)

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

def generate_timelapse(target_date=None):
    config = load_config()
    if not config:
        return
    
    fps = config.get("playback_fps", 30)
    delete_images = config.get("delete_images_after_compile", False)
    
    if target_date:
        date_str = target_date.strftime("%Y-%m-%d")
    else:
        # Generate timelapse for yesterday
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
    
    logging.info(f"Starting timelapse generation for date: {date_str}")
    
    for cam in config.get("cameras", []):
        name = cam.get("name")
        cam_dir = os.path.join(DATA_DIR, name, date_str)
        
        if not os.path.exists(cam_dir):
            logging.info(f"No images found for {name} on {date_str}. Skipping.")
            continue
            
        output_video = os.path.join(DATA_DIR, name, f"{name}_{date_str}.mp4")
        
        # Build ffmpeg command
        # ffmpeg requires sequential numbering or globbing.
        # Globbing is easiest: ffmpeg -pattern_type glob -i "*.jpg" ...
        # But wait, globbing is not always supported on all platforms in ffmpeg (e.g., Windows sometimes).
        # We can rename files or use an input text file for ffmpeg, or use cv2.VideoWriter as a reliable fallback.
        # Let's try cv2.VideoWriter as it is cross-platform and already installed via opencv-python.
        
        images = sorted(glob.glob(os.path.join(cam_dir, "*.jpg")))
        if not images:
            continue
            
        logging.info(f"Compiling {len(images)} images for {name} into {output_video} at {fps} FPS.")
        
        # Read first image to get dimensions
        first_frame = cv2.imread(images[0])
        if first_frame is None:
            logging.error(f"Failed to read first image {images[0]}")
            continue
            
        height, width, layers = first_frame.shape
        size = (width, height)
        
        # Define the codec and create VideoWriter object
        # mp4v is standard for MP4
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_video, fourcc, fps, size)
        
        for image_path in images:
            frame = cv2.imread(image_path)
            if frame is not None:
                # Resize if the frame size changed
                if (frame.shape[1], frame.shape[0]) != size:
                    frame = cv2.resize(frame, size)
                out.write(frame)
            else:
                logging.warning(f"Could not read image {image_path}, skipping.")
                
        out.release()
        logging.info(f"Finished timelapse: {output_video}")
        
        if delete_images:
            logging.info(f"Deleting raw images in {cam_dir}")
            for img_path in images:
                try:
                    os.remove(img_path)
                except Exception as e:
                    logging.error(f"Error removing {img_path}: {e}")
            # Optionally remove the directory
            try:
                os.rmdir(cam_dir)
            except OSError:
                pass

def run():
    config = load_config()
    if not config:
        logging.error("Exiting due to missing config.")
        return

    interval = config.get("capture_interval_seconds", 60)
    schedule_time = config.get("generate_timelapse_schedule", "00:00")

    # Start the web dashboard in a separate thread
    logging.info("Starting web dashboard on port 5000...")
    web_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False))
    web_thread.daemon = True
    web_thread.start()

    logging.info(f"Scheduling captures every {interval} seconds.")
    schedule.every(interval).seconds.do(job_capture_all)
    
    logging.info(f"Scheduling daily timelapse generation at {schedule_time}.")
    schedule.every().day.at(schedule_time).do(generate_timelapse)
    
    # Run a capture immediately
    job_capture_all()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run()
