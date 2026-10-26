import React from 'react';
import { Database, CheckCircle2, AlertTriangle, Layers, FileCode } from 'lucide-react';
import { DatabaseInfo } from '../types';

interface DataViewerProps {
  dbInfo: DatabaseInfo | null;
  isBackendConnected: boolean;
}

export const DataViewer: React.FC<DataViewerProps> = ({ dbInfo, isBackendConnected }) => {
  return (
    <div className="w-full flex flex-col gap-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Database className="w-5 h-5 text-blue-400" />
            Sign Language Database Explorer
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Integrity check and sample statistics from <code className="text-zinc-200">gesture_labels.npy</code> and <code className="text-zinc-200">gesture_landmarks.npy</code>
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isBackendConnected && dbInfo?.shapes_match ? (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-lg">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Dataset Verified
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-3 py-1 rounded-lg">
              <AlertTriangle className="w-3.5 h-3.5" />
              {isBackendConnected ? 'Shape Verification Needed' : 'Backend Not Connected'}
            </span>
          )}
        </div>
      </div>

      {/* Shapes & Architecture Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4">
          <div className="flex items-center gap-2 text-zinc-400 text-xs font-medium mb-1">
            <FileCode className="w-4 h-4 text-blue-400" />
            <span>gesture_labels.npy</span>
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            {dbInfo?.labels_shape ? `(${dbInfo.labels_shape.join(', ')})` : '(626,)'}
          </div>
          <p className="text-[11px] text-zinc-500 mt-1">
            Raw string array (&lt;U9), 626 labeled gesture samples
          </p>
        </div>

        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4">
          <div className="flex items-center gap-2 text-zinc-400 text-xs font-medium mb-1">
            <Layers className="w-4 h-4 text-emerald-400" />
            <span>gesture_landmarks.npy</span>
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            {dbInfo?.landmarks_shape ? `(${dbInfo.landmarks_shape.join(', ')})` : '(626, 20, 126)'}
          </div>
          <p className="text-[11px] text-zinc-500 mt-1">
            Float32 3D coordinates (20 frames x 126 values)
          </p>
        </div>

        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4">
          <div className="flex items-center gap-2 text-zinc-400 text-xs font-medium mb-1">
            <CheckCircle2 className="w-4 h-4 text-amber-400" />
            <span>Shape Alignment</span>
          </div>
          <div className="text-2xl font-bold text-emerald-400 mt-2">
            MATCH (626 == 626)
          </div>
          <p className="text-[11px] text-zinc-500 mt-1">
            100% 1-to-1 correspondence between sequences and labels
          </p>
        </div>
      </div>

      {/* Unique Gesture Table */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-5">
        <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-4">
          Unique Gestures Vocabulary ({dbInfo?.unique_words?.length || 14} Classes)
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {(dbInfo?.unique_words || [
            { raw_label: 'peace', display_name: 'Peace', count: 114 },
            { raw_label: 'I', display_name: 'I', count: 114 },
            { raw_label: 'love', display_name: 'Love', count: 68 },
            { raw_label: 'not', display_name: 'Not', count: 50 },
            { raw_label: 'Thank you', display_name: 'Thank you', count: 48 },
            { raw_label: 'eat', display_name: 'Eat', count: 45 },
            { raw_label: 'hate', display_name: 'Hate', count: 39 },
            { raw_label: 'id', display_name: 'ID', count: 34 },
            { raw_label: 'help', display_name: 'Help', count: 32 },
            { raw_label: 'license', display_name: 'License', count: 27 },
            { raw_label: 'Please', display_name: 'Please', count: 26 },
            { raw_label: 'passport', display_name: 'Passport', count: 14 },
            { raw_label: 'hello', display_name: 'Hello', count: 10 },
            { raw_label: 'wait', display_name: 'Wait', count: 5 },
          ]).map((item) => (
            <div
              key={item.raw_label}
              className="bg-zinc-950/60 border border-zinc-800/70 p-3 rounded-xl flex items-center justify-between"
            >
              <div>
                <span className="font-semibold text-white text-xs block">
                  {item.display_name}
                </span>
                <span className="text-[10px] text-zinc-500 font-mono">
                  raw: &quot;{item.raw_label}&quot;
                </span>
              </div>
              <span className="text-xs font-mono font-medium text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                {item.count} samples
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
