"""
train_asl_test.py - train a TEST model on the imported ASL data only.

It never touches your real files (action.h5, gesture_landmarks.npy, gesture_labels.npy).
Everything is read from / written to the asl_test/ folder:
    in : asl_test/asl_test_landmarks.npy, asl_test/asl_test_labels.npy   (made by import_asl.py)
    out: asl_test/asl_test_model.h5, asl_test/asl_test_classes.json, asl_test/asl_test_report.txt

Usage:
    python train_asl_test.py
    python train_asl_test.py --epochs 150 --folder asl_test

Same network as train.py (LSTM 64-128-64 + two dense layers), so what you learn here carries over.

HOW TO READ THE RESULT
  If asl_test/asl_test_signers.npy exists (made by import_asl.py), the test set contains SIGNERS THE MODEL NEVER
  SAW DURING TRAINING. That is the honest number: it is much closer to how the model will do on a new person
  (you, on the webcam). Without that file the split is random and the accuracy is optimistic.

  Training data is augmented (mirrored hands for left-handed signers, small scale / rotation changes, noise).
  Validation and test data are never augmented.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np


def mirror_hands(A, mask):
    """A: (N, 20, 2, 21, 3). For samples where mask is True: swap left/right hand and flip x."""
    A = A.copy()
    sub = A[mask][:, :, ::-1].copy()
    sub[..., 0] *= -1.0
    A[mask] = sub
    return A


def augment(X, rng, copies):
    """Return X plus `copies` randomly altered versions of it. A missing hand stays exactly zero."""
    n = len(X)
    outs = [X]
    for _ in range(copies):
        A = X.reshape(n, 20, 2, 21, 3).copy()
        A = mirror_hands(A, rng.random(n) < 0.5)                      # left-handed signers
        A *= rng.uniform(0.9, 1.1, size=(n, 1, 1, 1, 1)).astype(np.float32)   # hand size
        th = np.deg2rad(rng.uniform(-10, 10, size=(n, 1, 1, 1)))      # small rotation in the image plane
        x, y = A[..., 0].copy(), A[..., 1].copy()
        A[..., 0] = x * np.cos(th) - y * np.sin(th)
        A[..., 1] = x * np.sin(th) + y * np.cos(th)
        present = (A != 0).any(axis=(3, 4), keepdims=True)            # (n, 20, 2, 1, 1)
        A += rng.normal(0, 0.02, size=A.shape).astype(np.float32) * present
        A *= present
        outs.append(A.reshape(n, 20, 126).astype(np.float32))
    return np.concatenate(outs, axis=0)


def split_by_signer(y, signers, seed):
    """Whole signers go to train / validation / test. Returns three index arrays."""
    rng = np.random.default_rng(seed)
    ids = np.array(sorted(set(signers.tolist())))
    rng.shuffle(ids)
    n_test = max(1, int(round(0.20 * len(ids))))
    n_val = max(1, int(round(0.15 * len(ids))))
    test_ids, val_ids = set(ids[:n_test].tolist()), set(ids[n_test:n_test + n_val].tolist())
    idx = np.arange(len(y))
    te = idx[np.isin(signers, list(test_ids))]
    va = idx[np.isin(signers, list(val_ids))]
    tr = idx[~np.isin(signers, list(test_ids | val_ids))]
    return tr, va, te, (len(ids) - n_test - n_val, n_val, n_test)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="asl_test")
    ap.add_argument("--epochs", type=int, default=150)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--aug-copies", type=int, default=4, help="augmented copies added per training sample (0 = none)")
    args = ap.parse_args()

    folder = Path(args.folder)
    xp, yp = folder / "asl_test_landmarks.npy", folder / "asl_test_labels.npy"
    if not xp.is_file() or not yp.is_file():
        sys.exit(f"Missing {xp} / {yp}. Run import_asl.py first.")

    X = np.load(xp).astype(np.float32)
    y_raw = np.load(yp).astype(str)
    if X.ndim != 3 or X.shape[1:] != (20, 126) or len(X) != len(y_raw):
        sys.exit(f"Unexpected data shape {X.shape} with {len(y_raw)} labels (expected (N, 20, 126)).")

    classes = sorted(set(y_raw))
    counts = {c: int((y_raw == c).sum()) for c in classes}
    print(f"{len(X)} samples, {len(classes)} signs, {min(counts.values())}-{max(counts.values())} samples per sign")
    if min(counts.values()) < 10:
        sys.exit("Some signs have fewer than 10 samples: " +
                 ", ".join(f"{c} ({n})" for c, n in counts.items() if n < 10) +
                 "\nRun the full import first (python import_asl.py --per-sign 30).")

    import tensorflow as tf
    from sklearn.model_selection import train_test_split
    from sklearn.utils.class_weight import compute_class_weight
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.utils import to_categorical

    tf.keras.utils.set_random_seed(args.seed)
    idx = {c: i for i, c in enumerate(classes)}
    y = np.array([idx[v] for v in y_raw])

    sp = folder / "asl_test_signers.npy"
    if sp.is_file() and len(np.load(sp)) == len(X):
        signers = np.load(sp)
        tr, va, te, ns = split_by_signer(y, signers, args.seed)
        X_tr, y_tr, X_va, y_va, X_te, y_te = X[tr], y[tr], X[va], y[va], X[te], y[te]
        how = f"by signer ({ns[0]} signers train / {ns[1]} validation / {ns[2]} test: test signers are UNSEEN in training)"
        missing = [classes[c] for c in range(len(classes)) if not (y_tr == c).any()]
        if missing:
            sys.exit("These signs have no training samples after the signer split: " + ", ".join(missing))
    else:
        how = "RANDOM split (no signer file: accuracy will be optimistic; run import_asl.py again to create it)"
        X_tr, X_rest, y_tr, y_rest = train_test_split(X, y, test_size=0.30, stratify=y, random_state=args.seed)
        X_va, X_te, y_va, y_te = train_test_split(X_rest, y_rest, test_size=0.50, stratify=y_rest,
                                                  random_state=args.seed)
    print(f"Split: {how}")
    print(f"train {len(X_tr)}  validation {len(X_va)}  test {len(X_te)}")
    if args.aug_copies > 0:
        rng = np.random.default_rng(args.seed)
        X_tr = augment(X_tr, rng, args.aug_copies)
        y_tr = np.tile(y_tr, args.aug_copies + 1)
        print(f"Training set after augmentation: {len(X_tr)} samples")

    n = len(classes)
    model = Sequential([
        Input(shape=(20, 126)),
        LSTM(64, return_sequences=True), Dropout(0.2),
        LSTM(128, return_sequences=True), Dropout(0.2),
        LSTM(64, return_sequences=False), Dropout(0.2),
        Dense(64, activation="relu"),
        Dense(32, activation="relu"),
        Dense(n, activation="softmax"),
    ])
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])

    cw = compute_class_weight("balanced", classes=np.arange(n), y=y_tr)
    model.fit(
        X_tr, to_categorical(y_tr, n),
        validation_data=(X_va, to_categorical(y_va, n)),
        epochs=args.epochs, batch_size=args.batch,
        class_weight={i: float(w) for i, w in enumerate(cw)},
        callbacks=[EarlyStopping(monitor="val_loss", patience=20, restore_best_weights=True),
                   ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=8, min_lr=1e-5)],
        verbose=2,
    )

    probs = model.predict(X_te, verbose=0)
    pred = probs.argmax(axis=1)
    acc = float((pred == y_te).mean())

    lines = [f"TEST accuracy: {acc:.1%}  ({int((pred == y_te).sum())}/{len(y_te)} correct, {n} signs)",
             f"Chance level would be about {1 / n:.1%}", f"Split: {how}", "", "Per sign (test set):"]
    per = []
    for c in range(n):
        m = y_te == c
        if m.any():
            per.append((float((pred[m] == c).mean()), classes[c], int(m.sum())))
    for a, name, k in sorted(per):
        lines.append(f"  {name:12s} {a:5.0%}  ({k} test samples)")
    conf = {}
    for t, p in zip(y_te, pred):
        if t != p:
            conf[(classes[t], classes[p])] = conf.get((classes[t], classes[p]), 0) + 1
    lines += ["", "Most common confusions (true -> predicted):"]
    for (t, p), k in sorted(conf.items(), key=lambda kv: -kv[1])[:8]:
        lines.append(f"  {t} -> {p}: {k}x")
    if not conf:
        lines.append("  none")
    report = "\n".join(lines)
    print("\n" + report)

    model.save(folder / "asl_test_model.h5")
    (folder / "asl_test_classes.json").write_text(json.dumps(classes))
    (folder / "asl_test_report.txt").write_text(report)
    print(f"\nSaved {folder / 'asl_test_model.h5'} (your real action.h5 was not touched)")


if __name__ == "__main__":
    main()