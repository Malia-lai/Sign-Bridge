export interface Landmark3D {
  x: number;
  y: number;
  z: number;
}

export interface StageTimings {
  decode: number;
  mediapipe: number;
  lstm: number;
  total: number;
}

export interface ParityResult {
  type: 'parity_result';
  max_abs_diff: number;
  py_label: string;
  browser_label: string;
  labels_match: boolean;
  py_hands_detected: number;
  timestamp: number;
  error?: string;
}

export interface DetectionResult {
  detected_label: string;
  label?: string;
  display_label: string;
  confidence: number;
  stable_progress: number;
  history_words: string[];
  history_display: string[];
  sentence: string;
  probabilities: Record<string, number>;
  raw_probabilities?: Record<string, number>;
  landmarks?: Landmark3D[][];
  hands_count: number;
  sequence_buffer?: number;
  buffer_size?: number;
  sequence_target?: number;
  speak_word?: string | null;
  latency_ms: number;
  candidate_label?: string;
  candidate_display?: string;
  candidate_confidence?: number;
  status_mode?: 'predicting' | 'recognised' | string;
  timings?: StageTimings;
  debug_frame?: string | null;
  error?: string;
  type?: string;
}

export interface UniqueGesture {
  raw_label: string;
  display_name: string;
  count: number;
}

export interface DatabaseInfo {
  labels_loaded: boolean;
  landmarks_loaded: boolean;
  labels_shape: number[] | null;
  landmarks_shape: number[] | null;
  shapes_match: boolean;
  has_nan?: boolean;
  min_val?: number;
  max_val?: number;
  non_zero_pct?: number;
  total_samples: number;
  unique_words: UniqueGesture[];
}

export interface Frame3D {
  frame_index: number;
  left_hand: Landmark3D[];
  right_hand: Landmark3D[];
}

export interface SequenceData {
  raw_label: string;
  display_name: string;
  sample_index?: number;
  frames_count?: number;
  active_frames_count?: number;
  has_usable_data?: boolean;
  frames: Frame3D[];
}

export interface HealthCheckResponse {
  status: string;
  backend_dir: string;
  files: Record<string, boolean>;
  missing_files: string[];
  shapes_match: boolean;
  labels_shape: number[] | null;
  landmarks_shape: number[] | null;
  has_nan?: boolean;
  min_val?: number;
  max_val?: number;
  non_zero_pct?: number;
  total_unique_words: number;
}

export interface ServerStatus {
  status: string;
  model_loaded: boolean;
  classes_count: number;
  classes: string[];
  classes_display: string[];
  threshold: number;
  stable_duration: number;
  cooldown: number;
  shapes_match: boolean;
  labels_shape: number[] | null;
  landmarks_shape: number[] | null;
  missing_files: string[];
}
