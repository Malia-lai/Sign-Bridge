import React from 'react';
import { Camera, FolderPlus, Database, BookOpen, Terminal, Code2 } from 'lucide-react';

export type TabType = 'live' | 'collect' | 'data' | 'dictionary' | 'python' | 'audit';

interface HeaderProps {
  currentTab: TabType;
  onSelectTab: (tab: TabType) => void;
  uniqueWordsCount: number;
}

export const Header: React.FC<HeaderProps> = ({ currentTab, onSelectTab, uniqueWordsCount }) => {
  return (
    <header className="w-full bg-zinc-950 border-b border-zinc-900 px-6 py-3 flex items-center justify-between">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20 text-amber-300 font-bold text-xl select-none">
          🤟
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-white font-semibold text-base tracking-tight">
              Sign Language AI Studio
            </h1>
            <span className="text-[11px] font-medium text-blue-400 bg-blue-500/10 border border-blue-500/20 px-1.5 py-0.5 rounded">
              v2.0
            </span>
          </div>
          <p className="text-xs text-zinc-400">
            Real-time Hand Tracking &amp; Sentence Synthesis
          </p>
        </div>
      </div>

      {/* Nav Tabs */}
      <nav className="flex items-center bg-zinc-900/80 p-1 rounded-xl border border-zinc-800/80 gap-1 text-xs">
        <button
          onClick={() => onSelectTab('live')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all font-medium ${
            currentTab === 'live'
              ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/30'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
          }`}
        >
          <Camera className="w-3.5 h-3.5" />
          <span>Live</span>
        </button>

        <button
          onClick={() => onSelectTab('collect')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all font-medium ${
            currentTab === 'collect'
              ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/30'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
          }`}
        >
          <FolderPlus className="w-3.5 h-3.5" />
          <span>Collect</span>
        </button>

        <button
          onClick={() => onSelectTab('data')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all font-medium ${
            currentTab === 'data'
              ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/30'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Data ({uniqueWordsCount})</span>
        </button>

        <button
          onClick={() => onSelectTab('dictionary')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all font-medium ${
            currentTab === 'dictionary'
              ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/30'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          <span>Dictionary</span>
        </button>

        <button
          onClick={() => onSelectTab('python')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all font-medium ${
            currentTab === 'python'
              ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/30'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
          }`}
        >
          <Terminal className="w-3.5 h-3.5" />
          <span>&gt;_ Python</span>
        </button>

        <button
          onClick={() => onSelectTab('audit')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all font-medium ${
            currentTab === 'audit'
              ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/30'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
          }`}
        >
          <Code2 className="w-3.5 h-3.5" />
          <span>&lt;/&gt; Audit &amp; Code</span>
        </button>
      </nav>
    </header>
  );
};
