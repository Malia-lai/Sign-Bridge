"""
backend.py - High-performance FastAPI + WebSocket backend for Sign Language AI Studio.
Key features:
  - Binary WebSocket frame processing (320x240 @ 20+ FPS)
  - Worker thread execution via asyncio.to_thread (non-blocking async server)
  - One persistent MediaPipe Hands instance per connection
  - Per-stage timings (decode, MediaPipe, LSTM, total)
  - Pre-cached 3D simulation sequences with active frame extraction
"""
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import mediapipe as mp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from detector import (
    SignLanguageDetector,
    to_display_name,
    CONFIDENCE_THRESHOLD,
    STABLE_DURATION,
    COOLDOWN,
    GLOBAL_ACTIONS
)

# ==========================================================
# 1. PATH RESOLUTION & DATABASE PRE-LOADING
# ==========================================================
BASE_DIR = Path(__file__).parent.resolve()
MODEL_PATH = BASE_DIR / 'action.h5'
LABEL_PATH = BASE_DIR / 'gesture_labels.npy'
DATA_PATH = BASE_DIR / 'gesture_landmarks.npy'
DIST_DIR = BASE_DIR / 'dist'

files_status = {
    "action.h5": MODEL_PATH.is_file(),
    "gesture_labels.npy": LABEL_PATH.is_file(),
    "gesture_landmarks.npy": DATA_PATH.is_file(),
}
missing_files = [k for k, v in files_status.items() if not v]

labels_loaded = False
landmarks_loaded = False
labels_shape = None
landmarks_shape = None
shapes_match = False
has_nan = False
min_val = 0.0
max_val = 0.0
non_zero_pct = 0.0

raw_labels_list: List[str] = []
unique_labels_list: List[str] = []
sequences_cache: Dict[str, Any] = {}

if LABEL_PATH.is_file() and DATA_PATH.is_file():
    try:
        raw_labels = np.load(str(LABEL_PATH))
        landmarks_data = np.load(str(DATA_PATH))

        labels_shape = list(raw_labels.shape)
        landmarks_shape = list(landmarks_data.shape)
        labels_loaded = True
        landmarks_loaded = True

        if len(labels_shape) >= 1 and len(landmarks_shape) >= 1 and labels_shape[0] == landmarks_shape[0]:
            shapes_match = True

        has_nan = bool(np.isnan(landmarks_data).any())
        min_val = float(np.min(landmarks_data))
        max_val = float(np.max(landmarks_data))
        non_zero_pct = float(np.mean(landmarks_data != 0) * 100)

        raw_labels_list = [str(lbl) for lbl in raw_labels]
        unique_labels_list = sorted(list(set(raw_labels_list)))

        print(f"[BACKEND] Loaded {len(raw_labels_list)} samples, {len(unique_labels_list)} unique words.")
        print(f"[BACKEND] Stats: shape={landmarks_shape}, range=[{min_val:.4f}, {max_val:.4f}], has_nan={has_nan}, active={non_zero_pct:.1f}%")

        # Pick best active sample per word (skip all-zero frames)
        for word in unique_labels_list:
            matches = [i for i, lbl in enumerate(raw_labels_list) if lbl == word]
            best_idx = matches[0]
            best_active = -1

            for m in matches:
                sample = landmarks_data[m] # (20, 126)
                active_cnt = sum(1 for fi in range(20) if np.any(sample[fi] != 0))
                if active_cnt > best_active:
                    best_active = active_cnt
                    best_idx = m

            best_seq = landmarks_data[best_idx]
            frames_list = []

            for fi in range(20):
                frame_raw = best_seq[fi]
                if not np.any(frame_raw != 0):
                    continue

                left_hand = []
                right_hand = []

                if np.any(frame_raw[0:63] != 0):
                    for p in range(21):
                        idx = p * 3
                        left_hand.append({
                            "x": float(frame_raw[idx]),
                            "y": float(frame_raw[idx + 1]),
                            "z": float(frame_raw[idx + 2])
                        })

                if np.any(frame_raw[63:126] != 0):
                    for p in range(21):
                        idx = 63 + (p * 3)
                        right_hand.append({
                            "x": float(frame_raw[idx]),
                            "y": float(frame_raw[idx + 1]),
                            "z": float(frame_raw[idx + 2])
                        })

                frames_list.append({
                    "frame_index": fi,
                    "left_hand": left_hand,
                    "right_hand": right_hand
                })

            sequences_cache[word] = {
                "raw_label": word,
                "display_name": to_display_name(word),
                "sample_index": best_idx,
                "active_frames_count": len(frames_list),
                "has_usable_data": len(frames_list) > 0,
                "count": len(matches),
                "frames": frames_list
            }

    except Exception as e:
        print(f"[BACKEND ERROR] Failed to load data: {e}")

