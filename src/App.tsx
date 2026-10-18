import React, { useState, useEffect } from 'react';
import {
  Hand,
  Volume2,
  Video,
  Database,
  Terminal,
  RotateCcw,
  Sparkles,
  MessageSquare,
  BookOpen,
  Copy,
  Check,
  PowerOff,
  Play,
  Share2,
  ShieldCheck,
  CheckCircle2,
  SlidersHorizontal,
  ChevronRight,
  ExternalLink
} from 'lucide-react';
import { CameraView, SIMULATABLE_GESTURES } from './components/CameraView';
import { CollectMode } from './components/CollectMode';
import { DatasetViewer } from './components/DatasetViewer';
import { PythonGuide } from './components/PythonGuide';
import { CodeAuditView } from './components/CodeAuditView';
import { GestureStat, GestureSequence } from './types';
import { audioService } from './utils/audioService';

// Default starter gestures matching the repository
const DEFAULT_GESTURES: GestureStat[] = [
  { label: 'hello', count: 25, key: 'h', description: 'Main ouverte levée avec léger mouvement' },
  { label: 'eat', count: 20, key: 't', description: 'Doigts regroupés en corolle portés vers la bouche' },
  { label: 'love', count: 22, key: 'l', description: 'Pouce, index et auriculaire tendus (signe ILY)' },
  { label: 'sleep', count: 18, key: 's', description: 'Main à plat inclinée posée contre la joue' },
  { label: 'hate', count: 15, key: 'm', description: 'Pouce dirigé nettement vers le bas' },
  { label: 'peace', count: 30, key: 'p', description: 'Index et majeur tendus formant un V' },
  { label: 'not', count: 16, key: 'n', description: 'Pouce tendu vers l\'extérieur (geste de refus)' },
  { label: 'I', count: 24, key: 'i', description: 'Seul le petit doigt (auriculaire) est levé' },
  { label: 'Shawarma', count: 12, key: '1', description: 'Deux mains formant un cylindre de face' },
  { label: 'tacos', count: 14, key: '2', description: 'Deux mains courbées superposées en coquille' },
];

