import React, { useState } from 'react';
import { Play, Plus, CheckCircle2, Video } from 'lucide-react';
import { GestureStat } from '../types';

interface CollectModeProps {
  gestures: GestureStat[];
  onStartRecord: (label: string) => void;
  isRecording: boolean;
  recordingLabel?: string;
  onAddGesture: (name: string, key?: string) => void;
}

export const CollectMode: React.FC<CollectModeProps> = ({
  gestures,
  onStartRecord,
  isRecording,
  recordingLabel,
  onAddGesture,
}) => {
  const [newGestureName, setNewGestureName] = useState('');
  const [newGestureKey, setNewGestureKey] = useState('');

  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGestureName.trim()) return;
    onAddGesture(newGestureName.trim().toLowerCase(), newGestureKey.trim().toLowerCase() || undefined);
    setNewGestureName('');
    setNewGestureKey('');
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 shadow-xl flex flex-col h-full">
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800 mb-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Video className="w-5 h-5 text-emerald-400" />
            Mode Collecte (collect.py)
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Cliquez sur un geste ou pressez son raccourci clavier pour enregistrer 20 frames
          </p>
        </div>
      </div>

      {/* Quick Add Form */}
      <form onSubmit={handleAddSubmit} className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="Nouveau geste (ex: merci, oui)..."
          value={newGestureName}
          onChange={(e) => setNewGestureName(e.target.value)}
          className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-colors"
        />
        <input
          type="text"
          maxLength={1}
          placeholder="Touche"
          value={newGestureKey}
          onChange={(e) => setNewGestureKey(e.target.value)}
          className="w-16 text-center bg-zinc-950 border border-zinc-800 rounded-xl px-2 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-colors"
        />
        <button
          type="submit"
          className="bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-2 rounded-xl text-sm font-medium flex items-center gap-1.5 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Ajouter
        </button>
      </form>

      {/* Gestures Grid */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-2 max-h-[380px]">
        {gestures.map((g) => {
          const isCurrentRec = isRecording && recordingLabel === g.label;
          return (
            <div
              key={g.label}
              className={`flex items-center justify-between p-3 rounded-xl border transition-all ${
                isCurrentRec
                  ? 'bg-red-500/10 border-red-500/60 shadow-[0_0_15px_rgba(239,68,68,0.2)]'
                  : 'bg-zinc-950/60 border-zinc-800/80 hover:border-zinc-700'
              }`}
            >
              <div className="flex items-center gap-3">
                {g.key && (
                  <span className="w-7 h-7 flex items-center justify-center rounded-lg bg-zinc-800 text-emerald-400 font-mono font-bold text-xs uppercase border border-zinc-700">
                    {g.key}
                  </span>
                )}
                <div>
                  <div className="font-semibold text-white capitalize text-sm">{g.label}</div>
                  <div className="text-xs text-zinc-400">
                    {g.count} échantillon{g.count > 1 ? 's' : ''}
                  </div>
                </div>
              </div>

              <button
                disabled={isRecording}
                onClick={() => onStartRecord(g.label)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                  isCurrentRec
                    ? 'bg-red-500 text-white animate-pulse'
                    : 'bg-zinc-800 hover:bg-emerald-600 text-zinc-200 hover:text-white'
                }`}
              >
                {isCurrentRec ? (
                  <>
                    <span className="w-2 h-2 rounded-full bg-white animate-ping" />
                    En cours...
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5" />
                    Capturer
                  </>
                )}
              </button>
            </div>
          );
        })}
      </div>

      <div className="mt-4 pt-3 border-t border-zinc-800 text-xs text-zinc-500 flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
        Pour un bon entraînement, visez au moins 20 à 30 séquences par geste.
      </div>
    </div>
  );
};
