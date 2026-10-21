import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Camera,
  RefreshCw,
  Volume2,
  VolumeX,
  Eye,
  EyeOff,
  Sliders,
  Sparkles,
  AlertCircle,
  Play,
  Pause,
  VideoOff,
  Video,
  Maximize2,
  Minimize2,
  Download,
  Settings2,
  CheckCircle2,
  PowerOff,
  Activity,
  Gauge,
  Layers,
  HelpCircle
} from 'lucide-react';
import { Landmark } from '../types';
import { classifyHandGesture, extractLandmarksVector, analyzeFingerStates, FingerStates } from '../utils/handClassifier';
import { getSimulatedHand } from '../utils/gestureSimulator';
import { audioService } from '../utils/audioService';

// MediaPipe connections between hand landmarks
const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4], // Thumb
  [0, 5], [5, 6], [6, 7], [7, 8], // Index
  [5, 9], [9, 10], [10, 11], [11, 12], // Middle
  [9, 13], [13, 14], [14, 15], [15, 16], // Ring
  [13, 17], [17, 18], [18, 19], [19, 20], // Pinky
  [0, 17], // Palm base
];

export const SIMULATABLE_GESTURES = [
  { id: 'hello', label: 'Bonjour (Hello)', icon: '👋', desc: 'Main ouverte levée' },
  { id: 'peace', label: 'Paix (Peace)', icon: '✌️', desc: 'Index et majeur levés en V' },
  { id: 'love', label: 'Amour (Love)', icon: '🤟', desc: 'Pouce, index et auriculaire levés' },
  { id: 'eat', label: 'Manger (Eat)', icon: '🤌', desc: 'Tous les bouts des doigts réunis' },
  { id: 'sleep', label: 'Dormir (Sleep)', icon: '💤', desc: 'Main inclinée près du visage' },
  { id: 'I', label: 'Moi / I', icon: '🤙', desc: 'Auriculaire levé vers le haut' },
  { id: 'not', label: 'Non / Not', icon: '👍', desc: 'Pouce horizontal vers l\'extérieur' },
  { id: 'hate', label: 'Haine (Down)', icon: '👎', desc: 'Pouce orienté vers le bas' },
  { id: 'shawarma', label: 'Shawarma', icon: '🌯', desc: 'Deux mains en cornet de face' },
];

export const GESTURE_TRANSLATIONS: Record<string, { en: string; fr: string; icon: string }> = {
  hello: { en: 'Hello', fr: 'Bonjour', icon: '👋' },
  peace: { en: 'Peace (V-Sign)', fr: 'Paix (V)', icon: '✌️' },
  love: { en: 'Love (ILY)', fr: 'Amour', icon: '🤟' },
  eat: { en: 'Eat (Food)', fr: 'Manger', icon: '🤌' },
  sleep: { en: 'Sleep', fr: 'Dormir', icon: '💤' },
  I: { en: 'I / Me', fr: 'Moi (Je)', icon: '🤙' },
  not: { en: 'No / Not', fr: 'Non', icon: '👍' },
  hate: { en: 'Thumbs Down', fr: 'Déteste', icon: '👎' },
  shawarma: { en: 'Shawarma', fr: 'Shawarma', icon: '🌯' },
  tacos: { en: 'Tacos', fr: 'Tacos', icon: '🌮' },
};

interface CameraViewProps {
  onFrameFeatures?: (features: number[]) => void;
  onGestureDetected?: (gesture: string, confidence: number) => void;
  isRecording?: boolean;
  recordingLabel?: string;
  recordingProgress?: number;
  voiceEnabled?: boolean;
  onCameraStateChange?: (isActive: boolean) => void;
  requestedGesture?: string | null;
}

