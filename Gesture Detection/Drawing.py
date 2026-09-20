from PIL import TiffImagePlugin
from PIL import TiffImagePlugin
from PIL import TiffImagePlugin
import protobuf_patch
from camera_utils import open_camera, StreamSender
import cv2
import sys
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

def is_drawing_gesture(landmarks):
    """
    Returns True if ONLY the Index finger is up (Drawing mode).
    If both Index and Middle are up, drawing pauses (Move mode).
    """
    index_up = landmarks[8].y < landmarks[6].y
    middle_up = landmarks[12].y < landmarks[10].y
    return index_up and not middle_up

# Open webcam with robust retry helper
def main():
    global clear_pressed, quit_pressed, btn_clear_rect, btn_quit_rect

    cap = open_camera(0)
    if cap is None:
        print("Could not open camera hardware. Exiting.")
        sys.exit(1)

    stream_sender = StreamSender()

    # Store drawn emoji coordinates: list of (x, y) tuples
    points = []

    # Selected emoji and rendering settings
    EMOJI = "🌸"
    EMOJI_SIZE = 20

    # Global state for mouse interaction
    clear_pressed = False
    quit_pressed = False
    btn_clear_rect = (0, 0, 0, 0)
    btn_quit_rect = (0, 0, 0, 0)

    # Load system font capable of rendering color emojis
    font = None
    font_paths = [
        "C:/Windows/Fonts/seguiemj.ttf",
        "seguiemj.ttf",
        "/System/Library/Fonts/Apple Color Emoji.ttc",
    ]
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, EMOJI_SIZE)
            break
        except OSError:
            continue

    if font is None:
        font = ImageFont.load_default()

    button_cooldown = 0
    failed_frames = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            failed_frames += 1
            if failed_frames > 20:
                print("Failed to read webcam frame after multiple retries. Exiting...")
                break
            time.sleep(0.1)
            continue
        failed_frames = 0

        # Flip horizontally for natural mirror effect
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # Define button rectangles at top-right
        btn_clear_rect = (w - 230, 10, w - 125, 50)
        btn_quit_rect  = (w - 115, 10, w - 10, 50)

        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb_frame)

        status_text = "No Hand Detected"
        status_color = (0, 0, 255)

        if button_cooldown > 0:
            button_cooldown -= 1

        if result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:
                # Draw hand landmarks for visual tracking feedback
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                # Get index fingertip coordinates (Landmark 8)
                index_tip = hand_landmarks.landmark[8]
                cx, cy = int(index_tip.x * w), int(index_tip.y * h)

                x1_c, y1_c, x2_c, y2_c = btn_clear_rect
                x1_q, y1_q, x2_q, y2_q = btn_quit_rect

                in_clear_btn = (x1_c <= cx <= x2_c and y1_c <= cy <= y2_c)
                in_quit_btn  = (x1_q <= cx <= x2_q and y1_q <= cy <= y2_q)

                if in_clear_btn:
                    if button_cooldown == 0:
                        points.clear()
                        button_cooldown = 15
                        status_text = "Cleared!"
                elif in_quit_btn:
                    if button_cooldown == 0:
                        quit_pressed = True

                # Check if gesture is in drawing mode (and not hovering on buttons)
                if is_drawing_gesture(hand_landmarks.landmark):
                    if not (in_clear_btn or in_quit_btn):
                        status_text = "Drawing Mode (Index Up)"
                        status_color = (0, 255, 0)
                        # Visual cursor at fingertip
                        cv2.circle(frame, (cx, cy), 8, (0, 255, 0), -1)

                        # Avoid stacking too many points directly on top of each other
                        if not points or np.linalg.norm(np.array([cx, cy]) - np.array(points[-1])) > 5:
                            points.append((cx, cy))
                else:
                    if not (in_clear_btn or in_quit_btn):
                        status_text = "Paused / Move Mode"
                        status_color = (0, 255, 255)
                        cv2.circle(frame, (cx, cy), 8, (0, 255, 255), 2)

        # Handle mouse press on buttons
        if clear_pressed:
            points.clear()
            clear_pressed = False
            status_text = "Cleared!"

        if quit_pressed:
            break

        # Convert OpenCV image to PIL image to render Unicode/Emoji characters
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        # Draw all stored emoji points
        for pt in points:
            # Center the emoji around the point
            draw.text((pt[0] - EMOJI_SIZE // 2, pt[1] - EMOJI_SIZE // 2), EMOJI, font=font, embedded_color=True)

        # Convert back to OpenCV format
        frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # Draw visible UI Buttons
        # Clear Button
        x1_c, y1_c, x2_c, y2_c = btn_clear_rect
        cv2.rectangle(frame, (x1_c, y1_c), (x2_c, y2_c), (40, 40, 180), -1)
        cv2.rectangle(frame, (x1_c, y1_c), (x2_c, y2_c), (255, 255, 255), 2)
        cv2.putText(frame, "CLEAR", (x1_c + 15, y1_c + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        # Quit Button
        x1_q, y1_q, x2_q, y2_q = btn_quit_rect
        cv2.rectangle(frame, (x1_q, y1_q), (x2_q, y2_q), (0, 0, 180), -1)
        cv2.rectangle(frame, (x1_q, y1_q), (x2_q, y2_q), (255, 255, 255), 2)
        cv2.putText(frame, "QUIT", (x1_q + 25, y1_q + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        # Status Overlay
        cv2.putText(frame, f"Status: {status_text}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2, cv2.LINE_AA)
        cv2.putText(frame, "Touch/Click Buttons | 'C': Clear | 'Q'/ESC: Quit",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


        stream_sender.send_frame(frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):  # 'q', 'Q', or Esc
            break
        elif key in (ord('c'), ord('C')):  # 'c' or 'C'
            points.clear()

    cap.release()
    stream_sender.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
