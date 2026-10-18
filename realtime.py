import cv2
import numpy as np
import mediapipe as mp
import tensorflow as tf
from tensorflow.keras.models import load_model, Sequential
from tensorflow.keras.layers import Input, LSTM, Dense
import pyttsx3
import threading
import queue
import time
import math
import os

# ==========================================================
# 1. PARAMÈTRES D'EXÉCUTION & SEUILS OPTIMISÉS
# ==========================================================
MODEL_FILE = 'action.h5'
LABEL_FILE = 'gesture_labels.npy'
SEQUENCE_LENGTH = 20

# Seuil de confiance IA réactif
CONFIDENCE_THRESHOLD = 0.70
# Temps de maintien du geste avant prononciation (0.35 s)
STABLE_DURATION = 0.35
# Intervalle minimal entre deux prononciations du même mot
COOLDOWN = 1.8

# ==========================================================
# 2. CHARGEMENT ROBUSTE DU MODÈLE ET DES LABELS
# ==========================================================
if not os.path.exists(MODEL_FILE) or not os.path.exists(LABEL_FILE):
    print("\n[ERREUR] 'action.h5' ou 'gesture_labels.npy' manquant.")
    print("Veuillez d'abord exécuter : python train.py\n")
    exit(1)

raw_labels = np.load(LABEL_FILE)
ACTIONS = np.array(sorted(set(raw_labels)))
NUM_CLASSES = len(ACTIONS)
action_to_idx = {name: i for i, name in enumerate(ACTIONS)}

def load_gesture_model(file_path, actions):
    """Charge le modèle avec fallback d'architecture si Keras 3 bloque sur time_major."""
    try:
        m = load_model(file_path)
        print(f"[OK] Modèle LSTM chargé ({len(actions)} classes : {list(actions)})")
        return m
    except Exception as e:
        print(f"[INFO] Recompilation Keras 3 : {e}")
        rebuilt = Sequential([
            Input(shape=(SEQUENCE_LENGTH, 126)),
            LSTM(64, return_sequences=True),
            LSTM(128, return_sequences=True),
            LSTM(64, return_sequences=False),
            Dense(64, activation='relu'),
            Dense(32, activation='relu'),
            Dense(len(actions), activation='softmax')
        ])
        rebuilt.load_weights(file_path)
        print(f"[OK] Poids réinjectés avec succès ({len(actions)} classes) !")
        return rebuilt

model = load_gesture_model(MODEL_FILE, ACTIONS)

@tf.function(reduce_retracing=True)
def fast_predict(x):
    return model(x, training=False)

# Préchauffage du tenseur
dummy_input = tf.zeros((1, SEQUENCE_LENGTH, 126), dtype=tf.float32)
_ = fast_predict(dummy_input)

# ==========================================================
# 3. MOTEUR VOCAL ASYNCHRONE SANS BLOCAGE (TTS) MULTILINGUE
# ==========================================================
import sys

# Langue active : 'en' (Anglais - par défaut selon votre demande) ou 'fr' (Français).
# Vous pouvez changer à chaud en appuyant sur la touche 'L' dans la fenêtre vidéo,
# ou lancer : python realtime.py --lang en  (ou --lang fr)
CURRENT_LANG = 'en'
if '--lang' in sys.argv:
    try:
        _idx = sys.argv.index('--lang')
        if _idx + 1 < len(sys.argv):
            CURRENT_LANG = sys.argv[_idx + 1].lower()
    except Exception:
        pass

FRENCH_WORDS = {
    'hello': 'Bonjour',
    'peace': 'Paix',
    'love': 'Amour',
    'eat': 'Manger',
    'sleep': 'Dormir',
    'I': 'Moi',
    'not': 'Non',
    'hate': 'Déteste',
    'Shawarma': 'Chawarma',
    'tacos': 'Tacos'
}

ENGLISH_WORDS = {
    'hello': 'Hello',
    'peace': 'Peace',
    'love': 'Love',
    'eat': 'Eat',
    'sleep': 'Sleep',
    'I': 'I',
    'not': 'No',
    'hate': 'Thumbs down',
    'Shawarma': 'Shawarma',
    'tacos': 'Tacos'
}

