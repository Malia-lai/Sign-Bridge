"""
import_asl.py - build a small ASL test dataset for Sign-Bridge from the Kaggle
"Google - Isolated Sign Language Recognition" (asl-signs) competition.

What it does
  1. reads train.csv (small file you already downloaded)
  2. picks N sequences for each of ~25 signs (spread over different signers)
  3. downloads ONLY those parquet files, one by one, with the Kaggle command line
  4. keeps the two hands, resamples to 20 frames, normalizes (sign_features.py)
  5. saves SEPARATE test files (your original .npy files are never touched):
        asl_test/asl_test_landmarks.npy   float32, shape (N, 20, 126)
        asl_test/asl_test_labels.npy      array of strings, shape (N,)
        asl_test/asl_test_signers.npy     signer id of every sample (lets train_asl_test.py test on unseen signers)
        asl_test/asl_test_meta.json       signs, counts, settings
        asl_test/preview.png              black-canvas view of one sample per sign

Setup (once)
  python -m pip install pandas pyarrow numpy opencv-python kaggle
  - join the competition and accept its rules:  https://www.kaggle.com/competitions/asl-signs
  - log in to Kaggle once:   python -m kaggle auth login     (opens the browser)
    (or save a token from kaggle.com/settings/api in ~/.kaggle/access_token)

Usage
  python import_asl.py --dry-run                 # shows what would be downloaded, downloads nothing
  python import_asl.py --per-sign 1              # smoke test: ~25 files
  python import_asl.py --per-sign 100            # the real run (~2500 files, about 25 min; earlier downloads are reused)
  python import_asl.py --offline --data-dir kaggle_files   # convert files you already have
"""
import argparse
import json
import random
import shutil
import subprocess
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from sign_features import (FRAME_SIZE, N_LANDMARKS, SEQUENCE_LENGTH, normalize_sequence,
                           resample_sequence)

COMPETITION = "asl-signs"

# 25 signs: mix of mostly-handshape signs and mostly-motion signs. All exist in train.csv.
# Edit freely - the script checks every name against train.csv.
DEFAULT_SIGNS = [
    "hello", "bye", "thankyou", "please", "yes", "no", "hate", "not", "sleep",
    "mom", "dad", "drink", "water", "food", "hungry", "happy", "sad", "cry",
    "up", "down", "wait", "finish", "look", "bad", "like",
]

HAND_NAMES = ("left_hand", "right_hand")   # slot 0 = left_hand, slot 1 = right_hand
MAX_GAP = 5                                # fill gaps of up to 5 missing frames inside a hand track

CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10),
               (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18),
               (18, 19), (19, 20), (0, 17)]


# ---------------------------------------------------------------- selection
def select_sequences(df, signs, per_sign, seed):
    """Up to per_sign sequences per sign, taken round-robin across signers (participants)."""
    rng = random.Random(seed)
    chosen = []
    for sign in signs:
        sub = df[df["sign"] == sign]
        by_person = {}
        for row in sub.itertuples(index=False):
            by_person.setdefault(row.participant_id, []).append(row)
        people = sorted(by_person)
        rng.shuffle(people)
        for p in people:
            rng.shuffle(by_person[p])
        picked = []
        while len(picked) < per_sign and any(by_person[p] for p in people):
            for p in people:
                if by_person[p] and len(picked) < per_sign:
                    picked.append(by_person[p].pop())
        chosen.extend(picked)
    return chosen


# ---------------------------------------------------------------- download
def find_local(data_dir, path):
    """Locate a downloaded parquet file (the CLI may flatten the folder structure)."""
    name = Path(path).name
    for cand in (data_dir / path, data_dir / name):
        if cand.is_file():
            return cand
    hits = list(data_dir.rglob(name))
    return hits[0] if hits else None


_preferred_form = 0   # remembers which CLI syntax worked (0 = new style, 1 = old "-c" style)


