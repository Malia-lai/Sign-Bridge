import mediapipe as mp
import numpy as np
import os
import cv2
import time

# --- 1. PATH CONFIGURATION ---
current_path = os.getcwd()
DATA_FILE = os.path.join(current_path, 'gesture_landmarks.npy')
LABEL_FILE = os.path.join(current_path, 'gesture_labels.npy')

print(f"--- PATH CHECK ---")
print(f"Files will be saved at: {DATA_FILE}")

# --- 2. CONFIGURATION ---
GESTURES = {'h': 'hello',
            't': 'eat',
            'l': 'love',
            's': 'sleep',
            'm': 'hate',
            'p': 'peace',
            'n': 'not',
            'e': 'eat',
            'i': 'I',
            'y': 'Thank you',
            'o': 'Please',
            '1': 'id',
            '2': 'license',
            '3': 'passport',
            '4': 'money',
            '5': 'help',
            '6': 'wait',
            }
SEQUENCE_LENGTH = 20
SEQUENCE_LIST = []
counts = {label: 0 for label in GESTURES.values()}

# Recording & Countdown State Variables
recording = False
record_label = None
counting_down = False
countdown_start_time = 0
COUNTDOWN_DURATION = 2.0  # 2 seconds delay

# --- 3. MEDIAPIPE SETUP ---
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)

def save_dataset(data, label):
    print(f"Attempting to save '{label}'...")
    try:
        new_seq = np.array(data, dtype=np.float32).reshape(1, SEQUENCE_LENGTH, 126)
        new_label = np.array([label])

        if not os.path.exists(DATA_FILE):
            np.save(DATA_FILE, new_seq)
            print(f"Created new file: {DATA_FILE}")
        else:
            old_data = np.load(DATA_FILE)
            np.save(DATA_FILE, np.vstack((old_data, new_seq)))
            print(f"Updated existing file.")

        if not os.path.exists(LABEL_FILE):
            np.save(LABEL_FILE, new_label)
        else:
            old_labels = np.load(LABEL_FILE)
            np.save(LABEL_FILE, np.append(old_labels, new_label))

        print("SAVE COMPLETE!")
    except Exception as e:
        print(f"ERROR IN SAVE_DATASET: {e}")

def draw_ui(frame, current_counts, recording_state, counting_down_state, progress=0, cd_progress=0, label=""):
    h, w = frame.shape[:2]
    
    # Dynamic rectangle height based on number of gestures
    num_gestures = len(current_counts)
    rect_height = 20 + (num_gestures * 30)
    cv2.rectangle(frame, (0, 0), (220, rect_height), (30, 30, 30), -1)
    
    for i, (lbl, count) in enumerate(current_counts.items()):
        cv2.putText(frame, f"{lbl}: {count}", (10, 30 + (i * 30)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Bottom helper text
    cv2.putText(frame, "Press gesture keys to record",
                (10, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Countdown Visual Indicator (Orange)
    if counting_down_state:
        rem_sec = max(1, int(np.ceil(COUNTDOWN_DURATION - (time.time() - countdown_start_time))))
        cv2.putText(frame, f"Get Ready for '{label}': {rem_sec}s", 
                    (20, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
        bar_w = int((w - 40) * cd_progress)
        cv2.rectangle(frame, (20, h - 25), (20 + bar_w, h - 10), (0, 165, 255), -1)

    # Recording Visual Indicator (Green)
    elif recording_state:
        cv2.putText(frame, f"Recording '{label}'...", 
                    (20, h - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        bar_w = int((w - 40) * progress)
        cv2.rectangle(frame, (20, h - 25), (20 + bar_w, h - 10), (0, 255, 0), -1)

# --- 4. MAIN LOOP ---
print("Tentative de connexion a la webcam...")
def init_webcam():
    for backend in [cv2.CAP_DSHOW, None]:
        for idx in [0, 1, 2]:
            try:
                c = cv2.VideoCapture(idx, backend) if backend is not None else cv2.VideoCapture(idx)
                if c.isOpened():
                    for _ in range(3):
                        ret, test_frame = c.read()
                        if ret and test_frame is not None:
                            print(f"[OK] Webcam connectee sur index {idx} !")
                            return c
                        time.sleep(0.05)
                    c.release()
            except Exception:
                pass
    return None

cap = init_webcam()
if cap is None:
    print("\n[ERREUR] Impossible d'ouvrir la webcam !")
    print("Verifiez les autorisations de camera dans Windows ou fermez les applications qui l'utilisent.")
    input("\nAppuyez sur Entree pour fermer...")
    exit(1)

fail_count = 0
while cap.isOpened():
    ret, frame = cap.read()
    if not ret or frame is None:
        fail_count += 1
        if fail_count > 30:
            break
        time.sleep(0.03)
        continue
    fail_count = 0

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    # Always start with a clean list of zeros
    frame_landmarks = [0.0] * 126

    if result.multi_hand_landmarks:
        coords = []
        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            for lm in hand_landmarks.landmark:
                coords.extend([lm.x, lm.y, lm.z])
        # Pad or trim to exactly 126
        coords = coords[:126]
        frame_landmarks[:len(coords)] = coords

    # Countdown Logic
    cd_progress = 0
    if counting_down:
        elapsed = time.time() - countdown_start_time
        cd_progress = min(1.0, elapsed / COUNTDOWN_DURATION)
        if elapsed >= COUNTDOWN_DURATION:
            counting_down = False
            recording = True
            SEQUENCE_LIST = []

    # Recording Logic
    if recording:
        SEQUENCE_LIST.append(frame_landmarks)
        if len(SEQUENCE_LIST) >= SEQUENCE_LENGTH:
            recording = False
            save_dataset(SEQUENCE_LIST, record_label)
            counts[record_label] += 1
            SEQUENCE_LIST = []

    draw_ui(frame, counts, recording, counting_down,
            len(SEQUENCE_LIST) / SEQUENCE_LENGTH if recording else 0,
            cd_progress, record_label)
    cv2.imshow('Sign Language Collector', frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    
    # Only trigger if not already recording or counting down
    if key != 0xFF and not recording and not counting_down:
        key_char = chr(key)
        if key_char in GESTURES:
            record_label = GESTURES[key_char]
            counting_down = True
            countdown_start_time = time.time()
            SEQUENCE_LIST = []

cap.release()
cv2.destroyAllWindows()