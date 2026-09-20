import protobuf_patch
from camera_utils import open_camera, StreamSender
import cv2
import numpy as np
import mediapipe as mp
import math
import time
import sys

# Try importing pycaw for master volume control
try:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume_obj = interface.QueryInterface(IAudioEndpointVolume)
    vol_range = volume_obj.GetVolumeRange()  # e.g., (-65.25, 0.0, 0.03125)
    min_vol, max_vol = vol_range[0], vol_range[1]
    HAS_PYCAW = True
except Exception as e:
    HAS_PYCAW = False
    volume_obj = None

# Try importing screen_brightness_control for display brightness
try:
    import screen_brightness_control as sbc
    HAS_SBC = True
except Exception as e:
    HAS_SBC = False

# Fallback volume using PyAutoGUI if pycaw is unavailable
import pyautogui
pyautogui.FAILSAFE = False

# Camera setup
wCam, hCam = 1280, 720

# MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.4,
    min_tracking_confidence=0.4
)
mp_draw = mp.solutions.drawing_utils

# Min and Max pinch distance thresholds (in pixels)
MIN_DIST = 25
MAX_DIST = 220

# UI State & Smoothing
vol_percent = 50
vol_bar = 400
bright_percent = 50
bright_bar = 400

def get_distance(p1, p2):
    """Euclidean distance between two 2D points."""
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def set_system_volume(percent):
    """Sets master volume percentage (0 to 100)."""
    percent = max(0, min(100, percent))
    if HAS_PYCAW and volume_obj:
        try:
            # Map percentage (0-100) to scalar (0.0 to 1.0)
            volume_obj.SetMasterVolumeLevelScalar(percent / 100.0, None)
        except Exception:
            pass
    else:
        # Fallback using pyautogui key presses
        pass

def set_system_brightness(percent):
    """Sets display brightness percentage (0 to 100)."""
    percent = max(0, min(100, percent))
    if HAS_SBC:
        try:
            sbc.set_brightness(int(percent))
        except Exception:
            pass

def main():
    global vol_percent, vol_bar, bright_percent, bright_bar

    cap = open_camera(0)
    if cap is None:
        print("Could not open camera hardware. Exiting...")
        sys.exit(1)
    cap.set(3, wCam)
    cap.set(4, hCam)

    stream_sender = StreamSender()

    pTime = 0

    print("=== System Brightness & Volume Gesture Controller ===")
    print("Controls:")
    print(" - LEFT Hand (or Left side of screen)  : Control BRIGHTNESS (Pinch Thumb & Index)")
    print(" - RIGHT Hand (or Right side of screen): Control VOLUME (Pinch Thumb & Index)")
    print(" - Press 'q' or 'Esc' to Quit.\n")

    failed_frames = 0

    while cap.isOpened():
        success, img = cap.read()
        if not success:
            failed_frames += 1
            if failed_frames > 20:
                print("Webcam frame capture failed after multiple retries. Exiting...")
                break
            time.sleep(0.1)
            continue
        failed_frames = 0

        # Mirror frame
        img = cv2.flip(img, 1)
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = hands.process(imgRGB)

        if results.multi_hand_landmarks and results.multi_handedness:
            for handLms, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                mp_draw.draw_landmarks(img, handLms, mp_hands.HAND_CONNECTIONS)

                landmarks = handLms.landmark
                lm_list = [(int(lm.x * wCam), int(lm.y * hCam)) for lm in landmarks]

                if len(lm_list) >= 21:
                    thumb_tip = lm_list[4]
                    index_tip = lm_list[8]
                    cx, cy = (thumb_tip[0] + index_tip[0]) // 2, (thumb_tip[1] + index_tip[1]) // 2

                    # Draw pinch visual elements
                    cv2.circle(img, thumb_tip, 10, (255, 0, 255), cv2.FILLED)
                    cv2.circle(img, index_tip, 10, (255, 0, 255), cv2.FILLED)
                    cv2.line(img, thumb_tip, index_tip, (255, 0, 255), 3)
                    cv2.circle(img, (cx, cy), 10, (0, 255, 0), cv2.FILLED)

                    dist = get_distance(thumb_tip, index_tip)

                    # Determine hand label ('Left' vs 'Right') or screen half
                    hand_label = handedness.classification[0].label  # 'Left' or 'Right'
                    
                    # Note: Because frame is flipped, MediaPipe 'Left' hand appears on Left side of screen
                    is_brightness_control = (hand_label == 'Left') or (cx < wCam // 2 and len(results.multi_hand_landmarks) == 1)

                    if is_brightness_control:
                        # Brightness control
                        bright_percent = int(np.interp(dist, [MIN_DIST, MAX_DIST], [0, 100]))
                        bright_bar = int(np.interp(dist, [MIN_DIST, MAX_DIST], [400, 150]))
                        set_system_brightness(bright_percent)

                        if dist < MIN_DIST + 5:
                            cv2.circle(img, (cx, cy), 12, (0, 255, 255), cv2.FILLED)
                    else:
                        # Volume control
                        vol_percent = int(np.interp(dist, [MIN_DIST, MAX_DIST], [0, 100]))
                        vol_bar = int(np.interp(dist, [MIN_DIST, MAX_DIST], [400, 150]))
                        set_system_volume(vol_percent)

                        if dist < MIN_DIST + 5:
                            cv2.circle(img, (cx, cy), 12, (0, 255, 0), cv2.FILLED)

        # --- DRAW VISUAL UI BARS ---
        # 1. Brightness Bar (Left Side - Cyan/Yellow)
        cv2.rectangle(img, (50, 150), (85, 400), (0, 255, 255), 3)
        cv2.rectangle(img, (50, bright_bar), (85, 400), (0, 255, 255), cv2.FILLED)
        cv2.putText(img, f'{bright_percent}%', (40, 440), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.putText(img, 'BRIGHTNESS', (25, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # 2. Volume Bar (Right Side - Green/Blue)
        cv2.rectangle(img, (wCam - 85, 150), (wCam - 50, 400), (0, 255, 0), 3)
        cv2.rectangle(img, (wCam - 85, vol_bar), (wCam - 50, 400), (0, 255, 0), cv2.FILLED)
        cv2.putText(img, f'{vol_percent}%', (wCam - 95, 440), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(img, 'VOLUME', (wCam - 125, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Header HUD
        cv2.rectangle(img, (0, 0), (wCam, 60), (30, 30, 30), cv2.FILLED)
        cv2.putText(img, "System Brightness & Volume Control", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # FPS Counter
        cTime = time.time()
        fps = 1 / (cTime - pTime) if (cTime - pTime) > 0 else 0
        pTime = cTime
        cv2.putText(img, f'FPS: {int(fps)}', (wCam - 150, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Show Window
        stream_sender.send_frame(img)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    cap.release()
    stream_sender.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
