import protobuf_patch
from camera_utils import open_camera, StreamSender
import cv2
import sys
import numpy as np
import mediapipe as mp
import pyautogui
import time
import math

# ============================================================
# SETTINGS
# ============================================================

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.01

CAM_WIDTH = 1280
CAM_HEIGHT = 720

FRAME_MARGIN = 80
SMOOTHING = 5

SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()

# Gesture thresholds
PINCH_THRESHOLD = 35
ZOOM_THRESHOLD = 30

CLICK_COOLDOWN = 0.40
ZOOM_COOLDOWN = 0.40
SCROLL_COOLDOWN = 0.10


# ============================================================
# MEDIAPIPE
# ============================================================

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

draw_points = mp_draw.DrawingSpec(
    color=(0, 255, 0),
    thickness=2,
    circle_radius=3
)

draw_connections = mp_draw.DrawingSpec(
    color=(255, 255, 0),
    thickness=2
)


# ============================================================
# GLOBAL VARIABLES
# ============================================================

previous_mouse_x = 0
previous_mouse_y = 0

last_click_time = 0
last_zoom_time = 0
last_scroll_time = 0

previous_zoom_distance = None

previous_time = 0


# ============================================================
# DISTANCE
# ============================================================

def get_distance(p1, p2):

    return math.hypot(
        p2[0] - p1[0],
        p2[1] - p1[1]
    )


# ============================================================
# FINGER DETECTION
# ============================================================

def finger_extended(wrist, tip, pip):

    return (
        get_distance(tip, wrist)
        >
        get_distance(pip, wrist) + 15
    )


# ============================================================
# MAIN
# ============================================================

