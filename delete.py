import numpy as np

X = np.load('gesture_landmarks.npy')
y = np.load('gesture_labels.npy')

keep = y != 'sleep' #Add name of the gesture exemple != 'Hate'
np.save('gesture_landmarks.npy', X[keep])
np.save('gesture_labels.npy', y[keep])
print(f"Removed. Remaining: {dict(zip(*np.unique(y[keep], return_counts=True)))}")
