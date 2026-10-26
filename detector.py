"""
detector.py - Real-time sign language detector for FastAPI WebSocket backend.
Key performance optimizations:
  - Global model loading with @tf.function and warm-up dummy tensor (loaded once)
  - Accepts binary JPEG bytes at 320x240
  - Thread-safe frame processing for asyncio.to_thread
  - Per-stage timings: decode, MediaPipe, LSTM, total
  - Verbatim MediaPipe settings, LSTM architecture, and classify_geometry
"""
import os
import math
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import mediapipe as mp
import cv2

# TensorFlow / Keras setup
try:
    import tensorflow as tf
    from tensorflow.keras.models import load_model, Sequential
    from tensorflow.keras.layers import Input, LSTM, Dense
    TF_AVAILABLE = True
except Exception as e:
    tf = None
    TF_AVAILABLE = False
    print(f"[WARN] TensorFlow not loaded in detector: {e}")

# ==========================================================
# 0. CONFIGURATION & CONSTANTS
# ==========================================================
BASE_DIR = Path(__file__).parent.resolve()
MODEL_FILE = str(BASE_DIR / 'action.h5')
LABEL_FILE = str(BASE_DIR / 'gesture_labels.npy')

ONCE_PER_SENTENCE = ["hello"]
BLOCK_IMMEDIATE_REPEAT = True
SEQUENCE_LENGTH = 20

# Thresholds
CONFIDENCE_THRESHOLD = 0.75
STABLE_DURATION = 0.35
COOLDOWN = 1.8

DISPLAY_NAMES: Dict[str, str] = {
    'hello': 'Hello',
    'peace': 'Peace',
    'love': 'Love',
    'eat': 'Eat',
    'sleep': 'Sleep',
    'I': 'I',
    'not': 'Not',
    'Shawarma': 'Shawarma',
    'tacos': 'Tacos',
    'Thank you': 'Thank you',
    'Please': 'Please',
    'id': 'ID',
    'license': 'License',
    'passport': 'Passport',
    'money': 'Money',
    'help': 'Help',
    'wait': 'Wait',
}

def to_display_name(label: str) -> str:
    if not label:
        return ''
    return DISPLAY_NAMES.get(label, label.capitalize())


def get_allowed_best_sign(sentence_history, probabilities, threshold, actions_list):
    once_set = {s.lower() for s in ONCE_PER_SENTENCE}
    history_lower = [s.lower() for s in sentence_history]
    last_word = history_lower[-1] if history_lower else None

    valid_candidates = []
    for i, sign in enumerate(actions_list):
        prob = float(probabilities[i]) if i < len(probabilities) else 0.0
        if prob < threshold:
            continue

        sign_lower = sign.lower()
        if sign_lower in once_set and sign_lower in history_lower:
            continue
        if BLOCK_IMMEDIATE_REPEAT and sign_lower == last_word:
            continue

        valid_candidates.append((sign, prob))

    if not valid_candidates:
        return None

    best_sign, _ = max(valid_candidates, key=lambda x: x[1])
    return best_sign


# ==========================================================
# 1. GEOMETRY CLASSIFIER (VERBATIM FROM REALTIME.PY)
# ==========================================================
def dist_3d(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)

def is_finger_extended(raw_lms, tip_idx, pip_idx):
    wrist = raw_lms[0]
    d_tip = dist_3d(raw_lms[tip_idx], wrist)
    d_pip = dist_3d(raw_lms[pip_idx], wrist)
    return d_tip > (d_pip * 1.15)

