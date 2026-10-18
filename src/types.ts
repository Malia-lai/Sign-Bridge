export interface Landmark {
  x: number;
  y: number;
  z: number;
}

export interface HandData {
  landmarks: Landmark[];
  label: 'Right' | 'Left';
  score: number;
}

export interface GestureSequence {
  id: string;
  label: string;
  timestamp: number;
  frames: number[][]; // 20 frames x 126 coordinates
}

export interface GestureStat {
  label: string;
  count: number;
  key?: string;
  description?: string;
}

export interface RecognitionResult {
  label: string;
  confidence: number;
  details?: string;
}
