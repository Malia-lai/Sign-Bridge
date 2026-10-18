// Audio Service with guaranteed Web Audio chime & bulletproof SpeechSynthesis
class AudioService {
  private audioCtx: AudioContext | null = null;
  public isUnlocked: boolean = false;
  private voicesLoaded: boolean = false;
  private voices: SpeechSynthesisVoice[] = [];
  private lastSpokenWord: string = '';
  private lastSpokenTime: number = 0;
  // Keep persistent reference to prevent V8 garbage collection mid-speech
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private keepAliveInterval: any = null;

  // Translations for natural pronunciation in French
  private frenchTranslations: Record<string, string> = {
    hello: 'Bonjour',
    peace: 'Paix',
    love: 'Amour',
    eat: 'Manger',
    sleep: 'Dormir',
    I: 'Moi',
    not: 'Non',
    hate: 'Déteste',
    shawarma: 'Chawarma',
    Shawarma: 'Chawarma',
    tacos: 'Tacos',
  };

  // Natural pronunciation in English
  private englishTranslations: Record<string, string> = {
    hello: 'Hello',
    peace: 'Peace',
    love: 'Love',
    eat: 'Eat',
    sleep: 'Sleep',
    I: 'I',
    not: 'No',
    hate: 'Thumbs down',
    shawarma: 'Shawarma',
    Shawarma: 'Shawarma',
    tacos: 'Tacos',
  };

