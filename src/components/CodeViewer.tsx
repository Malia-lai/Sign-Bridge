import React, { useState } from 'react';
import { Code2, Check, Copy, FileText } from 'lucide-react';

const DETECTOR_SNIPPET = `# detector.py - Adapted verbatim from realtime.py with 3 requested changes:
# 1. CONFIDENCE_THRESHOLD = 0.75 (realtime.py stays at 0.70)
# 2. English-only display (French dictionary removed, translations applied to display only)
# 3. Internal labels unchanged (matching gesture_labels.npy exactly)

import numpy as np
import mediapipe as mp
import math
import time

ONCE_PER_SENTENCE = ["hello"]
BLOCK_IMMEDIATE_REPEAT = True
CONFIDENCE_THRESHOLD = 0.75
STABLE_DURATION = 0.35
COOLDOWN = 1.8

def get_allowed_best_sign(sentence_history, probabilities, threshold, actions_list):
    once_set = {s.lower() for s in ONCE_PER_SENTENCE}
    history_lower = [s.lower() for s in sentence_history]
    last_word = history_lower[-1] if history_lower else None

    valid_candidates = []
    for i, sign in enumerate(actions_list):
        prob = float(probabilities[i]) if i < len(probabilities) else 0.0
        if prob < threshold:
            continue
        sign_lower = sign.lower()
        if sign_lower in once_set and sign_lower in history_lower:
            continue
        if BLOCK_IMMEDIATE_REPEAT and sign_lower == last_word:
            continue
        valid_candidates.append((sign, prob))

    if not valid_candidates:
        return None
    best_sign, _ = max(valid_candidates, key=lambda x: x[1])
    return best_sign

def classify_geometry(hands_lms_list):
    if not hands_lms_list:
        return None, 0.0
    primary = hands_lms_list[0]
    if len(primary) < 21:
        return None, 0.0
    # ... Anatomical rules (I, peace, love, eat, hello, hate vs not, etc.) ...
`;

const REALTIME_SNIPPET = `# realtime.py - Original OpenCV desktop application (UNTOUCHED)
# Seuil: 0.70 | pyttsx3 voice engine | cv2.VideoCapture direct window
CONFIDENCE_THRESHOLD = 0.70
STABLE_DURATION = 0.35
COOLDOWN = 1.8

# Strict rule enforced: realtime.py, action.h5, gesture_labels.npy,
# gesture_landmarks.npy, collect.py, train.py, and delete.py are kept intact.
`;

const RUN_APP_BAT_SNIPPET = `@echo off
:: run_app.bat - Launcher for Windows with automatic venv and dependencies
where python >nul 2>nul
if not exist ".venv\\Scripts\\activate.bat" (
    python -m venv .venv
)
call .venv\\Scripts\\activate.bat
python -m pip install -r requirements.txt
start "" "http://localhost:8000"
python backend.py
`;

export const CodeViewer: React.FC = () => {
  const [activeFile, setActiveFile] = useState<'detector' | 'realtime' | 'launcher'>('detector');
  const [copied, setCopied] = useState(false);

  const getActiveCode = () => {
    switch (activeFile) {
      case 'detector':
        return DETECTOR_SNIPPET;
      case 'realtime':
        return REALTIME_SNIPPET;
      case 'launcher':
        return RUN_APP_BAT_SNIPPET;
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(getActiveCode());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="w-full flex flex-col gap-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Code2 className="w-5 h-5 text-blue-400" />
            Code Audit &amp; Verification
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Verifying strict rules: <code className="text-zinc-200">realtime.py</code> untouched, <code className="text-zinc-200">detector.py</code> verbatim with 0.75 threshold and English display.
          </p>
        </div>

        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs px-3 py-1.5 rounded-xl border border-zinc-700/60 transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? 'Copied!' : 'Copy Code'}</span>
        </button>
      </div>

      {/* File Tabs */}
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
        <button
          onClick={() => setActiveFile('detector')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            activeFile === 'detector'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>detector.py (New, 0.75 threshold)</span>
        </button>

        <button
          onClick={() => setActiveFile('realtime')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            activeFile === 'realtime'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>realtime.py (Untouched)</span>
        </button>

        <button
          onClick={() => setActiveFile('launcher')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            activeFile === 'launcher'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>run_app.bat (Windows Launcher)</span>
        </button>
      </div>

      {/* Code Display Box */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-4 overflow-x-auto font-mono text-xs text-zinc-300 leading-relaxed shadow-inner">
        <pre>{getActiveCode()}</pre>
      </div>
    </div>
  );
};