def find_kaggle_command():
    """
    The command (a list) that runs the Kaggle CLI, or None.
    'python -m kaggle' uses the SAME Python that runs this script, so it works even when the
    folder where pip puts kaggle.exe is not on PATH (the usual problem on Windows).
    """
    import importlib.util
    if importlib.util.find_spec("kaggle") is not None:
        return [sys.executable, "-m", "kaggle"]
    exe = shutil.which("kaggle")
    return [exe] if exe else None


def kaggle_command_forms(path, data_dir):
    d = str(data_dir)
    return [
        ["competitions", "download", COMPETITION, "-f", path, "-p", d],         # kaggle 2.x
        ["competitions", "download", "-c", COMPETITION, "-f", path, "-p", d],   # older kaggle 1.x
    ]


AUTH_HELP = (
    "Kaggle login problem. Fix it once with ONE of these (then run the script again):\n"
    "  1) In a terminal:  {py} -m kaggle auth login      (opens the browser, recommended)\n"
    "  2) or on https://www.kaggle.com/settings/api click 'Generate New Token', save the token text in\n"
    "     the file  <your user folder>/.kaggle/access_token   (Windows: C:\\Users\\<you>\\.kaggle\\access_token)\n"
    "Also make sure you clicked 'Join Competition' / accepted the rules on "
    "https://www.kaggle.com/competitions/asl-signs"
)


def download_one(kaggle_cmd, path, data_dir):
    global _preferred_form
    forms = kaggle_command_forms(path, data_dir)
    order = [_preferred_form] + [i for i in range(len(forms)) if i != _preferred_form]
    last_err = ""
    for idx in order:
        proc = subprocess.run(kaggle_cmd + forms[idx], capture_output=True, text=True)
        found = find_local(data_dir, path)
        if found is None:  # maybe it arrived zipped
            for z in list(data_dir.rglob(Path(path).name + "*.zip")) + list(data_dir.glob("*.zip")):
                try:
                    with zipfile.ZipFile(z) as zf:
                        zf.extractall(data_dir)
                    z.unlink()
                except zipfile.BadZipFile:
                    pass
            found = find_local(data_dir, path)
        if found is not None:
            _preferred_form = idx
            return found
        last_err = (proc.stderr or proc.stdout or "").strip()
        if "unrecognized arguments" in last_err or "usage:" in last_err.lower()[:200]:
            continue          # wrong CLI syntax: try the other form
        break                 # real error (login, rules, network): the other syntax will not help
    raise RuntimeError(last_err[-500:] or "file not found after download")


def download_with_retry(kaggle_cmd, path, data_dir, attempts=3):
    """Retry a few times (network hiccups, Kaggle rate limits). Login/rules problems are not retried."""
    err = None
    for k in range(attempts):
        try:
            return download_one(kaggle_cmd, path, data_dir)
        except RuntimeError as e:
            err = e
            low = str(e).lower()
            if any(w in low for w in ("authentication", "unauthorized", "forbidden", "401", "403")):
                raise
            time.sleep(2.0 * (k + 1))
    raise err


def short_reason(msg):
    lines = [ln.strip() for ln in str(msg).splitlines() if ln.strip()]
    return (lines[-1] if lines else "unknown error")[:110]


# ---------------------------------------------------------------- conversion
def fill_short_gaps(raw, max_gap=MAX_GAP):
    """raw: (T, 2, 21, 3) with NaN for missing. Linearly fills short gaps BETWEEN two detections."""
    t_len = raw.shape[0]
    for h in range(2):
        present = ~np.isnan(raw[:, h]).all(axis=(1, 2))
        t = 0
        while t < t_len:
            if present[t]:
                t += 1
                continue
            start = t
            while t < t_len and not present[t]:
                t += 1
            end = t  # first present frame after the gap (or t_len)
            if start > 0 and end < t_len and (end - start) <= max_gap:
                a, b = raw[start - 1, h], raw[end, h]
                for k in range(start, end):
                    w = (k - start + 1) / (end - start + 1)
                    raw[k, h] = (1 - w) * a + w * b
    return raw


