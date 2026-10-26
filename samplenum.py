import numpy as np

file_path = 'gesture_landmarks.npy'

try:
    # mmap_mode='r' ensures we don't accidentally write to it while checking
    data = np.load(file_path, mmap_mode='r')
    print("✅ File loaded successfully!")
    print(f"Dataset Shape: {data.shape}")
    print(f"Data Type: {data.dtype}")
except Exception as e:
    print(f"❌ File is corrupted or invalid! Error: {e}")