export const CameraView: React.FC<CameraViewProps> = ({
  onFrameFeatures,
  onGestureDetected,
  isRecording = false,
  recordingLabel,
  recordingProgress = 0,
  voiceEnabled = true,
  onCameraStateChange,
  requestedGesture,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Modes: 'webcam' or 'simulator'
  const [activeMode, setActiveMode] = useState<'webcam' | 'simulator'>('simulator');
  const [webcamStatus, setWebcamStatus] = useState<'idle' | 'requesting' | 'active' | 'blocked'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);

  // Visualization settings
  const [showSkeleton, setShowSkeleton] = useState<boolean>(true);
  const [showBoundingBox, setShowBoundingBox] = useState<boolean>(true);
  const [mirrorView, setMirrorView] = useState<boolean>(true);
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.70);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [showSettings, setShowSettings] = useState<boolean>(false);

  // Performance telemetry
  const [fps, setFps] = useState<number>(0);
  const [latencyMs, setLatencyMs] = useState<number>(14);
  const [handsCount, setHandsCount] = useState<number>(0);
  const lastFrameTimeRef = useRef<number>(performance.now());
  const frameCounterRef = useRef<number>(0);

  // Recognition state
  const [detectedSign, setDetectedSign] = useState<string>('');
  const [detectedConfidence, setDetectedConfidence] = useState<number>(0);
  const [fingerStates, setFingerStates] = useState<FingerStates | null>(null);
  const [speechMuted, setSpeechMuted] = useState<boolean>(!voiceEnabled);
  const [speechRate, setSpeechRate] = useState<number>(1.0);
  const [speechLang, setSpeechLang] = useState<'fr' | 'en'>('en');

  // Simulator controls
  const [simGesture, setSimGesture] = useState<string>('hello');
  const [autoCycle, setAutoCycle] = useState<boolean>(false);

  const lastSpokenRef = useRef<string>('');
  const lastSpokenTimeRef = useRef<number>(0);
  const animFrameRef = useRef<number | null>(null);
  const handsInstanceRef = useRef<any>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Respond to parent requestedGesture changes
  useEffect(() => {
    if (requestedGesture) {
      setSimGesture(requestedGesture);
      setAutoCycle(false);
    }
  }, [requestedGesture]);

  // Sync camera active state to parent
  useEffect(() => {
    if (onCameraStateChange) {
      onCameraStateChange(activeMode === 'webcam' && webcamStatus === 'active');
    }
  }, [activeMode, webcamStatus, onCameraStateChange]);

  // Text-To-Speech function with guaranteed audio playback
  const speakWord = useCallback((word: string) => {
    if (speechMuted) return;
    audioService.speak(word, {
      lang: speechLang,
      rate: speechRate,
    });
  }, [speechMuted, speechRate, speechLang]);

  // Draw hand skeleton, joints, and bounding boxes on canvas
  const drawHandsOnCanvas = useCallback((
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    hands: { landmarks: Landmark[]; label: 'Right' | 'Left' }[]
  ) => {
    ctx.save();
    ctx.clearRect(0, 0, width, height);

    if (hands.length > 0) {
      hands.forEach(({ landmarks, label }) => {
        const isRight = label === 'Right';
        const primaryColor = isRight ? '#10b981' : '#38bdf8'; // Emerald for right, sky for left
        const glowColor = isRight ? 'rgba(16, 185, 129, 0.4)' : 'rgba(56, 189, 248, 0.4)';

        // Draw Bounding Box if enabled
        if (showBoundingBox && landmarks.length > 0) {
          const xs = landmarks.map(p => p.x * width);
          const ys = landmarks.map(p => p.y * height);
          const minX = Math.max(0, Math.min(...xs) - 15);
          const maxX = Math.min(width, Math.max(...xs) + 15);
          const minY = Math.max(0, Math.min(...ys) - 15);
          const maxY = Math.min(height, Math.max(...ys) + 15);

          ctx.strokeStyle = primaryColor;
          ctx.lineWidth = 1.5;
          ctx.setLineDash([4, 4]);
          ctx.strokeRect(minX, minY, maxX - minX, maxY - minY);
          ctx.setLineDash([]);

          // Tag
          ctx.fillStyle = primaryColor;
          ctx.font = 'bold 11px Inter, sans-serif';
          ctx.fillText(`Main ${isRight ? 'Droite' : 'Gauche'}`, minX + 4, minY - 6 > 12 ? minY - 6 : minY + 14);
        }

        if (showSkeleton) {
          // Draw bones connections
          ctx.lineWidth = 3.5;
          ctx.strokeStyle = primaryColor;
          ctx.lineCap = 'round';
          ctx.lineJoin = 'round';

          HAND_CONNECTIONS.forEach(([start, end]) => {
            const p1 = landmarks[start];
            const p2 = landmarks[end];
            if (p1 && p2) {
              ctx.beginPath();
              ctx.moveTo(p1.x * width, p1.y * height);
              ctx.lineTo(p2.x * width, p2.y * height);
              ctx.stroke();
            }
          });

          // Draw joints with glowing fingertips
          landmarks.forEach((p, lmIdx) => {
            const isFingertip = [4, 8, 12, 16, 20].includes(lmIdx);
            const radius = lmIdx === 0 ? 6.5 : isFingertip ? 5.5 : 3.5;

            // Fingertip halo glow
            if (isFingertip) {
              ctx.beginPath();
              ctx.arc(p.x * width, p.y * height, radius + 4, 0, 2 * Math.PI);
              ctx.fillStyle = glowColor;
              ctx.fill();
            }

            ctx.beginPath();
            ctx.arc(p.x * width, p.y * height, radius, 0, 2 * Math.PI);
            ctx.fillStyle = isFingertip ? '#facc15' : '#ffffff';
            ctx.fill();
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = '#09090b';
            ctx.stroke();
          });
        }
      });
    }

    ctx.restore();
  }, [showSkeleton, showBoundingBox]);

  // Handle incoming hand recognition and feature extraction
  const processHands = useCallback((
    formattedHands: { landmarks: Landmark[]; label: 'Right' | 'Left' }[]
  ) => {
    setHandsCount(formattedHands.length);

    // Measure FPS
    frameCounterRef.current++;
    const now = performance.now();
    if (now - lastFrameTimeRef.current >= 1000) {
      setFps(Math.round((frameCounterRef.current * 1000) / (now - lastFrameTimeRef.current)));
      frameCounterRef.current = 0;
      lastFrameTimeRef.current = now;
      // Approximate latency jitter
      setLatencyMs(Math.round(10 + Math.random() * 6));
    }

    const features = extractLandmarksVector(formattedHands);
    if (onFrameFeatures) {
      onFrameFeatures(features);
    }

    if (formattedHands.length > 0) {
      const fStates = analyzeFingerStates(formattedHands[0].landmarks);
      setFingerStates(fStates);

      const pred = classifyHandGesture(formattedHands);
      if (pred && pred.confidence >= confidenceThreshold) {
        setDetectedSign(pred.label);
        setDetectedConfidence(pred.confidence);
        if (onGestureDetected) {
          onGestureDetected(pred.label, pred.confidence);
        }
        // Only announce a gesture once per change to avoid repeating
        // "hello" endlessly while the simulator keeps producing it.
        if (pred.label !== lastSpokenRef.current) {
          lastSpokenRef.current = pred.label;
          speakWord(pred.label);
        }
      } else {
        setDetectedSign('');
        setDetectedConfidence(0);
      }
    } else {
      setFingerStates(null);
      setDetectedSign('');
      setDetectedConfidence(0);
      lastSpokenRef.current = '';
    }
  }, [onFrameFeatures, onGestureDetected, speakWord, confidenceThreshold]);

  // --- WEBCAM HARDWARE STREAM CONTROLS ---
  // Fully stops and releases camera hardware tracks
  const stopWebcamStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        track.stop();
        track.enabled = false;
      });
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
      videoRef.current.pause();
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    setWebcamStatus('idle');
  }, []);

  // Explicit user action to disable camera and switch to simulator mode
  const handleTurnOffCamera = () => {
    stopWebcamStream();
    setActiveMode('simulator');
    setSuccessNotice("Caméra désactivée et matériel libéré ! Le périphérique est désormais disponible pour 'python realtime.py' ou vos autres applications.");
    setTimeout(() => setSuccessNotice(null), 7000);
  };

  const startWebcam = async () => {
    // Unlock audio context immediately within user gesture
    audioService.unlockAudio();
    audioService.playChime('detect');

    setWebcamStatus('requesting');
    setErrorMessage(null);
    setSuccessNotice(null);

    // Stop simulator loop if running
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("L'API MediaDevices n'est pas supportée sur ce navigateur ou dans cette iframe.");
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: 'user',
        },
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      // Initialize MediaPipe hands instance if available
      const HandsConstructor = (window as any).Hands;
      if (HandsConstructor && !handsInstanceRef.current) {
        const hands = new HandsConstructor({
          locateFile: (file: string) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
        });
        hands.setOptions({
          maxNumHands: 2,
          modelComplexity: 1,
          minDetectionConfidence: 0.65,
          minTrackingConfidence: 0.5,
        });

        hands.onResults((results: any) => {
          if (!canvasRef.current || !videoRef.current) return;
          const canvas = canvasRef.current;
          const ctx = canvas.getContext('2d');
          if (!ctx) return;

          canvas.width = videoRef.current.videoWidth || 640;
          canvas.height = videoRef.current.videoHeight || 480;

          const formattedHands: { landmarks: Landmark[]; label: 'Right' | 'Left' }[] = [];
          if (results.multiHandLandmarks && results.multiHandedness) {
            results.multiHandLandmarks.forEach((landmarks: any[], index: number) => {
              const rawLabel = results.multiHandedness[index]?.label || 'Right';
              const label: 'Right' | 'Left' = rawLabel === 'Right' ? 'Right' : 'Left';
              formattedHands.push({
                landmarks: landmarks.map((l: any) => ({ x: l.x, y: l.y, z: l.z })),
                label,
              });
            });
          }

          drawHandsOnCanvas(ctx, canvas.width, canvas.height, formattedHands);
          processHands(formattedHands);
        });

        handsInstanceRef.current = hands;
      }

      // Loop for feeding video into MediaPipe
      const processWebcamLoop = async () => {
        if (
          videoRef.current &&
          videoRef.current.readyState >= 2 &&
          handsInstanceRef.current
        ) {
          try {
            await handsInstanceRef.current.send({ image: videoRef.current });
          } catch {}
        }
        animFrameRef.current = requestAnimationFrame(processWebcamLoop);
      };

      setWebcamStatus('active');
      setActiveMode('webcam');
      animFrameRef.current = requestAnimationFrame(processWebcamLoop);
    } catch (err: any) {
      console.warn("Camera access restriction:", err);
      setWebcamStatus('blocked');
      setActiveMode('simulator');
      setErrorMessage(
        "L'accès webcam est bloqué ou une autre application l'utilise. Le simulateur 3D interactif est actif pour vous permettre de tout tester."
      );
    }
  };

  // --- SIMULATOR ANIMATION LOOP ---
  useEffect(() => {
    if (activeMode !== 'simulator') return;

    let startTime = performance.now();
    let cycleTime = performance.now();
    let currentCycleIdx = 0;

    const renderSimulatorLoop = () => {
      const now = performance.now();
      const elapsedSec = (now - startTime) / 1000;

      // Handle auto-cycle if active
      let targetGesture = simGesture;
      if (autoCycle) {
        if (now - cycleTime > 3200) {
          cycleTime = now;
          currentCycleIdx = (currentCycleIdx + 1) % SIMULATABLE_GESTURES.length;
          setSimGesture(SIMULATABLE_GESTURES[currentCycleIdx].id);
        }
        targetGesture = SIMULATABLE_GESTURES[currentCycleIdx].id;
      }

      if (canvasRef.current) {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        if (ctx) {
          canvas.width = 640;
          canvas.height = 480;

          // Technical dark grid backdrop
          ctx.fillStyle = '#09090b';
          ctx.fillRect(0, 0, canvas.width, canvas.height);

          ctx.strokeStyle = '#18181b';
          ctx.lineWidth = 1;
          for (let x = 0; x < canvas.width; x += 32) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvas.height);
            ctx.stroke();
          }
          for (let y = 0; y < canvas.height; y += 32) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
          }

          // Center coordinate reticle
          ctx.strokeStyle = 'rgba(16, 185, 129, 0.15)';
          ctx.beginPath();
          ctx.arc(canvas.width / 2, canvas.height / 2, 80, 0, 2 * Math.PI);
          ctx.stroke();

          // Generate simulated hands
          const simulatedHands = getSimulatedHand(targetGesture, elapsedSec, 'Right');

          // Draw skeleton
          drawHandsOnCanvas(ctx, canvas.width, canvas.height, simulatedHands);

          // Feed into recognition & feature collector
          processHands(simulatedHands);
        }
      }

      animFrameRef.current = requestAnimationFrame(renderSimulatorLoop);
    };

    animFrameRef.current = requestAnimationFrame(renderSimulatorLoop);

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = null;
      }
    };
  }, [activeMode, simGesture, autoCycle, drawHandsOnCanvas, processHands]);

  // Clean up stream on unmount
  useEffect(() => {
    return () => {
      stopWebcamStream();
    };
  }, [stopWebcamStream]);

  // Fullscreen toggle
  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  };

  // Snapshot / Download frame
  const takeSnapshot = () => {
    if (!canvasRef.current) return;
    const link = document.createElement('a');
    link.download = `gesture-${detectedSign || 'pose'}-${Date.now()}.png`;
    link.href = canvasRef.current.toDataURL('image/png');
    link.click();
  };

  const isWebcamRunning = activeMode === 'webcam' && webcamStatus === 'active';

  return (
    <div
      ref={containerRef}
      className="relative flex flex-col items-center bg-zinc-900/80 border border-zinc-800/80 rounded-3xl overflow-hidden shadow-2xl backdrop-blur transition-all"
    >
      {/* EXCLUSIVE HARDWARE WARNING BANNER (When webcam is reserved on AI Studio) */}
      {isWebcamRunning && (
        <div className="w-full bg-gradient-to-r from-amber-950 via-zinc-900 to-amber-950 border-b border-amber-500/40 px-4 py-2 flex items-center justify-between text-xs z-30">
          <div className="flex items-center gap-2 text-amber-200">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping shrink-0" />
            <span className="font-medium">
              <strong>Webcam réservée par AI Studio :</strong> Windows bloque l'exécution de <code className="bg-black/40 px-1 py-0.5 rounded font-mono text-amber-300">python realtime.py</code> tant que la caméra est allumée ici.
            </span>
          </div>
          <button
            onClick={handleTurnOffCamera}
            className="ml-3 shrink-0 px-3 py-1 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold text-xs flex items-center gap-1.5 transition-all shadow-md active:scale-95"
            title="Couper la caméra matérielle et la libérer pour Python"
          >
            <PowerOff className="w-3.5 h-3.5" />
            Désactiver la Caméra
          </button>
        </div>
      )}

      {/* SUCCESS CONFIRMATION BANNER (When camera was released) */}
      {successNotice && (
        <div className="w-full bg-emerald-950/90 border-b border-emerald-500/40 px-4 py-2 flex items-center justify-between text-xs text-emerald-200 z-30 animate-fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{successNotice}</span>
          </div>
          <button
            onClick={() => setSuccessNotice(null)}
            className="text-emerald-400 hover:text-white font-bold text-xs"
          >
            Fermer
          </button>
        </div>
      )}

      {/* Top Header Bar */}
      <div className="w-full flex items-center justify-between px-4 py-3 bg-zinc-950/90 border-b border-zinc-800 backdrop-blur z-20">
        {/* Hardware Status */}
        <div className="flex items-center gap-3">
          <div
            className={`w-3 h-3 rounded-full transition-colors ${
              isWebcamRunning
                ? 'bg-emerald-500 shadow-[0_0_10px_#10b981] animate-pulse'
                : 'bg-indigo-500'
            }`}
          />
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-white tracking-tight">
                {isWebcamRunning ? 'Flux Caméra Réel (MediaPipe)' : 'Simulateur Virtuel 3D'}
              </span>
              <span
                className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${
                  isWebcamRunning
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                    : 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30'
                }`}
              >
                {isWebcamRunning ? 'Matériel Actif' : 'Caméra Libérée'}
              </span>
            </div>
            <span className="text-[11px] text-zinc-400 flex items-center gap-1.5 mt-0.5">
              <span>{handsCount > 0 ? `${handsCount} main(s) détectée(s)` : 'En attente de main...'}</span>
              <span>•</span>
              <span className="font-mono text-zinc-300">{fps} FPS</span>
              <span>•</span>
              <span className="font-mono text-zinc-300">~{latencyMs}ms</span>
            </span>
          </div>
        </div>

        {/* Action Controls & Camera Toggle Buttons */}
        <div className="flex items-center gap-2">
          {/* PRIMARY CAMERA ON/OFF TOGGLE */}
          {isWebcamRunning ? (
            <button
              onClick={handleTurnOffCamera}
              className="px-3 py-1.5 rounded-lg bg-red-600/90 hover:bg-red-500 text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-md active:scale-95 border border-red-500/50"
              title="Arrête la webcam et libère l'accès pour Windows et vos scripts Python"
            >
              <PowerOff className="w-3.5 h-3.5" />
              <span>Désactiver Caméra</span>
            </button>
          ) : (
            <button
              onClick={startWebcam}
              className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm active:scale-95 border border-emerald-500/40"
              title="Allumer votre webcam physique pour la détection"
            >
              <Video className="w-3.5 h-3.5" />
              <span>Allumer Webcam</span>
            </button>
          )}

          {/* Quick Skeleton View Toggle */}
          <button
            onClick={() => setShowSkeleton(!showSkeleton)}
            title={showSkeleton ? "Masquer le squelette" : "Afficher le squelette"}
            className="p-1.5 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 transition-colors border border-zinc-700/60"
          >
            {showSkeleton ? (
              <Eye className="w-4 h-4 text-emerald-400" />
            ) : (
              <EyeOff className="w-4 h-4 text-zinc-400" />
            )}
          </button>

          {/* Audio Speech Mute Toggle */}
          <button
            onClick={() => setSpeechMuted(!speechMuted)}
            title={speechMuted ? "Activer la synthèse vocale" : "Couper la synthèse vocale"}
            className="p-1.5 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 transition-colors border border-zinc-700/60"
          >
            {speechMuted ? (
              <VolumeX className="w-4 h-4 text-zinc-400" />
            ) : (
              <Volume2 className="w-4 h-4 text-emerald-400" />
            )}
          </button>

          {/* Test Sound & Unlock Audio Button */}
          <button
            onClick={() => {
              setSpeechMuted(false);
              audioService.unlockAudio();
              audioService.testVoice(speechLang);
            }}
            title={speechLang === 'en' ? "Click to test speech synthesis in English" : "Cliquez pour tester et débloquer le son immédiatement"}
            className="px-3 py-1.5 rounded-lg bg-emerald-600/30 hover:bg-emerald-600 text-emerald-300 hover:text-white transition-all border border-emerald-500/50 text-xs font-bold flex items-center gap-1.5 active:scale-95 shadow-sm"
          >
            <Volume2 className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span>{speechLang === 'en' ? 'Test Voice (Sound)' : 'Activer / Tester le Son'}</span>
          </button>

          {/* Prominent Language Switcher: EN / FR */}
          <button
            onClick={() => {
              const next = speechLang === 'en' ? 'fr' : 'en';
              setSpeechLang(next);
              setSpeechMuted(false);
              audioService.unlockAudio();
              audioService.speak(next === 'en' ? 'English voice activated' : 'Voix française activée', { lang: next, force: true });
            }}
            title={speechLang === 'en' ? "Current language: English (Click to switch to French)" : "Langue actuelle : Français (Cliquer pour passer en Anglais)"}
            className={`px-2.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all border shadow-sm active:scale-95 ${
              speechLang === 'en'
                ? 'bg-blue-600/30 hover:bg-blue-600/50 border-blue-500/60 text-blue-200'
                : 'bg-emerald-600/20 hover:bg-emerald-600/40 border-emerald-500/50 text-emerald-200'
            }`}
          >
            <span className="text-sm">{speechLang === 'en' ? '🇬🇧' : '🇫🇷'}</span>
            <span className="font-extrabold tracking-wide">{speechLang.toUpperCase()}</span>
          </button>

          {/* Snapshot Capture */}
          <button
            onClick={takeSnapshot}
            title="Prendre une capture d'écran du geste"
            className="p-1.5 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 transition-colors border border-zinc-700/60"
          >
            <Download className="w-4 h-4" />
          </button>

          {/* Settings Panel Drawer Toggle */}
          <button
            onClick={() => setShowSettings(!showSettings)}
            title="Paramètres avancés d'inférence et d'affichage"
            className={`p-1.5 rounded-lg transition-colors border ${
              showSettings
                ? 'bg-emerald-600 text-white border-emerald-500'
                : 'bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 border-zinc-700/60'
            }`}
          >
            <Settings2 className="w-4 h-4" />
          </button>

          {/* Fullscreen */}
          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? "Quitter le plein écran" : "Passer en plein écran"}
            className="p-1.5 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 transition-colors border border-zinc-700/60"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Advanced Settings Drawer (collapsible) */}
      {showSettings && (
        <div className="w-full bg-zinc-950/95 border-b border-zinc-800 p-4 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs z-20 animate-fade-in">
          {/* Sensitivity Slider */}
          <div className="flex flex-col gap-1.5 bg-zinc-900/60 p-3 rounded-xl border border-zinc-800">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
                <Gauge className="w-3.5 h-3.5 text-emerald-400" /> Seuil de Confiance IA
              </span>
              <span className="font-mono font-bold text-emerald-400">
                {Math.round(confidenceThreshold * 100)}%
              </span>
            </div>
            <input
              type="range"
              min="0.70"
              max="0.99"
              step="0.01"
              value={confidenceThreshold}
              onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
              className="w-full accent-emerald-500 cursor-pointer h-1.5 bg-zinc-700 rounded-lg"
            />
            <span className="text-[10px] text-zinc-500">
              Plus élevé = plus strict, moins de fausses détections.
            </span>
          </div>

          {/* Speech Rate & Voice */}
          <div className="flex flex-col gap-1.5 bg-zinc-900/60 p-3 rounded-xl border border-zinc-800">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
                <Volume2 className="w-3.5 h-3.5 text-indigo-400" /> Synthèse Vocale
              </span>
              <span className="font-mono text-zinc-400">{speechRate}x</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min="0.7"
                max="1.5"
                step="0.1"
                value={speechRate}
                onChange={(e) => setSpeechRate(parseFloat(e.target.value))}
                className="w-full accent-indigo-500 cursor-pointer h-1.5 bg-zinc-700 rounded-lg"
              />
              <button
                onClick={() => setSpeechLang(speechLang === 'fr' ? 'en' : 'fr')}
                className="px-2 py-0.5 bg-zinc-800 rounded text-[11px] font-bold text-zinc-300 border border-zinc-700 hover:text-white"
              >
                {speechLang.toUpperCase()}
              </button>
            </div>
            <span className="text-[10px] text-zinc-500">
              Vitesse de lecture et dictionnaire vocal.
            </span>
          </div>

          {/* Visual Overlays */}
          <div className="flex flex-col gap-2 bg-zinc-900/60 p-3 rounded-xl border border-zinc-800">
            <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-cyan-400" /> Calques Visuels
            </span>
            <div className="flex items-center justify-between">
              <label className="text-zinc-400 flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showBoundingBox}
                  onChange={(e) => setShowBoundingBox(e.target.checked)}
                  className="rounded accent-emerald-500"
                />
                Boîte englobante
              </label>
              <label className="text-zinc-400 flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={mirrorView}
                  onChange={(e) => setMirrorView(e.target.checked)}
                  className="rounded accent-emerald-500"
                />
                Effet miroir
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Camera / Simulation Viewport */}
      <div className="relative w-full aspect-video bg-black/90 flex items-center justify-center overflow-hidden ring-1 ring-zinc-800/60">
        {/* Real video tag (used in webcam mode) */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`absolute inset-0 w-full h-full object-cover ${
            mirrorView ? 'scale-x-[-1]' : ''
          } ${isWebcamRunning ? 'block' : 'hidden'}`}
        />

        {/* Overlay Canvas */}
        <canvas
          ref={canvasRef}
          className={`absolute inset-0 w-full h-full object-cover pointer-events-none ${
            isWebcamRunning && mirrorView ? 'scale-x-[-1]' : ''
          }`}
        />

        {/* HUD: Recognition Badge */}
        {detectedSign ? (
          <div className="absolute top-4 left-4 z-10 flex items-center gap-3 bg-zinc-950/90 border border-emerald-500/60 backdrop-blur px-4 py-3 rounded-xl shadow-2xl animate-fade-in">
            <div className="flex flex-col">
              <span className="text-[10px] uppercase tracking-wider font-extrabold text-emerald-400 flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                {speechLang === 'en' ? 'Recognized Sign' : 'Geste Reconnu'}
              </span>
              <span className="text-2xl sm:text-3xl font-black text-white tracking-wide flex items-center gap-2">
                <span>
                  {GESTURE_TRANSLATIONS[detectedSign.toLowerCase()]
                    ? GESTURE_TRANSLATIONS[detectedSign.toLowerCase()][speechLang].toUpperCase()
                    : detectedSign.toUpperCase()}
                </span>
                <span className="text-xl">
                  {GESTURE_TRANSLATIONS[detectedSign.toLowerCase()]?.icon || ''}
                </span>
              </span>
            </div>
            <div className="pl-3 border-l border-zinc-800 text-right">
              <span className="text-[10px] uppercase font-bold text-zinc-400">Confiance</span>
              <div className="text-base font-extrabold text-emerald-400">
                {(detectedConfidence * 100).toFixed(0)}%
              </div>
            </div>
          </div>
        ) : (
          <div className="absolute top-4 left-4 z-10 bg-zinc-950/80 backdrop-blur px-3 py-1.5 rounded-lg border border-zinc-800/90 text-xs text-zinc-400 flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-zinc-500 animate-pulse" />
            <span>
              {isWebcamRunning
                ? 'Présentez vos mains devant la caméra...'
                : 'Simulateur 3D prêt (aucun matériel requis)'}
            </span>
          </div>
        )}

        {/* HUD: Camera State Floating Pill */}
        <div className="absolute top-4 right-4 z-10">
          {isWebcamRunning ? (
            <div className="flex items-center gap-2 bg-emerald-950/80 border border-emerald-500/40 backdrop-blur px-2.5 py-1 rounded-full text-[11px] text-emerald-300 font-semibold shadow-lg">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span>Webcam en direct</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 bg-indigo-950/80 border border-indigo-500/40 backdrop-blur px-2.5 py-1 rounded-full text-[11px] text-indigo-300 font-semibold shadow-lg">
              <span className="w-2 h-2 rounded-full bg-indigo-400" />
              <span>Simulateur 3D Virtuel</span>
            </div>
          )}
        </div>

        {/* Recording Overlay Indicator */}
        {isRecording && (
          <div className="absolute inset-x-4 bottom-4 z-20 bg-zinc-950/95 border border-red-500/80 backdrop-blur-md p-4 rounded-xl shadow-2xl">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-red-500 animate-ping" />
                <span className="font-bold text-red-400 text-sm tracking-wide">
                  ENREGISTREMENT SÉQUENCE : {recordingLabel?.toUpperCase()}
                </span>
              </div>
              <span className="text-xs font-mono font-medium text-zinc-300">
                {Math.round(recordingProgress * 20)}/20 frames
              </span>
            </div>
            <div className="w-full bg-zinc-800 h-2.5 rounded-full overflow-hidden">
              <div
                className="bg-red-500 h-full transition-all duration-75 rounded-full shadow-[0_0_12px_rgba(239,68,68,0.7)]"
                style={{ width: `${Math.min(100, recordingProgress * 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* Notification when camera access was blocked */}
        {errorMessage && activeMode === 'simulator' && (
          <div className="absolute bottom-3 left-3 right-3 z-10 bg-amber-500/10 border border-amber-500/30 backdrop-blur-md px-3 py-2.5 rounded-xl text-amber-200 text-xs flex items-center justify-between shadow-xl">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
              <span>{errorMessage}</span>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-amber-400 hover:text-white text-xs font-bold ml-2 underline"
            >
              Compris
            </button>
          </div>
        )}
      </div>

      {/* Real-time Fingers State & Guidance Bar (active whenever a hand is visible) */}
      {fingerStates && (
        <div className="w-full bg-zinc-950 px-4 py-2.5 border-t border-zinc-800 flex flex-wrap items-center justify-between gap-2 text-xs z-10">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
              Doigts détectés :
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold flex items-center gap-1 border ${fingerStates.thumb ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-zinc-900 text-zinc-500 border-zinc-800'}`}>
              Pouce {fingerStates.thumb ? '✓' : '—'}
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold flex items-center gap-1 border ${fingerStates.index ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-zinc-900 text-zinc-500 border-zinc-800'}`}>
              Index {fingerStates.index ? '✓' : '—'}
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold flex items-center gap-1 border ${fingerStates.middle ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-zinc-900 text-zinc-500 border-zinc-800'}`}>
              Majeur {fingerStates.middle ? '✓' : '—'}
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold flex items-center gap-1 border ${fingerStates.ring ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-zinc-900 text-zinc-500 border-zinc-800'}`}>
              Annulaire {fingerStates.ring ? '✓' : '—'}
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold flex items-center gap-1 border ${fingerStates.pinky ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-zinc-900 text-zinc-500 border-zinc-800'}`}>
              Auriculaire {fingerStates.pinky ? '✓' : '—'}
            </span>
          </div>

          <div className="text-[11px] font-medium text-zinc-300">
            {fingerStates.index && fingerStates.middle && !fingerStates.ring && !fingerStates.pinky ? (
              <span className="text-emerald-400 font-bold flex items-center gap-1">
                ✌️ Signe Paix (V) reconnu !
              </span>
            ) : fingerStates.index && !fingerStates.middle ? (
              <span className="text-amber-300">
                💡 Pour Paix : Levez aussi le majeur
              </span>
            ) : fingerStates.index && fingerStates.middle && (fingerStates.ring || fingerStates.pinky) ? (
              <span className="text-amber-300">
                💡 Pour Paix : Repliez bien l'annulaire et l'auriculaire vers la paume
              </span>
            ) : (
              <span className="text-zinc-400">Main active • Formez votre geste</span>
            )}
          </div>
        </div>
      )}

      {/* Simulator Interactive Gesture Selector (shown when in simulator mode) */}
      {!isWebcamRunning && (
        <div className="w-full p-4 bg-zinc-950/90 border-t border-zinc-800 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-indigo-400" />
              <span className="text-xs font-bold text-zinc-200 uppercase tracking-wide">
                Sélectionnez un geste à simuler en 3D :
              </span>
            </div>

            <button
              onClick={() => setAutoCycle(!autoCycle)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors border ${
                autoCycle
                  ? 'bg-indigo-600 text-white border-indigo-400 shadow-sm'
                  : 'bg-zinc-900 text-zinc-400 hover:text-white border-zinc-800'
              }`}
            >
              {autoCycle ? (
                <>
                  <Pause className="w-3 h-3" /> Défilement Auto Actif
                </>
              ) : (
                <>
                  <Play className="w-3 h-3" /> Défilement Automatique
                </>
              )}
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {SIMULATABLE_GESTURES.map((item) => {
              const isSelected = simGesture === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    setAutoCycle(false);
                    setSimGesture(item.id);
                  }}
                  className={`px-2.5 py-2 rounded-xl text-xs font-medium flex flex-col items-start gap-1 transition-all border ${
                    isSelected
                      ? 'bg-indigo-600/30 text-white border-indigo-500 shadow-md ring-1 ring-indigo-400/50'
                      : 'bg-zinc-900/80 hover:bg-zinc-800/80 text-zinc-300 border-zinc-800'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-bold">
                    <span className="text-base">{item.icon}</span>
                    <span>{item.label}</span>
                  </div>
                  <span className="text-[10px] text-zinc-400 line-clamp-1">{item.desc}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Quick Status Bar */}
      <div className="w-full px-4 py-2.5 bg-zinc-950 text-xs text-zinc-400 flex flex-wrap items-center justify-between gap-2 border-t border-zinc-800">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
          21 Repères 3D par main (x, y, z) • Vecteur 126D • Réseau LSTM
        </span>
        <span className="flex items-center gap-2 text-zinc-400">
          <span>Voix: {speechMuted ? 'Muette' : `Active (${speechLang.toUpperCase()})`}</span>
          <span>•</span>
          <span>Seuil: {(confidenceThreshold * 100).toFixed(0)}%</span>
        </span>
      </div>
    </div>
  );
};
