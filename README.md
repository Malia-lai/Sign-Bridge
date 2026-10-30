# Sign-Bridge

Real-time **sign language recognition** from a normal webcam, with a **voice** that reads the signs out loud.

Your hands are tracked with MediaPipe (21 points per hand), a short movement (20 frames) is given to an **LSTM neural
network**, and the recognised sign is added to a sentence that is spoken. You can record your **own signs** and retrain
the model, so the vocabulary is not fixed.

Current vocabulary (14 signs): I, Please, Thank you, eat, hate, hello, help, id, license, love, not, passport, peace, wait.
It includes everyday words and administrative words (ID, license, passport).

---

## Features
- Real-time recognition of **static and moving** signs, one or two hands.
- **Voice output**: each recognised word is spoken once; the whole sentence can be replayed.
- **Editable sign database**: add, delete or change signs with simple scripts (no code in the model).
- **Web interface** (React + a small FastAPI server): live camera, sentence builder, sign dictionary and a 3D replay of
  each sign from your real data. The hands are tracked in the browser; the prediction is made by the Python model.


---

## How it works
1. `collect.py` records examples. One example = 20 frames x 126 numbers
   (2 hands x 21 landmarks x x/y/z, a missing hand = zeros).
2. Examples are saved in two files: `gesture_landmarks.npy` (data) and `gesture_labels.npy` (sign names).
3. `train.py` trains an LSTM (64 -> 128 -> 64 units, then two dense layers, softmax) and saves it as `action.h5`.
4. `realtime.py` runs the webcam, keeps the last 20 frames, and predicts a sign. A sign must be confident (> 0.75) and
   held for 0.35 s before it is accepted, then a cooldown avoids repeating it.
5. The web interface does the same thing in a browser: MediaPipe in the page sends the hand coordinates to `backend.py`
   (FastAPI + WebSocket), which uses `detector.py` and the same `action.h5`.

---

## Requirements
- **Python 3.11** (3.8-3.11 work; it must be compatible with `mediapipe 0.10.9` and `tensorflow 2.13`)
- A webcam
- Windows 10/11 (tested). `requirements.txt` contains Windows-only packages (`pywin32`, `comtypes`, `pypiwin32`,
  `tensorflow-intel`): on Linux/macOS remove those lines first.
- Node.js 18+ (only for the web interface)

## Run it locally

```bash
git clone https://github.com/Malia-lai/Sign-Bridge
cd Sign-Bridge

python -m venv venv
venv\Scripts\activate            # Windows (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
```

**Start recognising signs (needs `action.h5`, `gesture_landmarks.npy`, `gesture_labels.npy`, already in the repo):**
```bash
python realtime.py
```
Keys: `q` or `Esc` quit 
- `c` clear the sentence
- `s` speak the sentence
- `m` mute / unmute the voice.

**Web interface (Windows, one command):**
```bash
run_app.bat          # creates .venv, installs requirements, builds the page, starts the server, opens the browser
```
It serves the app at http://localhost:8000. The camera needs your permission in the browser.

**Web interface (manual, any system):**
```bash
pip install -r requirements.txt
npm install
npm run build
python backend.py                  # open http://localhost:8000
```
Open the page from port 8000 (not the Vite dev port 3000): the live recognition connection is served by `backend.py`.

---

## Use your own signs
| Step | Command | What it does |
|---|---|---|
| 1. Add the sign | edit the `GESTURES` dictionary in `collect.py` (`'key': 'name'`) | one key per sign |
| 2. Record | `python collect.py` | press the key, wait for the 2 s countdown, then make the sign. Record 30+ examples per sign. `q` quits |
| 3. Check | `python samplenum.py` | shape of the data and whether the file is valid |
| 4. Train | `python train.py` | writes `action.h5` and prints the test result |
| 5. Run | `python realtime.py` | |

To **delete** signs: `python remove_labels.py name1 name2` (makes a backup first), or edit the name in `delete.py`.

---

## Project files
| File | Purpose |
|---|---|
| `collect.py` | record signs with the webcam |
| `train.py` | train the LSTM and save `action.h5` |
| `realtime.py` | live recognition, sentence and voice |
| `samplenum.py`, `delete.py`, `remove_labels.py` | check and edit the data |
| `backend.py`, `detector.py` | web server and the sign detector used by the web interface |
| `src/`, `public/`, `index.html` | web interface (React + TypeScript + MediaPipe) |
| `agent/` | AI sentence agent (FastAPI, Mistral / Gemini), with its own `README.md` and tests |
| `sign_features.py`, `import_asl.py`, `train_asl_test.py` | experiments with the public Kaggle "ASL Signs" dataset |
| `gesture_landmarks.npy`, `gesture_labels.npy`, `action.h5` | the dataset and the trained model |

---

## Limits (honest notes)
- Recognition is trained on the recordings of one person and one webcam setup: another signer or camera angle can lower
  accuracy until more examples are recorded.
- Very similar hand shapes made in different places on the body (hello at the forehead, please on the chest) can be
  confused, because the model mostly sees the hand movement in the picture.

---

## Who built what

| Person | Part |
|---|---|
| Malia | Data collection and sign database (`collect.py`, `delete.py`, `samplenum.py`) |
| Malia | Model training and evaluation (`train.py`, accuracy tests) |
| Malia | Real-time recognition, sentence rules and voice (`realtime.py`) |
| Malia, Aymen | Web interface, dictionary and 3D replay (`src/`) |
| Malia, Aymen | Dataset experiments, documentation and testing |

Built with the help of AI tools (Google AI Studio and Claude) for parts of the code, reviewed and tested by the team.

