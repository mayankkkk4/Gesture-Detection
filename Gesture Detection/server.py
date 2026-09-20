import protobuf_patch
import os
import sys
import subprocess
import signal
import time
import socket
import threading
import webbrowser
from flask import Flask, jsonify, send_from_directory, request, Response

app = Flask(__name__, static_folder='.')

# Script Name Mappings
SCRIPT_MAP = {
    'virtual_mouse': 'virtual_mouse.py',
    'smart_presentation': 'smart_presentation.py',
    'system_adjustment': 'system_adjustment.py',
    'zoom': 'zoom.py',
    'Drawing': 'Drawing.py',
    'Steering_wheel': 'Steering wheel.py'
}

import cv2
import numpy as np

current_process = None
current_module_key = None
latest_frame = None

def create_placeholder_jpeg(text="Initializing Gesture Engine..."):
    try:
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(img, text, (40, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 170), 2)
        cv2.putText(img, "Connecting to camera hardware...", (40, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        _, buffer = cv2.imencode('.jpg', img)
        return buffer.tobytes()
    except Exception:
        return None

placeholder_frame = create_placeholder_jpeg()

def udp_frame_receiver():
    """Background thread listening for UDP frame buffers from active gesture processes."""
    global latest_frame
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 5002))
    while True:
        try:
            data, _ = sock.recvfrom(65535)
            if data:
                latest_frame = data
        except Exception:
            time.sleep(0.01)

# Start frame receiver thread
udp_thread = threading.Thread(target=udp_frame_receiver, daemon=True)
udp_thread.start()

def terminate_active_process():
    """Terminates the currently running gesture detection subprocess and any orphaned gesture instances."""
    global current_process, current_module_key, latest_frame
    latest_frame = None
    if current_process is not None:
        try:
            current_process.terminate()
            current_process.wait(timeout=1.5)
        except Exception:
            try:
                current_process.kill()
            except Exception:
                pass
        current_process = None
        current_module_key = None

    # Purge any orphaned gesture script processes to guarantee exclusive camera access
    try:
        import psutil
        my_pid = os.getpid()
        script_names = [name.lower() for name in SCRIPT_MAP.values()]
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] != my_pid and proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
                    if any(s in cmdline for s in script_names):
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/styles.css')
def styles():
    return send_from_directory('.', 'styles.css')

@app.route('/app.js')
def scripts():
    return send_from_directory('.', 'app.js')

def gen_frames():
    """Generator function yielding MJPEG frame stream."""
    global latest_frame
    while True:
        frame_data = latest_frame if latest_frame is not None else placeholder_frame
        if frame_data is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
            time.sleep(0.033)  # ~30 FPS
        else:
            time.sleep(0.1)

@app.route('/video_feed')
def video_feed():
    """Serves the live MJPEG camera stream from active gesture engines."""
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/status', methods=['GET'])
def get_status():
    global current_process, current_module_key, latest_frame
    # Check if process is still running
    if current_process is not None:
        poll = current_process.poll()
        if poll is not None:
            print(f"[Server] Active module '{current_module_key}' terminated with exit code {poll}")
            current_process = None
            current_module_key = None
            latest_frame = None

    return jsonify({
        'status': 'online',
        'active_module': current_module_key
    })

@app.route('/api/launch/<script_key>', methods=['POST'])
def launch_module(script_key):
    global current_process, current_module_key, latest_frame

    if script_key not in SCRIPT_MAP:
        return jsonify({'error': 'Invalid script key'}), 400

    script_filename = SCRIPT_MAP[script_key]
    script_path = os.path.join(os.path.dirname(__file__), script_filename)

    if not os.path.exists(script_path):
        return jsonify({'error': f'Script {script_filename} not found'}), 404

    # Stop any existing process first
    terminate_active_process()

    # Show initial loading placeholder in video stream
    latest_frame = placeholder_frame

    # Delay for camera hardware resource release
    time.sleep(0.6)

    try:
        # Launch python script as a subprocess
        current_process = subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(__file__))
        current_module_key = script_key
        print(f"[Server] Successfully launched module '{script_key}' (PID: {current_process.pid})")
        return jsonify({'success': True, 'launched': script_key})
    except Exception as e:
        latest_frame = None
        return jsonify({'error': str(e)}), 500

@app.route('/api/terminate/<script_key>', methods=['POST'])
def terminate_module(script_key):
    global current_module_key
    if current_module_key == script_key:
        terminate_active_process()
    return jsonify({'success': True})

@app.route('/api/stop_all', methods=['POST'])
def stop_all():
    terminate_active_process()
    return jsonify({'success': True})

if __name__ == '__main__':
    # Purge any leftover/orphaned gesture processes from previous sessions
    terminate_active_process()

    print("==================================================")
    print("      GestureX Control Server Starting            ")
    print("  Access dashboard at: http://localhost:5000      ")
    print("==================================================")
    
    # Auto-open browser dashboard
    webbrowser.open("http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=False)