// NLP Grammar reconstructor: translates isolated sign tokens into fluent sentences
function reconstructFluentSentence(words: string[]): { french: string; english: string } {
  if (words.length === 0) return { french: '', english: '' };

  const lower = words.map(w => w.toLowerCase());
  const hasHello = lower.includes('hello');
  const hasI = lower.includes('i');
  const hasLove = lower.includes('love');
  const hasEat = lower.includes('eat');
  const hasTacos = lower.includes('tacos');
  const hasShawarma = lower.includes('shawarma');
  const hasSleep = lower.includes('sleep');
  const hasPeace = lower.includes('peace');
  const hasNot = lower.includes('not');
  const hasHate = lower.includes('hate');

  let fr = '';
  let en = '';

  if (hasPeace && hasLove) {
    fr = 'Paix et amour à tous !';
    en = 'Peace and love to everyone!';
  } else if (hasI && hasLove && hasTacos) {
    fr = "J'adore les tacos !";
    en = 'I love tacos!';
  } else if (hasI && hasLove && hasShawarma) {
    fr = "J'adore les chawarmas !";
    en = 'I love shawarmas!';
  } else if (hasI && hasLove) {
    fr = "Je t'aime beaucoup.";
    en = 'I love you very much.';
  } else if (hasI && hasEat && hasTacos) {
    fr = 'Je mange des tacos délicieux.';
    en = 'I am eating delicious tacos.';
  } else if (hasI && hasEat && hasShawarma) {
    fr = 'Je mange un bon chawarma.';
    en = 'I am eating a good shawarma.';
  } else if (hasI && hasEat) {
    fr = 'Je suis en train de manger.';
    en = 'I am currently eating.';
  } else if (hasI && hasSleep) {
    fr = 'Je suis fatigué, je vais dormir.';
    en = 'I am tired, I am going to sleep.';
  } else if (hasHate && hasNot) {
    fr = 'Je ne déteste pas du tout.';
    en = 'I do not hate at all.';
  } else {
    const frMap: Record<string, string> = {
      hello: 'bonjour',
      eat: 'manger',
      love: 'aimer',
      sleep: 'dormir',
      hate: 'détester',
      peace: 'paix',
      not: 'non',
      i: 'je',
      shawarma: 'chawarma',
      tacos: 'tacos'
    };
    const translatedFr = lower.map(w => frMap[w] || w).join(' ');
    fr = translatedFr.charAt(0).toUpperCase() + translatedFr.slice(1) + '.';
    en = words.join(' ') + '.';
  }

  if (hasHello && !fr.toLowerCase().startsWith('bonjour')) {
    fr = 'Bonjour ! ' + fr;
    en = 'Hello! ' + en;
  }

  return { french: fr, english: en };
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'live' | 'dictionary' | 'collect' | 'dataset' | 'python' | 'audit'>('audit');
  const [gestures, setGestures] = useState<GestureStat[]>(() => {
    const saved = localStorage.getItem('sign_gestures');
    return saved ? JSON.parse(saved) : DEFAULT_GESTURES;
  });

  const [sequences, setSequences] = useState<GestureSequence[]>(() => {
    const saved = localStorage.getItem('sign_sequences');
    return saved ? JSON.parse(saved) : [];
  });

  // Recording State
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordingLabel, setRecordingLabel] = useState<string>('');
  const [recordedFrames, setRecordedFrames] = useState<number[][]>([]);
  const [historyWords, setHistoryWords] = useState<string[]>([]);
  const [voiceEnabled, setVoiceEnabled] = useState<boolean>(true);
  const [isCameraActiveOnWeb, setIsCameraActiveOnWeb] = useState<boolean>(false);
  const [copiedSentence, setCopiedSentence] = useState<boolean>(false);
  const [selectedGestureToTest, setSelectedGestureToTest] = useState<string | null>(null);
  const [fluentSentence, setFluentSentence] = useState<{ french: string; english: string } | null>(null);

  const handleReconstructSentence = () => {
    if (historyWords.length === 0) return;
    const res = reconstructFluentSentence(historyWords);
    setFluentSentence(res);
    audioService.speakSentence(res.french, 'fr');
  };

  // Sync to local storage
  useEffect(() => {
    localStorage.setItem('sign_gestures', JSON.stringify(gestures));
  }, [gestures]);

  useEffect(() => {
    localStorage.setItem('sign_sequences', JSON.stringify(sequences));
  }, [sequences]);

  // Handle frame capture when in recording mode
  const handleFrameFeatures = (features: number[]) => {
    if (!isRecording || !recordingLabel) return;

    setRecordedFrames((prev) => {
      const next = [...prev, features];
      if (next.length >= 20) {
        const newSeq: GestureSequence = {
          id: `${recordingLabel}-${Date.now()}`,
          label: recordingLabel,
          timestamp: Date.now(),
          frames: next.slice(0, 20),
        };

        setSequences((curr) => [...curr, newSeq]);

        // Increment count
        setGestures((curr) =>
          curr.map((g) => (g.label === recordingLabel ? { ...g, count: g.count + 1 } : g))
        );

        setIsRecording(false);
        setRecordingLabel('');
        return [];
      }
      return next;
    });
  };

  const handleStartRecord = (label: string) => {
    setRecordingLabel(label);
    setRecordedFrames([]);
    setIsRecording(true);
  };

  const handleGestureDetected = (label: string) => {
    setHistoryWords((prev) => {
      if (prev.length > 0 && prev[prev.length - 1] === label) {
        return prev;
      }
      const updated = [...prev, label];
      return updated.slice(-12); // keep last 12 words
    });
  };

  const handleAddGesture = (name: string, key?: string) => {
    if (gestures.some((g) => g.label === name)) return;
    setGestures((prev) => [...prev, { label: name, count: 0, key }]);
  };

  const handleDeleteGesture = (label: string) => {
    setGestures((prev) => prev.filter((g) => g.label !== label));
    setSequences((prev) => prev.filter((s) => s.label !== label));
  };

  const handleClearAll = () => {
    setGestures(DEFAULT_GESTURES.map((g) => ({ ...g, count: 0 })));
    setSequences([]);
    setHistoryWords([]);
  };

  const handleImportDataset = (imported: GestureSequence[]) => {
    setSequences(imported);
    const countsMap: Record<string, number> = {};
    imported.forEach((s) => {
      countsMap[s.label] = (countsMap[s.label] || 0) + 1;
    });

    setGestures((prev) => {
      return prev.map((g) => ({
        ...g,
        count: countsMap[g.label] || 0,
      }));
    });
  };

  // Speak whole sentence
  const speakWholeSentence = () => {
    if (historyWords.length === 0) return;
    const frMap: Record<string, string> = {
      hello: 'Bonjour',
      peace: 'Paix',
      love: 'Amour',
      eat: 'Manger',
      sleep: 'Dormir',
      I: 'Moi',
      not: 'Non',
      hate: 'Déteste',
      Shawarma: 'Chawarma',
      tacos: 'Tacos'
    };
    const sentenceText = historyWords.map(w => frMap[w.toLowerCase()] || w).join(' ');
    audioService.speakSentence(sentenceText, 'fr');
  };

  // Copy sentence to clipboard
  const copySentence = () => {
    if (historyWords.length === 0) return;
    navigator.clipboard.writeText(historyWords.join(' '));
    setCopiedSentence(true);
    setTimeout(() => setCopiedSentence(false), 2000);
  };

  // Test gesture in simulator
  const handleTestGesture = (gestureId: string) => {
    setSelectedGestureToTest(gestureId);
    audioService.unlockAudio();
    audioService.speak(gestureId, { lang: 'fr', force: true });
    setActiveTab('live');
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans selection:bg-emerald-500 selection:text-black">
      {/* Top Navigation Bar */}
      <header className="border-b border-zinc-800/80 bg-zinc-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 p-0.5 shadow-lg shadow-emerald-500/10">
              <div className="w-full h-full bg-zinc-950 rounded-[10px] flex items-center justify-center text-emerald-400">
                <Hand className="w-5 h-5" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-extrabold text-white text-base tracking-tight">
                  Sign Language AI Studio
                </h1>
                <span className="hidden sm:inline-block px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 uppercase tracking-wider">
                  Pro Edition
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 hidden sm:block">
                Traduction de la langue des signes • MediaPipe 3D & Réseau LSTM
              </p>
            </div>
          </div>

          {/* Center / Right: Hardware State Indicator */}
          <div className="hidden md:flex items-center gap-2">
            {isCameraActiveOnWeb ? (
              <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/30 px-3 py-1.5 rounded-xl text-xs text-amber-300">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
                <span className="font-medium">Webcam occupée (AI Studio)</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 px-3 py-1.5 rounded-xl text-xs text-emerald-300">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="font-medium">Caméra libérée pour Python</span>
              </div>
            )}
          </div>

          {/* Tab Switcher */}
          <nav className="flex items-center gap-1 bg-zinc-950/80 p-1 rounded-xl border border-zinc-800">
            <button
              onClick={() => setActiveTab('audit')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                activeTab === 'audit'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-300" />
              <span>Audit & Code</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            </button>
            <button
              onClick={() => setActiveTab('live')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                activeTab === 'live'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              Direct
            </button>
            <button
              onClick={() => setActiveTab('dictionary')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                activeTab === 'dictionary'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              Dictionnaire (10)
            </button>
            <button
              onClick={() => setActiveTab('collect')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                activeTab === 'collect'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Video className="w-3.5 h-3.5" />
              Collecte
            </button>
            <button
              onClick={() => setActiveTab('dataset')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                activeTab === 'dataset'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Database className="w-3.5 h-3.5" />
              Données
            </button>
            <button
              onClick={() => setActiveTab('python')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                activeTab === 'python'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              Python (Windows)
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Webcam & Hands Detection (7 cols) */}
        <section className="lg:col-span-7 flex flex-col gap-4">
          <CameraView
            onFrameFeatures={handleFrameFeatures}
            onGestureDetected={handleGestureDetected}
            isRecording={isRecording}
            recordingLabel={recordingLabel}
            recordingProgress={recordedFrames.length / 20}
            voiceEnabled={voiceEnabled}
            onCameraStateChange={setIsCameraActiveOnWeb}
            requestedGesture={selectedGestureToTest}
          />

          {/* Professional Sentence Builder & Live Transcription Strip */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 shadow-xl">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-zinc-300">
                  Constructeur de Phrases & Transcription
                </span>
                <span className="text-[10px] bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded-full font-mono">
                  {historyWords.length} mot(s)
                </span>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-2">
                {historyWords.length > 0 && (
                  <>
                    <button
                      onClick={handleReconstructSentence}
                      title="Restructurer les mots en phrase naturelle fluide (Français & Anglais)"
                      className="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      Phrase naturelle
                    </button>

                    <button
                      onClick={speakWholeSentence}
                      title="Lire toute la phrase avec la synthèse vocale"
                      className="px-2.5 py-1 rounded-lg bg-emerald-600/90 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
                    >
                      <Volume2 className="w-3.5 h-3.5" />
                      Écouter
                    </button>

                    <button
                      onClick={copySentence}
                      title="Copier le texte"
                      className="px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                    >
                      {copiedSentence ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      {copiedSentence ? 'Copié !' : 'Copier'}
                    </button>

                    <button
                      onClick={() => {
                        setHistoryWords((prev) => prev.slice(0, -1));
                        setFluentSentence(null);
                      }}
                      title="Effacer le dernier mot"
                      className="px-2 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white text-xs transition-colors"
                    >
                      ⌫
                    </button>

                    <button
                      onClick={() => {
                        setHistoryWords([]);
                        setFluentSentence(null);
                      }}
                      title="Réinitialiser la phrase"
                      className="px-2 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white text-xs transition-colors"
                    >
                      <RotateCcw className="w-3 h-3" />
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Sentence Words Flow */}
            <div className="min-h-14 flex flex-wrap items-center gap-2 bg-zinc-950/80 border border-zinc-800/80 p-3.5 rounded-xl">
              {historyWords.length === 0 ? (
                <span className="text-xs text-zinc-500 italic">
                  Les signes reconnus (webcam ou simulateur) formeront une phrase ici et seront prononcés à voix haute...
                </span>
              ) : (
                historyWords.map((word, idx) => (
                  <span
                    key={idx}
                    className="px-3 py-1.5 rounded-xl bg-gradient-to-r from-emerald-500/10 to-teal-500/10 border border-emerald-500/30 text-emerald-300 font-bold text-sm shadow-sm flex items-center gap-1.5 animate-fade-in"
                  >
                    <span>{word}</span>
                  </span>
                ))
              )}
            </div>

            {/* NLP Reconstructed Fluent Sentence Box */}
            {fluentSentence && (
              <div className="mt-3 p-3.5 rounded-xl bg-indigo-950/40 border border-indigo-500/30 flex flex-col gap-1.5 text-xs">
                <div className="flex items-center justify-between text-indigo-300 font-bold">
                  <span className="flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                    Traduction & Structure de Phrase Naturelle (IA) :
                  </span>
                  <button
                    onClick={() => {
                      if ('speechSynthesis' in window) {
                        window.speechSynthesis.cancel();
                        const u = new SpeechSynthesisUtterance(fluentSentence.french);
                        u.lang = 'fr-FR';
                        window.speechSynthesis.speak(u);
                      }
                    }}
                    className="text-[11px] text-indigo-300 hover:text-white flex items-center gap-1 font-semibold transition-colors"
                  >
                    <Volume2 className="w-3.5 h-3.5" /> Rejouer la voix
                  </button>
                </div>
                <div className="text-sm font-bold text-white tracking-wide">
                  🇫🇷 {fluentSentence.french}
                </div>
                <div className="text-xs text-zinc-400">
                  🇬🇧 {fluentSentence.english}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Right Column: Dynamic Tabs (5 cols) */}
        <section className="lg:col-span-5 h-full">
          {/* TAB 1: LIVE RECOGNITION SUMMARY */}
          {activeTab === 'live' && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 shadow-xl flex flex-col gap-4">
              <div className="pb-3 border-b border-zinc-800 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-emerald-400" />
                    Reconnaissance Directe
                  </h2>
                  <p className="text-xs text-zinc-400 mt-1">
                    Détection instantanée par vision artificielle et classification neuronale.
                  </p>
                </div>
              </div>

              {/* Hardware Quick Summary Card */}
              <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 flex flex-col gap-2">
                <span className="text-xs font-bold text-zinc-300 uppercase tracking-wide">
                  État du Matériel Vidéo
                </span>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Statut Webcam physique :</span>
                  <span className={`font-semibold ${isCameraActiveOnWeb ? 'text-amber-400' : 'text-emerald-400'}`}>
                    {isCameraActiveOnWeb ? 'Réservée par cette page' : 'Libérée (Prête pour Python)'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Modèle Réseau de Neurones :</span>
                  <span className="font-mono text-zinc-300">LSTM (64, 128, 64)</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">Extraction des Repères :</span>
                  <span className="font-mono text-zinc-300">21 points 3D (126 features)</span>
                </div>
              </div>

              {/* Quick Gesture Catalog with test click */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block">
                    Vocabulaire Détecté (10 signes) :
                  </span>
                  <button
                    onClick={() => setActiveTab('dictionary')}
                    className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-medium"
                  >
                    Voir le guide complet <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2 max-h-[300px] overflow-y-auto pr-1">
                  {gestures.map((g) => (
                    <div
                      key={g.label}
                      onClick={() => handleTestGesture(g.label)}
                      className="bg-zinc-950/80 hover:bg-zinc-800/60 border border-zinc-800/80 hover:border-emerald-500/40 rounded-xl p-3 flex flex-col justify-between cursor-pointer transition-all group"
                      title="Cliquer pour simuler ce geste"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-white capitalize text-sm group-hover:text-emerald-400 transition-colors">
                          {g.label}
                        </span>
                        {g.key && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                            '{g.key}'
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-zinc-400 mt-1 line-clamp-1 leading-snug">
                        {g.description || `${g.count} captures`}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Speech toggle */}
              <div className="pt-3 border-t border-zinc-800 flex items-center justify-between">
                <span className="text-xs text-zinc-400">Synthèse vocale automatique</span>
                <button
                  onClick={() => setVoiceEnabled(!voiceEnabled)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors ${
                    voiceEnabled
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : 'bg-zinc-800 text-zinc-400'
                  }`}
                >
                  <Volume2 className="w-3.5 h-3.5" />
                  {voiceEnabled ? 'Voix Activée' : 'Voix Désactivée'}
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: VISUAL GESTURE DICTIONARY */}
          {activeTab === 'dictionary' && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 shadow-xl flex flex-col gap-4 overflow-y-auto max-h-[640px]">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-emerald-400" />
                  Dictionnaire Visuel des Signes (10 Gestes)
                </h2>
                <p className="text-xs text-zinc-400 mt-1">
                  Description anatomique de chaque geste et comment le reproduire devant la caméra.
                </p>
              </div>

              <div className="space-y-3">
                {SIMULATABLE_GESTURES.map((item) => (
                  <div
                    key={item.id}
                    className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-3.5 flex items-center justify-between gap-3 hover:border-zinc-700 transition-all"
                  >
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-xl shrink-0">
                        {item.icon}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-bold text-white text-sm capitalize">{item.label}</h3>
                          <span className="text-[10px] font-mono bg-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded">
                            id: {item.id}
                          </span>
                        </div>
                        <p className="text-xs text-zinc-400 mt-0.5">{item.desc}</p>
                      </div>
                    </div>

                    <button
                      onClick={() => handleTestGesture(item.id)}
                      className="shrink-0 px-2.5 py-1.5 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/40 rounded-lg text-xs font-semibold flex items-center gap-1 transition-all"
                    >
                      <Play className="w-3 h-3" />
                      Tester
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: COLLECT MODE */}
          {activeTab === 'collect' && (
            <CollectMode
              gestures={gestures}
              onStartRecord={handleStartRecord}
              isRecording={isRecording}
              recordingLabel={recordingLabel}
              onAddGesture={handleAddGesture}
            />
          )}

          {/* TAB 4: DATASET EXPLORER */}
          {activeTab === 'dataset' && (
            <DatasetViewer
              gestures={gestures}
              sequences={sequences}
              onDeleteGesture={handleDeleteGesture}
              onClearAll={handleClearAll}
              onImportDataset={handleImportDataset}
            />
          )}

          {/* TAB 5: PYTHON LOCAL RUN GUIDE */}
          {activeTab === 'python' && <PythonGuide />}

          {/* TAB 6: CODE AUDIT & OPTIMIZATION REPORT */}
          {activeTab === 'audit' && (
            <CodeAuditView onNavigateToLive={() => setActiveTab('live')} />
          )}
        </section>
      </main>
    </div>
  );
}
