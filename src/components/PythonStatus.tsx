import React from 'react';
import { Terminal, CheckCircle2, XCircle, Cpu, Sliders, RefreshCw, Play } from 'lucide-react';
import { ServerStatus } from '../types';

interface PythonStatusProps {
  status: ServerStatus | null;
  isBackendConnected: boolean;
  onRefresh: () => void;
}

export const PythonStatus: React.FC<PythonStatusProps> = ({
  status,
  isBackendConnected,
  onRefresh,
}) => {
  return (
    <div className="w-full flex flex-col gap-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Terminal className="w-5 h-5 text-blue-400" />
            Python Backend Environment &amp; Engine
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            FastAPI server running <code className="text-zinc-200">detector.py</code> via WebSockets on port 8000
          </p>
        </div>

        <button
          onClick={onRefresh}
          className="flex items-center gap-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs px-3 py-1.5 rounded-xl border border-zinc-700/60 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Connection & Model Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              FastAPI WebSocket Server
            </span>
            {isBackendConnected ? (
              <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-md font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Online
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-md font-medium">
                <XCircle className="w-3.5 h-3.5" />
                Disconnected
              </span>
            )}
          </div>
          <div className="font-mono text-sm text-zinc-200 mb-2">
            ws://localhost:8000/ws
          </div>
          <p className="text-[11px] text-zinc-500">
            {isBackendConnected
              ? 'Receiving browser video frames and streaming predictions in real time.'
              : 'Start the server locally using run_app.bat or "python backend.py".'}
          </p>
        </div>

        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-blue-400" />
              LSTM Model Engine
            </span>
            <span className="text-xs font-mono text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded">
              action.h5
            </span>
          </div>
          <div className="text-sm font-semibold text-white mb-2">
            Sequential LSTM (64-128-64) + Dense (64-32-{status?.classes_count || 14})
          </div>
          <p className="text-[11px] text-zinc-500">
            Sequence length: 20 frames • 126 coordinate features per frame (63 left + 63 right)
          </p>
        </div>
      </div>

      {/* Runtime Hyperparameters & Thresholds */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-5">
        <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2 mb-4">
          <Sliders className="w-4 h-4 text-emerald-400" />
          Configured Hyperparameters (detector.py)
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800">
            <span className="text-zinc-500 block mb-1 text-[11px]">Confidence Threshold</span>
            <span className="text-base font-bold text-emerald-400">0.75</span>
            <span className="text-[10px] text-zinc-500 block mt-0.5">(Upgraded from 0.70)</span>
          </div>

          <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800">
            <span className="text-zinc-500 block mb-1 text-[11px]">Stable Duration</span>
            <span className="text-base font-bold text-blue-400">0.35s</span>
            <span className="text-[10px] text-zinc-500 block mt-0.5">Continuous hold</span>
          </div>

          <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800">
            <span className="text-zinc-500 block mb-1 text-[11px]">Word Cooldown</span>
            <span className="text-base font-bold text-amber-400">1.8s</span>
            <span className="text-[10px] text-zinc-500 block mt-0.5">Between repeats</span>
          </div>

          <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800">
            <span className="text-zinc-500 block mb-1 text-[11px]">Input Window</span>
            <span className="text-base font-bold text-purple-400">20 Frames</span>
            <span className="text-[10px] text-zinc-500 block mt-0.5">126 float32 values</span>
          </div>
        </div>
      </div>

      {/* Windows Launch Instructions */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-5">
        <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2 mb-3">
          <Play className="w-4 h-4 text-blue-400" />
          Windows Launcher (run_app.bat)
        </h3>
        <p className="text-xs text-zinc-400 mb-3">
          Double-click <code className="text-white bg-zinc-800 px-1.5 py-0.5 rounded font-mono">run_app.bat</code> in your project directory. It automatically:
        </p>
        <ol className="text-xs text-zinc-400 space-y-1.5 list-decimal list-inside pl-1 font-mono">
          <li>Verifies Python 3.9, 3.10, or 3.11</li>
          <li>Creates <code className="text-blue-300">.venv</code> virtual environment if missing</li>
          <li>Installs dependencies from <code className="text-blue-300">requirements.txt</code></li>
          <li>Builds the frontend and starts FastAPI on <code className="text-emerald-400">http://localhost:8000</code></li>
        </ol>
      </div>
    </div>
  );
};