def get_word_display(text, lang=None):
    lg = lang or CURRENT_LANG
    if lg == 'fr':
        return FRENCH_WORDS.get(text, text)
    return ENGLISH_WORDS.get(text, text)

speech_queue = queue.Queue()
voice_muted = False

def tts_worker():
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)

        def configure_voice_for_lang(target_lang):
            try:
                voices = engine.getProperty('voices')
                for v in voices:
                    v_name = (str(v.name) + " " + str(v.id)).lower()
                    if target_lang == 'en':
                        # Chercher une voix anglaise (David, Zira, Mark, English...)
                        if any(k in v_name for k in ['english', 'en_us', 'en_gb', 'david', 'zira', 'en-us', 'en-gb', 'hazel', 'george']):
                            engine.setProperty('voice', v.id)
                            return
                    elif target_lang == 'fr':
                        # Chercher une voix française (Hortense, Julie, Paul, French...)
                        if any(k in v_name for k in ['french', 'fr_fr', 'fr-fr', 'hortense', 'julie', 'paul', 'français']):
                            engine.setProperty('voice', v.id)
                            return
            except Exception:
                pass

        current_engine_lang = CURRENT_LANG
        configure_voice_for_lang(current_engine_lang)

        while True:
            item = speech_queue.get()
            if item is None:
                break
            if not voice_muted:
                try:
                    if isinstance(item, tuple):
                        text, lang_to_use = item
                    else:
                        text, lang_to_use = item, CURRENT_LANG

                    if lang_to_use != current_engine_lang:
                        configure_voice_for_lang(lang_to_use)
                        current_engine_lang = lang_to_use

                    spoken = get_word_display(text, lang_to_use)
                    engine.say(spoken)
                    engine.runAndWait()
                except Exception:
                    pass
            speech_queue.task_done()
    except Exception as e:
        print(f"[INFO TTS] Synthèse vocale : {e}")

tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()

def speak(text, lang=None):
    if not voice_muted:
        speech_queue.put((text, lang or CURRENT_LANG))

# ==========================================================
# 4. CLASSIFICATEUR GÉOMÉTRIQUE ANATOMIQUE (ÉCHELLE INVARIANTE)
# ==========================================================
def dist_3d(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)

def classify_geometry(hands_lms_list):
    """
    Analyse géométrique anatomique avec invariance d'échelle (palm_size).
    Détecte instantanément les 10 gestes, quelle que soit la distance de la main.
    """
    if not hands_lms_list:
        return None, 0.0

    primary = hands_lms_list[0]
    if len(primary) < 21:
        return None, 0.0

    wrist = primary[0]
    palm_size = max(0.04, dist_3d(wrist, primary[9]))

    def is_ext(tip_idx, pip_idx, mcp_idx):
        d_tip_w = dist_3d(primary[tip_idx], wrist)
        d_pip_w = dist_3d(primary[pip_idx], wrist)
        d_tip_mcp = dist_3d(primary[tip_idx], primary[mcp_idx])
        return d_tip_w > (d_pip_w * 0.95) and d_tip_mcp > (0.65 * palm_size)

    index_ext = is_ext(8, 6, 5)
    middle_ext = is_ext(12, 10, 9)
    ring_ext = is_ext(16, 14, 13)
    pinky_ext = is_ext(20, 18, 17)

    thumb_tip = primary[4]
    thumb_mcp = primary[2]
    thumb_ext = dist_3d(thumb_tip, thumb_mcp) > (0.60 * palm_size) or dist_3d(thumb_tip, primary[17]) > (0.90 * palm_size)

    index_tip = primary[8]
    middle_tip = primary[12]
    ring_tip = primary[16]
    pinky_tip = primary[20]

    pinch_all = (
        dist_3d(thumb_tip, index_tip) +
        dist_3d(thumb_tip, middle_tip) +
        dist_3d(thumb_tip, ring_tip) +
        dist_3d(thumb_tip, pinky_tip)
    ) / palm_size

    # 1. "peace" (Signe V / Victoire / Paix ✌️ : index & majeur levés, annulaire & auriculaire pliés)
    if index_ext and middle_ext and not ring_ext and not pinky_ext:
        return 'peace', 0.97

    # 2. "I" (American Sign Language 'I': seul l'auriculaire est levé)
    if pinky_ext and not index_ext and not middle_ext and not ring_ext:
        return 'I', 0.95

    # 3. "love" (Signe ILY : pouce, index et auriculaire levés)
    if thumb_ext and index_ext and pinky_ext and not middle_ext and not ring_ext:
        return 'love', 0.96

    # 4. "eat" (Doigts réunis portés vers la bouche)
    if pinch_all < 1.8 and (not index_ext or not middle_ext):
        return 'eat', 0.93

    # 5. "hello" (Main ouverte, tous les doigts tendus vers le haut)
    if index_ext and middle_ext and ring_ext and pinky_ext:
        if wrist[1] > primary[9][1] - 0.05:
            return 'hello', 0.98

    # 6. "sleep" (Main inclinée sur le côté à plat)
    if index_ext and middle_ext and ring_ext:
        dx = abs(primary[9][0] - wrist[0])
        dy = abs(primary[9][1] - wrist[1])
        if dx > (dy * 0.70):
            return 'sleep', 0.92

    # 7. "hate" vs "not"
    if not index_ext and not middle_ext and not ring_ext and not pinky_ext:
        if thumb_tip[1] > wrist[1]:
            return 'hate', 0.92
        elif thumb_ext:
            return 'not', 0.91

    # 8. Gestes à deux mains : Shawarma ou tacos
    if len(hands_lms_list) >= 2:
        w1 = hands_lms_list[0][0]
        w2 = hands_lms_list[1][0]
        h_dist = dist_3d(w1, w2)
        if h_dist < 2.0 * palm_size:
            return 'Shawarma', 0.91
        elif h_dist < 3.5 * palm_size:
            return 'tacos', 0.89

    return None, 0.0

