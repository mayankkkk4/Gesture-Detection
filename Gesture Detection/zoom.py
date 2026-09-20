import protobuf_patch
from camera_utils import open_camera, StreamSender
import cv2
import sys
import mediapipe as mp
import pyautogui
import math
import time

# -----------------------------
# SETTINGS
# -----------------------------
CAM_WIDTH = 1280
CAM_HEIGHT = 720

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# -----------------------------
# MEDIAPIPE HANDS
# -----------------------------
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# -----------------------------
# CAMERA
# -----------------------------
cap = open_camera(0)
if cap is None:
    print("[ERROR] Could not open camera hardware for Zoom module.")
    sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)

stream_sender = StreamSender()

# -----------------------------
# VARIABLES
# -----------------------------
previous_distance = None
last_action_time = 0

COOLDOWN = 0.35
THRESHOLD = 40


# -----------------------------
# DISTANCE FUNCTION
# -----------------------------
def distance(p1, p2):
    return math.hypot(
        p2[0] - p1[0],
        p2[1] - p1[1]
    )


# -----------------------------
# MAIN LOOP
# -----------------------------
while True:

    success, frame = cap.read()

    if not success:
        print("Camera not available")
        break

    # Mirror camera
    frame = cv2.flip(frame, 1)

    # Convert BGR → RGB
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Detect hands
    results = hands.process(rgb)

    status = "Show your hands"

    # ---------------------------------
    # TWO HAND GESTURE
    # ---------------------------------
    if results.multi_hand_landmarks:

        number_of_hands = len(results.multi_hand_landmarks)

        # Draw landmarks
        for hand in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(
                frame,
                hand,
                mp_hands.HAND_CONNECTIONS
            )

        # =================================
        # TWO HAND ZOOM
        # =================================
        if number_of_hands == 2:

            hand1 = results.multi_hand_landmarks[0]
            hand2 = results.multi_hand_landmarks[1]

            # Index fingertips
            x1 = int(hand1.landmark[8].x * CAM_WIDTH)
            y1 = int(hand1.landmark[8].y * CAM_HEIGHT)

            x2 = int(hand2.landmark[8].x * CAM_WIDTH)
            y2 = int(hand2.landmark[8].y * CAM_HEIGHT)

            p1 = (x1, y1)
            p2 = (x2, y2)

            # Draw points
            cv2.circle(frame, p1, 12, (255, 0, 255), -1)
            cv2.circle(frame, p2, 12, (255, 0, 255), -1)

            cv2.line(
                frame,
                p1,
                p2,
                (255, 0, 255),
                3
            )

            # Calculate distance
            current_distance = distance(p1, p2)

            # First frame
            if previous_distance is None:
                previous_distance = current_distance

            change = current_distance - previous_distance

            current_time = time.time()

            # -----------------------------
            # ZOOM IN
            # -----------------------------
            if change > THRESHOLD:

                status = "ZOOM IN"

                if current_time - last_action_time > COOLDOWN:

                    pyautogui.hotkey("ctrl", "+")

                    last_action_time = current_time

                previous_distance = current_distance

            # -----------------------------
            # ZOOM OUT
            # -----------------------------
            elif change < -THRESHOLD:

                status = "ZOOM OUT"

                if current_time - last_action_time > COOLDOWN:

                    pyautogui.hotkey("ctrl", "-")

                    last_action_time = current_time

                previous_distance = current_distance

            else:
                status = "Two hands detected"

        # =================================
        # SINGLE HAND PINCH
        # =================================
        elif number_of_hands == 1:

            hand = results.multi_hand_landmarks[0]

            # Thumb tip
            thumb_x = int(
                hand.landmark[4].x * CAM_WIDTH
            )
            thumb_y = int(
                hand.landmark[4].y * CAM_HEIGHT
            )

            # Index tip
            index_x = int(
                hand.landmark[8].x * CAM_WIDTH
            )
            index_y = int(
                hand.landmark[8].y * CAM_HEIGHT
            )

            thumb = (thumb_x, thumb_y)
            index = (index_x, index_y)

            # Draw points
            cv2.circle(
                frame,
                thumb,
                12,
                (0, 255, 255),
                -1
            )

            cv2.circle(
                frame,
                index,
                12,
                (0, 255, 255),
                -1
            )

            cv2.line(
                frame,
                thumb,
                index,
                (0, 255, 255),
                3
            )

            # Calculate pinch distance
            current_distance = distance(
                thumb,
                index
            )

            if previous_distance is None:
                previous_distance = current_distance

            change = current_distance - previous_distance

            current_time = time.time()

            # -----------------------------
            # PINCH FINGERS APART
            # -----------------------------
            if change > THRESHOLD:

                status = "ZOOM IN"

                if current_time - last_action_time > COOLDOWN:

                    pyautogui.hotkey("ctrl", "+")

                    last_action_time = current_time

                previous_distance = current_distance

            # -----------------------------
            # PINCH FINGERS TOGETHER
            # -----------------------------
            elif change < -THRESHOLD:

                status = "ZOOM OUT"

                if current_time - last_action_time > COOLDOWN:

                    pyautogui.hotkey("ctrl", "-")

                    last_action_time = current_time

                previous_distance = current_distance

            else:
                status = "One hand detected"

    else:

        previous_distance = None
        status = "Show your hands"

    # -----------------------------
    # DISPLAY STATUS
    # -----------------------------
    cv2.rectangle(
        frame,
        (0, 0),
        (CAM_WIDTH, 70),
        (30, 30, 30),
        -1
    )

    cv2.putText(
        frame,
        status,
        (30, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (0, 255, 0),
        3
    )

    # Instructions
    cv2.putText(
        frame,
        "Two hands: Move apart = Zoom In | Move together = Zoom Out",
        (30, CAM_HEIGHT - 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    cv2.putText(
        frame,
        "R = Reset    Q / ESC = Exit",
        (30, CAM_HEIGHT - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )


    stream_sender.send_frame(frame)

    # Keyboard
    key = cv2.waitKey(1) & 0xFF

    if key == ord("r"):
        previous_distance = None
        print("Zoom gesture reset")

    elif key == ord("q") or key == 27:
        break


# -----------------------------
# CLEANUP
# -----------------------------
cap.release()
stream_sender.close()
cv2.destroyAllWindows()
hands.close()