def main():

    global previous_mouse_x
    global previous_mouse_y

    global last_click_time
    global last_zoom_time
    global last_scroll_time

    global previous_zoom_distance
    global previous_time

    # ========================================================
    # OPEN CAMERA
    # ========================================================

    cap = open_camera(0)

    if cap is None:

        print("\n========================================")
        print("ERROR: NO WORKING WEBCAM FOUND")
        print("========================================")
        print()
        print("Please check:")
        print("1. Your webcam is connected.")
        print("2. Windows Camera app can see the webcam.")
        print("3. No other application is using the webcam.")
        print("4. Windows Camera permissions are enabled.")
        print()
        print("Windows Settings:")
        print("Settings -> Privacy & security -> Camera")
        print()
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)

    stream_sender = StreamSender()

    print("\n==============================================")
    print("        AI GESTURE VIRTUAL MOUSE")
    print("==============================================")
    print()
    print("GESTURES:")
    print()
    print("Index finger       -> Move cursor")
    print("Thumb + Index      -> Left click")
    print("Thumb + Middle     -> Right click")
    print("Index + Middle     -> Scroll")
    print("Two index fingers apart   -> Zoom IN")
    print("Two index fingers together -> Zoom OUT")
    print()
    print("Q / ESC -> Exit")
    print()
    print("==============================================\n")

    failed_frames = 0

    # ========================================================
    # MAIN LOOP
    # ========================================================

    while cap.isOpened():

        success, frame = cap.read()

        if not success or frame is None:
            failed_frames += 1
            if failed_frames > 20:
                print("WARNING: Could not read camera frame after retries. Exiting...")
                break
            time.sleep(0.1)
            continue
        failed_frames = 0

        # ----------------------------------------------------
        # Flip camera
        # ----------------------------------------------------

        frame = cv2.flip(frame, 1)

        # ----------------------------------------------------
        # Actual frame size
        # ----------------------------------------------------

        frame_height, frame_width = frame.shape[:2]

        # ----------------------------------------------------
        # Active tracking area
        # ----------------------------------------------------

        cv2.rectangle(
            frame,
            (FRAME_MARGIN, FRAME_MARGIN),
            (
                frame_width - FRAME_MARGIN,
                frame_height - FRAME_MARGIN
            ),
            (255, 0, 255),
            2
        )

        # ----------------------------------------------------
        # Convert BGR -> RGB
        # ----------------------------------------------------

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        # ----------------------------------------------------
        # MediaPipe
        # ----------------------------------------------------

        results = hands.process(rgb)

        current_time = time.time()

        status = "Searching for Hand..."
        status_color = (0, 255, 255)

        hand_count = 0

        # ====================================================
        # HAND DETECTED
        # ====================================================

        if results.multi_hand_landmarks:

            hand_count = len(
                results.multi_hand_landmarks
            )

            # =================================================
            # TWO HAND MODE = ZOOM
            # =================================================

            if hand_count == 2:

                hand1 = results.multi_hand_landmarks[0]
                hand2 = results.multi_hand_landmarks[1]

                # Draw hands
                mp_draw.draw_landmarks(
                    frame,
                    hand1,
                    mp_hands.HAND_CONNECTIONS,
                    draw_points,
                    draw_connections
                )

                mp_draw.draw_landmarks(
                    frame,
                    hand2,
                    mp_hands.HAND_CONNECTIONS,
                    draw_points,
                    draw_connections
                )

                # Index fingertips
                p1 = (
                    int(
                        hand1.landmark[8].x
                        * frame_width
                    ),
                    int(
                        hand1.landmark[8].y
                        * frame_height
                    )
                )

                p2 = (
                    int(
                        hand2.landmark[8].x
                        * frame_width
                    ),
                    int(
                        hand2.landmark[8].y
                        * frame_height
                    )
                )

                # Distance
                current_distance = get_distance(
                    p1,
                    p2
                )

                # Draw points
                cv2.circle(
                    frame,
                    p1,
                    15,
                    (255, 0, 255),
                    -1
                )

                cv2.circle(
                    frame,
                    p2,
                    15,
                    (255, 0, 255),
                    -1
                )

                # Draw line
                cv2.line(
                    frame,
                    p1,
                    p2,
                    (255, 0, 255),
                    4
                )

                # Distance text
                cv2.putText(
                    frame,
                    f"Zoom Distance: "
                    f"{int(current_distance)}",
                    (20, 100),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )

                # Initialize
                if previous_zoom_distance is None:

                    previous_zoom_distance = (
                        current_distance
                    )

                # Difference
                difference = (
                    current_distance
                    -
                    previous_zoom_distance
                )

                # --------------------------------------------
                # ZOOM IN
                # --------------------------------------------

                if difference > ZOOM_THRESHOLD:

                    status = "ZOOM IN"
                    status_color = (0, 255, 0)

                    if (
                        current_time
                        -
                        last_zoom_time
                        >
                        ZOOM_COOLDOWN
                    ):

                        pyautogui.hotkey(
                            "ctrl",
                            "+"
                        )

                        last_zoom_time = current_time

                    previous_zoom_distance = (
                        current_distance
                    )

                # --------------------------------------------
                # ZOOM OUT
                # --------------------------------------------

                elif difference < -ZOOM_THRESHOLD:

                    status = "ZOOM OUT"
                    status_color = (0, 165, 255)

                    if (
                        current_time
                        -
                        last_zoom_time
                        >
                        ZOOM_COOLDOWN
                    ):

                        pyautogui.hotkey(
                            "ctrl",
                            "-"
                        )

                        last_zoom_time = current_time

                    previous_zoom_distance = (
                        current_distance
                    )

                else:

                    status = "Two Hands - Zoom Mode"
                    status_color = (255, 0, 255)

            # =================================================
            # ONE HAND MODE
            # =================================================

            elif hand_count == 1:

                # Reset zoom state
                previous_zoom_distance = None

                hand = results.multi_hand_landmarks[0]

                # Draw landmarks
                mp_draw.draw_landmarks(
                    frame,
                    hand,
                    mp_hands.HAND_CONNECTIONS,
                    draw_points,
                    draw_connections
                )

                landmarks = hand.landmark

                # Convert to pixel coordinates
                points = []

                for lm in landmarks:

                    x = int(
                        lm.x * frame_width
                    )

                    y = int(
                        lm.y * frame_height
                    )

                    points.append(
                        (x, y)
                    )

                if len(points) == 21:

                    wrist = points[0]

                    thumb_tip = points[4]

                    index_tip = points[8]
                    index_pip = points[6]

                    middle_tip = points[12]
                    middle_pip = points[10]

                    # ----------------------------------------
                    # Finger status
                    # ----------------------------------------

                    index_up = finger_extended(
                        wrist,
                        index_tip,
                        index_pip
                    )

                    middle_up = finger_extended(
                        wrist,
                        middle_tip,
                        middle_pip
                    )

                    # ----------------------------------------
                    # Pinch distances
                    # ----------------------------------------

                    thumb_index = get_distance(
                        thumb_tip,
                        index_tip
                    )

                    thumb_middle = get_distance(
                        thumb_tip,
                        middle_tip
                    )

                    # =================================================
                    # LEFT CLICK
                    # =================================================

                    if thumb_index < PINCH_THRESHOLD:

                        status = "LEFT CLICK"
                        status_color = (0, 255, 0)

                        cv2.circle(
                            frame,
                            index_tip,
                            15,
                            (0, 255, 0),
                            -1
                        )

                        if (
                            current_time
                            -
                            last_click_time
                            >
                            CLICK_COOLDOWN
                        ):

                            pyautogui.click()

                            last_click_time = (
                                current_time
                            )

                    # =================================================
                    # RIGHT CLICK
                    # =================================================

                    elif thumb_middle < PINCH_THRESHOLD:

                        status = "RIGHT CLICK"
                        status_color = (0, 0, 255)

                        cv2.circle(
                            frame,
                            middle_tip,
                            15,
                            (0, 0, 255),
                            -1
                        )

                        if (
                            current_time
                            -
                            last_click_time
                            >
                            CLICK_COOLDOWN
                        ):

                            pyautogui.rightClick()

                            last_click_time = (
                                current_time
                            )

                    # =================================================
                    # SCROLL
                    # =================================================

                    elif index_up and middle_up:

                        status = "SCROLLING"
                        status_color = (0, 255, 255)

                        center_y = (
                            index_tip[1]
                            +
                            middle_tip[1]
                        ) // 2

                        if (
                            current_time
                            -
                            last_scroll_time
                            >
                            SCROLL_COOLDOWN
                        ):

                            if center_y < (
                                frame_height // 2 - 50
                            ):

                                pyautogui.scroll(3)

                                last_scroll_time = (
                                    current_time
                                )

                            elif center_y > (
                                frame_height // 2 + 50
                            ):

                                pyautogui.scroll(-3)

                                last_scroll_time = (
                                    current_time
                                )

                    # =================================================
                    # MOVE CURSOR
                    # =================================================

                    elif (
                        index_up
                        and
                        not middle_up
                        and
                        thumb_index >= PINCH_THRESHOLD
                    ):

                        status = "MOVING CURSOR"
                        status_color = (255, 0, 0)

                        # Map camera to screen
                        mouse_x = np.interp(
                            index_tip[0],
                            (
                                FRAME_MARGIN,
                                frame_width - FRAME_MARGIN
                            ),
                            (
                                0,
                                SCREEN_WIDTH
                            )
                        )

                        mouse_y = np.interp(
                            index_tip[1],
                            (
                                FRAME_MARGIN,
                                frame_height - FRAME_MARGIN
                            ),
                            (
                                0,
                                SCREEN_HEIGHT
                            )
                        )

                        # Limit cursor
                        mouse_x = max(
                            0,
                            min(
                                SCREEN_WIDTH - 1,
                                mouse_x
                            )
                        )

                        mouse_y = max(
                            0,
                            min(
                                SCREEN_HEIGHT - 1,
                                mouse_y
                            )
                        )

                        # Smooth
                        current_mouse_x = (
                            previous_mouse_x
                            +
                            (
                                mouse_x
                                -
                                previous_mouse_x
                            )
                            /
                            SMOOTHING
                        )

                        current_mouse_y = (
                            previous_mouse_y
                            +
                            (
                                mouse_y
                                -
                                previous_mouse_y
                            )
                            /
                            SMOOTHING
                        )

                        # Move mouse
                        pyautogui.moveTo(
                            int(current_mouse_x),
                            int(current_mouse_y)
                        )

                        previous_mouse_x = (
                            current_mouse_x
                        )

                        previous_mouse_y = (
                            current_mouse_y
                        )

                        cv2.circle(
                            frame,
                            index_tip,
                            12,
                            (255, 0, 0),
                            -1
                        )

                    else:

                        status = "Hand Detected"
                        status_color = (
                            255,
                            255,
                            255
                        )

        else:

            previous_zoom_distance = None

        # ====================================================
        # HEADER
        # ====================================================

        cv2.rectangle(
            frame,
            (0, 0),
            (frame_width, 75),
            (30, 30, 30),
            -1
        )

        cv2.putText(
            frame,
            status,
            (20, 48),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            status_color,
            2
        )

        # ====================================================
        # HAND COUNT
        # ====================================================

        cv2.putText(
            frame,
            f"Hands: {hand_count}",
            (
                frame_width - 180,
                35
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        # ====================================================
        # FPS
        # ====================================================

        current_time_fps = time.time()

        if previous_time != 0:

            fps = (
                1 /
                (
                    current_time_fps
                    -
                    previous_time
                )
            )

        else:

            fps = 0

        previous_time = current_time_fps

        cv2.putText(
            frame,
            f"FPS: {int(fps)}",
            (
                frame_width - 180,
                65
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        # ====================================================
        # INSTRUCTIONS
        # ====================================================

        cv2.putText(
            frame,
            "Index: Move | Pinch: Click | 2 Hands: Zoom",
            (20, frame_height - 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            "Q / ESC: Exit",
            (20, frame_height - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        # ====================================================
        # DISPLAY & WEB STREAMING
        # ====================================================


        stream_sender.send_frame(frame)

        # ====================================================
        # KEYBOARD
        # ====================================================

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27:

            break

    # ========================================================
    # CLEANUP
    # ========================================================

    cap.release()

    stream_sender.close()

    cv2.destroyAllWindows()

    hands.close()

    print("\nAI Gesture Virtual Mouse stopped.")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()