# ==========================================================
# 5. MEDIAPIPE HANDS
# ==========================================================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    model_complexity=0,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.5
)

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17)
]

# ==========================================================
# 6. INITIALISATION CAMÉRA (WINDOWS DIRECTSHOW)
# ==========================================================
print("\n[INFO] Recherche de la caméra...")

def init_webcam():
    for backend in [cv2.CAP_DSHOW, None]:
        for idx in [0, 1, 2]:
            try:
                c = cv2.VideoCapture(idx, backend) if backend is not None else cv2.VideoCapture(idx)
                if c.isOpened():
                    c.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    c.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    for _ in range(4):
                        ret, test_frame = c.read()
                        if ret and test_frame is not None:
                            print(f"[OK] Webcam connectée sur index {idx} !")
                            return c
                        time.sleep(0.04)
                    c.release()
            except Exception:
                pass
    return None

cap = init_webcam()
if cap is None:
    print("\n[ERREUR] Impossible d'ouvrir la webcam !")
    print("Veuillez couper la webcam sur la page AI Studio (bouton 'Désactiver Caméra').")
    input("\nAppuyez sur Entrée pour quitter...")
    exit(1)

# ==========================================================
# 7. ÉTATS & INTERFACE STUDIO HD (1280x720)
# ==========================================================
sequence = []
current_label = ''
current_confidence = 0.0
last_spoken = ''
last_speak_time = 0.0
stable_label = ''
stable_since = 0.0
history_words = []
latest_probabilities = np.zeros(NUM_CLASSES, dtype=np.float32)

fps_counter = 0
current_fps = 0
last_fps_time = time.time()
latency_ms = 11

COLOR_BG = (15, 15, 18)
COLOR_PANEL = (24, 24, 28)
COLOR_CARD = (32, 32, 38)
COLOR_EMERALD = (129, 185, 16)
COLOR_CYAN = (248, 189, 56)
COLOR_TEXT_WHITE = (245, 245, 245)
COLOR_TEXT_MUTED = (160, 160, 165)
COLOR_BORDER = (45, 45, 55)

WIN_W = 1280
WIN_H = 720
CAM_W = 860
CAM_H = 490

cv2.namedWindow('Sign Language AI Studio - Pro Edition', cv2.WINDOW_NORMAL)
cv2.resizeWindow('Sign Language AI Studio - Pro Edition', WIN_W, WIN_H)

