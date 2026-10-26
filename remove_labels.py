"""
remove_labels.py - delete all samples of some labels from your .npy dataset (with a backup).

Usage:
    python remove_labels.py Shawarma tacos
    python remove_labels.py Shawarma tacos --data gesture_landmarks.npy --labels gesture_labels.npy

Label matching ignores upper/lower case. The two files are backed up first into
backup_<date-time>/ and are only rewritten if both stay the same length.
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np


def load(path):
    try:
        return np.load(path)
    except ValueError:  # old files saved with pickled objects
        return np.load(path, allow_pickle=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("labels_to_remove", nargs="+")
    ap.add_argument("--data", default="gesture_landmarks.npy")
    ap.add_argument("--labels", default="gesture_labels.npy")
    args = ap.parse_args()

    data_path, label_path = Path(args.data), Path(args.labels)
    for p in (data_path, label_path):
        if not p.is_file():
            sys.exit(f"File not found: {p}")

    X, y = load(data_path), load(label_path)
    if len(X) != len(y):
        sys.exit(f"Data ({len(X)}) and labels ({len(y)}) have different lengths - nothing changed.")

    targets = {t.lower() for t in args.labels_to_remove}
    mask = np.array([str(l).lower() in targets for l in y])
    print(f"Before: {len(y)} samples, labels: {sorted(set(map(str, y)))}")
    for t in args.labels_to_remove:
        n = int(sum(str(l).lower() == t.lower() for l in y))
        print(f"  '{t}': {n} samples" + ("" if n else "   <- not found"))
    if not mask.any():
        sys.exit("Nothing to remove - files untouched.")

    backup = Path("backup_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    backup.mkdir()
    shutil.copy2(data_path, backup / data_path.name)
    shutil.copy2(label_path, backup / label_path.name)

    np.save(data_path, X[~mask])
    np.save(label_path, y[~mask])
    print(f"After: {int((~mask).sum())} samples, labels: {sorted(set(map(str, y[~mask])))}")
    print(f"Backup of the originals: {backup}/")
    print("IMPORTANT: the model (action.h5) still knows the removed labels. Run train.py again.")


if __name__ == "__main__":
    main()
