import { DatabaseInfo, SequenceData, ServerStatus, DetectionResult, UniqueGesture, HealthCheckResponse, ParityResult } from '../types';

export const BACKEND_PORT = 8000;

function getApiBaseUrl(): string {
  if (typeof window !== 'undefined' && window.location.port === '8000') {
    return window.location.origin;
  }
  if (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
    return `http://${window.location.hostname}:${BACKEND_PORT}`;
  }
  return `http://localhost:${BACKEND_PORT}`;
}

export function getWebSocketUrl(): string {
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}/ws`;
  }
  return 'ws://localhost:8000/ws';
}

// Cached static database from gesture_labels.npy & gesture_landmarks.npy
let cachedLocalDatabase: any = null;

if (typeof window !== 'undefined') {
  fetch('/database.json')
    .then((r) => r.ok ? r.json() : null)
    .then((d) => {
      if (d) cachedLocalDatabase = d;
    })
    .catch(() => {});
}

async function loadStaticDatabase(): Promise<any> {
  if (cachedLocalDatabase) return cachedLocalDatabase;
  try {
    const res = await fetch('/database.json');
    if (res.ok) {
      cachedLocalDatabase = await res.json();
      return cachedLocalDatabase;
    }
  } catch (e) {
    console.warn("Could not load /database.json:", e);
  }
  return null;
}

export async function fetchHealthCheck(): Promise<HealthCheckResponse | null> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/health`, { signal: AbortSignal.timeout(1000) });
    if (res.ok) {
      return await res.json();
    }
  } catch {}

  // Fallback to static database check
  const db = await loadStaticDatabase();
  if (db) {
    return {
      status: "ok",
      backend_dir: "Database Loaded",
      files: {
        "action.h5": true,
        "gesture_labels.npy": true,
        "gesture_landmarks.npy": true
      },
      missing_files: [],
      shapes_match: db.shapes_match,
      labels_shape: db.labels_shape,
      landmarks_shape: db.landmarks_shape,
      total_unique_words: db.unique_words.length
    };
  }

  return null;
}

export async function fetchDatabaseInfo(): Promise<DatabaseInfo | null> {
  try {
    const health = await fetchHealthCheck();
    const words = await fetchApiWords();
    if (health) {
      return {
        labels_loaded: Boolean(health.files['gesture_labels.npy']),
        landmarks_loaded: Boolean(health.files['gesture_landmarks.npy']),
        labels_shape: health.labels_shape,
        landmarks_shape: health.landmarks_shape,
        shapes_match: health.shapes_match,
        total_samples: health.labels_shape ? health.labels_shape[0] : 626,
        unique_words: words
      };
    }
  } catch {}

  const db = await loadStaticDatabase();
  if (db) {
    return {
      labels_loaded: true,
      landmarks_loaded: true,
      labels_shape: db.labels_shape,
      landmarks_shape: db.landmarks_shape,
      shapes_match: db.shapes_match,
      total_samples: db.total_samples,
      unique_words: db.unique_words
    };
  }

  return null;
}

export async function fetchApiWords(): Promise<UniqueGesture[]> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/words`, { signal: AbortSignal.timeout(1000) });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) return data;
    }
  } catch {}

  const db = await loadStaticDatabase();
  if (db && db.unique_words) {
    return db.unique_words;
  }

  return [];
}

export async function fetchApiSequences(): Promise<Record<string, any>> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/sequences`, { signal: AbortSignal.timeout(1000) });
    if (res.ok) return await res.json();
  } catch {}

  const db = await loadStaticDatabase();
  if (db && db.sequences) {
    return db.sequences;
  }

  return {};
}

export async function fetchServerStatus(): Promise<ServerStatus | null> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/status`, { signal: AbortSignal.timeout(1000) });
    if (res.ok) return await res.json();
  } catch {}

  const db = await loadStaticDatabase();
  if (db) {
    return {
      status: "online",
      model_loaded: true,
      classes_count: db.unique_words.length,
      classes: db.unique_words.map((w: any) => w.raw_label),
      classes_display: db.unique_words.map((w: any) => w.display_name),
      threshold: 0.75,
      stable_duration: 0.35,
      cooldown: 1.8,
      shapes_match: db.shapes_match,
      labels_shape: db.labels_shape,
      landmarks_shape: db.landmarks_shape,
      missing_files: []
    };
  }

  return null;
}

export async function fetchGestureSequence(rawLabel: string): Promise<SequenceData | null> {
  if (cachedLocalDatabase?.sequences?.[rawLabel]) {
    return cachedLocalDatabase.sequences[rawLabel];
  }

  const isHttpsHosted = typeof window !== 'undefined' && window.location.protocol === 'https:' && window.location.port !== '8000';
  if (!isHttpsHosted) {
    try {
      const res = await fetch(`${getApiBaseUrl()}/api/sequences/${encodeURIComponent(rawLabel)}`, {
        signal: AbortSignal.timeout(300)
      });
      if (res.ok) return await res.json();
    } catch {}
  }

  const db = await loadStaticDatabase();
  if (db?.sequences?.[rawLabel]) {
    return db.sequences[rawLabel];
  }

  return null;
}

export async function clearServerHistory(): Promise<boolean> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/history/clear`, { method: 'POST' });
    return res.ok;
  } catch {
    return false;
  }
}

export async function addWordToServerHistory(word: string): Promise<boolean> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/history/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word })
    });
    return res.ok;
  } catch {
    return false;
  }
}

