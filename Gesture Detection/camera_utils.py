import protobuf_patch
import cv2
import time
import socket
import numpy as np

def open_camera(camera_index=0, max_retries=25, retry_delay=0.25):
    """
    Robustly opens a VideoCapture camera source with multiple backends and retries.
    Handles OS DirectShow camera release delays gracefully when transitioning from browser stream.
    """
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
    preferred_index = camera_index if camera_index is not None else 0
    candidate_indices = [preferred_index] + [i for i in range(3) if i != preferred_index]

    for attempt in range(max_retries):
        for idx in candidate_indices:
            for backend in backends:
                try:
                    cap = cv2.VideoCapture(idx, backend)
                    if cap.isOpened():
                        # Read a test frame to ensure device driver is sending active video pixels
                        ret, test_frame = cap.read()
                        if ret and test_frame is not None and test_frame.size > 0:
                            print(f"[CameraUtils] Successfully opened camera index {idx} with backend {backend} on attempt {attempt + 1}")
                            return cap
                        cap.release()
                except Exception as e:
                    pass
        time.sleep(retry_delay)

    print("[CameraUtils] Warning: Could not open webcam after max retries.")
    return None

class StreamSender:
    """
    Transmits compressed JPEG frame buffers over local UDP socket to server.py for MJPEG web streaming.
    """
    def __init__(self, host='127.0.0.1', port=5002):
        self.host = host
        self.port = port
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except Exception:
            self.sock = None

    def send_frame(self, frame, max_width=640, quality=60):
        if self.sock is None or frame is None or frame.size == 0:
            return

        try:
            h, w = frame.shape[:2]
            if w > max_width:
                scale = max_width / float(w)
                dim = (max_width, int(h * scale))
                send_img = cv2.resize(frame, dim, interpolation=cv2.INTER_AREA)
            else:
                send_img = frame

            q = quality
            success, buffer = cv2.imencode('.jpg', send_img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
            if success:
                data = buffer.tobytes()
                while len(data) >= 60000 and q > 20:
                    q -= 15
                    success, buffer = cv2.imencode('.jpg', send_img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
                    if success:
                        data = buffer.tobytes()
                    else:
                        break
                if success and len(data) < 64000:
                    self.sock.sendto(data, (self.host, self.port))
        except Exception:
            pass

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
