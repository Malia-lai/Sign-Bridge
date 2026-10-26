import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { Camera, Sparkles, Volume2, VolumeX, AlertTriangle, Play, Pause, RotateCcw } from 'lucide-react';
import { UniqueGesture, SequenceData, HealthCheckResponse } from '../types';
import { fetchGestureSequence, fetchHealthCheck } from '../services/api';
import { speechService } from '../services/speech';

const HAND_CONNECTIONS: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17]
];

interface Simulator3DProps {
  isBackendConnected: boolean;
  uniqueWords: UniqueGesture[];
  onBackToCamera?: () => void;
  sentenceWords?: string[];
}

export const Simulator3D: React.FC<Simulator3DProps> = ({
  isBackendConnected,
  uniqueWords,
  onBackToCamera,
  sentenceWords = []
}) => {
  const [selectedGesture, setSelectedGesture] = useState<UniqueGesture | null>(null);
  const [sequenceData, setSequenceData] = useState<SequenceData | null>(null);
  const [loadingSequence, setLoadingSequence] = useState(false);
  const [healthData, setHealthData] = useState<HealthCheckResponse | null>(null);
  const [isMuted, setIsMuted] = useState(false);

  // Playback state
  const [currentFrame, setCurrentFrame] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [playSpeed, setPlaySpeed] = useState<number>(1.0);

  // Three.js refs
  const canvasHolderRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const handsGroupRef = useRef<THREE.Group | null>(null);
  const reqIdRef = useRef<number | null>(null);

  // 1. Fetch health stats on mount
  useEffect(() => {
    fetchHealthCheck().then((h) => {
      if (h) setHealthData(h);
    });
  }, [isBackendConnected]);

  // 2. Select initial gesture (prioritize 'peace' to match user screenshot, or first available)
  useEffect(() => {
    if (uniqueWords.length > 0 && !selectedGesture) {
      const peace = uniqueWords.find((w) => w.raw_label.toLowerCase() === 'peace');
      setSelectedGesture(peace || uniqueWords[0]);
    }
  }, [uniqueWords, selectedGesture]);

  // 3. Fetch sequence when gesture changes
  useEffect(() => {
    if (!selectedGesture) {
      setSequenceData(null);
      return;
    }

    setLoadingSequence(true);
    fetchGestureSequence(selectedGesture.raw_label)
      .then((seq) => {
        setSequenceData(seq);
        setCurrentFrame(0);
      })
      .catch((e) => {
        console.warn("Could not load sequence:", e);
      })
      .finally(() => setLoadingSequence(false));
  }, [selectedGesture]);

  // 4. Initialize Three.js scene with OrbitControls & ResizeObserver
  useEffect(() => {
    const container = canvasHolderRef.current;
    if (!container) return;

    const width = container.clientWidth || 720;
    const height = container.clientHeight || 480;

    const scene = new THREE.Scene();
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 50);
    camera.position.set(0, 0, 1.8);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0, 0, 0);
    controls.minDistance = 0.5;
    controls.maxDistance = 4.0;
    controlsRef.current = controls;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.3);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0x38bdf8, 1.8);
    dirLight1.position.set(5, 10, 7);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x22c55e, 1.2);
    dirLight2.position.set(-5, -5, -3);
    scene.add(dirLight2);

    // Hands group
    const handsGroup = new THREE.Group();
    scene.add(handsGroup);
    handsGroupRef.current = handsGroup;

    // Animation render loop
    const animate = () => {
      reqIdRef.current = requestAnimationFrame(animate);
      controls.update();
      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        rendererRef.current.render(sceneRef.current, cameraRef.current);
      }
    };
    animate();

    const handleResize = () => {
      if (!container || !rendererRef.current || !cameraRef.current) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w > 0 && h > 0) {
        cameraRef.current.aspect = w / h;
        cameraRef.current.updateProjectionMatrix();
        rendererRef.current.setSize(w, h);
      }
    };

    window.addEventListener('resize', handleResize);

    // ResizeObserver guarantees the canvas sizes properly even if previously hidden
    const ro = new ResizeObserver(() => {
      handleResize();
    });
    ro.observe(container);

    return () => {
      if (reqIdRef.current) cancelAnimationFrame(reqIdRef.current);
      window.removeEventListener('resize', handleResize);
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  // 5. Update 3D scene meshes per frame matching image_2a3eb444.png
  useEffect(() => {
    const handsGroup = handsGroupRef.current;
    if (!handsGroup || !sequenceData || !sequenceData.frames || sequenceData.frames.length === 0) return;

    while (handsGroup.children.length > 0) {
      const obj = handsGroup.children[0];
      handsGroup.remove(obj);
    }

    const frameIdx = Math.min(currentFrame, sequenceData.frames.length - 1);
    const frameObj = sequenceData.frames[frameIdx];
    if (!frameObj) return;

    const hasLeft = frameObj.left_hand && frameObj.left_hand.length === 21;
    const hasRight = frameObj.right_hand && frameObj.right_hand.length === 21;

    // Display scale factor
    const SCALE = 3.6;

    const renderHand = (
      landmarks: { x: number; y: number; z: number }[],
      xOffset: number
    ) => {
      if (!landmarks || landmarks.length !== 21) return;

      const wrist = landmarks[0];

      // Display-only transformation: subtract wrist, flip y, scale, and center vertically
      const pts3D = landmarks.map((lm) => {
        const dx = (lm.x - wrist.x) * SCALE + xOffset;
        const dy = -(lm.y - wrist.y) * SCALE - 0.22;
        const dz = -(lm.z - wrist.z) * SCALE;
        return new THREE.Vector3(dx, dy, dz);
      });

      // Joint geometries matching image_2a3eb444.png
      const intermediateGeom = new THREE.SphereGeometry(0.024, 16, 16);
      const keyLandmarkGeom = new THREE.SphereGeometry(0.042, 16, 16);

      // Intermediate joints: Light sky blue / white (#bae6fd / #e0f2fe)
      const intermediateMat = new THREE.MeshStandardMaterial({
        color: 0xbae6fd,
        roughness: 0.2,
        metalness: 0.7,
        emissive: 0x38bdf8,
        emissiveIntensity: 0.5
      });

      // Key landmark joints (fingertips: 4, 8, 12, 16, 20 & thumb CMC: 2): Bright Green (#22c55e)
      const keyLandmarkMat = new THREE.MeshStandardMaterial({
        color: 0x22c55e,
        roughness: 0.1,
        metalness: 0.8,
        emissive: 0x16a34a,
        emissiveIntensity: 0.85
      });

      pts3D.forEach((pt, idx) => {
        const isKeyLandmark = [4, 8, 12, 16, 20, 2].includes(idx);
        const mesh = new THREE.Mesh(
          isKeyLandmark ? keyLandmarkGeom : intermediateGeom,
          isKeyLandmark ? keyLandmarkMat : intermediateMat
        );
        mesh.position.copy(pt);
        handsGroup.add(mesh);
      });

      // Bone lines: vibrant sky blue / cyan (#38bdf8) matching image_2a3eb444.png
      const lineMat = new THREE.LineBasicMaterial({
        color: 0x38bdf8,
        linewidth: 3.5,
        transparent: true,
        opacity: 0.95
      });

      HAND_CONNECTIONS.forEach(([startIdx, endIdx]) => {
        const p1 = pts3D[startIdx];
        const p2 = pts3D[endIdx];
        const geom = new THREE.BufferGeometry().setFromPoints([p1, p2]);
        const line = new THREE.Line(geom, lineMat);
        handsGroup.add(line);
      });
    };

    if (hasLeft && hasRight) {
      renderHand(frameObj.left_hand, -0.45);
      renderHand(frameObj.right_hand, 0.45);
    } else if (hasLeft) {
      renderHand(frameObj.left_hand, 0.0);
    } else if (hasRight) {
      renderHand(frameObj.right_hand, 0.0);
    }
  }, [currentFrame, sequenceData]);

  // 6. Animation playback loop
  useEffect(() => {
    if (!isPlaying || !sequenceData || !sequenceData.frames || sequenceData.frames.length === 0) return;

    const intervalTime = Math.max(30, Math.floor(90 / playSpeed));
    const timer = setInterval(() => {
      setCurrentFrame((prev) => {
        const total = sequenceData.frames.length;
        if (total <= 1) return 0;
        return (prev + 1) % total;
      });
    }, intervalTime);

    return () => clearInterval(timer);
  }, [isPlaying, sequenceData, playSpeed]);

  const resetCamera = useCallback(() => {
    if (controlsRef.current && cameraRef.current) {
      cameraRef.current.position.set(0, 0, 1.8);
      controlsRef.current.target.set(0, 0, 0);
      controlsRef.current.update();
    }
  }, []);

  const toggleSound = () => {
    const nextMuted = !isMuted;
    setIsMuted(nextMuted);
    speechService.isMuted = nextMuted;
    if (!nextMuted && selectedGesture) {
      speechService.speak(selectedGesture.display_name);
    }
  };

  const framesCount = sequenceData?.frames?.length || 0;
  const hasUsableData = sequenceData?.has_usable_data ?? (framesCount > 0);

  // Check if current sign is already in the sentence history (matching image_2a3eb444.png)
  const isIgnoredInSentence = selectedGesture
    ? sentenceWords.some((w) => w.toLowerCase() === selectedGesture.raw_label.toLowerCase())
    : false;

  return (
    <div className="flex flex-col gap-3 w-full">
      {/* Top Header Bar matching image_2a3eb444.png */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-zinc-950/80 px-4 py-2.5 rounded-2xl border border-zinc-800/80">
        {/* Left: Mode Switch Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={onBackToCamera}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-xl text-xs font-semibold transition-all shadow-md shadow-blue-500/20 cursor-pointer"
          >
            <Camera className="w-4 h-4" />
            <span>Start Camera</span>
          </button>

          <button
            className="flex items-center gap-2 bg-purple-700/80 hover:bg-purple-700 text-white px-4 py-2 rounded-xl text-xs font-semibold transition-all border border-purple-500/30 shadow-md shadow-purple-600/20"
          >
            <Sparkles className="w-4 h-4 text-purple-200" />
            <span>3D Simulator</span>
          </button>
        </div>

        {/* Right: Sign Select Dropdown & Audio Toggle (Matches image_2a3eb444.png) */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-zinc-900/90 border border-zinc-700/60 rounded-xl px-3 py-1.5 shadow-sm">
            <span className="text-xs font-medium text-zinc-400">Sign:</span>
            <select
              value={selectedGesture?.raw_label || ''}
              onChange={(e) => {
                const found = uniqueWords.find((w) => w.raw_label === e.target.value);
                if (found) {
                  setSelectedGesture(found);
                  if (!isMuted) {
                    speechService.speak(found.display_name);
                  }
                }
              }}
              className="bg-transparent text-xs font-semibold text-white focus:outline-none cursor-pointer pr-1"
            >
              {uniqueWords.map((w) => (
                <option key={w.raw_label} value={w.raw_label} className="bg-zinc-900 text-white">
                  {w.display_name}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={toggleSound}
            className={`w-9 h-9 rounded-xl flex items-center justify-center border transition-all ${
              isMuted
                ? 'bg-zinc-800 text-zinc-500 border-zinc-700'
                : 'bg-blue-600/30 text-blue-400 border-blue-500/40 hover:bg-blue-600/50'
            }`}
            title={isMuted ? 'Unmute pronunciation' : 'Mute pronunciation'}
          >
            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Main 3D Viewport matching image_2a3eb444.png */}
      <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-3 flex flex-col relative overflow-hidden shadow-2xl">
        <div
          className="w-full h-[460px] rounded-xl overflow-hidden cursor-grab active:cursor-grabbing border border-zinc-900 bg-black relative"
          style={{
            backgroundImage: `
              linear-gradient(to right, rgba(255, 255, 255, 0.05) 1px, transparent 1px),
              linear-gradient(to bottom, rgba(255, 255, 255, 0.05) 1px, transparent 1px)
            `,
            backgroundSize: '40px 40px'
          }}
        >
          {/* Dedicated Three.js canvas container */}
          <div ref={canvasHolderRef} className="absolute inset-0 w-full h-full" />

          {/* Toast Notification matching image_2a3eb444.png */}
          <div className="absolute top-4 right-4 z-20 pointer-events-none transition-all">
            {isIgnoredInSentence ? (
              <div className="flex items-center gap-2 bg-amber-950/85 backdrop-blur-md border border-amber-600/60 text-amber-300 text-xs px-3.5 py-1.5 rounded-xl shadow-lg animate-in fade-in">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                <span>{selectedGesture?.display_name || 'peace'} ignored: already in the sentence</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 bg-zinc-900/80 backdrop-blur-md border border-zinc-700/60 text-zinc-300 text-xs px-3 py-1.5 rounded-xl shadow">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span>Showing: <strong className="text-white capitalize">{selectedGesture?.display_name || 'peace'}</strong></span>
              </div>
            )}
          </div>

          {/* Bottom Right Watermark matching image_2a3eb444.png */}
          <div className="absolute bottom-4 right-4 z-20 pointer-events-none">
            <span className="text-[11px] font-medium text-zinc-400 bg-zinc-900/80 backdrop-blur-md border border-zinc-800 px-3 py-1 rounded-lg">
              3D Gesture Simulator
            </span>
          </div>

          {/* Left Controls & Status */}
          <div className="absolute top-4 left-4 z-20 flex items-center gap-2 pointer-events-auto">
            <button
              onClick={resetCamera}
              className="text-xs text-zinc-400 hover:text-white flex items-center gap-1.5 bg-zinc-900/80 hover:bg-zinc-800 px-2.5 py-1.5 rounded-lg border border-zinc-800 transition-colors backdrop-blur-sm"
              title="Reset Orbit Camera"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Reset View</span>
            </button>
          </div>

          {loadingSequence && (
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center text-xs text-zinc-300 z-30 pointer-events-none">
              Loading 20-frame landmark sequence...
            </div>
          )}

          {!loadingSequence && !hasUsableData && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-950/90 text-center p-6 z-30 pointer-events-none">
              <AlertTriangle className="w-8 h-8 text-amber-400 mb-2" />
              <h3 className="text-sm font-semibold text-zinc-200">No data for this word</h3>
              <p className="text-xs text-zinc-500 mt-1 max-w-xs">
                This gesture in gesture_landmarks.npy does not have active recorded coordinates.
              </p>
            </div>
          )}
        </div>

        {/* Playback Controls & Scrubber */}
        <div className="mt-3 flex items-center gap-3 bg-zinc-900/50 p-2.5 rounded-xl border border-zinc-800/80">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            disabled={!hasUsableData}
            className="w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white flex items-center justify-center transition-colors shadow-sm cursor-pointer"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
          </button>

          <span className="text-xs font-mono text-zinc-400 w-16">
            Frame {(currentFrame + 1).toString().padStart(2, '0')} / {framesCount || 20}
          </span>

          <input
            type="range"
            min="0"
            max={Math.max(0, framesCount - 1)}
            value={currentFrame}
            disabled={!hasUsableData}
            onChange={(e) => {
              setCurrentFrame(parseInt(e.target.value, 10));
              setIsPlaying(false);
            }}
            className="flex-1 accent-blue-500 h-1.5 bg-zinc-800 rounded-lg cursor-pointer"
          />

          <div className="flex items-center gap-1 bg-zinc-800/80 p-0.5 rounded-lg border border-zinc-700/60 text-xs">
            {[0.5, 1.0, 2.0].map((s) => (
              <button
                key={s}
                onClick={() => setPlaySpeed(s)}
                className={`px-2 py-0.5 rounded cursor-pointer ${
                  playSpeed === s ? 'bg-blue-600 text-white font-medium' : 'text-zinc-400 hover:text-white'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        {/* Quick word selector chips */}
        <div className="mt-2.5 flex items-center gap-1.5 overflow-x-auto pb-1 pt-0.5 scrollbar-thin">
          {uniqueWords.map((item) => {
            const isSelected = selectedGesture?.raw_label === item.raw_label;
            return (
              <button
                key={item.raw_label}
                onClick={() => {
                  setSelectedGesture(item);
                  if (!isMuted) {
                    speechService.speak(item.display_name);
                  }
                }}
                className={`shrink-0 px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                    : 'bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-white border border-zinc-800/80'
                }`}
              >
                {item.display_name}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