def classify_geometry(hands_lms_list):
    if not hands_lms_list:
        return None, 0.0

    primary = hands_lms_list[0]
    if len(primary) < 21:
        return None, 0.0

    wrist = primary[0]
    thumb_ext = is_finger_extended(primary, 4, 2)
    index_ext = is_finger_extended(primary, 8, 6)
    middle_ext = is_finger_extended(primary, 12, 10)
    ring_ext = is_finger_extended(primary, 16, 14)
    pinky_ext = is_finger_extended(primary, 20, 18)

    thumb_tip = primary[4]
    index_tip = primary[8]
    middle_tip = primary[12]
    ring_tip = primary[16]
    pinky_tip = primary[20]

    pinch_all = (
        dist_3d(thumb_tip, index_tip) +
        dist_3d(thumb_tip, middle_tip) +
        dist_3d(thumb_tip, ring_tip) +
        dist_3d(thumb_tip, pinky_tip)
    )

    # 1. "I"
    if pinky_ext and not index_ext and not middle_ext and not ring_ext and not thumb_ext:
        return 'I', 0.95

    # 2. "peace"
    if index_ext and middle_ext and not ring_ext and not pinky_ext and dist_3d(index_tip, middle_tip) > 0.04:
        return 'peace', 0.96

    # 3. "love"
    if thumb_ext and index_ext and pinky_ext and not middle_ext and not ring_ext:
        return 'love', 0.95

    # 4. "eat"
    if pinch_all < 0.35 and not index_ext and not middle_ext:
        return 'eat', 0.93

    # 5. "hello"
    if index_ext and middle_ext and ring_ext and pinky_ext:
        if wrist[1] > primary[9][1]:
            return 'hello', 0.97

    # 7. "hate" vs "not"
    if not index_ext and not middle_ext and not ring_ext and not pinky_ext and thumb_ext:
        if thumb_tip[1] > wrist[1]:
            return 'hate', 0.92
        else:
            return 'not', 0.90

    # 8. Gestes a deux mains
    if len(hands_lms_list) >= 2:
        w1 = hands_lms_list[0][0]
        w2 = hands_lms_list[1][0]
        h_dist = dist_3d(w1, w2)
        if h_dist < 0.28:
            return 'Shawarma', 0.91
        elif h_dist < 0.50:
            return 'tacos', 0.89

    return None, 0.0


# ==========================================================
# 2. GLOBAL MODEL & ACTIONS (LOADED ONCE AT STARTUP)
# ==========================================================
GLOBAL_ACTIONS = np.array([])
GLOBAL_ACTION_TO_IDX = {}
GLOBAL_MODEL = None
GLOBAL_FAST_PREDICT = None

def init_global_model():
    global GLOBAL_ACTIONS, GLOBAL_ACTION_TO_IDX, GLOBAL_MODEL, GLOBAL_FAST_PREDICT

    if os.path.exists(LABEL_FILE):
        try:
            raw_labels = np.load(LABEL_FILE)
            GLOBAL_ACTIONS = np.array(sorted(set(raw_labels)))
            GLOBAL_ACTION_TO_IDX = {name: i for i, name in enumerate(GLOBAL_ACTIONS)}
            print(f"[DETECTOR] Initialized {len(GLOBAL_ACTIONS)} classes: {list(GLOBAL_ACTIONS)}")
        except Exception as e:
            print(f"[DETECTOR] Labels load error: {e}")

    if TF_AVAILABLE and os.path.exists(MODEL_FILE) and len(GLOBAL_ACTIONS) > 0:
        try:
            try:
                GLOBAL_MODEL = load_model(MODEL_FILE)
                print(f"[DETECTOR] Loaded model from {MODEL_FILE}")
            except Exception as e:
                print(f"[DETECTOR] Rebuilding Keras fallback: {e}")
                rebuilt = Sequential([
                    Input(shape=(SEQUENCE_LENGTH, 126)),
                    LSTM(64, return_sequences=True),
                    LSTM(128, return_sequences=True),
                    LSTM(64, return_sequences=False),
                    Dense(64, activation='relu'),
                    Dense(32, activation='relu'),
                    Dense(len(GLOBAL_ACTIONS), activation='softmax')
                ])
                rebuilt.load_weights(MODEL_FILE)
                GLOBAL_MODEL = rebuilt

            @tf.function(reduce_retracing=True)
            def _predict(x):
                return GLOBAL_MODEL(x, training=False)

            GLOBAL_FAST_PREDICT = _predict
            # Warm up
            dummy = tf.zeros((1, SEQUENCE_LENGTH, 126), dtype=tf.float32)
            _ = GLOBAL_FAST_PREDICT(dummy)
            print("[DETECTOR] Global model compiled with tf.function and warmed up.")
        except Exception as e:
            print(f"[DETECTOR] Model load failed: {e}")

# Run once upon module import
init_global_model()


