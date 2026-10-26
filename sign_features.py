"""
sign_features.py - shared feature code for Sign-Bridge.

Use the SAME functions in import_asl.py, collect.py and realtime.py, so the model
always sees numbers built the same way.

Data layout of one frame (126 values):
    [ LEFT hand: 21 landmarks x (x, y, z) = 63 | RIGHT hand: 21 landmarks x (x, y, z) = 63 ]
A hand that is not visible is all zeros.

A sequence is an array of shape (20, 126), dtype float32.
"""
import numpy as np

SEQUENCE_LENGTH = 20
N_LANDMARKS = 21
HAND_SIZE = N_LANDMARKS * 3      # 63
FRAME_SIZE = HAND_SIZE * 2       # 126

WRIST = 0
MIDDLE_MCP = 9                   # base of the middle finger: wrist->this = "palm size"


def hand_present(seq, hand):
    """Boolean array (T,): is `hand` (0 = left slot, 1 = right slot) visible in each frame?"""
    block = seq[:, hand * HAND_SIZE:(hand + 1) * HAND_SIZE]
    return np.any(block != 0.0, axis=1)


def normalize_sequence(seq, aspect=1.0):
    """
    Make a sequence independent of WHERE the hands are on screen and how FAR they are,
    while keeping the hand shape and the movement.

    seq    : (T, 126) raw landmarks (MediaPipe x, y, z; zeros for a missing hand)
    aspect : image width / height. x is multiplied by it so x and y use the same unit.
             Webcam 640x480 -> 1.333.  Kaggle ASL Signs -> see import_asl.py (--aspect).

    - origin = wrist position at the FIRST frame where a hand is visible
               (so movement over time is kept, only the starting position is removed)
    - scale  = median wrist->middle-finger-base distance (palm size)
    Missing hands stay zeros.
    """
    seq = np.array(seq, dtype=np.float32, copy=True)
    t_len = seq.shape[0]
    pts = seq.reshape(t_len, 2, N_LANDMARKS, 3)
    pts[..., 0] *= aspect

    present = np.stack([hand_present(seq, 0), hand_present(seq, 1)], axis=1)  # (T, 2)
    if not present.any():
        return seq.reshape(t_len, FRAME_SIZE).astype(np.float32)

    first = int(np.argmax(present.any(axis=1)))
    wrists = [pts[first, h, WRIST] for h in (0, 1) if present[first, h]]
    origin = np.mean(wrists, axis=0)

    sizes = []
    for h in (0, 1):
        for t in np.where(present[:, h])[0]:
            d = pts[t, h, MIDDLE_MCP, :2] - pts[t, h, WRIST, :2]
            sizes.append(float(np.hypot(d[0], d[1])))
    scale = float(np.median(sizes)) if sizes else 1.0
    if scale < 1e-4:
        scale = 1.0

    for h in (0, 1):
        for t in np.where(present[:, h])[0]:
            pts[t, h] = (pts[t, h] - origin) / scale
    return pts.reshape(t_len, FRAME_SIZE).astype(np.float32)


def resample_sequence(seq, length=SEQUENCE_LENGTH):
    """
    Pick `length` evenly spaced REAL frames from (T, 126) -> (length, 126).
    Nearest-frame sampling (no blending), so a missing hand stays exactly zero
    and no invented values appear when a hand enters or leaves the picture.
    """
    seq = np.asarray(seq, dtype=np.float32)
    t_len = seq.shape[0]
    idx = np.round(np.linspace(0, t_len - 1, length)).astype(int)
    return seq[idx].copy()


def hands_to_frame(left_xyz=None, right_xyz=None):
    """
    Build one 126-value frame from two optional (21, 3) arrays.
    Always LEFT first, RIGHT second. Use this in collect.py / realtime.py.
    """
    frame = np.zeros(FRAME_SIZE, dtype=np.float32)
    if left_xyz is not None:
        frame[:HAND_SIZE] = np.asarray(left_xyz, dtype=np.float32).reshape(-1)
    if right_xyz is not None:
        frame[HAND_SIZE:] = np.asarray(right_xyz, dtype=np.float32).reshape(-1)
    return frame
