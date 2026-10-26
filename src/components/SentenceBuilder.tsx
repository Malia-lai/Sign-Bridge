import React, { useState } from 'react';
import { Sparkles, Clock, Volume2, Copy, Trash2, Plus, Check, Layers } from 'lucide-react';
import { speechService } from '../services/speech';

interface SentenceBuilderProps {
  historyWords: string[];
  historyDisplay: string[];
  fluentSentence: string;
  uniqueWords: { raw_label: string; display_name: string }[];
  onClearHistory: () => void;
  onAddWord: (word: string) => void;
  onRemoveWord: (index: number) => void;
}

export const SentenceBuilder: React.FC<SentenceBuilderProps> = ({
  historyWords,
  historyDisplay,
  fluentSentence,
  uniqueWords,
  onClearHistory,
  onAddWord,
  onRemoveWord,
}) => {
  const [selectedWordToAdd, setSelectedWordToAdd] = useState<string>('');
  const [copied, setCopied] = useState(false);

  const handleSpeakSentence = () => {
    if (fluentSentence) {
      speechService.speak(fluentSentence);
    }
  };

  const handleCopySentence = () => {
    if (!fluentSentence) return;
    navigator.clipboard.writeText(fluentSentence);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleAddSelectedWord = () => {
    if (selectedWordToAdd) {
      onAddWord(selectedWordToAdd);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* 1. FLUENT SENTENCE CARD */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4 flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <h2 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
              Fluent Sentence
            </h2>
          </div>

          {fluentSentence && (
            <div className="flex items-center gap-1">
              <button
                onClick={handleSpeakSentence}
                title="Speak sentence"
                className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
              >
                <Volume2 className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleCopySentence}
                title="Copy to clipboard"
                className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
              <button
                onClick={onClearHistory}
                title="Clear sentence"
                className="p-1.5 rounded-lg text-zinc-400 hover:text-red-400 hover:bg-zinc-800 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Inset Box */}
        <div className="min-h-[75px] bg-zinc-950/70 border border-zinc-800/80 rounded-xl p-3.5 flex items-center justify-center text-center">
          {fluentSentence ? (
            <p className="text-sm text-zinc-100 font-medium leading-relaxed">
              &ldquo;{fluentSentence}&rdquo;
            </p>
          ) : (
            <p className="text-xs text-zinc-500 italic">
              Sign words to reconstruct a fluent sentence...
            </p>
          )}
        </div>
      </div>

      {/* 2. RECOGNISED WORDS (N) CARD */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4 flex flex-col min-h-[300px]">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-blue-400" />
            <h2 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
              Recognised Words ({historyWords.length})
            </h2>
          </div>

          {historyWords.length > 0 && (
            <button
              onClick={onClearHistory}
              className="text-[11px] text-zinc-400 hover:text-red-400 transition-colors"
            >
              Clear
            </button>
          )}
        </div>

        {/* Words List or Empty State */}
        <div className="flex-1 flex flex-col justify-center">
          {historyWords.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <div className="w-12 h-12 rounded-xl bg-zinc-800/40 flex items-center justify-center text-zinc-500 mb-3 border border-zinc-800">
                <Layers className="w-6 h-6" />
              </div>
              <p className="text-xs font-medium text-zinc-400 mb-0.5">No gestures recorded yet</p>
              <p className="text-[11px] text-zinc-500 max-w-[200px]">
                Turn on camera and sign to see results here
              </p>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2 py-2">
              {historyDisplay.map((word, idx) => (
                <div
                  key={`${word}-${idx}`}
                  className="flex items-center gap-1.5 bg-zinc-800/80 border border-zinc-700/60 px-2.5 py-1.5 rounded-xl text-xs text-zinc-100 shadow-sm animate-in fade-in zoom-in-95 duration-150"
                >
                  <span className="text-zinc-500 font-mono text-[10px]">{idx + 1}.</span>
                  <span className="font-semibold text-white">{word}</span>
                  <button
                    onClick={() => speechService.speak(word)}
                    title="Speak word"
                    className="text-zinc-400 hover:text-amber-400 ml-0.5 transition-colors"
                  >
                    <Volume2 className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => onRemoveWord(idx)}
                    title="Remove word"
                    className="text-zinc-500 hover:text-red-400 transition-colors"
                  >
                    &times;
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Manual Add Word Area */}
        <div className="mt-4 pt-3 border-t border-zinc-800/80">
          <label className="text-[11px] font-medium text-zinc-400 mb-1.5 block">
            Manual Add-Word Area
          </label>
          <div className="flex items-center gap-2">
            <select
              value={selectedWordToAdd}
              onChange={(e) => setSelectedWordToAdd(e.target.value)}
              className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">Select gesture word...</option>
              {uniqueWords.map((item) => (
                <option key={item.raw_label} value={item.raw_label}>
                  {item.display_name}
                </option>
              ))}
            </select>
            <button
              onClick={handleAddSelectedWord}
              disabled={!selectedWordToAdd}
              className="flex items-center gap-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 text-white px-3 py-1.5 rounded-xl text-xs font-medium transition-colors shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