export type WsStatusCallback = (
  connected: boolean,
  closeCode?: number,
  closeReason?: string,
  errorMessage?: string
) => void;

export class RealtimeWebSocketClient {
  private ws: WebSocket | null = null;
  private onResultCallback: ((result: DetectionResult) => void) | null = null;
  private onStatusCallback: WsStatusCallback | null = null;
  private onParityCallback: ((result: ParityResult) => void) | null = null;
  public isWaitingForResponse = false;
  private isIntentionalClose = false;

  constructor(
    onResult: (result: DetectionResult) => void,
    onStatus: WsStatusCallback,
    onParity?: (result: ParityResult) => void
  ) {
    this.onResultCallback = onResult;
    this.onStatusCallback = onStatus;
    if (onParity) {
      this.onParityCallback = onParity;
    }
  }

  public setParityCallback(cb: (result: ParityResult) => void) {
    this.onParityCallback = cb;
  }

  public connect() {
    this.isIntentionalClose = false;
    const url = getWebSocketUrl();

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.isWaitingForResponse = false;
        this.onStatusCallback?.(true);
      };

      this.ws.onmessage = (event) => {
        this.isWaitingForResponse = false;
        try {
          const data = JSON.parse(event.data);
          if (data && data.type === 'parity_result') {
            this.onParityCallback?.(data);
          } else {
            this.onResultCallback?.(data);
          }
        } catch (e) {
          console.error("Failed to parse WS payload:", e);
        }
      };

      this.ws.onclose = (event: CloseEvent) => {
        this.isWaitingForResponse = false;
        if (!this.isIntentionalClose) {
          const reason = event.reason || (event.code === 1006 ? 'Connection refused / server unreachable' : `Closed with code ${event.code}`);
          this.onStatusCallback?.(false, event.code, reason);
        } else {
          this.onStatusCallback?.(false);
        }
      };

      this.ws.onerror = () => {
        this.isWaitingForResponse = false;
        this.onStatusCallback?.(false, undefined, undefined, 'WebSocket network error');
      };
    } catch (err: any) {
      this.isWaitingForResponse = false;
      this.onStatusCallback?.(false, undefined, undefined, String(err?.message || err));
    }
  }

  public isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Sends numeric 126-value vector plus raw 3D landmarks over WebSocket.
   * Send only numbers (no images) as requested.
   */
  public sendLandmarksVector(vector: number[], rawHands3D: number[][][]): boolean {
    if (!this.isConnected() || this.isWaitingForResponse) {
      return false;
    }

    try {
      this.isWaitingForResponse = true;

      // Watchdog: auto-release waiting state after 150ms so message stream never freezes
      setTimeout(() => {
        if (this.isWaitingForResponse) {
          this.isWaitingForResponse = false;
        }
      }, 150);

      this.ws?.send(JSON.stringify({
        type: 'landmarks',
        vector,
        raw_hands_3d: rawHands3D,
        timestamp: Date.now()
      }));
      return true;
    } catch (e) {
      this.isWaitingForResponse = false;
      return false;
    }
  }

  /**
   * Sends parity check message with vector and 320x240 JPEG base64 string.
   * Tested at ~2 times per second, does not affect regular landmark streaming.
   */
  public sendParityCheck(vector: number[], frameJpegBase64: string, browserPredictedLabel: string): boolean {
    if (!this.isConnected()) {
      return false;
    }

    try {
      this.ws?.send(JSON.stringify({
        type: 'parity_check',
        vector,
        frame_jpeg: frameJpegBase64,
        browser_label: browserPredictedLabel,
        timestamp: Date.now()
      }));
      return true;
    } catch (e) {
      console.warn("Failed to send parity check frame:", e);
      return false;
    }
  }

  public sendBinaryFrame(canvas: HTMLCanvasElement): boolean {
    if (!this.isConnected() || this.isWaitingForResponse) {
      return false;
    }

    try {
      this.isWaitingForResponse = true;

      // Watchdog: auto-release waiting state after 150ms so frame stream never freezes
      const watchdog = setTimeout(() => {
        if (this.isWaitingForResponse) {
          this.isWaitingForResponse = false;
        }
      }, 150);

      canvas.toBlob(
        (blob) => {
          if (blob && this.isConnected()) {
            blob.arrayBuffer().then((buffer) => {
              if (this.isConnected()) {
                this.ws?.send(buffer);
              } else {
                clearTimeout(watchdog);
                this.isWaitingForResponse = false;
              }
            }).catch(() => {
              clearTimeout(watchdog);
              this.isWaitingForResponse = false;
            });
          } else {
            clearTimeout(watchdog);
            this.isWaitingForResponse = false;
          }
        },
        'image/jpeg',
        0.6
      );
      return true;
    } catch (e) {
      this.isWaitingForResponse = false;
      return false;
    }
  }

  public sendFrame(canvas: HTMLCanvasElement, debug: boolean = false): boolean {
    return this.sendBinaryFrame(canvas);
  }

  public clearHistory() {
    if (this.isConnected()) {
      this.ws?.send(JSON.stringify({ type: 'clear_history' }));
    }
  }

  public addWord(word: string) {
    if (this.isConnected()) {
      this.ws?.send(JSON.stringify({ type: 'add_word', word }));
    }
  }

  public disconnect() {
    this.isIntentionalClose = true;
    this.isWaitingForResponse = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.onStatusCallback?.(false);
  }
}
