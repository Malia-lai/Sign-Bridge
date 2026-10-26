import os
import numpy as np
from sklearn.model_selection import train_test_split
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.callbacks import TensorBoard, EarlyStopping

# --- 1. SETTINGS & PATHS ---
DATA_FILE = 'gesture_landmarks.npy'
LABEL_FILE = 'gesture_labels.npy'


# --- 2. LOAD AND PREPARE DATA ---
if not os.path.exists(DATA_FILE) or not os.path.exists(LABEL_FILE):
    print("ERROR: Could not find .npy files. Run collect.py first!")
    exit()


X = np.load(DATA_FILE).astype(np.float32)
raw_labels = np.load(LABEL_FILE)
ACTIONS = np.array(sorted(set(raw_labels)))
raw_labels = np.load(LABEL_FILE)

label_map = {label: num for num, label in enumerate(ACTIONS)}
labels = np.array([label_map[l] for l in raw_labels])

y = to_categorical(labels, num_classes=len(ACTIONS)).astype(int)

# Fixed: 20% test split, stratified for balanced classes, reproducible seed
x_train, x_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=labels
)

print(f"Data Loaded Successfully!")
print(f"X Shape (Samples, Frames, Coords): {X.shape}")
print(f"y Shape (Samples, Categories): {y.shape}")

# --- 3. BUILD THE LSTM MODEL ---
from tensorflow.keras.layers import Input

model = Sequential([
    Input(shape=(X.shape[1], X.shape[2])),
    LSTM(64, return_sequences=True),
    LSTM(128, return_sequences=True),
    LSTM(64, return_sequences=False),
    Dense(64, activation='relu'),
    Dense(32, activation='relu'),
    Dense(len(ACTIONS), activation='softmax')
])

# --- 4. COMPILE AND TRAIN ---
model.compile(optimizer='Adam', loss='categorical_crossentropy', metrics=['categorical_accuracy'])

log_dir = os.path.join('Logs')
tb_callback = TensorBoard(log_dir=log_dir)

# Fixed: added early stopping, validation data, and balanced class weights
from sklearn.utils.class_weight import compute_class_weight
raw_classes = np.unique(labels)
weights = compute_class_weight(class_weight='balanced', classes=raw_classes, y=labels)
class_weight_dict = {int(c): float(w) for c, w in zip(raw_classes, weights)}
print(f"Balanced Class Weights: {class_weight_dict}")

early_stop = EarlyStopping(monitor='val_loss', patience=30, restore_best_weights=True)

print("\n--- Starting Training ---")
model.fit(
    x_train, y_train,
    epochs=200,
    validation_data=(x_test, y_test),
    class_weight=class_weight_dict,
    callbacks=[tb_callback, early_stop]
)

# --- 5. EVALUATE & SAVE ---
model.save('action.h5')
print("\nModel saved as 'action.h5'")

if len(x_test) > 0:
    res = model.predict(x_test)
    print(f"Test Prediction: {ACTIONS[np.argmax(res[0])]}")
    print(f"Actual Label:    {ACTIONS[np.argmax(y_test[0])]}")