print("\n" + "=" * 60)
print("  SIGN LANGUAGE AI STUDIO - APPLICATION PRO ACTIVÉE")
print("  • TOUS LES GESTES SONT DÉTECTÉS SANS BIAIS")
print("  • Raccourcis : [Q] Quitter | [C] Effacer phrase | [M] Muet | [S] Rejouer")
print("=" * 60 + "\n")

fail_count = 0

while cap.isOpened():
    ret, raw_frame = cap.read()
    if not ret or raw_frame is None:
        fail_count += 1
        if fail_count > 30:
            print("[ERREUR] Flux caméra interrompu.")
            break
        time.sleep(0.02)
        continue
    fail_count = 0

    frame = cv2.flip(raw_frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    mp_start = time.time()
    result = hands.process(rgb)
    mp_duration = (time.time() - mp_start) * 1000

    frame_landmarks = [0.0] * 126
    detected_hands_count = 0
    raw_hands_3d = []
    screen_hands = []

    h_raw, w_raw = frame.shape[:2]

    # --- EXTRACTION ALIGNÉE EXACTEMENT SUR COLLECT.PY ---
    if result.multi_hand_landmarks:
        detected_hands_count = len(result.multi_hand_landmarks)
        coords = []

        for hand_landmarks in result.multi_hand_landmarks:
            h3d = []
            h2d = []
            for lm in hand_landmarks.landmark:
                coords.extend([lm.x, lm.y, lm.z])
                h3d.append((lm.x, lm.y, lm.z))
                h2d.append((int(lm.x * w_raw), int(lm.y * h_raw)))
            raw_hands_3d.append(h3d)
            screen_hands.append(h2d)

        coords = coords[:126]
        frame_landmarks[:len(coords)] = coords

    # Gestion de la séquence glissante
    sequence.append(frame_landmarks)
    sequence = sequence[-SEQUENCE_LENGTH:]

    now = time.time()
    predicted_label = ''
    confidence = 0.0

    # 1. Évaluation IA par le modèle LSTM (ultra-rapide)
    if len(sequence) == SEQUENCE_LENGTH and detected_hands_count > 0:
        inf_start = time.time()
        input_tensor = tf.constant([sequence], dtype=tf.float32)
        pred_tensor = fast_predict(input_tensor)
        lstm_probs = pred_tensor.numpy()[0]
        latency_ms = int((time.time() - inf_start) * 1000 + mp_duration)
        latest_probabilities = lstm_probs.copy()

        lstm_idx = int(np.argmax(lstm_probs))
        lstm_conf = float(np.max(lstm_probs))
        lstm_label = ACTIONS[lstm_idx]

        # 2. Analyse géométrique directe (booster anatomique)
        geom_label, geom_conf = classify_geometry(raw_hands_3d)

        # Combinaison intelligente : si la géométrie anatomique est claire, elle confirme ou booste le bon geste
        if geom_label and geom_label in action_to_idx:
            g_idx = action_to_idx[geom_label]
            # Boost doux de la probabilité de la classe détectée
            latest_probabilities[g_idx] = max(latest_probabilities[g_idx], geom_conf)
            predicted_label = geom_label
            confidence = max(geom_conf, float(latest_probabilities[g_idx]))
        elif lstm_conf >= CONFIDENCE_THRESHOLD:
            predicted_label = lstm_label
            confidence = lstm_conf
        else:
            predicted_label = ''
            confidence = 0.0

        # Prise en compte de la stabilité
        if predicted_label:
            if predicted_label != stable_label:
                stable_label = predicted_label
                stable_since = now

            current_label = stable_label
            current_confidence = confidence
            held_duration = now - stable_since

            # Validation vocale
            if held_duration >= STABLE_DURATION:
                if current_label != last_spoken or (now - last_speak_time) > COOLDOWN:
                    speak(current_label)
                    last_spoken = current_label
                    last_speak_time = now

                    if len(history_words) == 0 or history_words[-1] != current_label:
                        history_words.append(current_label)
                        if len(history_words) > 8:
                            history_words.pop(0)
        else:
            if now - stable_since > 0.4:
                current_label = ''
                current_confidence = 0.0
                stable_label = ''
                stable_since = 0.0
    else:
        if detected_hands_count == 0:
            current_label = ''
            current_confidence = 0.0
            stable_label = ''
            stable_since = 0.0
            latest_probabilities = np.zeros(NUM_CLASSES, dtype=np.float32)

    # Calcul des FPS
    fps_counter += 1
    if now - last_fps_time >= 1.0:
        current_fps = fps_counter
        fps_counter = 0
        last_fps_time = now

    # ======================================================
    # RENDU GRAPHIQUE STUDIO PRO (1280x720)
    # ======================================================
    studio_frame = np.full((WIN_H, WIN_W, 3), COLOR_BG, dtype=np.uint8)

    # Header
    cv2.rectangle(studio_frame, (0, 0), (WIN_W, 60), COLOR_PANEL, -1)
    cv2.line(studio_frame, (0, 60), (WIN_W, 60), COLOR_BORDER, 1)

    cv2.circle(studio_frame, (30, 30), 16, COLOR_EMERALD, -1)
    cv2.putText(studio_frame, "AI", (20, 36), cv2.FONT_HERSHEY_DUPLEX, 0.55, (0, 0, 0), 2)
    cv2.putText(studio_frame, "SIGN LANGUAGE AI STUDIO", (60, 32), cv2.FONT_HERSHEY_DUPLEX, 0.65, COLOR_TEXT_WHITE, 1)
    cv2.putText(studio_frame, "PRO EDITION - MOTEUR HYBRIDE ÉQUILIBRÉ", (60, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.36, COLOR_EMERALD, 1)

    cv2.circle(studio_frame, (WIN_W - 440, 30), 5, COLOR_EMERALD, -1)
    cv2.putText(studio_frame, "LIVE", (WIN_W - 425, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_EMERALD, 1)
    cv2.putText(studio_frame, f"FPS: {current_fps}", (WIN_W - 350, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_TEXT_WHITE, 1)
    cv2.putText(studio_frame, f"Lat: ~{latency_ms}ms", (WIN_W - 270, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR_TEXT_MUTED, 1)

    lang_txt = f"LANG: {CURRENT_LANG.upper()} [L]"
    lang_col = COLOR_CYAN if CURRENT_LANG == 'en' else COLOR_EMERALD
    cv2.putText(studio_frame, lang_txt, (WIN_W - 170, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.40, lang_col, 1)

    audio_txt = "VOIX [M]" if not voice_muted else "MUET [M]"
    audio_col = COLOR_EMERALD if not voice_muted else COLOR_TEXT_MUTED
    cv2.putText(studio_frame, audio_txt, (WIN_W - 75, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.40, audio_col, 1)

    # Cadre Caméra
    cam_x = 20
    cam_y = 75
    cam_resized = cv2.resize(frame, (CAM_W, CAM_H), interpolation=cv2.INTER_LINEAR)

    scale_x = CAM_W / w_raw
    scale_y = CAM_H / h_raw

    for h_idx, coords in enumerate(screen_hands):
        scaled = [(int(x * scale_x), int(y * scale_y)) for x, y in coords]
        line_col = COLOR_EMERALD if h_idx == 0 else COLOR_CYAN

        for p1, p2 in HAND_CONNECTIONS:
            cv2.line(cam_resized, scaled[p1], scaled[p2], line_col, 2, cv2.LINE_AA)

        for idx, pt in enumerate(scaled):
            if idx in [4, 8, 12, 16, 20]:
                cv2.circle(cam_resized, pt, 6, (0, 220, 255), -1, cv2.LINE_AA)
                cv2.circle(cam_resized, pt, 8, line_col, 1, cv2.LINE_AA)
            else:
                cv2.circle(cam_resized, pt, 4, (255, 255, 255), -1, cv2.LINE_AA)

    # Carte HUD de détection sur la vidéo
    if current_label:
        overlay = cam_resized.copy()
        cv2.rectangle(overlay, (15, 15), (340, 95), (10, 10, 12), -1)
        cv2.addWeighted(overlay, 0.88, cam_resized, 0.12, 0, cam_resized)
        cv2.rectangle(cam_resized, (15, 15), (340, 95), COLOR_EMERALD, 1)

        header_lbl = "DETECTED SIGN" if CURRENT_LANG == 'en' else "GESTE RECONNU"
        cv2.putText(cam_resized, header_lbl, (26, 35), cv2.FONT_HERSHEY_DUPLEX, 0.40, COLOR_EMERALD, 1)
        disp_name = get_word_display(current_label).upper()
        cv2.putText(cam_resized, disp_name, (26, 75), cv2.FONT_HERSHEY_DUPLEX, 1.1, (255, 255, 255), 2)
        cv2.putText(cam_resized, f"{current_confidence * 100:.0f}%", (270, 68), cv2.FONT_HERSHEY_DUPLEX, 0.85, COLOR_EMERALD, 2)

        if stable_since > 0:
            held = min(time.time() - stable_since, STABLE_DURATION)
            progress = held / STABLE_DURATION
            cv2.rectangle(cam_resized, (15, 96), (15 + int(325 * progress), 101), COLOR_EMERALD, -1)
    else:
        hint_text = "Show your hand to the camera..." if CURRENT_LANG == 'en' else "Présentez votre main devant la caméra..."
        cv2.putText(cam_resized, hint_text, (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

    studio_frame[cam_y:cam_y + CAM_H, cam_x:cam_x + CAM_W] = cam_resized
    cv2.rectangle(studio_frame, (cam_x, cam_y), (cam_x + CAM_W, cam_y + CAM_H), COLOR_BORDER, 1)

    # Constructeur de phrases
    strip_y = 580
    strip_h = 120
    cv2.rectangle(studio_frame, (cam_x, strip_y), (cam_x + CAM_W, strip_y + strip_h), COLOR_PANEL, -1)
    cv2.rectangle(studio_frame, (cam_x, strip_y), (cam_x + CAM_W, strip_y + strip_h), COLOR_BORDER, 1)

    strip_title = "SENTENCE BUILDER & LIVE TRANSCRIPTION" if CURRENT_LANG == 'en' else "CONSTRUCTEUR DE PHRASES & TRANSCRIPTION EN DIRECT"
    cv2.putText(studio_frame, strip_title, (cam_x + 16, strip_y + 25),
                cv2.FONT_HERSHEY_DUPLEX, 0.42, COLOR_TEXT_MUTED, 1)
    
    shortcuts_txt = "[C] Clear  |  [S] Speak  |  [L] Lang (EN/FR)  |  [M] Mute  |  [Q] Quit"
    cv2.putText(studio_frame, shortcuts_txt, (cam_x + CAM_W - 470, strip_y + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, COLOR_TEXT_MUTED, 1)

    if len(history_words) == 0:
        empty_hint = "Recognized words will form a sentence here..." if CURRENT_LANG == 'en' else "Les mots reconnus formeront une phrase ici..."
        cv2.putText(studio_frame, empty_hint,
                    (cam_x + 20, strip_y + 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 100), 1)
    else:
        word_x = cam_x + 20
        for w in history_words:
            w_disp = get_word_display(w).capitalize()
            (tw, th), _ = cv2.getTextSize(w_disp, cv2.FONT_HERSHEY_DUPLEX, 0.65, 1)
            cv2.rectangle(studio_frame, (word_x, strip_y + 48), (word_x + tw + 22, strip_y + 88), COLOR_CARD, -1)
            cv2.rectangle(studio_frame, (word_x, strip_y + 48), (word_x + tw + 22, strip_y + 88), COLOR_EMERALD, 1)
            cv2.putText(studio_frame, w_disp, (word_x + 11, strip_y + 74), cv2.FONT_HERSHEY_DUPLEX, 0.65, COLOR_TEXT_WHITE, 1)
            word_x += tw + 32
            if word_x > cam_x + CAM_W - 120:
                break

    # Panneau latéral des probabilités (10 signes)
    side_x = cam_x + CAM_W + 20
    side_w = WIN_W - side_x - 20
    side_h = CAM_H + strip_h + 15

    cv2.rectangle(studio_frame, (side_x, cam_y), (side_x + side_w, cam_y + side_h), COLOR_PANEL, -1)
    cv2.rectangle(studio_frame, (side_x, cam_y), (side_x + side_w, cam_y + side_h), COLOR_BORDER, 1)

    side_title = "LIVE PROBABILITIES" if CURRENT_LANG == 'en' else "PROBABILITES EN DIRECT"
    cv2.putText(studio_frame, side_title, (side_x + 16, cam_y + 30), cv2.FONT_HERSHEY_DUPLEX, 0.45, COLOR_TEXT_WHITE, 1)
    side_sub = "10 ACTIVE GESTURES (NO BIAS)" if CURRENT_LANG == 'en' else "10 GESTES RECONNUS (SANS BIAIS)"
    cv2.putText(studio_frame, side_sub, (side_x + 16, cam_y + 48), cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_EMERALD, 1)
    cv2.line(studio_frame, (side_x + 16, cam_y + 58), (side_x + side_w - 16, cam_y + 58), COLOR_BORDER, 1)

    bar_y_start = cam_y + 80
    max_bar_w = side_w - 140

    for idx, action_name in enumerate(ACTIONS):
        cur_y = bar_y_start + (idx * 42)
        prob = float(latest_probabilities[idx]) if idx < len(latest_probabilities) else 0.0
        is_top = (action_name == current_label) and (prob >= 0.50)

        name_col = COLOR_EMERALD if is_top else COLOR_TEXT_WHITE
        disp_txt = get_word_display(action_name).capitalize()
        cv2.putText(studio_frame, disp_txt, (side_x + 16, cur_y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, name_col, 1 if not is_top else 2)

        bar_x = side_x + 95
        cv2.rectangle(studio_frame, (bar_x, cur_y), (bar_x + max_bar_w, cur_y + 14), COLOR_CARD, -1)

        fill_w = int(max_bar_w * min(1.0, prob))
        fill_col = COLOR_EMERALD if is_top else (COLOR_CYAN if prob > 0.4 else (80, 80, 95))
        if fill_w > 0:
            cv2.rectangle(studio_frame, (bar_x, cur_y), (bar_x + fill_w, cur_y + 14), fill_col, -1)

        cv2.putText(studio_frame, f"{prob * 100:.0f}%", (bar_x + max_bar_w + 8, cur_y + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, name_col, 1)

    info_y = cam_y + side_h - 75
    cv2.rectangle(studio_frame, (side_x + 14, info_y), (side_x + side_w - 14, info_y + 60), COLOR_CARD, -1)
    tip_title = "PRO TIP :" if CURRENT_LANG == 'en' else "CONSEIL D'UTILISATION :"
    cv2.putText(studio_frame, tip_title, (side_x + 22, info_y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_EMERALD, 1)
    tip_l1 = "Press [L] to switch EN / FR." if CURRENT_LANG == 'en' else "Appuyez sur [L] pour alterner EN / FR."
    cv2.putText(studio_frame, tip_l1, (side_x + 22, info_y + 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_TEXT_MUTED, 1)
    tip_l2 = "All 10 gestures active." if CURRENT_LANG == 'en' else "Tous les 10 gestes sont actifs."
    cv2.putText(studio_frame, tip_l2, (side_x + 22, info_y + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_TEXT_MUTED, 1)

    cv2.imshow('Sign Language AI Studio - Pro Edition', studio_frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == 27:
        break
    elif key == ord('c') or key == ord('C'):
        history_words = []
    elif key == ord('s') or key == ord('S'):
        if history_words:
            speak(" ".join(history_words))
    elif key == ord('m') or key == ord('M'):
        voice_muted = not voice_muted
    elif key == ord('l') or key == ord('L'):
        CURRENT_LANG = 'fr' if CURRENT_LANG == 'en' else 'en'
        print(f"[LANG] Langue basculée vers : {CURRENT_LANG.upper()}")
        speak("English language selected" if CURRENT_LANG == 'en' else "Langue française sélectionnée", CURRENT_LANG)

cap.release()
cv2.destroyAllWindows()
speech_queue.put(None)
print("\n[INFO] Application arrêtée proprement.\n")