def parquet_to_sequence(path, aspect):
    """One Kaggle parquet file -> normalized (20, 126) float32 array, or None if no hand was ever seen."""
    df = pd.read_parquet(path, columns=["frame", "type", "landmark_index", "x", "y", "z"])
    frames = np.sort(df["frame"].unique())
    raw = np.full((len(frames), 2, N_LANDMARKS, 3), np.nan, dtype=np.float32)
    for h, name in enumerate(HAND_NAMES):
        sub = df[df["type"] == name]
        if sub.empty:
            continue
        fi = np.searchsorted(frames, sub["frame"].to_numpy())
        li = sub["landmark_index"].to_numpy().astype(int)
        raw[fi, h, li, 0] = sub["x"].to_numpy()
        raw[fi, h, li, 1] = sub["y"].to_numpy()
        raw[fi, h, li, 2] = sub["z"].to_numpy()

    present_any = ~np.isnan(raw).all(axis=(2, 3))          # (T, 2)
    if not present_any.any():
        return None
    active = np.where(present_any.any(axis=1))[0]
    raw = raw[active[0]:active[-1] + 1]                    # crop to the part where hands are visible
    raw = fill_short_gaps(raw)
    raw = np.nan_to_num(raw, nan=0.0)                      # remaining missing = 0

    seq = raw.reshape(raw.shape[0], FRAME_SIZE)
    seq = resample_sequence(seq, SEQUENCE_LENGTH)
    return normalize_sequence(seq, aspect=aspect)


