import cv2
import mediapipe as mp
import pyautogui
import time

# Open camera
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("ERROR: Camera could not be opened.")
    print("Try changing VideoCapture(0) to VideoCapture(1).")
    exit()

# MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

drawing_utils = mp.solutions.drawing_utils

# Screen size
screen_width, screen_height = pyautogui.size()

last_action = 0
cooldown = 1.0

while True:

    ret, frame = cap.read()

    # Camera failed to provide frame
    if not ret or frame is None:
        print("ERROR: Could not read frame from camera.")
        break

    # Mirror image
    frame = cv2.flip(frame, 1)

    frame_height, frame_width, _ = frame.shape

    # Convert BGR -> RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Detect hands
    output = hands.process(rgb_frame)

    if output.multi_hand_landmarks:

        for hand in output.multi_hand_landmarks:

            drawing_utils.draw_landmarks(
                frame,
                hand,
                mp_hands.HAND_CONNECTIONS
            )

            landmarks = hand.landmark

            # Index finger = landmark 8
            index = landmarks[8]

            index_x = int(index.x * frame_width)
            index_y = int(index.y * frame_height)

            cv2.circle(
                frame,
                (index_x, index_y),
                10,
                (0, 255, 255),
                -1
            )

            # Thumb = landmark 4
            thumb = landmarks[4]

            thumb_x = int(thumb.x * frame_width)
            thumb_y = int(thumb.y * frame_height)

            cv2.circle(
                frame,
                (thumb_x, thumb_y),
                10,
                (255, 0, 255),
                -1
            )

            # Distance between thumb and index finger
            distance = ((index_x - thumb_x) ** 2 +
                        (index_y - thumb_y) ** 2) ** 0.5

            cv2.putText(
                frame,
                f"Distance: {int(distance)}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            # Example gesture:
            # Thumb + index close = Page Up
            # Thumb + index far = Page Down

            current_time = time.time()

            if current_time - last_action > cooldown:

                if distance < 50:
                    pyautogui.press("pageup")
                    last_action = current_time

                elif distance > 120:
                    pyautogui.press("pagedown")
                    last_action = current_time

    cv2.imshow("GestureX - Virtual Mouse", frame)

    # Press Q to exit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


cap.release()
cv2.destroyAllWindows()
hands.close()