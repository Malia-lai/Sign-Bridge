import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Camera, CameraOff, Sparkles, Volume2, VolumeX, AlertCircle, RefreshCw, Activity, Layers, Terminal, CheckCircle2, XCircle, Scale } from 'lucide-react';
import { DetectionResult, Landmark3D, ParityResult } from '../types';
import { RealtimeWebSocketClient } from '../services/api';
import { speechService } from '../services/speech';

const HAND_CONNECTIONS: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17]
];

const FINGERTIP_INDICES = new Set([4, 8, 12, 16, 20]);

function getReadyStateName(state: number): string {
  switch (state) {
    case 0: return 'HAVE_NOTHING';
    case 1: return 'HAVE_METADATA';
    case 2: return 'HAVE_CURRENT_DATA';
    case 3: return 'HAVE_FUTURE_DATA';
    case 4: return 'HAVE_ENOUGH_DATA';
    default: return `STATE_${state}`;
  }
}

interface LiveCameraProps {
  isBackendConnected: boolean;
  missingFiles?: string[];
  historyWords: string[];
  onOpen3DSimulator: () => void;
  onDetectionUpdate: (res: DetectionResult) => void;
  onAddWord: (word: string) => void;
}

export const LiveCamera: React.FC<LiveCameraProps> = ({
  isBackendConnected: _isBackendConnectedProp,
  missingFiles = [],
  historyWords,
  onOpen3DSimulator,
  onDetectionUpdate,
  onAddWord: _onAddWord,
}) => {
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(true);

  // Diagnostics: MediaPipe
  const [mpLoaded, setMpLoaded] = useState<boolean>(false);
  const [mpError, setMpError] = useState<string | null>(null);

  // Diagnostics: Video Feed
  const [videoReadyState, setVideoReadyState] = useState<number>(0);
  const [videoResolution, setVideoResolution] = useState<string>('0×0');

  // Diagnostics: Frame Pipeline Counters
  const [framesSent, setFramesSent] = useState<number>(0);
  const [resultsReceived, setResultsReceived] = useState<number>(0);
  const [resultsWithHand, setResultsWithHand] = useState<number>(0);
  const [handsDetected, setHandsDetected] = useState<number>(0);

  // Diagnostics: WebSocket & Backend State
  const [wsState, setWsState] = useState<'connecting' | 'connected' | 'closed' | 'error'>('closed');
  const [wsCloseCode, setWsCloseCode] = useState<number | null>(null);
  const [wsCloseReason, setWsCloseReason] = useState<string | null>(null);
  const [wsMessagesSent, setWsMessagesSent] = useState<number>(0);
  const [wsMessagesReceived, setWsMessagesReceived] = useState<number>(0);
  const [measuredLatencyMs, setMeasuredLatencyMs] = useState<number | null>(null);
  const [sequenceBuffer, setSequenceBuffer] = useState<number>(0);

  // Performance: Measured FPS
  const [measuredFps, setMeasuredFps] = useState<number>(0);

  // Parity Check Mode
  const [parityMode, setParityMode] = useState<boolean>(false);
  const [parityResult, setParityResult] = useState<ParityResult | null>(null);

  // Environment detection: AI Studio Preview container
  const isAiStudioPreview = typeof window !== 'undefined' && (
    window.location.hostname.includes('run.app') ||
    window.location.hostname.includes('aistudio') ||
    window.location.hostname.includes('google') ||
    window.location.hostname.includes('webcontainer') ||
    (!window.location.hostname.includes('localhost') && !window.location.hostname.includes('127.0.0.1'))
  );

  // Prediction HUD State (From Backend)
  const [predictedSign, setPredictedSign] = useState<string>('');
  const [predictedConfidence, setPredictedConfidence] = useState<number>(0);
  const [statusMode, setStatusMode] = useState<'recognised' | 'predicting' | ''>('');
  const [stableProgress, setStableProgress] = useState<number>(0);

  // Refs for camera & rendering
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const wsClientRef = useRef<RealtimeWebSocketClient | null>(null);
  const mpHandsRef = useRef<any>(null);
  const cameraLoopRef = useRef<number | null>(null);
  const renderLoopRef = useRef<number | null>(null);
  const isComponentMountedRef = useRef<boolean>(true);
  const isProcessingRef = useRef<boolean>(false);
  const retryCountRef = useRef<number>(0);
  const watchdogTimerRef = useRef<number | null>(null);

  // Parity check refs
  const parityModeRef = useRef<boolean>(false);
  const parityCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const lastParityTimestampRef = useRef<number>(0);
  const latestPredictedSignRef = useRef<string>('');

  useEffect(() => {
    parityModeRef.current = parityMode;
  }, [parityMode]);

  // Landmark buffer for 60 FPS drawing
  const latestLandmarksRef = useRef<Landmark3D[][]>([]);

  // FPS calculation refs
  const resultsCountForFpsRef = useRef<number>(0);
  const lastFpsTimestampRef = useRef<number>(Date.now());

  // Message counters refs
  const framesSentCountRef = useRef<number>(0);
  const resultsReceivedCountRef = useRef<number>(0);
  const resultsWithHandsCountRef = useRef<number>(0);
  const wsSentCountRef = useRef<number>(0);
  const wsReceivedCountRef = useRef<number>(0);

  // Audio toggle
  const toggleMute = () => {
    const nextMuted = !isMuted;
    setIsMuted(nextMuted);
    speechService.isMuted = nextMuted;
  };

  // 1. Initialize WebSocket Connection to Backend
  useEffect(() => {
    isComponentMountedRef.current = true;
    setWsState('connecting');

    const client = new RealtimeWebSocketClient(
      (result: DetectionResult) => {
        wsReceivedCountRef.current++;
        setWsMessagesReceived(wsReceivedCountRef.current);

        if (result.latency_ms !== undefined) {
          setMeasuredLatencyMs(result.latency_ms);
        }
        if (result.sequence_buffer !== undefined) {
          setSequenceBuffer(result.sequence_buffer);
        } else if (result.buffer_size !== undefined) {
          setSequenceBuffer(result.buffer_size);
        }

        // Top candidate or recognized gesture
        const isRecognised = result.status_mode === 'recognised' || (result.confidence && result.confidence >= 0.75);
        if (isRecognised && (result.display_label || result.label)) {
          setStatusMode('recognised');
          const lbl = result.display_label || result.label || '';
          setPredictedSign(lbl);
          latestPredictedSignRef.current = lbl;
          setPredictedConfidence(result.confidence || 0);
        } else if (result.candidate_label || result.candidate_display) {
          setStatusMode('predicting');
          const lbl = result.candidate_display || result.candidate_label || '';
          setPredictedSign(lbl);
          latestPredictedSignRef.current = lbl;
          setPredictedConfidence(result.candidate_confidence || 0);
        } else {
          setStatusMode('');
          setPredictedSign('');
          latestPredictedSignRef.current = '';
          setPredictedConfidence(0);
        }

        setStableProgress(result.stable_progress || 0);

        if (result.speak_word && !speechService.isMuted) {
          speechService.speak(result.speak_word);
        }

        onDetectionUpdate(result);
      },
      (connected: boolean, closeCode?: number, closeReason?: string, errorMsg?: string) => {
        setWsState(connected ? 'connected' : 'closed');
        if (!connected) {
          setMeasuredLatencyMs(null);
          if (closeCode !== undefined) setWsCloseCode(closeCode);
          if (closeReason) setWsCloseReason(closeReason);
          if (errorMsg) setWsCloseReason(errorMsg);
        } else {
          setWsCloseCode(null);
          setWsCloseReason(null);
        }
      },
      (pRes: ParityResult) => {
        setParityResult(pRes);
      }
    );

    client.connect();
    wsClientRef.current = client;

    return () => {
      isComponentMountedRef.current = false;
      client.disconnect();
    };
  }, [onDetectionUpdate]);

  // 2. Initialize MediaPipe Hands (Bundled Locally in /mediapipe/hands/)
  useEffect(() => {
    let handsInstance: any = null;
    try {
      const win = window as any;
      if (!win.Hands) {
        setMpLoaded(false);
        setMpError("window.Hands is not defined. Checking local scripts...");
        return;
      }

      // Point locateFile to local bundled assets (never CDN)
      handsInstance = new win.Hands({
        locateFile: (file: string) => `/mediapipe/hands/${file}`
      });

      handsInstance.setOptions({
        selfieMode: true, // Mirrors horizontally like cv2.flip(frame, 1)
        maxNumHands: 2,
        modelComplexity: 0,
        minDetectionConfidence: 0.6,
        minTrackingConfidence: 0.5
      });

      handsInstance.onResults((results: any) => {
        isProcessingRef.current = false;
        resultsReceivedCountRef.current++;
        setResultsReceived(resultsReceivedCountRef.current);

        // Measured FPS calculation
        resultsCountForFpsRef.current++;
        const now = Date.now();
        if (now - lastFpsTimestampRef.current >= 1000) {
          const elapsed = (now - lastFpsTimestampRef.current) / 1000;
          setMeasuredFps(Math.round(resultsCountForFpsRef.current / elapsed));
          resultsCountForFpsRef.current = 0;
          lastFpsTimestampRef.current = now;
        }

        const multiHands = results.multiHandLandmarks || [];
        const count = multiHands.length;
        setHandsDetected(count);

        if (count > 0) {
          resultsWithHandsCountRef.current++;
          setResultsWithHand(resultsWithHandsCountRef.current);
        }

        // Store for immediate drawing on next animation frame
        latestLandmarksRef.current = multiHands;

        // Build 126-value vector exactly like realtime.py:
        // hand order as MediaPipe returns it, x,y,z per landmark, zero-padded, truncated to 126
        const coords: number[] = [];
        const rawHands3D: [number, number, number][][] = [];

        for (const hand of multiHands) {
          const h3d: [number, number, number][] = [];
          for (const lm of hand) {
            coords.push(lm.x, lm.y, lm.z);
            h3d.push([lm.x, lm.y, lm.z]);
          }
          rawHands3D.push(h3d);
        }

        const vector126 = new Array(126).fill(0.0);
        for (let i = 0; i < Math.min(coords.length, 126); i++) {
          vector126[i] = coords[i];
        }

        // Send ONLY numbers over WebSocket (no images)
        if (wsClientRef.current && wsClientRef.current.isConnected()) {
          wsSentCountRef.current++;
          setWsMessagesSent(wsSentCountRef.current);
          wsClientRef.current.sendLandmarksVector(vector126, rawHands3D);

          // Parity check mode: About 2 times per second (~500ms), also send a 320x240 JPEG
          // This mode is for testing only and must not affect normal operation.
          if (parityModeRef.current && videoRef.current) {
            const pNow = Date.now();
            if (pNow - lastParityTimestampRef.current >= 500) {
              lastParityTimestampRef.current = pNow;
              try {
                if (!parityCanvasRef.current) {
                  parityCanvasRef.current = document.createElement('canvas');
                  parityCanvasRef.current.width = 320;
                  parityCanvasRef.current.height = 240;
                }
                const pCtx = parityCanvasRef.current.getContext('2d');
                if (pCtx && videoRef.current.videoWidth > 0) {
                  pCtx.drawImage(videoRef.current, 0, 0, 320, 240);
                  const frameJpeg = parityCanvasRef.current.toDataURL('image/jpeg', 0.65);
                  wsClientRef.current.sendParityCheck(vector126, frameJpeg, latestPredictedSignRef.current || '');
                }
              } catch (pErr) {
                console.warn("Parity frame capture error:", pErr);
              }
            }
          }
        }
      });

      mpHandsRef.current = handsInstance;
      setMpLoaded(true);
      setMpError(null);
    } catch (err: any) {
      console.error("MediaPipe initialization error:", err);
      setMpLoaded(false);
      setMpError(String(err?.message || err));
    }

    return () => {
      if (handsInstance?.close) {
        try {
          handsInstance.close();
        } catch {}
      }
    };
  }, []);

  // 3. Camera Control & Track Management
  const stopAllTracks = useCallback(() => {
    if (watchdogTimerRef.current) {
      clearTimeout(watchdogTimerRef.current);
      watchdogTimerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch {}
      });
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    if (cameraLoopRef.current) {
      cancelAnimationFrame(cameraLoopRef.current);
      cameraLoopRef.current = null;
    }
    if (renderLoopRef.current) {
      cancelAnimationFrame(renderLoopRef.current);
      renderLoopRef.current = null;
    }
    latestLandmarksRef.current = [];
    isProcessingRef.current = false;
  }, []);

  const startCamera = useCallback(async () => {
    setCameraError(null);
    stopAllTracks();

    try {
      const constraints: MediaStreamConstraints = {
        video: {
          width: { ideal: 640, max: 1280 },
          height: { ideal: 480, max: 720 },
          frameRate: { ideal: 30, max: 60 },
          facingMode: 'user'
        },
        audio: false
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      if (!isComponentMountedRef.current) {
        stream.getTracks().forEach(t => t.stop());
        return;
      }

      streamRef.current = stream;
      const video = videoRef.current;

      if (video) {
        video.srcObject = stream;
        video.autoplay = true;
        video.muted = true;
        video.playsInline = true;

        video.onloadedmetadata = () => {
          video.play().catch(e => console.warn("video.play() warning:", e));
          setVideoReadyState(video.readyState);
          setVideoResolution(`${video.videoWidth}×${video.videoHeight}`);
        };
      }

      setIsCameraActive(true);

      // Watchdog: check if videoWidth > 0 within 2000ms
      watchdogTimerRef.current = window.setTimeout(() => {
        if (!video || video.videoWidth === 0) {
          if (retryCountRef.current < 3) {
            retryCountRef.current += 1;
            startCamera();
          } else {
            setCameraError("Camera feed returned an empty frame. Please check webcam privacy permissions.");
            stopAllTracks();
            setIsCameraActive(false);
          }
        } else {
          retryCountRef.current = 0;
        }
      }, 2000);

    } catch (err: unknown) {
      console.error("Camera getUserMedia error:", err);
      const msg = err instanceof Error ? err.message : String(err);
      setCameraError(`Unable to open camera: ${msg}. Please grant webcam permissions.`);
      setIsCameraActive(false);
    }
  }, [stopAllTracks]);

  const handleTurnOffCamera = () => {
    retryCountRef.current = 0;
    stopAllTracks();
    setIsCameraActive(false);
    setHandsDetected(0);
    setPredictedSign('');
    setPredictedConfidence(0);
    setStatusMode('');
    setStableProgress(0);
    setMeasuredFps(0);
    setSequenceBuffer(0);
  };

  useEffect(() => {
    const handleBeforeUnload = () => {
      stopAllTracks();
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      stopAllTracks();
    };
  }, [stopAllTracks]);

  // 4. Ingestion Loop: MediaPipe Hands Runs on Live <video> at Camera Rate
  useEffect(() => {
    if (!isCameraActive) return;

    let isLoopRunning = true;

    const cameraTick = () => {
      if (!isLoopRunning) return;

      const video = videoRef.current;
      if (video && video.readyState >= 2 && video.videoWidth > 0) {
        setVideoReadyState(video.readyState);
        setVideoResolution(`${video.videoWidth}×${video.videoHeight}`);

        if (!isProcessingRef.current && mpHandsRef.current) {
          isProcessingRef.current = true;
          framesSentCountRef.current++;
          setFramesSent(framesSentCountRef.current);

          mpHandsRef.current.send({ image: video })
            .catch((err: any) => {
              console.error("MediaPipe hands.send error:", err);
              setMpError(String(err?.message || err));
            })
            .finally(() => {
              isProcessingRef.current = false;
            });
        }
      }

      const vAny = video as any;
      if (vAny && typeof vAny.requestVideoFrameCallback === 'function') {
        vAny.requestVideoFrameCallback(cameraTick);
      } else {
        cameraLoopRef.current = requestAnimationFrame(cameraTick);
      }
    };

    cameraLoopRef.current = requestAnimationFrame(cameraTick);

    return () => {
      isLoopRunning = false;
      if (cameraLoopRef.current) {
        cancelAnimationFrame(cameraLoopRef.current);
        cameraLoopRef.current = null;
      }
    };
  }, [isCameraActive]);

  // 5. Drawing Loop: Drawn from Latest Result on Every Animation Frame (Zero Network in Drawing Path)
  useEffect(() => {
    if (!isCameraActive) return;

    let animId: number;

    const renderTick = () => {
      const canvas = canvasRef.current;
      const video = videoRef.current;

      if (canvas && video && video.videoWidth > 0 && video.videoHeight > 0) {
        if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
        }

        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.clearRect(0, 0, canvas.width, canvas.height);

          const hands = latestLandmarksRef.current;
          if (hands && hands.length > 0) {
            const w = canvas.width;
            const h = canvas.height;

            hands.forEach((hand, hIdx) => {
              if (!hand || hand.length < 21) return;

              const boneColor = hIdx === 0 ? '#10b981' : '#06b6d4'; // Hand 0: Emerald Green, Hand 1: Sky Cyan

              // Draw bones
              ctx.strokeStyle = boneColor;
              ctx.lineWidth = 3.0;
              ctx.lineCap = 'round';
              ctx.lineJoin = 'round';

              HAND_CONNECTIONS.forEach(([p1, p2]) => {
                const pt1 = hand[p1];
                const pt2 = hand[p2];
                if (pt1 && pt2) {
                  ctx.beginPath();
                  ctx.moveTo(pt1.x * w, pt1.y * h);
                  ctx.lineTo(pt2.x * w, pt2.y * h);
                  ctx.stroke();
                }
              });

              // Draw joints and fingertips
              hand.forEach((lm, idx) => {
                const isTip = FINGERTIP_INDICES.has(idx);

                ctx.beginPath();
                ctx.arc(lm.x * w, lm.y * h, isTip ? 5.5 : 3.5, 0, 2 * Math.PI);

                // Fingertips: Yellow/amber; Joints: White
                ctx.fillStyle = isTip ? '#facc15' : '#ffffff';
                ctx.fill();

                ctx.strokeStyle = isTip ? '#ca8a04' : boneColor;
                ctx.lineWidth = isTip ? 1.5 : 1.2;
                ctx.stroke();
              });
            });
          }
        }
      }

      animId = requestAnimationFrame(renderTick);
    };

    renderTick();

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [isCameraActive]);

  return (
    <div className="flex flex-col gap-3">
      {/* Top Action Row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isCameraActive ? (
            <button
              onClick={handleTurnOffCamera}
              className="flex items-center gap-2 bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-xl text-xs font-medium transition-all shadow-md shadow-red-500/20"
            >
              <CameraOff className="w-4 h-4" />
              <span>Turn Off Camera</span>
            </button>
          ) : (
            <button
              onClick={startCamera}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-xl text-xs font-medium transition-all shadow-md shadow-blue-500/20"
            >
              <Camera className="w-4 h-4" />
              <span>Start Camera</span>
            </button>
          )}

          <button
            onClick={onOpen3DSimulator}
            className="flex items-center gap-2 bg-zinc-800/80 hover:bg-zinc-700/80 text-zinc-200 px-4 py-2 rounded-xl text-xs font-medium transition-all border border-zinc-700/60"
          >
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span>3D Simulator</span>
          </button>

          {/* Diagnostics Panel Toggle */}
          <button
            onClick={() => setShowDiagnostics(!showDiagnostics)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
              showDiagnostics
                ? 'bg-emerald-600/20 border-emerald-500/40 text-emerald-300'
                : 'bg-zinc-800/60 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>Diagnostics {showDiagnostics ? 'ON' : 'OFF'}</span>
          </button>

          {/* Parity Check Mode Toggle */}
          <button
            onClick={() => setParityMode(!parityMode)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
              parityMode
                ? 'bg-purple-600/25 border-purple-500/50 text-purple-300 shadow-md shadow-purple-500/10'
                : 'bg-zinc-800/60 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Verify parity with Python realtime.py via live frame comparison"
          >
            <Scale className="w-3.5 h-3.5 text-purple-400" />
            <span>Parity Check {parityMode ? 'ON' : 'OFF'}</span>
          </button>
        </div>

        {/* Audio Mute Toggle */}
        <button
          onClick={toggleMute}
          title={isMuted ? "Unmute Voice" : "Mute Voice"}
          className={`p-2.5 rounded-xl border transition-all ${
            isMuted
              ? 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300'
              : 'bg-zinc-800/80 border-zinc-700 text-blue-400 hover:bg-zinc-800'
          }`}
        >
          {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </button>
      </div>

      {/* Main Viewport Container */}
      <div className="w-full h-[480px] bg-zinc-900/60 border border-zinc-800/80 rounded-2xl relative overflow-hidden flex items-center justify-center">
        {/* Error notification if camera permission denied or watchdog failed */}
        {cameraError && (
          <div className="absolute top-4 inset-x-4 z-30 bg-red-500/15 border border-red-500/40 text-red-200 text-xs px-4 py-3 rounded-xl flex items-center justify-between shadow-xl">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
              <span>{cameraError}</span>
            </div>
            <button
              onClick={startCamera}
              className="flex items-center gap-1 bg-red-600/40 hover:bg-red-600/60 text-white px-2.5 py-1 rounded-lg text-xs"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Retry</span>
            </button>
          </div>
        )}

        {/* Standby State (Camera OFF) */}
        {!isCameraActive ? (
          <div className="flex flex-col items-center justify-center p-8 text-center max-w-md">
            <div className="w-14 h-14 rounded-2xl bg-zinc-800/80 border border-zinc-700/60 flex items-center justify-center text-zinc-400 mb-4 shadow-inner">
              <Camera className="w-7 h-7" />
            </div>

            <h3 className="text-base font-semibold text-white mb-1.5">
              Camera Ready
            </h3>
            <p className="text-xs text-zinc-400 leading-relaxed mb-6">
              Click &quot;Start Camera&quot; to begin real-time sign recognition with your webcam, or test with the 3D Simulator.
            </p>

            <div className="flex items-center gap-3">
              <button
                onClick={startCamera}
                className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium px-4 py-2 rounded-xl transition-all shadow-md shadow-blue-500/20"
              >
                Start Camera
              </button>
              <button
                onClick={onOpen3DSimulator}
                className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium px-4 py-2 rounded-xl transition-all border border-zinc-700/60"
              >
                Try 3D Simulator
              </button>
            </div>

            <div className="absolute bottom-4 right-4">
              <span className="text-[11px] font-medium text-zinc-400 bg-zinc-800/80 border border-zinc-700/60 px-2.5 py-1 rounded-lg">
                Standby
              </span>
            </div>
          </div>
        ) : null}

        {/* PERSISTENT VIDEO & SKELETON OVERLAY (Hidden with CSS when not active) */}
        <div className={`relative w-full h-full flex items-center justify-center bg-black ${!isCameraActive ? 'hidden' : ''}`}>
          {/* Mirrored video element via CSS scale-x-[-1] */}
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-cover scale-x-[-1]"
          />

          {/* Skeleton overlay canvas */}
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full object-cover pointer-events-none"
          />

          {/* Active Gesture Recognition HUD (Top-Left) */}
          <div className="absolute top-4 left-4 z-20 max-w-sm">
            {wsState !== 'connected' ? (
              <div className="bg-zinc-950/92 backdrop-blur-md rounded-xl p-3 shadow-2xl border border-amber-500/40">
                <div className="flex items-center gap-2 text-amber-400 text-xs font-semibold mb-1">
                  <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
                  <span>{isAiStudioPreview ? 'Backend only runs locally via run_app.bat' : 'Backend Not Connected'}</span>
                </div>
                <p className="text-[11px] text-zinc-400 leading-tight">
                  {isAiStudioPreview
                    ? 'Browser hand tracking runs fluently at 30+ FPS. Real-time LSTM classification requires running run_app.bat on your local machine.'
                    : `Hand tracking active locally.${wsCloseCode ? ` (Code: ${wsCloseCode})` : ''} Run run_app.bat to connect backend.`}
                </p>
              </div>
            ) : predictedSign && handsDetected > 0 ? (
              <div className={`bg-zinc-950/90 backdrop-blur-md rounded-xl p-3 shadow-2xl transition-all border ${
                statusMode === 'recognised' ? 'border-emerald-500/60 shadow-emerald-950/40' : 'border-cyan-500/40 shadow-black/50'
              }`}>
                <div className="flex items-center justify-between gap-4 mb-1">
                  <span className={`text-[10px] font-bold tracking-wider font-mono uppercase ${
                    statusMode === 'recognised' ? 'text-emerald-400' : 'text-cyan-400'
                  }`}>
                    {statusMode === 'recognised' ? 'RECOGNISED' : 'PREDICTING'}
                  </span>
                  <span className={`text-sm font-bold font-mono ${
                    statusMode === 'recognised' ? 'text-emerald-300' : 'text-cyan-300'
                  }`}>
                    {Math.round(predictedConfidence * 100)}%
                  </span>
                </div>

                <div className="text-2xl font-black text-white tracking-wider font-mono">
                  {predictedSign.toUpperCase()}
                </div>

                {/* Accent underline */}
                <div className={`w-full h-1 rounded-full my-1.5 ${
                  statusMode === 'recognised' ? 'bg-emerald-500' : 'bg-cyan-500'
                }`} />

                {/* Stability Progress Bar */}
                <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-75 ${
                      statusMode === 'recognised' ? 'bg-emerald-400' : 'bg-cyan-400'
                    }`}
                    style={{ width: `${Math.min(100, Math.max(8, stableProgress * 100))}%` }}
                  />
                </div>
              </div>
            ) : null}
          </div>

          {/* STATUS PANEL (Bottom Bar): All measured values, no hardcoded claims */}
          <div className="absolute bottom-4 inset-x-4 z-20 flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-300 bg-zinc-950/85 backdrop-blur-md px-3.5 py-2 rounded-xl border border-zinc-800/80 shadow-lg">
            {/* Left: Hand Detection & Buffer */}
            <div className="flex flex-wrap items-center gap-2.5">
              {handsDetected === 0 ? (
                <span className="flex items-center gap-1.5 text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-lg font-medium">
                  <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                  <span>No hand detected</span>
                </span>
              ) : (
                <span className="flex items-center gap-1.5 text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-lg font-medium">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  <span>{handsDetected} hand{handsDetected > 1 ? 's' : ''} detected</span>
                </span>
              )}

              {/* Buffer Size */}
              <div className="flex items-center gap-1 text-zinc-400 bg-zinc-900/80 px-2 py-0.5 rounded-lg border border-zinc-800">
                <span className="text-zinc-500">Buffer:</span>
                <span className="font-mono text-zinc-200 font-semibold">{sequenceBuffer}/20</span>
              </div>

              {/* Total Frames Processed */}
              <div className="flex items-center gap-1.5 text-zinc-400">
                <Layers className="w-3.5 h-3.5 text-blue-400" />
                <span>Frames: <strong className="font-mono text-white">{resultsReceived}</strong></span>
              </div>
            </div>

            {/* Right: Measured FPS & Measured Latency */}
            <div className="flex items-center gap-3 text-zinc-400">
              <div className="flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-emerald-400" />
                <span>FPS: <strong className="font-mono text-white font-bold">{measuredFps}</strong></span>
              </div>

              {measuredLatencyMs !== null && (
                <div>
                  <span>Latency: <strong className="font-mono text-white">{measuredLatencyMs}ms</strong></span>
                </div>
              )}

              <div className="flex items-center gap-1.5 bg-zinc-900/80 px-2 py-0.5 rounded-lg border border-zinc-800">
                <span className={`w-2 h-2 rounded-full ${wsState === 'connected' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                <span className="text-[10px] font-medium font-mono">
                  {wsState === 'connected' ? 'Backend Live' : 'Backend Disconnected'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* DIAGNOSTICS PANEL (Visible by default, shows every state and error without silent failures) */}
      {showDiagnostics && (
        <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-4 shadow-xl">
          <div className="flex items-center justify-between mb-3 border-b border-zinc-800 pb-2">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-emerald-400" />
              <h4 className="text-xs font-semibold text-white uppercase tracking-wider">
                System Diagnostics (No Silent Failures)
              </h4>
            </div>
            <span className="text-[10px] font-mono text-zinc-500">
              Auto-updating
            </span>
          </div>

          {/* Diagnostic Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 font-mono text-xs">
            {/* 1. MediaPipe Status */}
            <div className="bg-zinc-950/60 p-2.5 rounded-xl border border-zinc-800/80">
              <span className="text-[10px] text-zinc-500 uppercase block mb-1">MediaPipe (Local)</span>
              <div className="flex items-center gap-1.5">
                {mpLoaded ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span className="text-emerald-400 font-semibold">Loaded: YES</span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-4 h-4 text-red-400 shrink-0" />
                    <span className="text-red-400 font-semibold">Loaded: NO</span>
                  </>
                )}
              </div>
              {mpError && (
                <p className="text-[9px] text-red-400 mt-1 break-all leading-tight">
                  {mpError}
                </p>
              )}
            </div>

            {/* 2. Video Feed */}
            <div className="bg-zinc-950/60 p-2.5 rounded-xl border border-zinc-800/80">
              <span className="text-[10px] text-zinc-500 uppercase block mb-1">Video Stream</span>
              <div className="text-zinc-200 font-semibold">{videoResolution}</div>
              <div className="text-[10px] text-zinc-400 mt-0.5">
                State: {videoReadyState} ({getReadyStateName(videoReadyState)})
              </div>
            </div>

            {/* 3. MediaPipe Ingestion */}
            <div className="bg-zinc-950/60 p-2.5 rounded-xl border border-zinc-800/80">
              <span className="text-[10px] text-zinc-500 uppercase block mb-1">MediaPipe Pipeline</span>
              <div className="text-zinc-200">Sent: <strong className="text-white">{framesSent}</strong></div>
              <div className="text-[10px] text-zinc-400 mt-0.5">
                Results: <strong className="text-emerald-400">{resultsReceived}</strong> (Hand: {resultsWithHand})
              </div>
            </div>

            {/* 4. WebSocket State */}
            <div className="bg-zinc-950/60 p-2.5 rounded-xl border border-zinc-800/80">
              <span className="text-[10px] text-zinc-500 uppercase block mb-1">WebSocket (ws://)</span>
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${
                  wsState === 'connected' ? 'bg-emerald-400' : wsState === 'connecting' ? 'bg-amber-400' : 'bg-red-400'
                }`} />
                <span className={`font-semibold capitalize ${
                  wsState === 'connected' ? 'text-emerald-400' : wsState === 'connecting' ? 'text-amber-400' : 'text-zinc-400'
                }`}>
                  {wsState}
                </span>
              </div>
              <div className="text-[10px] text-zinc-400 mt-0.5">
                Sent: {wsMessagesSent} • Recv: {wsMessagesReceived}
              </div>
              {wsCloseCode !== null && wsState !== 'connected' && (
                <div className="text-[9px] text-amber-400 mt-1 font-mono break-all leading-tight">
                  Code {wsCloseCode}: {wsCloseReason || 'Unreachable'}
                </div>
              )}
              {isAiStudioPreview && wsState !== 'connected' && (
                <div className="text-[9px] text-cyan-400 mt-1 font-medium leading-tight">
                  Backend only runs locally via run_app.bat
                </div>
              )}
            </div>

            {/* 5. Metrics */}
            <div className="bg-zinc-950/60 p-2.5 rounded-xl border border-zinc-800/80">
              <span className="text-[10px] text-zinc-500 uppercase block mb-1">Measured Performance</span>
              <div className="text-zinc-200">
                FPS: <strong className={measuredFps >= 25 ? 'text-emerald-400' : 'text-amber-400'}>{measuredFps}</strong>
              </div>
              <div className="text-[10px] text-zinc-400 mt-0.5">
                Latency: <strong className="text-white">{measuredLatencyMs !== null ? `${measuredLatencyMs}ms` : 'N/A'}</strong>
              </div>
            </div>
          </div>

          {/* Parity Check Mode Panel */}
          <div className="mt-3 pt-3 border-t border-zinc-800">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Scale className="w-4 h-4 text-purple-400" />
                <h5 className="text-xs font-semibold text-purple-300 uppercase tracking-wider">
                  realtime.py Parity Verification
                </h5>
              </div>
              <button
                onClick={() => setParityMode(!parityMode)}
                className={`text-[10px] font-mono px-2.5 py-1 rounded-lg border font-semibold transition-all ${
                  parityMode
                    ? 'bg-purple-600/30 border-purple-500/60 text-purple-200'
                    : 'bg-zinc-800 border-zinc-700 text-zinc-400 hover:text-white'
                }`}
              >
                {parityMode ? 'Testing 2x/sec (ACTIVE)' : 'Enable Parity Mode'}
              </button>
            </div>

            {parityMode ? (
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-2.5 font-mono text-xs">
                <div className="bg-zinc-950/70 p-2.5 rounded-xl border border-zinc-800/80">
                  <span className="text-[10px] text-zinc-500 uppercase block">Max Abs Difference</span>
                  <div className="text-zinc-200 font-bold mt-0.5">
                    {parityResult ? (
                      <span className={parityResult.max_abs_diff < 0.05 ? 'text-emerald-400' : 'text-amber-400'}>
                        {parityResult.max_abs_diff.toFixed(5)}
                      </span>
                    ) : wsState === 'connected' ? (
                      <span className="text-zinc-400">Comparing...</span>
                    ) : (
                      <span className="text-zinc-500">Awaiting Backend</span>
                    )}
                  </div>
                  <span className="text-[9px] text-zinc-500">126-vector parity</span>
                </div>

                <div className="bg-zinc-950/70 p-2.5 rounded-xl border border-zinc-800/80">
                  <span className="text-[10px] text-zinc-500 uppercase block">Python MediaPipe</span>
                  <div className="text-zinc-200 font-semibold mt-0.5">
                    {parityResult ? (parityResult.py_label || 'None') : '—'}
                  </div>
                  <span className="text-[9px] text-zinc-500">
                    {parityResult ? `${parityResult.py_hands_detected} hand${parityResult.py_hands_detected > 1 ? 's' : ''} detected` : 'via Python cv2.flip'}
                  </span>
                </div>

                <div className="bg-zinc-950/70 p-2.5 rounded-xl border border-zinc-800/80">
                  <span className="text-[10px] text-zinc-500 uppercase block">Browser MediaPipe</span>
                  <div className="text-zinc-200 font-semibold mt-0.5">
                    {parityResult ? (parityResult.browser_label || 'None') : (predictedSign || 'None')}
                  </div>
                  <span className="text-[9px] text-zinc-500">via JS selfieMode: true</span>
                </div>

                <div className="bg-zinc-950/70 p-2.5 rounded-xl border border-zinc-800/80">
                  <span className="text-[10px] text-zinc-500 uppercase block">Label Agreement</span>
                  <div className="mt-0.5">
                    {parityResult ? (
                      parityResult.labels_match ? (
                        <span className="text-emerald-400 font-bold flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> MATCH: YES
                        </span>
                      ) : (
                        <span className="text-amber-400 font-bold flex items-center gap-1">
                          <AlertCircle className="w-3.5 h-3.5" /> DIVERGENT
                        </span>
                      )
                    ) : (
                      <span className="text-zinc-500">Standing by</span>
                    )}
                  </div>
                  <span className="text-[9px] text-zinc-500">Python vs Browser prediction</span>
                </div>
              </div>
            ) : (
              <p className="text-[11px] text-zinc-400 leading-relaxed font-sans">
                When enabled, captures a 320×240 JPEG frame ~2 times per second and compares the browser&apos;s 126-value landmark vector directly against Python MediaPipe running in <code className="text-purple-300 font-mono">backend.py</code>.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
