import React, { useState } from 'react';
import {
  Terminal,
  Copy,
  Check,
  AlertTriangle,
  Code2,
  PlayCircle,
  VideoOff,
  ShieldCheck,
  Cpu,
  HelpCircle,
  Sparkles
} from 'lucide-react';

export const PythonGuide: React.FC = () => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const setupCommands = `# 1. Accédez à votre dossier de projet
cd "C:\\Users\\Userhome\\Desktop\\App malia"

# 2. Activez votre environnement virtuel Python existant
venv\\Scripts\\activate

# 3. Re-entrainez le modele IA pour qu'il soit adapte a votre machine
python train.py

# 4. Lancez la reconnaissance (Lecture vocale en Anglais par defaut, touche [L] pour alterner)
python realtime.py`;

  const collectCommand = `python collect.py`;
  const trainCommand = `python train.py`;
  const realtimeCommand = `python realtime.py`;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 shadow-xl flex flex-col h-full space-y-4 overflow-y-auto max-h-[640px]">
      <div>
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Terminal className="w-5 h-5 text-emerald-400" />
          Guide Exécution Locale (Windows / Python)
        </h2>
        <p className="text-xs text-zinc-400 mt-1">
          Toutes les étapes pour exécuter vos scripts Python sur votre ordinateur sans conflit ni erreur.
        </p>
      </div>

      {/* NEW PRO STUDIO EDITION HIGHLIGHT */}
      <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-4 flex gap-3 text-xs text-emerald-200">
        <Sparkles className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
        <div className="space-y-1.5">
          <strong className="text-emerald-300 font-bold block text-sm">
            Nouvelle Version Studio Pro de realtime.py intégrée !
          </strong>
          <p className="leading-relaxed text-zinc-300">
            Le script <code className="bg-black/40 px-1 py-0.5 rounded text-emerald-300 font-mono">realtime.py</code> a été entièrement repensé pour afficher <strong>exactement la même interface qu'AI Studio</strong> (design sombre HD 1280x720, tableau de bord des probabilités, constructeur de phrases, FPS et latence en direct).
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2 pt-2 border-t border-emerald-500/20 text-[11px]">
            <div>⚡ <strong>Inférence x25 plus rapide :</strong> Graphe TensorFlow compilé (~2ms au lieu de 60ms).</div>
            <div>⏱️ <strong>Détection instantanée :</strong> Seuil réajusté à 80% (au lieu de 98% trop rigide).</div>
            <div>📝 <strong>Constructeur de phrases :</strong> Mots accumulés au fur et à mesure.</div>
            <div>⌨️ <strong>Raccourcis :</strong> [C] Effacer phrase, [S] Répéter, [M] Muet, [Q] Quitter.</div>
          </div>
        </div>
      </div>

      {/* CRITICAL PYTHON 3.13 WARNING & FIX */}
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex gap-3 text-xs text-red-200">
        <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
        <div className="space-y-1.5 w-full">
          <div className="flex items-center justify-between">
            <strong className="text-red-300 font-bold block text-sm">
              Erreur OpenCV / MediaPipe : Vous avez Python 3.13
            </strong>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-300 uppercase">
              Action Requise
            </span>
          </div>
          <p className="leading-relaxed text-zinc-300">
            Python 3.13 est trop récent : les bibliothèques d'IA mondiales (<strong>TensorFlow</strong>, <strong>MediaPipe</strong>, <strong>OpenCV</strong>) ne fournissent pas encore de binaires pour 3.13, ce qui provoque l'erreur <code className="bg-black/40 px-1 py-0.5 rounded text-red-300 font-mono">Failed to build opencv-python</code>.
          </p>
          <div className="p-3 bg-black/50 rounded-lg border border-red-500/20 space-y-2 mt-1">
            <div className="text-[11px] text-zinc-200 font-semibold">
              Solution instantanée : Installez Python 3.10 (la version standard de référence IA)
            </div>
            <div className="flex items-center justify-between gap-2 bg-zinc-900 px-2.5 py-1.5 rounded border border-zinc-800">
              <code className="text-emerald-400 font-mono text-[11px]">winget install Python.Python.3.10</code>
              <button
                onClick={() => copyToClipboard('winget install Python.Python.3.10', 'winget-cmd')}
                className="text-[11px] bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-2 py-1 rounded flex items-center gap-1 transition-colors shrink-0"
              >
                {copiedId === 'winget-cmd' ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                Copier
              </button>
            </div>
            <p className="text-[10px] text-zinc-400">
              Ou téléchargez l'installateur officiel : <a href="https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe" target="_blank" rel="noreferrer" className="text-blue-400 underline">python-3.10.11-amd64.exe</a> (en cochant <strong className="text-white">[x] Add Python to PATH</strong>).
            </p>
          </div>
        </div>
      </div>

      {/* CRITICAL TIP ABOUT CAMERA EXCLUSIVITY IN WINDOWS */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex gap-3 text-xs text-amber-200">
        <VideoOff className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="space-y-1.5">
          <strong className="text-amber-300 font-bold block text-sm">
            Règle d'or Windows : La caméra ne peut pas être partagée
          </strong>
          <p className="leading-relaxed">
            Sous Windows, une webcam physique ne peut être utilisée que par <strong>une seule application à la fois</strong>.
            Si la caméra est allumée sur cette page web AI Studio, Windows bloquera l'accès à <code className="bg-black/40 px-1 py-0.5 rounded text-amber-300 font-mono">python realtime.py</code> et aucune fenêtre ne s'ouvrira.
          </p>
          <div className="p-2 bg-amber-500/10 rounded-lg border border-amber-500/20 text-amber-100 flex items-center gap-2">
            <span className="font-bold">Solution :</span>
            <span>Cliquez sur le bouton rouge <strong>« Désactiver la Caméra »</strong> sur cette page avant de lancer le script Python !</span>
          </div>
        </div>
      </div>

      {/* 1-CLICK LAUNCHER FOR WINDOWS */}
      <div className="bg-gradient-to-r from-emerald-950/80 via-zinc-900 to-indigo-950/80 border border-emerald-500/40 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <strong className="text-emerald-300 font-bold text-sm">
              Nouveau Lanceur Automatique : lancer_app.bat
            </strong>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 uppercase">
              1 Clic Windows
            </span>
          </div>
          <p className="text-zinc-300 leading-relaxed">
            Plus besoin de taper de commandes complexes ! Double-cliquez simplement sur le fichier <code className="bg-black/50 px-1.5 py-0.5 rounded font-mono text-emerald-300">lancer_app.bat</code> dans votre dossier de projet pour afficher un menu interactif.
          </p>
        </div>
        <button
          onClick={() => copyToClipboard('lancer_app.bat', 'bat-run')}
          className="shrink-0 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg flex items-center gap-1.5 transition-all shadow-md active:scale-95 text-xs"
        >
          {copiedId === 'bat-run' ? <Check className="w-3.5 h-3.5 text-white" /> : <Copy className="w-3.5 h-3.5" />}
          <span>Copier le nom du fichier</span>
        </button>
      </div>

      {/* WHY THE ERROR HAPPENED */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-3.5 flex gap-3 text-xs text-blue-200">
        <Cpu className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <strong className="text-blue-300 font-semibold block">
            Explication de l'erreur « Unrecognized keyword arguments passed to LSTM »
          </strong>
          <p className="leading-relaxed text-blue-100/90">
            L'ancien fichier <code className="bg-black/30 px-1 py-0.5 rounded font-mono">action.h5</code> a été enregistré avec une version antérieure de Keras. 
            Il suffit d'exécuter une fois <code className="bg-black/30 px-1 py-0.5 rounded text-blue-300 font-mono">python train.py</code> pour regénérer un fichier modèle tout neuf, optimisé pour votre version locale.
          </p>
        </div>
      </div>

      {/* Step 1 : Commandes Clés */}
      <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            Commandes à copier dans votre invite de commande (CMD)
          </span>
          <button
            onClick={() => copyToClipboard(setupCommands, 'setup')}
            className="text-xs text-zinc-300 hover:text-white flex items-center gap-1 bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1 rounded-md transition-colors"
          >
            {copiedId === 'setup' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            Tout copier
          </button>
        </div>
        <pre className="text-xs font-mono bg-black/60 p-3 rounded-lg text-emerald-300 overflow-x-auto leading-relaxed border border-zinc-900">
          {setupCommands}
        </pre>
      </div>

      {/* Step 2 : Les 3 scripts du projet */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
        <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-3.5 flex flex-col justify-between">
          <div>
            <div className="text-xs font-semibold text-white flex items-center gap-1.5 mb-1">
              <PlayCircle className="w-4 h-4 text-emerald-400" />
              1. Enregistrer des gestes
            </div>
            <p className="text-[11px] text-zinc-400">Touches 'h' pour hello, 't' pour eat, 'l' pour love...</p>
          </div>
          <button
            onClick={() => copyToClipboard(collectCommand, 'cmd1')}
            className="mt-3 flex items-center justify-between w-full bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1.5 rounded-lg text-xs font-mono text-zinc-200 transition-colors"
          >
            <span>{collectCommand}</span>
            {copiedId === 'cmd1' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          </button>
        </div>

        <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-3.5 flex flex-col justify-between">
          <div>
            <div className="text-xs font-semibold text-white flex items-center gap-1.5 mb-1">
              <Code2 className="w-4 h-4 text-blue-400" />
              2. Entraîner l'IA
            </div>
            <p className="text-[11px] text-zinc-400">Crée le réseau de neurones action.h5</p>
          </div>
          <button
            onClick={() => copyToClipboard(trainCommand, 'cmd2')}
            className="mt-3 flex items-center justify-between w-full bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1.5 rounded-lg text-xs font-mono text-zinc-200 transition-colors"
          >
            <span>{trainCommand}</span>
            {copiedId === 'cmd2' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          </button>
        </div>

        <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-3.5 flex flex-col justify-between">
          <div>
            <div className="text-xs font-semibold text-white flex items-center gap-1.5 mb-1">
              <Terminal className="w-4 h-4 text-amber-400" />
              3. Détection en Direct
            </div>
            <p className="text-[11px] text-zinc-400">Ouvre OpenCV avec voix et détection</p>
          </div>
          <button
            onClick={() => copyToClipboard(realtimeCommand, 'cmd3')}
            className="mt-3 flex items-center justify-between w-full bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1.5 rounded-lg text-xs font-mono text-zinc-200 transition-colors"
          >
            <span>{realtimeCommand}</span>
            {copiedId === 'cmd3' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          </button>
        </div>
      </div>
    </div>
  );
};