# ==========================================================
# 3. CONNECTION-SPECIFIC DETECTOR INSTANCE
# ==========================================================
class SignLanguageDetector:
    def __init__(self, hands_instance=None):
        # MediaPipe instance (one per connection)
        if hands_instance is not None:
            self.hands = hands_instance
        else:
            mp_hands = mp.solutions.hands
            self.hands = mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                model_complexity=0,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.5
            )

        self.actions = GLOBAL_ACTIONS
        self.action_to_idx = GLOBAL_ACTION_TO_IDX
        self.num_classes = len(self.actions)

        # State tracking (per connection)
        self.sequence: List[List[float]] = []
        self.current_label = ''
        self.current_confidence = 0.0
        self.last_spoken = ''
        self.last_speak_time = 0.0
        self.stable_label = ''
        self.stable_since = 0.0
        self.history_words: List[str] = []

    def process_binary_frame(self, frame_bytes: bytes) -> Dict[str, Any]:
        """
        Receives binary JPEG frame bytes (at 320x240).
        Runs decode, MediaPipe, and LSTM, measuring per-stage timings.
        """
        t0 = time.perf_counter()

        # Stage 1: Decode & Flip
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame_bgr is None:
            return {"error": "Failed to decode frame", "timings": {}}

        frame = cv2.flip(frame_bgr, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        t1 = time.perf_counter()
        t_decode = (t1 - t0) * 1000

        # Stage 2: MediaPipe Hand Tracking
        result = self.hands.process(rgb)

        frame_landmarks = [0.0] * 126
        detected_hands_count = 0
        raw_hands_3d = []
        screen_hands_normalized = []

        if result.multi_hand_landmarks:
            detected_hands_count = len(result.multi_hand_landmarks)
            coords = []

            for hand_landmarks in result.multi_hand_landmarks:
                h3d = []
                h_norm = []
                for lm in hand_landmarks.landmark:
                    coords.extend([lm.x, lm.y, lm.z])
                    h3d.append((lm.x, lm.y, lm.z))
                    h_norm.append({"x": float(lm.x), "y": float(lm.y), "z": float(lm.z)})
                raw_hands_3d.append(h3d)
                screen_hands_normalized.append(h_norm)

            coords = coords[:126]
            frame_landmarks[:len(coords)] = coords

        self.sequence.append(frame_landmarks)
        self.sequence = self.sequence[-SEQUENCE_LENGTH:]

        t2 = time.perf_counter()
        t_mediapipe = (t2 - t1) * 1000

        # Stage 3: LSTM Prediction & Constraints
        now = time.time()
        predicted_label = ''
        confidence = 0.0
        speak_word = None
        probabilities_dict = {}

        candidate_label = ''
        candidate_confidence = 0.0

        if len(self.sequence) == SEQUENCE_LENGTH and detected_hands_count > 0:
            if GLOBAL_FAST_PREDICT is not None and self.num_classes > 0:
                input_tensor = tf.constant([self.sequence], dtype=tf.float32)
                pred_tensor = GLOBAL_FAST_PREDICT(input_tensor)
                lstm_probs = pred_tensor.numpy()[0]
                latest_probs = lstm_probs.copy()
            else:
                latest_probs = np.zeros(self.num_classes, dtype=np.float32)

            # Apply geometry boost
            geom_label, geom_conf = classify_geometry(raw_hands_3d)
            if geom_label and geom_label in self.action_to_idx:
                g_idx = self.action_to_idx[geom_label]
                latest_probs[g_idx] = max(latest_probs[g_idx], geom_conf)

            # Raw best candidate regardless of threshold
            if len(latest_probs) > 0 and np.max(latest_probs) > 0.01:
                b_idx = int(np.argmax(latest_probs))
                candidate_label = self.actions[b_idx]
                candidate_confidence = float(latest_probs[b_idx])

            # Allowed best sign (0.75 threshold)
            allowed_best = get_allowed_best_sign(
                self.history_words,
                latest_probs,
                CONFIDENCE_THRESHOLD,
                self.actions
            )

            if allowed_best:
                predicted_label = allowed_best
                confidence = float(latest_probs[self.action_to_idx[allowed_best]])
            else:
                predicted_label = ''
                confidence = 0.0

            # Stability tracking
            if predicted_label:
                if predicted_label != self.stable_label:
                    self.stable_label = predicted_label
                    self.stable_since = now

                self.current_label = self.stable_label
                self.current_confidence = confidence
                held_duration = now - self.stable_since

                if held_duration >= STABLE_DURATION:
                    if self.current_label != self.last_spoken or (now - self.last_speak_time) > COOLDOWN:
                        speak_word = to_display_name(self.current_label)
                        self.last_spoken = self.current_label
                        self.last_speak_time = now

                        if len(self.history_words) == 0 or self.history_words[-1] != self.current_label:
                            self.history_words.append(self.current_label)
                            if len(self.history_words) > 8:
                                self.history_words.pop(0)
            else:
                if now - self.stable_since > 0.4:
                    self.current_label = ''
                    self.current_confidence = 0.0
                    self.stable_label = ''
                    self.stable_since = 0.0

            for idx, act in enumerate(self.actions):
                probabilities_dict[act] = float(latest_probs[idx])
        else:
            if detected_hands_count > 0:
                geom_label, geom_conf = classify_geometry(raw_hands_3d)
                if geom_label:
                    candidate_label = geom_label
                    candidate_confidence = geom_conf

            if detected_hands_count == 0:
                self.current_label = ''
                self.current_confidence = 0.0
                self.stable_label = ''
                self.stable_since = 0.0

        t3 = time.perf_counter()
        t_lstm = (t3 - t2) * 1000
        t_total = (t3 - t0) * 1000

        stable_progress = 0.0
        if self.stable_since > 0 and self.current_label:
            held = min(now - self.stable_since, STABLE_DURATION)
            stable_progress = float(held / STABLE_DURATION)

        return {
            "status_mode": "recognised" if (self.current_label and self.current_confidence >= CONFIDENCE_THRESHOLD) else "predicting",
            "detected_label": self.current_label,
            "label": self.current_label,
            "display_label": to_display_name(self.current_label),
            "confidence": round(float(self.current_confidence), 3),
            "candidate_label": candidate_label,
            "candidate_display": to_display_name(candidate_label),
            "candidate_confidence": round(float(candidate_confidence), 3),
            "stable_progress": round(stable_progress, 3),
            "history_words": self.history_words,
            "history_display": [to_display_name(w) for w in self.history_words],
            "sentence": self.build_fluent_sentence(),
            "probabilities": {to_display_name(k): round(v, 3) for k, v in probabilities_dict.items()},
            "landmarks": screen_hands_normalized,
            "hands_count": detected_hands_count,
            "sequence_buffer": len(self.sequence),
            "buffer_size": len(self.sequence),
            "sequence_target": SEQUENCE_LENGTH,
            "speak_word": speak_word,
            "timings": {
                "decode": round(t_decode, 1),
                "mediapipe": round(t_mediapipe, 1),
                "lstm": round(t_lstm, 1),
                "total": round(t_total, 1)
            }
        }

    def process_vector(self, vector_126: List[float], raw_hands_3d: List[Any] = None) -> Dict[str, Any]:
        """
        Receives numeric 126-value vector plus raw 3D landmarks from browser MediaPipe.
        Executes sliding window of 20, classify_geometry, LSTM, stability 0.35s, cooldown 1.8s,
        threshold 0.75, all verbatim from realtime.py.
        Returns predicted label, confidence, candidate for sub-threshold, probabilities, and buffer size.
        """
        t0 = time.perf_counter()

        if raw_hands_3d is None:
            raw_hands_3d = []

        # Ensure vector has length 126
        if len(vector_126) < 126:
            vector = list(vector_126) + [0.0] * (126 - len(vector_126))
        else:
            vector = list(vector_126[:126])

        has_active_signal = any(abs(v) > 1e-4 for v in vector)
        detected_hands_count = len(raw_hands_3d) if raw_hands_3d else (1 if has_active_signal else 0)

        # Sliding window of 20 frames
        self.sequence.append(vector)
        self.sequence = self.sequence[-SEQUENCE_LENGTH:]

        now = time.time()
        predicted_label = ''
        confidence = 0.0
        candidate_label = ''
        candidate_confidence = 0.0
        speak_word = None
        probabilities_dict = {}

        if len(self.sequence) == SEQUENCE_LENGTH and detected_hands_count > 0:
            if GLOBAL_FAST_PREDICT is not None and self.num_classes > 0:
                input_tensor = tf.constant([self.sequence], dtype=tf.float32)
                pred_tensor = GLOBAL_FAST_PREDICT(input_tensor)
                lstm_probs = pred_tensor.numpy()[0]
                latest_probs = lstm_probs.copy()
            else:
                latest_probs = np.zeros(self.num_classes, dtype=np.float32)

            # Apply geometry boost verbatim from realtime.py
            if raw_hands_3d:
                geom_label, geom_conf = classify_geometry(raw_hands_3d)
                if geom_label and geom_label in self.action_to_idx:
                    g_idx = self.action_to_idx[geom_label]
                    latest_probs[g_idx] = max(latest_probs[g_idx], geom_conf)

            # Top candidate regardless of threshold (for predicting state)
            if len(latest_probs) > 0 and np.max(latest_probs) > 0.01:
                b_idx = int(np.argmax(latest_probs))
                candidate_label = self.actions[b_idx]
                candidate_confidence = float(latest_probs[b_idx])

            # Constraint filter function verbatim from realtime.py
            allowed_best = get_allowed_best_sign(
                self.history_words,
                latest_probs,
                CONFIDENCE_THRESHOLD,
                self.actions
            )

            if allowed_best:
                predicted_label = allowed_best
                confidence = float(latest_probs[self.action_to_idx[allowed_best]])
            else:
                predicted_label = ''
                confidence = 0.0

            # Stability tracking (0.35s hold duration, 1.8s cooldown)
            if predicted_label:
                if predicted_label != self.stable_label:
                    self.stable_label = predicted_label
                    self.stable_since = now

                self.current_label = self.stable_label
                self.current_confidence = confidence
                held_duration = now - self.stable_since

                if held_duration >= STABLE_DURATION:
                    if self.current_label != self.last_spoken or (now - self.last_speak_time) > COOLDOWN:
                        speak_word = to_display_name(self.current_label)
                        self.last_spoken = self.current_label
                        self.last_speak_time = now

                        if len(self.history_words) == 0 or self.history_words[-1] != self.current_label:
                            self.history_words.append(self.current_label)
                            if len(self.history_words) > 8:
                                self.history_words.pop(0)
            else:
                if now - self.stable_since > 0.4:
                    self.current_label = ''
                    self.current_confidence = 0.0
                    self.stable_label = ''
                    self.stable_since = 0.0

            for idx, act in enumerate(self.actions):
                probabilities_dict[act] = float(latest_probs[idx])
        else:
            if detected_hands_count == 0:
                self.current_label = ''
                self.current_confidence = 0.0
                self.stable_label = ''
                self.stable_since = 0.0
                candidate_label = ''
                candidate_confidence = 0.0

        t1 = time.perf_counter()
        latency_ms = round((t1 - t0) * 1000, 1)

        stable_progress = 0.0
        if self.stable_since > 0 and self.current_label:
            held = min(now - self.stable_since, STABLE_DURATION)
            stable_progress = float(held / STABLE_DURATION)

        status_mode = "recognised" if (self.current_label and self.current_confidence >= CONFIDENCE_THRESHOLD) else "predicting"

        return {
            "status_mode": status_mode,
            "detected_label": self.current_label,
            "label": self.current_label,
            "display_label": to_display_name(self.current_label),
            "confidence": round(float(self.current_confidence), 3),
            "candidate_label": candidate_label,
            "candidate_display": to_display_name(candidate_label),
            "candidate_confidence": round(float(candidate_confidence), 3),
            "stable_progress": round(stable_progress, 3),
            "sequence_buffer": len(self.sequence),
            "buffer_size": len(self.sequence),
            "sequence_target": SEQUENCE_LENGTH,
            "hands_count": detected_hands_count,
            "speak_word": speak_word,
            "history_words": self.history_words,
            "history_display": [to_display_name(w) for w in self.history_words],
            "sentence": self.build_fluent_sentence(),
            "probabilities": {to_display_name(k): round(v, 3) for k, v in probabilities_dict.items()},
            "latency_ms": latency_ms
        }

    def run_parity_check(self, browser_vector: List[float], frame_jpeg: str, browser_predicted_label: str = '') -> Dict[str, Any]:
        """
        Runs Python MediaPipe on frame_jpeg with exact settings from realtime.py:
        maxNumHands=2, modelComplexity=0, minDetectionConfidence=0.6, minTrackingConfidence=0.5,
        cv2.flip(frame, 1) mirror, exact landmark order, 126-value vector.
        Logs and returns maximum absolute difference between Python vector and browser vector,
        and whether predicted labels match.
        """
        import base64
        try:
            if not frame_jpeg:
                return {
                    "type": "parity_result",
                    "max_abs_diff": 0.0,
                    "py_label": "",
                    "browser_label": browser_predicted_label,
                    "labels_match": False,
                    "py_hands_detected": 0,
                    "timestamp": time.time(),
                    "error": "Empty frame data"
                }

            if "," in frame_jpeg:
                frame_jpeg = frame_jpeg.split(",", 1)[1]

            img_bytes = base64.b64decode(frame_jpeg)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return {
                    "type": "parity_result",
                    "max_abs_diff": 0.0,
                    "py_label": "",
                    "browser_label": browser_predicted_label,
                    "labels_match": False,
                    "py_hands_detected": 0,
                    "timestamp": time.time(),
                    "error": "Failed to decode JPEG"
                }

            # Exactly verbatim from realtime.py lines 354-358:
            frame = cv2.flip(frame_bgr, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self.hands.process(rgb)

            py_vector = [0.0] * 126
            raw_h3d = []
            detected_hands_count = 0

            if result.multi_hand_landmarks:
                detected_hands_count = len(result.multi_hand_landmarks)
                coords = []
                for hand_landmarks in result.multi_hand_landmarks:
                    h3d = []
                    for lm in hand_landmarks.landmark:
                        coords.extend([lm.x, lm.y, lm.z])
                        h3d.append((lm.x, lm.y, lm.z))
                    raw_h3d.append(h3d)
                coords = coords[:126]
                py_vector[:len(coords)] = coords

            # Browser vector zero-padding or truncation to 126
            b_vec = list(browser_vector[:126]) if browser_vector else [0.0] * 126
            if len(b_vec) < 126:
                b_vec += [0.0] * (126 - len(b_vec))

            # Maximum absolute difference
            diff_arr = np.abs(np.array(b_vec, dtype=np.float32) - np.array(py_vector, dtype=np.float32))
            max_abs_diff = float(np.max(diff_arr))

            # Evaluate Python candidate label
            geom_label, geom_conf = classify_geometry(raw_h3d)
            py_label = geom_label if geom_label else ""

            if not py_label and len(self.sequence) == SEQUENCE_LENGTH and GLOBAL_FAST_PREDICT is not None and self.num_classes > 0:
                temp_seq = self.sequence[:-1] + [py_vector]
                input_tensor = tf.constant([temp_seq], dtype=tf.float32)
                pred_tensor = GLOBAL_FAST_PREDICT(input_tensor)
                probs = pred_tensor.numpy()[0]
                if len(probs) > 0 and np.max(probs) > 0.01:
                    b_idx = int(np.argmax(probs))
                    py_label = self.actions[b_idx]

            py_display = to_display_name(py_label) if py_label else ""
            br_label = (browser_predicted_label or "").strip()

            if not py_display and not br_label:
                labels_match = True
            elif py_display and br_label:
                labels_match = (py_display.lower() == br_label.lower())
            else:
                labels_match = False

            print(f"[PARITY CHECK] max_abs_diff={max_abs_diff:.5f} | py_hands={detected_hands_count} | py='{py_display}' | js='{br_label}' | match={labels_match}")

            return {
                "type": "parity_result",
                "max_abs_diff": round(max_abs_diff, 5),
                "py_label": py_display,
                "browser_label": br_label,
                "labels_match": labels_match,
                "py_hands_detected": detected_hands_count,
                "timestamp": time.time()
            }
        except Exception as e:
            print(f"[PARITY CHECK ERROR] {e}")
            return {
                "type": "parity_result",
                "max_abs_diff": 0.0,
                "py_label": "Error",
                "browser_label": browser_predicted_label,
                "labels_match": False,
                "py_hands_detected": 0,
                "timestamp": time.time(),
                "error": str(e)
            }

    def clear_history(self):
        self.history_words = []
        self.last_spoken = ''
        self.stable_label = ''
        self.stable_since = 0.0
        return {"status": "ok", "message": "History cleared"}

    def add_word(self, raw_label: str):
        if not raw_label:
            return {"status": "error", "message": "Empty word"}
        self.history_words.append(raw_label)
        if len(self.history_words) > 8:
            self.history_words.pop(0)
        return {
            "status": "ok",
            "history_words": self.history_words,
            "history_display": [to_display_name(w) for w in self.history_words],
            "sentence": self.build_fluent_sentence()
        }

    def remove_word(self, index: int):
        if 0 <= index < len(self.history_words):
            self.history_words.pop(index)
        return {
            "status": "ok",
            "history_words": self.history_words,
            "history_display": [to_display_name(w) for w in self.history_words],
            "sentence": self.build_fluent_sentence()
        }

    def build_fluent_sentence(self) -> str:
        if not self.history_words:
            return ""
        words = [to_display_name(w) for w in self.history_words]
        s = " ".join(words)
        if not s.endswith(('.', '!', '?')):
            s = s + "."
        return s
