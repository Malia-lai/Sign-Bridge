import React, { useState, useEffect, useCallback } from 'react';
import { Header, TabType } from './components/Header';
import { LiveCamera } from './components/LiveCamera';
import { Simulator3D } from './components/Simulator3D';
import { SentenceBuilder } from './components/SentenceBuilder';
import { DataViewer } from './components/DataViewer';
import { DictionaryView } from './components/DictionaryView';
import { PythonStatus } from './components/PythonStatus';
import { CodeViewer } from './components/CodeViewer';
import { DatabaseInfo, DetectionResult, ServerStatus, UniqueGesture } from './types';
import {
  fetchServerStatus,
  fetchDatabaseInfo,
  fetchHealthCheck,
  fetchApiWords,
  clearServerHistory,
  addWordToServerHistory
} from './services/api';
import { FolderPlus, Camera, Layers, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function App() {
  const [currentTab, setCurrentTab] = useState<TabType>('live');
  const [activeScreen, setActiveScreen] = useState<'camera' | '3d'>('camera');

  // Backend, health & database status
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [serverStatus, setServerStatus] = useState<ServerStatus | null>(null);
  const [dbInfo, setDbInfo] = useState<DatabaseInfo | null>(null);
  const [missingFiles, setMissingFiles] = useState<string[]>([]);
  const [uniqueWords, setUniqueWords] = useState<UniqueGesture[]>([]);

  // History and fluent sentence state
  const [historyWords, setHistoryWords] = useState<string[]>([]);
  const [historyDisplay, setHistoryDisplay] = useState<string[]>([]);
  const [fluentSentence, setFluentSentence] = useState<string>('');

  // 1. Automatic loading on startup: /health, /api/words, /api/status
  const loadDataAutomatically = useCallback(() => {
    // Health check (checks action.h5, gesture_labels.npy, gesture_landmarks.npy)
    fetchHealthCheck().then((health) => {
      if (health) {
        setIsBackendConnected(true);
        setMissingFiles(health.missing_files || []);
      } else {
        setIsBackendConnected(false);
      }
    });

    // Automatic words loading
    fetchApiWords().then((words) => {
      if (words && words.length > 0) {
        setUniqueWords(words);
      }
    });

    // Status and database info
    fetchServerStatus().then((status) => {
      if (status) {
        setServerStatus(status);
        if (status.missing_files) {
          setMissingFiles(status.missing_files);
        }
      }
    });

    fetchDatabaseInfo().then((info: DatabaseInfo | null) => {
      if (info) {
        setDbInfo(info);
        if (info.unique_words && info.unique_words.length > 0) {
          setUniqueWords(info.unique_words);
        }
      }
    });
  }, []);

  useEffect(() => {
    loadDataAutomatically();
    const timer = setInterval(loadDataAutomatically, 3000);
    return () => clearInterval(timer);
  }, [loadDataAutomatically]);

  // Handle incoming detection updates
  const handleDetectionUpdate = useCallback((res: DetectionResult) => {
    if (res.history_words) {
      setHistoryWords(res.history_words);
    }
    if (res.history_display) {
      setHistoryDisplay(res.history_display);
    }
    if (res.sentence !== undefined) {
      setFluentSentence(res.sentence);
    }
  }, []);

  // History management
  const handleClearHistory = () => {
    setHistoryWords([]);
    setHistoryDisplay([]);
    setFluentSentence('');
    clearServerHistory();
  };

  const handleAddWord = (rawLabel: string) => {
    addWordToServerHistory(rawLabel).then(() => {
      loadDataAutomatically();
    });
    const updated = [...historyWords, rawLabel];
    setHistoryWords(updated);
    const wordsDisplay = updated.map((w) => {
      const match = uniqueWords.find((u) => u.raw_label === w);
      return match ? match.display_name : w.charAt(0).toUpperCase() + w.slice(1);
    });
    setHistoryDisplay(wordsDisplay);
    setFluentSentence(wordsDisplay.join(' ') + '.');
  };

  const handleRemoveWord = (index: number) => {
    const updated = historyWords.filter((_, i) => i !== index);
    setHistoryWords(updated);
    const wordsDisplay = updated.map((w) => {
      const match = uniqueWords.find((u) => u.raw_label === w);
      return match ? match.display_name : w.charAt(0).toUpperCase() + w.slice(1);
    });
    setHistoryDisplay(wordsDisplay);
    setFluentSentence(wordsDisplay.length ? wordsDisplay.join(' ') + '.' : '');
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans selection:bg-blue-600/30 selection:text-blue-200">
      {/* Top Header */}
      <Header
        currentTab={currentTab}
        onSelectTab={(tab) => {
          setCurrentTab(tab);
          if (tab === 'live') {
            setActiveScreen('camera');
          }
        }}
        uniqueWordsCount={uniqueWords.length}
      />

      {/* Main View Area */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
        {/* Missing Files Warning Banner if any file is missing */}
        {missingFiles.length > 0 && (
          <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-2xl p-4 flex items-center justify-between text-xs text-red-200">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
              <div>
                <p className="font-semibold text-white">Missing Required Data Files:</p>
                <p className="text-zinc-300">
                  {missingFiles.join(', ')} not found in backend directory. Please place your database files in the project root.
                </p>
              </div>
            </div>
            <span className="font-mono text-xs bg-red-950/60 px-3 py-1 rounded-lg border border-red-800/60 text-red-300">
              Files Required
            </span>
          </div>
        )}

        {/* Tab 1: Live & 3D Screen */}
        {currentTab === 'live' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left 2 Columns: Live Camera & 3D Simulator */}
            <div className="lg:col-span-2 flex flex-col gap-4">
              {/* IMPORTANT: LiveCamera is NEVER unmounted when switching to 3D Simulator.
                  It is hidden with CSS instead to prevent black screens and stream re-acquisitions. */}
              <div className={activeScreen === 'camera' ? 'block' : 'hidden'}>
                <LiveCamera
                  isBackendConnected={isBackendConnected}
                  missingFiles={missingFiles}
                  historyWords={historyWords}
                  onOpen3DSimulator={() => setActiveScreen('3d')}
                  onDetectionUpdate={handleDetectionUpdate}
                  onAddWord={handleAddWord}
                />
              </div>

              <div className={activeScreen === '3d' ? 'block' : 'hidden'}>
                <Simulator3D
                  isBackendConnected={isBackendConnected}
                  uniqueWords={uniqueWords}
                  onBackToCamera={() => setActiveScreen('camera')}
                  sentenceWords={historyWords}
                />
              </div>
            </div>

            {/* Right Column: Sentence Builder (Fluent Sentence + Recognised Words) */}
            <div className="lg:col-span-1">
              <SentenceBuilder
                historyWords={historyWords}
                historyDisplay={historyDisplay}
                fluentSentence={fluentSentence}
                uniqueWords={uniqueWords}
                onClearHistory={handleClearHistory}
                onAddWord={handleAddWord}
                onRemoveWord={handleRemoveWord}
              />
            </div>
          </div>
        )}

        {/* Tab 2: Collect Guide */}
        {currentTab === 'collect' && (
          <div className="max-w-4xl mx-auto bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-2">
              <FolderPlus className="w-5 h-5 text-blue-400" />
              Collect Data Module (collect.py)
            </h2>
            <p className="text-xs text-zinc-400 leading-relaxed mb-6">
              Use your local webcam script <code className="text-zinc-200">collect.py</code> to record new gestures and append them to <code className="text-zinc-200">gesture_landmarks.npy</code> and <code className="text-zinc-200">gesture_labels.npy</code>.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800/80">
                <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block mb-1">
                  Sequence Length
                </span>
                <span className="text-xl font-bold text-white">20 Frames</span>
                <p className="text-[11px] text-zinc-500 mt-1">Recorded at 30 FPS</p>
              </div>

              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800/80">
                <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block mb-1">
                  Coordinates per Frame
                </span>
                <span className="text-xl font-bold text-white">126 Features</span>
                <p className="text-[11px] text-zinc-500 mt-1">21 left (63) + 21 right (63)</p>
              </div>

              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800/80">
                <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block mb-1">
                  Countdown Delay
                </span>
                <span className="text-xl font-bold text-amber-400">2.0 Seconds</span>
                <p className="text-[11px] text-zinc-500 mt-1">Get ready indicator</p>
              </div>
            </div>

            <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800/80 font-mono text-xs text-zinc-300">
              <p className="text-zinc-500 mb-2"># Run collector from terminal:</p>
              <p className="text-emerald-400">python collect.py</p>
            </div>
          </div>
        )}

        {/* Tab 3: Data Explorer */}
        {currentTab === 'data' && (
          <DataViewer dbInfo={dbInfo} isBackendConnected={isBackendConnected} />
        )}

        {/* Tab 4: Dictionary */}
        {currentTab === 'dictionary' && <DictionaryView />}

        {/* Tab 5: Python Status */}
        {currentTab === 'python' && (
          <PythonStatus
            status={serverStatus}
            isBackendConnected={isBackendConnected}
            onRefresh={loadDataAutomatically}
          />
        )}

        {/* Tab 6: Audit & Code */}
        {currentTab === 'audit' && <CodeViewer />}
      </main>
    </div>
  );
}