# ==========================================================
# 2. FASTAPI APP
# ==========================================================
app = FastAPI(title="Sign Language AI Studio Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

shared_detector = SignLanguageDetector()

class AddWordRequest(BaseModel):
    word: str

@app.get("/health")
def health_check():
    return {
        "status": "ok" if not missing_files else "degraded",
        "backend_dir": str(BASE_DIR),
        "files": files_status,
        "missing_files": missing_files,
        "shapes_match": shapes_match,
        "labels_shape": labels_shape,
        "landmarks_shape": landmarks_shape,
        "has_nan": has_nan,
        "min_val": round(min_val, 4),
        "max_val": round(max_val, 4),
        "non_zero_pct": round(non_zero_pct, 1),
        "total_unique_words": len(unique_labels_list)
    }

@app.get("/api/words")
def get_words():
    if not labels_loaded:
        return []
    return [
        {
            "raw_label": w,
            "display_name": to_display_name(w),
            "count": raw_labels_list.count(w)
        }
        for w in unique_labels_list
    ]

@app.get("/api/sequences")
def get_all_sequences():
    return sequences_cache

@app.get("/api/sequences/{raw_label}")
def get_single_sequence(raw_label: str):
    if raw_label not in sequences_cache:
        raise HTTPException(status_code=404, detail=f"No sequence for '{raw_label}'")
    return sequences_cache[raw_label]

@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "model_loaded": shared_detector.num_classes > 0,
        "classes_count": shared_detector.num_classes,
        "classes": list(shared_detector.actions),
        "classes_display": [to_display_name(c) for c in shared_detector.actions],
        "threshold": CONFIDENCE_THRESHOLD,
        "stable_duration": STABLE_DURATION,
        "cooldown": COOLDOWN,
        "shapes_match": shapes_match,
        "labels_shape": labels_shape,
        "landmarks_shape": landmarks_shape,
        "has_nan": has_nan,
        "min_val": round(min_val, 4),
        "max_val": round(max_val, 4),
        "non_zero_pct": round(non_zero_pct, 1),
        "missing_files": missing_files
    }

@app.post("/api/history/clear")
def clear_history():
    return shared_detector.clear_history()

@app.post("/api/history/add")
def add_word(req: AddWordRequest):
    return shared_detector.add_word(req.word)

@app.post("/api/history/remove/{index}")
def remove_word(index: int):
    return shared_detector.remove_word(index)

# ==========================================================
# 3. REAL-TIME BINARY WEBSOCKET (20+ FPS via asyncio.to_thread)
# ==========================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Create one persistent MediaPipe instance per connection
    mp_hands = mp.solutions.hands
    hands_instance = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        model_complexity=0,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.5
    )
    conn_detector = SignLanguageDetector(hands_instance=hands_instance)

    try:
        while True:
            message = await websocket.receive()

            # Fast binary frame path
            if "bytes" in message and message["bytes"]:
                frame_bytes = message["bytes"]
                # Process in worker thread: never blocks the async server loop
                result = await asyncio.to_thread(conn_detector.process_binary_frame, frame_bytes)
                await websocket.send_json(result)

            elif "text" in message and message["text"]:
                txt = message["text"]
                try:
                    payload = json.loads(txt)
                    msg_type = payload.get("type")
                    if msg_type == "landmarks" or "vector" in payload:
                        vector = payload.get("vector", [0.0] * 126)
                        raw_hands_3d = payload.get("raw_hands_3d", [])
                        res = await asyncio.to_thread(conn_detector.process_vector, vector, raw_hands_3d)
                        await websocket.send_json(res)
                    elif msg_type == "parity_check":
                        vector = payload.get("vector", [0.0] * 126)
                        frame_jpeg = payload.get("frame_jpeg", "")
                        browser_label = payload.get("browser_label", "")
                        parity_res = await asyncio.to_thread(
                            conn_detector.run_parity_check, vector, frame_jpeg, browser_label
                        )
                        await websocket.send_json(parity_res)
                    elif msg_type == "clear_history":
                        res = conn_detector.clear_history()
                        await websocket.send_json(res)
                    elif msg_type == "add_word":
                        res = conn_detector.add_word(payload.get("word", ""))
                        await websocket.send_json(res)
                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
                except Exception as e:
                    print(f"[WS MSG ERROR] {e}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS ERROR] {e}")
    finally:
        try:
            hands_instance.close()
        except Exception:
            pass

# Serve production frontend if built
if DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(DIST_DIR / "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=False)