  constructor() {
    if (typeof window !== 'undefined') {
      this.initVoices();

      // Listen on all user interaction events to unlock audio context immediately
      const unlockEvents = ['click', 'keydown', 'touchstart', 'mousedown', 'pointerdown'];
      const unlockHandler = () => {
        this.unlockAudio();
      };

      unlockEvents.forEach(evt => {
        window.addEventListener(evt, unlockHandler, { passive: true });
      });

      // Keepalive timer for Chromium speech synthesis bug (freezes after 15s)
      this.keepAliveInterval = setInterval(() => {
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
          if (window.speechSynthesis.speaking && window.speechSynthesis.paused) {
            window.speechSynthesis.resume();
          }
        }
      }, 3000);
    }
  }

  private initVoices() {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;

    const load = () => {
      try {
        const list = window.speechSynthesis.getVoices();
        if (list && list.length > 0) {
          this.voices = list;
          this.voicesLoaded = true;
        }
      } catch {}
    };

    load();
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = load;
    }
  }

  // Ensures AudioContext is active and not suspended by browser autoplay policy
  public unlockAudio(): boolean {
    try {
      if (!this.audioCtx) {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        if (AudioContextClass) {
          this.audioCtx = new AudioContextClass();
        }
      }

      if (this.audioCtx && this.audioCtx.state === 'suspended') {
        this.audioCtx.resume().catch(() => {});
      }

      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.resume();
      }

      this.isUnlocked = true;
      return true;
    } catch {
      return false;
    }
  }

  // Melodic pleasant chime played via Web Audio API (Guaranteed audible even if TTS blocked)
  public playChime(type: 'success' | 'detect' | 'click' = 'detect') {
    try {
      this.unlockAudio();
      if (!this.audioCtx) return;

      const ctx = this.audioCtx;
      if (ctx.state === 'suspended') {
        ctx.resume().catch(() => {});
      }

      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'detect') {
        // Melodic upward chime: E5 -> B5 (rich & clear)
        osc.type = 'sine';
        osc.frequency.setValueAtTime(659.25, now); // E5
        osc.frequency.exponentialRampToValueAtTime(987.77, now + 0.10); // B5
        gain.gain.setValueAtTime(0.30, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.30);
        osc.start(now);
        osc.stop(now + 0.32);
      } else if (type === 'success') {
        // Major third chord arpeggio
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(523.25, now); // C5
        osc.frequency.setValueAtTime(659.25, now + 0.08); // E5
        osc.frequency.setValueAtTime(783.99, now + 0.16); // G5
        gain.gain.setValueAtTime(0.35, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
        osc.start(now);
        osc.stop(now + 0.46);
      } else {
        // Subtle click
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, now);
        gain.gain.setValueAtTime(0.20, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
        osc.start(now);
        osc.stop(now + 0.09);
      }
    } catch (e) {
      console.warn("Chime audio context:", e);
    }
  }

  // Speak word with speech synthesis + audio chime
  public speak(
    word: string,
    options: {
      lang?: 'fr' | 'en';
      rate?: number;
      force?: boolean;
    } = {}
  ) {
    const now = Date.now();
    const minCooldown = 1500; // ms

    if (!options.force && word === this.lastSpokenWord && now - this.lastSpokenTime < minCooldown) {
      return;
    }

    this.lastSpokenWord = word;
    this.lastSpokenTime = now;

    // 1. Play auditory chime confirmation
    this.playChime('detect');

    // 2. Synthesize speech
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;

    try {
      this.unlockAudio();

      // Clear any stuck/frozen speech queue in Chromium
      window.speechSynthesis.cancel();
      window.speechSynthesis.resume();

      const lang = options.lang || 'en';
      const textToSpeak = lang === 'fr' 
        ? (this.frenchTranslations[word] || word) 
        : (this.englishTranslations[word] || word);

      const utterance = new SpeechSynthesisUtterance(textToSpeak);
      utterance.rate = options.rate || 1.0;
      utterance.pitch = 1.05;
      utterance.volume = 1.0;

      // Select appropriate voice if available (priority to English or French native voices)
      if (this.voices.length > 0) {
        const targetPrefix = lang === 'fr' ? 'fr' : 'en';
        const bestVoice = this.voices.find(
          (v) => v.lang.toLowerCase().startsWith(targetPrefix) && 
                (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha') || v.name.includes('David') || v.name.includes('Zira') || v.name.includes('Hortense'))
        ) || this.voices.find(
          (v) => v.lang.toLowerCase().startsWith(targetPrefix)
        );
        if (bestVoice) {
          utterance.voice = bestVoice;
        }
      }

      utterance.lang = lang === 'fr' ? 'fr-FR' : 'en-US';

      // CRITICAL: Hold global reference to avoid V8 garbage collection mid-speech
      this.currentUtterance = utterance;
      (window as any)._activeSpeechUtterance = utterance;

      utterance.onend = () => {
        this.currentUtterance = null;
        (window as any)._activeSpeechUtterance = null;
      };

      utterance.onerror = (err) => {
        console.warn("SpeechSynthesis error:", err);
        this.currentUtterance = null;
        (window as any)._activeSpeechUtterance = null;
      };

      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn("Speech synthesis notice:", e);
    }
  }

  // Speak a full sentence
  public speakSentence(text: string, lang: 'fr' | 'en' = 'fr') {
    if (!text || typeof window === 'undefined' || !('speechSynthesis' in window)) return;

    try {
      this.unlockAudio();
      this.playChime('click');

      window.speechSynthesis.cancel();
      window.speechSynthesis.resume();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.95;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      utterance.lang = lang === 'fr' ? 'fr-FR' : 'en-US';

      if (this.voices.length > 0) {
        const targetPrefix = lang === 'fr' ? 'fr' : 'en';
        const matchingVoice = this.voices.find(
          (v) => v.lang.toLowerCase().startsWith(targetPrefix)
        );
        if (matchingVoice) {
          utterance.voice = matchingVoice;
        }
      }

      this.currentUtterance = utterance;
      (window as any)._activeSpeechUtterance = utterance;

      utterance.onend = () => {
        this.currentUtterance = null;
        (window as any)._activeSpeechUtterance = null;
      };

      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn("SpeechSentence notice:", e);
    }
  }

  public testVoice(lang: 'fr' | 'en' = 'fr') {
    this.unlockAudio();
    this.playChime('success');
    this.speak('peace', { lang, force: true });
  }
}

export const audioService = new AudioService();
