import protobuf_patch
from camera_utils import open_camera, StreamSender
import cv2
import sys
import numpy as np
import mediapipe as mp
import pyautogui
import time

# Disable PyAutoGUI failsafe to avoid unexpected exits
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# Camera Settings
wCam, hCam = 1280, 720

# MediaPipe Hands Setup
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.4,
    min_tracking_confidence=0.4
)
mp_draw = mp.solutions.drawing_utils

# Canvas for air annotations during presentation
canvas = np.zeros((hCam, wCam, 3), dtype=np.uint8)

# Swipe Tracking Variables
prev_x = None
swipe_threshold = 80  # Pixels moved to trigger swipe
gesture_cooldown = 1.0  # Seconds delay between slide changes
last_gesture_time = 0

# Drawing tracking
prev_draw_point = None

def get_fingers_up(landmarks):
    """
    Returns a list of 5 booleans indicating which fingers are up.
    Order: [Thumb, Index, Middle, Ring, Pinky]
    """
    fingers = []
    
    # Thumb (Check X coordinate relative to IP joint for horizontal extension)
    # Assumes right/mirrored hand orientation
    if landmarks[4].x < landmarks[3].x:
        fingers.append(1)
    else:
        fingers.append(0)

    # 4 Fingers (Check Y coordinate: Tip vs PIP joint)
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    
    for tip, pip in zip(tips, pips):
        if landmarks[tip].y < landmarks[pip].y:
            fingers.append(1)
        else:
            fingers.append(0)

    return fingers

def main():
    global prev_x, last_gesture_time, canvas, prev_draw_point

    cap = open_camera(0)
    if cap is None:
        print("Could not open camera hardware. Exiting...")
        sys.exit(1)
    cap.set(3, wCam)
    cap.set(4, hCam)

    stream_sender = StreamSender()

    pTime = 0
    annotation_color = (0, 0, 255)  # Red for drawing
    laser_color = (0, 255, 255)       # Yellow/Cyan laser

    print("=== AI Smart Presentation Controller Started ===")
    print("Controls & Gestures:")
    print(" 1. Next Slide         : Swipe Hand RIGHT (or Index Pointing Right)")
    print(" 2. Previous Slide     : Swipe Hand LEFT (or Index Pointing Left)")
    print(" 3. Laser Pointer      : Index Finger UP (Red Laser dot follows tip)")
    print(" 4. Draw / Annotate    : Index + Middle Fingers UP")
    print(" 5. Clear Annotations  : Open Palm (All 5 Fingers UP)")
    print(" 6. Blank Screen (B)   : Fist (All Fingers DOWN)")
    print(" - Press 'c' to manually clear annotations")
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

        # Mirror frame for natural interaction
        img = cv2.flip(img, 1)

        # Convert image to RGB for MediaPipe
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = hands.process(imgRGB)

        current_time = time.time()
        status_text = "Presentation Mode Active"
        status_color = (255, 255, 255)

        if results.multi_hand_landmarks:
            # Focus on primary hand
            handLms = results.multi_hand_landmarks[0]
            mp_draw.draw_landmarks(img, handLms, mp_hands.HAND_CONNECTIONS)

            landmarks = handLms.landmark
            lm_list = [(int(lm.x * wCam), int(lm.y * hCam)) for lm in landmarks]

            if len(lm_list) >= 21:
                wrist_x = lm_list[0][0]
                index_tip = lm_list[8]
                index_pip = lm_list[6]
                middle_tip = lm_list[12]

                fingers = get_fingers_up(landmarks)
                total_fingers = sum(fingers)

                # --- 1. SWIPE DETECTION (Next / Previous Slide) ---
                if current_time - last_gesture_time > gesture_cooldown:
                    if prev_x is not None:
                        delta_x = wrist_x - prev_x

                        # Swipe Right -> Next Slide
                        if delta_x > swipe_threshold:
                            pyautogui.press('right')
                            status_text = ">> NEXT SLIDE >>"
                            status_color = (0, 255, 0)
                            last_gesture_time = current_time
                            prev_x = None

                        # Swipe Left -> Previous Slide
                        elif delta_x < -swipe_threshold:
                            pyautogui.press('left')
                            status_text = "<< PREVIOUS SLIDE <<"
                            status_color = (0, 165, 255)
                            last_gesture_time = current_time
                            prev_x = None
                        else:
                            prev_x = wrist_x
                    else:
                        prev_x = wrist_x

                # --- 2. LASER POINTER MODE (Index Finger UP only) ---
                if fingers == [0, 1, 0, 0, 0]:
                    cv2.circle(img, index_tip, 12, (0, 0, 255), cv2.FILLED)
                    cv2.circle(img, index_tip, 20, laser_color, 2)
                    status_text = "Laser Pointer Active"
                    status_color = (0, 0, 255)
                    prev_draw_point = None

                # --- 3. DRAW / ANNOTATE MODE (Index + Middle Fingers UP) ---
                elif fingers == [0, 1, 1, 0, 0] or fingers == [1, 1, 1, 0, 0]:
                    cv2.circle(img, index_tip, 8, annotation_color, cv2.FILLED)
                    status_text = "Annotating / Air Pen"
                    status_color = (255, 0, 255)

                    if prev_draw_point is not None:
                        cv2.line(canvas, prev_draw_point, index_tip, annotation_color, 5)
                    prev_draw_point = index_tip

                else:
                    prev_draw_point = None

                # --- 4. CLEAR ANNOTATIONS GESTURE (Open Palm - 5 Fingers UP) ---
                if total_fingers == 5:
                    canvas = np.zeros((hCam, wCam, 3), dtype=np.uint8)
                    status_text = "Cleared Annotations"
                    status_color = (255, 255, 0)

                # --- 5. BLANK / BLACK SCREEN GESTURE (Fist - 0 Fingers UP) ---
                if total_fingers == 0 and (current_time - last_gesture_time > gesture_cooldown):
                    pyautogui.press('b')  # PowerPoint 'B' key toggles black screen
                    status_text = "Toggle Black Screen (B)"
                    status_color = (128, 128, 128)
                    last_gesture_time = current_time

        else:
            prev_x = None
            prev_draw_point = None

        # Merge drawing canvas onto live video frame
        img_gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
        _, img_inv = cv2.threshold(img_gray, 20, 255, cv2.THRESH_BINARY_INV)
        img_inv = cv2.cvtColor(img_inv, cv2.COLOR_GRAY2BGR)
        img = cv2.bitwise_and(img, img_inv)
        img = cv2.bitwise_or(img, canvas)

        # UI Overlay Header Bar
        cv2.rectangle(img, (0, 0), (wCam, 60), (30, 30, 30), cv2.FILLED)
        cv2.putText(img, status_text, (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 1.1, status_color, 2)

        # FPS Counter
        cTime = time.time()
        fps = 1 / (cTime - pTime) if (cTime - pTime) > 0 else 0
        pTime = cTime
        cv2.putText(img, f'FPS: {int(fps)}', (wCam - 150, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)


        stream_sender.send_frame(img)

        # Keyboard Controls
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            canvas = np.zeros((hCam, wCam, 3), dtype=np.uint8)
        elif key == ord('q') or key == 27:
            break

    cap.release()
    stream_sender.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
