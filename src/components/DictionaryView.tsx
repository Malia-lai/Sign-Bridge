import React from 'react';
import { BookOpen, Volume2, ShieldCheck, Zap } from 'lucide-react';
import { speechService } from '../services/speech';

interface SignEntry {
  raw_label: string;
  display_name: string;
  description: string;
  handType: 'Single Hand' | 'Two Hands';
  rule?: string;
  category: 'Common' | 'Identity' | 'Emotion' | 'Action';
}

const DICTIONARY_ENTRIES: SignEntry[] = [
  {
    raw_label: 'hello',
    display_name: 'Hello',
    description: 'Open hand with extended fingers held upright above the wrist.',
    handType: 'Single Hand',
    rule: 'Once per sentence (cleared with Clear button)',
    category: 'Common'
  },
  {
    raw_label: 'peace',
    display_name: 'Peace',
    description: 'V-sign with index and middle fingers extended apart; thumb and other fingers folded.',
    handType: 'Single Hand',
    category: 'Common'
  },
  {
    raw_label: 'love',
    display_name: 'Love',
    description: 'I-Love-You handshape: thumb, index, and pinky extended; middle and ring folded.',
    handType: 'Single Hand',
    category: 'Emotion'
  },
  {
    raw_label: 'I',
    display_name: 'I',
    description: 'Pinky finger extended vertically, thumb and other three fingers folded into palm.',
    handType: 'Single Hand',
    category: 'Common'
  },
  {
    raw_label: 'not',
    display_name: 'Not',
    description: 'Thumb pointing upward or forward under chin with fingers tucked in a fist.',
    handType: 'Single Hand',
    category: 'Common'
  },
  {
    raw_label: 'eat',
    display_name: 'Eat',
    description: 'Fingers pinched together toward the thumb tip moved toward the mouth.',
    handType: 'Single Hand',
    category: 'Action'
  },
  {
    raw_label: 'hate',
    display_name: 'Hate',
    description: 'Fist with thumb pointing downward or outward in rejection gesture.',
    handType: 'Single Hand',
    category: 'Emotion'
  },
  {
    raw_label: 'help',
    display_name: 'Help',
    description: 'Flat palm supporting a closed fist with thumb up, lifting gently upward.',
    handType: 'Two Hands',
    category: 'Action'
  },
  {
    raw_label: 'Please',
    display_name: 'Please',
    description: 'Open flat hand rubbing gently in circular motion over the chest.',
    handType: 'Single Hand',
    category: 'Common'
  },
  {
    raw_label: 'Thank you',
    display_name: 'Thank you',
    description: 'Fingertips touching lips/chin and moving outward toward recipient.',
    handType: 'Single Hand',
    category: 'Common'
  },
  {
    raw_label: 'id',
    display_name: 'ID',
    description: 'Two fingers tapping or showing rectangular card gesture.',
    handType: 'Single Hand',
    category: 'Identity'
  },
  {
    raw_label: 'license',
    display_name: 'License',
    description: 'Two hands forming an outline or driver identity badge in front of chest.',
    handType: 'Two Hands',
    category: 'Identity'
  },
  {
    raw_label: 'passport',
    display_name: 'Passport',
    description: 'Hand stamping into an open palm representing a passport booklet.',
    handType: 'Two Hands',
    category: 'Identity'
  },
  {
    raw_label: 'wait',
    display_name: 'Wait',
    description: 'Both open hands held out with palms facing forward in a gentle pause posture.',
    handType: 'Two Hands',
    category: 'Action'
  }
];

export const DictionaryView: React.FC = () => {
  return (
    <div className="w-full flex flex-col gap-6 max-w-5xl mx-auto">
      <div>
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-blue-400" />
          Sign Language Dictionary
        </h2>
        <p className="text-xs text-zinc-400 mt-0.5">
          Standardized gestures recognized by the LSTM model and anatomical classifier. English-only display names.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {DICTIONARY_ENTRIES.map((entry) => (
          <div
            key={entry.raw_label}
            className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4 flex flex-col justify-between hover:border-zinc-700/80 transition-all"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-base font-bold text-white tracking-wide">
                    {entry.display_name}
                  </span>
                  <span className="text-[10px] font-mono text-zinc-500 bg-zinc-800/60 px-1.5 py-0.5 rounded border border-zinc-700/40">
                    raw: &quot;{entry.raw_label}&quot;
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded-full border border-zinc-700/50">
                    {entry.handType}
                  </span>
                  <button
                    onClick={() => speechService.speak(entry.display_name)}
                    className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
                    title={`Pronounce ${entry.display_name}`}
                  >
                    <Volume2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <p className="text-xs text-zinc-300 leading-relaxed mb-3">
                {entry.description}
              </p>
            </div>

            {entry.rule ? (
              <div className="flex items-center gap-1.5 text-[11px] text-amber-400/90 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded-lg">
                <ShieldCheck className="w-3 h-3 shrink-0" />
                <span>Constraint: {entry.rule}</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                <Zap className="w-3 h-3 text-emerald-400" />
                <span>Detection: 0.75 threshold &bull; 0.35s stable &bull; 1.8s cooldown</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