# ---------------------------------------------------------------- preview
def draw_preview(X, y, out_path, max_signs=8):
    import cv2
    labels = list(dict.fromkeys(y.tolist()))[:max_signs]
    cols = [0, 4, 9, 14, 19]
    cell = 200
    sheet = np.zeros((len(labels) * cell, len(cols) * cell, 3), dtype=np.uint8)
    unit = 30.0  # pixels per "palm size"
    colors = [(80, 255, 80), (255, 200, 60)]  # left = green, right = blue-ish (BGR)
    for r, lab in enumerate(labels):
        seq = X[int(np.where(y == lab)[0][0])].reshape(SEQUENCE_LENGTH, 2, N_LANDMARKS, 3)
        for c, t in enumerate(cols):
            ox, oy = c * cell, r * cell
            cv2.rectangle(sheet, (ox, oy), (ox + cell - 1, oy + cell - 1), (40, 40, 40), 1)
            for h in range(2):
                pts = seq[t, h]
                if not np.any(pts != 0):
                    continue
                xy = [(int(ox + cell * 0.5 + p[0] * unit), int(oy + cell * 0.3 + p[1] * unit)) for p in pts]
                for a, b in CONNECTIONS:
                    cv2.line(sheet, xy[a], xy[b], colors[h], 1, cv2.LINE_AA)
                for q in xy:
                    cv2.circle(sheet, q, 2, (255, 255, 255), -1)
        cv2.putText(sheet, lab, (6, r * cell + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
    cv2.imwrite(str(out_path), sheet)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default="train.csv")
    ap.add_argument("--signs", default=",".join(DEFAULT_SIGNS), help="comma-separated sign names")
    ap.add_argument("--per-sign", type=int, default=100)
    ap.add_argument("--data-dir", default="kaggle_files", help="where downloaded parquet files are stored")
    ap.add_argument("--out-dir", default="asl_test")
    ap.add_argument("--aspect", type=float, default=0.75,
                    help="image width/height of the Kaggle data (x is multiplied by it). "
                         "If hands look squashed in preview.png, try 1.0 or 1.333.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true", help="only show the plan, download nothing")
    ap.add_argument("--offline", action="store_true", help="do not download; use files already in --data-dir")
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    signs = [s.strip() for s in args.signs.split(",") if s.strip()]
    missing = [s for s in signs if s not in set(df["sign"])]
    if missing:
        sys.exit("These signs are not in train.csv: " + ", ".join(missing))

    chosen = select_sequences(df, signs, args.per_sign, args.seed)
    print(f"{len(signs)} signs, {len(chosen)} sequences selected "
          f"({len({r.participant_id for r in chosen})} different signers).")

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    if args.dry_run:
        for s in signs:
            print(f"  {s:10s} {sum(1 for r in chosen if r.sign == s)}")
        print("Dry run: nothing downloaded or written.")
        return
    data_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    kaggle_cmd = None
    if not args.offline:
        kaggle_cmd = find_kaggle_command()
        if kaggle_cmd is None:
            sys.exit("Kaggle is not installed for this Python. Run exactly this, then run the script again:\n"
                     f"    {sys.executable} -m pip install kaggle")
        print("Using Kaggle command:", " ".join(kaggle_cmd))

    X, y, signers, failed, skipped = [], [], [], [], 0
    for i, row in enumerate(chosen, 1):
        local = find_local(data_dir, row.path)
        if local is None:
            if args.offline:
                failed.append((row.path, "missing in --data-dir"))
                continue
            try:
                local = download_with_retry(kaggle_cmd, row.path, data_dir)
            except Exception as e:  # keep going, report at the end
                failed.append((row.path, str(e)))
                if len(failed) >= 5 and not X:
                    sys.exit("First downloads all failed - stopping.\n\nKaggle said:\n" + str(e) +
                             "\n\n" + AUTH_HELP.format(py=sys.executable))
                continue
        try:
            seq = parquet_to_sequence(local, args.aspect)
        except Exception as e:
            failed.append((row.path, f"unreadable: {e}"))
            continue
        if seq is None:
            skipped += 1
            continue
        X.append(seq)
        y.append(row.sign)
        signers.append(int(row.participant_id))
        if i % 25 == 0 or i == len(chosen):
            print(f"  {i}/{len(chosen)} processed")

    if not X:
        sys.exit("No sequences were converted.")

    X = np.stack(X).astype(np.float32)
    y = np.array(y)
    assert X.shape[1:] == (SEQUENCE_LENGTH, FRAME_SIZE) and not np.isnan(X).any()

    np.save(out_dir / "asl_test_landmarks.npy", X)
    np.save(out_dir / "asl_test_labels.npy", y)
    np.save(out_dir / "asl_test_signers.npy", np.array(signers, dtype=np.int64))
    counts = {s: int((y == s).sum()) for s in signs}
    left = float(np.mean([np.any(x[:, :63] != 0) for x in X]))
    right = float(np.mean([np.any(x[:, 63:] != 0) for x in X]))
    meta = {"shape": list(X.shape), "counts": counts, "aspect": args.aspect, "seed": args.seed,
            "layout": "[left_hand 63 | right_hand 63], normalized with sign_features.normalize_sequence",
            "signers": len(set(signers)), "failed": len(failed), "no_hands_skipped": skipped}
    (out_dir / "asl_test_meta.json").write_text(json.dumps(meta, indent=2))
    if not args.no_preview:
        draw_preview(X, y, out_dir / "preview.png")

    print(f"\nSaved {X.shape} float32 -> {out_dir / 'asl_test_landmarks.npy'}")
    print(f"Sequences using left hand: {left:.0%}, right hand: {right:.0%}")
    print(f"Skipped (no hand found): {skipped}, failed: {len(failed)}")
    if failed:
        print("Why files failed (count - reason):")
        for reason, n in Counter(short_reason(e) for _, e in failed).most_common(5):
            print(f"  {n:4d} - {reason}")
        print("Run the same command again: files already downloaded are reused and only the failed ones are retried.")
    print("Counts:", counts)


if __name__ == "__main__":
    main()